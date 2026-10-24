"""One technical trained-LoRA generation or GET-only original-report verification."""

import argparse

from backend import training_artifacts as artifacts
from backend.training_files import digest
from scripts import verify_local_generation as base
from scripts.verify_multi_lora import StyleAcceptance, MODEL
from scripts.verify_lora_generation import check_identity


def runner_type(run_id, branch):
    class TrainedAcceptance(StyleAcceptance):
        def __init__(self, *arguments, **options):
            self.artifact = artifacts.registration(run_id)
            super().__init__(*arguments, **options)
            if self.checkpoint != MODEL['filename']:
                raise ValueError('Pinned Animagine base required.')

        def expected_settings(self):
            choices = (
                []
                if branch == 'baseline'
                else [
                    dict(
                        name=self.artifact['filename'],
                        enabled=True,
                        strength_model=1.0,
                        strength_clip=0.0,
                    )
                ]
            )
            return base.settings(self.engine, self.checkpoint) | dict(
                title='T04 technical trained LoRA ' + branch,
                prompt=self.artifact['dataset']['trigger']
                + ', flat colored rectangle and circle, plain background',
                negative_prompt='blurry, text, watermark',
                seed=artifacts.SEEDS[0],
                width=512,
                height=512,
                steps=4,
                cfg=5.0,
                sampler_name='euler_ancestral',
                scheduler='normal',
                loras=choices,
            )

        def manifests(self):
            return [MODEL] + (
                []
                if branch == 'baseline'
                else [
                    dict(
                        filename=self.artifact['filename'],
                        version=self.artifact['version'],
                        **self.artifact['weight'],
                    )
                ]
            )

        def preflight(self):
            artifacts.verify_installed(run_id)
            path = artifacts.runs.ROOT / 'runtime/ComfyUI/models/checkpoints' / MODEL['filename']
            if path.stat().st_size != MODEL['size_bytes'] or digest(path) != MODEL['sha256']:
                raise ValueError('The actual base checkpoint differs.')
            models = self.json('GET', 'models')
            check_identity(next(v for v in models['models'] if v['name'] == self.checkpoint), MODEL)
            if branch == 'candidate':
                artifacts.publish(self.client, run_id)
            self.report['trained_artifact'] = dict(
                run_id=run_id,
                branch=branch,
                manifest_sha256=self.artifact['manifest_sha256'],
                weight=self.artifact['weight'],
                scope='Technical load/save/restore only; no style or character quality acceptance.',
            )

        def validate_report(self, value):
            super().validate_report(value)
            expected = dict(
                run_id=run_id,
                branch=branch,
                manifest_sha256=self.artifact['manifest_sha256'],
                weight=self.artifact['weight'],
                scope='Technical load/save/restore only; no style or character quality acceptance.',
            )
            if value.get('trained_artifact') != expected:
                raise ValueError('Original training provenance differs.')

    return TrainedAcceptance


def main(argv=None):
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument('--run-id', required=True)
    parser.add_argument('--branch', choices=('baseline', 'candidate'), required=True)
    args, remaining = parser.parse_known_args(argv)
    return base.main(
        remaining,
        runner_type=runner_type(args.run_id, args.branch),
        default_checkpoint=MODEL['filename'],
        default_report='runtime/training/t04-' + args.branch + '-acceptance.json',
    )


if __name__ == '__main__':
    raise SystemExit(main())
