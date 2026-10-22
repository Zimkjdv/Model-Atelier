import inspect
import importlib.util
import asyncio
from pathlib import Path
import tempfile
import subprocess
import io
import json
from types import SimpleNamespace
from uuid import uuid4
import unittest
from urllib.parse import parse_qs, urlsplit
from unittest.mock import patch

import httpx
from PIL import Image

from backend import (jobs, main, test_api, test_submissions, test_flux_workflows,
                     test_image_workflows, test_inpaint_workflows, test_control_workflows,
                     test_inpaint_feather, test_control_edges, execution_device, workflows, catalog, gallery)
from scripts import install_execution_device


PATH = '/model_atelier/execution-device'


def report(probe_id, status='unavailable'):
    return dict(schema_version=1, producer='model-atelier-execution-device-v1', probe_id=probe_id,
                status=status, reason='backend_unavailable' if status == 'unavailable' else 'device_selected',
                device=dict(type='cuda', index=0), backend_available=status == 'available')


def device_remote(remote, payload=None, hook=None):
    regular = remote.get.side_effect

    async def get(url):
        if urlsplit(url).path == PATH:
            if hook:
                hook()
            nonce = parse_qs(urlsplit(url).query)['probe_id'][0]
            data = report(nonce) if payload is None else payload(nonce)
            if isinstance(data, Exception):
                raise data
            return httpx.Response(200, json=data, request=httpx.Request('GET', url))
        result = regular(url)
        return await result if inspect.isawaitable(result) else result

    remote.get.side_effect = get
    return remote


class ExecutionDeviceSubmissionTests(unittest.TestCase):
    setUp = test_api.ApiTests.setUp
    tearDown = test_api.ApiTests.tearDown
    payload = test_submissions.SubmissionTests.payload

    def test_unavailable_device_blocks_all_generation_before_upload_and_keeps_uuid(self):
        fixtures = [
            ('/api/generate', test_submissions.SubmissionTests, 'payload'),
            ('/api/generate', test_image_workflows.ImageWorkflowTests, 'body'),
            ('/api/inpaint/generate', test_inpaint_workflows.InpaintTests, 'body'),
            ('/api/inpaint-feather/generate', test_inpaint_feather.FeatherTests, 'body'),
            ('/api/control/generate', test_control_workflows.ControlTests, 'body'),
            ('/api/control-edge/generate', test_control_edges.ControlEdgeTests, 'body'),
            ('/api/flux/generate', test_flux_workflows.FluxWorkflowTests, 'body'),
        ]
        for path, fixture, factory in fixtures:
            with self.subTest(path=path, fixture=fixture.__name__):
                body = getattr(fixture, factory)(self)
                remote = (fixture.remote(self) if fixture in (test_submissions.SubmissionTests, test_flux_workflows.FluxWorkflowTests)
                          else fixture.remote(self, body))
                device_remote(remote)
                with patch('backend.submissions.httpx.AsyncClient', return_value=remote):
                    response = self.client.post(path, json=body)
                self.assertEqual(response.status_code, 409, response.text[:400])
                remote.post.assert_not_awaited()
                job = jobs.get(self.db, body['request_id'])
                self.assertEqual(job['status'], 'failed')
                self.assertEqual(job['failure_info']['code'], 'execution_device_unavailable')
                self.assertEqual(job['runtime_metadata']['execution_device']['status'], 'unavailable')
                self.assertEqual(job['runtime_metadata']['execution_device']['engine_url'], body['engine_url'])
                with patch('backend.submissions.httpx.AsyncClient', side_effect=AssertionError('no re-probe or replay')):
                    self.assertEqual(self.client.post(path, json=body).json(), job)
                self.assertEqual(self.client.get('/api/health').status_code, 200)
                self.assertEqual(self.client.get('/api/settings').status_code, 200)
                self.assertEqual(self.client.get('/api/artworks').status_code, 200)
                self.assertEqual(self.client.get('/api/assets').status_code, 200)
                self.assertFalse((self.host.DATA / 'job_inputs' / body['request_id']).exists())

    def test_raw_job_submission_uses_same_guard(self):
        body = self.payload()
        raw = {key: body[key] for key in ('request_id', 'engine_url', 'checkpoint')}
        raw['workflow'] = workflows.build(main.DraftInput.model_validate(body).model_dump())
        remote = device_remote(test_submissions.SubmissionTests.remote(self))
        with patch('backend.submissions.httpx.AsyncClient', return_value=remote):
            self.assertEqual(self.client.post('/api/jobs', json=raw).status_code, 409)
        remote.post.assert_not_awaited()

    def test_existing_model_node_and_architecture_guards_still_apply(self):
        for condition, expected in [('checkpoint', 'no_checkpoints'), ('node', 'missing_nodes'), ('architecture', 'unsupported_architecture')]:
            body = self.payload()
            remote = test_submissions.SubmissionTests.remote(self, [] if condition == 'checkpoint' else None)
            if condition == 'node':
                regular = remote.get.side_effect
                remote.get.side_effect = lambda url: (httpx.Response(200, json={}, request=httpx.Request('GET', url))
                                                       if url.endswith('/VAEDecode') else regular(url))
            if condition == 'architecture':
                catalog.merge(self.db, body['engine_url'], [body['checkpoint']])
                catalog.update_metadata(self.db, body['engine_url'], body['checkpoint'], dict(architecture='flux'))
            device_remote(remote)
            with patch('backend.submissions.httpx.AsyncClient', return_value=remote):
                response = self.client.post('/api/generate', json=body)
            self.assertIn(response.status_code, (409, 422), response.text[:400])
            self.assertEqual(jobs.get(self.db, body['request_id'])['failure_info']['code'], expected)
            remote.post.assert_not_awaited()

    def test_missing_malformed_offline_and_cpu_reports_do_not_block(self):
        variants = [
            lambda nonce: {},
            lambda nonce: dict(system={}, devices=[]),
            lambda nonce: httpx.ConnectError('offline'),
            lambda nonce: report('stale-probe'),
            lambda nonce: report(nonce) | dict(schema_version=True),
            lambda nonce: report(nonce) | dict(backend_available='false'),
            lambda nonce: report(nonce) | dict(device=dict(type='cpu', index=None)),
            lambda nonce: report(nonce) | dict(device=dict(type='cuda', index=True)),
            lambda nonce: report(nonce) | dict(producer='other'),
            lambda nonce: report(nonce) | dict(reason='unknown'),
            lambda nonce: report(nonce, 'available') | dict(device=dict(type='cpu', index=None), backend_available=None),
        ]
        for payload in variants:
            body = self.payload()
            remote = device_remote(test_submissions.SubmissionTests.remote(self), payload)
            with patch('backend.submissions.httpx.AsyncClient', return_value=remote):
                response = self.client.post('/api/generate', json=body)
            self.assertEqual(response.status_code, 200, response.text)
            remote.post.assert_awaited_once()
            self.assertNotEqual(response.json()['runtime_metadata']['execution_device']['status'], 'unavailable')

    def test_engine_change_during_device_probe_does_not_dispatch(self):
        body = self.payload()
        remote = device_remote(test_submissions.SubmissionTests.remote(self), hook=lambda:
            self.client.put('/api/settings', json=dict(comfy_url='http://127.0.0.1:9999')))
        with patch('backend.submissions.httpx.AsyncClient', return_value=remote):
            response = self.client.post('/api/generate', json=body)
        self.assertEqual(response.status_code, 409)
        remote.post.assert_not_awaited()
        self.assertEqual(jobs.get(self.db, body['request_id'])['failure_info']['code'], 'engine_changed')

    def test_repaired_or_other_engine_only_affects_new_requests(self):
        body = self.payload()
        with patch('backend.submissions.httpx.AsyncClient', return_value=device_remote(test_submissions.SubmissionTests.remote(self))):
            self.assertEqual(self.client.post('/api/generate', json=body).status_code, 409)
        original = jobs.get(self.db, body['request_id'])
        for engine in (body['engine_url'], 'http://127.0.0.1:9191'):
            self.client.put('/api/settings', json=dict(comfy_url=engine))
            fresh = body | dict(request_id=str(uuid4()), engine_url=engine)
            remote = device_remote(test_submissions.SubmissionTests.remote(self), lambda nonce: report(nonce, 'available'))
            with patch('backend.submissions.httpx.AsyncClient', return_value=remote):
                self.assertEqual(self.client.post('/api/generate', json=fresh).status_code, 200)
            remote.post.assert_awaited_once()
        self.assertEqual(jobs.get(self.db, body['request_id']), original)

    def test_unavailable_device_does_not_block_drafts_offline_artwork_or_cpu_preview(self):
        body = self.payload()
        remote = device_remote(test_submissions.SubmissionTests.remote(self), lambda nonce: report(nonce, 'available'))
        with patch('backend.submissions.httpx.AsyncClient', return_value=remote):
            job = self.client.post('/api/generate', json=body).json()
        image = io.BytesIO()
        Image.new('RGB', (8, 8), 'white').save(image, format='PNG')
        artwork, _ = gallery.save(self.db, self.host.DATA / 'artworks', job,
                                 dict(node_id='7', filename='old.png', subfolder='', type='output'), image.getvalue())
        body = self.payload()
        with patch('backend.submissions.httpx.AsyncClient', return_value=device_remote(test_submissions.SubmissionTests.remote(self))):
            self.assertEqual(self.client.post('/api/generate', json=body).status_code, 409)
        preview = test_inpaint_feather.FeatherTests.body(self)
        preview.pop('request_id')
        with patch('backend.submissions.httpx.AsyncClient', side_effect=AssertionError('offline actions must not probe')):
            self.assertEqual(self.client.post('/api/drafts', json=self.payload()).status_code, 201)
            self.assertEqual(self.client.get('/api/artworks/' + artwork['id'] + '/image').content, image.getvalue())
            self.assertEqual(self.client.post('/api/inpaint-feather/preview', json=preview).status_code, 200)

    def test_engine_status_uses_only_fresh_selected_engine_report_even_when_stats_fail(self):
        for stats_fail, switch in [(False, False), (True, False), (False, True)]:
            remote = test_submissions.SubmissionTests.remote(self)
            regular = remote.get.side_effect
            def get(url):
                if url.endswith('/system_stats'):
                    if stats_fail:
                        raise httpx.ConnectError('stats unavailable')
                    return httpx.Response(200, json=dict(system={}, devices=[]), request=httpx.Request('GET', url))
                return regular(url)
            remote.get.side_effect = get
            device_remote(remote, hook=(lambda: self.client.put('/api/settings', json=dict(comfy_url='http://localhost:9999'))) if switch else None)
            with patch('backend.main.httpx.AsyncClient', return_value=remote):
                response = self.client.get('/api/engine')
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()['execution_device']['status'], 'unknown' if switch else 'unavailable')
            remote.post.assert_not_awaited()


class ExecutionDeviceContractTests(unittest.IsolatedAsyncioTestCase):
    async def test_bounded_http_failure_and_nonce_contract(self):
        for status, payload in [(404, {}), (503, {}), (200, {'oversized': 'x' * 17000}),
                                (200, {'status': 'unavailable'}), (200, report('old-request'))]:
            async with httpx.AsyncClient(transport=httpx.MockTransport(lambda request:
                    httpx.Response(status, json=payload))) as client:
                value = await execution_device.fetch(client, 'http://selected-engine')
            self.assertEqual(value['status'], 'unknown')
            self.assertEqual(value['engine_url'], 'http://selected-engine')
            self.assertIsNone(value['device'])

    async def test_timeout_is_unknown(self):
        async def wait(request):
            await asyncio.sleep(0.05)
            return httpx.Response(200)
        real_wait = asyncio.wait_for
        async def short_wait(future, timeout):
            return await real_wait(future, 0.001)
        async with httpx.AsyncClient(transport=httpx.MockTransport(wait)) as client:
            with patch.object(execution_device.asyncio, 'wait_for', new=short_wait):
                result = await execution_device.fetch(client, 'http://selected-engine')
        self.assertEqual(result['status'], 'unknown')


class ExecutionDeviceProbeTests(unittest.TestCase):
    def setUp(self):
        self.repository = Path(__file__).resolve().parents[1]
        self.source = self.repository / 'comfyui_extensions' / 'model_atelier_execution_device'
        spec = importlib.util.spec_from_file_location('atelier_device_probe_test', self.source / 'probe.py')
        self.probe = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.probe)

    def management(self, kind, available=True):
        backend = SimpleNamespace(is_available=lambda: available)
        torch = SimpleNamespace(backends=SimpleNamespace(mps=backend), **{kind: backend})
        return SimpleNamespace(get_torch_device=lambda: SimpleNamespace(type=kind, index=None if kind in ('cpu', 'mps') else 0), torch=torch)

    def test_cpu_and_other_devices_are_not_a_gpu_whitelist(self):
        for kind in ('cpu', 'cuda', 'mps', 'xpu', 'npu', 'mlu', 'privateuseone'):
            result = self.probe.collect(self.management(kind), 'test-probe')
            self.assertEqual(result['status'], 'available')
            self.assertEqual(execution_device.normalize(result, 'http://engine', 'test-probe')['status'], 'available')

    def test_explicit_negative_and_device_selection_failure(self):
        for kind in ('cuda', 'mps', 'xpu', 'npu', 'mlu'):
            result = self.probe.collect(self.management(kind, False), 'test-probe')
            self.assertEqual(result['status'], 'unavailable')
            self.assertEqual(execution_device.normalize(result, 'http://engine', 'test-probe')['status'], 'unavailable')
        management = self.management('cuda')
        def fail():
            raise RuntimeError('PRIVATE_EXCEPTION')
        management.get_torch_device = fail
        result = self.probe.collect(management, 'test-probe')
        self.assertEqual(result['reason'], 'device_selection_failed')
        self.assertEqual(execution_device.normalize(result, 'http://engine', 'test-probe')['status'], 'unavailable')
        self.assertNotIn('PRIVATE_EXCEPTION', str(result))

    def test_partial_or_invalid_backend_query_remains_unknown(self):
        self.assertEqual(self.probe.collect(SimpleNamespace(), 'test-probe')['status'], 'unknown')
        management = self.management('cuda')
        def fail():
            raise RuntimeError('PRIVATE_EXCEPTION')
        management.torch.cuda.is_available = fail
        self.assertEqual(self.probe.collect(management, 'test-probe')['status'], 'unknown')
        self.assertEqual(self.probe.collect(self.management('cuda', 'false'), 'test-probe')['status'], 'unknown')
        partial = report('test-probe')
        partial.pop('backend_available')
        self.assertEqual(execution_device.normalize(partial, 'http://engine', 'test-probe')['status'], 'unknown')

    def test_installer_is_repeatable_and_preserves_other_extensions(self):
        import shutil
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            shutil.copytree(self.source, root / 'comfyui_extensions' / self.source.name, ignore=shutil.ignore_patterns('__pycache__'))
            other = root / 'runtime' / 'ComfyUI' / 'custom_nodes' / 'other.py'
            other.parent.mkdir(parents=True)
            other.write_text('existing extension', encoding='utf-8')
            target = install_execution_device.install(root)
            before = (target / 'probe.py').stat().st_mtime_ns
            install_execution_device.install(root)
            self.assertEqual((target / 'probe.py').stat().st_mtime_ns, before)
            self.assertEqual((target / 'probe.py').read_bytes(), (self.source / 'probe.py').read_bytes())
            self.assertEqual(other.read_text(encoding='utf-8'), 'existing extension')

    def test_real_aiohttp_route_rejects_bad_nonce_and_handles_negative_cpu_unknown(self):
        python = self.repository / 'runtime' / 'ComfyUI' / '.venv' / 'Scripts' / 'python.exe'
        if not python.is_file():
            self.skipTest('Managed ComfyUI Python is not installed')
        result = subprocess.run([str(python), str(self.repository / 'scripts' / 'verify_execution_device.py')],
                                capture_output=True, text=True, timeout=20,
                                creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(len(json.loads(result.stdout)['route_checks']), 4)
