"""Explicit local hardware acceptance; each report admits at most one GPU job.

Reuse the existing generation, checksum, import and GET-only verification checks.
Hardware snapshots describe the observed machine, never minimum requirements.
"""

import argparse
import hashlib
import json
from pathlib import Path
import subprocess

import httpx

from backend import image_workflows
from scripts import verify_local_generation as base
from scripts.verify_animagine_generation import AnimagineAcceptance, MODEL
from scripts.verify_control_generation import ControlAcceptance
from scripts.verify_inpaint_generation import InpaintAcceptance
from scripts.verify_multi_lora import StyleAcceptance
from scripts.verify_lora_generation import CHECKPOINT, check_identity
from scripts import install_pony as downloader

ROOT = Path(__file__).resolve().parents[1]


class PonyAcceptance(base.Acceptance):
    def preflight(self):
        target = downloader._paths(ROOT, CHECKPOINT['filename'], create=False)[0]
        if not target.is_file() or not downloader._verified(target, CHECKPOINT):
            raise ValueError('Fixed Pony complete weight checksum differs')
        item = next(m for m in self.json('GET', 'models')['models'] if m['name'] == self.checkpoint)
        check_identity(item, CHECKPOINT)
        self.report['local_weights_verified'] = [
            {k: CHECKPOINT[k] for k in ('filename', 'sha256', 'size_bytes')}
        ]


class HighLoadAcceptance(PonyAcceptance):
    def expected_settings(self):
        return super().expected_settings() | dict(
            title='RTX 4080 separate 1536-square 30-step acceptance',
            width=1536,
            height=1536,
            steps=30,
        )


def source_revision(path):
    result = subprocess.run(
        ['git', '-C', str(path), 'rev-parse', 'HEAD'],
        capture_output=True,
        text=True,
        timeout=10,
        check=True,
    )
    return result.stdout.strip()


def snapshot(platform, engine):
    with httpx.Client(base_url=base.local_url(platform), trust_env=False, timeout=30) as client:

        def get(path):
            result = client.get('/api/' + path)
            result.raise_for_status()
            return result.json()

        system, selected = get('system'), get('engine')
        if not selected.get('connected') or selected.get('url') != base.local_url(engine):
            raise ValueError('Selected original engine must be online and match the requested URL')
        probe = subprocess.run(
            [
                str(ROOT / 'runtime/ComfyUI/.venv/Scripts/python.exe'),
                str(ROOT / 'scripts/check_local_environment.py'),
            ],
            capture_output=True,
            text=True,
            encoding='utf-8',
            timeout=90,
            check=True,
        )
        return dict(
            schema_version=1,
            checked_at=base.utc_now(),
            platform_url=platform,
            platform=system,
            engine=selected,
            local_python=json.loads(probe.stdout),
            source_commits=dict(
                platform=source_revision(ROOT), comfyui=source_revision(ROOT / 'runtime/ComfyUI')
            ),
            scope='Observed host and selected engine; no model minimum or task-exclusive peak claim',
        )


class ImageAcceptance(AnimagineAcceptance):
    source_id = None

    def expected_settings(self):
        return super().expected_settings() | dict(
            title='RTX hardware image input acceptance',
            workflow_mode='image2image',
            image_asset_id=self.source_id,
            reference_ids=[self.source_id],
            reference_resize='fit',
            denoise=0.6,
        )

    def build_workflow(self, settings, job_id=None):
        return image_workflows.build(settings, job_id)


def runner_class(case, source_id=None, mask_id=None):
    if case == 'pony':
        return PonyAcceptance, 'pony-v6-xl.safetensors'
    if case == 'pony-high':
        return HighLoadAcceptance, 'pony-v6-xl.safetensors'
    if case == 'animagine':
        return AnimagineAcceptance, MODEL['filename']
    parent, options = {
        'multi': (StyleAcceptance, dict(profile='multi-8')),
        'image': (ImageAcceptance, dict(source_id=source_id)),
        'inpaint': (
            InpaintAcceptance,
            dict(model_id=MODEL['id'], source_id=source_id, mask_id=mask_id),
        ),
        'canny': (ControlAcceptance, dict(model_id=MODEL['id'], source_id=source_id)),
    }[case]
    if case in ('image', 'inpaint', 'canny') and not source_id:
        raise ValueError('Explicit source asset UUID required')
    if case == 'inpaint' and not mask_id:
        raise ValueError('Explicit mask UUID required')
    return type('HardwareAcceptance', (parent,), options), MODEL['filename']


def summarize(report, client):
    if report.get('status') != 'passed':
        raise ValueError('Only successful, fully verified generation reports may be summarized')
    result = client.get('/api/jobs/' + report['job_id'], timeout=30)
    result.raise_for_status()
    job = result.json()
    if job['status'] != 'completed' or job['engine_url'] != report['expected_engine']:
        raise ValueError('Original terminal job no longer matches report')
    return dict(
        job_id=job['id'],
        artwork_ids=report['artwork_ids'],
        settings=report['settings'],
        model_metadata=job.get('model_metadata'),
        lora_metadata=job.get('lora_metadata'),
        component_metadata=job.get('component_metadata'),
        reference_metadata=job.get('reference_metadata'),
        runtime_metadata=job.get('runtime_metadata'),
        measurements=job.get('measurements'),
        submission_to_history_wall_seconds=report['submission_to_history_wall_seconds'],
        vram_sampling=report.get('vram_sampling'),
        verified_artworks=report['verified_artworks'],
        workflow_sha256=hashlib.sha256(
            json.dumps(job['workflow'], sort_keys=True, separators=(',', ':')).encode()
        ).hexdigest(),
    )


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    environment = sub.add_parser('snapshot')
    environment.add_argument('--platform', default='http://127.0.0.1:8000')
    environment.add_argument('--engine', default='http://127.0.0.1:8188')
    environment.add_argument('--report', required=True)
    run = sub.add_parser('run')
    run.add_argument(
        '--case',
        choices=['pony', 'pony-high', 'animagine', 'multi', 'image', 'inpaint', 'canny'],
        required=True,
    )
    run.add_argument('--source-id')
    run.add_argument('--mask-id')
    run.add_argument('generation_arguments', nargs=argparse.REMAINDER)
    args = parser.parse_args(argv)
    if args.command == 'snapshot':
        path = base.report_path(args.report)
        base.reserve_report(path)
        try:
            base.write_report(path, snapshot(args.platform, args.engine))
        except Exception as exc:
            base.write_report(path, dict(status='failed', error=str(exc)))
            raise
        print(path)
        return 0
    cls, checkpoint = runner_class(args.case, args.source_id, args.mask_id)
    rest = args.generation_arguments
    if rest[:1] == ['--']:
        rest = rest[1:]
    return base.main(
        rest,
        runner_type=cls,
        default_checkpoint=checkpoint,
        default_report='runtime/hardware-' + args.case + '.json',
    )


if __name__ == '__main__':
    raise SystemExit(main())
