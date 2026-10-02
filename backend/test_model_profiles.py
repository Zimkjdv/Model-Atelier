import copy
import json
import sqlite3
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

from backend import catalog, jobs, main, model_profiles, test_api, test_submissions, test_model_metadata, workflows

ENGINE = test_model_metadata.ENGINE
CHECKPOINT = test_model_metadata.CHECKPOINT


class ModelProfileTests(unittest.TestCase):
    setUp = test_api.ApiTests.setUp
    tearDown = test_api.ApiTests.tearDown
    sync = test_api.ApiTests.sync
    target = test_model_metadata.ModelMetadataTests.target
    register = test_model_metadata.ModelMetadataTests.register
    body = test_model_metadata.ModelMetadataTests.body
    remote = test_submissions.SubmissionTests.remote

    def get_profile(self, name=CHECKPOINT, engine=ENGINE):
        return self.client.get('/api/models/profile', params=dict(engine_url=engine, name=name))

    def saved_rows(self):
        with closing(sqlite3.connect(self.db)) as db:
            return db.execute('SELECT key, value FROM settings ORDER BY key').fetchall()

    def test_profiles_are_read_only_and_do_not_probe_comfy_or_gpu(self):
        self.sync([CHECKPOINT])
        registered = self.register(architecture='sdxl')
        before = self.saved_rows()
        with (patch('backend.main.httpx.AsyncClient', side_effect=AssertionError('must not probe engine')),
              patch.object(main, 'gpu_info', side_effect=AssertionError('must not inspect GPU'))):
            response = self.get_profile()
        self.assertEqual(response.status_code, 200, response.text)
        result = response.json()
        self.assertEqual(set(result), {'engine_url', 'name', 'architecture', 'metadata_updated_at', 'compatibility', 'preset'})
        self.assertEqual(result['metadata_updated_at'], registered['metadata_updated_at'])
        self.assertEqual(result['compatibility']['status'], 'supported')
        self.assertTrue(result['compatibility']['allows_submission'])
        self.assertIn('使用者登記', result['compatibility']['message'])
        self.assertIn('未讀取或驗證', result['compatibility']['message'])
        self.assertEqual(self.saved_rows(), before)

    def test_generic_supported_presets_are_explicitly_unverified_and_do_not_mutate_catalog(self):
        self.sync([CHECKPOINT])
        for kind, pixels in [('sd1', 512), ('sdxl', 768)]:
            with self.subTest(kind=kind):
                self.register(architecture=kind)
                preset = self.get_profile().json()['preset']
                self.assertEqual(preset['id'], kind + '-starter')
                self.assertEqual(preset['settings'], dict(width=pixels, height=pixels, steps=20, cfg=7.0,
                                                         sampler_name='euler', scheduler='normal', denoise=1.0))
                self.assertIn('實測', preset['validation'])
                self.assertEqual(preset['prompt_hint'], '')
                self.assertEqual(preset['reference'], '')
                self.assertNotIn('seed', preset['settings'])
                self.assertNotIn('prompt', preset['settings'])

    def test_pony_preset_requires_declared_sdxl_and_exact_official_manifest_checksum(self):
        manifest = json.loads((Path(__file__).resolve().parents[1] / 'models' / 'pony-v6-xl.json').read_text(encoding='utf-8'))
        self.assertEqual(model_profiles.PONY_SHA256, manifest['sha256'])
        self.sync([CHECKPOINT])
        self.register(architecture='sdxl', sha256=manifest['sha256'], version='not guessed')
        result = self.get_profile().json()
        preset = result['preset']
        self.assertEqual(preset['id'], 'pony-v6-xl-rtx3060-landscape')
        self.assertEqual(preset['settings'], dict(width=768, height=768, steps=20, cfg=5.5,
                                                sampler_name='dpmpp_2m', scheduler='karras', denoise=1.0))
        self.assertEqual(preset['reference'], 'docs/validation/pony-v6-xl-rtx3060.md')
        self.assertIn('單張風景', preset['validation'])
        self.assertIn('未驗證目前檔案', preset['description'])
        self.assertEqual(preset['prompt_hint'], model_profiles.PONY_PROMPT_HINT)
        self.register(architecture='unknown')
        self.assertIsNone(self.get_profile().json()['preset'])
        self.register(architecture='sd1')
        self.assertEqual(self.get_profile().json()['preset']['id'], 'sd1-starter')
        self.register(architecture='sdxl', sha256='a' * 64)
        self.assertEqual(self.get_profile().json()['preset']['id'], 'sdxl-starter')

    def test_names_versions_and_unknown_legacy_architecture_do_not_infer_a_preset(self):
        guessed_name = 'pony-v6-xl-flux-sdxl.safetensors'
        self.sync([guessed_name])
        self.client.put('/api/models/metadata', json=self.target(name=guessed_name, version='Pony V6 XL'))
        for value in (None, 'SDXL', 'invalid', True, ['sdxl']):
            entry = catalog.read(self.db, ENGINE)
            entry['models'][0]['architecture'] = value
            entry['models'][0]['sha256'] = model_profiles.PONY_SHA256
            catalog.write(self.db, entry)
            result = self.get_profile(guessed_name).json()
            self.assertEqual(result['architecture'], 'unknown')
            self.assertEqual(result['compatibility']['status'], 'unknown')
            self.assertTrue(result['compatibility']['allows_submission'])
            self.assertIsNone(result['preset'])

    def test_profile_engine_scope_and_unknown_model_guards(self):
        self.sync([CHECKPOINT])
        self.register(architecture='sdxl', sha256=model_profiles.PONY_SHA256)
        self.assertEqual(self.get_profile('missing').status_code, 404)
        other = 'http://127.0.0.1:9000'
        self.client.put('/api/settings', json={'comfy_url': other})
        self.assertEqual(self.get_profile().status_code, 409)
        self.sync([CHECKPOINT])
        self.client.put('/api/models/metadata', json=self.target(engine_url=other, architecture='flux'))
        result = self.get_profile(engine=other).json()
        self.assertEqual(result['architecture'], 'flux')
        self.assertEqual(result['compatibility']['status'], 'unsupported')
        self.assertFalse(result['compatibility']['allows_submission'])
        self.assertIsNone(result['preset'])
        self.client.put('/api/settings', json={'comfy_url': ENGINE})
        self.assertEqual(self.get_profile().json()['preset']['id'], 'pony-v6-xl-rtx3060-landscape')

    def test_known_unsupported_architectures_block_both_submission_apis_and_preserve_failed_job(self):
        self.sync([CHECKPOINT])
        for kind in ('flux', 'sd3', 'other'):
            self.register(architecture=kind)
            for endpoint in ('/api/generate', '/api/jobs'):
                with self.subTest(architecture=kind, endpoint=endpoint):
                    body = self.body()
                    if endpoint == '/api/jobs':
                        body = {key: body[key] for key in ('request_id', 'engine_url', 'checkpoint')} | {'workflow': workflows.build(self.body())}
                    with patch('backend.submissions.httpx.AsyncClient', side_effect=AssertionError('must not contact engine')):
                        response = self.client.post(endpoint, json=body)
                    self.assertEqual(response.status_code, 422, response.text)
                    job = self.client.get('/api/jobs/' + response.json()['detail']['job_id']).json()
                    self.assertEqual(job['id'], body['request_id'])
                    self.assertEqual(job['status'], 'failed')
                    self.assertEqual(job['model_metadata']['architecture'], kind)
                    self.assertIn('專用工作流程', job['error'])
                    if endpoint == '/api/jobs':
                        self.assertEqual(job['workflow'], body['workflow'])

    def test_supported_and_unknown_generation_keep_explicit_nondefault_parameters_without_gpu_gating(self):
        self.sync([CHECKPOINT])
        for kind in ('sd1', 'sdxl', 'unknown'):
            self.register(architecture=kind, sha256=model_profiles.PONY_SHA256)
            body = self.body() | dict(width=640, height=768, steps=37, cfg=4.125,
                                      sampler_name='dpmpp_2m', scheduler='karras', denoise=0.42,
                                      seed='18446744073709551615')
            remote = self.remote()
            with (patch('backend.submissions.httpx.AsyncClient', return_value=remote),
                  patch.object(main, 'gpu_info', side_effect=AssertionError('must not gate by GPU'))):
                response = self.client.post('/api/generate', json=body)
            self.assertEqual(response.status_code, 200, response.text)
            self.assertEqual(response.json()['status'], 'queued')
            submitted = remote.post.call_args.kwargs['json']['prompt']
            self.assertEqual(submitted, workflows.build(body))
            self.assertEqual(submitted['5']['inputs']['seed'], 2**64 - 1)
            self.assertEqual(submitted['5']['inputs']['cfg'], 4.125)
            self.assertEqual(remote.post.await_count, 1)

    def test_architecture_changed_to_unsupported_during_capability_fetch_blocks_without_recapturing(self):
        self.sync([CHECKPOINT])
        self.register(architecture='sdxl', version='original')
        body = self.body()
        for endpoint in ('/api/generate', '/api/jobs'):
            self.register(architecture='sdxl', version='original')
            body = body | {'request_id': str(uuid4())}
            payload = body if endpoint == '/api/generate' else {
                key: body[key] for key in ('request_id', 'engine_url', 'checkpoint')} | {'workflow': workflows.build(body)}
            remote = self.remote()
            original_get = remote.get.side_effect
            def response(url):
                result = original_get(url)
                if url.endswith('/object_info/KSampler'):
                    catalog.update_metadata(self.db, ENGINE, CHECKPOINT, dict(architecture='flux', version='changed'))
                return result
            remote.get.side_effect = response
            with patch('backend.submissions.httpx.AsyncClient', return_value=remote):
                result = self.client.post(endpoint, json=payload)
            self.assertEqual(result.status_code, 422, result.text)
            remote.post.assert_not_called()
            job = jobs.get(self.db, body['request_id'])
            self.assertEqual(job['status'], 'failed')
            self.assertEqual(job['model_metadata']['architecture'], 'sdxl')
            self.assertEqual(job['model_metadata']['version'], 'original')
            self.assertIn('驗證期間', job['error'])

    def test_existing_request_recovery_ignores_later_unsupported_registration_and_never_probes(self):
        self.sync([CHECKPOINT])
        self.register(architecture='sdxl')
        body = self.body()
        remote = self.remote()
        with patch('backend.submissions.httpx.AsyncClient', return_value=remote):
            submitted = self.client.post('/api/generate', json=body).json()
        self.register(architecture='flux')
        self.client.put('/api/settings', json={'comfy_url': 'http://127.0.0.1:9000'})
        with (patch('backend.submissions.catalog.read', side_effect=AssertionError('must not recheck metadata')),
              patch('backend.submissions.httpx.AsyncClient', side_effect=AssertionError('must not contact engine'))):
            for endpoint, payload in [('/api/generate', body), ('/api/jobs', {
                    key: body[key] for key in ('request_id', 'engine_url', 'checkpoint')} | {'workflow': submitted['workflow']})]:
                result = self.client.post(endpoint, json=payload)
                self.assertEqual(result.status_code, 200, result.text)
                self.assertEqual(result.json(), submitted)
        self.assertEqual(remote.post.await_count, 1)

    def test_allowed_architecture_updates_during_validation_keep_original_snapshot_and_all_parameters(self):
        self.sync([CHECKPOINT])
        for initial, final in [('unknown', 'sdxl'), ('sdxl', 'unknown'), ('sd1', 'sdxl'), ('sdxl', 'sd1')]:
            for endpoint in ('/api/generate', '/api/jobs'):
                with self.subTest(initial=initial, final=final, endpoint=endpoint):
                    model = self.register(architecture=initial, version='original')
                    body = self.body() | dict(width=640, height=768, steps=37, cfg=3.875,
                                              sampler_name='dpmpp_2m', scheduler='karras', denoise=0.42)
                    graph = workflows.build(body)
                    payload = body if endpoint == '/api/generate' else {
                        key: body[key] for key in ('request_id', 'engine_url', 'checkpoint')} | {'workflow': graph}
                    remote = self.remote()
                    original_get = remote.get.side_effect
                    def response(url):
                        result = original_get(url)
                        if url.endswith('/object_info/KSampler'):
                            catalog.update_metadata(self.db, ENGINE, CHECKPOINT, dict(architecture=final, version='updated'))
                        return result
                    remote.get.side_effect = response
                    with patch('backend.submissions.httpx.AsyncClient', return_value=remote):
                        result = self.client.post(endpoint, json=payload)
                    self.assertEqual(result.status_code, 200, result.text)
                    job = result.json()
                    self.assertEqual(job['status'], 'queued')
                    self.assertEqual(job['model_metadata']['architecture'], initial)
                    self.assertEqual(job['model_metadata']['version'], 'original')
                    self.assertEqual(job['model_metadata']['metadata_updated_at'], model['metadata_updated_at'])
                    self.assertEqual(job['workflow'], graph)
                    self.assertEqual(remote.post.call_args.kwargs['json']['prompt'], graph)
                    self.assertEqual(graph['5']['inputs']['seed'], 9007199254740993)
                    self.assertEqual(remote.post.await_count, 1)

    def test_profile_response_objects_do_not_share_mutable_settings(self):
        model = dict(name=CHECKPOINT, architecture='sdxl', sha256=model_profiles.PONY_SHA256)
        first = model_profiles.profile(ENGINE, model)
        original = copy.deepcopy(first)
        first['preset']['settings']['cfg'] = 99
        first['compatibility']['allows_submission'] = False
        self.assertEqual(model_profiles.profile(ENGINE, model), original)
