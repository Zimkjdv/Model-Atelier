import copy
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from uuid import uuid4

import httpx
from PIL import Image

from backend.test_generation_acceptance import Clock, Platform
from scripts import (
    verify_reference_generation as check,
    install_model,
    install_ipadapter_nodes as nodes,
)
from backend import adapter_workflows as flow


class ReferencePlatform(Platform):
    def __init__(self, mode='style', seed=check.SEEDS[0], scene='portrait', **kwargs):
        super().__init__(**kwargs)
        self.checkpoint = check.MODEL['filename']
        self.source_id = str(uuid4())
        buffer = io.BytesIO()
        Image.new('RGB', (224, 224), 'white').save(buffer, 'PNG')
        self.source = buffer.getvalue()
        self.source_sha = hashlib.sha256(self.source).hexdigest()
        self.runner = type(
            'FixedReference',
            (check.ReferenceAcceptance,),
            dict(
                source_id=self.source_id,
                source_sha256=self.source_sha,
                mode=mode,
                seed=seed,
                scene=scene,
            ),
        )
        runner = self.runner(None, self.engine, self.checkpoint)
        self.settings = runner.expected_settings()
        self.workflow = flow.build(self.settings, str(uuid4()))

        def record(m, arch='sdxl'):
            return dict(
                name=m['filename'],
                version=m['version'],
                architecture=arch,
                sha256=m['sha256'],
                size_bytes=m['size_bytes'],
                listed=True,
            )

        self.model = record(check.MODEL)
        self.components = [
            record(check.ADAPTER) | dict(role='ipadapter', family='sdxl-plus-vit-h'),
            record(check.VISION, 'other') | dict(role='clip_vision', family='clip-vit-h-14'),
        ]
        self.job_version = self.artwork_version = check.MODEL['version']
        prep = dict(
            id='ipadapter-square-input',
            version=1,
            width=224,
            height=224,
            size=len(self.source),
            sha256=self.source_sha,
            resize='fit',
            output_mode='RGB',
            output_format='PNG',
            background='#ffffff',
            resampling='LANCZOS',
        )
        self.refs = [
            dict(
                id=self.source_id,
                width=224,
                height=224,
                size=len(self.source),
                sha256=self.source_sha,
                archived=False,
                input_role='source',
                generation_preprocessing=prep,
                adapter_preprocessing=flow.conditioning(self.settings),
            )
        ]
        buffer = io.BytesIO()
        Image.new('RGB', (1024, 1024), 'green').save(buffer, 'PNG')
        self.image = buffer.getvalue()
        self.runtime = dict(engine=dict(comfyui='mock'))

    def snapshots(self):
        return dict(
            workflow_id=flow.ID,
            reference_settings=self.settings,
            reference_metadata=self.refs,
            model_metadata=self.model,
            component_metadata=self.components,
            runtime_metadata=self.runtime,
            measurements=None,
            lora_metadata=[],
        )

    def job(self):
        return super().job() | self.snapshots()

    def artwork(self):
        return super().artwork() | self.snapshots() | dict(width=1024, height=1024)

    def handle(self, request):
        path = request.url.path
        if path == '/api/reference/generate':
            self.submissions += 1
            body = json.loads(request.content)
            self.job_id = body.pop('request_id')
            assert body == self.settings
            self.workflow = flow.build(self.settings, self.job_id)
            if self.lose_submission:
                raise httpx.ReadTimeout('lost', request=request)
            value = self.job()
        elif path == '/api/models':
            value = dict(
                engine_url=self.engine, synced_at='time', sync_error=None, models=[self.model]
            )
        elif path == '/api/reference-components/sync':
            value = dict(
                engine_url=self.engine,
                synced_at='time',
                sync_error=None,
                components=self.components,
            )
        elif path == '/api/assets/' + self.source_id:
            value = self.refs[0]
        elif path in (
            '/api/jobs/' + str(self.job_id) + '/creation-settings',
            '/api/artworks/' + self.artwork_id + '/creation-settings',
        ):
            value = dict(
                settings=self.settings | self.restore_override,
                model_version=self.job_version,
                reference_metadata=self.refs,
                component_metadata=self.components,
                runtime_metadata=self.runtime,
            )
        elif path == '/api/jobs/' + str(self.job_id) + '/reference-image':
            value = self.source
        else:
            response = super().handle(request)
            if path == '/api/engine/capabilities/sync':
                return httpx.Response(
                    200,
                    json=response.json()
                    | dict(sampler_names=['euler_ancestral'], schedulers=['normal']),
                )
            return response
        self.seen.append((request.method, path))
        return (
            httpx.Response(200, content=value)
            if isinstance(value, bytes)
            else httpx.Response(200, json=value)
        )


class ReferenceAcceptanceTests(unittest.TestCase):
    def check(self, platform, previous=None, verified=True):
        clock = Clock()
        with (
            httpx.Client(
                base_url='http://127.0.0.1:8000', transport=httpx.MockTransport(platform.handle)
            ) as client,
            patch.object(
                check.downloader, '_paths', return_value=(Path(__file__), None, None, None)
            ),
            patch.object(check.downloader, '_verified', return_value=verified),
        ):
            return platform.runner(
                client, platform.engine, platform.checkpoint, clock=clock.now, sleep=clock.sleep
            ).run(previous)

    def test_modes_seeds_scenes_once_then_get_only(self):
        for mode in ['style', 'character']:
            for seed in check.SEEDS:
                for scene in check.SCENES:
                    p = ReferencePlatform(mode, seed, scene, lose_submission=True)
                    report = self.check(p)
                    self.assertEqual(report['status'], 'passed', report)
                    self.assertEqual(p.submissions, 1)
                    self.assertEqual(str(report['workflow']['5']['inputs']['seed']), seed)
                    p.seen.clear()
                    self.assertEqual(self.check(p, report, verified=False)['status'], 'passed')
                    self.assertTrue(all(method == 'GET' for method, _ in p.seen))

    def test_tampered_source_family_mode_and_version_fail_before_network(self):
        p = ReferencePlatform()
        original = self.check(p)
        self.assertEqual(original['status'], 'passed', original)
        for part in ['source', 'family', 'mode', 'version']:
            report = copy.deepcopy(original)
            if part == 'source':
                report['original_assets'][0]['sha256'] = 'b' * 64
            if part == 'family':
                report['component_metadata'][1]['family'] = 'other'
            if part == 'mode':
                report['settings']['reference_mode'] = 'character'
            if part == 'version':
                report['reference_metadata'][0]['generation_preprocessing']['version'] = 2
            p.seen.clear()
            self.assertEqual(self.check(p, report)['stage'], 'validate_report')
            self.assertEqual(p.seen, [])

    def test_wrong_local_weight_or_saved_input_cannot_pass(self):
        p = ReferencePlatform()
        self.assertEqual(self.check(p, verified=False)['status'], 'failed')
        self.assertEqual(p.submissions, 0)
        original = self.check(p)
        p.source = b'changed'
        p.seen.clear()
        self.assertEqual(self.check(p, original)['status'], 'failed')
        self.assertTrue(all(method == 'GET' for method, _ in p.seen))


class ReferenceInstallTests(unittest.TestCase):
    def test_fixed_weight_categories_readonly_plan_and_source_pin(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            for identifier, category in [
                ('ip-adapter-plus-sdxl-vit-h', 'ipadapter'),
                ('clip-vision-vit-h', 'clip_vision'),
            ]:
                value = install_model.manifest(identifier)
                plan = install_model.plan(value, workspace=workspace)
                self.assertEqual(
                    Path(plan['target']).parent, workspace / 'runtime/ComfyUI/models' / category
                )
                self.assertEqual(list(workspace.iterdir()), [])
                with self.assertRaises(check.downloader.InstallationError):
                    check.downloader.validate_manifest(
                        value | dict(source=value['source'] | dict(revision='main'))
                    )

    def test_node_check_no_writes_install_fixed_blobs_reuse_and_tamper_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            with self.assertRaises(FileNotFoundError):
                nodes.install(workspace=workspace, check=True)
            self.assertEqual(list(workspace.iterdir()), [])
            manifest = json.loads((nodes.ROOT / 'models/ipadapter-nodes.json').read_text())
            originals = {
                r['path']: ('fixture file: ' + r['path']).encode() for r in manifest['files']
            }
            for row in manifest['files']:
                raw = originals[row['path']]
                row['git_blob_sha1'] = hashlib.sha1(
                    b'blob ' + str(len(raw)).encode() + b'\0' + raw
                ).hexdigest()
            (workspace / 'models').mkdir()
            (workspace / 'models/ipadapter-nodes.json').write_text(json.dumps(manifest))

            def handle(request):
                self.assertIn('/' + nodes.REVISION + '/', str(request.url))
                return httpx.Response(200, content=originals[request.url.path.rsplit('/', 1)[-1]])

            with (
                patch.object(nodes, 'ROOT', workspace),
                httpx.Client(transport=httpx.MockTransport(handle)) as client,
            ):
                result = nodes.install(workspace=workspace, client=client)
                self.assertFalse(result['reused'])
                self.assertTrue(nodes.install(workspace=workspace, check=True)['reused'])
                path = Path(result['path']) / 'utils.py'
                path.write_bytes(b'changed')
                with self.assertRaises(ValueError):
                    nodes.install(workspace=workspace, client=client)
                self.assertEqual(path.read_bytes(), b'changed')
