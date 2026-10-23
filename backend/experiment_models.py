"""Frozen registered model identities for comparison v2; not weight verification."""

from copy import deepcopy
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field
from backend import catalog

NEW_AXES = frozenset({'checkpoint', 'sampler_name', 'scheduler', 'prompt', 'negative_prompt'})
IDENTITY = ('name', 'version', 'architecture', 'size_bytes', 'sha256')


class ModelSnapshot(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    engine_url: str = Field(min_length=1, max_length=2048)
    name: str = Field(min_length=1, max_length=2048)
    version: str = Field(min_length=1, max_length=100)
    architecture: Literal['unknown', 'sd1', 'sdxl', 'sd3', 'flux', 'other']
    size_bytes: int | None = Field(ge=1, le=9007199254740991)
    sha256: str = Field(pattern=r'^(?:[a-f0-9]{64})?$')
    source_url: str = Field(max_length=2048)
    license_name: str = Field(max_length=200)
    license_url: str = Field(max_length=2048)
    metadata_updated_at: str | None = Field(max_length=100)
    origin: Literal['user_registered']


def registered(item, engine_url):
    snapshot = catalog.capture(item, item['name'])
    snapshot.pop('captured_at')
    return dict(snapshot, engine_url=engine_url)


def collect(path, base, variants, axis, provided=None):
    names = list(
        dict.fromkeys([base['checkpoint'], *[v['settings']['checkpoint'] for v in variants]])
    )
    if provided is None:
        library = catalog.read(path, base['engine_url'])
        if not library.get('synced_at') or library.get('sync_error'):
            raise ValueError('新增比較軸需原引擎最近成功同步的模型登記，請先同步模型庫')
        items = {v['name']: v for v in library['models'] if v.get('listed')}
        if any(name not in items for name in names):
            raise ValueError('比較模型未在原引擎登記清單中，未建立部分方案')
        provided = [registered(items[name], base['engine_url']) for name in names]
    result = [ModelSnapshot.model_validate(item).model_dump(mode='json') for item in provided]
    if [item['name'] for item in result] != names or any(
        item['engine_url'] != base['engine_url'] for item in result
    ):
        raise ValueError('模型快照的順序、名稱或原引擎與完整比較設定不符')
    if axis == 'checkpoint' and (
        result[0]['architecture'] not in ('sd1', 'sdxl')
        or any(item['architecture'] != result[0]['architecture'] for item in result)
    ):
        raise ValueError(
            'checkpoint 比較需登記為相同 SD 1.x 或 SDXL 架構；不自動修改 LoRA 或其他參數'
        )
    return result


def expected(plan, variant):
    if plan['schema_version'] == 1:
        return None
    return deepcopy(
        next(
            item
            for item in plan['model_snapshots']
            if item['name'] == variant['settings']['checkpoint']
        )
    )


def verify(db, expected_model, actual):
    # Reuse the caller's write transaction so catalog edits cannot race reservation.
    library = catalog._read(db, expected_model['engine_url'])
    current = next(
        (v for v in library['models'] if v['name'] == expected_model['name'] and v.get('listed')),
        None,
    )
    if (
        not current
        or not library.get('synced_at')
        or library.get('sync_error')
        or not isinstance(actual, dict)
    ):
        raise ValueError('比較方案的模型登記不可用；請重新同步並建立新方案，未提交任務')
    identity = lambda item: {key: item.get(key) for key in IDENTITY}
    if identity(expected_model) != identity(
        registered(current, expected_model['engine_url'])
    ) or identity(expected_model) != identity(actual):
        raise ValueError('模型版本、hash、架構或大小已與原比較快照不同；請重新預覽保存，未提交任務')
