"""Dedicated versioned reference endpoint; original UUID recovery precedes live checks."""

from types import SimpleNamespace
from typing import Literal
from uuid import UUID

from fastapi import HTTPException
from pydantic import ConfigDict, Field, model_validator
from starlette.concurrency import run_in_threadpool

from backend import adapter_catalog as records, adapter_workflows as flow, diagnostics, jobs


def install(app, host, submissions):
    class Input(host.DraftInput):
        model_config = ConfigDict(extra='forbid')
        workflow_mode: Literal['text2image'] = 'text2image'
        denoise: float = Field(default=1, strict=True, ge=1, le=1)
        reference_resize: Literal['fit'] = 'fit'
        loras: list = Field(default_factory=list, max_length=0)
        reference_mode: Literal['style', 'character']
        ipadapter_name: str = Field(min_length=1, max_length=2048)
        clip_vision_name: str = Field(min_length=1, max_length=2048)
        reference_weight: float = Field(default=0.6, strict=True, ge=0, le=2, allow_inf_nan=False)
        reference_start: float = Field(default=0, strict=True, ge=0, le=1, allow_inf_nan=False)
        reference_end: float = Field(default=1, strict=True, ge=0, le=1, allow_inf_nan=False)

        @model_validator(mode='after')
        def valid_reference(self):
            if (
                not self.image_asset_id
                or self.reference_ids != [self.image_asset_id]
                or not self.ipadapter_name.strip()
                or not self.clip_vision_name.strip()
            ):
                raise ValueError('需一張參考素材及 adapter／編碼器')
            if self.reference_start >= self.reference_end or self.width * self.height > 16_000_000:
                raise ValueError('作用起始需小於結束，輸出不可超過 1600 萬像素')
            return self

    host.ReferenceInput = Input

    class Generate(Input):
        request_id: UUID

    @app.get('/api/reference/workflow')
    def descriptor():
        return dict(
            id=flow.ID,
            name='SDXL 畫風／角色外觀參考',
            implemented=True,
            architectures=['sdxl'],
            image_count=1,
            lora=False,
            modes=['style', 'character'],
            preprocessing=dict(
                id='ipadapter-square-input',
                version=1,
                width=224,
                height=224,
                resize='fit',
                background='#ffffff',
            ),
            node_version=None,
            tested_node_revision='a0f451a5113cf9becb0847b92884cb10cbdec0ef',
        )

    @app.post('/api/reference/generate')
    async def generate(value: Generate):
        diagnostics.bind_submission(value.request_id, flow.ID)
        settings = value.model_dump(mode='json', exclude={'request_id', 'revision'})
        async with submissions.job_lock(value.request_id):
            try:
                existing = jobs.get(host.DB, str(value.request_id))
            except KeyError:
                existing = None
            if existing is not None:
                if (
                    existing.get('workflow_id') != flow.ID
                    or existing.get('reference_settings') != settings
                    or existing.get('experiment_context') is not None
                ):
                    raise HTTPException(409, '此 UUID 已用於不同參考流程設定')
                diagnostics.record_job('submission_recovered', existing)
                return existing
            if not value.checkpoint:
                raise HTTPException(422, '請選擇 SDXL checkpoint')
            if value.engine_url != host.engine_url():
                raise HTTPException(409, '引擎設定已變更，請連接原引擎')
            library = records.read(host.DB, value.engine_url)
            components = []
            for role, name in [
                ('ipadapter', value.ipadapter_name),
                ('clip_vision', value.clip_vision_name),
            ]:
                record = next(
                    (r for r in library['components'] if r['role'] == role and r['name'] == name),
                    None,
                )
                if record is None:
                    raise HTTPException(422, '請先同步並登記 adapter 與 ViT-H 編碼器')
                components.append(records.capture(record))
            try:
                snapshot, encoded = await run_in_threadpool(
                    flow.prepare, host.DB, host.DATA, settings
                )
            except ValueError as exc:
                raise HTTPException(422, str(exc)) from exc

            def recheck(job):
                records.recheck(
                    host.DB,
                    value.engine_url,
                    value.checkpoint,
                    job['component_metadata'],
                    job['model_metadata'],
                )

            submission = SimpleNamespace(
                request_id=value.request_id,
                engine_url=value.engine_url,
                checkpoint=value.checkpoint,
                workflow=flow.build(settings, value.request_id),
            )
            return await submissions.submit_locked(
                submission,
                reference=dict(
                    settings=settings,
                    snapshot=snapshot,
                    encoded=encoded,
                    adapter=flow,
                    workflow_id=flow.ID,
                    component_metadata=components,
                    recheck=recheck,
                ),
            )
