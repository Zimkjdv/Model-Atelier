"""Separately versioned Schnell model-only LoRA and VAE image-input workflows."""

import json
from pathlib import Path
from typing import Annotated, Literal
from uuid import UUID, uuid4

from fastapi import HTTPException
from pydantic import Field
from starlette.concurrency import run_in_threadpool

from backend import (
    catalog,
    drafts,
    flux_catalog,
    flux_plan,
    flux_workflows as base,
    image_workflows,
    loras,
)

LORA_ID = 'flux1-schnell-lora-v1'
IMAGE_ID = 'flux1-schnell-image2image-v1'
IDS = frozenset((LORA_ID, IMAGE_ID))
LORA_MANIFEST = Path(__file__).resolve().parents[1] / 'models/flux-schnell-pvc-style-lora.json'


class LoraInput(base.Input):
    workflow_id: Literal['flux1-schnell-lora-v1'] = LORA_ID
    lora_name: str = Field(min_length=1, max_length=2048)
    lora_strength: float = Field(default=0.7, strict=True, ge=0, le=1, allow_inf_nan=False)


class ImageInput(base.Input):
    workflow_id: Literal['flux1-schnell-image2image-v1'] = IMAGE_ID
    image_asset_id: UUID
    denoise: float = Field(default=0.6, strict=True, ge=0.05, lt=1, allow_inf_nan=False)
    reference_resize: Literal['fit', 'stretch'] = 'fit'


class LoraGenerate(LoraInput):
    request_id: UUID


class ImageGenerate(ImageInput):
    request_id: UUID


class LoraDraft(LoraInput):
    revision: int | None = Field(default=None, strict=True, ge=1)


class ImageDraft(ImageInput):
    revision: int | None = Field(default=None, strict=True, ge=1)


Input = Annotated[LoraInput | ImageInput, Field(discriminator='workflow_id')]
Generate = Annotated[LoraGenerate | ImageGenerate, Field(discriminator='workflow_id')]
Draft = Annotated[LoraDraft | ImageDraft, Field(discriminator='workflow_id')]


def settings(value):
    return value.model_dump(mode='json', exclude={'request_id', 'revision'})


def parse(value):
    cls = LoraInput if value.get('workflow_id') == LORA_ID else ImageInput
    return cls.model_validate(value)


def build(value, job_id):
    v = settings(value) if hasattr(value, 'model_dump') else value
    graph = base.build(v)
    if v['workflow_id'] == LORA_ID:
        graph['10'] = dict(
            class_type='LoraLoaderModelOnly',
            inputs=dict(
                model=['1', 0], lora_name=v['lora_name'], strength_model=v['lora_strength']
            ),
        )
        graph['7']['inputs']['model'] = ['10', 0]
    elif v['workflow_id'] == IMAGE_ID:
        target = image_workflows.location(job_id)
        graph['10'] = dict(
            class_type='LoadImage', inputs={'image': target['subfolder'] + '/' + target['name']}
        )
        graph['6'] = dict(class_type='VAEEncode', inputs={'pixels': ['10', 0], 'vae': ['3', 0]})
        graph['7']['inputs']['denoise'] = v['denoise']
    else:
        raise ValueError('未知 FLUX 附加流程；未降級成其他架構')
    return graph


def check_profile(value, components):
    if (value.width, value.height, value.steps, value.weight_dtype, value.encoder_device) != (
        512,
        512,
        4,
        'fp8_e4m3fn',
        'cpu',
    ):
        raise ValueError('FLUX 附加流程目前只驗收 512×512／4 步／FP8 e4m3fn／CPU 編碼器')
    for item in components:
        pinned = flux_plan.PINNED[item['role']]
        if (
            item['name'] != pinned[1]
            or item['sha256'] != pinned[5]
            or item['version'] != 'revision ' + pinned[3]
        ):
            raise ValueError(
                '請先依完整驗檔結果登記固定 FLUX 四元件版本及 SHA256；未知組合保持停用'
            )


def lora_snapshot(host, value):
    manifest = json.loads(LORA_MANIFEST.read_text(encoding='utf-8'))
    records = loras.read(host.DB, value.engine_url)
    item = next((item for item in records['loras'] if item['name'] == value.lora_name), {})
    if (
        records['sync_error']
        or item.get('listed') is not True
        or value.lora_name != manifest['filename']
        or item.get('architecture') != 'flux'
        or item.get('sha256') != manifest['sha256']
        or item.get('version') != manifest['version']
    ):
        raise ValueError(
            '此 LoRA／Schnell 組合尚未驗收；請同步並登記固定 PVC LoRA 版本及 SHA256。SDXL、Dev 或未知 LoRA 不會套用'
        )
    return catalog.capture(item, value.lora_name) | dict(
        strength_model=value.lora_strength, strength_clip=0
    )


async def prepare(host, value, components):
    check_profile(value, components)
    result = dict(loras=[], references=[], encoded=None, settings=settings(value))
    if value.workflow_id == LORA_ID:
        result['loras'] = [lora_snapshot(host, value)]
    else:
        source = settings(value) | dict(reference_ids=[str(value.image_asset_id)])
        snapshot, encoded = await run_in_threadpool(
            image_workflows.prepare, host.DB, host.DATA, source
        )
        snapshot['generation_preprocessing']['id'] = 'flux1-image-input'
        result.update(references=[snapshot], encoded=encoded)
    return result


def recheck(host, value, original):
    components = flux_catalog.capture(
        host.DB,
        value.engine_url,
        [(role, group, getattr(value, role)) for role, group in base.ROLES],
    )
    check_profile(value, components)
    if value.workflow_id == LORA_ID:
        current = lora_snapshot(host, value)
        if any(
            current[key] != original['loras'][0][key]
            for key in ('name', 'version', 'sha256', 'architecture')
        ):
            raise ValueError('驗證期間 LoRA 登記已變更；原快照保留，尚未提交')


async def upload(host, client, value, job, state):
    if state['encoded'] is None:
        return None
    await run_in_threadpool(image_workflows.save_input, host.DATA, job['id'], state['encoded'])
    target = image_workflows.location(job['id'])
    response = await client.post(
        value.engine_url + '/upload/image',
        files={'image': (target['name'], state['encoded'], 'image/png')},
        data={key: target[key] for key in ('type', 'subfolder')} | {'overwrite': 'false'},
    )
    response.raise_for_status()
    if len(response.content) > 1024 * 1024:
        raise ValueError('輸入上傳回應過大')
    receipt = response.json()
    if not isinstance(receipt, dict) or any(
        receipt.get(key) != expected for key, expected in target.items()
    ):
        raise ValueError('輸入上傳回應不符；可能已上傳，請求不會重送')
    return target


def extract(item):
    try:
        value = parse(item['reference_settings'])
        owner = item.get('job_id') or item['id']
        if (
            item['workflow_id'] != value.workflow_id
            or item['engine_url'] != value.engine_url
            or item['workflow'] != build(value, owner)
        ):
            raise ValueError()
        if value.workflow_id == IMAGE_ID:
            refs = item['reference_metadata']
            if len(refs) != 1 or refs[0]['id'] != str(value.image_asset_id):
                raise ValueError()
            prep = refs[0]['generation_preprocessing']
            if (prep['id'], prep['version'], prep['width'], prep['height'], prep['resize']) != (
                'flux1-image-input',
                1,
                value.width,
                value.height,
                value.reference_resize,
            ):
                raise ValueError()
        else:
            records = item['lora_metadata']
            if (
                len(records) != 1
                or records[0]['name'] != value.lora_name
                or records[0]['strength_model'] != value.lora_strength
                or records[0]['strength_clip'] != 0
            ):
                raise ValueError()
        return settings(value)
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError('FLUX 附加流程快照不完整；請下載原 JSON，未載入部分設定') from exc


def install(app, host, job_lock):
    @app.get('/api/flux/extensions/workflow')
    def describe():
        manifest = json.loads(LORA_MANIFEST.read_text(encoding='utf-8'))
        return dict(
            ids=sorted(IDS),
            components={role: pinned[1] for role, pinned in flux_plan.PINNED.items()},
            lora=manifest,
            supported_size=[512, 512],
            steps=4,
            weight_dtype='fp8_e4m3fn',
            encoder_device='cpu',
            redux=False,
            ipadapter=False,
            style_identity_guaranteed=False,
            combined_lora_image=False,
        )

    @app.post('/api/flux/extensions/workflow')
    def preview(value: Input):
        graph = build(value, uuid4())
        return dict(
            workflow_id=value.workflow_id,
            workflow_json=json.dumps(graph, ensure_ascii=False, indent=2),
            note='圖生圖 JSON 的輸入路徑為預覽 UUID；平台生成時才會保存及上傳實際素材',
        )

    @app.post('/api/flux/extensions/generate')
    async def generate(value: Generate):
        async with job_lock(value.request_id):
            return await base.submit(host, value)

    @app.get('/api/flux/extensions/drafts')
    def all_drafts():
        return drafts.list_all(host.DB, prefix='flux_extension_draft:')

    def save(value, draft_id=None):
        try:
            return drafts.save(
                host.DB,
                settings(value),
                str(draft_id) if draft_id else None,
                value.revision,
                prefix='flux_extension_draft:',
            )
        except KeyError as exc:
            raise HTTPException(404, '找不到 FLUX 附加草稿') from exc
        except ValueError as exc:
            raise HTTPException(409, str(exc)) from exc

    @app.post('/api/flux/extensions/drafts')
    def create(value: Draft):
        return save(value)

    @app.put('/api/flux/extensions/drafts/{draft_id}')
    def update(draft_id: UUID, value: Draft):
        return save(value, draft_id)
