"""Explicit read-only output import, never a generation or on-demand GET fetch."""
import asyncio
import sqlite3
from uuid import UUID
import httpx
from fastapi import HTTPException,Response
from starlette.concurrency import run_in_threadpool
from backend import control_edges as edges,jobs,gallery


def install(app,host):
    lock=asyncio.Lock()
    def lookup(identifier):
        try: return jobs.get(host.DB,str(identifier))
        except KeyError: raise HTTPException(404,'找不到原任務')
    def validate(value): return host.ControlInput.model_validate(value).model_dump(mode='json',exclude={'revision'})
    def read(job):
        try: return edges.summary(host.DB,host.DATA,job,validate)
        except (ValueError,OSError) as exc: raise HTTPException(409,str(exc)) from exc
    @app.get('/api/jobs/{job_id}/control-edge')
    def detail(job_id:UUID): return read(lookup(job_id))
    @app.get('/api/jobs/{job_id}/control-edge/image')
    def image(job_id:UUID,download:bool=False):
        item=read(lookup(job_id))
        if not item['image_available']: raise HTTPException(404,item['message'])
        try: raw=edges.checked_raw(host.DATA,item)
        except (OSError,ValueError) as exc: raise HTTPException(409,str(exc)) from exc
        headers={'X-Content-Type-Options':'nosniff'}
        if download: headers['Content-Disposition']='attachment; filename="canny-'+str(job_id)+'.png"'
        return Response(raw,media_type='image/png',headers=headers)
    @app.post('/api/jobs/{job_id}/control-edge')
    async def import_edge(job_id:UUID):
        async with lock:
            job=lookup(job_id);item=await run_in_threadpool(read,job)
            if item['state']=='saved': return item|dict(imported=False)
            if item['state']=='unavailable': raise HTTPException(409,item['message'])
            try: anchors,source=edges.source(job,validate)
            except ValueError as exc: raise HTTPException(409,str(exc)) from exc
            try:
                async with httpx.AsyncClient(timeout=30,trust_env=False,follow_redirects=False) as client:
                    async with client.stream('GET',job['engine_url']+'/view',params={k:source[k] for k in ('filename','subfolder','type')}) as response:
                        if response.status_code==404: raise HTTPException(404,'原引擎邊緣輸出已遺失，不會重新生成。')
                        response.raise_for_status();raw=bytearray()
                        async for chunk in response.aiter_bytes(chunk_size=64*1024):
                            if len(raw)+len(chunk)>edges.MAX_BYTES: raise ValueError('邊緣輸出超過 32 MiB')
                            raw.extend(chunk)
                _,created=await run_in_threadpool(edges.save,host.DB,host.DATA,job,anchors,source,bytes(raw))
            except httpx.HTTPError as exc: raise HTTPException(502,'無法讀取原引擎邊緣 PNG；請確認原引擎，尚未保存，也不會生成新任務。') from exc
            except ValueError as exc: raise HTTPException(422,str(exc)) from exc
            except (OSError,sqlite3.Error) as exc: raise HTTPException(507,'邊緣圖保存失敗，請檢查磁碟／備份；不覆寫已有檔案。') from exc
            return await run_in_threadpool(read,job)|dict(imported=created)
    @app.get('/api/artworks/{artwork_id}/control-edge')
    def artwork_detail(artwork_id:UUID):
        try: artwork=gallery.get(host.DB,str(artwork_id))
        except KeyError: raise HTTPException(404,'找不到作品')
        job=lookup(artwork['job_id'])
        if artwork.get('workflow_id')!=job.get('workflow_id') or artwork.get('workflow')!=job.get('workflow'): raise HTTPException(409,'作品與原任務的工作流程不同')
        return read(job)
