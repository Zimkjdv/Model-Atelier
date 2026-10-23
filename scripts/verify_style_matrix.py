"""One fixed LoRA stack/strength/seed/subject; loading is separate from quality."""

import argparse
from backend import experiment_plans
from scripts import convert_pixel_lora, verify_local_generation as base
from scripts.verify_multi_lora import StyleAcceptance, MODEL, STYLE, LCM

PIXEL = convert_pixel_lora.manifest()
SEEDS = ('9007199254740993', '18446744073709551615')
# Each tuple preserves the exact order, MODEL strength and CLIP strength.
PROFILES = {
    'baseline': (),
    'pixel-half': ((PIXEL, 0.5, 1.0),),
    'pixel': ((PIXEL, 1.0, 1.0),),
    'pixel-clip-half': ((PIXEL, 1.0, 0.5),),
    'ikea-pixel': ((STYLE, 1.0, 1.0), (PIXEL, 1.0, 1.0)),
    'pixel-ikea': ((PIXEL, 1.0, 1.0), (STYLE, 1.0, 1.0)),
    'lcm': ((LCM, 1.0, 0.0),),
    'lcm-pixel': ((LCM, 1.0, 0.0), (PIXEL, 1.0, 1.0)),
    'pixel-lcm': ((PIXEL, 1.0, 1.0), (LCM, 1.0, 0.0)),
    'lcm-ikea-pixel': ((LCM, 1.0, 0.0), (STYLE, 1.0, 1.0), (PIXEL, 1.0, 1.0)),
}
SUBJECTS = ('anime-portrait', 'stuffed-bear')
BEAR_PROMPT = 'pixel art, one stuffed teddy bear, brown fur, red scarf, sitting, full body, white background, bold outlines, flat colors'


class MatrixAcceptance(StyleAcceptance):
    profile = 'pixel'
    seed = SEEDS[0]
    subject = 'anime-portrait'

    def __init__(self, *args, **kwargs):
        self.suite = experiment_plans.suite('anime-illustration')
        super().__init__(*args, **kwargs)
        if self.checkpoint != MODEL['filename']:
            raise ValueError('Pinned Animagine checkpoint required')

    def expected_settings(self):
        case = next(v for v in self.suite['cases'] if v['id'] == 'anime-portrait')
        prompt = 'pixel art, ' + case['prompt'] if self.subject == 'anime-portrait' else BEAR_PROMPT
        accelerated = any(m is LCM for m, _, _ in PROFILES[self.profile])
        return base.settings(self.engine, self.checkpoint) | dict(
            title=f'L01 / {self.subject} / {self.profile} / {self.seed}'[:100],
            prompt=prompt,
            negative_prompt='blurry, low quality, text, watermark',
            seed=self.seed,
            width=1024,
            height=1024,
            steps=8 if accelerated else 28,
            cfg=1.0 if accelerated else 5.0,
            sampler_name='lcm' if accelerated else 'euler_ancestral',
            scheduler='sgm_uniform' if accelerated else 'normal',
            loras=[
                dict(name=m['filename'], enabled=True, strength_model=model, strength_clip=clip)
                for m, model, clip in PROFILES[self.profile]
            ],
        )

    def manifests(self):
        return [MODEL, *[m for m, _, _ in PROFILES[self.profile]]]

    def provenance(self):
        return dict(
            schema_version=1,
            profile=self.profile,
            seed=self.seed,
            subject=self.subject,
            suite_sha256=self.suite['sha256'] if self.subject == 'anime-portrait' else None,
            source_revision=PIXEL['source']['revision'],
            converted_weight_sha256=PIXEL['sha256'],
            scope='Native ComfyUI text2image LoraLoader; no upstream image conversion, quantization, '
            'reference images, automatic quality scores or author-style acceptance. '
            'LCM uses separate sampling controls; compare orders within the same control group.',
        )

    def preflight(self):
        super().preflight()
        if experiment_plans.suite('anime-illustration') != self.suite:
            raise ValueError('Anime suite changed; no job submitted')
        self.report['style_study'] = self.provenance()

    def validate_report(self, value):
        super().validate_report(value)
        if value.get('style_study') != self.provenance():
            raise ValueError('Study subject, suite, seed, profile or source revision differs')
        # Validate original strengths/order before any GET, including restore snapshots.
        for item in value['verified_artworks']:
            if (
                item['restore_settings'].get('lora_metadata')
                != value['weight_snapshots']['lora_metadata']
            ):
                raise ValueError('Restored ordered LoRA metadata differs')

    def verify_artworks(self, expected):
        super().verify_artworks(expected)
        for item in self.report['verified_artworks']:
            if (
                item['restore_settings'].get('lora_metadata')
                != self.report['weight_snapshots']['lora_metadata']
            ):
                raise ValueError('Saved restored ordered LoRA metadata differs')


def main(argv=None):
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument('--profile', choices=tuple(PROFILES), default='pixel')
    parser.add_argument('--seed', choices=SEEDS, default=SEEDS[0])
    parser.add_argument('--subject', choices=SUBJECTS, default=SUBJECTS[0])
    args, rest = parser.parse_known_args(argv)
    runner = type(
        'FixedStyleMatrix',
        (MatrixAcceptance,),
        dict(profile=args.profile, seed=args.seed, subject=args.subject),
    )
    return base.main(
        rest,
        runner_type=runner,
        default_checkpoint=MODEL['filename'],
        default_report=f'runtime/style-{args.subject}-{args.profile}-{args.seed}.json',
    )


if __name__ == '__main__':
    raise SystemExit(main())
