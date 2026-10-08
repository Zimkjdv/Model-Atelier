"""Bounded comparison previews; never save drafts, enqueue jobs or contact an engine."""
import hashlib
import json
from pathlib import Path
from typing import Any, Literal
from uuid import UUID
from fastapi import HTTPException, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator
from backend import assets, experiment_store, settings_transfer

SUITE = Path(__file__).resolve().parents[1] / 'experiments/general-illustration-v1.json'
MAX_VARIANTS = 8
MAX_DOCUMENT_BYTES = 1024 * 1024
Axis = Literal['steps', 'cfg', 'seed', 'denoise', 'lora_strength_model', 'lora_strength_clip']


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
    axis: Axis
    target_lora: str | None = Field(default=None, min_length=1, max_length=2048)
    values: list[Any] = Field(min_length=1, max_length=4)
    case_ids: list[str] = Field(default_factory=list, max_length=4)
    expected_plan_sha256: str | None = Field(default=None, pattern=r'^[a-f0-9]{64}$')

    @model_validator(mode='after')
    def unique(self):
        if not self.title.strip() or len(set(self.case_ids)) != len(self.case_ids):
            raise ValueError('Blank title or duplicate cases')
        return self


class SuiteSnapshot(Suite):
    sha256: str = Field(pattern=r'^[a-f0-9]{64}$')


class Variant(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    id: str = Field(pattern=r'^variant-[1-8]$')
    case_id: str = Field(min_length=1, max_length=100)
    value: Any
    settings: dict = Field(min_length=1, max_length=64)


class Document(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    kind: Literal['model-atelier-comparison-plan']
    schema_version: int = Field(strict=True, ge=1, le=1)
    title: str = Field(min_length=1, max_length=100)
    workflow_id: Literal[settings_transfer.STANDARD, settings_transfer.IMAGE]
    baseline: dict = Field(min_length=1, max_length=64)
    axis: Axis
    target_lora: str | None = Field(default=None, min_length=1, max_length=2048)
    values: list[Any] = Field(min_length=1, max_length=4)
    suite: SuiteSnapshot | None
    variants: list[Variant] = Field(min_length=1, max_length=MAX_VARIANTS)
    expected_job_count: int = Field(strict=True, ge=1, le=MAX_VARIANTS)
    batch_size: int = Field(strict=True, ge=1, le=1)
    plan_sha256: str = Field(pattern=r'^[a-f0-9]{64}$')
    warnings: list[str] = Field(max_length=32)


class SaveInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    request_id: UUID
    plan: dict


class ArchiveInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    revision: int = Field(strict=True, ge=1)
    archived: bool = Field(strict=True)


def digest(value):
    content = {key:item for key,item in value.items() if key not in ('plan_sha256','warnings')}
    raw = json.dumps(content,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False)
    return hashlib.sha256(raw.encode()).hexdigest()


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
            if value['workflow_mode'] == 'image2image':
                if not value['image_asset_id'] or value['reference_ids'] != [value['image_asset_id']]:
                    raise ValueError('Exactly one matching source image required')
            elif value['image_asset_id'] or value['reference_ids']:
                raise ValueError('Reference-free text2image required')
            if not value['checkpoint'].strip():
                raise ValueError('Checkpoint required')
            return value
        except (ValidationError, ValueError, TypeError) as exc:
            raise HTTPException(422, '比較需完整 checkpoint 設定；文生圖不套用素材，圖生圖需一個相符的素材 ID。請確認模型、字串 seed、參數及欄位。') from exc

    def build(value, original):
        base = normalize(value.settings)
        if value.axis == 'denoise' and base['workflow_mode'] != 'image2image':
            raise HTTPException(422, 'Denoise 比較僅支援單張 checkpoint 圖生圖；未變更流程模式。')
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
                        workflow_id=settings_transfer.IMAGE if base['workflow_mode'] == 'image2image' else settings_transfer.STANDARD, baseline=base, axis=value.axis, values=values,
                        suite=(original | dict(cases=cases)) if original else None, variants=variants,
                        expected_job_count=len(variants), batch_size=1)
        if is_lora:
            document['target_lora'] = value.target_lora
        document['plan_sha256'] = digest(document)
        if value.expected_plan_sha256 and value.expected_plan_sha256 != document['plan_sha256']:
            raise HTTPException(409, '原比較方案或測試集已變更，請重新預覽後再匯出。')
        document['warnings'] = ['只是原設定的比較方案；未保存草稿、生成、驗權重或連線引擎。',
            '一次只比較一個參數；固定案例會明確替換提示詞，其餘設定保留。品質需以原圖及人工評分判斷。',
            '每個方案需載入設定後再明確生成；載入次數不是已生成數，沒有自動批次、重試或耗時／VRAM 估算。']
        if base['engine_url'] != host.engine_url():
            document['warnings'].append('原引擎與目前設定不同，已保留原網址；生成前請確認引擎與模型。')
        if base['workflow_mode'] == 'image2image':
            document['warnings'].append('每組沿用同一素材 ID 與前處理；文件不包含原圖片，固定案例只替換文字，不代表畫風或角色鎖定。')
            try:
                asset = assets.get(host.DB, base['image_asset_id'])
            except KeyError:
                asset = None
            if not asset or asset.get('archived') or not (host.DATA / 'assets' / (base['image_asset_id'] + '.png')).is_file():
                document['warnings'].append('原素材在本機不可用；保留原 ID，請修復或重新選擇後再生成。')
        return document

    def preview(value):
        return build(value, suite() if value.case_ids else None)

    def validate_document(raw):
        try:
            value = Document.model_validate(raw)
            original = value.suite.model_dump(mode='json') if value.suite else None
            selected = [case['id'] for case in original['cases']] if original else []
            parameters = Input(title=value.title, settings=value.baseline, axis=value.axis, values=value.values,
                               target_lora=value.target_lora, case_ids=selected)
            rebuilt = build(parameters, original)
            if value.plan_sha256 != digest(raw) or value.plan_sha256 != rebuilt['plan_sha256']:
                raise ValueError('Hash or reconstructed variants differ')
            if len(json.dumps(raw,ensure_ascii=False,allow_nan=False).encode()) > MAX_DOCUMENT_BYTES:
                raise HTTPException(413, '比較方案不可超過 1 MiB')
        except (ValidationError, ValueError, TypeError, RecursionError) as exc:
            raise HTTPException(422, '比較文件或 hash 無效；完整設定、單一變因與每組快照需相符，未保存或生成。') from exc
        rebuilt['warnings'].append('保存／匯入文件只驗證結構及內容一致性；來源與 hash 由文件提供，不是權重、環境或品質證明。')
        if original:
            try:
                current = suite()
                matching = (all(original[k] == current[k] for k in ('id','version','name','sha256'))
                            and all(case in current['cases'] for case in original['cases']))
            except HTTPException:
                matching = False
            if not matching:
                rebuilt['warnings'].append('文件案例與目前固定測試集不符或目前測試集不可用；保留原案例快照，不替換成新版。')
        return rebuilt

    def shown(value):
        return value | dict(plan=validate_document(value['plan']))

    async def read(request):
        try:
            return Input.model_validate(await settings_transfer.read_json(request))
        except ValidationError as exc:
            raise HTTPException(422, '比較方案格式無效；需完整設定、單一參數軸、1–4 個值及最多四個不同案例。') from exc

    def download(document):
        raw = json.dumps(document, ensure_ascii=False, indent=2, allow_nan=False)
        if len(raw.encode()) > MAX_DOCUMENT_BYTES:
            raise HTTPException(413, '比較方案超過 1 MiB，請縮短提示詞或減少案例。')
        return Response(raw, media_type='application/json', headers={
            'Content-Disposition':'attachment; filename="model-atelier-comparison-plan.json"', 'X-Content-Type-Options':'nosniff'})

    @app.post('/api/experiments/import-preview')
    async def import_preview(request: Request):
        return validate_document(await settings_transfer.read_json(request,max_bytes=MAX_DOCUMENT_BYTES))

    @app.post('/api/experiments/document-export')
    async def export_document(request: Request):
        return download(validate_document(await settings_transfer.read_json(request,max_bytes=MAX_DOCUMENT_BYTES)))

    @app.get('/api/experiments/plans')
    def list_plans():
        return experiment_store.summaries(host.DB)

    @app.get('/api/experiments/plans/{identifier}')
    def get_plan(identifier: UUID):
        try:
            return shown(experiment_store.get(host.DB,str(identifier)))
        except KeyError:
            raise HTTPException(404, '找不到比較方案')

    @app.post('/api/experiments/plans')
    async def save_plan(request: Request):
        try:
            value = SaveInput.model_validate(await settings_transfer.read_json(request,max_bytes=MAX_DOCUMENT_BYTES))
        except ValidationError as exc:
            raise HTTPException(422, '保存需包含 request_id 與完整 plan；不接受修訂或任務欄位。') from exc
        plan = validate_document(value.plan)
        try:
            record,created = experiment_store.save(host.DB,str(value.request_id),plan)
            return JSONResponse(shown(record),status_code=201 if created else 200)
        except ValueError as exc:
            raise HTTPException(409,str(exc)) from exc

    @app.put('/api/experiments/plans/{identifier}')
    async def archive_plan(identifier: UUID, request: Request):
        try:
            value = ArchiveInput.model_validate(await settings_transfer.read_json(request))
        except ValidationError as exc:
            raise HTTPException(422, '封存／還原需包含整數 revision 及 archived 布林值；原方案不可覆寫。') from exc
        try:
            return shown(experiment_store.archive(host.DB,str(identifier),value.revision,value.archived))
        except KeyError:
            raise HTTPException(404, '找不到比較方案')
        except ValueError as exc:
            raise HTTPException(409,str(exc)) from exc

    @app.get('/api/experiments/suite')
    def get_suite():
        return suite()

    @app.post('/api/experiments/preview')
    async def get_preview(request: Request):
        return preview(await read(request))

    @app.post('/api/experiments/export')
    async def export(request: Request):
        return download(preview(await read(request)))
