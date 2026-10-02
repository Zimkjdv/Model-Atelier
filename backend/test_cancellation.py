import copy
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import httpx

from backend import jobs, main, test_api, test_submissions, workflows


class CancellationTests(unittest.TestCase):
    setUp = test_api.ApiTests.setUp
    tearDown = test_api.ApiTests.tearDown

    def job(self, status='queued', **changes):
        values = main.DraftInput(title='取消測試', engine_url='http://127.0.0.1:8188',
                                 checkpoint='sample.safetensors', seed=str(2**64 - 1)).model_dump()
        item, _ = jobs.reserve(self.db, str(uuid4()), values['engine_url'], workflows.build(values),
                               values['checkpoint'], 'original-v1')
        # Separate request ID from remote prompt ID to catch deleting the wrong one.
        return jobs.update(self.db, item['id'], status=status, prompt_id=str(uuid4()), **changes)

    def queue(self, job=None, state='pending', others=None):
        result = dict(queue_running=[], queue_pending=[])
        if job:
            result['queue_' + state].append([0, job['prompt_id'], job['workflow'],
                                             {'model_atelier_job_id': job['id']}, ['7']])
        if others:
            result['queue_pending'].extend(others)
        return result

    def history(self, job, failed=False, complete=True):
        return {job['prompt_id']: {'status': {'completed': complete, 'status_str': 'error' if failed else 'success'},
                                  'outputs': {'7': {'images': [{'filename': 'result.png'}]}}}}

    def response(self, value, status=200):
        return httpx.Response(status, request=httpx.Request('GET', 'http://test'), json=value)

    def remote(self, *values):
        remote = AsyncMock()
        remote.__aenter__.return_value = remote
        remote.get.side_effect = [value if isinstance(value, Exception) else self.response(value) for value in values]
        remote.post.return_value = httpx.Response(200, request=httpx.Request('POST', 'http://test'))
        return remote

    def post(self, job, action='cancel'):
        return self.client.post('/api/jobs/' + job['id'] + '/' + action)

    def test_targeted_delete_pins_original_engine_and_preserves_everything(self):
        job = self.job()
        self.client.put('/api/settings', json={'comfy_url': 'http://127.0.0.1:9999'})
        unrelated_id = str(uuid4())
        unrelated = [1, unrelated_id, {}, {'model_atelier_job_id': job['id']}, []]
        remote = self.remote(self.queue(job, others=[unrelated]), self.queue(others=[unrelated]), {})
        with patch('backend.cancellation.httpx.AsyncClient', return_value=remote):
            result = self.post(job)
        self.assertEqual(result.status_code, 200, result.text)
        value = result.json()
        self.assertEqual(value['status'], 'cancelled')
        self.assertEqual(value['cancel_attempt']['phase'], 'acknowledged')
        self.assertEqual(value['cancel_attempt']['confirmation'], 'legacy_ack_then_queue_then_history')
        self.assertIn('不保證', value['error'])
        for field in ('engine_url', 'prompt_id', 'workflow', 'checkpoint', 'model_version', 'created_at'):
            self.assertEqual(value[field], job[field])
        remote.post.assert_awaited_once_with(job['engine_url'] + '/queue', json={'delete': [job['prompt_id']]})
        self.assertEqual([call.args[0] for call in remote.get.await_args_list],
                         [job['engine_url'] + '/queue', job['engine_url'] + '/queue',
                          job['engine_url'] + '/history/' + job['prompt_id']])
        with patch('backend.cancellation.httpx.AsyncClient', side_effect=AssertionError('terminal has no network')):
            self.assertEqual(self.post(job).json()['status'], 'cancelled')
            self.assertEqual(self.post(job, 'refresh').json()['status'], 'cancelled')
            submission = {'request_id': job['id'], 'engine_url': job['engine_url'],
                          'checkpoint': job['checkpoint'], 'workflow': job['workflow']}
            # Switch back for the existing submission API's engine guard.
            self.client.put('/api/settings', json={'comfy_url': job['engine_url']})
            self.assertEqual(self.client.post('/api/jobs', json=submission).json()['status'], 'cancelled')

    def test_terminal_and_unsafe_local_states_never_contact_engine(self):
        with patch('backend.cancellation.httpx.AsyncClient', side_effect=AssertionError('unexpected remote call')):
            for status in ('completed', 'failed', 'cancelled'):
                job = self.job(status)
                self.assertEqual(self.post(job).json()['status'], status)
            for status in ('running', 'unknown', 'validating', 'submitting'):
                job = self.job(status)
                self.assertEqual(self.post(job).status_code, 409)
                self.assertEqual(jobs.get(self.db, job['id'])['status'], status)
            self.assertEqual(self.client.post('/api/jobs/' + str(uuid4()) + '/cancel').status_code, 404)

    def test_live_running_snapshot_is_not_deleted(self):
        job = self.job()
        remote = self.remote(self.queue(job, 'running'), {})
        with patch('backend.cancellation.httpx.AsyncClient', return_value=remote):
            result = self.post(job)
        self.assertEqual(result.status_code, 409)
        self.assertEqual(jobs.get(self.db, job['id'])['status'], 'running')
        remote.post.assert_not_awaited()

    def test_same_metadata_wrong_id_or_wrong_workflow_does_not_authorize_delete(self):
        for mismatch in ('id', 'workflow', 'owner'):
            with self.subTest(mismatch=mismatch):
                job = self.job()
                data = self.queue(job)
                if mismatch == 'id':
                    data['queue_pending'][0][1] = str(uuid4())
                    remote = self.remote(data, {})
                else:
                    if mismatch == 'workflow':
                        data['queue_pending'][0][2] = {'other': {}}
                    else:
                        data['queue_pending'][0][3]['model_atelier_job_id'] = str(uuid4())
                    remote = self.remote(data)
                with patch('backend.cancellation.httpx.AsyncClient', return_value=remote):
                    result = self.post(job)
                self.assertIn(result.status_code, (409, 503))
                remote.post.assert_not_awaited()
                self.assertEqual(jobs.get(self.db, job['id'])['status'], 'cancel_unknown')

    def test_pending_to_running_race_never_claims_cancelled_or_interrupts(self):
        job = self.job()
        remote = self.remote(self.queue(job), self.queue(job, 'running'), {})
        with patch('backend.cancellation.httpx.AsyncClient', return_value=remote):
            result = self.post(job)
        self.assertEqual(result.status_code, 409)
        value = jobs.get(self.db, job['id'])
        self.assertEqual(value['status'], 'running')
        self.assertEqual(value['cancel_attempt']['result'], 'not_removed')
        self.assertEqual(remote.post.await_count, 1)
        self.assertTrue(remote.post.await_args.args[0].endswith('/queue'))

    def test_job_finishing_during_cancel_keeps_outputs_and_success_or_failure(self):
        for failed in (False, True):
            with self.subTest(failed=failed):
                job = self.job()
                entry = self.history(job, failed)
                remote = self.remote(self.queue(job), self.queue(), entry)
                with patch('backend.cancellation.httpx.AsyncClient', return_value=remote):
                    result = self.post(job)
                self.assertEqual(result.status_code, 200, result.text)
                self.assertEqual(result.json()['status'], 'failed' if failed else 'completed')
                self.assertEqual(result.json()['history'], entry[job['prompt_id']])

    def test_delete_acknowledgement_without_actual_removal_is_not_success(self):
        job = self.job()
        remote = self.remote(self.queue(job), self.queue(job), {})
        with patch('backend.cancellation.httpx.AsyncClient', return_value=remote):
            result = self.post(job)
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.json()['status'], 'queued')
        self.assertIn('尚未生效', result.json()['error'])

    def test_offline_timeout_malformed_and_failed_verification_are_durable(self):
        cases = [([httpx.ConnectError('offline')], 'prepared'),
                 ([self.queue(), {}], 'prepared'),
                 ([{'queue_running': [], 'queue_pending': [[0]]}], 'prepared')]
        for values, phase in cases:
            job = self.job()
            remote = self.remote(*values)
            with patch('backend.cancellation.httpx.AsyncClient', return_value=remote):
                result = self.post(job)
            self.assertIn(result.status_code, (409, 503))
            stored = jobs.get(self.db, job['id'])
            self.assertEqual(stored['status'], 'cancel_unknown')
            self.assertEqual(stored['cancel_attempt']['phase'], phase)
            remote.post.assert_not_awaited()
        job = self.job()
        remote = self.remote(self.queue(job))
        remote.post.side_effect = httpx.ReadTimeout('unknown delete result')
        with patch('backend.cancellation.httpx.AsyncClient', return_value=remote):
            self.assertEqual(self.post(job).status_code, 503)
        stored = jobs.get(self.db, job['id'])
        self.assertEqual(stored['status'], 'cancel_unknown')
        self.assertEqual(stored['cancel_attempt']['phase'], 'dispatched')
        job = self.job()
        remote = self.remote(self.queue(job), self.queue(), [])
        with patch('backend.cancellation.httpx.AsyncClient', return_value=remote):
            self.assertEqual(self.post(job).status_code, 503)
        stored = jobs.get(self.db, job['id'])
        self.assertEqual(stored['status'], 'cancel_unknown')
        self.assertEqual(stored['cancel_attempt']['phase'], 'acknowledged')
        self.assertEqual(stored['workflow'], job['workflow'])

    def test_unknown_cancel_confirmation_never_reposts_and_can_recover(self):
        for state, expected in (('pending', 'queued'), ('running', 'running'), ('absent', 'cancel_unknown'), ('done', 'completed')):
            with self.subTest(state=state):
                job = self.job('cancel_unknown', cancel_attempt={'phase': 'dispatched'})
                data = self.queue(job, state) if state in ('pending', 'running') else self.queue()
                remote = self.remote(data, self.history(job) if state == 'done' else {})
                with patch('backend.cancellation.httpx.AsyncClient', return_value=remote):
                    result = self.post(job)
                self.assertEqual(result.status_code, 200, result.text)
                self.assertEqual(result.json()['status'], expected)
                remote.post.assert_not_awaited()

    def test_acknowledged_cancel_verification_recovers_via_refresh(self):
        job = self.job('cancel_unknown', cancel_attempt={'phase': 'acknowledged'})
        remote = self.remote(self.queue(), {})
        with patch('backend.cancellation.httpx.AsyncClient', return_value=remote):
            result = self.post(job, 'refresh')
        self.assertEqual(result.json()['status'], 'cancelled')
        remote.post.assert_not_awaited()

    def test_restart_lease_has_bounded_duration_and_safe_recovery(self):
        future = (datetime.now(timezone.utc) + timedelta(seconds=30)).isoformat()
        live = self.job('cancelling', cancel_attempt={'phase': 'dispatched', 'active_until': future})
        with patch('backend.cancellation.httpx.AsyncClient', side_effect=AssertionError('live operation remains owned')):
            self.assertEqual(self.post(live).json()['status'], 'cancelling')
            self.assertEqual(self.post(live, 'refresh').json()['status'], 'cancelling')
        expired = (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat()
        for phase, result in (('dispatched', 'cancel_unknown'), ('acknowledged', 'cancelled')):
            job = self.job('cancelling', cancel_attempt={'phase': phase, 'active_until': expired})
            remote = self.remote(self.queue(), {})
            with patch('backend.cancellation.httpx.AsyncClient', return_value=remote):
                self.assertEqual(self.post(job, 'refresh').json()['status'], result)
            remote.post.assert_not_awaited()

    def test_submission_guard_expires_so_crashed_submission_can_be_reconciled(self):
        for state in ('validating', 'submitting'):
            job = self.job(state)
            with patch('backend.cancellation.httpx.AsyncClient', side_effect=AssertionError('live submit should retain ownership')):
                self.assertEqual(self.post(job, 'refresh').json()['status'], state)
            remote = self.remote({}, self.queue(job))
            future = datetime.now(timezone.utc) + timedelta(seconds=61)
            with patch('backend.submissions.datetime') as clock, patch('backend.cancellation.httpx.AsyncClient', return_value=remote):
                clock.fromisoformat.side_effect = datetime.fromisoformat
                clock.now.return_value = future
                result = self.post(job, 'refresh')
            self.assertEqual(result.status_code, 200, result.text)
            self.assertEqual(result.json()['status'], 'queued')
            self.assertEqual(result.json()['prompt_id'], job['prompt_id'])
            remote.post.assert_not_awaited()

    def test_atomic_revision_prevents_stale_refresh_from_overwriting_cancellation(self):
        job = self.job()
        remote = self.remote()

        async def observe(url):
            jobs.update(self.db, job['id'], status='cancelled', cancel_attempt={'phase': 'acknowledged'})
            return self.response(self.history(job))

        remote.get.side_effect = observe
        with patch('backend.cancellation.httpx.AsyncClient', return_value=remote):
            self.assertEqual(self.post(job, 'refresh').status_code, 409)
        stored = jobs.get(self.db, job['id'])
        self.assertEqual(stored['status'], 'cancelled')
        self.assertEqual(stored['workflow'], job['workflow'])

    def test_metadata_only_refresh_cannot_reassign_identity_for_cancellation(self):
        job = self.job('unknown')
        foreign = self.queue(job)
        foreign_id = str(uuid4())
        foreign['queue_pending'][0][1] = foreign_id
        remote = self.remote({}, foreign)
        with patch('backend.cancellation.httpx.AsyncClient', return_value=remote):
            result = self.post(job, 'refresh')
            self.assertEqual(result.status_code, 200, result.text)
            self.assertEqual(result.json()['status'], 'unknown')
            self.assertEqual(result.json()['prompt_id'], job['prompt_id'])
            self.assertEqual(self.post(job).status_code, 409)
        remote.post.assert_not_awaited()

    def test_late_submission_result_cannot_overwrite_newer_terminal_state(self):
        for timeout in (False, True):
            with self.subTest(timeout=timeout):
                values = main.DraftInput(title='race', engine_url='http://127.0.0.1:8188', checkpoint='sample.safetensors').model_dump(mode='json')
                job_id = str(uuid4())
                values['request_id'] = job_id
                remote = self.remote({'CheckpointLoaderSimple': {'input': {'required': {'ckpt_name': [['sample.safetensors']]}}}},
                                     test_submissions.sampler_capabilities())

                async def submitted(url, **kwargs):
                    # Represents another worker reconciling the accepted upstream
                    # prompt while this worker still awaits its HTTP acknowledgement.
                    jobs.update(self.db, job_id, status='cancelled', cancel_attempt={'phase': 'acknowledged'})
                    if timeout:
                        raise httpx.ReadTimeout('response lost after newer result')
                    return self.response({'prompt_id': job_id})

                remote.post.side_effect = submitted
                with patch('backend.cancellation.httpx.AsyncClient', return_value=remote):
                    result = self.client.post('/api/generate', json=values)
                self.assertEqual(result.status_code, 200, result.text)
                self.assertEqual(result.json()['status'], 'cancelled')
                self.assertEqual(jobs.get(self.db, job_id)['status'], 'cancelled')

    def test_atomic_revision_prevents_delete_when_another_worker_changed_the_job(self):
        job = self.job()
        remote = self.remote()

        async def observe(url):
            jobs.update(self.db, job['id'], status='running')
            return self.response(self.queue(job))

        remote.get.side_effect = observe
        with patch('backend.cancellation.httpx.AsyncClient', return_value=remote):
            self.assertEqual(self.post(job).status_code, 409)
        self.assertEqual(jobs.get(self.db, job['id'])['status'], 'running')
        remote.post.assert_not_awaited()

    def test_duplicate_and_malformed_history_do_not_claim_success(self):
        job = self.job()
        duplicate = self.queue(job)
        duplicate['queue_running'] = copy.deepcopy(duplicate['queue_pending'])
        remote = self.remote(duplicate)
        with patch('backend.cancellation.httpx.AsyncClient', return_value=remote):
            self.assertEqual(self.post(job).status_code, 503)
        remote.post.assert_not_awaited()
        for entry in ({}, {'status': None}, {'status': {'completed': 'true', 'status_str': 'success'}}):
            job = self.job('cancel_unknown', cancel_attempt={'phase': 'acknowledged'})
            remote = self.remote(self.queue(), {job['prompt_id']: entry})
            with patch('backend.cancellation.httpx.AsyncClient', return_value=remote):
                self.assertEqual(self.post(job, 'refresh').status_code, 503)
            self.assertEqual(jobs.get(self.db, job['id'])['status'], 'cancel_unknown')
            remote.post.assert_not_awaited()
