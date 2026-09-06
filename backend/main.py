import csv
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
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, field_validator

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'data'
DATA.mkdir(exist_ok=True)
DB = DATA / 'atelier.sqlite3'
with closing(sqlite3.connect(DB)) as db, db:
    db.execute('CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL)')

app = FastAPI(title='Model Atelier', version='0.1.0')


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


if (ROOT / 'frontend' / 'dist').exists():
    app.mount('/', StaticFiles(directory=ROOT / 'frontend' / 'dist', html=True), name='frontend')
