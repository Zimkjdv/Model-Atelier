import copy
import asyncio
import io
import json
import sqlite3
import unittest
from contextlib import closing
from unittest.mock import patch
from uuid import uuid4
import httpx
from PIL import Image
from backend import gallery, jobs, main, runtime_metadata, test_api, test_submissions, test_flux_workflows


STATS = dict(system=dict(comfyui_version='0.34.0', python_version='engine-python', pytorch_version='engine-torch+cu999',
                        comfy_package_versions=[dict(name='comfy-kitchen', installed='0.2.33', required='0.2.30'),
                                                dict(name='unknown-secret-package', installed='private')]))


class RuntimeMetadataTests(unittest.TestCase):
    setUp = test_api.ApiTests.setUp
    tearDown = test_api.ApiTests.tearDown
    payload = test_submissions.SubmissionTests.payload
    remote = test_submissions.SubmissionTests.remote

    def engine(self, value=STATS, error=None, hook=None):
        remote = self.remote()
        regular = remote.get.side_effect
        def get(url):
            if url.endswith('/system_stats'):
                if hook:
                    hook()
                if error:
                    raise error
                return httpx.Response(200, json=value, request=httpx.Request('GET', url))
            return regular(url)
        remote.get.side_effect = get
        return remote

    def submit(self, body, remote):
        with patch('backend.submissions.httpx.AsyncClient', return_value=remote):
            return self.client.post('/api/generate', json=body)

    def test_snapshot_sources_workflow_hash_and_idempotence_never_refresh_versions(self):
        body, remote = self.payload(), self.engine()
        response = self.submit(body, remote)
        self.assertEqual(response.status_code, 200, response.text)
        original = response.json()
        observed = original['runtime_metadata']
        self.assertEqual(observed['engine']['comfyui'], '0.34.0')
        self.assertEqual(observed['engine']['python'], 'engine-python')
        self.assertEqual(observed['engine']['pytorch'], 'engine-torch+cu999')
        self.assertIsNone(observed['engine']['cuda'])
        self.assertEqual(observed['engine']['packages'], [dict(name='comfy-kitchen', installed='0.2.33', required='0.2.30')])
        self.assertEqual(observed['workflow']['id'], 'checkpoint-text2image-v1')
        self.assertEqual(len(observed['workflow']['sha256']), 64)
        self.assertTrue(observed['platform']['packages'])
        with patch('backend.submissions.httpx.AsyncClient', side_effect=AssertionError('no network on UUID recovery')):
            repeated = self.client.post('/api/generate', json=body).json()
        self.assertEqual(repeated['runtime_metadata'], observed)
        self.assertEqual(remote.post.await_count, 1)
        with self.assertRaises(ValueError):
            jobs.update(self.db, original['id'], runtime_metadata={})
        self.assertFalse(jobs.freeze_runtime(self.db, repeated, {})[1])

    def test_unknown_versions_http_failures_and_bad_stats_do_not_block_submission(self):
        for value, error in [(None, httpx.ConnectError('offline')), ({}, None),
                             (dict(system=dict(comfyui_version=True, pytorch_version='x'*300)), None)]:
            body, remote = self.payload(), self.engine(value, error)
            response = self.submit(body, remote)
            self.assertEqual(response.status_code, 200, response.text)
            observed = response.json()['runtime_metadata']['engine']
            self.assertIsNone(observed['comfyui'])
            self.assertIsNone(observed['pytorch'])
            self.assertIsNone(observed['cuda'])
            self.assertEqual(remote.post.await_count, 1)

    def test_engine_switch_and_concurrent_revision_after_observation_never_post(self):
        for conflict in ('engine', 'revision'):
            body = self.payload()
            def change():
                if conflict == 'engine':
                    self.client.put('/api/settings', json=dict(comfy_url='http://127.0.0.1:9999'))
                else:
                    jobs.update(self.db, body['request_id'], status='cancelled')
            remote = self.engine(hook=change)
            response = self.submit(body, remote)
            self.assertEqual(response.status_code, 409, response.text)
            remote.post.assert_not_awaited()
            stored = jobs.get(self.db, body['request_id'])
            if conflict == 'revision':
                self.assertEqual(stored['status'], 'cancelled')
                self.assertIsNone(stored['runtime_metadata'])
            self.client.put('/api/settings', json=dict(comfy_url='http://127.0.0.1:8188'))

    def test_slow_or_oversized_version_response_remains_unknown(self):
        for kind in ('timeout', 'oversized'):
            remote = self.remote()
            regular = remote.get.side_effect
            async def get(url):
                if not url.endswith('/system_stats'):
                    return regular(url)
                if kind == 'timeout':
                    await asyncio.sleep(5)
                    return httpx.Response(200, json=STATS, request=httpx.Request('GET', url))
                return httpx.Response(200, content=b'x' * (256*1024+1), request=httpx.Request('GET', url))
            remote.get.side_effect = get
            response = self.submit(self.payload(), remote)
            self.assertEqual(response.status_code, 200, response.text)
            self.assertEqual(response.json()['runtime_metadata']['engine']['status'], 'unavailable')
            remote.post.assert_awaited_once()

    def test_artwork_copies_original_snapshot_and_old_jobs_are_not_backfilled(self):
        body = self.payload()
        job = self.submit(body, self.engine()).json()
        image = io.BytesIO()
        Image.new('RGB', (8, 8), 'white').save(image, format='PNG')
        source = dict(node_id='7', filename='result.png', subfolder='', type='output')
        item, _ = gallery.save(self.db, main.DATA/'artworks', job, source, image.getvalue())
        self.assertEqual(item['runtime_metadata'], job['runtime_metadata'])
        path = '/api/artworks/' + item['id']
        with patch('backend.submissions.httpx.AsyncClient', side_effect=AssertionError('offline')):
            self.assertEqual(self.client.get(path).json()['runtime_metadata'], job['runtime_metadata'])
            self.assertEqual(self.client.get(path+'/creation-settings').json()['runtime_metadata'], job['runtime_metadata'])
        old = copy.deepcopy(job)
        old.pop('runtime_metadata')
        old.update(id=str(uuid4()), status='validating')
        with closing(sqlite3.connect(self.db)) as db, db:
            db.execute('INSERT INTO settings VALUES (?,?)', ('job:'+old['id'], json.dumps(old)))
        self.assertFalse(jobs.freeze_runtime(self.db, old, job['runtime_metadata'])[1])
        with closing(sqlite3.connect(self.db)) as db:
            raw = db.execute('SELECT value FROM settings WHERE key=?', ('job:'+old['id'],)).fetchone()[0]
        self.assertNotIn('runtime_metadata', json.loads(raw))

    def test_flux_uses_its_own_workflow_snapshot(self):
        fixture = test_flux_workflows.FluxWorkflowTests
        body, remote = fixture.body(self), fixture.remote(self)
        regular = remote.get.side_effect
        async def get(url):
            return httpx.Response(200, json=STATS, request=httpx.Request('GET', url)) if url.endswith('/system_stats') else await regular(url)
        remote.get.side_effect = get
        with patch('backend.flux_workflows.httpx.AsyncClient', return_value=remote):
            response = self.client.post('/api/flux/generate', json=body)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()['runtime_metadata']['workflow']['id'], 'flux1-schnell-text2image-v1')
        self.assertEqual(remote.post.await_count, 1)

    def test_extra_branch_does_not_claim_standard_template_version(self):
        from backend import workflows
        graph = workflows.build(main.DraftInput(title='test', engine_url='http://127.0.0.1:8188', checkpoint='test.safetensors').model_dump())
        value = dict(workflow=graph, engine_url='http://127.0.0.1:8188', checkpoint='test.safetensors')
        self.assertEqual(runtime_metadata.workflow_identity(value), 'checkpoint-text2image-v1')
        graph['99'] = dict(class_type='CLIPTextEncode', inputs=dict(text='extra', clip=['1', 1]))
        self.assertEqual(runtime_metadata.workflow_identity(value), 'checkpoint-api-workflow-v1')
