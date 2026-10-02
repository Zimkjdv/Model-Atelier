"""Reviewed, condition-scoped evidence; registered hashes do not verify live files."""
import json
from datetime import date
from pathlib import Path
from typing import Literal

from fastapi import Query
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from backend import model_profiles

REGISTRY = Path(__file__).resolve().parents[1] / 'models' / 'validation-records.json'
WORKFLOW = 'checkpoint-text2image-v1'


class Settings(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True, allow_inf_nan=False)
    width: int = Field(ge=64, le=2048, multiple_of=64)
    height: int = Field(ge=64, le=2048, multiple_of=64)
    steps: int = Field(ge=1, le=150)
    cfg: float = Field(ge=0, le=30)
    sampler_name: str = Field(min_length=1, max_length=100)
    scheduler: str = Field(min_length=1, max_length=100)
    denoise: float = Field(ge=0, le=1)
    batch_size: Literal[1]


class Record(BaseModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False)
    id: str = Field(pattern=r'^[a-z0-9-]{1,100}$')
    date: date
    model: str = Field(min_length=1, max_length=100)
    architecture: Literal['sd1', 'sdxl']
    sha256: str = Field(pattern=r'^[a-f0-9]{64}$')
    workflow: Literal['checkpoint-text2image-v1']
    workload: Literal['inference']
    gpu: str = Field(min_length=1, max_length=240)
    vram_bytes: int = Field(strict=True, gt=0, le=9007199254740991)
    ram_gib: float = Field(gt=0)
    os: str = Field(min_length=1, max_length=240)
    python: str = Field(min_length=1, max_length=100)
    comfyui: str = Field(min_length=1, max_length=100)
    pytorch: str = Field(min_length=1, max_length=100)
    driver: str = Field(min_length=1, max_length=100)
    precision: str = Field(min_length=1, max_length=240)
    offload: str = Field(min_length=1, max_length=500)
    settings: Settings
    cold_wall_seconds: float = Field(gt=0)
    warm_engine_seconds: float = Field(gt=0)
    sampled_device_peak_bytes: int = Field(strict=True, gt=0, le=9007199254740991)
    sample_count: int = Field(strict=True, gt=0)
    reference: str = Field(pattern=r'^docs/validation/[a-z0-9-]+\.md$')
    conditions: str = Field(min_length=1, max_length=2000)


def records():
    try:
        raw = json.loads(REGISTRY.read_text(encoding='utf-8'))
        if not isinstance(raw, dict) or set(raw) != {'records'} or not isinstance(raw['records'], list) or len(raw['records']) > 100:
            raise ValueError('Invalid registry')
        values = [Record.model_validate(value).model_dump(mode='json') for value in raw['records']]
        if len({value['id'] for value in values}) != len(values):
            raise ValueError('Duplicate evidence IDs')
        return values, None
    except (OSError, ValueError, ValidationError):
        return [], '驗證紀錄無法讀取；不推定任何模型已通過實測。'


def evaluate(model):
    values, error = records()
    architecture = model_profiles.architecture(model.get('architecture'))
    compatible = model_profiles.compatibility(architecture)
    matched = [value for value in values if value['sha256'] == model.get('sha256')
               and value['architecture'] == architecture and value['workflow'] == WORKFLOW]
    status = 'incompatible' if not compatible['allows_submission'] else 'verified' if matched else 'unverified'
    return dict(workflow=WORKFLOW, status=status, records=matched, registry_error=error,
                identity_source='registered_metadata', current_file_verified=False, training_status='unverified',
                message={'incompatible': compatible['message'],
                         'verified': '此 SHA256 與架構有已通過的推論紀錄；僅適用紀錄中的環境與設定，不代表目前檔案或本次生成已驗證。',
                         'unverified': '此模型與標準文生圖流程尚無匹配的實測紀錄；檔名與版本名稱不作為相容性證明。'}[status])


def install(app, host):
    @app.get('/api/models/validation')
    def get_validation(engine_url: str = Query(min_length=1, max_length=2048), name: str = Query(min_length=1, max_length=2048)):
        _, model = host.current_catalog(host.ModelTarget(engine_url=engine_url, name=name))
        return dict(engine_url=engine_url, name=name, **evaluate(model))
