import csv
import asyncio
import io
import math
import os
import platform
import shutil
import sqlite3
import subprocess
import sys
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit
from typing import Literal

import httpx
import psutil
from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from starlette.concurrency import run_in_threadpool
from uuid import UUID
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator
from backend import catalog, drafts, assets, submissions, gallery_api, model_profiles, model_paths, environment, validation_records, generation_advice, storage, loras, lora_compatibility, lora_validation
from backend.lora_settings import LoraSetting
from backend import flux_plan, flux_catalog
from backend import reference_workflows, settings_transfer, stack_validation

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'data'
DATA.mkdir(exist_ok=True)
DB = DATA / 'atelier.sqlite3'
with closing(sqlite3.connect(DB)) as db, db:
    db.execute('CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL)')

app = FastAPI(title='Model Atelier', version='0.1.0')
catalog_lock = asyncio.Lock()


@app.exception_handler(RequestValidationError)
async def validation_error(request: Request, exc: RequestValidationError):
    # Raw invalid JSON numbers such as NaN cannot be echoed by a JSON response.
    return JSONResponse(status_code=422, content={'detail': [
        {key: error[key] for key in ('type', 'loc', 'msg')} for error in exc.errors()]})


def engine_url():
    with closing(sqlite3.connect(DB)) as db:
        row = db.execute("SELECT value FROM settings WHERE key='comfy_url'").fetchone()
    return row[0] if row else 'http://127.0.0.1:8188'


class Settings(BaseModel):
    comfy_url: str

    @field_validator('comfy_url')
    @classmethod
    def validate_url(cls, value):
        value = value.strip().rstrip('/')
        parsed = urlsplit(value)
        if parsed.scheme not in ('http', 'https') or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ValueError('請使用不含帳密、查詢參數的 HTTP 或 HTTPS 位址')
        try:
            parsed.port
        except ValueError as exc:
            raise ValueError('連接埠無效') from exc
        return value


@app.get('/api/settings')
def settings():
    return {'comfy_url': engine_url()}


@app.put('/api/settings')
def save_settings(value: Settings):
    with closing(sqlite3.connect(DB)) as db, db:
        db.execute('INSERT OR REPLACE INTO settings VALUES (?, ?)', ('comfy_url', value.comfy_url))
    return value


def gpu_info():
    try:
        result = subprocess.run(
            ['nvidia-smi', '--query-gpu=index,name,memory.total,memory.used,memory.free,driver_version', '--format=csv,noheader,nounits'],
            capture_output=True, text=True, timeout=5,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0,
        )
        if result.returncode:
            return [], '無法取得 NVIDIA 資訊，請檢查驅動與裝置狀態'
        cards = []
        for row in csv.reader(io.StringIO(result.stdout), skipinitialspace=True):
            if len(row) != 6:
                continue
            def memory(value):
                try:
                    amount = float(value)
                    return int(amount * 1024 * 1024) if math.isfinite(amount) and amount >= 0 and amount * 1024 * 1024 <= environment.MAX_NUMBER else None
                except (ValueError, OverflowError):
                    return None
            total, used, free = (memory(value) for value in row[2:5])
            total = total if total is not None and total > 0 else None
            used = used if used is not None and (total is None or used <= total) else None
            free = free if free is not None and (total is None or free <= total) else None
            cards.append(dict(index=row[0], name=environment.text(row[1]), total=total, used=used, free=free,
                              driver=environment.text(row[5], 80)))
        return cards, None if cards else '未偵測到 NVIDIA GPU'
    except (OSError, subprocess.TimeoutExpired):
        return [], '無法取得 NVIDIA 資訊：nvidia-smi 不可用或查詢逾時'


@app.get('/api/system')
def system():
    cards, error = gpu_info()
    ram = psutil.virtual_memory()
    disk = shutil.disk_usage(DATA)
    return {
        'host': platform.node(), 'role': '平台主機', 'os': platform.platform(),
        'python': platform.python_version(), 'updated_at': datetime.now(timezone.utc).isoformat(),
        'gpus': cards, 'gpu_error': error,
        'ram': {'total': ram.total, 'used': ram.total - ram.available, 'free': ram.available},
        'disk': {'path': str(DATA), 'total': disk.total, 'used': disk.used, 'free': disk.free},
    }


@app.get('/api/engine')
async def engine():
    url = engine_url()
    try:
        async with httpx.AsyncClient(timeout=5, trust_env=False) as client:
            response = await client.get(url + '/system_stats')
            response.raise_for_status()
            stats = response.json()
        if not isinstance(stats, dict) or not isinstance(stats.get('system'), dict) or not isinstance(stats.get('devices'), list):
            raise ValueError('回應不是 ComfyUI 系統資訊')
        diagnostics = environment.scoped_engine_diagnostics(stats, url, engine_url())
        result = {'connected': True, 'url': url, 'stats': environment.compatible_stats(stats), 'diagnostics': diagnostics}
        if not diagnostics['matches_selected_engine']:
            result['error'] = '查詢期間引擎設定已變更，請重新整理'
        return result
    except httpx.HTTPError:
        return {'connected': False, 'url': url, 'error': '無法連接 ComfyUI，請確認服務已啟動且位址正確。',
                'diagnostics': environment.scoped_engine_diagnostics(None, url, engine_url(), status='offline')}
    except ValueError:
        return {'connected': False, 'url': url, 'error': 'ComfyUI 系統資訊格式無效，尚未確認引擎裝置。',
                'diagnostics': environment.scoped_engine_diagnostics(None, url, engine_url(), status='invalid')}


@app.get('/api/health')
def health():
    return {'status': 'ok'}


class ModelTarget(BaseModel):
    engine_url: str
    name: str = Field(min_length=1, max_length=2048)


class ModelMetadata(ModelTarget):
    version: str = Field(default='', max_length=100)
    notes: str = Field(default='', max_length=4000)
    source_url: str = Field(default='', max_length=2048)
    architecture: Literal['unknown', 'sd1', 'sdxl', 'sd3', 'flux', 'other'] = 'unknown'
    size_bytes: int | None = Field(default=None, strict=True, gt=0, le=9007199254740991)
    sha256: str = Field(default='', max_length=64, pattern=r'^(?:[0-9a-f]{64})?$')
    license_name: str = Field(default='', max_length=200)
    license_url: str = Field(default='', max_length=2048)

    @field_validator('version', 'notes', 'source_url', 'sha256', 'license_name', 'license_url', mode='before')
    @classmethod
    def clear_nullable_text(cls, value):
        return '' if value is None else value

    @field_validator('architecture', mode='before')
    @classmethod
    def clear_architecture(cls, value):
        return 'unknown' if value is None or value == '' else value

    @field_validator('size_bytes', mode='before')
    @classmethod
    def clear_size(cls, value):
        return None if isinstance(value, str) and value == '' else value

    @field_validator('sha256', mode='before')
    @classmethod
    def normalize_checksum(cls, value):
        return value.strip().lower() if isinstance(value, str) else value

    @field_validator('source_url', 'license_url')
    @classmethod
    def validate_source(cls, value):
        return Settings.validate_url(value) if value.strip() else ''


def current_catalog(target):
    if target.engine_url != engine_url():
        raise HTTPException(409, '執行引擎已變更，請重新載入模型庫')
    value = catalog.read(DB, target.engine_url)
    model = next((item for item in value['models'] if item['name'] == target.name), None)
    if model is None:
        raise HTTPException(404, '模型未登記，請先同步清單')
    return value, model


@app.get('/api/models')
def models():
    return catalog.read(DB, engine_url())


@app.post('/api/models/sync')
async def sync_models():
    async with catalog_lock:
        url = engine_url()
        try:
            async with httpx.AsyncClient(timeout=10, trust_env=False) as client:
                response = await client.get(url + '/object_info/CheckpointLoaderSimple')
                response.raise_for_status()
                names = catalog.checkpoint_names(response.json())
        except (httpx.HTTPError, ValueError) as exc:
            message = (str(exc) if isinstance(exc, ValueError)
                       else '無法同步 ComfyUI，保留上次清單；請檢查連線後重試。')
            return catalog.sync_error(DB, url, message)
        return catalog.merge(DB, url, names)


@app.put('/api/models/metadata')
async def model_metadata(target: ModelMetadata):
    async with catalog_lock:
        current_catalog(target)
        changes = target.model_dump(exclude_unset=True, exclude={'name', 'engine_url'})
        for field in ('version', 'license_name'):
            if field in changes:
                changes[field] = changes[field].strip()
        return catalog.update_metadata(DB, target.engine_url, target.name, changes)


@app.put('/api/models/selection')
async def model_selection(target: ModelTarget):
    async with catalog_lock:
        current_catalog(target)
        try:
            return catalog.select(DB, target.engine_url, target.name)
        except ValueError as exc:
            raise HTTPException(409, str(exc))


class DraftInput(BaseModel):
    workflow_mode: Literal['text2image', 'image2image'] = 'text2image'
    image_asset_id: UUID | None = None
    reference_resize: Literal['fit', 'stretch'] = 'fit'
    loras: list[LoraSetting] = Field(default_factory=list, max_length=4)
    reference_ids: list[UUID] = Field(default_factory=list, max_length=8)
    title: str = Field(min_length=1, max_length=100)
    prompt: str = Field(default='', max_length=20000)
    negative_prompt: str = Field(default='', max_length=20000)
    engine_url: str
    checkpoint: str = Field(default='', max_length=2048)
    width: int = Field(default=1024, ge=64, le=8192, multiple_of=8, strict=True)
    height: int = Field(default=1024, ge=64, le=8192, multiple_of=8, strict=True)
    seed: str = '0'
    steps: int = Field(default=20, ge=1, le=150, strict=True)
    cfg: float = Field(default=7.0, ge=0, le=30, strict=True, allow_inf_nan=False)
    sampler_name: str = Field(default='euler', min_length=1, max_length=64, pattern=r'^[a-z][a-z0-9_]*$')
    scheduler: str = Field(default='normal', min_length=1, max_length=64, pattern=r'^[a-z][a-z0-9_]*$')
    denoise: float = Field(default=1.0, ge=0, le=1, strict=True, allow_inf_nan=False)
    revision: int | None = Field(default=None, ge=1)

    @field_validator('loras')
    @classmethod
    def unique_loras(cls, value):
        if len({item.name for item in value}) != len(value):
            raise ValueError('同一 LoRA 不可重複選取')
        return value

    @field_validator('title')
    @classmethod
    def title_not_blank(cls, value):
        if not value.strip():
            raise ValueError('草稿名稱不可空白')
        return value.strip()

    @field_validator('engine_url')
    @classmethod
    def draft_url(cls, value):
        return Settings.validate_url(value)

    @field_validator('seed')
    @classmethod
    def seed_valid(cls, value):
        if not value.isascii() or not value.isdigit() or len(value) > 20 or int(value) > 18446744073709551615:
            raise ValueError('Seed 必須是 0 至 18446744073709551615 的整數')
        return str(int(value))


def draft_payload(value):
    payload = value.model_dump(mode='json', exclude={'revision'})
    payload['reference_ids'] = list(dict.fromkeys(payload['reference_ids']))
    entries = catalog.read(DB, value.engine_url)['models']
    item = next((item for item in entries if item['name'] == value.checkpoint), {})
    payload['model_version'] = item.get('version', '')
    return payload


@app.get('/api/drafts')
def list_drafts():
    # Supply the original generation defaults for old records without rewriting them.
    defaults = {name: DraftInput.model_fields[name].default for name in
                ('negative_prompt', 'steps', 'cfg', 'sampler_name', 'scheduler', 'denoise', 'workflow_mode', 'image_asset_id', 'reference_resize')}
    return [dict(loras=[]) | defaults | item for item in drafts.list_all(DB)]


@app.post('/api/drafts', status_code=201)
def create_draft(value: DraftInput):
    try:
        return drafts.save(DB, draft_payload(value))
    except ValueError as exc:
        raise HTTPException(409, str(exc))


@app.put('/api/drafts/{draft_id}')
def update_draft(draft_id: str, value: DraftInput):
    try:
        return drafts.save(DB, draft_payload(value), draft_id, value.revision)
    except KeyError:
        raise HTTPException(404, '草稿不存在')
    except ValueError as exc:
        raise HTTPException(409, str(exc))


@app.get('/api/assets')
def list_assets():
    return assets.list_all(DB)


@app.post('/api/assets', status_code=201)
async def upload_asset(request: Request, filename: str = '未命名素材'):
    chunks = bytearray()
    async for chunk in request.stream():
        if len(chunks) + len(chunk) > assets.MAX_BYTES:
            raise HTTPException(413, '圖片不可超過 20 MiB')
        chunks.extend(chunk)
    try:
        return await run_in_threadpool(assets.create, DB, DATA / 'assets', bytes(chunks), filename)
    except ValueError as exc:
        raise HTTPException(422, str(exc))


@app.get('/api/assets/{asset_id}/image')
def asset_image(asset_id: UUID):
    try:
        assets.get(DB, str(asset_id))
    except KeyError:
        raise HTTPException(404, '找不到素材')
    target = DATA / 'assets' / (str(asset_id) + '.png')
    if not target.is_file():
        raise HTTPException(404, '素材檔案已遺失')
    return FileResponse(target, media_type='image/png', headers={'X-Content-Type-Options': 'nosniff'})


class AssetUpdate(BaseModel):
    title: str = Field(min_length=1, max_length=100)
    archived: bool = False
    purpose: Literal['unspecified', 'style', 'character', 'composition'] | None = None
    revision: int | None = Field(default=None, strict=True, ge=0)

    @field_validator('title')
    @classmethod
    def not_blank(cls, value):
        if not value.strip():
            raise ValueError('名稱不可空白')
        return value.strip()


@app.put('/api/assets/{asset_id}')
def update_asset(asset_id: UUID, value: AssetUpdate):
    try:
        return assets.update(DB, str(asset_id), value.title, value.archived, value.purpose, value.revision)
    except KeyError:
        raise HTTPException(404, '找不到素材')
    except ValueError as exc:
        raise HTTPException(409, str(exc))


@app.get('/api/assets/{asset_id}/usage')
def asset_usage(asset_id: UUID):
    try:
        return assets.usage(DB, str(asset_id))
    except KeyError:
        raise HTTPException(404, '找不到素材')


@app.get('/api/reference-workflows')
def reference_capabilities():
    return reference_workflows.descriptions()


submissions.install(app, sys.modules[__name__])
gallery_api.install(app, sys.modules[__name__])
model_profiles.install(app, sys.modules[__name__])
model_paths.install(app, sys.modules[__name__])
environment.install(app, sys.modules[__name__])
validation_records.install(app, sys.modules[__name__])
generation_advice.install(app, sys.modules[__name__])
storage.install(app, sys.modules[__name__])
loras.install(app, sys.modules[__name__])
lora_compatibility.install(app, sys.modules[__name__])
lora_validation.install(app, sys.modules[__name__])
flux_plan.install(app, sys.modules[__name__])
flux_catalog.install(app, sys.modules[__name__])
settings_transfer.install(app, sys.modules[__name__])
stack_validation.install(app, sys.modules[__name__])


if (ROOT / 'frontend' / 'dist').exists():
    app.mount('/', StaticFiles(directory=ROOT / 'frontend' / 'dist', html=True), name='frontend')
