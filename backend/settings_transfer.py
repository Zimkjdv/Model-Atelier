"""Versioned creation settings transfer; validation never dispatches or saves."""
import json
from typing import Literal
from uuid import UUID
from fastapi import HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator
from backend import assets, catalog, flux_workflows, gallery, jobs, workflows

MAX_BYTES = 256 * 1024
STANDARD = 'checkpoint-text2image-v1'
IMAGE = 'checkpoint-image2image-v1'
FLUX = flux_workflows.WORKFLOW_ID


class SourceSnapshot(BaseModel):
    model_config = ConfigDict(extra='forbid')
    kind: Literal['artwork', 'job']
    id: UUID
    model_version: str = Field(max_length=100)
    model_metadata: dict | None = None
    lora_metadata: list[dict] | None = Field(default=None, max_length=4)
    component_metadata: list[dict] | None = Field(default=None, max_length=4)
    reference_metadata: list[dict] | None = Field(default=None, max_length=8)
    runtime_metadata: dict | None = None
    workflow_json: str = Field(max_length=200000)


class ExportInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    workflow_id: Literal[STANDARD, IMAGE, FLUX]
    settings: dict = Field(min_length=1, max_length=64)


class Bundle(ExportInput):
    kind: Literal['model-atelier-creation']
    schema_version: int = Field(strict=True)
    source_snapshot: SourceSnapshot | None = None

    @field_validator('schema_version')
    @classmethod
    def supported_schema(cls, value):
        if value != 1:
            raise ValueError('僅支援設定檔 schema_version 1')
        return value


def document(workflow_id, settings, source_snapshot=None):
    return dict(kind='model-atelier-creation', schema_version=1, workflow_id=workflow_id,
                settings=settings, source_snapshot=source_snapshot)


async def read_json(request, *, max_bytes=MAX_BYTES):
    raw = bytearray()
    async for chunk in request.stream():
        if len(raw) + len(chunk) > max_bytes:
            raise HTTPException(413, f'JSON 文件不可超過 {max_bytes // 1024} KiB')
        raw.extend(chunk)
    def pairs(entries):
        result = {}
        for key, value in entries:
            if key in result:
                raise ValueError('duplicate key')
            result[key] = value
        return result
    def constant(_):
        raise ValueError('Non-finite JSON number')
    try:
        return json.loads(raw.decode('utf-8-sig'), object_pairs_hook=pairs, parse_constant=constant)
    except (UnicodeError, ValueError, RecursionError):
        raise HTTPException(422, '設定檔需為有效 UTF-8 JSON，不可含重複欄位或非有限數值')


def install(app, host):
    class CheckpointInput(host.DraftInput):
        model_config = ConfigDict(extra='forbid')

    def normalized(workflow_id, settings):
        try:
            cls = flux_workflows.Input if workflow_id == FLUX else CheckpointInput
            fields = set(cls.model_fields) - {'revision'}
            if set(settings) != fields:
                raise ValueError('設定欄位缺少或包含不支援內容；不接受任務 ID、修訂號或任意工作流程')
            value = cls.model_validate(settings).model_dump(mode='json', exclude={'revision'})
            if workflow_id == FLUX:
                if value['workflow_id'] != FLUX:
                    raise ValueError('FLUX 流程 ID 不符')
            elif value['workflow_mode'] != ('image2image' if workflow_id == IMAGE else 'text2image'):
                raise ValueError('工作流程 ID 與參考圖模式不符')
            return value
        except (ValidationError, ValueError, TypeError) as exc:
            raise HTTPException(422, '無法完整驗證創作設定；請確認欄位、流程 ID、字串 seed、尺寸及參數') from exc

    def download(value, name):
        raw = json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False)
        if len(raw.encode()) > MAX_BYTES:
            raise HTTPException(413, '完整設定與來源快照超過 256 KiB；請下載原始任務 JSON')
        return Response(raw, media_type='application/json', headers={
            'Content-Disposition': f'attachment; filename="{name}-settings.json"',
            'X-Content-Type-Options': 'nosniff'})

    def original(item, kind):
        workflow_id = item.get('workflow_id') or STANDARD
        try:
            if workflow_id == FLUX:
                settings = flux_workflows.extract(item)
            else:
                outputs = [key for key, node in item['workflow'].items() if node['class_type'] == 'SaveImage']
                if len(outputs) != 1:
                    raise ValueError('需唯一輸出')
                settings = workflows.extract(item | dict(title=item.get('title', '歷史設定'),
                    source=item.get('source') or dict(node_id=outputs[0])),
                    lambda v: CheckpointInput.model_validate(v).model_dump(mode='json', exclude={'revision'}))
        except (ValueError, KeyError, TypeError) as exc:
            raise HTTPException(422, '原流程無法完整轉換成創作設定；請下載完整工作流程 JSON') from exc
        source = dict(kind=kind, id=item['id'], model_version=item.get('model_version') or '未知',
                      workflow_json=json.dumps(item['workflow'], ensure_ascii=False, indent=2, allow_nan=False))
        source.update({key: item.get(key) for key in ('model_metadata', 'lora_metadata', 'component_metadata',
                                                     'reference_metadata', 'runtime_metadata')})
        return document(workflow_id, normalized(workflow_id, settings), source)

    @app.post('/api/creation-settings/export')
    async def export_current(request: Request):
        try:
            value = ExportInput.model_validate(await read_json(request))
        except ValidationError as exc:
            raise HTTPException(422, '匯出需包含已支援 workflow_id 與完整 settings') from exc
        return download(document(value.workflow_id, normalized(value.workflow_id, value.settings)), 'model-atelier')

    @app.get('/api/artworks/{artwork_id}/settings-export')
    def export_artwork(artwork_id: UUID):
        try:
            item = gallery.get(host.DB, str(artwork_id))
        except KeyError:
            raise HTTPException(404, '找不到作品')
        return download(original(item, 'artwork'), str(artwork_id))

    @app.get('/api/jobs/{job_id}/settings-export')
    def export_job(job_id: UUID):
        try:
            item = jobs.get(host.DB, str(job_id))
        except KeyError:
            raise HTTPException(404, '找不到任務')
        if item['status'] not in ('completed', 'failed', 'stopped', 'cancelled'):
            raise HTTPException(409, '請先確認任務終止；未重新提交任何任務')
        return download(original(item, 'job'), str(job_id))

    @app.post('/api/creation-settings/import')
    async def import_settings(request: Request):
        try:
            value = Bundle.model_validate(await read_json(request))
        except ValidationError as exc:
            raise HTTPException(422, '不是支援的 Model Atelier 創作設定檔；請確認 schema_version、kind 與 workflow_id') from exc
        settings = normalized(value.workflow_id, value.settings)
        warnings = ['只驗證設定格式與本機保存資料；未連線引擎、保存草稿、更新模型庫或生成圖片。']
        if settings['engine_url'] != host.engine_url():
            warnings.append('文件原引擎與目前設定不同；保留原位址，生成前請手動確認。')
        if value.source_snapshot:
            warnings.append('來源快照由文件提供，未核實；保留在設定檔供查看，不作為新任務的版本或相容性證明。')
        if value.workflow_id == FLUX:
            warnings.append(flux_workflows.WARNING)
        else:
            inventory = catalog.read(host.DB, settings['engine_url'])
            item = next((m for m in inventory['models'] if m['name'] == settings['checkpoint']), None)
            if not item or not item.get('listed') or inventory.get('sync_error'):
                warnings.append('checkpoint 在本機同步快照中未確認；生成前需確認模型及引擎。')
            identifiers = set(settings['reference_ids']) | ({settings['image_asset_id']} if settings['image_asset_id'] else set())
            for identifier in sorted(identifiers):
                try:
                    asset = assets.get(host.DB, identifier)
                except KeyError:
                    asset = None
                if not asset or asset.get('archived') or not (host.DATA/'assets'/(identifier+'.png')).is_file():
                    warnings.append('參考素材 ' + identifier + ' 在本機不可用；檔案只保存素材 ID，不包含圖片，請手動重新選取。')
        return dict(bundle=document(value.workflow_id, settings, value.source_snapshot.model_dump(mode='json') if value.source_snapshot else None),
                    warnings=warnings)
