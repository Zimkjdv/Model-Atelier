"""Bounded, allowlisted process diagnostics. No payloads, paths or raw errors."""
from collections import deque
import asyncio
from contextlib import asynccontextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
import math
import threading
import time
from urllib.parse import urlsplit
from uuid import UUID, uuid4

import httpx
from backend import failures

MAX_EVENTS = 500
MAX_BYTES = 256 * 1024
TTL = 24 * 60 * 60
STATES = {'validating', 'uploading_input', 'submitting', 'queued', 'running', 'unknown', 'completed', 'failed',
          'cancelling', 'cancel_unknown', 'cancelled', 'stopping', 'stop_unknown', 'stopped'}
TERMINAL = {'completed', 'failed', 'cancelled', 'stopped'}
WORKFLOWS = {'checkpoint-text2image-v1', 'checkpoint-image2image-v1', 'flux1-schnell-text2image-v1',
             'checkpoint-inpaint-v1', 'checkpoint-inpaint-feather-v2', 'checkpoint-canny-controlnet-v1',
             'checkpoint-canny-controlnet-edge-v2','checkpoint-structure-controlnet-v3','checkpoint-fooocus-inpaint-v3'}
STAGES = {'api_request', 'submission_new', 'submission_recovered', 'job_transition', 'observation_stale',
          'engine_submit', 'engine_history', 'engine_queue', 'engine_image', 'engine_preflight', 'engine_status',
          'engine_upload', 'engine_other'}
CLASSIFICATIONS = set(failures.TEXT) | {'none', 'conflict', 'invalid_request', 'not_found', 'request_failed',
    'internal_error', 'storage_unavailable', 'engine_rejected', 'submission_uncertain', 'outcome_unknown', 'cancelled'}
current = ContextVar('atelier_diagnostic_request', default=None)


def identifier(value):
    try:
        return str(UUID(str(value)))
    except (ValueError, TypeError, AttributeError):
        return None


def choice(value, values, default=None):
    return value if isinstance(value, str) and value in values else default


def timestamp(value):
    return datetime.fromtimestamp(value, timezone.utc).isoformat()


class Recorder:
    def __init__(self, *, max_events=MAX_EVENTS, max_bytes=MAX_BYTES, ttl=TTL, clock=time.time):
        self.max_events, self.max_bytes, self.ttl, self.clock = max_events, max_bytes, ttl, clock
        self.events, self.size, self.sequence = deque(), 0, 0
        self.lock = threading.RLock()
        self.engine_status = {'status': 'unknown', 'checked_at': None}

    def _prune(self):
        cutoff = self.clock() - self.ttl
        while self.events and (self.events[0][0] < cutoff or len(self.events) > self.max_events or self.size > self.max_bytes):
            _, size, _ = self.events.popleft()
            self.size -= size

    def add(self, stage, **fields):
        if stage not in STAGES:
            return
        with self.lock:
            self.sequence += 1
            now = self.clock()
            value = dict(sequence=self.sequence, timestamp=timestamp(now), stage=stage,
                         request_id=identifier(fields.get('request_id')), job_id=identifier(fields.get('job_id')),
                         workflow=choice(fields.get('workflow'), WORKFLOWS, 'unknown'))
            for name, allowed in [('state', STATES), ('attempted_state', STATES), ('classification', CLASSIFICATIONS),
                                  ('outcome', {'persisted', 'ignored_stale', 'recovered', 'observed'}),
                                  ('method', {'GET', 'POST', 'PUT', 'PATCH', 'DELETE', 'HEAD', 'OPTIONS'})]:
                if (safe := choice(fields.get(name), allowed)) is not None:
                    value[name] = safe
            duration = fields.get('duration_ms')
            if type(duration) in (int, float) and math.isfinite(duration):
                value['duration_ms'] = round(min(86400000, max(0, duration)), 2)
            status = fields.get('status_code')
            if type(status) is int and 100 <= status <= 599:
                value['status_code'] = status
            # Routes are supplied only from FastAPI's matched template, never URL input.
            if isinstance(fields.get('route'), str):
                value['route'] = fields['route'][:256]
            if 'state' in value:
                value['terminal'] = value['state'] in TERMINAL
            size = len(json.dumps(value, ensure_ascii=True).encode())
            self.events.append((now, size, value)); self.size += size
            self._prune()

    def snapshot(self, job_id=None, request_id=None):
        with self.lock:
            self._prune()
            values = [dict(value) for _, _, value in self.events
                      if (job_id is None or value['job_id'] == job_id) and (request_id is None or value['request_id'] == request_id)]
            return dict(schema_version=1, generated_at=timestamp(self.clock()),
                        retention=dict(scope='current_process_memory', max_events=self.max_events,
                                       max_bytes=self.max_bytes, ttl_seconds=self.ttl, retained_bytes=self.size),
                        events=values)


@dataclass
class RequestTrace:
    recorder: Recorder
    request_id: str = field(default_factory=lambda: str(uuid4()))
    started: float = field(default_factory=time.monotonic)
    job_id: str | None = None
    workflow: str = 'unknown'
    classification: str = 'none'


def bind_submission(job_id, workflow=None):
    if trace := current.get():
        trace.job_id = identifier(job_id)
        trace.workflow = choice(workflow, WORKFLOWS, trace.workflow)


def bind_job(job):
    if trace := current.get():
        trace.job_id = identifier(job.get('id'))
        trace.workflow = choice(job.get('workflow_id') or 'checkpoint-text2image-v1', WORKFLOWS, 'unknown')


def record_job(stage, job, *, attempted_state=None, previous_state=None):
    trace = current.get()
    if trace is None:
        return
    bind_job(job)
    failure = job.get('failure_info')
    classification = choice(failure.get('code') if isinstance(failure, dict) else None, CLASSIFICATIONS, 'none')
    if job.get('status') == 'unknown':
        classification = 'submission_uncertain' if previous_state == 'submitting' else 'outcome_unknown'
    if stage == 'job_transition':
        trace.classification = classification
    trace.recorder.add(stage, request_id=trace.request_id, job_id=trace.job_id, workflow=trace.workflow,
        state=job.get('status'), attempted_state=attempted_state, classification=classification,
        duration_ms=(time.monotonic() - trace.started) * 1000,
        outcome='ignored_stale' if stage == 'observation_stale' else 'recovered' if stage == 'submission_recovered' else 'persisted')


def exception_class(exc, stage=''):
    import sqlite3
    if isinstance(exc, (asyncio.CancelledError, GeneratorExit, BrokenPipeError, ConnectionResetError)):
        return 'cancelled'
    if isinstance(exc, httpx.HTTPStatusError):
        return 'engine_rejected'
    if isinstance(exc, (sqlite3.Error, OSError)) and not isinstance(exc, httpx.HTTPError):
        return 'storage_unavailable'
    if isinstance(exc, httpx.RequestError):
        return 'submission_uncertain' if stage == 'engine_submit' else 'engine_offline'
    return 'internal_error'


def engine_stage(url):
    path = urlsplit(str(url)).path
    if path.endswith('/prompt'): return 'engine_submit'
    if '/history/' in path: return 'engine_history'
    if path.endswith('/queue'): return 'engine_queue'
    if path.endswith('/view'): return 'engine_image'
    if '/object_info' in path: return 'engine_preflight'
    if path.endswith(('/system_stats', '/execution-device')): return 'engine_status'
    if '/upload/' in path: return 'engine_upload'
    return 'engine_other'


class EngineClient:
    """Preserve injected clients/timeouts, adding only metadata around existing calls."""
    def __init__(self, client):
        self.manager = client

    async def __aenter__(self):
        self.client = await self.manager.__aenter__()
        return self

    async def __aexit__(self, *args):
        return await self.manager.__aexit__(*args)

    def event(self, stage, method, started, response, classification):
        if trace := current.get():
            trace.recorder.add(stage, request_id=trace.request_id, job_id=trace.job_id, workflow=trace.workflow,
                method=method, duration_ms=(time.monotonic() - started) * 1000,
                status_code=getattr(response, 'status_code', None), classification=classification)

    async def call(self, method, url, **options):
        started, stage, response, classification = time.monotonic(), engine_stage(url), None, 'none'
        try:
            response = await getattr(self.client, method.lower())(url, **options)
            if isinstance(response.status_code, int) and response.status_code >= 400:
                classification = 'engine_rejected'
            return response
        except BaseException as exc:
            classification = exception_class(exc, stage)
            raise
        finally:
            self.event(stage, method, started, response, classification)

    async def get(self, url, **options): return await self.call('GET', url, **options)
    async def post(self, url, **options): return await self.call('POST', url, **options)

    @asynccontextmanager
    async def stream(self, method, url, **options):
        started, stage, response, classification = time.monotonic(), engine_stage(url), None, 'none'
        try:
            async with self.client.stream(method, url, **options) as response:
                if isinstance(response.status_code, int) and response.status_code >= 400:
                    classification = 'engine_rejected'
                yield response
        except BaseException as exc:
            classification = exception_class(exc, stage)
            raise
        finally:
            self.event(stage, method, started, response, classification)


class DiagnosticsMiddleware:
    def __init__(self, app, recorder):
        self.app, self.recorder = app, recorder

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http' or not scope['path'].startswith('/api/'):
            return await self.app(scope, receive, send)
        trace = RequestTrace(self.recorder)
        scope['atelier_request_id'] = trace.request_id
        token, status = current.set(trace), 500
        async def traced_send(message):
            nonlocal status
            if message['type'] == 'http.response.start':
                status = message['status']
                message = dict(message, headers=[*(item for item in message.get('headers', []) if item[0].lower() != b'x-request-id'), (b'x-request-id', trace.request_id.encode())])
            await send(message)
        try:
            await self.app(scope, receive, traced_send)
        except BaseException as exc:
            trace.classification = exception_class(exc)
            raise
        finally:
            route = getattr(scope.get('route'), 'path', 'unmatched')
            if not scope['path'].startswith(('/api/diagnostics', '/api/status')):
                status_class = {409: 'conflict', 422: 'invalid_request', 404: 'not_found'}.get(status)
                classification = status_class or trace.classification
                if classification == 'none' and status >= 400:
                    classification = 'internal_error' if status >= 500 else 'request_failed'
                job_id = trace.job_id or identifier(scope.get('path_params', {}).get('job_id'))
                self.recorder.add('api_request', request_id=trace.request_id, job_id=job_id, workflow=trace.workflow,
                    route=route, method=scope['method'], status_code=status, classification=classification,
                    duration_ms=(time.monotonic() - trace.started) * 1000)
            current.reset(token)
