"""Engine-scoped adapter/vision registration, frozen and rechecked at dispatch."""

import asyncio
from contextlib import closing
from datetime import datetime, timezone
import json
import sqlite3
from typing import Literal

from fastapi import HTTPException
import httpx
from pydantic import ConfigDict, field_validator

from backend import catalog

ROLES = {
    'ipadapter': ('IPAdapterModelLoader', 'ipadapter_file', 'sdxl-plus-vit-h', 'sdxl'),
    'clip_vision': ('CLIPVisionLoader', 'clip_name', 'clip-vit-h-14', 'other'),
}


def _read(db, engine):
    row = db.execute('SELECT value FROM settings WHERE key=?', ('adapters:' + engine,)).fetchone()
    result = (
        json.loads(row[0])
        if row
        else dict(engine_url=engine, components=[], synced_at=None, sync_error=None)
    )
    result['components'] = [
        catalog.METADATA_DEFAULTS
        | dict(family='unknown')
        | r
        | dict(origin=catalog.METADATA_ORIGIN)
        for r in result['components']
    ]
    return result


def read(path, engine):
    with closing(sqlite3.connect(path)) as db:
        return _read(db, engine)


def mutate(path, engine, change):
    with closing(sqlite3.connect(path)) as db, db:
        db.execute('BEGIN IMMEDIATE')
        value = _read(db, engine)
        change(value)
        db.execute(
            'INSERT OR REPLACE INTO settings VALUES (?,?)',
            ('adapters:' + engine, json.dumps(value, ensure_ascii=False)),
        )
    return value


def merge(path, engine, names):
    if set(names) != set(ROLES):
        raise ValueError('Adapter 與編碼器必須一起成功同步')

    def change(value):
        records = {(r['role'], r['name']): r for r in value['components']}
        for record in records.values():
            record['listed'] = False
        for role, entries in names.items():
            for name in entries:
                records.setdefault(
                    (role, name),
                    catalog.METADATA_DEFAULTS
                    | dict(role=role, name=name, family='unknown', origin=catalog.METADATA_ORIGIN),
                )['listed'] = True
        value.update(
            components=sorted(records.values(), key=lambda r: (r['role'], r['name'].casefold())),
            synced_at=datetime.now(timezone.utc).isoformat(),
            sync_error=None,
        )

    return mutate(path, engine, change)


def update_metadata(path, engine, role, name, changes):
    def change(value):
        record = next(
            (r for r in value['components'] if r['role'] == role and r['name'] == name), None
        )
        if record is None:
            raise KeyError('元件未同步')
        record.update(changes, metadata_updated_at=datetime.now(timezone.utc).isoformat())

    return mutate(path, engine, change)


def capture(record):
    return catalog.capture(record, record['name']) | dict(
        role=record['role'], family=record.get('family', 'unknown')
    )


def validate_snapshot(db, engine, checkpoint, components, model_metadata):
    if (
        not isinstance(components, list)
        or len(components) != 2
        or [r.get('role') for r in components] != list(ROLES)
    ):
        raise ValueError('參考流程需唯一 adapter 與 ViT-H 編碼器快照')
    model = next((r for r in catalog._read(db, engine)['models'] if r['name'] == checkpoint), None)
    if (
        not model
        or model.get('architecture') != 'sdxl'
        or not isinstance(model_metadata, dict)
        or model_metadata.get('architecture') != 'sdxl'
    ):
        raise ValueError('參考流程需明確登記 SDXL checkpoint')
    library = _read(db, engine)
    if library['sync_error'] or not library['synced_at']:
        raise ValueError('需先成功同步 adapter 與影像編碼器')
    for snapshot in components:
        role = snapshot['role']
        record = next(
            (
                r
                for r in library['components']
                if r['role'] == role and r['name'] == snapshot['name']
            ),
            None,
        )
        if (
            not record
            or not record.get('listed')
            or record.get('family') != ROLES[role][2]
            or record.get('architecture') != ROLES[role][3]
            or not record['name'].endswith('.safetensors')
        ):
            raise ValueError(
                '元件需登記 SDXL Plus ViT-H／CLIP ViT-H/14 的匹配家族與架構，且使用 safetensors'
            )
        if any(capture(record).get(k) != v for k, v in snapshot.items() if k != 'captured_at'):
            raise ValueError('參考元件登記於提交期間變更，未提交生成')
    if any(
        catalog.capture(model, checkpoint).get(k) != v
        for k, v in model_metadata.items()
        if k != 'captured_at'
    ):
        raise ValueError('Checkpoint 登記於提交期間變更，未提交生成')


def recheck(path, engine, checkpoint, components, model_metadata):
    with closing(sqlite3.connect(path)) as db:
        validate_snapshot(db, engine, checkpoint, components, model_metadata)


def restoration_warnings(path, engine, components):
    originals = [r for r in components or [] if r.get('role') in ROLES]
    if not originals:
        return []
    library = read(path, engine)
    warnings = []
    for original in originals:
        record = next(
            (
                r
                for r in library['components']
                if (r['role'], r['name']) == (original['role'], original['name'])
            ),
            None,
        )
        if (
            library['sync_error']
            or not library['synced_at']
            or not record
            or not record.get('listed')
        ):
            warnings.append(
                '原參考元件清單未確認或檔名已不存在；保留原名稱與版本，生成前請重新檢查。'
            )
        elif any(
            capture(record).get(k) != original.get(k)
            for k in ('architecture', 'family', 'version', 'sha256', 'size_bytes')
        ):
            warnings.append('目前參考元件登記與原快照不同；原設定未被替換。')
    return warnings


def install(app, host):
    lock = asyncio.Lock()

    class Target(host.Settings):
        model_config = ConfigDict(extra='forbid')

    class Metadata(host.ModelMetadata):
        model_config = ConfigDict(extra='forbid')
        role: Literal['ipadapter', 'clip_vision']
        family: Literal['unknown', 'sdxl-plus-vit-h', 'clip-vit-h-14', 'other'] = 'unknown'

        @field_validator('engine_url')
        @classmethod
        def valid_url(cls, value):
            return host.Settings.validate_url(value)

        @field_validator('name')
        @classmethod
        def not_blank(cls, value):
            if not value.strip():
                raise ValueError('元件名稱不可空白')
            return value

    def require_engine(engine):
        if engine != host.engine_url():
            raise HTTPException(409, '引擎設定已變更，請重新載入參考元件')

    @app.get('/api/reference-components')
    def get():
        return read(host.DB, host.engine_url())

    @app.post('/api/reference-components/sync')
    async def sync(target: Target):
        async with lock:
            engine = target.comfy_url
            require_engine(engine)
            try:
                async with host.http_client(timeout=10, trust_env=False) as client:

                    async def one(role, spec):
                        response = await client.get(engine + '/object_info/' + spec[0])
                        response.raise_for_status()
                        if len(response.content) > 1024 * 1024:
                            raise ValueError('節點清單過大')
                        try:
                            names = response.json()[spec[0]]['input']['required'][spec[1]][0]
                        except (KeyError, TypeError, IndexError) as exc:
                            raise ValueError('參考節點缺少元件清單') from exc
                        if (
                            not isinstance(names, list)
                            or len(names) > 10000
                            or any(
                                not isinstance(n, str) or not n.strip() or len(n) > 2048
                                for n in names
                            )
                        ):
                            raise ValueError('參考元件清單無效')
                        return role, sorted(set(names), key=str.casefold)

                    results = await asyncio.gather(
                        *(one(role, spec) for role, spec in ROLES.items()), return_exceptions=True
                    )
                    for result in results:
                        if isinstance(result, BaseException):
                            raise result
            except (httpx.HTTPError, ValueError) as exc:
                require_engine(engine)
                message = str(exc)
                return mutate(host.DB, engine, lambda value: value.update(sync_error=message))
            require_engine(engine)
            return merge(host.DB, engine, dict(results))

    @app.put('/api/reference-components/metadata')
    async def edit(target: Metadata):
        async with lock:
            require_engine(target.engine_url)
            try:
                return update_metadata(
                    host.DB,
                    target.engine_url,
                    target.role,
                    target.name,
                    target.model_dump(exclude={'engine_url', 'role', 'name'}, exclude_unset=True),
                )
            except KeyError as exc:
                raise HTTPException(404, str(exc)) from exc
