"""Engine-scoped LoRA registration. No weight loading or generation here."""
import asyncio
import json
import sqlite3
from contextlib import closing
from datetime import datetime, timezone

import httpx
from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field, field_validator

from backend import catalog


def _read(db, url):
    row = db.execute('SELECT value FROM settings WHERE key=?', ('loras:' + url,)).fetchone()
    value = json.loads(row[0]) if row else dict(engine_url=url, loras=[], synced_at=None, sync_error=None)
    value['loras'] = [catalog.METADATA_DEFAULTS | item | dict(origin=catalog.METADATA_ORIGIN)
                      for item in value['loras']]
    return value


def read(db_path, url):
    with closing(sqlite3.connect(db_path)) as db:
        return _read(db, url)


def mutate(db_path, url, change):
    with closing(sqlite3.connect(db_path)) as db, db:
        db.execute('BEGIN IMMEDIATE')
        value = _read(db, url)
        change(value)
        db.execute('INSERT OR REPLACE INTO settings VALUES (?, ?)',
                   ('loras:' + url, json.dumps(value, ensure_ascii=False)))
    return value


def names_from(payload):
    try:
        names = payload['LoraLoader']['input']['required']['lora_name'][0]
    except (KeyError, IndexError, TypeError) as exc:
        raise ValueError('ComfyUI 未提供有效的 LoRA 清單；請確認 LoraLoader 節點可用。') from exc
    if not isinstance(names, list) or len(names) > 10000 or any(
            not isinstance(name, str) or not name.strip() or len(name) > 2048 for name in names):
        raise ValueError('ComfyUI LoRA 清單格式不正確，保留上次成功同步資料。')
    return sorted(set(names), key=str.casefold)


def merge(db_path, url, names):
    def change(value):
        records = {item['name']: item for item in value['loras']}
        for item in records.values():
            item['listed'] = False
        for name in names:
            records.setdefault(name, catalog.METADATA_DEFAULTS | dict(name=name, origin=catalog.METADATA_ORIGIN))['listed'] = True
        value.update(loras=sorted(records.values(), key=lambda item: item['name'].casefold()),
                     synced_at=datetime.now(timezone.utc).isoformat(), sync_error=None)
    return mutate(db_path, url, change)


def update_metadata(db_path, url, name, changes):
    def change(value):
        model = next((item for item in value['loras'] if item['name'] == name), None)
        if model is None:
            raise KeyError('LoRA 未登記，請先同步清單。')
        if changes:
            model.update(changes, metadata_updated_at=datetime.now(timezone.utc).isoformat())
    return mutate(db_path, url, change)


def install(app, host):
    lock = asyncio.Lock()

    class SyncTarget(BaseModel):
        model_config = ConfigDict(extra='forbid')
        engine_url: str = Field(min_length=1, max_length=2048)

        @field_validator('engine_url')
        @classmethod
        def valid_engine(cls, value):
            return host.Settings.validate_url(value)

    class LoraMetadata(host.ModelMetadata):
        model_config = ConfigDict(extra='forbid')
        engine_url: str = Field(min_length=1, max_length=2048)

        @field_validator('engine_url')
        @classmethod
        def valid_engine(cls, value):
            return host.Settings.validate_url(value)

        @field_validator('name')
        @classmethod
        def not_blank(cls, value):
            if not value.strip():
                raise ValueError('LoRA 名稱不可空白')
            return value

    def require_engine(url):
        if url != host.engine_url():
            raise HTTPException(409, '執行引擎已變更，請重新載入 LoRA 模型庫。')

    @app.get('/api/loras')
    def get_loras():
        return read(host.DB, host.engine_url())

    @app.post('/api/loras/sync')
    async def sync_loras(target: SyncTarget):
        async with lock:
            url = target.engine_url
            require_engine(url)
            try:
                async with httpx.AsyncClient(timeout=10, trust_env=False) as client:
                    response = await client.get(url + '/object_info/LoraLoader')
                    response.raise_for_status()
                    names = names_from(response.json())
            except (httpx.HTTPError, ValueError) as exc:
                require_engine(url)
                message = str(exc) if isinstance(exc, ValueError) else '無法同步 ComfyUI LoRA，保留上次清單；請檢查連線後重試。'
                return mutate(host.DB, url, lambda value: value.update(sync_error=message))
            require_engine(url)
            return merge(host.DB, url, names)

    @app.put('/api/loras/metadata')
    async def edit_metadata(target: LoraMetadata):
        async with lock:
            require_engine(target.engine_url)
            changes = target.model_dump(exclude={'name', 'engine_url'}, exclude_unset=True)
            for field in ('version', 'license_name'):
                if field in changes:
                    changes[field] = changes[field].strip()
            try:
                return update_metadata(host.DB, target.engine_url, target.name, changes)
            except KeyError:
                raise HTTPException(404, 'LoRA 未登記，請先同步清單。')
