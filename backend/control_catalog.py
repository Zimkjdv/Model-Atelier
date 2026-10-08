"""Engine-scoped ControlNet registration. No weight loading or generation here."""
import asyncio
import json
import sqlite3
from contextlib import closing
from datetime import datetime, timezone

import httpx
from fastapi import HTTPException
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator

from backend import catalog


def _read(db, url):
    row = db.execute('SELECT value FROM settings WHERE key=?', ('controlnets:' + url,)).fetchone()
    value = json.loads(row[0]) if row else dict(engine_url=url, controlnets=[], synced_at=None, sync_error=None)
    value['controlnets'] = [catalog.METADATA_DEFAULTS | dict(kind='unknown') | item | dict(origin=catalog.METADATA_ORIGIN)
                      for item in value['controlnets']]
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
                   ('controlnets:' + url, json.dumps(value, ensure_ascii=False)))
    return value


def names_from(payload):
    try:
        names = payload['ControlNetLoader']['input']['required']['control_net_name'][0]
    except (KeyError, IndexError, TypeError) as exc:
        raise ValueError('ComfyUI 未提供有效的 ControlNet 清單；請確認 ControlNetLoader 節點可用。') from exc
    if not isinstance(names, list) or len(names) > 10000 or any(
            not isinstance(name, str) or not name.strip() or len(name) > 2048 for name in names):
        raise ValueError('ComfyUI ControlNet 清單格式不正確，保留上次成功同步資料。')
    return sorted(set(names), key=str.casefold)


def merge(db_path, url, names):
    def change(value):
        records = {item['name']: item for item in value['controlnets']}
        for item in records.values():
            item['listed'] = False
        for name in names:
            records.setdefault(name, catalog.METADATA_DEFAULTS | dict(kind='unknown',name=name, origin=catalog.METADATA_ORIGIN))['listed'] = True
        value.update(controlnets=sorted(records.values(), key=lambda item: item['name'].casefold()),
                     synced_at=datetime.now(timezone.utc).isoformat(), sync_error=None)
    return mutate(db_path, url, change)


def update_metadata(db_path, url, name, changes):
    def change(value):
        model = next((item for item in value['controlnets'] if item['name'] == name), None)
        if model is None:
            raise KeyError('ControlNet 未登記，請先同步清單。')
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

    class ControlMetadata(host.ModelMetadata):
        kind: Literal['unknown','canny','depth','pose','other'] = 'unknown'
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
                raise ValueError('ControlNet 名稱不可空白')
            return value

    def require_engine(url):
        if url != host.engine_url():
            raise HTTPException(409, '執行引擎已變更，請重新載入 ControlNet 模型庫。')

    @app.get('/api/controlnets')
    def get_controlnets():
        return read(host.DB, host.engine_url())

    @app.post('/api/controlnets/sync')
    async def sync_controlnets(target: SyncTarget):
        async with lock:
            url = target.engine_url
            require_engine(url)
            try:
                async with httpx.AsyncClient(timeout=10, trust_env=False) as client:
                    response = await client.get(url + '/object_info/ControlNetLoader')
                    response.raise_for_status()
                    names = names_from(response.json())
            except (httpx.HTTPError, ValueError) as exc:
                require_engine(url)
                message = str(exc) if isinstance(exc, ValueError) else '無法同步 ComfyUI ControlNet，保留上次清單；請檢查連線後重試。'
                return mutate(host.DB, url, lambda value: value.update(sync_error=message))
            require_engine(url)
            return merge(host.DB, url, names)

    @app.put('/api/controlnets/metadata')
    async def edit_metadata(target: ControlMetadata):
        async with lock:
            require_engine(target.engine_url)
            changes = target.model_dump(exclude={'name', 'engine_url'}, exclude_unset=True)
            for field in ('version', 'license_name'):
                if field in changes:
                    changes[field] = changes[field].strip()
            try:
                return update_metadata(host.DB, target.engine_url, target.name, changes)
            except KeyError:
                raise HTTPException(404, 'ControlNet 未登記，請先同步清單。')


def capture(record):
    return catalog.capture(record,record['name']) | dict(role='controlnet',kind=record.get('kind','unknown'))


def validate_snapshot(db,engine,checkpoint,components,model_metadata):
    if not isinstance(components,list) or len(components)!=1 or components[0].get('role')!='controlnet':
        raise ValueError('結構參考需唯一 ControlNet 快照')
    snapshot=components[0]
    if not isinstance(model_metadata,dict): raise ValueError('缺少 checkpoint 來源快照')
    library=_read(db,engine)
    control=next((r for r in library['controlnets'] if r['name']==snapshot['name']),None)
    model=next((r for r in catalog._read(db,engine)['models'] if r['name']==checkpoint),None)
    if not control or not control.get('listed') or library.get('sync_error') or not library.get('synced_at'):
        raise ValueError('ControlNet 尚未登記於成功同步的清單，請先同步')
    if not model or model.get('architecture') not in ('sd1','sdxl') or control.get('architecture')!=model['architecture'] or control.get('kind')!='canny':
        raise ValueError('Canny ControlNet 與 checkpoint 需明確登記相同的 SD 1.x／SDXL 架構與 canny 類型')
    for current,original in ((capture(control),snapshot),(catalog.capture(model,checkpoint),model_metadata)):
        if any(current.get(k)!=v for k,v in original.items() if k!='captured_at'):
            raise ValueError('控制模型或 checkpoint 登記在提交期間變更，請重新確認；未提交生成')


def recheck(path,engine,checkpoint,components,model_metadata):
    with closing(sqlite3.connect(path)) as db:
        validate_snapshot(db,engine,checkpoint,components,model_metadata)


def restoration_warnings(path,engine,components):
    library=read(path,engine);warnings=[]
    for snapshot in components or []:
        if snapshot.get('role')!='controlnet': continue
        record=next((r for r in library['controlnets'] if r['name']==snapshot['name']),None)
        if library.get('sync_error') or not library.get('synced_at'): warnings.append('原 ControlNet 清單尚未確認；保留原設定，生成前需重新檢查。')
        elif not record or not record.get('listed'): warnings.append('原 ControlNet 已不在清單；保留原名稱，未替換控制模型。')
        elif any(capture(record).get(k)!=snapshot.get(k) for k in ('version','architecture','kind','sha256','size_bytes')): warnings.append('目前 ControlNet 登記與原快照不同；保留原版本與條件，請重新確認。')
    return warnings
