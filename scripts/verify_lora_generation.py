"""Fixed Pony + LCM SDXL GPU acceptance; verification uses saved records only."""
import copy

from scripts import install_model, install_pony as downloader, verify_local_generation as base

CHECKPOINT = install_model.manifest('pony-v6-xl')
LORA = install_model.manifest('lcm-lora-sdxl')


def settings(engine, checkpoint):
    if checkpoint != CHECKPOINT['filename']:
        raise ValueError('This acceptance profile only supports the pinned Pony checkpoint')
    return base.settings(engine, checkpoint) | dict(
        title='Pony + LCM single LoRA GPU acceptance', steps=4, cfg=1.0,
        sampler_name='lcm', scheduler='sgm_uniform',
        loras=[dict(name=LORA['filename'], enabled=True, strength_model=1.0, strength_clip=0.0)])


def check_identity(item, manifest):
    if (not isinstance(item, dict) or item.get('name') != manifest['filename']
            or item.get('sha256') != manifest['sha256'] or item.get('architecture') != 'sdxl'
            or item.get('version') != manifest['version']):
        raise ValueError('Pinned checkpoint/LoRA registered identity does not match the acceptance profile')


class LoraAcceptance(base.Acceptance):
    checkpoint_manifest = CHECKPOINT

    def expected_settings(self):
        return settings(self.engine, self.checkpoint)

    def preflight(self):
        # Recheck actual local bytes for this explicit GPU acceptance. This is
        # separate from platform metadata registration and never runs offline.
        for manifest in (self.checkpoint_manifest, LORA):
            target, _, _, _ = downloader._paths(downloader.WORKSPACE, manifest['filename'], create=False)
            if not target.is_file() or not downloader._verified(target, manifest):
                raise ValueError('Local pinned weight size/SHA256 check failed: ' + manifest['filename'])
        models = self.json('GET', 'models')
        loras = self.json('POST', 'loras/sync', json=dict(engine_url=self.engine))
        for catalog, field, manifest in ((models, 'models', self.checkpoint_manifest), (loras, 'loras', LORA)):
            if catalog.get('engine_url') != self.engine or catalog.get('sync_error'):
                raise ValueError('Fresh original-engine catalog required')
            item = next((item for item in catalog.get(field, []) if item.get('name') == manifest['filename']), None)
            check_identity(item, manifest)
            if item.get('listed') is not True:
                raise ValueError('Pinned weight is absent from the original-engine catalog')
        self.report['local_weights_verified'] = [dict(name=m['filename'], sha256=m['sha256'], size_bytes=m['size_bytes'])
                                                 for m in (self.checkpoint_manifest, LORA)]

    def check_snapshots(self, item):
        check_identity(item.get('model_metadata'), self.checkpoint_manifest)
        entries = item.get('lora_metadata')
        if not isinstance(entries, list) or len(entries) != 1:
            raise ValueError('Expected one immutable LoRA metadata snapshot')
        check_identity(entries[0], LORA)
        if (entries[0].get('enabled') is not True
                or any(type(entries[0].get(k)) not in (int, float) for k in ('strength_model', 'strength_clip'))
                or entries[0].get('strength_model') != 1.0
                or entries[0].get('strength_clip') != 0.0):
            raise ValueError('Immutable LoRA snapshot strengths differ')
        return dict(model_metadata=item['model_metadata'], lora_metadata=entries)

    def assert_job(self, value, expected):
        super().assert_job(value, expected)
        snapshots = self.check_snapshots(value)
        if 'weight_snapshots' in self.report and snapshots != self.report['weight_snapshots']:
            raise ValueError('Original immutable weight snapshots changed')
        self.report['weight_snapshots'] = copy.deepcopy(snapshots)

    def validate_report(self, value):
        super().validate_report(value)
        choice = value['settings']['loras'][0]
        if choice.get('enabled') is not True or any(type(choice.get(k)) not in (int, float)
                                                   for k in ('strength_model', 'strength_clip')):
            raise ValueError('Report original LoRA parameter types are invalid')
        self.check_snapshots(value['weight_snapshots'])

    def verify_artworks(self, expected):
        super().verify_artworks(expected)
        for artwork_id in self.report['artwork_ids']:
            snapshots = self.check_snapshots(self.json('GET', 'artworks/' + artwork_id))
            if snapshots != self.report['weight_snapshots']:
                raise ValueError('Artwork immutable weight snapshots differ from the original job')


def main(argv=None):
    return base.main(argv, runner_type=LoraAcceptance, default_report='runtime/pony-lcm-acceptance.json')


if __name__ == '__main__':
    raise SystemExit(main())
