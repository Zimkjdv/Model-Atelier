import json
from uuid import uuid4
from unittest.mock import AsyncMock, patch
import httpx
from backend import test_api
import unittest
from backend import main


class SubmissionTests(unittest.TestCase):
    setUp = test_api.ApiTests.setUp
    tearDown = test_api.ApiTests.tearDown
    def payload(self):
        return dict(request_id=str(uuid4()), engine_url='http://127.0.0.1:8188', checkpoint='test.safetensors', title='test', prompt='a mountain', width=512, height=512, seed='18446744073709551615')

    def remote(self, names=None):
        remote = AsyncMock()
        remote.__aenter__.return_value = remote
        remote.get.return_value = httpx.Response(200, request=httpx.Request('GET', 'http://test'), json={'CheckpointLoaderSimple': {'input': {'required': {'ckpt_name': [names if names is not None else ['test.safetensors']]}}}})
        remote.post.return_value = httpx.Response(200, request=httpx.Request('POST', 'http://test'), json={'prompt_id': str(uuid4()), 'number': 0, 'node_errors': {}})
        return remote

    def test_submit_idempotence_and_workflow_precision(self):
        body = self.payload()
        remote = self.remote()
        with patch('backend.submissions.httpx.AsyncClient', return_value=remote):
            result = self.client.post('/api/generate', json=body)
            self.assertEqual(result.status_code, 200, result.text)
            job = result.json()
            self.assertEqual(job['status'], 'queued')
            self.assertEqual(self.client.post('/api/generate', json=body).json()['id'], job['id'])
            self.assertEqual(remote.post.await_count, 1)
            body['prompt'] = 'changed'
            self.assertEqual(self.client.post('/api/generate', json=body).status_code, 409)
        workflow = self.client.get('/api/jobs/' + job['id'] + '/workflow')
        self.assertEqual(json.loads(workflow.text)['5']['inputs']['seed'], 2**64-1)
        self.assertEqual(job['workflow'], remote.post.call_args.kwargs['json']['prompt'])
        self.assertEqual(len(self.client.get('/api/jobs').json()), 1)

    def test_missing_checkpoint_and_offline_never_submit(self):
        for names, offline, status in [([], False, 409), (['other'], False, 409), ([], True, 503)]:
            remote = self.remote(names)
            if offline:
                remote.get.side_effect = httpx.ConnectError('offline')
            with patch('backend.submissions.httpx.AsyncClient', return_value=remote):
                response = self.client.post('/api/generate', json=self.payload())
            self.assertEqual(response.status_code, status)
            remote.post.assert_not_called()
            self.assertEqual(self.client.get('/api/jobs/' + response.json()['detail']['job_id']).json()['status'], 'failed')

    def test_unknown_submission_is_not_retried(self):
        body = self.payload()
        remote = self.remote()
        remote.post.side_effect = httpx.ReadTimeout('uncertain')
        with patch('backend.submissions.httpx.AsyncClient', return_value=remote):
            self.assertEqual(self.client.post('/api/generate', json=body).json()['status'], 'unknown')
            self.assertEqual(self.client.post('/api/generate', json=body).json()['status'], 'unknown')
        self.assertEqual(remote.post.await_count, 1)

    def test_rejection_and_unsupported_reference(self):
        remote = self.remote()
        remote.post.return_value = httpx.Response(400, request=httpx.Request('POST', 'http://test'), json={'error': 'invalid', 'node_errors': {'1': 'bad'}})
        with patch('backend.submissions.httpx.AsyncClient', return_value=remote):
            response = self.client.post('/api/generate', json=self.payload())
        self.assertEqual(response.status_code, 422)
        job = self.client.get('/api/jobs/' + response.json()['detail']['job_id']).json()
        self.assertIn('node_errors', job['upstream_error'])
        self.assertEqual(self.client.post('/api/generate', json={**self.payload(), 'reference_ids': [str(uuid4())]}).status_code, 422)
        self.assertEqual(self.client.post('/api/jobs', json={**self.payload(), 'workflow': {'1': {'class_type': 'CustomCode', 'inputs': {}}}}).status_code, 422)

    def test_queue_history_and_pinned_engine(self):
        remote = self.remote()
        with patch('backend.submissions.httpx.AsyncClient', return_value=remote):
            job = self.client.post('/api/generate', json=self.payload()).json()
            self.client.put('/api/settings', json={'comfy_url': 'http://127.0.0.1:9999'})
            def response(data):
                return httpx.Response(200, request=httpx.Request('GET', 'http://test'), json=data)
            remote.get.side_effect = [response({}), response({'queue_running': [[0, job['prompt_id'], {}, {}]], 'queue_pending': []})]
            path = '/api/jobs/' + job['id'] + '/refresh'
            self.assertEqual(self.client.post(path).json()['status'], 'running')
            self.assertTrue(remote.get.call_args.args[0].startswith(job['engine_url']))
            remote.get.side_effect = httpx.ConnectError('offline')
            self.assertEqual(self.client.post(path).status_code, 503)
            self.assertEqual(self.client.get('/api/jobs/' + job['id']).json()['status'], 'running')
            entry = {'status': {'completed': True, 'status_str': 'success'}, 'outputs': {'7': {'images': [{'filename': 'result.png'}]}}}
            remote.get.side_effect = [response({job['prompt_id']: entry})]
            finished = self.client.post(path).json()
            self.assertEqual(finished['status'], 'completed')
            self.assertEqual(finished['history'], entry)

    def test_missing_job_and_malformed_engine(self):
        self.assertEqual(self.client.get('/api/jobs/' + str(uuid4())).status_code, 404)
        remote = self.remote()
        remote.get.return_value = httpx.Response(200, request=httpx.Request('GET', 'http://test'), json={})
        with patch('backend.submissions.httpx.AsyncClient', return_value=remote):
            self.assertEqual(self.client.post('/api/generate', json=self.payload()).status_code, 502)
        remote.post.assert_not_called()
