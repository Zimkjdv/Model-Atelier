"""Checkpoint text-to-image API and pinned-engine job reconciliation."""
import json
from uuid import UUID
import httpx
from fastapi import HTTPException, Response
from pydantic import BaseModel, Field, field_validator
from backend import jobs


class Submission(BaseModel):
    request_id: UUID
    engine_url: str
    checkpoint: str = Field(min_length=1, max_length=2048)
    workflow: dict = Field(min_length=1, max_length=64)

    @field_validator('workflow')
    @classmethod
    def validate_workflow(cls, value):
        if len(json.dumps(value, allow_nan=False).encode()) > 2_000_000:
            raise ValueError('工作流程不可超過 2 MiB')
        allowed = {'CheckpointLoaderSimple', 'CLIPTextEncode', 'EmptyLatentImage', 'KSampler', 'VAEDecode', 'SaveImage'}
        for node in value.values():
            if not isinstance(node, dict) or node.get('class_type') not in allowed or not isinstance(node.get('inputs'), dict):
                raise ValueError('第一版僅接受標準 checkpoint 文生圖 API 工作流程，不支援自訂節點')
            if node['class_type'] == 'SaveImage' and node['inputs'].get('filename_prefix') != 'ModelAtelier':
                raise ValueError('輸出檔名前綴必須為 ModelAtelier')
        return value


def install(app, host):
    class Generate(host.DraftInput):
        request_id: UUID

    def lookup(job_id):
        try:
            return jobs.get(host.DB, str(job_id))
        except KeyError:
            raise HTTPException(404, '找不到任務')

    async def submit(value):
        if value.engine_url != host.engine_url():
            raise HTTPException(409, '引擎設定已變更，請重新載入模型庫')
        loaders = [n['inputs'].get('ckpt_name') for n in value.workflow.values() if n['class_type'] == 'CheckpointLoaderSimple']
        if not loaders or any(name != value.checkpoint for name in loaders):
            raise HTTPException(422, '工作流程 checkpoint 與選擇的模型不一致')
        try:
            job, fresh = jobs.reserve(host.DB, str(value.request_id), value.engine_url, value.workflow, value.checkpoint)
        except ValueError as exc:
            raise HTTPException(409, str(exc))
        if not fresh:
            return job
        job_id = job['id']
        def fail(code, message, **extra):
            jobs.update(host.DB, job_id, status='failed', error=message, **extra)
            raise HTTPException(code, {'message': message, 'job_id': job_id})
        async with httpx.AsyncClient(timeout=15, trust_env=False) as client:
            try:
                response = await client.get(value.engine_url + '/object_info/CheckpointLoaderSimple')
                response.raise_for_status()
                names = response.json()['CheckpointLoaderSimple']['input']['required']['ckpt_name'][0]
                if not isinstance(names, list) or not all(isinstance(n, str) for n in names):
                    raise ValueError('invalid checkpoint list')
            except httpx.RequestError:
                fail(503, 'ComfyUI 離線或連線逾時，尚未提交任務')
            except (httpx.HTTPStatusError, KeyError, IndexError, TypeError, ValueError):
                fail(502, 'ComfyUI 模型清單格式無效，尚未提交任務')
            if not names:
                fail(409, 'ComfyUI 尚未安裝任何 checkpoint，請先安裝模型並同步模型庫')
            if value.checkpoint not in names:
                fail(409, '所選 checkpoint 已不存在，請重新同步模型庫')
            jobs.update(host.DB, job_id, status='submitting')
            try:
                response = await client.post(value.engine_url + '/prompt', json={
                    'prompt': value.workflow, 'prompt_id': job_id, 'client_id': job_id,
                    'extra_data': {'model_atelier_job_id': job_id}})
                if response.status_code == 400:
                    fail(422, 'ComfyUI 拒絕工作流程，請檢查節點與模型相容性', upstream_error=response.json())
                response.raise_for_status()
                result = response.json()
                prompt_id = str(UUID(result['prompt_id']))
            except (httpx.RequestError, httpx.HTTPStatusError, ValueError, KeyError, TypeError):
                return jobs.update(host.DB, job_id, status='unknown', error='提交結果待確認；請查詢狀態，不要重新生成')
            return jobs.update(host.DB, job_id, status='queued', prompt_id=prompt_id, submission=result)

    async def submit_endpoint(value: Submission):
        return await submit(value)
    app.post('/api/jobs')(submit_endpoint)

    @app.post('/api/generate')
    async def generate(value: Generate):
        if value.reference_ids:
            raise HTTPException(422, '第一版文生圖尚未套用參考素材，請先取消素材選取')
        if not value.checkpoint:
            raise HTTPException(422, '請先選擇 checkpoint')
        workflow = {
            '1': {'class_type': 'CheckpointLoaderSimple', 'inputs': {'ckpt_name': value.checkpoint}},
            '2': {'class_type': 'CLIPTextEncode', 'inputs': {'text': value.prompt, 'clip': ['1', 1]}},
            '3': {'class_type': 'CLIPTextEncode', 'inputs': {'text': '', 'clip': ['1', 1]}},
            '4': {'class_type': 'EmptyLatentImage', 'inputs': {'width': value.width, 'height': value.height, 'batch_size': 1}},
            '5': {'class_type': 'KSampler', 'inputs': {'model': ['1', 0], 'positive': ['2', 0], 'negative': ['3', 0], 'latent_image': ['4', 0], 'seed': int(value.seed), 'steps': 20, 'cfg': 7.0, 'sampler_name': 'euler', 'scheduler': 'normal', 'denoise': 1.0}},
            '6': {'class_type': 'VAEDecode', 'inputs': {'samples': ['5', 0], 'vae': ['1', 2]}},
            '7': {'class_type': 'SaveImage', 'inputs': {'images': ['6', 0], 'filename_prefix': 'ModelAtelier'}},
        }
        return await submit(Submission(request_id=value.request_id, engine_url=value.engine_url, checkpoint=value.checkpoint, workflow=workflow))

    @app.get('/api/jobs')
    def history():
        return [{k: v for k, v in job.items() if k not in ('workflow', 'history', 'submission', 'upstream_error')} for job in jobs.list_all(host.DB)]

    @app.get('/api/jobs/{job_id}')
    def detail(job_id: UUID):
        return lookup(job_id)

    @app.get('/api/jobs/{job_id}/workflow')
    def workflow(job_id: UUID):
        return Response(json.dumps(lookup(job_id)['workflow'], ensure_ascii=False, indent=2), media_type='application/json', headers={'Content-Disposition': f'attachment; filename="{job_id}.json"'})

    @app.post('/api/jobs/{job_id}/refresh')
    async def refresh(job_id: UUID):
        job = lookup(job_id)
        if job['status'] in ('completed', 'failed'):
            return job
        try:
            async with httpx.AsyncClient(timeout=10, trust_env=False) as client:
                response = await client.get(job['engine_url'] + '/history/' + job['prompt_id'])
                response.raise_for_status()
                data = response.json()
                if not isinstance(data, dict):
                    raise ValueError()
                entry = data.get(job['prompt_id'])
                if entry:
                    state = entry['status']
                    status = 'failed' if state.get('status_str') == 'error' else 'completed' if state.get('completed') is True else 'unknown'
                    return jobs.update(host.DB, str(job_id), status=status, history=entry, error='ComfyUI 執行失敗，請查看任務 JSON' if status == 'failed' else None)
                response = await client.get(job['engine_url'] + '/queue')
                response.raise_for_status()
                queue = response.json()
                for key, state in [('queue_running', 'running'), ('queue_pending', 'queued')]:
                    if not isinstance(queue[key], list):
                        raise ValueError()
                    for item in queue[key]:
                        if item[1] == job['prompt_id'] or (isinstance(item[3], dict) and item[3].get('model_atelier_job_id') == job['id']):
                            return jobs.update(host.DB, str(job_id), status=state, prompt_id=str(UUID(item[1])), error=None)
                return jobs.update(host.DB, str(job_id), status='unknown', error='引擎佇列與歷史中找不到任務；可能已清除或重啟，請勿自動重送')
        except (httpx.HTTPError, ValueError, KeyError, IndexError, TypeError):
            raise HTTPException(503, '無法查詢原 ComfyUI 引擎；已保留任務原狀態與工作流程')
