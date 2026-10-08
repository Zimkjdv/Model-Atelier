from typing import Literal
from types import SimpleNamespace
from uuid import UUID
from fastapi import HTTPException
from pydantic import ConfigDict,Field,model_validator
from starlette.concurrency import run_in_threadpool
from backend import jobs,control_catalog,control_workflows as flow


def install(app,host,submissions):
    class Input(host.DraftInput):
        model_config=ConfigDict(extra='forbid')
        workflow_mode:Literal['text2image']='text2image'
        denoise:float=Field(default=1,strict=True,ge=1,le=1)
        control_net_name:str=Field(min_length=1,max_length=2048)
        control_strength:float=Field(default=0.5,strict=True,gt=0,le=10,allow_inf_nan=False)
        control_start:float=Field(default=0,strict=True,ge=0,le=1,allow_inf_nan=False)
        control_end:float=Field(default=1,strict=True,ge=0,le=1,allow_inf_nan=False)
        canny_low:float=Field(default=0.4,strict=True,ge=0.01,le=0.99,allow_inf_nan=False)
        canny_high:float=Field(default=0.8,strict=True,ge=0.01,le=0.99,allow_inf_nan=False)
        @model_validator(mode='after')
        def ordering(self):
            if not self.control_net_name.strip() or not self.image_asset_id or self.reference_ids!=[self.image_asset_id]: raise ValueError('需一張結構參考素材與 ControlNet 名稱')
            if self.control_start>=self.control_end or self.canny_low>=self.canny_high: raise ValueError('起始／低閾值必須小於結束／高閾值')
            return self
    host.ControlInput=Input
    class Generate(Input): request_id:UUID
    @app.get('/api/control/workflow')
    def descriptor():
        return dict(id=flow.ID,name='Canny 結構參考',architectures=['sd1','sdxl'],image_count=1,lora=True,implemented=True,preprocessor='ComfyUI native Canny',batch_size=1,denoise=1,comparison=False)
    @app.post('/api/control/generate')
    async def generate(value:Generate):
        settings=value.model_dump(mode='json',exclude={'request_id','revision'})
        async with submissions.job_lock(value.request_id):
            try: existing=jobs.get(host.DB,str(value.request_id))
            except KeyError: existing=None
            if existing is not None:
                if existing.get('workflow_id')!=flow.ID or existing.get('reference_settings')!=settings or existing.get('experiment_context') is not None: raise HTTPException(409,'此 UUID 已用於不同的結構參考設定')
                return existing
            if not value.checkpoint: raise HTTPException(422,'請選擇 checkpoint')
            if value.engine_url!=host.engine_url(): raise HTTPException(409,'引擎設定已變更，請連接原引擎')
            library=control_catalog.read(host.DB,value.engine_url)
            record=next((r for r in library['controlnets'] if r['name']==value.control_net_name),None)
            if not record: raise HTTPException(422,'請先同步及登記 ControlNet 的架構與類型')
            try: snapshot,encoded=await run_in_threadpool(flow.prepare,host.DB,host.DATA,settings)
            except ValueError as exc: raise HTTPException(422,str(exc)) from exc
            components=[control_catalog.capture(record)]
            def recheck(job): control_catalog.recheck(host.DB,value.engine_url,value.checkpoint,job['component_metadata'],job['model_metadata'])
            submission=SimpleNamespace(request_id=value.request_id,engine_url=value.engine_url,checkpoint=value.checkpoint,workflow=flow.build(settings,value.request_id))
            return await submissions.submit_locked(submission,reference=dict(settings=settings,snapshot=snapshot,encoded=encoded,adapter=flow,workflow_id=flow.ID,component_metadata=components,recheck=recheck))
