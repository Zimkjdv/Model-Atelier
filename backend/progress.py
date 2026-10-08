"""Bounded SSE fanout for a job's original ComfyUI WebSocket session.

Progress is per node, never an overall completion estimate. Upstream events are
untrusted hints; only history reconciliation can establish success or failure.
"""
import asyncio
import json
import math
import time
import anyio
from dataclasses import dataclass, field
from datetime import datetime, timezone
from urllib.parse import urlencode, urlsplit, urlunsplit
from uuid import UUID, uuid4

from fastapi import HTTPException, Request
from fastapi.responses import StreamingResponse
from websockets.asyncio.client import connect
from websockets.exceptions import WebSocketException

from backend import cancellation, jobs

MAX_MESSAGE = 1024 * 1024
MAX_LISTENERS = 8
MAX_SESSIONS = 16
HEARTBEAT = 2.0
POLL_INTERVAL = 10.0
DB_INTERVAL = 1.0
SEND_INTERVAL = 0.2
MAX_CONNECTIONS = 3
FALLBACK_POLLS = 3
END = object()
ELIGIBLE = {'queued', 'running', 'unknown'}


def summary(job):
    keys = ('id', 'prompt_id', 'engine_url', 'checkpoint', 'model_version',
            'status', 'error', 'failure_info', 'revision', 'created_at', 'updated_at', 'progress',
            'lora_metadata', 'preflight_warnings', 'runtime_metadata', 'measurements')
    value = {key: job[key] for key in keys if key in job}
    value.update({key: job[key] for key in ('workflow_id', 'component_metadata', 'reference_metadata') if job.get(key) is not None})
    return value


def frame(event, value):
    return 'event: ' + event + '\ndata: ' + json.dumps(value, ensure_ascii=False, allow_nan=False) + '\n\n'


def socket_url(job):
    parsed = urlsplit(job['engine_url'])
    return urlunsplit(('wss' if parsed.scheme == 'https' else 'ws', parsed.netloc,
                      parsed.path.rstrip('/') + '/ws', urlencode({'clientId': job['id']}), ''))


def parse_event(raw, job):
    """Drop previews, global state, missing identity, unknown nodes and bad numbers."""
    if not isinstance(raw, str):
        return None
    try:
        if len(raw.encode('utf-8')) > MAX_MESSAGE:
            return None
        value = json.loads(raw)
    except (ValueError, TypeError, RecursionError, UnicodeError):
        return None
    if not isinstance(value, dict) or not isinstance(value.get('data'), dict):
        return None
    kind, data = value.get('type'), value['data']
    if data.get('prompt_id') != job['prompt_id']:
        return None
    if kind in ('execution_success', 'execution_error', 'execution_interrupted'):
        return ('reconcile', None)
    if kind == 'executing' and data.get('node') is None:
        return ('reconcile', None)
    if kind not in ('progress', 'executing'):
        return None
    node = data.get('node')
    if not isinstance(node, str) or len(node) > 128 or node not in job['workflow']:
        return None
    progress = dict(node=node, current=None, max=None, percent=None,
                    updated_at=datetime.now(timezone.utc).isoformat())
    if kind == 'progress':
        current, maximum = data.get('value'), data.get('max')
        if (type(current) not in (int, float) or type(maximum) not in (int, float) or
                not 0 < maximum <= 1_000_000_000 or not 0 <= current <= maximum or
                not math.isfinite(current) or not math.isfinite(maximum)):
            return None
        progress.update(current=current, max=maximum, percent=round(current / maximum * 100, 2))
    return ('progress', progress)


def put_latest(queue, item):
    if queue.full():
        queue.get_nowait()
    queue.put_nowait(item)


@dataclass
class Session:
    job_id: str
    owner: str
    listeners: set = field(default_factory=set)
    task: asyncio.Task | None = None
    stop: asyncio.Event = field(default_factory=asyncio.Event)
    last_db: float = -math.inf
    last_send: float = -math.inf
    last_poll: float = -math.inf
    last_renew: float = -math.inf
    last_summary: dict | None = None
    last_connection: dict | None = None


class Hub:
    def __init__(self, host, reconcile, job_lock):
        self.host = host
        self.reconcile = reconcile
        self.job_lock = job_lock
        self.sessions = {}
        self.registry_lock = asyncio.Lock()

    def broadcast(self, session, event, value):
        if event == 'job':
            session.last_summary = value['job']
        elif event == 'connection':
            session.last_connection = value
        message = frame(event, value)
        for queue in tuple(session.listeners):
            put_latest(queue, message)

    def publish(self, session, job, live_progress=False):
        value = summary(job)
        if (not live_progress and session.last_summary and
                value.get('revision') == session.last_summary.get('revision') and
                value['status'] == session.last_summary['status']):
            return  # Do not replace newer streamed progress with the throttled DB copy.
        if value != session.last_summary:
            self.broadcast(session, 'job', {'job': value})

    async def subscribe(self, job_id):
        try:
            job = jobs.get(self.host.DB, job_id)
        except KeyError:
            raise HTTPException(404, '找不到任務')
        queue = asyncio.Queue(maxsize=16)
        async with self.registry_lock:
            session = self.sessions.get(job_id)
            if session is not None and session.task.done():
                self.sessions.pop(job_id)
                session = None
            if session is None:
                if len(self.sessions) >= MAX_SESSIONS:
                    raise HTTPException(429, '即時進度連線數已達上限，請稍後重新連線或手動刷新')
                session = Session(job_id, str(uuid4()))
                if job['status'] not in cancellation.TERMINAL:
                    if not jobs.claim_watch(self.host.DB, job_id, session.owner):
                        raise HTTPException(429, '此任務已有另一個平台程序監聽進度，請使用原連線或手動刷新')
                self.sessions[job_id] = session
                session.listeners.add(queue)
                self.publish(session, job)
                session.task = asyncio.create_task(self.run(session))
            else:
                if len(session.listeners) >= MAX_LISTENERS:
                    raise HTTPException(429, '此任務的即時進度瀏覽器連線已達上限，請稍後重試')
                session.listeners.add(queue)
                put_latest(queue, frame('job', {'job': summary(job)}))
                if session.last_connection:
                    put_latest(queue, frame('connection', session.last_connection))
        return session, queue

    async def unsubscribe(self, session, queue):
        # Keep the old session registered until its upstream socket fully closes:
        # ComfyUI uses clientId as a singleton, and an old socket's finalizer can
        # otherwise unregister the replacement socket opened with the same ID.
        async with self.registry_lock:
            session.listeners.discard(queue)
            if session.listeners:
                return
            session.stop.set()
            if session.task and not session.task.done():
                session.task.cancel()
                await asyncio.gather(session.task, return_exceptions=True)
            if self.sessions.get(session.job_id) is session:
                self.sessions.pop(session.job_id)
            jobs.release_watch(self.host.DB, session.job_id, session.owner)

    async def stream(self, session, queue, request):
        try:
            while not await request.is_disconnected():
                try:
                    item = await asyncio.wait_for(queue.get(), HEARTBEAT)
                except TimeoutError:
                    yield ': heartbeat\n\n'
                    continue
                if item is END:
                    break
                yield item
        finally:
            # Starlette uses an AnyIO cancellation scope on HTTP disconnect.
            # Shield cleanup so closing the upstream and registry/lease removal
            # cannot itself be repeatedly cancelled by that scope.
            with anyio.CancelScope(shield=True):
                await self.unsubscribe(session, queue)

    def renew(self, session):
        if time.monotonic() - session.last_renew < 20:
            return
        if not jobs.claim_watch(self.host.DB, session.job_id, session.owner):
            raise RuntimeError('progress reader ownership changed')
        session.last_renew = time.monotonic()

    async def observe(self, session):
        self.renew(session)
        try:
            # Shared with submission/cancellation so network reconciliation cannot
            # race a local cancel; its CAS still protects against other workers.
            job = await self.reconcile(UUID(session.job_id))
        except HTTPException:
            job = jobs.get(self.host.DB, session.job_id)
        session.last_poll = time.monotonic()
        self.publish(session, job)
        return job

    async def update_progress(self, session, value):
        async with self.job_lock(session.job_id):
            job = jobs.get(self.host.DB, session.job_id)
            if job['status'] not in ELIGIBLE:
                self.publish(session, job)
                return
            previous = job.get('progress')
            if value['max'] is None and previous and previous.get('node') == value['node']:
                return
            candidate = job | {'status': 'running', 'error': None, 'progress': value}
            if time.monotonic() - session.last_db >= DB_INTERVAL:
                candidate, changed = jobs.compare_update(self.host.DB, job, status='running', error=None, progress=value)
                if changed:
                    session.last_db = time.monotonic()
            if time.monotonic() - session.last_send >= SEND_INTERVAL:
                self.publish(session, candidate, live_progress=True)
                session.last_send = time.monotonic()

    async def pause(self, session, seconds):
        deadline = time.monotonic() + seconds
        while not session.stop.is_set() and time.monotonic() < deadline:
            job = jobs.get(self.host.DB, session.job_id)
            self.publish(session, job)
            if job['status'] in cancellation.TERMINAL:
                return True
            self.renew(session)
            try:
                await asyncio.wait_for(session.stop.wait(), min(HEARTBEAT, max(0.001, deadline - time.monotonic())))
            except TimeoutError:
                pass
        return session.stop.is_set()

    async def run(self, session):
        try:
            for attempt in range(MAX_CONNECTIONS):
                job = jobs.get(self.host.DB, session.job_id)
                self.publish(session, job)
                if job['status'] in cancellation.TERMINAL or session.stop.is_set():
                    return
                self.renew(session)
                try:
                    # No proxy/environment routing; pinned original engine only.
                    async with connect(socket_url(job), proxy=None, max_size=MAX_MESSAGE, max_queue=16,
                                       open_timeout=5, close_timeout=2, ping_interval=20, ping_timeout=20) as websocket:
                        self.broadcast(session, 'connection', {'state': 'connected'})
                        job = await self.observe(session)  # Connect first, then recover any missed final state.
                        if job['status'] in cancellation.TERMINAL:
                            return
                        while not session.stop.is_set():
                            self.renew(session)
                            try:
                                raw = await asyncio.wait_for(websocket.recv(), HEARTBEAT)
                            except TimeoutError:
                                raw = None
                            job = jobs.get(self.host.DB, session.job_id)
                            self.publish(session, job)
                            if job['status'] in cancellation.TERMINAL:
                                return
                            parsed = parse_event(raw, job) if raw is not None else None
                            if parsed:
                                if parsed[0] == 'progress':
                                    await self.update_progress(session, parsed[1])
                                elif time.monotonic() - session.last_poll >= DB_INTERVAL:
                                    job = await self.observe(session)
                            if time.monotonic() - session.last_poll >= POLL_INTERVAL:
                                job = await self.observe(session)
                            if job['status'] in cancellation.TERMINAL:
                                return
                            # Bounds both malformed-message floods and local fanout;
                            # slow clients retain at most the latest 16 small frames.
                            if raw is not None:
                                await asyncio.sleep(0.01)
                except (WebSocketException, OSError, TimeoutError):
                    self.broadcast(session, 'connection', {'state': 'reconnecting', 'message': '即時連線中斷，正在確認原引擎任務狀態'})
                    job = await self.observe(session)
                    if job['status'] in cancellation.TERMINAL:
                        return
                    if await self.pause(session, min(2 ** attempt, 4)):
                        return
            self.broadcast(session, 'connection', {'state': 'offline', 'message': '即時連線暫不可用，正在低頻查詢；可手動刷新原任務'})
            for _ in range(FALLBACK_POLLS):
                if await self.pause(session, POLL_INTERVAL):
                    return
                if (await self.observe(session))['status'] in cancellation.TERMINAL:
                    return
            self.broadcast(session, 'connection', {'state': 'offline', 'message': '即時監聽已停止，請手動刷新或重新連線；不會重新提交任務'})
        except (RuntimeError, KeyError):
            self.broadcast(session, 'connection', {'state': 'offline', 'message': '即時監聽已停止，請重新查詢任務'})
        finally:
            jobs.release_watch(self.host.DB, session.job_id, session.owner)
            for queue in tuple(session.listeners):
                put_latest(queue, END)


def install(app, host, reconcile, job_lock):
    hub = Hub(host, reconcile, job_lock)

    class EventResponse(StreamingResponse):
        async def __call__(self, scope, receive, send):
            try:
                await super().__call__(scope, receive, send)
            finally:
                # Also covers a disconnect while response headers are sent,
                # before the streaming generator has ever started.
                with anyio.CancelScope(shield=True):
                    await hub.unsubscribe(self.session, self.queue)

    @app.get('/api/jobs/{job_id}/events')
    async def events(job_id: UUID, request: Request):
        session, queue = await hub.subscribe(str(job_id))
        response = EventResponse(hub.stream(session, queue, request), media_type='text/event-stream',
                                 headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'})
        response.session, response.queue = session, queue
        return response

    return hub
