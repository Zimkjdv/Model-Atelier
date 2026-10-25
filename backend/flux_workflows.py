"""FLUX.1 schnell split-loader workflow; no checkpoint-template fallback."""

import asyncio
import json
import math
from typing import Literal
from uuid import UUID

import httpx
from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from backend import (
    capabilities,
    cancellation,
    compute_lease,
    drafts,
    failures,
    flux_catalog,
    gallery,
    jobs,
    runtime_metadata,
)

WORKFLOW_ID = 'flux1-schnell-text2image-v1'
ROLES = [
    ('diffusion_model', 'diffusion_models'),
    ('clip_l', 'text_encoders'),
    ('t5xxl', 'text_encoders'),
    ('vae', 'vae'),
]
WARNING = 'FLUX.1 [schnell] 已驗收固定四元件、512×512／4 步／主模型 FP8 e4m3fn／CPU 編碼器的 RTX 3060 配置；其他配置與目前引擎未自動驗證，清單及登記資料不代表權重驗證。'


class Input(BaseModel):
    model_config = ConfigDict(extra='forbid')
    workflow_id: Literal['flux1-schnell-text2image-v1'] = WORKFLOW_ID
    engine_url: str = Field(min_length=1, max_length=2048)
    title: str = Field(default='FLUX 草稿', min_length=1, max_length=100)
    diffusion_model: str = Field(min_length=1, max_length=2048)
    clip_l: str = Field(min_length=1, max_length=2048)
    t5xxl: str = Field(min_length=1, max_length=2048)
    vae: str = Field(min_length=1, max_length=2048)
    prompt: str = Field(default='', max_length=20000)
    seed: str = Field(default='0', strict=True, pattern=r'^[0-9]{1,20}$')
    width: int = Field(default=512, strict=True, ge=64, le=8192, multiple_of=16)
    height: int = Field(default=512, strict=True, ge=64, le=8192, multiple_of=16)
    steps: int = Field(default=4, strict=True, ge=1, le=4)
    weight_dtype: Literal['default', 'fp8_e4m3fn', 'fp8_e5m2'] = 'default'
    encoder_device: Literal['default', 'cpu'] = 'default'

    @field_validator('engine_url')
    @classmethod
    def valid_engine(cls, value):
        # Local import avoids a circular import while main installs routes.
        from backend.main import Settings

        return Settings.validate_url(value)

    @field_validator('title', 'diffusion_model', 'clip_l', 't5xxl', 'vae')
    @classmethod
    def nonempty(cls, value):
        if not value.strip():
            raise ValueError('名稱不可空白')
        return value

    @field_validator('seed')
    @classmethod
    def valid_seed(cls, value):
        if int(value) > 2**64 - 1:
            raise ValueError('seed 超過 64 位非負整數範圍')
        return str(int(value))

    @model_validator(mode='after')
    def separate_encoders(self):
        if self.clip_l == self.t5xxl:
            raise ValueError('CLIP-L 與 T5 需選擇不同元件')
        return self


def descriptor():
    return dict(
        id=WORKFLOW_ID,
        name='FLUX.1 [schnell] 分離元件文生圖',
        fields=list(Input.model_fields),
        steps=dict(min=1, max=4),
        size=dict(min=64, max=8192, multiple=16),
        batch_size=1,
        cfg=1.0,
        sampler_name='euler',
        scheduler='simple',
        denoise=1.0,
        negative_prompt=False,
        lora=False,
        reference_images=False,
        gpu_verified=False,
        gpu_verification_scope='current_engine_not_automatically_verified',
        verified_profiles=['flux-schnell-fp8-cpu-512-v1'],
        warning=WARNING,
    )


def build(value):
    v = value.model_dump() if isinstance(value, Input) else value
    return {
        '1': dict(
            class_type='UNETLoader',
            inputs=dict(unet_name=v['diffusion_model'], weight_dtype=v['weight_dtype']),
        ),
        '2': dict(
            class_type='DualCLIPLoader',
            inputs=dict(
                clip_name1=v['clip_l'],
                clip_name2=v['t5xxl'],
                type='flux',
                device=v['encoder_device'],
            ),
        ),
        '3': dict(class_type='VAELoader', inputs=dict(vae_name=v['vae'])),
        '4': dict(class_type='CLIPTextEncode', inputs=dict(text=v['prompt'], clip=['2', 0])),
        '5': dict(class_type='CLIPTextEncode', inputs=dict(text='', clip=['2', 0])),
        '6': dict(
            class_type='EmptySD3LatentImage',
            inputs=dict(width=v['width'], height=v['height'], batch_size=1),
        ),
        '7': dict(
            class_type='KSampler',
            inputs=dict(
                model=['1', 0],
                positive=['4', 0],
                negative=['5', 0],
                latent_image=['6', 0],
                seed=int(v['seed']),
                steps=v['steps'],
                cfg=1.0,
                sampler_name='euler',
                scheduler='simple',
                denoise=1.0,
            ),
        ),
        '8': dict(class_type='VAEDecode', inputs=dict(samples=['7', 0], vae=['3', 0])),
        '9': dict(
            class_type='SaveImage', inputs=dict(images=['8', 0], filename_prefix='ModelAtelier')
        ),
    }


def extract(job):
    from backend import flux_extensions

    if job.get('workflow_id') in flux_extensions.IDS:
        return flux_extensions.extract(job)
    try:
        if job.get('workflow_id') != WORKFLOW_ID:
            raise ValueError()
        g = job['workflow']
        seed = g['7']['inputs']['seed']
        if type(seed) is not int:
            raise ValueError()
        value = Input(
            engine_url=job['engine_url'],
            diffusion_model=g['1']['inputs']['unet_name'],
            clip_l=g['2']['inputs']['clip_name1'],
            t5xxl=g['2']['inputs']['clip_name2'],
            vae=g['3']['inputs']['vae_name'],
            prompt=g['4']['inputs']['text'],
            seed=str(seed),
            width=g['6']['inputs']['width'],
            height=g['6']['inputs']['height'],
            steps=g['7']['inputs']['steps'],
            weight_dtype=g['1']['inputs']['weight_dtype'],
            encoder_device=g['2']['inputs']['device'],
        )
        if build(value) != g:
            raise ValueError()
        return value.model_dump()
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError('無法完整還原此 FLUX 流程；請下載原 JSON，未載入部分參數。') from exc


OUTPUTS = {
    'UNETLoader': ['MODEL'],
    'DualCLIPLoader': ['CLIP'],
    'VAELoader': ['VAE'],
    'CLIPTextEncode': ['CONDITIONING'],
    'EmptySD3LatentImage': ['LATENT'],
    'KSampler': ['LATENT'],
    'VAEDecode': ['IMAGE'],
    'SaveImage': [],
    'LoraLoaderModelOnly': ['MODEL'],
    'LoadImage': ['IMAGE', 'MASK'],
    'VAEEncode': ['LATENT'],
}
LINK_TYPES = {
    'model': 'MODEL',
    'clip': 'CLIP',
    'positive': 'CONDITIONING',
    'negative': 'CONDITIONING',
    'latent_image': 'LATENT',
    'samples': 'LATENT',
    'vae': 'VAE',
    'images': 'IMAGE',
    'pixels': 'IMAGE',
}


async def preflight(client, engine_url, graph):
    async def load(kind):
        response = await client.get(engine_url + '/object_info/' + kind)
        response.raise_for_status()
        if len(response.content) > 1024 * 1024:
            raise ValueError('FLUX 節點定義回應過大')
        payload = response.json()
        if not isinstance(payload, dict) or not isinstance(payload.get(kind), dict):
            raise ValueError('ComfyUI 缺少 FLUX 必要節點：' + kind)
        return kind, payload[kind]

    kinds = dict.fromkeys(node['class_type'] for node in graph.values())
    results = await asyncio.gather(*(load(kind) for kind in kinds), return_exceptions=True)
    for result in results:
        if isinstance(result, BaseException):
            raise result
    definitions = dict(results)
    for node in graph.values():
        kind, inputs = node['class_type'], node['inputs']
        definition = definitions[kind]
        schema = definition.get('input', {})
        required, optional = schema.get('required'), schema.get('optional', {})
        output_valid = definition.get('output') == OUTPUTS[kind]
        if kind == 'SaveImage':
            # New native SaveImage returns its IMAGE; older versions return ().
            output_valid = (
                definition.get('output') in ([], ['IMAGE'])
                and definition.get('output_node') is True
            )
        if (
            not isinstance(required, dict)
            or not isinstance(optional, dict)
            or not set(required) <= set(inputs)
            or not set(inputs) <= set(required) | set(optional)
            or not output_valid
        ):
            raise ValueError('FLUX 節點介面不相容：' + kind)
        for field, value in inputs.items():
            spec = (required | optional)[field]
            if not isinstance(spec, list) or not spec:
                raise ValueError('FLUX 輸入定義格式無效：' + kind + '.' + field)
            expected = spec[0]
            if isinstance(value, list):
                valid = expected == LINK_TYPES[field]
            elif isinstance(expected, list):
                # Platform-owned image paths are uploaded only after preflight.
                valid = (
                    (type(value) is str and bool(value))
                    if kind == 'LoadImage' and field == 'image'
                    else value in expected
                )
            elif type(value) is str:
                valid = expected == 'STRING'
            elif type(value) in (int, float):
                valid = expected in ('INT', 'FLOAT') and (expected != 'INT' or type(value) is int)
                if len(spec) < 2 or not isinstance(spec[1], dict):
                    valid = False
                else:
                    low, high = spec[1].get('min'), spec[1].get('max')
                    valid = valid and type(low) in (int, float) and type(high) in (int, float)
                    valid = (
                        valid
                        and all(math.isfinite(n) for n in (low, high, value))
                        and low <= value <= high
                    )
            else:
                valid = False
            if not valid:
                raise ValueError('FLUX 元件或參數不在引擎目前有效範圍：' + kind + '.' + field)
    capabilities.validate_workflow(graph, capabilities.parse({'KSampler': definitions['KSampler']}))


def architecture_guard(metadata):
    for item in metadata:
        if item['role'] == 'diffusion_model' and item['architecture'] not in ('unknown', 'flux'):
            raise ValueError('FLUX 元件架構登記不相容：' + item['name'])


async def submit(host, value):
    from backend import diagnostics, flux_extensions

    extension = value.workflow_id in flux_extensions.IDS
    workflow_id, job_id = value.workflow_id, str(value.request_id)
    diagnostics.bind_submission(value.request_id, workflow_id)
    graph = flux_extensions.build(value, job_id) if extension else build(value)
    try:
        existing = jobs.get(host.DB, job_id)
    except KeyError:
        pass
    else:
        if (
            existing.get('workflow_id') != workflow_id
            or existing['workflow'] != graph
            or existing['engine_url'] != value.engine_url
            or extension
            and existing.get('reference_settings') != flux_extensions.settings(value)
        ):
            raise HTTPException(409, '此請求 ID 已用於其他工作流程')
        diagnostics.record_job('submission_recovered', existing)
        return existing
    if value.engine_url != host.engine_url():
        raise HTTPException(409, '引擎設定已變更，請重新載入 FLUX 元件。')
    try:
        compute_lease.check_training(host.ROOT, value.engine_url)
    except compute_lease.ComputeBusy as exc:
        raise HTTPException(409, str(exc)) from exc
    selections = [(role, group, getattr(value, role)) for role, group in ROLES]
    metadata = flux_catalog.capture(host.DB, value.engine_url, selections)
    extra = None
    if extension:
        try:
            extra = await flux_extensions.prepare(host, value, metadata)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
    try:
        job, fresh = jobs.reserve(
            host.DB,
            job_id,
            value.engine_url,
            graph,
            value.diffusion_model,
            metadata[0]['version'],
            metadata[0],
            extra['loras'] if extra else [],
            workflow_id=workflow_id,
            component_metadata=metadata,
            reference_metadata=extra['references'] if extra else None,
            reference_settings=extra['settings'] if extra else None,
        )
    except ValueError as exc:
        raise HTTPException(409, str(exc))
    if not fresh:
        return job

    def fail(code, message, reason='preflight_invalid', **extra):
        diagnostic = failures.info(reason)
        if reason == 'preflight_invalid':
            diagnostic['message'] = message[:400]
        _, changed = jobs.compare_update(
            host.DB, job, status='failed', error=message, failure_info=diagnostic, **extra
        )
        if not changed:
            raise HTTPException(409, '任務狀態已更新；請查詢原任務，未覆蓋新狀態。')
        raise HTTPException(code, dict(message=message, job_id=job_id, failure_info=diagnostic))

    try:
        architecture_guard(metadata)
    except ValueError as exc:
        fail(422, str(exc))
    async with host.http_client(timeout=15, trust_env=False) as client:
        try:
            await preflight(client, value.engine_url, graph)
        except httpx.HTTPError:
            fail(
                503,
                '無法讀取原 ComfyUI 的 FLUX 節點；引擎離線或服務失敗，尚未提交。',
                'engine_offline',
            )
        except ValueError as exc:
            fail(422, str(exc))
        observation = await runtime_metadata.capture(client, job)
        job, captured = jobs.freeze_runtime(host.DB, job, observation)
        if not captured:
            raise HTTPException(409, '任務狀態已更新；未改写環境快照或提交，請查詢原任務')
        if value.engine_url != host.engine_url():
            fail(409, '驗證期間引擎設定已變更，尚未提交。', 'engine_changed')
        if observation['execution_device']['status'] == 'unavailable':
            fail(
                409,
                '原 ComfyUI 引擎明確回報目前設定的執行裝置不可用；FLUX 尚未提交',
                'execution_device_unavailable',
            )
        try:
            architecture_guard(flux_catalog.capture(host.DB, value.engine_url, selections))
            if extra:
                flux_extensions.recheck(host, value, extra)
        except ValueError as exc:
            fail(422, '驗證期間 ' + str(exc))
        if extra and extra['encoded'] is not None:
            job = cancellation.persist(host, job, status='uploading_input')
            try:
                receipt = await flux_extensions.upload(host, client, value, job, extra)
            except (httpx.HTTPError, ValueError, OSError):
                fail(
                    502,
                    'FLUX 輸入保存或上傳失敗；原設定及錯誤保留，不自動重試',
                    'reference_input_failed',
                )
            job = cancellation.persist(host, job, input_upload=receipt)
            if value.engine_url != host.engine_url():
                fail(409, '圖片上傳期間引擎已變更，尚未提交', 'engine_changed')
            try:
                flux_extensions.recheck(host, value, extra)
            except ValueError as exc:
                fail(422, str(exc))
        job = cancellation.persist(host, job, status='submitting', preflight_warnings=[WARNING])
        try:
            async with compute_lease.dispatch(host.ROOT, value.engine_url):
                response = await client.post(
                    value.engine_url + '/prompt',
                    json=dict(
                        prompt=graph,
                        prompt_id=job_id,
                        client_id=job_id,
                        extra_data=dict(model_atelier_job_id=job_id),
                    ),
                )
            if response.status_code == 400:
                try:
                    rejected = response.json()
                except ValueError:
                    rejected = dict(http_status=400, body=response.text)
                fail(
                    422,
                    'ComfyUI 拒絕 FLUX 工作流程；完整錯誤保存在原任務。',
                    'workflow_rejected',
                    upstream_error=rejected,
                )
            response.raise_for_status()
            result = response.json()
            prompt_id = str(UUID(result['prompt_id']))
        except compute_lease.ComputeBusy as exc:
            fail(409, str(exc), 'training_busy')
        except (httpx.HTTPError, ValueError, KeyError, TypeError):
            return jobs.compare_update(
                host.DB, job, status='unknown', error='提交結果待確認；請查詢原任務，不要重新生成。'
            )[0]
        return jobs.compare_update(
            host.DB, job, status='queued', prompt_id=prompt_id, submission=result
        )[0]


def install(app, host, job_lock):
    from backend import flux_extensions

    flux_extensions.install(app, host, job_lock)

    class Generate(Input):
        request_id: UUID

    class Draft(Input):
        revision: int | None = Field(default=None, strict=True, ge=1)

    @app.get('/api/flux/drafts')
    def list_drafts():
        return drafts.list_all(host.DB, prefix='flux_draft:')

    def save_draft(value, draft_id=None):
        try:
            return drafts.save(
                host.DB,
                value.model_dump(exclude={'revision'}),
                str(draft_id) if draft_id else None,
                value.revision,
                prefix='flux_draft:',
            )
        except KeyError:
            raise HTTPException(404, '找不到 FLUX 草稿')
        except ValueError as exc:
            raise HTTPException(409, str(exc))

    @app.post('/api/flux/drafts')
    def create_draft(value: Draft):
        return save_draft(value)

    @app.put('/api/flux/drafts/{draft_id}')
    def update_draft(draft_id: UUID, value: Draft):
        return save_draft(value, draft_id)

    @app.get('/api/flux/workflow')
    def workflow_description():
        return descriptor()

    @app.post('/api/flux/workflow')
    def preview(value: Input):
        graph = build(value)
        # Browsers must export this string, never stringify parsed uint64 numbers.
        return dict(
            workflow_id=WORKFLOW_ID,
            workflow=graph,
            workflow_json=json.dumps(graph, ensure_ascii=False, indent=2),
            warnings=[WARNING],
        )

    @app.post('/api/flux/generate')
    async def generate(value: Generate):
        async with job_lock(value.request_id):
            return await submit(host, value)

    @app.get('/api/flux/jobs/{job_id}/creation-settings')
    def settings(job_id: UUID):
        try:
            job = jobs.get(host.DB, str(job_id))
        except KeyError:
            raise HTTPException(404, '找不到任務')
        if job['status'] not in ('completed', 'failed', 'stopped', 'cancelled'):
            raise HTTPException(409, '請先確認原任務終止狀態；未提交或重送任何任務。')
        try:
            value = extract(job)
        except ValueError as exc:
            raise HTTPException(422, str(exc))
        return dict(
            job_id=str(job_id),
            settings=value,
            component_metadata=job.get('component_metadata'),
            lora_metadata=job.get('lora_metadata'),
            reference_metadata=job.get('reference_metadata'),
            runtime_metadata=job.get('runtime_metadata'),
            engine_matches=job['engine_url'] == host.engine_url(),
            warnings=[WARNING, '已保留原引擎與設定；未建立任務。'],
        )

    @app.get('/api/flux/artworks/{artwork_id}/creation-settings')
    def artwork_settings(artwork_id: UUID):
        try:
            item = gallery.get(host.DB, str(artwork_id))
        except KeyError:
            raise HTTPException(404, '找不到作品')
        try:
            value = extract(item)
        except ValueError as exc:
            raise HTTPException(422, str(exc))
        return dict(
            artwork_id=str(artwork_id),
            settings=value,
            component_metadata=item.get('component_metadata'),
            lora_metadata=item.get('lora_metadata'),
            reference_metadata=item.get('reference_metadata'),
            runtime_metadata=item.get('runtime_metadata'),
            engine_matches=item['engine_url'] == host.engine_url(),
            warnings=[WARNING, '已完整載入原作品設定；未建立任務。'],
        )
