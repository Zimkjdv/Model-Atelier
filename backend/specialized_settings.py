"""Dedicated settings and comparison documents for the versioned image workflows."""

from contextlib import closing
import json
import sqlite3
from typing import Literal
from uuid import UUID

from fastapi import HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict, Field, ValidationError, create_model
from starlette.concurrency import run_in_threadpool

from backend import (
    adapter_catalog,
    adapter_workflows,
    assets,
    catalog,
    control_catalog,
    control_edge_workflows,
    control_workflows,
    drafts,
    experiment_context,
    experiment_results,
    experiment_store,
    fooocus_workflows,
    gallery,
    image_workflows,
    inpaint_feather_workflows,
    inpaint_workflows,
    jobs,
    loras,
    settings_transfer,
    structure_workflows,
    workflow_support,
    workflows,
)

PREFIX = '/api/specialized'
DRAFT_PREFIX = 'specialized-draft:'
PLAN_PREFIX = 'specialized-experiment:'
MAX_PLAN_BYTES = 1024 * 1024
FLOW_SCHEMAS = {
    inpaint_workflows.ID: 'InpaintInput',
    inpaint_feather_workflows.ID: 'InpaintFeatherInput',
    fooocus_workflows.ID: 'FooocusInput',
    control_workflows.ID: 'ControlInput',
    control_edge_workflows.ID: 'ControlInput',
    structure_workflows.ID: 'StructureInput',
    adapter_workflows.ID: 'ReferenceInput',
}
AXES = {
    inpaint_workflows.ID: ('denoise', 'grow_mask_by'),
    inpaint_feather_workflows.ID: ('denoise', 'grow_mask_by', 'feather_radius'),
    fooocus_workflows.ID: ('grow_mask_by', 'feather_radius'),
    control_workflows.ID: (
        'control_strength',
        'control_start',
        'control_end',
        'canny_low',
        'canny_high',
    ),
    control_edge_workflows.ID: (
        'control_strength',
        'control_start',
        'control_end',
        'canny_low',
        'canny_high',
    ),
    structure_workflows.ID: ('control_strength', 'control_start', 'control_end'),
    adapter_workflows.ID: ('reference_weight', 'reference_start', 'reference_end'),
}
INTEGER_AXES = {'steps', 'grow_mask_by', 'feather_radius'}
ASSET_KEYS = ('id', 'sha256', 'size', 'width', 'height')
REGISTRATION_KEYS = ('name', 'version', 'architecture', 'sha256', 'size_bytes')
ASSET_FIELDS = ('image_asset_id', 'mask_asset_id')
SELECTION_FIELDS = ('checkpoint', 'control_net_name', 'ipadapter_name', 'clip_vision_name')


class StrictDocument(BaseModel):
    model_config = ConfigDict(extra='forbid')


class AssetBinding(StrictDocument):
    role: Literal['source', 'mask']
    id: UUID
    sha256: str = Field(pattern=r'^[a-f0-9]{64}$')
    size: int = Field(strict=True, gt=0, le=image_workflows.MAX_ENCODED)
    width: int = Field(strict=True, gt=0, le=assets.MAX_PIXELS)
    height: int = Field(strict=True, gt=0, le=assets.MAX_PIXELS)


class Registration(StrictDocument):
    name: str = Field(max_length=2048)
    version: str = Field(max_length=100)
    architecture: str = Field(max_length=32)
    sha256: str = Field(pattern=r'^(?:[a-f0-9]{64})?$')
    size_bytes: int | None = Field(strict=True, ge=1, le=9007199254740991)


class ComponentRegistration(Registration):
    role: Literal['controlnet', 'ipadapter', 'clip_vision']
    kind: str | None = Field(default=None, max_length=32)
    family: str | None = Field(default=None, max_length=32)


class Registrations(StrictDocument):
    checkpoint: Registration
    loras: list[Registration] = Field(max_length=4)
    components: list[ComponentRegistration] = Field(max_length=2)


class Capture(StrictDocument):
    workflow_id: str
    settings: dict = Field(min_length=1, max_length=32)


class Document(Capture):
    kind: Literal['model-atelier-specialized-creation']
    schema_version: Literal[1]
    input_assets: list[AssetBinding] = Field(max_length=2)
    registrations: Registrations
    source_snapshot: settings_transfer.SourceSnapshot | None = None


class DraftSave(StrictDocument):
    document: Document
    revision: int | None = Field(default=None, strict=True, ge=1)


class PlanInput(StrictDocument):
    document: Document
    axis: str = Field(max_length=32)
    values: list[str | int | float] = Field(min_length=2, max_length=4)


class PlanSave(StrictDocument):
    request_id: UUID
    plan: dict


class Archive(StrictDocument):
    revision: int = Field(strict=True, ge=1)
    archived: bool = Field(strict=True)


def stable_registration(record, name):
    captured = catalog.capture(record or {}, name)
    return {key: captured[key] for key in REGISTRATION_KEYS}


def asset_bindings(db, data, settings, *, verify_files=True):
    bindings = []
    for field, role in zip(ASSET_FIELDS, ('source', 'mask'), strict=True):
        identifier = settings.get(field)
        if not identifier:
            continue
        row = db.execute(
            'SELECT value FROM settings WHERE key=?', ('asset:' + identifier,)
        ).fetchone()
        asset = json.loads(row[0]) if row else None
        if not asset or asset.get('archived') or asset.get('id') != identifier:
            raise ValueError(f'素材 {identifier} 不存在或已封存')
        if verify_files:
            image_workflows.read_asset_bytes(data, asset)
        bindings.append(dict(role=role, **{key: asset[key] for key in ASSET_KEYS}))
    if len(bindings) == 2 and any(bindings[0][k] != bindings[1][k] for k in ('width', 'height')):
        raise ValueError('原圖與遮罩的尺寸不同')
    return bindings


def registrations(db, settings):
    engine = settings['engine_url']
    model = next(
        (r for r in catalog._read(db, engine)['models'] if r['name'] == settings['checkpoint']), {}
    )
    lora_records = {r['name']: r for r in loras._read(db, engine)['loras']}
    components = []
    if 'control_net_name' in settings and settings['control_net_name']:
        name = settings['control_net_name']
        records = control_catalog._read(db, engine)['controlnets']
        row = next((r for r in records if r['name'] == name), {})
        components.append(
            stable_registration(row, name)
            | dict(role='controlnet', kind=row.get('kind', 'unknown'))
        )
    if 'reference_mode' in settings:
        records = adapter_catalog._read(db, engine)['components']
        for role in ('ipadapter', 'clip_vision'):
            name = settings[role + '_name']
            if not name:
                continue
            row = next((r for r in records if r['role'] == role and r['name'] == name), {})
            components.append(
                stable_registration(row, name)
                | dict(role=role, family=row.get('family', 'unknown'))
            )
    return dict(
        checkpoint=stable_registration(model, settings['checkpoint']),
        loras=[
            stable_registration(lora_records.get(choice['name']), choice['name'])
            for choice in settings['loras']
        ],
        components=components,
    )


def verify_bindings(db, data, document, *, verify_files=True, check_models=False):
    settings = document['settings']
    if asset_bindings(db, data, settings, verify_files=verify_files) != document['input_assets']:
        raise ValueError('素材 ID、角色、SHA256、大小或尺寸與原設定不同')
    if check_models and registrations(db, settings) != document['registrations']:
        raise ValueError('模型、LoRA 或控制元件登記已變更；請重建比較方案')


def freeze(db, selection, settings, workflow_id, reference_metadata, model_metadata, lora_metadata):
    row = db.execute(
        'SELECT value FROM settings WHERE key=?', (PLAN_PREFIX + selection['plan_id'],)
    ).fetchone()
    if not row:
        raise ValueError('找不到專用比較方案；未提交任務')
    record = json.loads(row[0])
    plan = record['plan']
    variant = next((v for v in plan['variants'] if v['id'] == selection['variant_id']), None)
    if (
        record['archived']
        or plan['plan_sha256'] != selection['plan_sha256']
        or experiment_context.plan_digest(plan) != selection['plan_sha256']
        or plan['workflow_id'] != workflow_id
        or not variant
        or variant['settings'] != settings
    ):
        raise ValueError('流程版本或設定與比較組不同，或方案已封存；未提交任務')
    verify_bindings(db, None, plan['document'], verify_files=False, check_models=True)
    snapshots = reference_metadata or []
    if len(snapshots) != len(plan['document']['input_assets']) or any(
        any(snapshot.get(k) != binding[k] for k in ASSET_KEYS)
        for snapshot, binding in zip(snapshots, plan['document']['input_assets'])
    ):
        raise ValueError('原始輸入素材與比較方案不同；未提交任務')
    registered = plan['document']['registrations']
    enabled = {item['name'] for item in settings['loras'] if item['enabled']}
    if stable_registration(model_metadata, settings['checkpoint']) != registered['checkpoint'] or [
        stable_registration(row, row['name']) for row in (lora_metadata or [])
    ] != [row for row in registered['loras'] if row['name'] in enabled]:
        raise ValueError('模型或 LoRA 在提交期間已變更；未提交任務')
    return experiment_context.snapshot(plan, selection, variant) | dict(
        specialized_registrations=registered
    )


def verify_dispatch(db_path, settings, expected):
    with closing(sqlite3.connect(db_path)) as db:
        db.execute('BEGIN')
        if registrations(db, settings) != expected:
            raise ValueError('模型、LoRA 或控制元件在提交期間已變更；未提交生成')


def install(app, host):
    schemas = {flow: getattr(host, name) for flow, name in FLOW_SCHEMAS.items()}
    draft_schemas = {}
    for flow, schema in schemas.items():
        overrides = {
            key: (field.annotation, field)
            for key, field in schema.model_fields.items()
            if key not in host.DraftInput.model_fields
            or field is not host.DraftInput.model_fields.get(key)
        }
        # Reuse field constraints while postponing the generation-only cross-field checks.
        for key in SELECTION_FIELDS[1:]:
            if key in overrides:
                overrides[key] = (str, Field(max_length=2048))
        if 'mask_asset_id' in overrides:
            overrides['mask_asset_id'] = (UUID | None, None)
        draft_schemas[flow] = create_model(
            schema.__name__ + 'Draft', __base__=host.DraftInput, **overrides
        )

    def checked(flow, settings, *, draft=False):
        if flow not in schemas:
            raise ValueError('未知的專用流程版本')
        schema = schemas[flow]
        if set(settings) != set(schema.model_fields) - {'revision'}:
            raise ValueError('專用設定需完整保存原版本欄位；不接受未知或遺漏的欄位')
        if draft:
            schema = draft_schemas[flow]
        value = schema.model_validate(settings).model_dump(mode='json', exclude={'revision'})
        selected = [value[field] for field in ASSET_FIELDS if value.get(field)]
        if len(set(selected)) != len(selected) or (
            value.get('mask_asset_id') and not value.get('image_asset_id')
        ):
            raise ValueError('原圖與遮罩必須為不同素材')
        expected_refs = selected if 'mask_asset_id' not in value or len(selected) == 2 else []
        if value['reference_ids'] != expected_refs:
            raise ValueError('素材角色與有序 reference_ids 不符')
        if value['width'] * value['height'] > assets.MAX_PIXELS:
            raise ValueError('輸出不可超過 1600 萬像素')
        if not draft and not value['checkpoint']:
            raise ValueError('請先選擇 checkpoint')
        return value

    def snapshot(flow, settings):
        with closing(sqlite3.connect(host.DB)) as db:
            return dict(
                kind='model-atelier-specialized-creation',
                schema_version=1,
                workflow_id=flow,
                settings=settings,
                input_assets=asset_bindings(db, host.DATA, settings),
                registrations=registrations(db, settings),
                source_snapshot=None,
            )

    def validate_document(raw):
        model = Document.model_validate(raw)
        if type(raw['schema_version']) is not int:
            raise ValueError('schema_version 必須是整數 1')
        value = model.model_dump(mode='json')
        for component in value['registrations']['components']:
            component.pop('family' if component['role'] == 'controlnet' else 'kind')
        value['settings'] = checked(model.workflow_id, model.settings, draft=True)
        expected = [
            (role, value['settings'][field])
            for field, role in zip(ASSET_FIELDS, ('source', 'mask'), strict=True)
            if value['settings'].get(field)
        ]
        if [(a['role'], a['id']) for a in value['input_assets']] != expected:
            raise ValueError('素材快照的 ID 或角色與設定不符')
        registrations_document = value['registrations']
        settings = value['settings']
        expected_components = [
            (role, settings[key])
            for role, key in (
                ('controlnet', 'control_net_name'),
                ('ipadapter', 'ipadapter_name'),
                ('clip_vision', 'clip_vision_name'),
            )
            if settings.get(key)
        ]
        if (
            registrations_document['checkpoint']['name'] != settings['checkpoint']
            or [row['name'] for row in registrations_document['loras']]
            != [row['name'] for row in settings['loras']]
            or [(row['role'], row['name']) for row in registrations_document['components']]
            != expected_components
            or any(
                row.get('kind' if row['role'] == 'controlnet' else 'family') is None
                for row in registrations_document['components']
            )
        ):
            raise ValueError('模型或元件快照與設定不符')
        return value

    def warnings(document):
        messages = []
        with closing(sqlite3.connect(host.DB)) as db:
            loadable = True
            try:
                verify_bindings(db, host.DATA, document)
            except (KeyError, ValueError) as exc:
                loadable = False
                messages.append(str(exc))
            if registrations(db, document['settings']) != document['registrations']:
                messages.append('目前模型或元件登記與設定檔快照不同；生成前請確認原引擎與元件。')
        return dict(
            document=document,
            warnings=messages,
            loadable=loadable,
        )

    def plan_from(value):
        document = validate_document(value.document.model_dump(mode='json'))
        flow = document['workflow_id']
        baseline = checked(flow, document['settings'])
        axis = value.axis
        if axis not in ('seed', 'steps', 'cfg', *AXES[flow]):
            raise ValueError('此流程不支援該比較參數')
        variants = []
        for index, raw in enumerate(value.values, 1):
            if (
                (axis == 'seed' and type(raw) is not str)
                or (axis in INTEGER_AXES and type(raw) is not int)
                or (axis != 'seed' and type(raw) not in (int, float))
            ):
                raise ValueError('Seed 需為整數字串；整數欄位及數字欄位須符合原流程')
            settings = checked(flow, baseline | {axis: raw})
            variants.append(
                dict(
                    id=f'variant-{index}',
                    case_id='baseline',
                    value=settings[axis],
                    settings=settings,
                )
            )
        values = [variant['value'] for variant in variants]
        if len(set(values)) != len(values):
            raise ValueError('比較值不可重複')
        result = dict(
            kind='model-atelier-specialized-comparison',
            schema_version=1,
            title=baseline['title'],
            workflow_id=flow,
            baseline=baseline,
            document=document,
            axis=axis,
            values=values,
            variants=variants,
            expected_job_count=len(variants),
            batch_size=1,
        )
        return result | dict(plan_sha256=experiment_context.plan_digest(result))

    def validate_plan(raw):
        if not isinstance(raw, dict):
            raise ValueError('需提供完整專用比較方案')
        value = PlanInput.model_validate(
            {key: raw[key] for key in ('document', 'axis', 'values') if key in raw}
        )
        plan = plan_from(value)
        if plan != raw:
            raise ValueError('比較方案與原始預覽不同；請重新預覽')
        return plan

    @app.post(PREFIX + '/comparisons/import-preview')
    async def import_plan(request: Request):
        def preview(raw):
            plan = validate_plan(raw)
            return dict(plan=plan, **warnings(plan['document']))

        return await read(request, None, preview, limit=MAX_PLAN_BYTES)

    async def read(request, model, action, *, limit=settings_transfer.MAX_BYTES):
        raw = await settings_transfer.read_json(request, max_bytes=limit)
        try:
            return await run_in_threadpool(action, model.model_validate(raw) if model else raw)
        except ValidationError as exc:
            raise HTTPException(422, '專用設定文件欄位或參數格式無效') from exc
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc

    def download(value, name, *, limit=settings_transfer.MAX_BYTES):
        raw = json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False)
        if len(raw.encode()) > limit:
            raise HTTPException(413, '專用文件超過匯出大小上限')
        return Response(
            raw,
            media_type='application/json',
            headers={
                'Content-Disposition': f'attachment; filename="{name}.json"',
                'X-Content-Type-Options': 'nosniff',
            },
        )

    @app.post(PREFIX + '/settings/capture')
    async def capture(request: Request):
        return await read(
            request,
            Capture,
            lambda value: snapshot(
                value.workflow_id, checked(value.workflow_id, value.settings, draft=True)
            ),
        )

    @app.post(PREFIX + '/settings/import-preview')
    async def import_preview(request: Request):
        return await read(request, None, lambda value: warnings(validate_document(value)))

    @app.get(PREFIX + '/drafts')
    def list_drafts(family: Literal['inpaint', 'control', 'reference']):
        identifiers = {f['id'] for f in workflow_support.FLOWS if f['family'] == family}
        return [
            record
            for record in drafts.list_all(host.DB, prefix=DRAFT_PREFIX)
            if record['workflow_id'] in identifiers
        ]

    def save_draft(value, identifier=None):
        if bool(identifier) != (value.revision is not None):
            raise ValueError('更新草稿必須提供讀取時的 revision')
        document = validate_document(value.document.model_dump(mode='json'))
        try:
            with closing(sqlite3.connect(host.DB)) as db:
                verify_bindings(db, host.DATA, document)
            return drafts.save(
                host.DB,
                document,
                identifier,
                value.revision,
                prefix=DRAFT_PREFIX,
                check=lambda db: verify_bindings(db, host.DATA, document, verify_files=False),
            )
        except KeyError as exc:
            raise HTTPException(404, '找不到專用草稿') from exc
        except ValueError as exc:
            raise HTTPException(409, str(exc)) from exc

    @app.post(PREFIX + '/drafts', status_code=201)
    async def create_draft(request: Request):
        return await read(request, DraftSave, save_draft)

    @app.put(PREFIX + '/drafts/{identifier}')
    async def update_draft(identifier: UUID, request: Request):
        return await read(request, DraftSave, lambda value: save_draft(value, str(identifier)))

    @app.post(PREFIX + '/comparisons/preview')
    async def preview_plan(request: Request):
        def preview(value):
            plan = plan_from(value)
            with closing(sqlite3.connect(host.DB)) as db:
                verify_bindings(db, host.DATA, plan['document'], check_models=True)
            return plan

        return await read(request, PlanInput, preview)

    @app.post(PREFIX + '/comparisons', status_code=201)
    async def save_plan(request: Request):
        def save(value):
            plan = validate_plan(value.plan)
            try:
                with closing(sqlite3.connect(host.DB)) as db:
                    verify_bindings(db, host.DATA, plan['document'], check_models=True)
                return experiment_store.save(
                    host.DB,
                    str(value.request_id),
                    plan,
                    prefix=PLAN_PREFIX,
                    check=lambda db: verify_bindings(
                        db, host.DATA, plan['document'], verify_files=False, check_models=True
                    ),
                )[0]
            except ValueError as exc:
                raise HTTPException(409, str(exc)) from exc

        return await read(request, PlanSave, save, limit=MAX_PLAN_BYTES)

    @app.get(PREFIX + '/comparisons')
    def list_plans(family: Literal['inpaint', 'control', 'reference']):
        identifiers = {f['id'] for f in workflow_support.FLOWS if f['family'] == family}
        return [
            row
            for row in experiment_store.summaries(host.DB, prefix=PLAN_PREFIX)
            if row['workflow_id'] in identifiers
        ]

    def plan_record(identifier):
        try:
            return experiment_store.get(host.DB, str(identifier), prefix=PLAN_PREFIX)
        except KeyError as exc:
            raise HTTPException(404, '找不到專用比較方案') from exc

    @app.get(PREFIX + '/comparisons/{identifier}')
    def get_plan(identifier: UUID):
        return plan_record(identifier)

    @app.get(PREFIX + '/comparisons/{identifier}/results')
    def results(identifier: UUID):
        return experiment_results.read(host.DB, plan_record(identifier), host.DATA / 'artworks')

    @app.get(PREFIX + '/comparisons/{identifier}/document')
    def plan_document(identifier: UUID):
        return download(
            plan_record(identifier)['plan'], 'specialized-comparison', limit=MAX_PLAN_BYTES
        )

    @app.put(PREFIX + '/comparisons/{identifier}')
    async def archive_plan(identifier: UUID, request: Request):
        def change(value):
            try:
                return experiment_store.archive(
                    host.DB, str(identifier), value.revision, value.archived, prefix=PLAN_PREFIX
                )
            except KeyError as exc:
                raise HTTPException(404, '找不到專用比較方案') from exc
            except ValueError as exc:
                raise HTTPException(409, str(exc)) from exc

        return await read(request, Archive, change)

    @app.get(PREFIX + '/{kind}/{identifier}/settings')
    def original(kind: Literal['jobs', 'artworks'], identifier: UUID):
        try:
            item = (jobs if kind == 'jobs' else gallery).get(host.DB, str(identifier))
        except KeyError as exc:
            raise HTTPException(404, '找不到原任務或作品') from exc
        flow = item.get('workflow_id')
        if flow not in schemas:
            raise HTTPException(422, '原始設定不屬於專用工作流程')
        if kind == 'jobs' and item['status'] not in ('completed', 'failed', 'stopped', 'cancelled'):
            raise HTTPException(409, '請先確認原任務已終止')
        try:
            settings = workflows.extract(
                item | dict(source=item.get('source') or dict(node_id='7')),
                lambda raw: checked(flow, raw),
            )
            input_assets = [
                dict(role=role, **{k: ref[k] for k in ASSET_KEYS})
                for ref, role in zip(item['reference_metadata'], ('source', 'mask'))
            ]
            model = item.get('model_metadata')
            lora_metadata = {r['name']: r for r in item.get('lora_metadata') or []}
            components = [
                stable_registration(r, r['name'])
                | {key: r[key] for key in ('role', 'kind', 'family') if key in r}
                for r in item.get('component_metadata') or []
            ]
            source = dict(
                kind='job' if kind == 'jobs' else 'artwork',
                id=item['id'],
                model_version=item.get('model_version') or '未知',
                workflow_json=json.dumps(item['workflow'], ensure_ascii=False, allow_nan=False),
            )
            source.update(
                {
                    key: item.get(key)
                    for key in (
                        'model_metadata',
                        'lora_metadata',
                        'component_metadata',
                        'reference_metadata',
                        'runtime_metadata',
                    )
                }
            )
            value = validate_document(
                dict(
                    kind='model-atelier-specialized-creation',
                    schema_version=1,
                    workflow_id=flow,
                    settings=settings,
                    input_assets=input_assets,
                    source_snapshot=source,
                    registrations=dict(
                        checkpoint=stable_registration(model, settings['checkpoint']),
                        loras=[
                            stable_registration(lora_metadata.get(r['name']), r['name'])
                            for r in settings['loras']
                        ],
                        components=components,
                    ),
                )
            )
        except (ValueError, KeyError, TypeError) as exc:
            raise HTTPException(422, '原流程或素材快照無法完整匯出；請下載原工作流程') from exc
        return download(value, 'specialized-' + str(identifier))
