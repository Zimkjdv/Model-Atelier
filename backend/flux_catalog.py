"""Engine-scoped split-model inventories; names are never weight verification."""
import asyncio
import json
import sqlite3
from contextlib import closing
from datetime import datetime, timezone

import httpx
from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field, field_validator

from backend import catalog

GROUPS = {'diffusion_models': ('UNETLoader', 'unet_name'),
          'text_encoders': ('DualCLIPLoader', 'clip_name1'), 'vae': ('VAELoader', 'vae_name')}


def _read(db, url):
    row = db.execute('SELECT value FROM settings WHERE key=?', ('flux_catalog:' + url,)).fetchone()
    value = json.loads(row[0]) if row else dict(engine_url=url, groups={name: [] for name in GROUPS},
                                              synced_at=None, sync_error=None)
    value['groups'] = {name: [catalog.METADATA_DEFAULTS | item | dict(origin=catalog.METADATA_ORIGIN)
                             for item in value['groups'].get(name, [])] for name in GROUPS}
    return value


def read(path, url):
    with closing(sqlite3.connect(path)) as db:
        return _read(db, url)


def mutate(path, url, change):
    with closing(sqlite3.connect(path)) as db, db:
        db.execute('BEGIN IMMEDIATE')
        value = _read(db, url)
        change(value)
        db.execute('INSERT OR REPLACE INTO settings VALUES (?, ?)',
                   ('flux_catalog:' + url, json.dumps(value, ensure_ascii=False)))
    return value


def names(definition, field):
    try:
        value = definition['input']['required'][field][0]
    except (KeyError, IndexError, TypeError) as exc:
        raise ValueError('FLUX 元件清單格式無效；請確認必要載入節點可用。') from exc
    if not isinstance(value, list) or len(value) > 10000 or any(
            not isinstance(item, str) or not item.strip() or len(item) > 2048 for item in value):
        raise ValueError('FLUX 元件清單格式無效；保留上次完整清單。')
    return sorted(set(value), key=str.casefold)


async def fetch(client, url):
    async def load(group, node, field):
        response = await client.get(url + '/object_info/' + node)
        response.raise_for_status()
        if len(response.content) > 1024 * 1024:
            raise ValueError('FLUX 節點回應過大')
        payload = response.json()
        if not isinstance(payload, dict) or not isinstance(payload.get(node), dict):
            raise ValueError('ComfyUI 缺少 FLUX 必要載入節點：' + node)
        definition = payload[node]
        listed = names(definition, field)
        if group == 'text_encoders':
            # Both encoder slots must be available; keep their intersection.
            listed = sorted(set(listed) & set(names(definition, 'clip_name2')), key=str.casefold)
        return group, listed, definition
    results = await asyncio.gather(*(load(group, *spec) for group, spec in GROUPS.items()), return_exceptions=True)
    for result in results:
        if isinstance(result, BaseException):
            raise result
    return {group: listed for group, listed, _ in results}, {GROUPS[group][0]: definition for group, _, definition in results}


def merge(path, url, listed):
    def change(value):
        for group in GROUPS:
            records = {item['name']: item for item in value['groups'][group]}
            for item in records.values():
                item['listed'] = False
            for name in listed[group]:
                records.setdefault(name, catalog.METADATA_DEFAULTS | dict(name=name, origin=catalog.METADATA_ORIGIN))['listed'] = True
            value['groups'][group] = sorted(records.values(), key=lambda item: item['name'].casefold())
        value.update(synced_at=datetime.now(timezone.utc).isoformat(), sync_error=None)
    return mutate(path, url, change)


def update_metadata(path, url, group, name, changes):
    def change(value):
        record = next((item for item in value['groups'][group] if item['name'] == name), None)
        if record is None:
            raise KeyError(name)
        if changes:
            record.update(changes, metadata_updated_at=datetime.now(timezone.utc).isoformat())
    return mutate(path, url, change)


def capture(path, url, selections):
    # All four dependencies are read in one SQLite snapshot.
    with closing(sqlite3.connect(path)) as db:
        value = _read(db, url)
    result = []
    for role, group, name in selections:
        item = next((record for record in value['groups'][group] if record['name'] == name), {})
        result.append(dict(role=role, category=group, **catalog.capture(item, name)))
    return result


def install(app, host):
    lock = asyncio.Lock()

    class Target(BaseModel):
        model_config = ConfigDict(extra='forbid')
        engine_url: str = Field(min_length=1, max_length=2048)

        @field_validator('engine_url')
        @classmethod
        def valid_url(cls, value):
            return host.Settings.validate_url(value)

    class Metadata(host.ModelMetadata):
        model_config = ConfigDict(extra='forbid')
        category: str

        @field_validator('category')
        @classmethod
        def valid_category(cls, value):
            if value not in GROUPS:
                raise ValueError('元件類別無效')
            return value

        @field_validator('engine_url')
        @classmethod
        def valid_url(cls, value):
            return host.Settings.validate_url(value)

        @field_validator('name')
        @classmethod
        def valid_name(cls, value):
            if not value.strip():
                raise ValueError('元件名稱不可空白')
            return value

    def require_engine(url):
        if url != host.engine_url():
            raise HTTPException(409, '引擎設定已變更，請重新載入 FLUX 元件庫。')

    @app.get('/api/flux/components')
    def get_components():
        return read(host.DB, host.engine_url())

    @app.post('/api/flux/components/sync')
    async def sync(target: Target):
        async with lock:
            require_engine(target.engine_url)
            try:
                async with httpx.AsyncClient(timeout=10, trust_env=False) as client:
                    listed, _ = await fetch(client, target.engine_url)
            except (httpx.HTTPError, ValueError) as exc:
                require_engine(target.engine_url)
                message = str(exc) if isinstance(exc, ValueError) else '無法連接 ComfyUI；保留上次完整 FLUX 元件清單。'
                return mutate(host.DB, target.engine_url, lambda value: value.update(sync_error=message))
            require_engine(target.engine_url)
            return merge(host.DB, target.engine_url, listed)

    @app.put('/api/flux/components/metadata')
    async def metadata(target: Metadata):
        async with lock:
            require_engine(target.engine_url)
            changes = target.model_dump(exclude={'engine_url', 'category', 'name'}, exclude_unset=True)
            for field in ('version', 'license_name'):
                if field in changes:
                    changes[field] = changes[field].strip()
            try:
                return update_metadata(host.DB, target.engine_url, target.category, target.name, changes)
            except KeyError:
                raise HTTPException(404, '元件未登記，請先同步清單。')
