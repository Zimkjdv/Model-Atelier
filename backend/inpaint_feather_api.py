"""Preview is CPU-only and ephemeral; generation is a separately admitted UUID."""
import hashlib
import io
from uuid import UUID
from fastapi import HTTPException,Response
from pydantic import Field
from PIL import Image
from starlette.concurrency import run_in_threadpool
from backend import inpaint_feather_workflows as flow,jobs,fooocus_workflows


def install(app,host,submissions):
    class Input(host.InpaintInput):
        feather_radius:int=Field(default=0,strict=True,ge=0,le=64)
    host.InpaintFeatherInput=Input
    class Generate(Input): request_id:UUID
    def validate(value): return Input.model_validate(value).model_dump(mode='json',exclude={'revision'})
    @app.get('/api/inpaint-feather/workflow')
    def description():
        return dict(id=flow.ID,name='Checkpoint 內側羽化局部編輯',architectures=['sd1','sdxl'],image_count=2,prepared_input_count=3,
            implemented=True,lora=True,mask=dict(channel='red',threshold=128,white='edit',black='preserve'),
            feather=dict(min=0,max=64,unit='output-pixels',default=0,method='inner-gaussian-threshold'),max_pixels=16_000_000,batch_size=1,comparison=False)
    @app.post('/api/inpaint-feather/generate')
    async def generate(value:Generate): return await submissions.submit(value,flow)
    @app.post('/api/inpaint-feather/preview')
    async def preview(value:Input):
        try: refs,encoded=await run_in_threadpool(flow.prepare,host.DB,host.DATA,value.model_dump(mode='json',exclude={'revision'}))
        except ValueError as exc: raise HTTPException(422,str(exc)) from exc
        prep=refs[1]['blend_preprocessing']
        return Response(encoded['blend'],media_type='image/png',headers={'Cache-Control':'no-store','X-Content-Type-Options':'nosniff',
            'X-Atelier-SHA256':prep['sha256'],'X-Atelier-Width':str(prep['width']),'X-Atelier-Height':str(prep['height']),'X-Atelier-Feather-Radius':str(prep['radius'])})
    @app.get('/api/jobs/{job_id}/reference-blend-mask')
    def blend_mask(job_id:UUID,download:bool=False):
        try: job=jobs.get(host.DB,str(job_id))
        except KeyError: raise HTTPException(404,'找不到任務')
        if job.get('workflow_id') not in (flow.ID,fooocus_workflows.ID): raise HTTPException(404,'舊版任務沒有獨立合成遮罩，不重新計算')
        try:
            adapter=fooocus_workflows if job['workflow_id']==fooocus_workflows.ID else flow
            checked=(lambda value:host.FooocusInput.model_validate(value).model_dump(mode='json',exclude={'revision'})) if adapter is fooocus_workflows else validate
            adapter.extract(dict(job,source=dict(node_id='7')),checked)
            prep=job['reference_metadata'][1]['blend_preprocessing'];path=flow.input_path(host.DATA,job_id,'blend')
            if not path.is_file(): raise FileNotFoundError()
            if path.stat().st_size!=prep['size'] or path.stat().st_size>flow.MAX_BYTES: raise ValueError('合成遮罩大小不符；請從備份還原')
            with path.open('rb') as stream: raw=stream.read(flow.MAX_BYTES+1)
            if hashlib.sha256(raw).hexdigest()!=prep['sha256']: raise ValueError('合成遮罩 SHA256 不符；請從備份還原')
            with Image.open(io.BytesIO(raw)) as image:
                if image.format!='PNG' or image.mode!='RGB' or image.size!=(prep['width'],prep['height']) or getattr(image,'n_frames',1)!=1: raise ValueError('合成遮罩格式不同')
                image.verify()
        except FileNotFoundError: raise HTTPException(404,'原合成遮罩尚未保存或遺失，請從備份還原；不重新計算')
        except (ValueError,OSError) as exc: raise HTTPException(409,str(exc)) from exc
        headers={'X-Content-Type-Options':'nosniff'}
        if download: headers['Content-Disposition']='attachment; filename="blend-'+str(job_id)+'.png"'
        return Response(raw,media_type='image/png',headers=headers)
