"""Pinned Animagine author-profile GPU acceptance; saved verification uses GET only."""
import copy
import sys

from scripts import install_model, install_pony as downloader, verify_local_generation as base

MODEL = install_model.manifest('animagine-xl-4.0-opt')
PROMPT = ('masterpiece,best quality,very aesthetic,anime style,scenery,mountain lake,'
          'pine forest,blue sky,peaceful daylight,no humans')


def settings(engine, checkpoint):
    if checkpoint != MODEL['filename']:
        raise ValueError('This fixed acceptance supports only the pinned Animagine checkpoint')
    return base.settings(engine, checkpoint) | dict(
        title='Animagine XL 4.0 Opt local GPU acceptance', prompt=PROMPT,
        width=1024, height=1024, steps=28, cfg=5.0,
        sampler_name='euler_ancestral', scheduler='normal')


def check_identity(item):
    if (not isinstance(item, dict) or item.get('name') != MODEL['filename']
            or item.get('sha256') != MODEL['sha256'] or item.get('architecture') != 'sdxl'
            or item.get('version') != MODEL['version'] or item.get('size_bytes') != MODEL['size_bytes']):
        raise ValueError('Pinned Animagine registered identity does not match the fixed profile')


class AnimagineAcceptance(base.Acceptance):
    def expected_settings(self):
        return settings(self.engine, self.checkpoint)

    def preflight(self):
        target, _, _, _ = downloader._paths(downloader.WORKSPACE, MODEL['filename'], create=False)
        if not target.is_file() or not downloader._verified(target, MODEL):
            raise ValueError('Local pinned Animagine size/SHA256 verification failed')
        catalog = self.json('GET', 'models')
        item = next((v for v in catalog.get('models', []) if v.get('name') == self.checkpoint), None)
        check_identity(item)
        if catalog.get('engine_url') != self.engine or catalog.get('sync_error') or item.get('listed') is not True:
            raise ValueError('Fresh original-engine model catalog required')
        self.report['local_weights_verified'] = [dict(name=MODEL['filename'], sha256=MODEL['sha256'],
                                                     size_bytes=MODEL['size_bytes'])]

    def check_snapshot(self, item):
        snapshot = item.get('model_metadata')
        check_identity(snapshot)
        if item.get('lora_metadata'):
            raise ValueError('The base acceptance must have no active LoRA')
        if 'model_snapshot' in self.report and snapshot != self.report['model_snapshot']:
            raise ValueError('Immutable original model metadata snapshot changed')
        self.report['model_snapshot'] = copy.deepcopy(snapshot)

    def assert_job(self, value, expected):
        super().assert_job(value, expected)
        self.check_snapshot(value)

    def validate_report(self, value):
        super().validate_report(value)
        check_identity(value['model_snapshot'])

    def verify_artworks(self, expected):
        super().verify_artworks(expected)
        for artwork_id in self.report['artwork_ids']:
            self.check_snapshot(self.json('GET', 'artworks/' + artwork_id))


class RepeatAcceptance(AnimagineAcceptance):
    def expected_settings(self):
        return super().expected_settings() | dict(seed=str(int(base.SEED) + 1))


def main(argv=None):
    args = list(sys.argv[1:] if argv is None else argv)
    repeat = '--repeat' in args
    if repeat:
        args.remove('--repeat')
    if '--help' in args or '-h' in args:
        print('--repeat: use the second fixed seed for an uncached repeat sample; choose a new report path')
    return base.main(args, runner_type=RepeatAcceptance if repeat else AnimagineAcceptance,
                     default_report='runtime/animagine-xl-4.0-opt-acceptance.json',
                     default_checkpoint=MODEL['filename'])


if __name__ == '__main__':
    raise SystemExit(main())
