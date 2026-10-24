from contextlib import closing
import asyncio
import errno
import io
import json
import sqlite3
import unittest
from unittest.mock import patch
from uuid import UUID, uuid4

import httpx
from PIL import Image
from fastapi.testclient import TestClient
from backend import diagnostics, gallery, jobs, main, test_api, test_submissions


class DiagnosticTests(unittest.TestCase):
    setUp = test_api.ApiTests.setUp
    tearDown = test_api.ApiTests.tearDown
    payload = test_submissions.SubmissionTests.payload
    remote = test_submissions.SubmissionTests.remote

    def events(self, job_id=None):
        return self.client.get('/api/diagnostics', params={'job_id': job_id} if job_id else {}).json()['events']

    def assert_private(self, value):
        text = json.dumps(value)
        for secret in ('PRIVATE', 'a mountain', 'test.safetensors', 'http://', str(self.db), 'current_inputs', 'node_errors'):
            self.assertNotIn(secret, text)

    def test_lost_response_recovery_and_conflict_share_job_not_new_submission(self):
        remote = self.remote()
        remote.post.side_effect = httpx.ReadTimeout('PRIVATE secret http://user:password@host/path')
        body = self.payload() | dict(prompt='PRIVATE_PROMPT C:\\Users\\PERSON', negative_prompt='PRIVATE_NEGATIVE')
        with patch.object(self.host, 'engine_client_factory', lambda **kw: remote):
            first = self.client.post('/api/generate', json=body, headers={'X-Request-ID': 'PRIVATE', 'Authorization': 'PRIVATE'})
            recovery = self.client.post('/api/generate', json=body)
            conflict = self.client.post('/api/generate', json=body | dict(prompt='PRIVATE_CHANGED'))
        self.assertEqual(first.json()['status'], 'unknown')
        self.assertEqual(recovery.json()['id'], body['request_id'])
        self.assertEqual(conflict.status_code, 409)
        self.assertEqual(remote.post.await_count, 1)
        for response in (first, recovery, conflict):
            self.assertEqual(str(UUID(response.headers['x-request-id'])), response.headers['x-request-id'])
        events = self.events(body['request_id'])
        self.assertEqual(sum(e['stage'] == 'submission_new' for e in events), 1)
        self.assertEqual(sum(e['stage'] == 'submission_recovered' for e in events), 1)
        submitted = [e for e in events if e['stage'] == 'engine_submit']
        self.assertEqual(len(submitted), 1)
        self.assertEqual(submitted[0]['classification'], 'submission_uncertain')
        requests = [e for e in events if e['stage'] == 'api_request']
        self.assertEqual({e['request_id'] for e in requests}, {r.headers['x-request-id'] for r in (first, recovery, conflict)})
        self.assertEqual(requests[-1]['classification'], 'conflict')
        filtered = self.client.get('/api/diagnostics', params={'job_id': body['request_id'], 'request_id': recovery.headers['x-request-id']}).json()['events']
        self.assertTrue(filtered)
        self.assertTrue(all(e['request_id'] == recovery.headers['x-request-id'] for e in filtered))
        self.assertTrue(all(e['workflow'] == 'checkpoint-text2image-v1' for e in events))
        self.assertTrue(all(e['duration_ms'] >= 0 for e in events))
        self.assert_private(self.client.get('/api/diagnostics').json())

    def test_offline_preflight_has_same_job_classification_and_no_submission(self):
        remote = self.remote(); remote.get.side_effect = httpx.ConnectError('PRIVATE_OFFLINE')
        body = self.payload()
        with patch.object(self.host, 'engine_client_factory', lambda **kw: remote):
            response = self.client.post('/api/generate', json=body)
        self.assertEqual(response.status_code, 503)
        remote.post.assert_not_called()
        events = self.events(body['request_id'])
        self.assertTrue(any(e.get('classification') == 'engine_offline' for e in events))
        terminal = [e for e in events if e['stage'] == 'job_transition' and e.get('terminal')]
        self.assertEqual(terminal[-1]['state'], 'failed')
        self.assertEqual(terminal[-1]['request_id'], response.headers['x-request-id'])

    def test_disk_error_after_dispatch_is_safe_and_recovers_uuid_without_repost(self):
        remote, body, original = self.remote(), self.payload(), jobs._update
        def disk_full(path, job_id, revision, changes):
            if changes.get('status') == 'queued':
                raise OSError(errno.ENOSPC, 'PRIVATE C:\\Users\\PERSON disk full')
            return original(path, job_id, revision, changes)
        with patch.object(self.host, 'engine_client_factory', lambda **kw: remote):
            with patch('backend.jobs._update', side_effect=disk_full):
                response = self.client.post('/api/generate', json=body)
            recovered = self.client.post('/api/generate', json=body)
        self.assertEqual(response.status_code, 503)
        self.assertEqual(recovered.json()['status'], 'submitting')
        self.assertEqual(remote.post.await_count, 1)
        events = self.events(body['request_id'])
        self.assertTrue(any(e.get('classification') == 'storage_unavailable' and e['request_id'] == response.headers['x-request-id'] for e in events))
        self.assertEqual(sum(e['stage'] == 'submission_new' for e in events), 1)
        self.assertEqual(sum(e['stage'] == 'submission_recovered' for e in events), 1)
        self.assert_private([response.json(), events])

    def test_stale_observation_is_ignored_and_separate_from_authoritative_terminal(self):
        remote, body = self.remote(), self.payload()
        with patch.object(self.host, 'engine_client_factory', lambda **kw: remote):
            self.client.post('/api/generate', json=body)
        @self.app.post('/api/test-stale/{job_id}')
        def stale(job_id: UUID):
            snapshot = jobs.get(self.db, str(job_id))
            jobs.update(self.db, str(job_id), status='completed')
            current, changed = jobs.compare_update(self.db, snapshot, status='running')
            return {'state': current['status'], 'changed': changed}
        # This route must precede the static frontend mount for test-only access.
        self.app.router.routes.insert(0, self.app.router.routes.pop())
        result = self.client.post('/api/test-stale/' + body['request_id'])
        self.assertEqual(result.json(), {'state': 'completed', 'changed': False})
        events = self.events(body['request_id'])
        ignored = [e for e in events if e['stage'] == 'observation_stale'][-1]
        self.assertEqual((ignored['state'], ignored['attempted_state'], ignored['outcome']), ('completed', 'running', 'ignored_stale'))
        self.assertTrue(ignored['terminal'])
        self.assertFalse(any(e['stage'] == 'job_transition' and e.get('state') == 'running' for e in events))

    def test_readiness_offline_artwork_preview_readonly_and_data_failure_separate(self):
        remote, body = self.remote(), self.payload()
        with patch.object(self.host, 'engine_client_factory', lambda **kw: remote):
            self.client.post('/api/generate', json=body)
        job = jobs.update(self.db, body['request_id'], status='completed', history={'status': {'completed': True, 'status_str': 'success'}, 'outputs': {'7': {'images': [{'filename': 'PRIVATE.png', 'type': 'output', 'subfolder': ''}]}}})
        image = io.BytesIO(); Image.new('RGB', (8, 8), 'red').save(image, 'PNG')
        artwork, _ = gallery.save(self.db, self.host.DATA / 'artworks', job, gallery.outputs(job)[0], image.getvalue())
        remote.get.side_effect = httpx.ConnectError('PRIVATE')
        with patch.object(self.host, 'engine_client_factory', lambda **kw: remote):
            report = self.client.get('/api/status?probe_engine=true').json()
        self.assertEqual((report['service']['status'], report['data']['status'], report['engine']['status']), ('alive', 'readable', 'offline'))
        self.assertEqual(self.client.get('/api/health').json(), {'status': 'ok'})
        self.assertEqual(self.client.get('/api/artworks/' + artwork['id'] + '/image').content, image.getvalue())
        conflict = self.client.patch('/api/artworks/' + artwork['id'] + '/organization', json={'revision': artwork['revision'] + 1, 'notes': 'PRIVATE_NOTE'})
        self.assertEqual(conflict.status_code, 409)
        self.assertTrue(any(e['job_id'] == job['id'] and e.get('classification') == 'conflict'
                            for e in self.events(job['id'])))
        before = self.db.read_bytes()
        with patch.object(self.host, 'engine_client_factory', side_effect=AssertionError('diagnostic must not call engine')):
            first = self.client.get('/api/diagnostics')
            second = self.client.get('/api/diagnostics')
        self.assertEqual(first.json()['events'], second.json()['events'])
        self.assertEqual(self.db.read_bytes(), before)
        self.assertEqual(first.headers['cache-control'], 'no-store')
        self.assert_private(first.json())
        with patch('backend.diagnostics_api.os.scandir', side_effect=OSError('PRIVATE')):
            report = self.client.get('/api/status').json()
        self.assertEqual(report['service']['status'], 'alive')
        self.assertEqual(report['data']['status'], 'unavailable')
        self.assertEqual(self.client.get('/api/diagnostics?job_id=invalid').status_code, 422)

    def test_bounded_retention_allowlist_and_unknown_urls_never_capture_payloads(self):
        clock = [1000000000.0]
        recorder = diagnostics.Recorder(max_events=3, max_bytes=1500, ttl=10, clock=lambda: clock[0])
        for _ in range(20):
            recorder.add('api_request', job_id='PRIVATE', workflow='PRIVATE', state='PRIVATE', classification='PRIVATE',
                         prompt='PRIVATE', headers='PRIVATE', request_id='PRIVATE')
        report = recorder.snapshot()
        self.assertLessEqual(len(report['events']), 3)
        self.assertLessEqual(report['retention']['retained_bytes'], 1500)
        self.assert_private(report)
        self.assertEqual(diagnostics.exception_class(asyncio.CancelledError()), 'cancelled')
        self.assertEqual(diagnostics.exception_class(BrokenPipeError()), 'cancelled')
        clock[0] += 11
        self.assertEqual(recorder.snapshot()['events'], [])
        recorder.add('api_request', request_id=str(uuid4()), state=[], classification={})
        self.assertEqual(len(recorder.snapshot()['events']), 1)
        self.client.get('/api/PRIVATE?token=PRIVATE', headers={'Authorization': 'PRIVATE'})
        self.assert_private(self.events())
        with TestClient(main.create_app(data_root=self.host.DATA / 'separate'), base_url='http://127.0.0.1:8000', client=('127.0.0.1', 50000)) as other:
            self.assertEqual(other.get('/api/diagnostics').json()['events'], [])

    def test_snapshot_reboot_is_empty_and_route_headers_do_not_use_client_identity(self):
        self.client.get('/api/settings', headers={'X-Request-ID': 'PRIVATE'})
        self.assertTrue(self.events())
        with TestClient(main.create_app(data_root=self.host.DATA, database=self.db), base_url='http://127.0.0.1:8000', client=('127.0.0.1', 50000)) as restarted:
            self.assertEqual(restarted.get('/api/diagnostics').json()['events'], [])
        self.assert_private(self.events())
