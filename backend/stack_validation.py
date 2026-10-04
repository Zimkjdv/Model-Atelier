"""Condition-scoped evidence for an ordered LoRA stack; no live weight proof."""
import json
import sqlite3
from contextlib import closing
from pathlib import Path
from typing import Literal
from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator
from backend import catalog, loras, lora_compatibility, lora_validation, validation_records
from backend.lora_settings import LoraSetting

REGISTRY = Path(__file__).resolve().parents[1] / 'models/stack-validation-records.json'


class Entry(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True, allow_inf_nan=False)
    name: str = Field(min_length=1, max_length=100)
    version: str = Field(min_length=1, max_length=100)
    architecture: Literal['sd1', 'sdxl']
    sha256: str = Field(pattern=r'^[a-f0-9]{64}$')
    strength_model: float = Field(ge=-20, le=20)
    strength_clip: float = Field(ge=-20, le=20)


class Record(validation_records.Record):
    workflow: Literal['ordered-lora-text2image-v1']
    settings: lora_validation.Parameters
    cold_wall_seconds: float | None = None
    warm_engine_seconds: float | None = None
    wall_seconds: float = Field(strict=True, gt=0)
    engine_seconds: float = Field(strict=True, gt=0)
    load_condition: str = Field(min_length=1, max_length=500)
    loras: list[Entry] = Field(min_length=2, max_length=4)
    quality_observation: str = Field(min_length=1, max_length=2000)

    @model_validator(mode='after')
    def coherent(self):
        if len({v.sha256 for v in self.loras}) != len(self.loras) or any(v.architecture != self.architecture for v in self.loras):
            raise ValueError('Duplicate weights or inconsistent architecture')
        return self


class Input(BaseModel):
    model_config = ConfigDict(extra='forbid')
    engine_url: str = Field(min_length=1, max_length=2048)
    checkpoint: str = Field(min_length=1, max_length=2048)
    loras: list[LoraSetting] = Field(min_length=2, max_length=4)
    settings: lora_validation.Parameters | None = None

    @model_validator(mode='after')
    def unique(self):
        if len({v.name for v in self.loras}) != len(self.loras):
            raise ValueError('Duplicate LoRA names')
        return self


def records():
    try:
        if REGISTRY.stat().st_size > 256 * 1024:
            raise ValueError('Oversized registry')
        raw = json.loads(REGISTRY.read_text(encoding='utf-8'))
        if not isinstance(raw, dict) or set(raw) != {'records'} or not isinstance(raw['records'], list) or len(raw['records']) > 100:
            raise ValueError('Invalid registry')
        values = [Record.model_validate(v).model_dump(mode='json') for v in raw['records']]
        if len({v['id'] for v in values}) != len(values):
            raise ValueError('Duplicate record IDs')
        return values, None
    except (OSError, ValueError, ValidationError):
        return [], '有序 LoRA 實測紀錄無法讀取，保持未驗證。'


def read_stack(db_path, url, checkpoint, choices):
    with closing(sqlite3.connect(db_path)) as db:
        db.execute('BEGIN')
        bases, collection = catalog._read(db, url), loras._read(db, url)
    model = next((v for v in bases['models'] if v['name'] == checkpoint), {})
    stack = [next((v for v in collection['loras'] if v['name'] == choice.name), {}) for choice in choices if choice.enabled]
    return model, stack, bool(bases.get('sync_error') or collection.get('sync_error'))


def evaluate(model, stack, choices, parameters=None, *, stale=False):
    values, error = records()
    active = [v for v in choices if v.enabled]
    incompatible = any(lora_compatibility.compare(model, item, stale=stale)['status'] == 'incompatible' for item in stack)
    matched = [v for v in values if not stale and model.get('listed') is True and len(active) == len(stack) == len(v['loras'])
               and model.get('sha256') == v['sha256'] and model.get('architecture') == v['architecture']
               and all(item.get('listed') is True and item.get('sha256') == original['sha256']
                       and item.get('architecture') == original['architecture'] for item, original in zip(stack, v['loras']))]
    matches = [v['id'] for v in matched if parameters == v['settings'] and all(
        choice.strength_model == original['strength_model'] and choice.strength_clip == original['strength_clip']
        for choice, original in zip(active, v['loras']))]
    status = 'incompatible' if incompatible else 'recorded' if matched else 'unverified'
    return dict(status=status, records=matched, matching_parameter_records=matches, registry_error=error,
        checkpoint=lora_validation.identity(model), loras=[lora_validation.identity(v) for v in stack],
        current_file_verified=False, training_status='unverified', identity_source='registered_metadata',
        message={'recorded':'有序雜湊及架構符合歷史載入紀錄；強度與取樣條件另比對，品質觀察不等於畫風保證。',
                 'unverified':'目前有序組合没有匹配紀錄或清單失效；不借用單一 LoRA、反向順序或其他模型的結論。',
                 'incompatible':'至少一個 LoRA 與 checkpoint 的登記架構不同。'}[status])


def install(app, host):
    @app.post('/api/loras/stack-validation')
    def validation(value: Input):
        try:
            url = host.Settings.validate_url(value.engine_url)
        except ValueError as exc:
            raise HTTPException(422, str(exc))
        def selected():
            if url != host.engine_url():
                raise HTTPException(409, '引擎已變更，請重新讀取有序紀錄。')
        selected()
        before = read_stack(host.DB, url, value.checkpoint, value.loras)
        if not before[0] or any(not v for v in before[1]):
            raise HTTPException(404, 'Checkpoint 或啟用 LoRA 尚未登記。')
        result = evaluate(before[0], before[1], value.loras, value.settings.model_dump() if value.settings else None, stale=before[2])
        selected()
        if before != read_stack(host.DB, url, value.checkpoint, value.loras):
            raise HTTPException(409, '登記資料已變更，請重新讀取有序紀錄。')
        return dict(engine_url=url, **result)
