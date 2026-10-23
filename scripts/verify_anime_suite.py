"""One model, anime case, exact seed and prompt format per explicit invocation."""

import argparse
import copy
from backend import experiment_plans
from scripts import install_pony as downloader, verify_local_generation as base
from scripts.verify_illustration_suite import MODELS, SuiteAcceptance

SEEDS = ('9007199254740993', '18446744073709551615')
CASES = ('anime-portrait', 'anime-full-body', 'anime-station')


def settings(engine, checkpoint, case, model, seed, prompt_format):
    prompt = case['prompt']
    if prompt_format == 'quality-tags':
        prompt = (
            'score_9, score_8_up, score_7_up, rating_safe, source_anime, ' + prompt
            if model == 'pony-v6-xl'
            else prompt + ', masterpiece, high score, great score, absurdres'
        )
    return base.settings(engine, checkpoint) | dict(
        title=f'Anime v1 / {case["id"]} / {prompt_format} / {seed}'[:100],
        prompt=prompt,
        negative_prompt='blurry, low quality, text, watermark',
        seed=seed,
        width=1024,
        height=1024,
        steps=28,
        cfg=5.0,
        sampler_name='euler_ancestral',
        scheduler='normal',
        loras=[],
    )


class AnimeAcceptance(SuiteAcceptance):
    case_id = 'anime-portrait'
    seed = SEEDS[0]
    prompt_format = 'common'

    def __init__(self, *args, **kwargs):
        self.manifest = MODELS[self.model_id]
        self.suite = experiment_plans.suite('anime-illustration')
        self.case = next(v for v in self.suite['cases'] if v['id'] == self.case_id)
        base.Acceptance.__init__(self, *args, **kwargs)
        if self.checkpoint != self.manifest['filename']:
            raise ValueError('Checkpoint must match the pinned model selection')

    def expected_settings(self):
        return settings(
            self.engine, self.checkpoint, self.case, self.model_id, self.seed, self.prompt_format
        )

    def provenance(self):
        return dict(
            id=self.suite['id'],
            version=self.suite['version'],
            sha256=self.suite['sha256'],
            case=copy.deepcopy(self.case),
            seed=self.seed,
            prompt_format=self.prompt_format,
            condition='Common controls: 1024x1024, 28 steps, CFG 5, euler_ancestral/normal; '
            'quality-tags changes positive prompt only, not a complete author preset. '
            'No LoRA/reference or claim of author-style/character identity validation.',
        )

    def preflight(self):
        target = downloader._paths(downloader.WORKSPACE, self.manifest['filename'], create=False)[0]
        if not target.is_file() or not downloader._verified(target, self.manifest):
            raise ValueError('Pinned local checkpoint size/SHA256 verification failed')
        catalog = self.json('GET', 'models')
        item = next(
            (v for v in catalog.get('models', []) if v.get('name') == self.checkpoint), None
        )
        self.identity(item)
        if (
            catalog.get('engine_url') != self.engine
            or catalog.get('sync_error')
            or not item['listed']
        ):
            raise ValueError('Fresh original-engine catalog required')
        if experiment_plans.suite('anime-illustration') != self.suite:
            raise ValueError('Anime suite changed before submission; no job submitted')
        self.report['test_suite'] = self.provenance()
        self.report['local_weights_verified'] = [
            {key: self.manifest[key] for key in ('filename', 'sha256', 'size_bytes')}
        ]


def main(argv=None):
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument('--model', choices=tuple(MODELS), default='animagine-xl-4.0-opt')
    parser.add_argument('--case', choices=CASES, default=CASES[0])
    parser.add_argument('--seed', choices=SEEDS, default=SEEDS[0])
    parser.add_argument('--prompt-format', choices=('common', 'quality-tags'), default='common')
    args, rest = parser.parse_known_args(argv)
    runner = type(
        'FixedAnimeAcceptance',
        (AnimeAcceptance,),
        dict(
            model_id=args.model, case_id=args.case, seed=args.seed, prompt_format=args.prompt_format
        ),
    )
    return base.main(
        rest,
        runner_type=runner,
        default_checkpoint=MODELS[args.model]['filename'],
        default_report=f'runtime/anime-{args.model}-{args.case}-{args.seed}-{args.prompt_format}.json',
    )


if __name__ == '__main__':
    raise SystemExit(main())
