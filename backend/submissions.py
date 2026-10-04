"""Checkpoint text-to-image API and pinned-engine job reconciliation."""
import json
import asyncio
from datetime import datetime, timedelta, timezone
from weakref import WeakValueDictionary
from uuid import UUID
import httpx
from fastapi import HTTPException, Response
from pydantic import BaseModel, Field, field_validator
from backend import jobs, catalog, workflows, cancellation, progress, capabilities, model_profiles, failures, node_preflight
from backend import lora_preflight, lora_records, stopping, flux_workflows


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
        allowed = {'CheckpointLoaderSimple', 'CLIPTextEncode', 'EmptyLatentImage', 'KSampler', 'VAEDecode', 'SaveImage', 'LoraLoader'}
        for node in value.values():
            if (not isinstance(node, dict) or not isinstance(node.get('class_type'), str)
                    or node['class_type'] not in allowed or not isinstance(node.get('inputs'), dict)):
                raise ValueError('第一版僅接受標準 checkpoint 文生圖 API 工作流程，不支援自訂節點')
            if node['class_type'] == 'SaveImage' and node['inputs'].get('filename_prefix') != 'ModelAtelier':
                raise ValueError('輸出檔名前綴必須為 ModelAtelier')
        return value


def install(app, host):
    locks = WeakValueDictionary()

    def job_lock(job_id):
        return locks.setdefault(str(job_id), asyncio.Lock())

    class Generate(host.DraftInput):
        request_id: UUID

    def lookup(job_id):
        try:
            return jobs.get(host.DB, str(job_id))
        except KeyError:
            raise HTTPException(404, '找不到任務')

    async def submit(value):
        async with job_lock(value.request_id):
            return await submit_locked(value)

    async def submit_locked(value):
        # Recovery is pinned to the recorded request, including after changing
        # the current engine. Never probe fresh capabilities or replay an old ID.
        try:
            existing = jobs.get(host.DB, str(value.request_id))
        except KeyError:
            pass
        else:
            if any(existing[name] != getattr(value, name) for name in ('engine_url', 'checkpoint', 'workflow')):
                raise HTTPException(409, '此請求 ID 已用於其他工作流程')
            return existing
        if value.engine_url != host.engine_url():
            raise HTTPException(409, '引擎設定已變更，請重新載入模型庫')
        loaders = [n['inputs'].get('ckpt_name') for n in value.workflow.values() if n['class_type'] == 'CheckpointLoaderSimple']
        if not loaders or any(name != value.checkpoint for name in loaders):
            raise HTTPException(422, '工作流程 checkpoint 與選擇的模型不一致')
        lora_nodes = [node for node in value.workflow.values() if node['class_type'] == 'LoraLoader']
        choices = []
        if lora_nodes:
            # Raw workflows with LoRA must be the entire supported template.
            outputs = [node_id for node_id, node in value.workflow.items() if node['class_type'] == 'SaveImage']
            try:
                if len(outputs) != 1:
                    raise ValueError('LoRA 流程需唯一輸出')
                settings = workflows.extract(dict(workflow=value.workflow, checkpoint=value.checkpoint,
                    engine_url=value.engine_url, source={'node_id': outputs[0]}, title='LoRA 提交'),
                    lambda data: host.DraftInput.model_validate(data).model_dump(), allow_lora=True)
                choices = settings['loras']
            except (ValueError, IndexError) as exc:
                raise HTTPException(422, '僅支援最多四個 LoRA 的完整有序文生圖模板；未提交任務') from exc
        try:
            model = next((m for m in catalog.read(host.DB, value.engine_url)['models'] if m['name'] == value.checkpoint), {})
            lora_metadata = []
            if choices:
                model, registered = lora_preflight.registrations(host.DB, value.engine_url, value.checkpoint, choices)
                lora_metadata = [lora_records.capture(record, choice) for choice, record, _ in registered]
            metadata = catalog.capture(model, value.checkpoint)
            job, fresh = jobs.reserve(host.DB, str(value.request_id), value.engine_url, value.workflow,
                                      value.checkpoint, metadata['version'], metadata, lora_metadata)
        except ValueError as exc:
            raise HTTPException(409, str(exc))
        if not fresh:
            return job
        job_id = job['id']
        def fail(code, message, failure_code='preflight_invalid', failure_info=None, **extra):
            diagnostic = failure_info or failures.info(failure_code)
            _, changed = jobs.compare_update(host.DB, job, status='failed', error=message, failure_info=diagnostic, **extra)
            if not changed:
                raise HTTPException(409, '任務狀態已由另一個請求更新，請重新查詢；未覆蓋新狀態或失敗原因')
            raise HTTPException(code, {'message': message, 'job_id': job_id, 'failure_info': diagnostic})
        initial_compatibility = model_profiles.compatibility(metadata.get('architecture'))
        if not initial_compatibility['allows_submission']:
            fail(422, initial_compatibility['message'], 'unsupported_architecture')
        for choice in choices:
            _, _, assessment = lora_preflight.registration(host.DB, value.engine_url, value.checkpoint, choice['name'])
            if assessment['status'] == 'incompatible':
                fail(422, assessment['label'] + '；' + assessment['message'], 'unsupported_architecture')
        async with httpx.AsyncClient(timeout=15, trust_env=False) as client:
            try:
                response = await client.get(value.engine_url + '/object_info/CheckpointLoaderSimple')
                response.raise_for_status()
                names = response.json()['CheckpointLoaderSimple']['input']['required']['ckpt_name'][0]
                if not isinstance(names, list) or not all(isinstance(n, str) for n in names):
                    raise ValueError('invalid checkpoint list')
            except httpx.RequestError:
                fail(503, 'ComfyUI 離線或連線逾時，尚未提交任務', 'engine_offline')
            except (httpx.HTTPStatusError, KeyError, IndexError, TypeError, ValueError):
                fail(502, 'ComfyUI 模型清單格式無效，尚未提交任務')
            if not names:
                fail(409, 'ComfyUI 尚未安裝任何 checkpoint，請先安裝模型並同步模型庫', 'no_checkpoints')
            if value.checkpoint not in names:
                fail(409, '所選 checkpoint 已不存在，請重新同步模型庫', 'checkpoint_missing')
            try:
                live = await capabilities.fetch(client, value.engine_url)
                capabilities.write(host.DB, value.engine_url, live)
            except httpx.RequestError:
                fail(503, 'ComfyUI 取樣能力離線或查詢逾時，尚未提交任務；快照不能用於提交驗證', 'engine_offline')
            except httpx.HTTPStatusError as exc:
                status = exc.response.status_code
                fail(503 if status >= 500 else 502, f'無法讀取 ComfyUI KSampler 能力（HTTP {status}），尚未提交任務')
            except ValueError:
                fail(502, 'ComfyUI KSampler 能力格式無效或不相容，尚未提交任務')
            try:
                capabilities.validate_workflow(value.workflow, live)
            except ValueError as exc:
                fail(422, '工作流程參數未通過平台與原引擎能力驗證，尚未提交任務', preflight_error=str(exc))
            try:
                if choices:
                    await lora_preflight.check_many(client, value.engine_url, choices)
                await node_preflight.check(client, value.engine_url, value.workflow, checked=('LoraLoader',) if choices else ())
            except node_preflight.MissingNodes as exc:
                fail(422, str(exc), 'missing_nodes')
            except httpx.RequestError:
                fail(503, '必要節點檢查連線失敗，尚未提交任務', 'engine_offline')
            except LookupError as exc:
                fail(409, str(exc))
            except ArithmeticError as exc:
                fail(422, str(exc))
            except (httpx.HTTPStatusError, ValueError):
                fail(502, '無法取得有效的必要節點定義，尚未提交任務')
            if value.engine_url != host.engine_url():
                fail(409, '驗證期間引擎設定已變更，尚未提交任務；請重新載入模型庫與能力清單', 'engine_changed')
            # Metadata may change while fresh capabilities are being fetched.
            # Recheck registered architecture without replacing the immutable
            # submission snapshot or silently applying a suggested preset.
            current_model = next((model for model in catalog.read(host.DB, value.engine_url)['models']
                                  if model['name'] == value.checkpoint), {})
            current_compatibility = model_profiles.compatibility(current_model.get('architecture'))
            if not current_compatibility['allows_submission']:
                fail(422, '驗證期間模型架構登記已變更，尚未提交任務；' + current_compatibility['message'], 'unsupported_architecture')
            warnings = []
            _, registered = lora_preflight.registrations(host.DB, value.engine_url, value.checkpoint, choices)
            for choice, _, assessment in registered:
                if assessment['status'] == 'incompatible':
                    fail(422, '驗證期間架構登記已變更；' + assessment['message'], 'unsupported_architecture')
                warnings.append(choice['name'] + '：' + assessment['message'])
            if choices:
                if len(choices) > 1:
                    warnings.append('多 LoRA 的有序串接尚未實機驗證；不沿用單一 LoRA 的品質或資源紀錄。')
                job = cancellation.persist(host, job, preflight_warnings=warnings)
            job = cancellation.persist(host, job, status='submitting')
            try:
                response = await client.post(value.engine_url + '/prompt', json={
                    'prompt': value.workflow, 'prompt_id': job_id, 'client_id': job_id,
                    'extra_data': {'model_atelier_job_id': job_id}})
                if response.status_code == 400:
                    try:
                        rejected = response.json()
                    except ValueError:
                        rejected = dict(http_status=400, body=response.text)
                    fail(422, 'ComfyUI 拒絕工作流程，請檢查節點與模型相容性',
                         failure_info=failures.from_rejection(job, rejected), upstream_error=rejected)
                response.raise_for_status()
                result = response.json()
                prompt_id = str(UUID(result['prompt_id']))
            except (httpx.RequestError, httpx.HTTPStatusError, ValueError, KeyError, TypeError):
                return jobs.compare_update(host.DB, job, status='unknown', error='提交結果待確認；請查詢狀態，不要重新生成')[0]
            return jobs.compare_update(host.DB, job, status='queued', prompt_id=prompt_id, submission=result)[0]

    async def submit_endpoint(value: Submission):
        return await submit(value)
    app.post('/api/jobs')(submit_endpoint)

    @app.post('/api/generate')
    async def generate(value: Generate):
        if value.reference_ids:
            raise HTTPException(422, '第一版文生圖尚未套用參考素材，請先取消素材選取')
        if not value.checkpoint:
            raise HTTPException(422, '請先選擇 checkpoint')
        workflow = workflows.build(value.model_dump())
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

    @app.get('/api/jobs/{job_id}/creation-settings')
    def creation_settings(job_id: UUID):
        job = lookup(job_id)
        if job['status'] != 'failed':
            raise HTTPException(409, '僅可載入已確認失敗任務的原設定；未提交或重送任何任務')
        outputs = [node_id for node_id, node in job['workflow'].items()
                   if isinstance(node, dict) and node.get('class_type') == 'SaveImage']
        if len(outputs) != 1:
            raise HTTPException(422, '此任務工作流程無法完整還原到目前創作表單，請下載原工作流程使用；未載入任何參數')
        item = dict(workflow=job['workflow'], checkpoint=job['checkpoint'], engine_url=job['engine_url'],
                    source={'node_id': outputs[0]}, title='失敗任務設定')
        def validate(value):
            return host.DraftInput.model_validate(value).model_dump(mode='json', exclude={'revision'})
        try:
            settings = workflows.extract(item, validate)
        except ValueError as exc:
            raise HTTPException(422, str(exc))
        original = catalog.read(host.DB, settings['engine_url'])
        model = next((value for value in original['models'] if value['name'] == settings['checkpoint']), None)
        current_engine = host.engine_url()
        matches = settings['engine_url'] == current_engine
        checkpoint_status = ('unknown' if original.get('synced_at') is None or original.get('sync_error')
                             else 'available' if model and model.get('listed') else 'missing')
        warnings = ['已保留失敗任務的原始設定；未提交或重送任務，確認並調整後請建立新請求。']
        if not matches:
            warnings.append('任務原引擎與目前設定不同；已保留原位址，生成前請先確認引擎設定')
        if checkpoint_status == 'missing':
            warnings.append('原 checkpoint 不在最近同步的模型清單；請先安裝模型或重新同步後確認')
        elif checkpoint_status == 'unknown':
            warnings.append('原引擎模型清單尚未同步或同步失敗；checkpoint 可用性待確認')
        else:
            warnings.append('checkpoint 僅在最近同步清單中，實際可用性將於生成前再次檢查')
        version = job.get('model_version') or '未知'
        if version == '未知':
            warnings.append('原任務模型版本未知，無法確認目前 checkpoint 與原版本一致')
        elif model and model.get('version') and model['version'] != version:
            warnings.append('目前登記的模型版本與原任務不同；已保留原任務版本供比較')
        lora_info = lora_records.restoration(host.DB, settings['engine_url'], settings, job.get('lora_metadata'))
        warnings.extend(lora_info['warnings'])
        return dict(job_id=str(job_id), settings=settings, model_version=version,
                    model_metadata=job.get('model_metadata'), lora_metadata=job.get('lora_metadata'), warnings=warnings,
                    availability=dict(current_engine_url=current_engine, engine_matches=matches,
                                      checkpoint_status=checkpoint_status, catalog_synced_at=original.get('synced_at'),
                                      loras=lora_info['loras'], lora_synced_at=lora_info['lora_synced_at']))

    @app.post('/api/jobs/{job_id}/cancel')
    async def cancel(job_id: UUID):
        async with job_lock(job_id):
            return await cancellation.cancel(host, lookup(job_id))

    @app.post('/api/jobs/{job_id}/refresh')
    async def refresh(job_id: UUID):
        async with job_lock(job_id):
            return await refresh_locked(job_id)

    @app.post('/api/jobs/{job_id}/stop')
    async def stop(job_id: UUID):
        async with job_lock(job_id):
            return await stopping.stop(host, lookup(job_id))

    async def refresh_locked(job_id):
        job = lookup(job_id)
        if job['status'] in cancellation.TERMINAL:
            return job
        if job['status'] in ('validating', 'submitting'):
            # Do not promote a live submission from a second worker. After a
            # process crash, the bounded guard expires so its original UUID can
            # still be reconciled from the upstream queue/history without replay.
            try:
                started = datetime.fromisoformat(job.get('updated_at', job['created_at']))
                if datetime.now(timezone.utc) - started < timedelta(seconds=60):
                    return job
            except (TypeError, ValueError):
                pass
        if job['status'] in cancellation.CANCEL_STATES:
            return await cancellation.refresh(host, job)
        if job['status'] in stopping.STATES:
            return await stopping.refresh(host, job)
        try:
            async with httpx.AsyncClient(timeout=10, trust_env=False) as client:
                status, entry = await cancellation.history_state(client, job)
                if entry is not None:
                    return cancellation.persist(host, job, status=status, history=entry,
                                                failure_info=failures.from_history(job, entry) if status == 'failed' else None,
                                                error='ComfyUI 執行失敗，請查看任務 JSON' if status == 'failed' else None)
                response = await client.get(job['engine_url'] + '/queue')
                response.raise_for_status()
                queue = response.json()
                for key, state in [('queue_running', 'running'), ('queue_pending', 'queued')]:
                    if not isinstance(queue[key], list):
                        raise ValueError()
                    for item in queue[key]:
                        if item[1] == job['prompt_id']:
                            return cancellation.persist(host, job, status=state, error=None)
                return cancellation.persist(host, job, status='unknown', error='引擎佇列與歷史中找不到任務；可能已清除或重啟，請勿自動重送')
        except (httpx.HTTPError, ValueError, KeyError, IndexError, TypeError):
            raise HTTPException(503, '無法查詢原 ComfyUI 引擎；已保留任務原狀態與工作流程')

    progress.install(app, host, refresh, job_lock)
    capabilities.install(app, host)
    flux_workflows.install(app, host, job_lock)
