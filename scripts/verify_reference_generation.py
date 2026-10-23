"""One explicit SDXL reference run; immutable reports and GET-only offline verification."""

import argparse

from backend import adapter_workflows as flow
from scripts import install_model, install_pony as downloader, verify_local_generation as base
from scripts.verify_control_generation import ControlAcceptance, canonical, checksum

MODEL = install_model.manifest('animagine-xl-4.0-opt')
ADAPTER = install_model.manifest('ip-adapter-plus-sdxl-vit-h')
VISION = install_model.manifest('clip-vision-vit-h')
SCENES = {
    'portrait': 'head and shoulders portrait, facing the viewer, plain gray background',
    'bookshop': 'standing in a bookshop, holding one closed red book, full body',
    'park': 'walking in a sunny park, holding a closed blue umbrella, full body',
}
SEEDS = ('9007199254740993', '18446744073709551615')


class ReferenceAcceptance(ControlAcceptance):
    generate_path = 'reference/generate'
    workflow_id = flow.ID
    model_id = 'animagine-xl-4.0-opt'
    mode = 'style'
    weight = 0.6
    scene = 'portrait'
    seed = SEEDS[0]
    source_sha256 = None

    def expected_settings(self):
        return base.settings(self.engine, self.checkpoint) | dict(
            title=f'R02 / {self.mode} / {self.weight} / {self.scene} / {self.seed}'[:100],
            prompt='masterpiece, best quality, anime illustration, one adult woman age 25, long chestnut brown hair, green eyes, small green hair ribbon, high-neck long-sleeved blue coat, fully clothed, '
            + SCENES[self.scene],
            negative_prompt='child, teenager, nudity, cleavage, lingerie, swimsuit, text, watermark, multiple people, blurry, bad hands',
            width=1024,
            height=1024,
            steps=28,
            cfg=5.0,
            sampler_name='euler_ancestral',
            scheduler='normal',
            seed=self.seed,
            workflow_mode='text2image',
            denoise=1.0,
            image_asset_id=self.source_id,
            reference_ids=[self.source_id],
            reference_resize='fit',
            reference_mode=self.mode,
            reference_weight=self.weight,
            reference_start=0.0,
            reference_end=1.0,
            ipadapter_name=ADAPTER['filename'],
            clip_vision_name=VISION['filename'],
            loras=[],
        )

    def build_workflow(self, settings, job_id=None):
        return flow.build(settings, job_id)

    def identity(self, item, manifest, control=False):
        expected = dict(
            name=manifest['filename'],
            version=manifest['version'],
            architecture='other' if manifest is VISION else 'sdxl',
            sha256=manifest['sha256'],
            size_bytes=manifest['size_bytes'],
        )
        if not isinstance(item, dict) or any(item.get(k) != v for k, v in expected.items()):
            raise ValueError('Pinned checkpoint/adapter/vision metadata differs')

    def weight_anchors(self):
        return [
            dict(
                name=m['filename'],
                sha256=m['sha256'],
                size_bytes=m['size_bytes'],
                revision=m['source']['revision'],
            )
            for m in (MODEL, ADAPTER, VISION)
        ]

    def preflight(self):
        for manifest in (MODEL, ADAPTER, VISION):
            target = downloader._paths(downloader.WORKSPACE, manifest['filename'], create=False)[0]
            if not target.is_file() or not downloader._verified(target, manifest):
                raise ValueError('Pinned local weight checksum differs: ' + manifest['filename'])
        catalog = self.json('GET', 'models')
        model = next((m for m in catalog.get('models', []) if m.get('name') == self.checkpoint), {})
        self.identity(model, MODEL)
        if (
            catalog.get('engine_url') != self.engine
            or catalog.get('sync_error')
            or not catalog.get('synced_at')
            or model.get('listed') is not True
        ):
            raise ValueError('Original checkpoint catalog differs')
        library = self.json('POST', 'reference-components/sync', json=dict(comfy_url=self.engine))
        if (
            library.get('engine_url') != self.engine
            or library.get('sync_error')
            or not library.get('synced_at')
        ):
            raise ValueError('Reference components not freshly confirmed')
        self.components(
            [
                next(
                    (
                        r
                        for r in library['components']
                        if r['role'] == role and r['name'] == manifest['filename']
                    ),
                    {},
                )
                for role, manifest in [('ipadapter', ADAPTER), ('clip_vision', VISION)]
            ]
        )
        source = self.json('GET', 'assets/' + self.source_id)
        if (
            source.get('archived')
            or source.get('id') != self.source_id
            or source.get('sha256') != self.source_sha256
        ):
            raise ValueError('Source unavailable or hash differs')
        self.report['original_assets'] = [
            {k: source[k] for k in ('id', 'sha256', 'size', 'width', 'height')}
        ]
        self.report['local_weights_verified'] = self.weight_anchors()

    def components(self, items):
        if not isinstance(items, list) or len(items) != 2:
            raise ValueError('Missing unique adapter and vision snapshots')
        for item, role, family, manifest in zip(
            items,
            ['ipadapter', 'clip_vision'],
            ['sdxl-plus-vit-h', 'clip-vit-h-14'],
            [ADAPTER, VISION],
        ):
            self.identity(item, manifest)
            if item.get('role') != role or item.get('family') != family:
                raise ValueError('Reference component family/order differs')

    def anchors(self, refs, originals):
        if (
            not isinstance(refs, list)
            or len(refs) != 1
            or not isinstance(originals, list)
            or len(originals) != 1
        ):
            raise ValueError('Missing original reference anchor')
        ref, original = refs[0], originals[0]
        if (
            ref.get('id') != self.source_id
            or ref.get('input_role') != 'source'
            or ref.get('sha256') != self.source_sha256
            or any(
                ref.get(k) != original.get(k) for k in ('id', 'sha256', 'size', 'width', 'height')
            )
        ):
            raise ValueError('Original reference identity differs')
        prep = ref.get('generation_preprocessing', {})
        if (
            any(
                prep.get(k) != v
                for k, v in dict(
                    id='ipadapter-square-input',
                    version=1,
                    width=224,
                    height=224,
                    resize='fit',
                    output_mode='RGB',
                    output_format='PNG',
                    background='#ffffff',
                    resampling='LANCZOS',
                ).items()
            )
            or type(prep.get('version')) is not int
            or not checksum(prep.get('sha256'))
            or not checksum(ref.get('sha256'))
        ):
            raise ValueError('Reference preprocessing differs')
        if ref.get('adapter_preprocessing') != flow.conditioning(self.expected_settings()):
            raise ValueError('Frozen style/appearance conditioning differs')

    def validate_report(self, value):
        base.Acceptance.validate_report(self, value)
        self.identity(value.get('model_metadata'), MODEL)
        self.components(value.get('component_metadata'))
        self.anchors(value.get('reference_metadata'), value.get('original_assets'))
        if (
            value.get('local_weights_verified') != self.weight_anchors()
            or not isinstance(value.get('runtime_metadata'), dict)
            or 'measurements' not in value
        ):
            raise ValueError('Missing fixed weights/environment evidence')


def main(argv=None):
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument('--source-id', required=True)
    parser.add_argument('--source-sha256', required=True)
    parser.add_argument('--mode', choices=['style', 'character'], default='style')
    parser.add_argument('--weight', type=float, choices=[0, 0.4, 0.6, 0.8, 1], default=0.6)
    parser.add_argument('--scene', choices=tuple(SCENES), default='portrait')
    parser.add_argument('--seed', choices=SEEDS, default=SEEDS[0])
    args, rest = parser.parse_known_args(argv)
    canonical(args.source_id)
    if not checksum(args.source_sha256):
        parser.error('Source SHA256 required')
    runner = type(
        'FixedReferenceAcceptance',
        (ReferenceAcceptance,),
        dict(
            source_id=args.source_id,
            source_sha256=args.source_sha256,
            mode=args.mode,
            weight=args.weight,
            scene=args.scene,
            seed=args.seed,
        ),
    )
    return base.main(
        rest,
        runner_type=runner,
        default_checkpoint=MODEL['filename'],
        default_report='runtime/reference-acceptance.json',
    )


if __name__ == '__main__':
    raise SystemExit(main())
