import csv
import asyncio
import io
import os
import platform
import shutil
import sqlite3
import subprocess
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

import httpx
import psutil
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator
from backend import catalog, drafts

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'data'
DATA.mkdir(exist_ok=True)
DB = DATA / 'atelier.sqlite3'
with closing(sqlite3.connect(DB)) as db, db:
    db.execute('CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL)')

app = FastAPI(title='Model Atelier', version='0.1.0')
catalog_lock = asyncio.Lock()


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
                    return int(float(value) * 1024 * 1024)
                except ValueError:
                    return None
            cards.append(dict(index=row[0], name=row[1], total=memory(row[2]), used=memory(row[3]), free=memory(row[4]), driver=row[5]))
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
        return {'connected': True, 'url': url, 'stats': stats}
    except (httpx.HTTPError, ValueError):
        return {'connected': False, 'url': url, 'error': '無法連接 ComfyUI，請確認服務已啟動且位址正確。'}


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

    @field_validator('source_url')
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
            value = catalog.read(DB, url)
            value['sync_error'] = (str(exc) if isinstance(exc, ValueError)
                                   else '無法同步 ComfyUI，保留上次清單；請檢查連線後重試。')
            catalog.write(DB, value)
            return value
        return catalog.merge(DB, url, names)


@app.put('/api/models/metadata')
async def model_metadata(target: ModelMetadata):
    async with catalog_lock:
        value, model = current_catalog(target)
        model.update(notes=target.notes, source_url=target.source_url, version=target.version.strip())
        catalog.write(DB, value)
        return value


@app.put('/api/models/selection')
async def model_selection(target: ModelTarget):
    async with catalog_lock:
        value, model = current_catalog(target)
        if not model['listed']:
            raise HTTPException(409, '模型已不在最近同步清單中，請重新同步確認')
        value['selected'] = model['name']
        catalog.write(DB, value)
        return value


class DraftInput(BaseModel):
    title: str = Field(min_length=1, max_length=100)
    prompt: str = Field(default='', max_length=20000)
    engine_url: str
    checkpoint: str = Field(default='', max_length=2048)
    width: int = Field(default=1024, ge=64, le=8192, multiple_of=8, strict=True)
    height: int = Field(default=1024, ge=64, le=8192, multiple_of=8, strict=True)
    seed: str = '0'
    revision: int | None = Field(default=None, ge=1)

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
    payload = value.model_dump(exclude={'revision'})
    entries = catalog.read(DB, value.engine_url)['models']
    item = next((item for item in entries if item['name'] == value.checkpoint), {})
    payload['model_version'] = item.get('version', '')
    return payload


@app.get('/api/drafts')
def list_drafts():
    return drafts.list_all(DB)


@app.post('/api/drafts', status_code=201)
def create_draft(value: DraftInput):
    return drafts.save(DB, draft_payload(value))


@app.put('/api/drafts/{draft_id}')
def update_draft(draft_id: str, value: DraftInput):
    try:
        return drafts.save(DB, draft_payload(value), draft_id, value.revision)
    except KeyError:
        raise HTTPException(404, '草稿不存在')
    except ValueError as exc:
        raise HTTPException(409, str(exc))


if (ROOT / 'frontend' / 'dist').exists():
    app.mount('/', StaticFiles(directory=ROOT / 'frontend' / 'dist', html=True), name='frontend')
