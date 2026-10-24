"""One Docker-platform/native-engine technical case, or GET-only original recovery."""

from scripts import verify_local_generation as base
from scripts.verify_animagine_generation import MODEL
from scripts.verify_lora_generation import check_identity
from backend.training_files import digest

ENGINE = 'http://host.docker.internal:8188'


class ContainerAcceptance(base.Acceptance):
    def __init__(self, client, engine, checkpoint, **options):
        if engine != ENGINE or checkpoint != MODEL['filename']:
            raise ValueError(
                'The fixed managed native engine and Animagine checkpoint are required.'
            )
        # The public platform must remain loopback. This exact Docker Desktop
        # engine alias is the only additional engine name admitted by this case.
        super().__init__(client, 'http://127.0.0.1:8188', checkpoint, **options)
        self.engine = engine

    def expected_settings(self):
        return base.settings(self.engine, self.checkpoint) | dict(
            title='D02 container technical case',
            prompt='one small tree, flat colored illustration, plain pale background',
            negative_prompt='text, watermark, blurry',
            seed='18446744073709551615',
            width=512,
            height=512,
            steps=4,
            cfg=5.0,
            sampler_name='euler_ancestral',
            scheduler='normal',
        )

    def preflight(self):
        system = self.json('GET', 'system')
        if system.get('runtime_kind') != 'container':
            raise ValueError('This check requires the actual container platform.')
        # This verifier runs on the native host and checks the managed engine's
        # weight there; the platform container does not mount Windows weights.
        path = base.ROOT / 'runtime/ComfyUI/models/checkpoints' / MODEL['filename']
        if path.stat().st_size != MODEL['size_bytes'] or digest(path) != MODEL['sha256']:
            raise ValueError('The actual managed base checkpoint differs.')
        models = self.json('GET', 'models')
        check_identity(next(v for v in models['models'] if v['name'] == self.checkpoint), MODEL)
        self.report['container_profile'] = dict(
            runtime_kind='container',
            model_sha256=MODEL['sha256'],
            platform_hardware_scope=system['hardware_scope'],
            scope='Technical transport/save/restore; no quality claim.',
        )

    def assert_job(self, value, expected):
        super().assert_job(value, expected)
        check_identity(value.get('model_metadata'), MODEL)

    def validate_report(self, value):
        super().validate_report(value)
        if value.get('container_profile', {}).get('model_sha256') != MODEL['sha256']:
            raise ValueError('Original fixed model provenance differs.')


if __name__ == '__main__':
    raise SystemExit(
        base.main(
            runner_type=ContainerAcceptance,
            default_checkpoint=MODEL['filename'],
            default_report='runtime/d02-generation.json',
        )
    )
