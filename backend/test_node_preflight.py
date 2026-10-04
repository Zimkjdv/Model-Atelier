import unittest
from unittest.mock import patch
import httpx
from backend import test_api, test_submissions


class NodePreflightTests(unittest.TestCase):
    setUp = test_api.ApiTests.setUp
    tearDown = test_api.ApiTests.tearDown
    payload = test_submissions.SubmissionTests.payload
    remote = test_submissions.SubmissionTests.remote

    def test_missing_malformed_and_unavailable_nodes_never_dispatch(self):
        for data, code, expected in [({}, 200, 422), ({'VAEDecode': {}}, 200, 502), ([], 200, 502), ({}, 503, 502)]:
            remote = self.remote()
            regular = remote.get.side_effect
            def get(url):
                if url.endswith('/VAEDecode'):
                    return httpx.Response(code, request=httpx.Request('GET', url), json=data)
                return regular(url)
            remote.get.side_effect = get
            body = self.payload()
            with patch('backend.submissions.httpx.AsyncClient', return_value=remote):
                response = self.client.post('/api/generate', json=body)
            self.assertEqual(response.status_code, expected, response.text)
            remote.post.assert_not_awaited()
            job = self.client.get('/api/jobs/' + body['request_id']).json()
            self.assertEqual(job['status'], 'failed')
            if expected == 422:
                self.assertIn('VAEDecode', job['error'])
                self.assertEqual(job['failure_info']['code'], 'missing_nodes')

    def test_each_unique_node_checked_once_and_recovery_never_rechecks(self):
        remote = self.remote()
        body = self.payload()
        with patch('backend.submissions.httpx.AsyncClient', return_value=remote):
            self.assertEqual(self.client.post('/api/generate', json=body).status_code, 200)
        calls = [call.args[0] for call in remote.get.call_args_list if '/object_info/' in call.args[0]]
        self.assertEqual(sum(url.endswith('/CLIPTextEncode') for url in calls), 1)
        self.assertEqual(len(calls), 6)
        with patch('backend.submissions.httpx.AsyncClient', side_effect=AssertionError('no replay')):
            self.assertEqual(self.client.post('/api/generate', json=body).status_code, 200)
