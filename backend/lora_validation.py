"""Read-only evidence for a specific checkpoint/LoRA pair, never live file proof."""
import json
import sqlite3
from contextlib import closing
from pathlib import Path
from typing import Literal

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

from backend import catalog, loras, lora_compatibility, validation_records
from backend.lora_settings import LoraSetting

REGISTRY = Path(__file__).resolve().parents[1] / 'models/lora-validation-records.json'
WORKFLOW = 'single-lora-text2image-v1'


class Parameters(validation_records.Settings):
    width: int = Field(ge=64, le=8192, multiple_of=8)
    height: int = Field(ge=64, le=8192, multiple_of=8)

    @field_validator('batch_size', mode='before')
    @classmethod
    def single_batch(cls, value):
        if type(value) is not int or value != 1:
            raise ValueError('Batch must be the integer 1')
        return value


class Record(validation_records.Record):
    workflow: Literal['single-lora-text2image-v1']
    lora: str = Field(min_length=1, max_length=100)
    lora_version: str = Field(min_length=1, max_length=100)
    lora_architecture: Literal['sd1', 'sdxl']
    lora_sha256: str = Field(pattern=r'^[a-f0-9]{64}$')
    strength_model: float = Field(strict=True, ge=-20, le=20)
    strength_clip: float = Field(strict=True, ge=-20, le=20)
    cold_engine_seconds: float = Field(strict=True, gt=0)
    warm_engine_seconds: float | None = Field(default=None, strict=True, gt=0)

    @model_validator(mode='after')
    def same_architecture(self):
        if self.architecture != self.lora_architecture:
            raise ValueError('Evidence must refer to the same base architecture')
        return self


class Input(BaseModel):
    model_config = ConfigDict(extra='forbid')
    engine_url: str = Field(min_length=1, max_length=2048)
    checkpoint: str = Field(min_length=1, max_length=2048)
    lora: LoraSetting
    settings: Parameters | None = None


def records():
    try:
        if REGISTRY.stat().st_size > 256 * 1024:
            raise ValueError('Oversized registry')
        raw = json.loads(REGISTRY.read_text(encoding='utf-8'))
        if not isinstance(raw, dict) or set(raw) != {'records'} or not isinstance(raw['records'], list) or len(raw['records']) > 100:
            raise ValueError('Invalid registry')
        values = [Record.model_validate(v).model_dump(mode='json') for v in raw['records']]
        if len({v['id'] for v in values}) != len(values):
            raise ValueError('Duplicate evidence IDs')
        return values, None
    except (OSError, ValueError, ValidationError):
        return [], 'LoRA 實測紀錄無法讀取；狀態保持未驗證。'


def read_pair(db_path, url, checkpoint, name):
    with closing(sqlite3.connect(db_path)) as db:
        db.execute('BEGIN')
        checkpoints, collection = catalog._read(db, url), loras._read(db, url)
    model = next((v for v in checkpoints['models'] if v['name'] == checkpoint), None)
    lora = next((v for v in collection['loras'] if v['name'] == name), None)
    return model, lora, bool(checkpoints.get('sync_error') or collection.get('sync_error'))


def identity(item):
    return {key: item.get(key) for key in ('name', 'sha256', 'architecture', 'metadata_updated_at', 'listed')}


def evaluate(model, lora, choice, parameters=None, *, stale=False):
    values, error = records()
    architecture = lora_compatibility.compare(model, lora, stale=stale)
    matched = [v for v in values if choice.enabled and not stale and model.get('listed') is True
               and lora.get('listed') is True and v['sha256'] == model.get('sha256')
               and v['lora_sha256'] == lora.get('sha256') and v['architecture'] == model.get('architecture')
               and v['lora_architecture'] == lora.get('architecture')]
    matches = [v['id'] for v in matched if parameters is not None and v['settings'] == parameters
               and v['strength_model'] == choice.strength_model and v['strength_clip'] == choice.strength_clip]
    status = 'incompatible' if architecture['status'] == 'incompatible' else 'recorded' if matched else 'unverified'
    message = {'incompatible': architecture['message'],
               'recorded': '此 checkpoint／LoRA 的登記雜湊及架構有實測紀錄；僅限列出的強度、參數與環境。',
               'unverified': '此組合尚無匹配的實測紀錄，或清單已失效；檔名、版本或同架構不代表載入成功。'}[status]
    return dict(workflow=WORKFLOW, status=status, records=matched, matching_parameter_records=matches,
                checkpoint=identity(model), lora=identity(lora), registry_error=error, message=message,
                identity_source='registered_metadata', current_file_verified=False, training_status='unverified')


def install(app, host):
    @app.post('/api/loras/validation')
    def get_validation(value: Input):
        try:
            url = host.Settings.validate_url(value.engine_url)
        except ValueError as exc:
            raise HTTPException(422, str(exc))
        def selected():
            if url != host.engine_url():
                raise HTTPException(409, '引擎已變更，請重新讀取組合實測紀錄。')
        selected()
        model, lora, stale = read_pair(host.DB, url, value.checkpoint, value.lora.name)
        if model is None or lora is None:
            raise HTTPException(404, 'Checkpoint 或 LoRA 尚未登記，請先同步清單。')
        result = evaluate(model, lora, value.lora, value.settings.model_dump() if value.settings else None, stale=stale)
        selected()
        if (model, lora, stale) != read_pair(host.DB, url, value.checkpoint, value.lora.name):
            raise HTTPException(409, '登記資料已變更，請重新讀取組合實測紀錄。')
        return dict(engine_url=url, **result)
