"""Inpainting has a separate schema; existing drafts and comparison files stay unchanged."""
from typing import Literal
from types import SimpleNamespace
from uuid import UUID
from fastapi import HTTPException
from fastapi.responses import FileResponse
from pydantic import ConfigDict,Field,model_validator
from starlette.concurrency import run_in_threadpool
from backend import jobs,inpaint_workflows


def install(app,host,submissions):
    class Input(host.DraftInput):
        model_config=ConfigDict(extra='forbid')
        workflow_mode:Literal['image2image']='image2image'
        mask_asset_id:UUID
        grow_mask_by:int=Field(default=6,strict=True,ge=0,le=64)
        @model_validator(mode='after')
        def references(self):
            if not self.image_asset_id or self.mask_asset_id==self.image_asset_id or self.reference_ids!=[self.image_asset_id,self.mask_asset_id]:
                raise ValueError('需不同原圖與遮罩，且 reference_ids 依序包含這兩張素材')
            return self
    host.InpaintInput=Input
    class Generate(Input):
        request_id:UUID

    @app.get('/api/inpaint/workflow')
    def description():
        return dict(id=inpaint_workflows.ID,name='Checkpoint 局部編輯',architectures=['sd1','sdxl'],image_count=2,
            implemented=True,lora=True,mask=dict(channel='red',threshold=128,white='edit',black='preserve'),
            max_pixels=16_000_000,batch_size=1,comparison=False)

    @app.post('/api/inpaint/generate')
    async def generate(value:Generate):
        settings=value.model_dump(mode='json',exclude={'request_id','revision'})
        async with submissions.job_lock(value.request_id):
            try: existing=jobs.get(host.DB,str(value.request_id))
            except KeyError: existing=None
            if existing is not None:
                if existing.get('workflow_id')!=inpaint_workflows.ID or existing.get('reference_settings')!=settings or existing.get('experiment_context') is not None:
                    raise HTTPException(409,'此請求 ID 已用於不同局部編輯設定')
                return existing
            if not value.checkpoint: raise HTTPException(422,'請先選擇 checkpoint')
            if value.engine_url!=host.engine_url(): raise HTTPException(409,'引擎設定已變更，請確認原引擎')
            try: snapshots,encoded=await run_in_threadpool(inpaint_workflows.prepare,host.DB,host.DATA,settings)
            except ValueError as exc: raise HTTPException(422,str(exc)) from exc
            submission=SimpleNamespace(request_id=value.request_id,engine_url=value.engine_url,checkpoint=value.checkpoint,
                workflow=inpaint_workflows.build(settings,value.request_id))
            return await submissions.submit_locked(submission,reference=dict(settings=settings,snapshots=snapshots,encoded=encoded,
                workflow_id=inpaint_workflows.ID,adapter=inpaint_workflows))

    @app.get('/api/jobs/{job_id}/reference-mask')
    def mask(job_id:UUID):
        try: job=jobs.get(host.DB,str(job_id))
        except KeyError: raise HTTPException(404,'找不到任務')
        if job.get('workflow_id')!=inpaint_workflows.ID: raise HTTPException(404,'此任務沒有局部編輯遮罩')
        path=host.DATA/'job_inputs'/(str(job_id)+'.mask.png')
        if not path.is_file(): raise HTTPException(404,'原遮罩尚未保存或檔案遺失')
        return FileResponse(path,media_type='image/png',headers={'X-Content-Type-Options':'nosniff'})
