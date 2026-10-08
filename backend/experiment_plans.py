"""Bounded comparison previews; never save drafts, enqueue jobs or contact an engine."""
import hashlib
import json
from pathlib import Path
from typing import Any, Literal
from fastapi import HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator
from backend import settings_transfer

SUITE = Path(__file__).resolve().parents[1] / 'experiments/general-illustration-v1.json'
MAX_VARIANTS = 8


class Case(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    id: str = Field(pattern=r'^[a-z0-9-]{1,100}$')
    name: str = Field(min_length=1, max_length=100)
    prompt: str = Field(min_length=1, max_length=20000)
    character_key: str | None = Field(max_length=100)
    checks: list[str] = Field(min_length=1, max_length=8)


class Suite(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    id: Literal['general-illustration']
    version: Literal[1]
    name: str = Field(min_length=1, max_length=100)
    cases: list[Case] = Field(min_length=1, max_length=4)

    @field_validator('version', mode='before')
    @classmethod
    def exact_version(cls, value):
        if type(value) is not int or value != 1:
            raise ValueError('Suite version must be the integer 1')
        return value

    @model_validator(mode='after')
    def distinct_cases(self):
        if type(self.version) is not int or len({v.id for v in self.cases}) != len(self.cases):
            raise ValueError('Invalid suite version or duplicate case')
        return self


class Input(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    title: str = Field(min_length=1, max_length=100)
    settings: dict = Field(min_length=1, max_length=64)
    axis: Literal['steps', 'cfg', 'seed', 'lora_strength_model', 'lora_strength_clip']
    target_lora: str | None = Field(default=None, min_length=1, max_length=2048)
    values: list[Any] = Field(min_length=1, max_length=4)
    case_ids: list[str] = Field(default_factory=list, max_length=4)
    expected_plan_sha256: str | None = Field(default=None, pattern=r'^[a-f0-9]{64}$')

    @model_validator(mode='after')
    def unique(self):
        if not self.title.strip() or len(set(self.case_ids)) != len(self.case_ids):
            raise ValueError('Blank title or duplicate cases')
        return self


def suite():
    try:
        raw = SUITE.read_bytes()
        if len(raw) > 64 * 1024:
            raise ValueError('Oversized suite')
        value = Suite.model_validate_json(raw).model_dump(mode='json')
        return value | dict(sha256=hashlib.sha256(raw).hexdigest())
    except (OSError, ValueError, ValidationError) as exc:
        raise HTTPException(503, '固定測試集無法讀取，不產生未驗證的比較方案。') from exc


def install(app, host):
    class Settings(host.DraftInput):
        model_config = ConfigDict(extra='forbid')

    def normalize(raw):
        try:
            if set(raw) != set(Settings.model_fields) - {'revision'}:
                raise ValueError('Incomplete or unknown fields')
            value = Settings.model_validate(raw).model_dump(mode='json', exclude={'revision'})
            if value['workflow_mode'] != 'text2image' or value['image_asset_id'] or value['reference_ids']:
                raise ValueError('Only reference-free checkpoint text2image')
            if not value['checkpoint'].strip():
                raise ValueError('Checkpoint required')
            return value
        except (ValidationError, ValueError, TypeError) as exc:
            raise HTTPException(422, '比較僅支援完整、無參考圖的 checkpoint 文生圖設定；請確認模型、字串 seed、參數及欄位。') from exc

    def preview(value):
        base = normalize(value.settings)
        original = suite() if value.case_ids else None
        cases = [next((c for c in original['cases'] if c['id'] == identifier), None) for identifier in value.case_ids] if original else [dict(id='current-prompt', name='目前提示詞', prompt=base['prompt'], character_key=None, checks=[])]
        if any(c is None for c in cases) or any(not c['prompt'].strip() for c in cases):
            raise HTTPException(422, '案例不存在或目前提示詞空白；請選擇固定案例或先填寫提示詞。')
        if len(cases) * len(value.values) > MAX_VARIANTS:
            raise HTTPException(422, '最多預覽 8 次生成，請減少案例或參數值；未建立任何任務。')
        is_lora = value.axis.startswith('lora_strength_')
        selected = next((v for v in base['loras'] if v['name'] == value.target_lora and v['enabled']), None)
        if (is_lora and selected is None) or (not is_lora and value.target_lora is not None):
            raise HTTPException(422, 'LoRA 強度比較需選擇基準中已啟用的 LoRA；其他參數軸不可指定 LoRA。')
        field = value.axis.removeprefix('lora_') if is_lora else value.axis
        def vary(item):
            changes = {'loras': [v | {field: item} if v['name'] == value.target_lora else dict(v) for v in base['loras']]} if is_lora else {field: item}
            return normalize(base | changes)
        def axis_value(settings):
            return next(v[field] for v in settings['loras'] if v['name'] == value.target_lora) if is_lora else settings[field]
        normalized = [vary(item) for item in value.values]
        values = [axis_value(v) for v in normalized]
        if len(set(values)) != len(values):
            raise HTTPException(422, '參數值正規化後重複，請移除重複值。')
        variants = []
        for case in cases:
            for settings in normalized:
                index = len(variants) + 1
                row = settings | dict(prompt=case['prompt'], title=f'{value.title.strip()} / {case["name"]} / {value.axis}={axis_value(settings)}'[:100])
                variants.append(dict(id=f'variant-{index}', case_id=case['id'], value=axis_value(settings), settings=row))
        document = dict(kind='model-atelier-comparison-plan', schema_version=1, title=value.title.strip(),
                        workflow_id=settings_transfer.STANDARD, baseline=base, axis=value.axis, values=values,
                        suite=(original | dict(cases=cases)) if original else None, variants=variants,
                        expected_job_count=len(variants), batch_size=1)
        if is_lora:
            document['target_lora'] = value.target_lora
        canonical = json.dumps(document, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)
        document['plan_sha256'] = hashlib.sha256(canonical.encode()).hexdigest()
        if value.expected_plan_sha256 and value.expected_plan_sha256 != document['plan_sha256']:
            raise HTTPException(409, '原比較方案或測試集已變更，請重新預覽後再匯出。')
        document['warnings'] = ['只是原設定的比較方案；未保存草稿、生成、驗權重或連線引擎。',
            '一次只比較一個參數；固定案例會明確替換提示詞，其餘設定保留。品質需以原圖及人工評分判斷。',
            '每個方案需載入設定後再明確生成；載入次數不是已生成數，沒有自動批次、重試或耗時／VRAM 估算。']
        if base['engine_url'] != host.engine_url():
            document['warnings'].append('原引擎與目前設定不同，已保留原網址；生成前請確認引擎與模型。')
        return document

    async def read(request):
        try:
            return Input.model_validate(await settings_transfer.read_json(request))
        except ValidationError as exc:
            raise HTTPException(422, '比較方案格式無效；需完整設定、單一參數軸、1–4 個值及最多四個不同案例。') from exc

    @app.get('/api/experiments/suite')
    def get_suite():
        return suite()

    @app.post('/api/experiments/preview')
    async def get_preview(request: Request):
        return preview(await read(request))

    @app.post('/api/experiments/export')
    async def export(request: Request):
        raw = json.dumps(preview(await read(request)), ensure_ascii=False, indent=2, allow_nan=False)
        if len(raw.encode()) > 1024 * 1024:
            raise HTTPException(413, '比較方案超過 1 MiB，請縮短提示詞或減少案例。')
        return Response(raw, media_type='application/json', headers={
            'Content-Disposition':'attachment; filename="model-atelier-comparison-plan.json"', 'X-Content-Type-Options':'nosniff'})
