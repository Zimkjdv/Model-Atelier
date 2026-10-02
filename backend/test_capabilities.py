import copy
import io
import json
import unittest
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import httpx
from PIL import Image

from backend import capabilities, catalog, gallery, jobs, main, test_api, test_submissions, workflows


class CapabilityTests(unittest.TestCase):
    setUp = test_api.ApiTests.setUp
    tearDown = test_api.ApiTests.tearDown

    def payload(self, **changes):
        value = main.DraftInput(title='能力驗證', engine_url='http://127.0.0.1:8188',
                                checkpoint='test.safetensors', width=832, height=1216,
                                seed=str(2**64 - 1), cfg=5.55).model_dump(mode='json', exclude={'revision'})
        return value | {'request_id': str(uuid4())} | changes

    def response(self, value, url='http://test', status=200):
        return httpx.Response(status, request=httpx.Request('GET', url), json=value)

    def remote(self, caps=None, capability_error=None):
        remote = AsyncMock()
        remote.__aenter__.return_value = remote

        def get(url):
            name = url.rsplit('/', 1)[-1]
            if name in {'CLIPTextEncode', 'EmptyLatentImage', 'VAEDecode', 'SaveImage'}:
                return self.response({name: {'input': {'required': {}}}}, url)
            if url.endswith('/object_info/KSampler'):
                if capability_error:
                    raise capability_error
                return self.response(caps if caps is not None else test_submissions.sampler_capabilities(), url)
            return self.response({'CheckpointLoaderSimple': {'input': {'required': {'ckpt_name': [['test.safetensors']]}}}}, url)

        remote.get.side_effect = get
        remote.post.return_value = self.response({'prompt_id': str(uuid4()), 'number': 0, 'node_errors': {}})
        return remote

    def raw(self, body, **graph_changes):
        graph = workflows.build(body)
        for name, value in graph_changes.items():
            graph['5']['inputs'][name] = value
        return {'request_id': body['request_id'], 'engine_url': body['engine_url'],
                'checkpoint': body['checkpoint'], 'workflow': graph}

    def test_live_api_returns_platform_intersection_and_deduplicates_preserving_order(self):
        caps = test_submissions.sampler_capabilities()
        caps['KSampler']['input']['required']['sampler_name'][0] = ['euler', 'dpmpp_2m', 'euler']
        caps['KSampler']['input']['required']['scheduler'][0] = ['karras', 'normal', 'karras']
        remote = self.remote(caps)
        with patch('backend.capabilities.httpx.AsyncClient', return_value=remote) as factory:
            result = self.client.get('/api/engine/capabilities')
        self.assertEqual(result.status_code, 200, result.text)
        value = result.json()
        self.assertEqual(value['sampler_names'], ['euler', 'dpmpp_2m'])
        self.assertEqual(value['schedulers'], ['karras', 'normal'])
        self.assertEqual(value['bounds'], {'steps': {'min': 1, 'max': 150}, 'cfg': {'min': 0, 'max': 30}, 'denoise': {'min': 0, 'max': 1}})
        self.assertEqual(value['engine_bounds']['steps']['max'], 10000)
        self.assertTrue(value['available'])
        self.assertFalse(value['stale'])
        self.assertTrue(value['engine_matches'])
        self.assertIsNone(value['sync_error'])
        self.assertIsNotNone(value['synced_at'])
        self.assertEqual(capabilities.read(self.db, value['engine_url'])['sampler_names'], value['sampler_names'])
        self.assertFalse(factory.call_args.kwargs['trust_env'])
        remote.post.assert_not_awaited()

    def test_offline_cache_isolation_and_no_snapshot_are_explicit(self):
        original = capabilities.write(self.db, 'http://127.0.0.1:8188', capabilities.parse(test_submissions.sampler_capabilities()))
        offline = self.remote(capability_error=httpx.ConnectError('offline'))
        with patch('backend.capabilities.httpx.AsyncClient', return_value=offline):
            stale = self.client.get('/api/engine/capabilities').json()
            self.assertTrue(stale['available'])
            self.assertTrue(stale['stale'])
            self.assertEqual(stale['synced_at'], original['synced_at'])
            self.assertIsNotNone(stale['sync_error'])
            self.client.put('/api/settings', json={'comfy_url': 'http://127.0.0.1:9999'})
            missing = self.client.post('/api/engine/capabilities/sync').json()
        self.assertFalse(missing['available'])
        self.assertTrue(missing['stale'])
        self.assertEqual(missing['engine_url'], 'http://127.0.0.1:9999')
        self.assertEqual(missing['sampler_names'], [])
        self.assertEqual(missing['bounds'], {})
        self.assertIsNone(missing['synced_at'])
        self.assertEqual(capabilities.read(self.db, original['engine_url']), original)

    def test_malformed_or_http_failure_keeps_last_good_snapshot(self):
        original = capabilities.write(self.db, 'http://127.0.0.1:8188', capabilities.parse(test_submissions.sampler_capabilities()))
        for bad in ({}, {'KSampler': None}):
            with patch('backend.capabilities.httpx.AsyncClient', return_value=self.remote(bad)):
                value = self.client.post('/api/engine/capabilities/sync').json()
            self.assertTrue(value['available'])
            self.assertTrue(value['stale'])
            self.assertEqual(value['sampler_names'], original['sampler_names'])
            self.assertEqual(capabilities.read(self.db, original['engine_url']), original)
        remote = self.remote()
        remote.get.side_effect = None
        remote.get.return_value = self.response({}, status=500)
        with patch('backend.capabilities.httpx.AsyncClient', return_value=remote):
            value = self.client.get('/api/engine/capabilities').json()
            self.assertTrue(value['stale'])
            self.assertIn('HTTP 500', value['sync_error'])
            self.assertIn('暫時不可用', value['sync_error'])

    def test_capability_sync_reports_engine_changed_during_query(self):
        remote = self.remote()

        def query(url):
            self.client.put('/api/settings', json={'comfy_url': 'http://127.0.0.1:9999'})
            return self.response(test_submissions.sampler_capabilities(), url)

        remote.get.side_effect = query
        with patch('backend.capabilities.httpx.AsyncClient', return_value=remote):
            value = self.client.get('/api/engine/capabilities').json()
        self.assertEqual(value['engine_url'], 'http://127.0.0.1:8188')
        self.assertEqual(value['current_engine_url'], 'http://127.0.0.1:9999')
        self.assertFalse(value['engine_matches'])
        self.assertTrue(value['stale'])
        self.assertFalse(capabilities.read(self.db, 'http://127.0.0.1:9999')['available'])

    def test_parser_rejects_invalid_options_numeric_bounds_and_empty_intersections(self):
        original = test_submissions.sampler_capabilities()
        cases = []
        for name, value in [('sampler_name', []), ('sampler_name', [[]]), ('scheduler', [['normal', False]]),
                             ('sampler_name', [['euler', 'not-a-token']]), ('scheduler', [['x' * 65]]),
                             ('steps', ['FLOAT', {'min': 1, 'max': 10000, 'default': 20}]),
                             ('steps', ['INT', {'min': True, 'max': 10000, 'default': 20}]),
                             ('steps', ['INT', {'min': 1.0, 'max': 10000, 'default': 20}]),
                             ('steps', ['INT', {'min': 151, 'max': 10000, 'default': 200}]),
                             ('cfg', ['FLOAT', {'min': 10, 'max': 5, 'default': 8}]),
                             ('cfg', ['FLOAT', {'min': 0, 'max': 30, 'default': 31}]),
                             ('cfg', ['FLOAT', {'min': 0, 'max': float('inf'), 'default': 7}]),
                             ('denoise', ['FLOAT', {'min': float('nan'), 'max': 1, 'default': 1}]),
                             ('denoise', ['FLOAT', {'min': 0, 'max': 1}]),
                             ('cfg', ['FLOAT', {'min': 0, 'max': 10**500, 'default': 7}])]:
            caps = copy.deepcopy(original)
            caps['KSampler']['input']['required'][name] = value
            cases.append(caps)
        for caps in cases:
            with self.subTest(caps=caps):
                with self.assertRaises(ValueError):
                    capabilities.parse(caps)

    def test_narrow_engine_limits_and_widget_step_do_not_silently_change_values(self):
        caps = test_submissions.sampler_capabilities()
        caps['KSampler']['input']['required']['steps'][1] = dict(min=10, max=100, default=20)
        caps['KSampler']['input']['required']['cfg'][1] = dict(min=5, max=6, default=5.5, step=0.1, round=0.01)
        value = capabilities.parse(caps)
        self.assertEqual(value['bounds']['steps'], {'min': 10, 'max': 100})
        body = self.payload(steps=20, cfg=5.55)
        capabilities.validate_workflow(workflows.build(body), value)
        with patch('backend.capabilities.httpx.AsyncClient', return_value=self.remote(caps)):
            success = self.client.post('/api/generate', json=body)
        self.assertEqual(success.status_code, 200, success.text)
        self.assertEqual(success.json()['workflow']['5']['inputs']['cfg'], 5.55)

    def test_generate_checks_live_options_and_ranges_before_queueing(self):
        changes = [{'sampler_name': 'unsupported'}, {'scheduler': 'unsupported'}, {'cfg': 7}, {'steps': 5}, {'denoise': 1}]
        caps = test_submissions.sampler_capabilities()
        required = caps['KSampler']['input']['required']
        required['steps'][1] = dict(min=10, max=100, default=20)
        required['cfg'][1] = dict(min=5, max=6, default=5.5)
        required['denoise'][1] = dict(min=0, max=0.9, default=0.9)
        for change in changes:
            with self.subTest(change=change):
                remote = self.remote(caps)
                with patch('backend.capabilities.httpx.AsyncClient', return_value=remote):
                    result = self.client.post('/api/generate', json=self.payload(denoise=0.8) | change)
                self.assertEqual(result.status_code, 422, result.text)
                self.assertIn('尚未提交', result.json()['detail']['message'])
                remote.post.assert_not_awaited()
                self.assertEqual(jobs.get(self.db, result.json()['detail']['job_id'])['status'], 'failed')

    def test_direct_jobs_validates_all_samplers_and_constant_scalar_fields(self):
        for changes in ({'scheduler': 'bad'}, {'sampler_name': ['2', 0]}, {'steps': 151}, {'steps': True},
                        {'cfg': 31}, {'cfg': ['2', 0]}, {'denoise': 1.1}, {'seed': str(2**64 - 1)},
                        {'seed': 2**64}, {'seed': True}):
            with self.subTest(changes=changes):
                body = self.payload()
                raw = self.raw(body)
                # The first sampler is valid; a second invalid sampler must not
                # bypass validation even when disconnected from the output.
                raw['workflow']['second'] = copy.deepcopy(raw['workflow']['5'])
                raw['workflow']['second']['inputs'].update(changes)
                remote = self.remote()
                with patch('backend.capabilities.httpx.AsyncClient', return_value=remote):
                    result = self.client.post('/api/jobs', json=raw)
                self.assertEqual(result.status_code, 422, result.text)
                remote.post.assert_not_awaited()

    def test_direct_jobs_rejects_missing_sampling_fields_and_unsafe_latent(self):
        for field in ('steps', 'cfg', 'denoise', 'seed', 'sampler_name', 'scheduler'):
            raw = self.raw(self.payload())
            raw['workflow']['5']['inputs'].pop(field)
            remote = self.remote()
            with patch('backend.capabilities.httpx.AsyncClient', return_value=remote):
                self.assertEqual(self.client.post('/api/jobs', json=raw).status_code, 422)
            remote.post.assert_not_awaited()
        for changes in ({'width': 8193}, {'height': 63}, {'width': 65}, {'width': True}, {'batch_size': 2}, {'batch_size': True}):
            raw = self.raw(self.payload())
            raw['workflow']['4']['inputs'].update(changes)
            remote = self.remote()
            with patch('backend.capabilities.httpx.AsyncClient', return_value=remote):
                self.assertEqual(self.client.post('/api/jobs', json=raw).status_code, 422)
            remote.post.assert_not_awaited()
        raw = self.raw(self.payload())
        raw['workflow'].pop('5')
        remote = self.remote()
        with patch('backend.capabilities.httpx.AsyncClient', return_value=remote):
            self.assertEqual(self.client.post('/api/jobs', json=raw).status_code, 422)
        remote.post.assert_not_awaited()

    def test_stale_cache_never_authorizes_submission_or_direct_api_bypass(self):
        snapshot = capabilities.write(self.db, 'http://127.0.0.1:8188', capabilities.parse(test_submissions.sampler_capabilities()))
        for endpoint in ('/api/generate', '/api/jobs'):
            body = self.payload()
            remote = self.remote(capability_error=httpx.ReadTimeout('offline capability query'))
            with patch('backend.capabilities.httpx.AsyncClient', return_value=remote):
                result = self.client.post(endpoint, json=body if endpoint.endswith('generate') else self.raw(body))
            self.assertEqual(result.status_code, 503, result.text)
            remote.post.assert_not_awaited()
            self.assertEqual(capabilities.read(self.db, body['engine_url']), snapshot)

    def test_malformed_or_oversized_live_response_blocks_submit(self):
        for value in ({}, {'KSampler': {'input': {'required': None}}}):
            remote = self.remote(value)
            with patch('backend.capabilities.httpx.AsyncClient', return_value=remote):
                result = self.client.post('/api/generate', json=self.payload())
            self.assertEqual(result.status_code, 502, result.text)
            remote.post.assert_not_awaited()
        remote = self.remote()
        regular = remote.get.side_effect

        def huge(url):
            return httpx.Response(200, request=httpx.Request('GET', url), content=b'x' * (capabilities.MAX_RESPONSE + 1)) if url.endswith('/KSampler') else regular(url)

        remote.get.side_effect = huge
        with patch('backend.capabilities.httpx.AsyncClient', return_value=remote):
            self.assertEqual(self.client.post('/api/generate', json=self.payload()).status_code, 502)
        remote.post.assert_not_awaited()

    def test_engine_switch_during_submission_validation_never_posts_to_either_engine(self):
        body = self.payload()
        remote = self.remote()
        regular = remote.get.side_effect

        def changed(url):
            if url.endswith('/KSampler'):
                self.client.put('/api/settings', json={'comfy_url': 'http://127.0.0.1:9999'})
            return regular(url)

        remote.get.side_effect = changed
        with patch('backend.capabilities.httpx.AsyncClient', return_value=remote):
            result = self.client.post('/api/generate', json=body)
        self.assertEqual(result.status_code, 409, result.text)
        self.assertIn('驗證期間', result.json()['detail']['message'])
        remote.post.assert_not_awaited()
        self.assertTrue(all(call.args[0].startswith(body['engine_url']) for call in remote.get.await_args_list))
        self.assertEqual(jobs.get(self.db, body['request_id'])['engine_url'], body['engine_url'])

    def test_exact_request_retries_keep_result_version_seed_and_do_not_probe_changed_engine(self):
        body = self.payload()
        value = catalog.merge(self.db, body['engine_url'], [body['checkpoint']])
        value['models'][0]['version'] = 'original-v1'
        catalog.write(self.db, value)
        remote = self.remote()
        with patch('backend.capabilities.httpx.AsyncClient', return_value=remote):
            result = self.client.post('/api/generate', json=body)
        original = result.json()
        self.assertEqual(result.status_code, 200, result.text)
        self.assertEqual(original['workflow']['5']['inputs']['seed'], 2**64 - 1)
        self.assertEqual(original['model_version'], 'original-v1')
        self.client.put('/api/settings', json={'comfy_url': 'http://127.0.0.1:9999'})
        with patch('backend.capabilities.httpx.AsyncClient', side_effect=AssertionError('idempotent retry must remain local')):
            self.assertEqual(self.client.post('/api/generate', json=body).json(), original)
            self.assertEqual(self.client.post('/api/jobs', json=self.raw(body)).json(), original)
            self.assertEqual(self.client.post('/api/generate', json=body | {'prompt': 'different'}).status_code, 409)

    def test_unsupported_old_values_remain_saveable_and_restorable_offline(self):
        body = self.payload(sampler_name='future_sampler', scheduler='future_scheduler')
        job, _ = jobs.reserve(self.db, str(uuid4()), body['engine_url'], workflows.build(body), body['checkpoint'], 'old-v1')
        image = io.BytesIO()
        Image.new('RGB', (64, 64)).save(image, 'PNG')
        item, _ = gallery.save(self.db, self.db.parent / 'artworks', job,
                              dict(node_id='7', filename='old.png', subfolder='', type='output'), image.getvalue())
        with patch('backend.capabilities.httpx.AsyncClient', side_effect=AssertionError('saving does not query capabilities')):
            saved = self.client.post('/api/drafts', json=body)
            self.assertEqual(saved.status_code, 201, saved.text)
            draft = self.client.get('/api/drafts').json()[0]
            restored = self.client.get('/api/artworks/' + item['id'] + '/creation-settings')
            self.assertEqual(restored.status_code, 200, restored.text)
        self.assertEqual(draft['sampler_name'], body['sampler_name'])
        self.assertEqual(draft['scheduler'], body['scheduler'])
        self.assertEqual(draft['cfg'], 5.55)
        self.assertEqual(restored.json()['settings']['sampler_name'], body['sampler_name'])
        self.assertEqual(restored.json()['settings']['scheduler'], body['scheduler'])
        self.assertEqual(restored.json()['model_version'], 'old-v1')

    def test_direct_valid_workflow_keeps_every_uint64_seed_without_clamping(self):
        body = self.payload()
        raw = self.raw(body)
        raw['workflow']['second'] = copy.deepcopy(raw['workflow']['5'])
        raw['workflow']['second']['inputs']['seed'] = 2**63 + 1
        remote = self.remote()
        with patch('backend.capabilities.httpx.AsyncClient', return_value=remote):
            result = self.client.post('/api/jobs', json=raw)
        self.assertEqual(result.status_code, 200, result.text)
        posted = remote.post.await_args.kwargs['json']['prompt']
        self.assertEqual(posted, raw['workflow'])
        self.assertEqual(posted['5']['inputs']['seed'], 2**64 - 1)
        self.assertEqual(posted['second']['inputs']['seed'], 2**63 + 1)
        self.assertEqual(remote.post.await_count, 1)
