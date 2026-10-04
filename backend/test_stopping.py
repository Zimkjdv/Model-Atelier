import hashlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import httpx
from backend import jobs, stopping
from backend import test_cancellation
from scripts import comfy_stop_capability as verifier


class StoppingTests(unittest.TestCase):
    setUp = test_cancellation.CancellationTests.setUp
    tearDown = test_cancellation.CancellationTests.tearDown
    job = test_cancellation.CancellationTests.job
    queue = test_cancellation.CancellationTests.queue
    history = test_cancellation.CancellationTests.history
    response = test_cancellation.CancellationTests.response
    remote = test_cancellation.CancellationTests.remote

    def post(self, job, action='stop'):
        return self.client.post('/api/jobs/' + job['id'] + '/' + action)

    def interrupted(self, job):
        entry = self.history(job, failed=True)
        entry[job['prompt_id']]['prompt'] = [0, job['prompt_id'], job['workflow'], {'model_atelier_job_id': job['id']}]
        entry[job['prompt_id']]['status']['messages'] = [['execution_interrupted', {
            'prompt_id': job['prompt_id'], 'node_id': '5', 'node_type': 'KSampler'}]]
        return entry

    def supported_remote(self, job, outcome=None):
        remote = self.remote({verifier.FEATURE: verifier.SOURCE_COMMIT}, self.queue(job, 'running'), self.queue(), outcome or {})
        remote.post.return_value = self.response({'cancelled': True})
        return remote

    def test_only_exact_owned_running_prompt_on_original_engine_is_stopped(self):
        job = self.job('running')
        self.client.put('/api/settings', json={'comfy_url': 'http://other-engine:9000'})
        remote = self.supported_remote(job, self.interrupted(job))
        with patch('backend.stopping.httpx.AsyncClient', return_value=remote):
            result = self.post(job)
        self.assertEqual(result.status_code, 200, result.text)
        self.assertEqual(result.json()['status'], 'stopped')
        remote.post.assert_awaited_once_with(job['engine_url'] + '/api/jobs/' + job['prompt_id'] + '/cancel')
        for field in ('workflow', 'prompt_id', 'engine_url', 'model_metadata', 'lora_metadata', 'created_at'):
            self.assertEqual(result.json()[field], job[field])
        self.assertEqual(result.json()['history'], self.interrupted(job)[job['prompt_id']])
        with patch('backend.stopping.httpx.AsyncClient', side_effect=AssertionError('no network')):
            self.assertEqual(self.post(job).json()['status'], 'stopped')
            self.assertEqual(self.post(job, 'refresh').json()['status'], 'stopped')

    def test_missing_or_false_capability_does_not_mutate_or_interrupt(self):
        for value in ({}, {verifier.FEATURE: False}, {verifier.FEATURE: 'true'}, [], {verifier.FEATURE: 1}):
            job = self.job('running')
            remote = self.remote(value)
            with patch('backend.stopping.httpx.AsyncClient', return_value=remote):
                self.assertEqual(self.post(job).status_code, 409)
            remote.post.assert_not_awaited()
            self.assertEqual(jobs.get(self.db, job['id'])['revision'], job['revision'])

    def test_unsafe_states_and_terminal_are_not_probed(self):
        with patch('backend.stopping.httpx.AsyncClient', side_effect=AssertionError('no network')):
            for status in ('queued', 'validating', 'submitting', 'unknown', 'cancelling', 'cancel_unknown'):
                self.assertEqual(self.post(self.job(status)).status_code, 409)
            for status in ('completed', 'failed', 'cancelled', 'stopped'):
                self.assertEqual(self.post(self.job(status)).json()['status'], status)

    def test_fresh_state_or_ownership_mismatch_never_sends_stop(self):
        for mutation in ('queued', 'absent', 'owner', 'workflow'):
            job = self.job('running')
            queue = self.queue(job, 'pending' if mutation == 'queued' else 'running')
            if mutation == 'absent':
                queue = self.queue()
            if mutation == 'owner':
                queue['queue_running'][0][3]['model_atelier_job_id'] = 'other'
            if mutation == 'workflow':
                queue['queue_running'][0][2] = {}
            remote = self.remote({verifier.FEATURE: verifier.SOURCE_COMMIT}, queue, {})
            with patch('backend.stopping.httpx.AsyncClient', return_value=remote):
                self.assertIn(self.post(job).status_code, (409, 503))
            remote.post.assert_not_awaited()
            self.assertEqual(jobs.get(self.db, job['id'])['status'], 'stop_unknown')

    def test_ack_or_absence_is_not_a_stopped_verdict(self):
        for receipt in (True, False):
            job = self.job('running')
            remote = self.supported_remote(job)
            remote.post.return_value = self.response({'cancelled': receipt})
            with patch('backend.stopping.httpx.AsyncClient', return_value=remote):
                result = self.post(job)
            self.assertEqual(result.json()['status'], 'stop_unknown')
            refresh_remote = self.remote(self.queue(), {})
            with patch('backend.stopping.httpx.AsyncClient', return_value=refresh_remote):
                self.assertEqual(self.post(job).json()['status'], 'stop_unknown')
            refresh_remote.post.assert_not_awaited()

    def test_finish_or_failure_during_stop_preserves_real_outcome(self):
        for failed in (False, True):
            job = self.job('running')
            history = self.history(job, failed=failed)
            remote = self.supported_remote(job, history)
            with patch('backend.stopping.httpx.AsyncClient', return_value=remote):
                result = self.post(job)
            self.assertEqual(result.json()['status'], 'failed' if failed else 'completed')
            self.assertEqual(result.json()['history'], history[job['prompt_id']])

    def test_wrong_interruption_id_or_node_is_not_trusted(self):
        for field, value in (('prompt_id', 'other'), ('node_id', 'missing'), ('node_type', 'SaveImage')):
            job = self.job('running')
            history = self.interrupted(job)
            history[job['prompt_id']]['status']['messages'][0][1][field] = value
            remote = self.supported_remote(job, history)
            with patch('backend.stopping.httpx.AsyncClient', return_value=remote):
                self.assertEqual(self.post(job).json()['status'], 'failed')

    def test_lost_stop_response_is_not_replayed_and_later_history_confirms(self):
        job = self.job('running')
        remote = self.supported_remote(job)
        remote.post.side_effect = httpx.ReadTimeout('lost')
        with patch('backend.stopping.httpx.AsyncClient', return_value=remote):
            self.assertEqual(self.post(job).status_code, 503)
        stored = jobs.get(self.db, job['id'])
        self.assertEqual(stored['stop_attempt']['phase'], 'dispatched')
        followup = self.remote(self.queue(), self.interrupted(job))
        with patch('backend.stopping.httpx.AsyncClient', return_value=followup):
            self.assertEqual(self.post(job, 'refresh').json()['status'], 'stopped')
        followup.post.assert_not_awaited()

    def test_invalid_receipt_and_capability_offline_are_safe(self):
        job = self.job('running')
        remote = self.supported_remote(job)
        remote.post.return_value = self.response({'cancelled': 'yes'})
        with patch('backend.stopping.httpx.AsyncClient', return_value=remote):
            self.assertEqual(self.post(job).status_code, 503)
        job = self.job('running')
        remote = self.remote(httpx.ConnectError('offline'))
        with patch('backend.stopping.httpx.AsyncClient', return_value=remote):
            self.assertEqual(self.post(job).status_code, 503)
        self.assertEqual(jobs.get(self.db, job['id'])['status'], 'running')
        remote.post.assert_not_awaited()

    def test_stale_stop_update_cannot_overwrite_a_newer_result(self):
        job = self.job('running')
        remote = self.supported_remote(job)
        async def response(*args, **kwargs):
            jobs.update(self.db, job['id'], status='completed', error=None)
            return self.response({'cancelled': True})
        remote.post.side_effect = response
        with patch('backend.stopping.httpx.AsyncClient', return_value=remote):
            self.assertEqual(self.post(job).status_code, 409)
        self.assertEqual(jobs.get(self.db, job['id'])['status'], 'completed')


class StopSourceTests(unittest.TestCase):
    def test_missing_modified_and_newline_normalized_sources(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            digest = hashlib.sha256(b'a\nb\n').hexdigest()
            with patch.dict(verifier.HASHES, {'one.py': digest}, clear=True):
                self.assertFalse(verifier.verify(root)['supported'])
                (root / 'one.py').write_bytes(b'a\r\nb\r\n')
                self.assertTrue(verifier.verify(root)['supported'])
                (root / 'one.py').write_bytes(b'unsafe')
                self.assertFalse(verifier.verify(root)['supported'])
