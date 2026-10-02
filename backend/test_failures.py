import copy
import json
import sqlite3
import unittest
from contextlib import closing
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import httpx

from backend import catalog, failures, jobs, main, progress, test_api, test_submissions, workflows


class FailureTests(unittest.TestCase):
    setUp = test_api.ApiTests.setUp
    tearDown = test_api.ApiTests.tearDown
    remote = test_submissions.SubmissionTests.remote

    def settings(self):
        return main.DraftInput(title='failure test', engine_url='http://127.0.0.1:8188', checkpoint='test.safetensors',
                               prompt='PRIVATE_PROMPT', negative_prompt='PRIVATE_NEGATIVE', width=640, height=768,
                               seed=str(2**64 - 1), steps=37, cfg=4.125, sampler_name='dpmpp_2m', scheduler='karras',
                               denoise=0.42).model_dump(mode='json', exclude={'revision'})

    def job(self, status='queued', node_ids=None):
        settings = self.settings()
        model = dict(name=settings['checkpoint'], version='original-v1', architecture='sdxl', sha256='a' * 64)
        metadata = catalog.capture(model, settings['checkpoint'])
        job, _ = jobs.reserve(self.db, str(uuid4()), settings['engine_url'], workflows.build(settings, node_ids),
                              settings['checkpoint'], 'original-v1', metadata)
        return jobs.update(self.db, job['id'], status=status, prompt_id=str(uuid4()))

    def entry(self, job, node='5', kind='KSampler', exception='torch.OutOfMemoryError', message='PRIVATE_PROMPT traceback PRIVATE_TRACE', **changes):
        data = dict(prompt_id=job['prompt_id'], node_id=node, node_type=kind, exception_type=exception,
                    exception_message=message, traceback=['PRIVATE_TRACE'], current_inputs={'text': 'PRIVATE_PROMPT'}) | changes
        return dict(status=dict(completed=False, status_str='error', messages=[['execution_error', data]]), outputs={})

    def response(self, payload, status=200):
        return httpx.Response(status, request=httpx.Request('GET', 'http://test'), json=payload)

    def historical_remote(self, *payloads):
        remote = AsyncMock()
        remote.__aenter__.return_value = remote
        remote.get.side_effect = [self.response(payload) for payload in payloads]
        return remote

    def post(self, job, action='refresh'):
        return self.client.post('/api/jobs/' + job['id'] + '/' + action)

    def rows(self):
        with closing(sqlite3.connect(self.db)) as db:
            return db.execute('SELECT key, value FROM settings ORDER BY key').fetchall()

    def assert_safe(self, diagnostic):
        self.assertEqual(set(diagnostic), {'code', 'title', 'message', 'suggestions', 'node_id', 'node_type', 'exception_type'})
        self.assertLessEqual(len(diagnostic['title']), 80)
        self.assertLessEqual(len(diagnostic['message']), 400)
        self.assertLessEqual(len(diagnostic['suggestions']), 3)
        self.assertTrue(all(len(value) <= 240 for value in diagnostic['suggestions']))
        text = json.dumps(diagnostic)
        self.assertNotIn('PRIVATE_', text)
        self.assertNotIn('traceback', text)
        self.assertNotIn('current_inputs', text)

    def test_confirmed_history_classifies_cuda_oom_loader_and_generic_without_leaking_raw_data(self):
        cases = [('5', 'KSampler', 'torch.OutOfMemoryError', 'PRIVATE_PROMPT', 'cuda_oom'),
                 ('5', 'KSampler', 'torch._C.OutOfMemoryError', 'PRIVATE_PROMPT', 'cuda_oom'),
                 ('5', 'KSampler', 'RuntimeError', 'CUDA out of memory. PRIVATE_PROMPT', 'cuda_oom'),
                 ('1', 'CheckpointLoaderSimple', 'FileNotFoundError', 'PRIVATE_PATH', 'model_load_failed'),
                 ('1', 'CheckpointLoaderSimple', 'ValueError', 'PRIVATE_WEIGHTS', 'model_load_failed'),
                 ('6', 'VAEDecode', 'RuntimeError', 'PRIVATE_PROMPT', 'execution_failed')]
        for node, kind, exception, message, code in cases:
            with self.subTest(code=code, exception=exception):
                job = self.job()
                entry = self.entry(job, node, kind, exception, message)
                remote = self.historical_remote({job['prompt_id']: entry})
                with patch('backend.submissions.httpx.AsyncClient', return_value=remote):
                    result = self.post(job)
                self.assertEqual(result.status_code, 200, result.text)
                value = result.json()
                self.assertEqual(value['status'], 'failed')
                self.assertEqual(value['failure_info']['code'], code)
                self.assertEqual(value['failure_info']['node_id'], node)
                self.assertEqual(value['failure_info']['node_type'], kind)
                self.assertEqual(value['failure_info']['exception_type'], exception)
                self.assertEqual(value['history'], entry)
                self.assert_safe(value['failure_info'])
                remote.post.assert_not_called()

    def test_oom_is_not_inferred_from_unrelated_or_malformed_diagnostics(self):
        job = self.job()
        entries = [self.entry(job, exception='RuntimeError', message='out of memory'),
                   self.entry(job, exception='OutOfMemoryError'),
                   self.entry(job, exception='example.OutOfMemoryError'),
                   self.entry(job, prompt_id=str(uuid4())), self.entry(job, node='unrelated'),
                   self.entry(job, kind='CheckpointLoaderSimple'), self.entry(job, node_id=5),
                   self.entry(job, exception='PRIVATE_\nTRACE'),
                   self.entry(job, exception='x' * 121),
                   self.entry(job, exception='RuntimeError', message='x' * 8193 + 'CUDA out of memory')]
        interrupted = self.entry(job)
        interrupted['status']['messages'][0][0] = 'execution_interrupted'
        entries += [interrupted, dict(status=dict(completed=False, status_str='error')),
                    dict(status=dict(completed=False, status_str='error', messages='CUDA out of memory'))]
        for entry in entries:
            diagnostic = failures.from_history(job, entry)
            self.assertEqual(diagnostic['code'], 'execution_failed', entry)
            self.assert_safe(diagnostic)
        success = self.entry(job)
        success['status'].update(status_str='success', completed=True)
        self.assertIsNone(failures.from_history(job, success))

    def test_execution_error_hint_without_confirmed_history_failure_does_not_claim_failure(self):
        job = self.job()
        entry = self.entry(job)
        entry['status'].update(status_str='success', completed=True)
        remote = self.historical_remote({job['prompt_id']: entry})
        with patch('backend.submissions.httpx.AsyncClient', return_value=remote):
            result = self.post(job)
        self.assertEqual(result.json()['status'], 'completed')
        self.assertIsNone(result.json()['failure_info'])
        hint = json.dumps(dict(type='execution_error', data=entry['status']['messages'][0][1]))
        self.assertEqual(progress.parse_event(hint, job), ('reconcile', None))

    def test_history_with_explicit_foreign_prompt_workflow_or_owner_is_not_reconciled(self):
        for mismatch in ('id', 'workflow', 'owner'):
            job = self.job()
            entry = self.entry(job)
            entry['prompt'] = [0, job['prompt_id'], job['workflow'], {'model_atelier_job_id': job['id']}]
            if mismatch == 'id':
                entry['prompt'][1] = str(uuid4())
            elif mismatch == 'workflow':
                entry['prompt'][2] = {}
            else:
                entry['prompt'][3]['model_atelier_job_id'] = str(uuid4())
            remote = self.historical_remote({job['prompt_id']: entry})
            with patch('backend.submissions.httpx.AsyncClient', return_value=remote):
                self.assertEqual(self.post(job).status_code, 503)
            value = jobs.get(self.db, job['id'])
            self.assertEqual(value['status'], 'queued')
            self.assertIsNone(value['failure_info'])
            self.assertIsNone(value['history'])

    def test_preflight_failures_have_actionable_codes_without_prompt_submission(self):
        for condition, code, status in [('empty', 'no_checkpoints', 409), ('missing', 'checkpoint_missing', 409),
                                        ('offline', 'engine_offline', 503), ('invalid', 'preflight_invalid', 502),
                                        ('unsupported', 'unsupported_architecture', 422)]:
            body = self.settings() | {'request_id': str(uuid4())}
            remote = self.remote(names=[] if condition == 'empty' else ['other'] if condition == 'missing' else None)
            if condition == 'offline':
                remote.get.side_effect = httpx.ConnectError('PRIVATE_CONNECT_TRACE')
            elif condition == 'invalid':
                remote.get.side_effect = None
                remote.get.return_value = self.response({})
            elif condition == 'unsupported':
                catalog.merge(self.db, body['engine_url'], [body['checkpoint']])
                catalog.update_metadata(self.db, body['engine_url'], body['checkpoint'], {'architecture': 'flux'})
            else:
                catalog.merge(self.db, body['engine_url'], [body['checkpoint']])
                catalog.update_metadata(self.db, body['engine_url'], body['checkpoint'], {'architecture': 'unknown'})
            with patch('backend.submissions.httpx.AsyncClient', return_value=remote):
                result = self.client.post('/api/generate', json=body)
            self.assertEqual(result.status_code, status, result.text)
            job = jobs.get(self.db, body['request_id'])
            self.assertEqual(job['failure_info']['code'], code)
            self.assertEqual(job['failure_info'], result.json()['detail']['failure_info'])
            self.assert_safe(job['failure_info'])
            remote.post.assert_not_called()

    def test_capability_offline_and_engine_changed_failures_are_classified(self):
        for change in (False, True):
            body = self.settings() | {'request_id': str(uuid4())}
            remote = self.remote()
            original = remote.get.side_effect
            def get(url):
                result = original(url)
                if url.endswith('/object_info/KSampler'):
                    if change:
                        self.client.put('/api/settings', json={'comfy_url': 'http://127.0.0.1:9000'})
                    else:
                        raise httpx.ReadTimeout('PRIVATE_TIMEOUT')
                return result
            remote.get.side_effect = get
            with patch('backend.submissions.httpx.AsyncClient', return_value=remote):
                result = self.client.post('/api/generate', json=body)
            self.assertEqual(result.status_code, 409 if change else 503, result.text)
            self.assertEqual(jobs.get(self.db, body['request_id'])['failure_info']['code'], 'engine_changed' if change else 'engine_offline')
            remote.post.assert_not_called()

    def test_upstream400_is_safe_rejection_not_oom_and_only_exposes_matching_saved_node(self):
        for bad_node in (False, True):
            body = self.settings() | {'request_id': str(uuid4())}
            raw = dict(error='CUDA out of memory PRIVATE_PROMPT', node_errors={
                '5': dict(class_type='CheckpointLoaderSimple' if bad_node else 'KSampler',
                          errors=[dict(type='PRIVATE_TYPE', details='PRIVATE_PROMPT', traceback='PRIVATE_TRACE')])})
            remote = self.remote()
            remote.post.return_value = self.response(raw, 400)
            with patch('backend.submissions.httpx.AsyncClient', return_value=remote):
                result = self.client.post('/api/generate', json=body)
            self.assertEqual(result.status_code, 422, result.text)
            job = jobs.get(self.db, body['request_id'])
            self.assertEqual(job['failure_info']['code'], 'workflow_rejected')
            self.assertEqual(job['failure_info']['node_id'], None if bad_node else '5')
            self.assertEqual(job['upstream_error'], raw)
            self.assert_safe(job['failure_info'])
        body = self.settings() | {'request_id': str(uuid4())}
        remote = self.remote()
        remote.post.return_value = httpx.Response(400, request=httpx.Request('POST', 'http://test'), content=b'PRIVATE_TRACE')
        with patch('backend.submissions.httpx.AsyncClient', return_value=remote):
            result = self.client.post('/api/generate', json=body)
        self.assertEqual(result.status_code, 422)
        self.assertEqual(jobs.get(self.db, body['request_id'])['failure_info']['code'], 'workflow_rejected')

    def test_cancellation_and_cancel_unknown_refresh_retain_confirmed_failure_and_raw_history(self):
        for action, initial in [('cancel', 'queued'), ('refresh', 'cancel_unknown')]:
            job = self.job(initial)
            entry = self.entry(job)
            remote = self.historical_remote(dict(queue_running=[], queue_pending=[]), {job['prompt_id']: entry})
            with patch('backend.cancellation.httpx.AsyncClient', return_value=remote):
                result = self.post(job, action)
            self.assertEqual(result.status_code, 200, result.text)
            self.assertEqual(result.json()['status'], 'failed')
            self.assertEqual(result.json()['failure_info']['code'], 'cuda_oom')
            self.assertEqual(result.json()['history'], entry)
            remote.post.assert_not_called()

    def test_stale_refresh_and_late400_cannot_overwrite_newer_cancellation_with_failure(self):
        job = self.job()
        remote = self.historical_remote()
        async def observed(url):
            jobs.update(self.db, job['id'], status='cancelled')
            return self.response({job['prompt_id']: self.entry(job)})
        remote.get.side_effect = observed
        with patch('backend.submissions.httpx.AsyncClient', return_value=remote):
            self.assertEqual(self.post(job).status_code, 409)
        current = jobs.get(self.db, job['id'])
        self.assertEqual(current['status'], 'cancelled')
        self.assertIsNone(current['failure_info'])
        self.assertIsNone(current['history'])
        body = self.settings() | {'request_id': str(uuid4())}
        remote = self.remote()
        async def rejected(url, **kwargs):
            jobs.update(self.db, body['request_id'], status='cancelled')
            return self.response({'error': 'PRIVATE_TRACE'}, 400)
        remote.post.side_effect = rejected
        with patch('backend.submissions.httpx.AsyncClient', return_value=remote):
            self.assertEqual(self.client.post('/api/generate', json=body).status_code, 409)
        self.assertEqual(jobs.get(self.db, body['request_id'])['status'], 'cancelled')
        self.assertIsNone(jobs.get(self.db, body['request_id'])['failure_info'])

    def test_failed_job_restore_is_lossless_read_only_and_retains_original_metadata_offline(self):
        node_ids = dict(zip(workflows.ROLES, ('loader', 'positive', 'negative', 'latent', 'sampler', 'decoder', 'actual_save')))
        job = self.job('failed', node_ids)
        catalog.merge(self.db, job['engine_url'], [job['checkpoint']])
        catalog.update_metadata(self.db, job['engine_url'], job['checkpoint'], {'version': 'changed', 'architecture': 'flux'})
        self.client.put('/api/settings', json={'comfy_url': 'http://127.0.0.1:9000'})
        before = self.rows()
        with patch('backend.submissions.httpx.AsyncClient', side_effect=AssertionError('restore must remain offline')):
            response = self.client.get('/api/jobs/' + job['id'] + '/creation-settings')
        self.assertEqual(response.status_code, 200, response.text)
        value = response.json()
        expected = self.settings() | {'title': '失敗任務設定'}
        self.assertEqual(value['settings'], expected)
        self.assertEqual(value['settings']['seed'], '18446744073709551615')
        self.assertEqual(value['model_version'], 'original-v1')
        self.assertEqual(value['model_metadata'], job['model_metadata'])
        self.assertFalse(value['availability']['engine_matches'])
        self.assertEqual(value['availability']['checkpoint_status'], 'available')
        self.assertTrue(any('原引擎' in warning for warning in value['warnings']))
        self.assertTrue(any('模型版本' in warning for warning in value['warnings']))
        self.assertNotIn('request_id', value['settings'])
        self.assertEqual(self.rows(), before)

    def test_restore_requires_failed_status_and_whole_standard_graph_without_partial_parameters(self):
        for status in ('queued', 'running', 'unknown', 'validating', 'submitting', 'cancel_unknown', 'cancelled', 'completed'):
            job = self.job(status)
            self.assertEqual(self.client.get('/api/jobs/' + job['id'] + '/creation-settings').status_code, 409)
        self.assertEqual(self.client.get('/api/jobs/' + str(uuid4()) + '/creation-settings').status_code, 404)
        for change in ('extra', 'custom', 'duplicate_output', 'missing_output', 'unsafe_seed'):
            job = self.job('failed')
            graph = copy.deepcopy(job['workflow'])
            if change == 'extra':
                graph['5']['inputs']['hidden_option'] = 'PRIVATE_PROMPT'
            elif change == 'custom':
                graph['1']['class_type'] = 'CustomLoader'
            elif change == 'duplicate_output':
                graph['8'] = copy.deepcopy(graph['7'])
            elif change == 'missing_output':
                graph.pop('7')
            else:
                graph['5']['inputs']['seed'] = True
            jobs.update(self.db, job['id'], workflow=graph)
            before = self.rows()
            response = self.client.get('/api/jobs/' + job['id'] + '/creation-settings')
            self.assertEqual(response.status_code, 422, response.text)
            self.assertNotIn('settings', response.json())
            self.assertEqual(self.rows(), before)

    def test_old_failures_remain_nullable_unknown_without_backfill_or_replay(self):
        job = self.job('failed')
        job.pop('failure_info')
        job.pop('model_metadata')
        with closing(sqlite3.connect(self.db)) as db, db:
            db.execute('UPDATE settings SET value=? WHERE key=?', (json.dumps(job), 'job:' + job['id']))
        before = self.rows()
        with (patch('backend.submissions.httpx.AsyncClient', side_effect=AssertionError('no retry')),
              patch('backend.submissions.catalog.read', side_effect=AssertionError('no metadata recapture'))):
            detail = self.client.get('/api/jobs/' + job['id']).json()
            listed = self.client.get('/api/jobs').json()[0]
            replay = self.client.post('/api/jobs', json=dict(request_id=job['id'], engine_url=job['engine_url'],
                                                           checkpoint=job['checkpoint'], workflow=job['workflow'])).json()
        for value in (detail, listed, replay, progress.summary(detail)):
            self.assertIsNone(value['failure_info'])
        self.assertEqual(self.rows(), before)
        restored = self.client.get('/api/jobs/' + job['id'] + '/creation-settings').json()
        self.assertIsNone(restored['model_metadata'])
        self.assertEqual(self.rows(), before)

    def test_sse_summary_includes_safe_failure_info_but_not_history_or_prompt_diagnostics(self):
        job = self.job('failed')
        entry = self.entry(job)
        job.update(history=entry, failure_info=failures.from_history(job, entry), upstream_error={'traceback': 'PRIVATE_TRACE'})
        summary = progress.summary(job)
        self.assertEqual(summary['failure_info']['code'], 'cuda_oom')
        self.assertNotIn('history', summary)
        raw = progress.frame('job', {'job': summary})
        self.assertNotIn('PRIVATE_', raw)
        self.assertNotIn('current_inputs', raw)
        self.assertNotIn('traceback', raw)
