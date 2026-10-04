import copy
import unittest
from unittest.mock import patch
from uuid import uuid4
import httpx

from backend import catalog, loras, main, test_api, test_submissions, workflows

ENGINE = 'http://127.0.0.1:8188'
NAME = 'styles/ink.safetensors'


def loader_definition(names=None):
    return {'LoraLoader': {'input': {'required': {
        'model': ['MODEL'], 'clip': ['CLIP'], 'lora_name': [names if names is not None else [NAME]],
        'strength_model': ['FLOAT', {'min': -100, 'max': 100}],
        'strength_clip': ['FLOAT', {'min': -100, 'max': 100}],
    }}, 'output': ['MODEL', 'CLIP']}}


class LoraSubmissionTests(unittest.TestCase):
    setUp = test_api.ApiTests.setUp
    tearDown = test_api.ApiTests.tearDown

    def body(self):
        return dict(request_id=str(uuid4()), title='LoRA', prompt='a forest', checkpoint='test.safetensors',
                    engine_url=ENGINE, seed=str(2**64-1), width=512, height=512,
                    loras=[dict(name=NAME, enabled=True, strength_model=-0.75, strength_clip=0.125)])

    def prepare(self, base='sdxl', kind='sdxl'):
        catalog.merge(self.db, ENGINE, ['test.safetensors'])
        catalog.update_metadata(self.db, ENGINE, 'test.safetensors', dict(architecture=base))
        loras.merge(self.db, ENGINE, [NAME])
        loras.update_metadata(self.db, ENGINE, NAME, dict(architecture=kind))

    def remote(self, definition=None, hook=None):
        remote = test_submissions.SubmissionTests.remote(self)
        original = remote.get.side_effect
        async def response(url):
            if hook:
                hook(url)
            if url.endswith('/object_info/LoraLoader'):
                if isinstance(definition, BaseException):
                    raise definition
                return httpx.Response(200, request=httpx.Request('GET', url),
                                      json=loader_definition() if definition is None else definition)
            return original(url)
        remote.get.side_effect = response
        return remote

    def submit(self, body, remote):
        with patch('backend.submissions.httpx.AsyncClient', return_value=remote):
            return self.client.post('/api/generate', json=body)

    def test_single_lora_routes_model_and_both_clip_paths_and_keeps_seed(self):
        self.prepare()
        body, remote = self.body(), self.remote()
        result = self.submit(body, remote)
        self.assertEqual(result.status_code, 200, result.text)
        job = result.json()
        self.assertEqual(job['status'], 'queued')
        graph = job['workflow']
        self.assertEqual(len(graph), 8)
        self.assertEqual(graph['5']['inputs']['model'], ['8', 0])
        for node in ('2', '3'):
            self.assertEqual(graph[node]['inputs']['clip'], ['8', 1])
        self.assertEqual(graph['6']['inputs']['vae'], ['1', 2])
        self.assertEqual(graph['5']['inputs']['seed'], 2**64-1)
        self.assertEqual(graph['8']['inputs']['strength_clip'], .125)
        self.assertEqual(remote.post.call_args.kwargs['json']['prompt'], graph)
        self.assertIn('未讀取權重或執行 LoRA', job['preflight_warnings'][0])
        with patch('backend.submissions.httpx.AsyncClient', side_effect=AssertionError('must not replay')):
            self.assertEqual(self.client.post('/api/generate', json=body).json(), job)

    def test_known_architecture_mismatch_blocks_without_engine_contact(self):
        for base, kind in [('sdxl', 'sd1'), ('sd1', 'flux')]:
            self.prepare(base, kind)
            with patch('backend.submissions.httpx.AsyncClient', side_effect=AssertionError('no engine')):
                response = self.client.post('/api/generate', json=self.body())
            self.assertEqual(response.status_code, 422, response.text)
            self.assertIn('架構', response.json()['detail']['message'])

    def test_missing_lo_ra_invalid_definition_and_offline_do_not_dispatch(self):
        cases = [(loader_definition([]), 409), ({}, 422), ([], 502),
                 (loader_definition() | {'LoraLoader': {'input': {'required': {}}}}, 502),
                 (httpx.ConnectError('offline'), 503)]
        for definition, code in cases:
            remote = self.remote(definition)
            result = self.submit(self.body(), remote)
            self.assertEqual(result.status_code, code, result.text)
            remote.post.assert_not_called()
            self.assertEqual(self.client.get('/api/jobs/' + result.json()['detail']['job_id']).json()['status'], 'failed')

    def test_platform_and_engine_strength_intersection_preserves_input(self):
        for field in ('strength_model', 'strength_clip'):
            definition = loader_definition()
            definition['LoraLoader']['input']['required'][field][1] = dict(min=0, max=.1)
            body, remote = self.body(), self.remote(definition)
            result = self.submit(body, remote)
            self.assertEqual(result.status_code, 422, result.text)
            self.assertIn(field, result.json()['detail']['message'])
            remote.post.assert_not_called()
        for low, high in [(True, 1), (1, -1), ('0', 1)]:
            definition = loader_definition()
            definition['LoraLoader']['input']['required']['strength_model'][1] = dict(min=low, max=high)
            self.assertEqual(self.submit(self.body(), self.remote(definition)).status_code, 502)

    def test_metadata_change_during_preflight_blocks_new_mismatch(self):
        for collection, name in [(loras, NAME), (catalog, 'test.safetensors')]:
            self.prepare()
            def changed(url):
                if url.endswith('/object_info/SaveImage'):
                    collection.update_metadata(self.db, ENGINE, name, dict(architecture='sd1'))
            remote = self.remote(hook=changed)
            self.assertEqual(self.submit(self.body(), remote).status_code, 422)
            remote.post.assert_not_called()

    def test_engine_change_during_preflight_blocks_dispatch(self):
        self.prepare()
        def changed(url):
            if url.endswith('/object_info/SaveImage'):
                self.client.put('/api/settings', json={'comfy_url': 'http://127.0.0.1:9999'})
        remote = self.remote(hook=changed)
        self.assertEqual(self.submit(self.body(), remote).status_code, 409)
        remote.post.assert_not_called()

    def test_unknown_registration_is_untested_and_fresh_names_are_authoritative(self):
        self.prepare('unknown', 'other')
        loras.merge(self.db, ENGINE, [])
        result = self.submit(self.body(), self.remote())
        self.assertEqual(result.status_code, 200, result.text)
        self.assertIn('未讀取權重或執行 LoRA', result.json()['preflight_warnings'][0])

    def test_raw_lora_graph_rejects_partial_or_multiple_paths_without_silent_drop(self):
        body = self.body()
        graph = workflows.build(main.DraftInput.model_validate(body).model_dump())
        mutations = []
        for mode in ('extra', 'clip', 'model', 'bool_link', 'multiple', 'bool_strength'):
            bad = copy.deepcopy(graph)
            if mode == 'extra': bad['8']['inputs']['extra'] = 'lost'
            if mode == 'clip': bad['3']['inputs']['clip'] = ['1', 1]
            if mode == 'model': bad['5']['inputs']['model'] = ['1', 0]
            if mode == 'bool_link': bad['8']['inputs']['clip'] = ['1', True]
            if mode == 'multiple': bad['9'] = copy.deepcopy(bad['8'])
            if mode == 'bool_strength': bad['8']['inputs']['strength_model'] = True
            mutations.append(bad)
        with patch('backend.submissions.httpx.AsyncClient', side_effect=AssertionError('no engine')):
            for bad in mutations:
                response = self.client.post('/api/jobs', json={key: body[key] for key in ('request_id', 'engine_url', 'checkpoint')} | dict(workflow=bad))
                self.assertEqual(response.status_code, 422, response.text)
        self.assertEqual(self.client.get('/api/jobs').json(), [])
