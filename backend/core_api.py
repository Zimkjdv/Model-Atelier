"""Core settings, catalog, drafts and assets bound to one AppContext."""

import asyncio
import platform
import shutil
import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from uuid import UUID

import httpx
import psutil
from fastapi import HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from starlette.concurrency import run_in_threadpool
from backend import assets, catalog, drafts, environment, execution_device, reference_workflows
from backend.schemas import Settings, ModelTarget, ModelMetadata, DraftInput, AssetUpdate


def install(app, host):
    catalog_lock = asyncio.Lock()

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError):
        # Raw invalid JSON numbers such as NaN cannot be echoed by a JSON response.
        return JSONResponse(
            status_code=422,
            content={
                'detail': [
                    {key: error[key] for key in ('type', 'loc', 'msg')} for error in exc.errors()
                ]
            },
        )

    @app.get('/api/settings')
    def settings():
        return {'comfy_url': host.engine_url()}

    @app.put('/api/settings')
    def save_settings(value: Settings):
        with closing(sqlite3.connect(host.DB)) as db, db:
            db.execute(
                'INSERT OR REPLACE INTO settings VALUES (?, ?)', ('comfy_url', value.comfy_url)
            )
        return value

    @app.get('/api/system')
    def system():
        cards, error = host.gpu_info()
        ram = psutil.virtual_memory()
        disk = shutil.disk_usage(host.DATA)
        return {
            'host': platform.node(),
            'role': '平台主機',
            'os': platform.platform(),
            'python': platform.python_version(),
            'updated_at': datetime.now(timezone.utc).isoformat(),
            'gpus': cards,
            'gpu_error': error,
            'ram': {'total': ram.total, 'used': ram.total - ram.available, 'free': ram.available},
            'disk': {
                'path': str(host.DATA),
                'total': disk.total,
                'used': disk.used,
                'free': disk.free,
            },
        }

    @app.get('/api/engine')
    async def engine():
        url = host.engine_url()
        device = execution_device.unknown(url)
        try:
            async with host.http_client(timeout=5, trust_env=False) as client:
                device = await execution_device.fetch(client, url)
                response = await client.get(url + '/system_stats')
                response.raise_for_status()
                stats = response.json()
            if (
                not isinstance(stats, dict)
                or not isinstance(stats.get('system'), dict)
                or not isinstance(stats.get('devices'), list)
            ):
                raise ValueError('回應不是 ComfyUI 系統資訊')
            diagnostics = environment.scoped_engine_diagnostics(stats, url, host.engine_url())
            result = {
                'connected': True,
                'url': url,
                'stats': environment.compatible_stats(stats),
                'diagnostics': diagnostics,
                'execution_device': execution_device.scoped(device, host.engine_url()),
            }
            if not diagnostics['matches_selected_engine']:
                result['error'] = '查詢期間引擎設定已變更，請重新整理'
            return result
        except httpx.HTTPError:
            return {
                'connected': False,
                'url': url,
                'error': '無法連接 ComfyUI，請確認服務已啟動且位址正確。',
                'execution_device': execution_device.scoped(device, host.engine_url()),
                'diagnostics': environment.scoped_engine_diagnostics(
                    None, url, host.engine_url(), status='offline'
                ),
            }
        except ValueError:
            return {
                'connected': False,
                'url': url,
                'error': 'ComfyUI 系統資訊格式無效，尚未確認引擎裝置。',
                'execution_device': execution_device.scoped(device, host.engine_url()),
                'diagnostics': environment.scoped_engine_diagnostics(
                    None, url, host.engine_url(), status='invalid'
                ),
            }

    @app.get('/api/health')
    def health():
        return {'status': 'ok'}

    def current_catalog(target):
        if target.engine_url != host.engine_url():
            raise HTTPException(409, '執行引擎已變更，請重新載入模型庫')
        value = catalog.read(host.DB, target.engine_url)
        model = next((item for item in value['models'] if item['name'] == target.name), None)
        if model is None:
            raise HTTPException(404, '模型未登記，請先同步清單')
        return value, model

    @app.get('/api/models')
    def models():
        return catalog.read(host.DB, host.engine_url())

    @app.post('/api/models/sync')
    async def sync_models():
        async with catalog_lock:
            url = host.engine_url()
            try:
                async with host.http_client(timeout=10, trust_env=False) as client:
                    response = await client.get(url + '/object_info/CheckpointLoaderSimple')
                    response.raise_for_status()
                    names = catalog.checkpoint_names(response.json())
            except (httpx.HTTPError, ValueError) as exc:
                message = (
                    str(exc)
                    if isinstance(exc, ValueError)
                    else '無法同步 ComfyUI，保留上次清單；請檢查連線後重試。'
                )
                return catalog.sync_error(host.DB, url, message)
            return catalog.merge(host.DB, url, names)

    @app.put('/api/models/metadata')
    async def model_metadata(target: ModelMetadata):
        async with catalog_lock:
            current_catalog(target)
            changes = target.model_dump(exclude_unset=True, exclude={'name', 'engine_url'})
            for field in ('version', 'license_name'):
                if field in changes:
                    changes[field] = changes[field].strip()
            return catalog.update_metadata(host.DB, target.engine_url, target.name, changes)

    @app.put('/api/models/selection')
    async def model_selection(target: ModelTarget):
        async with catalog_lock:
            current_catalog(target)
            try:
                return catalog.select(host.DB, target.engine_url, target.name)
            except ValueError as exc:
                raise HTTPException(409, str(exc))

    def draft_payload(value):
        payload = value.model_dump(mode='json', exclude={'revision'})
        payload['reference_ids'] = list(dict.fromkeys(payload['reference_ids']))
        entries = catalog.read(host.DB, value.engine_url)['models']
        item = next((item for item in entries if item['name'] == value.checkpoint), {})
        payload['model_version'] = item.get('version', '')
        return payload

    @app.get('/api/drafts')
    def list_drafts():
        # Supply the original generation defaults for old records without rewriting them.
        defaults = {
            name: DraftInput.model_fields[name].default
            for name in (
                'negative_prompt',
                'steps',
                'cfg',
                'sampler_name',
                'scheduler',
                'denoise',
                'workflow_mode',
                'image_asset_id',
                'reference_resize',
            )
        }
        return [dict(loras=[]) | defaults | item for item in drafts.list_all(host.DB)]

    @app.post('/api/drafts', status_code=201)
    def create_draft(value: DraftInput):
        try:
            return drafts.save(host.DB, draft_payload(value))
        except ValueError as exc:
            raise HTTPException(409, str(exc))

    @app.put('/api/drafts/{draft_id}')
    def update_draft(draft_id: str, value: DraftInput):
        try:
            return drafts.save(host.DB, draft_payload(value), draft_id, value.revision)
        except KeyError:
            raise HTTPException(404, '草稿不存在')
        except ValueError as exc:
            raise HTTPException(409, str(exc))

    @app.get('/api/assets')
    def list_assets():
        return assets.list_all(host.DB)

    @app.get('/api/assets/{asset_id}')
    def asset_detail(asset_id: UUID):
        try:
            return assets.get(host.DB, str(asset_id))
        except KeyError:
            raise HTTPException(404, '找不到素材')

    @app.post('/api/assets', status_code=201)
    async def upload_asset(request: Request, filename: str = '未命名素材'):
        chunks = bytearray()
        async for chunk in request.stream():
            if len(chunks) + len(chunk) > assets.MAX_BYTES:
                raise HTTPException(413, '圖片不可超過 20 MiB')
            chunks.extend(chunk)
        try:
            return await run_in_threadpool(
                assets.create, host.DB, host.DATA / 'assets', bytes(chunks), filename
            )
        except ValueError as exc:
            raise HTTPException(422, str(exc))

    @app.get('/api/assets/{asset_id}/image')
    def asset_image(asset_id: UUID):
        try:
            assets.get(host.DB, str(asset_id))
        except KeyError:
            raise HTTPException(404, '找不到素材')
        target = host.DATA / 'assets' / (str(asset_id) + '.png')
        if not target.is_file():
            raise HTTPException(404, '素材檔案已遺失')
        return FileResponse(
            target, media_type='image/png', headers={'X-Content-Type-Options': 'nosniff'}
        )

    @app.put('/api/assets/{asset_id}')
    def update_asset(asset_id: UUID, value: AssetUpdate):
        try:
            return assets.update(
                host.DB, str(asset_id), value.title, value.archived, value.purpose, value.revision
            )
        except KeyError:
            raise HTTPException(404, '找不到素材')
        except ValueError as exc:
            raise HTTPException(409, str(exc))

    @app.get('/api/assets/{asset_id}/usage')
    def asset_usage(asset_id: UUID):
        try:
            return assets.usage(host.DB, str(asset_id))
        except KeyError:
            raise HTTPException(404, '找不到素材')

    @app.get('/api/reference-workflows')
    def reference_capabilities():
        return reference_workflows.descriptions()

    host.engine = engine
    host.current_catalog = current_catalog
