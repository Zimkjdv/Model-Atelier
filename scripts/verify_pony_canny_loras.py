"""One pinned Pony Canny v2 profile per invocation; offline checks are GET-only."""

import argparse
import copy
from scripts import install_model, verify_control_edge_generation as edge
from scripts import verify_control_generation as control, verify_local_generation as base

STYLE = install_model.manifest('ikea-instructions-lora-sdxl')
LCM = install_model.manifest('lcm-lora-sdxl')
PROFILES = {
    'baseline': (),
    'style': (STYLE,),
    'lcm': (LCM,),
    'lcm-style': (LCM, STYLE),
    'style-lcm': (STYLE, LCM),
}


class PonyCannyAcceptance(edge.EdgeAcceptance):
    model_id = 'pony-v6-xl'
    profile = 'baseline'
    source_sha256 = 'fb219fb1268aef29671f77ab46dda4a2ea97de11a29ca9aec1b425f246406850'

    def expected_settings(self):
        value = control.ControlAcceptance.expected_settings(self)
        manifests = PROFILES[self.profile]
        accelerated = LCM in manifests
        return value | dict(
            title='Pony Canny v2 / ' + self.profile,
            control_start=0.0,
            control_end=1.0,
            loras=[
                dict(
                    name=m['filename'],
                    enabled=True,
                    strength_model=1.0,
                    strength_clip=0.0 if m is LCM else 1.0,
                )
                for m in manifests
            ],
            steps=8 if accelerated else 20,
            cfg=1.0 if accelerated else 5.5,
            sampler_name='lcm' if accelerated else 'dpmpp_2m',
            scheduler='sgm_uniform' if accelerated else 'karras',
        )

    def weight_anchors(self):
        return [
            dict(
                name=m['filename'],
                sha256=m['sha256'],
                size_bytes=m['size_bytes'],
                revision=m['source']['revision'],
            )
            for m in (self.manifest, control.CONTROL, *PROFILES[self.profile])
        ]

    def preflight(self):
        super().preflight()
        manifests = PROFILES[self.profile]
        self.report['local_weights_verified'] = self.weight_anchors()[:2]
        if self.report['original_assets'][0]['sha256'] != self.source_sha256:
            raise ValueError(
                'Fixed chair source differs; import experiments/fixtures/canny-chair-v1.png'
            )
        if not manifests:
            return
        # The parent records its anchors only after verifying checkpoint/control.
        # Do not claim LoRA bytes were checked if a later LoRA check fails.
        library = self.json('POST', 'loras/sync', json=dict(engine_url=self.engine))
        if (
            library.get('engine_url') != self.engine
            or library.get('sync_error')
            or not library.get('synced_at')
        ):
            raise ValueError('Fresh original-engine LoRA catalog required')
        for manifest in manifests:
            target = control.downloader._paths(
                control.downloader.WORKSPACE, manifest['filename'], create=False
            )[0]
            if not target.is_file() or not control.downloader._verified(target, manifest):
                raise ValueError('Pinned LoRA bytes differ: ' + manifest['filename'])
            item = next((v for v in library['loras'] if v['name'] == manifest['filename']), None)
            self.identity(item, manifest)
            if item.get('listed') is not True:
                raise ValueError('Pinned LoRA absent from original engine')
        self.report['local_weights_verified'] = self.weight_anchors()

    def lora_snapshots(self, snapshots):
        choices = self.expected_settings()['loras']
        if not isinstance(snapshots, list) or len(snapshots) != len(choices):
            raise ValueError('Ordered LoRA snapshot count differs')
        for snapshot, manifest, choice in zip(snapshots, PROFILES[self.profile], choices):
            self.identity(snapshot, manifest)
            if snapshot.get('enabled') is not True or any(
                type(snapshot.get(key)) not in (int, float) or snapshot[key] != choice[key]
                for key in ('strength_model', 'strength_clip')
            ):
                raise ValueError('Ordered LoRA strengths differ')

    def check_snapshots(self, item):
        self.identity(item.get('model_metadata'), self.manifest)
        self.components(item.get('component_metadata'))
        self.lora_snapshots(item.get('lora_metadata'))
        if (
            item.get('workflow_id') != self.workflow_id
            or item.get('reference_settings') != self.expected_settings()
        ):
            raise ValueError('Fixed Pony Canny v2 settings differ')
        self.anchors(item.get('reference_metadata'), self.report['original_assets'])
        for key in (
            'reference_metadata',
            'component_metadata',
            'model_metadata',
            'lora_metadata',
            'runtime_metadata',
            'measurements',
        ):
            if key in self.report and self.report[key] != item.get(key):
                raise ValueError('Immutable snapshot changed: ' + key)
            if item.get('status') == 'completed' or 'image_available' in item:
                self.report[key] = copy.deepcopy(item.get(key))

    def validate_report(self, value):
        super().validate_report(value)
        if value['original_assets'][0]['sha256'] != self.source_sha256:
            raise ValueError('Original fixed chair source differs')
        self.lora_snapshots(value.get('lora_metadata'))
        for item in value['verified_artworks']:
            if item['restore_settings'].get('lora_metadata') != value['lora_metadata']:
                raise ValueError('Original restored LoRA snapshot differs')

    def verify_artworks(self, expected):
        super().verify_artworks(expected)
        for kind, ids in (
            ('jobs', [self.report['job_id']]),
            ('artworks', self.report['artwork_ids']),
        ):
            for identifier in ids:
                restored = self.json('GET', kind + '/' + identifier + '/creation-settings')
                if restored.get('lora_metadata') != self.report['lora_metadata']:
                    raise ValueError('Restored ordered LoRA metadata differs')


def main(argv=None):
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument('--profile', choices=tuple(PROFILES), required=True)
    parser.add_argument('--source-id', required=True)
    options, rest = parser.parse_known_args(argv)
    runner = type(
        'FixedPonyCanny',
        (PonyCannyAcceptance,),
        dict(profile=options.profile, source_id=options.source_id),
    )
    return base.main(
        rest,
        runner_type=runner,
        default_checkpoint=control.MODELS['pony-v6-xl']['filename'],
        default_report='runtime/pony-canny-v2-' + options.profile + '.json',
    )


if __name__ == '__main__':
    raise SystemExit(main())
