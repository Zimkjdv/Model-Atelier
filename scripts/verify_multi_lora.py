"""Pinned Animagine baseline/style/ordered LCM+style acceptance, one job per run."""
import copy
import sys

from scripts import install_model, install_pony as downloader, verify_local_generation as base
from scripts.verify_lora_generation import check_identity
from scripts.verify_animagine_generation import MODEL

STYLE = install_model.manifest('ikea-instructions-lora-sdxl')
LCM = install_model.manifest('lcm-lora-sdxl')
PROFILES = ('baseline', 'style', 'multi', 'multi-8', 'style-lcm-8')


def settings(engine, checkpoint, profile):
    if checkpoint != MODEL['filename'] or profile not in PROFILES:
        raise ValueError('Unsupported fixed style acceptance profile')
    choices = []
    multi = profile in ('multi', 'multi-8', 'style-lcm-8')
    if multi:
        choices.append(dict(name=LCM['filename'], enabled=True, strength_model=1.0, strength_clip=0.0))
    if profile != 'baseline':
        choices.append(dict(name=STYLE['filename'], enabled=True, strength_model=1.0, strength_clip=1.0))
    if profile == 'style-lcm-8':
        choices.reverse()
    return base.settings(engine, checkpoint) | dict(
        title='Animagine ' + profile + ' LoRA acceptance', width=1024, height=1024,
        prompt='black and white line drawing, instruction manual, assembling a wooden chair, white background, no humans',
        negative_prompt='blurry, low quality, people, watermark', loras=choices,
        steps=(4 if profile == 'multi' else 8) if multi else 28, cfg=1.0 if multi else 5.0,
        sampler_name='lcm' if multi else 'euler_ancestral',
        scheduler='sgm_uniform' if multi else 'normal')


class StyleAcceptance(base.Acceptance):
    profile = 'multi'

    def expected_settings(self):
        return settings(self.engine, self.checkpoint, self.profile)

    def manifests(self):
        by_name = {v['filename']: v for v in (LCM, STYLE)}
        return [MODEL] + [by_name[v['name']] for v in self.expected_settings()['loras']]

    def preflight(self):
        manifests = self.manifests()
        for manifest in manifests:
            target, _, _, _ = downloader._paths(downloader.WORKSPACE, manifest['filename'], create=False)
            if not target.is_file() or not downloader._verified(target, manifest):
                raise ValueError('Local pinned weight size/SHA256 mismatch: ' + manifest['filename'])
        models = self.json('GET', 'models')
        loras = self.json('POST', 'loras/sync', json=dict(engine_url=self.engine)) if len(manifests) > 1 else None
        for manifest in manifests:
            catalog, field = (models, 'models') if manifest is MODEL else (loras, 'loras')
            if catalog.get('engine_url') != self.engine or catalog.get('sync_error'):
                raise ValueError('Fresh original-engine catalog required')
            item = next((v for v in catalog.get(field, []) if v.get('name') == manifest['filename']), None)
            check_identity(item, manifest)
            if item.get('listed') is not True:
                raise ValueError('Pinned weight is absent from the original engine')
        self.report['local_weights_verified'] = [dict(name=v['filename'], sha256=v['sha256'], size_bytes=v['size_bytes']) for v in manifests]

    def check_snapshots(self, value):
        check_identity(value.get('model_metadata'), MODEL)
        snapshots = value.get('lora_metadata', [])
        choices = self.expected_settings()['loras']
        if not isinstance(snapshots, list) or len(snapshots) != len(choices):
            raise ValueError('LoRA snapshot count differs')
        for snapshot, manifest, choice in zip(snapshots, self.manifests()[1:], choices):
            check_identity(snapshot, manifest)
            if snapshot.get('enabled') is not True or any(
                type(snapshot.get(key)) not in (int, float) or snapshot[key] != choice[key]
                for key in ('strength_model', 'strength_clip')
            ):
                raise ValueError('Ordered LoRA strengths differ')
        return dict(model_metadata=value['model_metadata'], lora_metadata=snapshots)

    def assert_job(self, value, expected):
        super().assert_job(value, expected)
        snapshots = self.check_snapshots(value)
        if 'weight_snapshots' in self.report and self.report['weight_snapshots'] != snapshots:
            raise ValueError('Original weight snapshots changed')
        self.report['weight_snapshots'] = copy.deepcopy(snapshots)

    def validate_report(self, value):
        super().validate_report(value)
        self.check_snapshots(value['weight_snapshots'])

    def verify_artworks(self, expected):
        super().verify_artworks(expected)
        for identifier in self.report['artwork_ids']:
            if self.check_snapshots(self.json('GET', 'artworks/' + identifier)) != self.report['weight_snapshots']:
                raise ValueError('Artwork snapshot differs from original job')


def main(argv=None):
    arguments = list(sys.argv[1:] if argv is None else argv)
    profile = 'multi'
    if '--profile' in arguments:
        index = arguments.index('--profile')
        if index + 1 >= len(arguments) or arguments[index + 1] not in PROFILES:
            print('--profile must be ' + ', '.join(PROFILES), file=sys.stderr)
            return 2
        profile = arguments[index + 1]
        del arguments[index:index+2]
    runner = type('FixedStyleAcceptance', (StyleAcceptance,), dict(profile=profile))
    return base.main(arguments, runner_type=runner, default_checkpoint=MODEL['filename'],
                     default_report='runtime/animagine-' + profile + '-acceptance.json')


if __name__ == '__main__':
    raise SystemExit(main())
