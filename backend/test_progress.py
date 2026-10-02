import asyncio
import copy
import json
import math
import sqlite3
import unittest
from collections import deque
from contextlib import closing
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import httpx
import anyio
from fastapi import FastAPI
from starlette.requests import ClientDisconnect

from backend import jobs, main, progress, test_api, workflows


class Socket:
    def __init__(self, events=(), order=None):
        self.events = deque(events)
        self.opened = False
        self.closed = False
        self.order = order if order is not None else []

    async def __aenter__(self):
        self.opened = True
        self.order.append('connect')
        return self

    async def __aexit__(self, *args):
        self.closed = True
        self.order.append('close')

    async def recv(self):
        if self.events:
            event = self.events.popleft()
            if isinstance(event, Exception):
                raise event
            if callable(event):
                return await event()
            return event
        await asyncio.Event().wait()


class ProgressTests(unittest.IsolatedAsyncioTestCase):
    setUp = test_api.ApiTests.setUp

    async def asyncSetUp(self):
        self.locks = {}
        self.observations = []

        async def reconcile(job_id):
            self.observations.append(str(job_id))
            return jobs.get(self.db, str(job_id))

        self.reconcile = reconcile
        self.hubs = []

    async def asyncTearDown(self):
        for hub in self.hubs:
            for session in tuple(hub.sessions.values()):
                for queue in tuple(session.listeners):
                    await hub.unsubscribe(session, queue)
        test_api.ApiTests.tearDown(self)

    def job(self, status='queued'):
        value = main.DraftInput(title='進度測試', engine_url='http://127.0.0.1:8188/base',
                                checkpoint='sample.safetensors', seed=str(2**64 - 1)).model_dump()
        item, _ = jobs.reserve(self.db, str(uuid4()), value['engine_url'], workflows.build(value), value['checkpoint'], 'v1')
        return jobs.update(self.db, item['id'], status=status, prompt_id=str(uuid4()))

    def lock(self, job_id):
        return self.locks.setdefault(str(job_id), asyncio.Lock())

    def hub(self, reconcile=None):
        hub = progress.Hub(main, reconcile or self.reconcile, self.lock)
        self.hubs.append(hub)
        return hub

    def event(self, job, kind='progress', **changes):
        return json.dumps({'type': kind, 'data': {'prompt_id': job['prompt_id'], 'node': '5', 'value': 5, 'max': 20} | changes})

    async def until(self, predicate):
        async with asyncio.timeout(2):
            while not predicate():
                await asyncio.sleep(0.01)

    def frames(self, queue):
        result = []
        while not queue.empty():
            value = queue.get_nowait()
            if value is not progress.END:
                result.append(value)
        return result

    def test_message_identity_node_and_number_validation(self):
        job = self.job()
        valid = progress.parse_event(self.event(job), job)
        self.assertEqual(valid[0], 'progress')
        self.assertEqual({key: valid[1][key] for key in ('node', 'current', 'max', 'percent')},
                         dict(node='5', current=5, max=20, percent=25))
        invalid = [b'preview', '{}', '[]', '{', 'x' * (progress.MAX_MESSAGE + 1), '\ud800',
                   self.event(job, prompt_id=str(uuid4())), self.event(job, prompt_id=None),
                   self.event(job, node='unknown'), self.event(job, node=5), self.event(job, node=None),
                   self.event(job, value=True), self.event(job, max=True), self.event(job, value=-1),
                   self.event(job, value=21), self.event(job, max=0), self.event(job, max=-1),
                   self.event(job, value=math.nan), self.event(job, max=math.inf),
                   self.event(job, value=10**500), self.event(job, max=10**500),
                   self.event(job, kind='status'), self.event(job, kind='executed', output={'secret': 'large graph'}),
                   self.event(job, kind='progress_state', nodes={'5': {'prompt_id': str(uuid4())}})]
        for raw in invalid:
            with self.subTest(raw=str(raw)[:80]):
                self.assertIsNone(progress.parse_event(raw, job))
        data = json.loads(self.event(job))
        data['data'].pop('prompt_id')
        self.assertIsNone(progress.parse_event(json.dumps(data), job))

    def test_finish_markers_only_request_history_reconciliation(self):
        job = self.job()
        for kind in ('execution_success', 'execution_error', 'execution_interrupted'):
            self.assertEqual(progress.parse_event(self.event(job, kind=kind), job), ('reconcile', None))
        self.assertEqual(progress.parse_event(self.event(job, kind='executing', node=None), job), ('reconcile', None))
        parsed = progress.parse_event(self.event(job, kind='executing', node='6'), job)
        self.assertEqual(parsed[1]['node'], '6')
        self.assertIsNone(parsed[1]['percent'])

    def test_summary_and_frame_do_not_forward_workflow_seed_history_or_outputs(self):
        job = self.job()
        job.update(history={'large': 'secret'}, submission={'x': 2**64 - 1}, upstream_error={'secret': True})
        value = progress.summary(job)
        for key in ('workflow', 'history', 'submission', 'upstream_error'):
            self.assertNotIn(key, value)
        raw = progress.frame('job', {'job': value})
        self.assertTrue(raw.startswith('event: job\ndata: '))
        self.assertNotIn(str(2**64 - 1), raw)
        self.assertNotIn('secret', raw)
        self.assertTrue(progress.socket_url(job).startswith('ws://127.0.0.1:8188/base/ws?clientId=' + job['id']))
        self.assertEqual(progress.socket_url(job | {'engine_url': 'https://engine.local/prefix'}),
                         'wss://engine.local/prefix/ws?clientId=' + job['id'])

    async def test_connect_before_recovery_shares_upstream_and_filters_foreign_events(self):
        job = self.job()
        order = []

        async def reconcile(job_id):
            order.append('recover')
            return jobs.get(self.db, str(job_id))

        socket = Socket([self.event(job, prompt_id=str(uuid4())), b'preview', self.event(job, prompt_id=None), self.event(job)], order)
        hub = self.hub(reconcile)
        with patch('backend.progress.connect', return_value=socket) as connection:
            session, first = await hub.subscribe(job['id'])
            _, second = await hub.subscribe(job['id'])
            await self.until(lambda: jobs.get(self.db, job['id']).get('progress') is not None)
            self.assertEqual(connection.call_count, 1)
            self.assertEqual(order[:2], ['connect', 'recover'])
            kwargs = connection.call_args.kwargs
            self.assertIsNone(kwargs['proxy'])
            self.assertEqual(kwargs['max_size'], 1024 * 1024)
            self.assertEqual(kwargs['max_queue'], 16)
            for queue in (first, second):
                messages = ''.join(self.frames(queue))
                self.assertIn('"percent": 25.0', messages)
                self.assertNotIn('preview', messages)
            await hub.unsubscribe(session, first)
            self.assertFalse(socket.closed)
            await hub.unsubscribe(session, second)
        self.assertTrue(socket.closed)
        self.assertNotIn(job['id'], hub.sessions)
        self.assertEqual(jobs.get(self.db, job['id'])['workflow'], job['workflow'])

    async def test_terminal_sse_responds_without_websocket_and_endpoint_unknown_is_404(self):
        job = self.job('completed')
        hub = self.hub()
        with patch('backend.progress.connect', side_effect=AssertionError('terminal has no socket')):
            session, queue = await hub.subscribe(job['id'])
            await session.task
            self.assertIn('"status": "completed"', ''.join(self.frames(queue)))
            result = self.client.get('/api/jobs/' + job['id'] + '/events')
        self.assertEqual(result.status_code, 200)
        self.assertIn('text/event-stream', result.headers['content-type'])
        self.assertEqual(result.headers['x-accel-buffering'], 'no')
        self.assertNotIn('workflow', result.text)
        self.assertEqual(self.client.get('/api/jobs/' + str(uuid4()) + '/events').status_code, 404)

    async def test_progress_db_throttled_and_streamed_values_do_not_flicker_to_old_db_copy(self):
        job = self.job()
        hub = self.hub()
        session = progress.Session(job['id'], str(uuid4()))
        queue = asyncio.Queue(maxsize=16)
        session.listeners.add(queue)
        value = progress.parse_event(self.event(job), job)[1]
        with patch('backend.progress.time.monotonic', return_value=10):
            await hub.update_progress(session, value)
        original_revision = jobs.get(self.db, job['id'])['revision']
        value2 = value | {'current': 10, 'percent': 50}
        with patch('backend.progress.time.monotonic', return_value=10.3):
            await hub.update_progress(session, value2)
        self.assertEqual(jobs.get(self.db, job['id'])['revision'], original_revision)
        self.assertEqual(session.last_summary['progress']['percent'], 50)
        hub.publish(session, jobs.get(self.db, job['id']))
        self.assertEqual(session.last_summary['progress']['percent'], 50)
        with patch('backend.progress.time.monotonic', return_value=11.1):
            await hub.update_progress(session, value2)
        self.assertEqual(jobs.get(self.db, job['id'])['revision'], original_revision + 1)
        self.assertEqual(jobs.get(self.db, job['id'])['progress']['percent'], 50)

    async def test_progress_does_not_override_terminal_or_cancellation_statuses(self):
        hub = self.hub()
        for state in ('completed', 'failed', 'cancelled', 'cancelling', 'cancel_unknown', 'submitting', 'validating'):
            job = self.job(state)
            session = progress.Session(job['id'], str(uuid4()))
            value = progress.parse_event(self.event(job), job)[1]
            await hub.update_progress(session, value)
            self.assertEqual(jobs.get(self.db, job['id']), job)

    async def test_cas_loses_to_concurrent_cancel_without_claiming_running(self):
        job = self.job()
        hub = self.hub()
        session = progress.Session(job['id'], str(uuid4()))
        original = jobs.compare_update

        def concurrent(path, snapshot, **changes):
            jobs.update(path, snapshot['id'], status='cancelled')
            return original(path, snapshot, **changes)

        with patch('backend.progress.jobs.compare_update', side_effect=concurrent):
            await hub.update_progress(session, progress.parse_event(self.event(job), job)[1])
        self.assertEqual(jobs.get(self.db, job['id'])['status'], 'cancelled')
        self.assertEqual(session.last_summary['status'], 'cancelled')

    async def test_progress_node_reset_and_known_completion_use_history(self):
        job = self.job()
        observations = 0

        async def reconcile(job_id):
            nonlocal observations
            observations += 1
            current = jobs.get(self.db, str(job_id))
            if observations >= 2:
                return jobs.compare_update(self.db, current, status='completed', history={'status': {'completed': True}})[0]
            return current

        # A success event is a hint. Poll is deferred and status remains running
        # until the history callback explicitly returns completed.
        socket = Socket([self.event(job), self.event(job, kind='execution_success')])
        hub = self.hub(reconcile)
        with patch('backend.progress.connect', return_value=socket), patch('backend.progress.POLL_INTERVAL', 0.02), patch('backend.progress.HEARTBEAT', 0.02):
            session, queue = await hub.subscribe(job['id'])
            await asyncio.wait_for(session.task, 2)
        self.assertEqual(jobs.get(self.db, job['id'])['status'], 'completed')
        self.assertTrue(socket.closed)
        self.assertGreaterEqual(observations, 2)

    async def test_reconnect_closes_old_socket_before_replacement_and_history_restores_completion(self):
        job = self.job()
        order = []
        first = Socket([OSError('closed')], order)
        second = Socket([], order)
        calls = 0

        async def reconcile(job_id):
            nonlocal calls
            calls += 1
            current = jobs.get(self.db, str(job_id))
            if calls == 3:
                return jobs.compare_update(self.db, current, status='completed', history={'result': 'retained'})[0]
            return current

        hub = self.hub(reconcile)
        with patch('backend.progress.connect', side_effect=[first, second]), patch.object(hub, 'pause', return_value=False):
            session, queue = await hub.subscribe(job['id'])
            await asyncio.wait_for(session.task, 2)
        self.assertEqual(order, ['connect', 'close', 'connect', 'close'])
        self.assertEqual(jobs.get(self.db, job['id'])['status'], 'completed')
        self.assertIn('"state": "reconnecting"', ''.join(self.frames(queue)))

    async def test_websocket_failure_falls_back_at_bounded_attempts_then_stops(self):
        job = self.job()
        hub = self.hub()
        with patch('backend.progress.connect', side_effect=OSError('offline')) as connection, patch.object(hub, 'pause', return_value=False):
            session, queue = await hub.subscribe(job['id'])
            await asyncio.wait_for(session.task, 2)
        self.assertEqual(connection.call_count, progress.MAX_CONNECTIONS)
        self.assertEqual(len(self.observations), progress.MAX_CONNECTIONS + progress.FALLBACK_POLLS)
        self.assertIn('"state": "offline"', ''.join(self.frames(queue)))
        self.assertEqual(jobs.get(self.db, job['id'])['status'], 'queued')
        self.assertEqual(jobs.get(self.db, job['id'])['workflow'], job['workflow'])

    async def test_slow_listener_queue_and_listener_count_are_bounded(self):
        job = self.job()
        socket = Socket()
        hub = self.hub()
        with patch('backend.progress.connect', return_value=socket):
            session, queue = await hub.subscribe(job['id'])
            for index in range(100):
                hub.broadcast(session, 'job', {'job': {'id': job['id'], 'status': 'running', 'progress': {'current': index}}})
            self.assertEqual(queue.qsize(), 16)
            self.assertIn('"current": 99', self.frames(queue)[-1])
            for _ in range(progress.MAX_LISTENERS - 1):
                await hub.subscribe(job['id'])
            with self.assertRaises(Exception) as error:
                await hub.subscribe(job['id'])
            self.assertEqual(error.exception.status_code, 429)

    async def test_stream_disconnect_cancels_reader_and_releases_cross_worker_lease(self):
        job = self.job()
        socket = Socket()
        hub = self.hub()
        request = AsyncMock()
        request.is_disconnected.return_value = False
        with patch('backend.progress.connect', return_value=socket):
            session, queue = await hub.subscribe(job['id'])
            await self.until(lambda: socket.opened)
            stream = hub.stream(session, queue, request)
            self.assertIn('event: job', await anext(stream))
            await stream.aclose()
        self.assertTrue(socket.closed)
        self.assertNotIn(job['id'], hub.sessions)
        self.assertTrue(jobs.claim_watch(self.db, job['id'], 'another-worker'))
        jobs.release_watch(self.db, job['id'], 'another-worker')

    async def test_anyio_disconnect_scope_cannot_interrupt_registry_cleanup(self):
        job = self.job()
        socket = Socket()
        hub = self.hub()
        request = AsyncMock()
        request.is_disconnected.return_value = False
        with patch('backend.progress.connect', return_value=socket):
            session, queue = await hub.subscribe(job['id'])
            await self.until(lambda: socket.opened)
            stream = hub.stream(session, queue, request)
            await anext(stream)
            with anyio.CancelScope() as scope:
                scope.cancel()
                await stream.aclose()
        self.assertTrue(socket.closed)
        self.assertNotIn(job['id'], hub.sessions)
        self.assertTrue(jobs.claim_watch(self.db, job['id'], 'replacement'))
        jobs.release_watch(self.db, job['id'], 'replacement')

    async def test_header_disconnect_before_stream_starts_still_releases_listener(self):
        job = self.job()
        app = FastAPI()
        hub = progress.install(app, main, self.reconcile, self.lock)
        self.hubs.append(hub)
        request = AsyncMock()
        request.is_disconnected.return_value = False

        async def send(message):
            raise OSError('HTTP client disconnected before headers')

        with patch('backend.progress.connect', return_value=Socket()):
            response = await app.routes[-1].endpoint(job['id'], request)
            with self.assertRaises(ClientDisconnect):
                await response({'type': 'http', 'asgi': {'spec_version': '2.4'}}, AsyncMock(), send)
        self.assertNotIn(job['id'], hub.sessions)
        self.assertTrue(jobs.claim_watch(self.db, job['id'], 'replacement'))
        jobs.release_watch(self.db, job['id'], 'replacement')

    async def test_separate_worker_cannot_open_same_client_id_while_lease_is_active(self):
        job = self.job()
        socket = Socket()
        first, second = self.hub(), self.hub()
        with patch('backend.progress.connect', return_value=socket) as connect_mock:
            session, queue = await first.subscribe(job['id'])
            with self.assertRaises(Exception) as error:
                await second.subscribe(job['id'])
            self.assertEqual(error.exception.status_code, 429)
            await self.until(lambda: socket.opened)
            self.assertEqual(connect_mock.call_count, 1)
            await first.unsubscribe(session, queue)

    def test_watch_lease_expires_and_old_owner_cannot_release_new_owner(self):
        job = self.job()
        self.assertTrue(jobs.claim_watch(self.db, job['id'], 'old'))
        self.assertFalse(jobs.claim_watch(self.db, job['id'], 'new'))
        with closing(sqlite3.connect(self.db)) as db, db:
            db.execute('UPDATE settings SET value=? WHERE key=?',
                       (json.dumps({'owner': 'old', 'expires': (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat()}), 'watch:' + job['id']))
        self.assertTrue(jobs.claim_watch(self.db, job['id'], 'new'))
        jobs.release_watch(self.db, job['id'], 'old')
        self.assertFalse(jobs.claim_watch(self.db, job['id'], 'old'))
        jobs.release_watch(self.db, job['id'], 'new')
        self.assertTrue(jobs.claim_watch(self.db, job['id'], 'old'))

    async def test_reconcile_failure_keeps_original_job_and_does_not_submit(self):
        job = self.job()
        remote = AsyncMock()
        remote.__aenter__.return_value = remote
        remote.get.return_value = httpx.Response(200, request=httpx.Request('GET', 'http://test'), json={job['prompt_id']: {'status': None}})
        with patch('backend.submissions.httpx.AsyncClient', return_value=remote):
            result = self.client.post('/api/jobs/' + job['id'] + '/refresh')
        self.assertEqual(result.status_code, 503)
        self.assertEqual(jobs.get(self.db, job['id']), job)
        remote.post.assert_not_awaited()
