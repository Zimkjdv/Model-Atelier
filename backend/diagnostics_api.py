"""Read-only readiness and previewable, sanitized diagnostic exports."""
from contextlib import closing
import os
import sqlite3
import time
from uuid import UUID

import httpx
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool
from backend.diagnostics import DiagnosticsMiddleware, current, timestamp


def data_status(host):
    try:
        with os.scandir(host.DATA) as entries:
            next(entries, None)
        for folder in ('assets', 'artworks', 'job_inputs', 'control_edges'):
            path = host.DATA / folder
            if path.exists():
                with os.scandir(path) as entries:
                    next(entries, None)
        with closing(sqlite3.connect(host.DB.as_uri() + '?mode=ro', uri=True, timeout=.2)) as db:
            db.execute('SELECT key FROM settings LIMIT 1').fetchone()
        return {'status': 'readable', 'write_status': 'not_tested', 'integrity': 'not_scanned'}
    except (sqlite3.Error, OSError, ValueError):
        return {'status': 'unavailable', 'write_status': 'not_tested', 'integrity': 'not_scanned'}


def install(app, host):
    app.add_middleware(DiagnosticsMiddleware, recorder=host.diagnostics)

    async def storage_error(request, exc):
        if trace := current.get():
            trace.classification = 'storage_unavailable'
        return JSONResponse(status_code=503, content={'detail': '本機資料無法讀寫；請保留原請求 ID，檢查儲存空間與存取權限，再查詢原任務。'},
                            headers={'X-Request-ID': request.scope.get('atelier_request_id', '')})
    app.add_exception_handler(sqlite3.Error, storage_error)
    app.add_exception_handler(OSError, storage_error)

    def readiness(data):
        engine = dict(host.diagnostics.engine_status)
        if engine.get('observed_at', 0) < time.time() - 60:
            engine['status'] = 'unknown'
        engine.pop('observed_at', None)
        return dict(checked_at=timestamp(time.time()), service={'status': 'alive'}, data=data, engine=engine)

    @app.get('/api/status')
    async def status(probe_engine: bool = False):
        data = await run_in_threadpool(data_status, host)
        if probe_engine:
            engine = {'status': 'unknown', 'checked_at': timestamp(time.time()), 'observed_at': time.time()}
            if data['status'] == 'readable':
                try:
                    url = host.engine_url()
                    async with host.http_client(timeout=3, trust_env=False) as client:
                        response = await client.get(url + '/system_stats')
                        response.raise_for_status()
                        stats = response.json()
                    engine['status'] = 'connected' if isinstance(stats, dict) and isinstance(stats.get('system'), dict) and isinstance(stats.get('devices'), list) else 'invalid'
                    if host.engine_url() != url:
                        engine['status'] = 'unknown'
                except httpx.HTTPError:
                    engine['status'] = 'offline'
                except ValueError:
                    engine['status'] = 'invalid'
                except (sqlite3.Error, OSError):
                    data = {'status': 'unavailable', 'write_status': 'not_tested', 'integrity': 'not_scanned'}
            with host.diagnostics.lock:
                host.diagnostics.engine_status = engine
        return readiness(data)

    @app.get('/api/diagnostics')
    async def preview(job_id: UUID | None = None, request_id: UUID | None = None):
        # No task reads, history refresh, POST, file writes or inference.
        result = host.diagnostics.snapshot(str(job_id) if job_id else None, str(request_id) if request_id else None)
        result['readiness'] = readiness(await run_in_threadpool(data_status, host))
        result['privacy'] = {'payloads': False, 'images': False, 'workflows': False, 'credentials': False, 'personal_paths': False}
        return JSONResponse(result, headers={'Cache-Control': 'no-store'})
