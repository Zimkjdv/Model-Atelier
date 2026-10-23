"""Single-reference SDXL Plus ViT-H, separate style/appearance controls."""

import asyncio
from copy import deepcopy
import json
import math
import re

from backend import image_workflows, node_preflight, workflows

ID = 'checkpoint-ipadapter-reference-v1'
CHECKED_NODES = ('LoadImage', 'IPAdapterModelLoader', 'CLIPVisionLoader', 'IPAdapterAdvanced')
location = image_workflows.location
save_input = image_workflows.save_input
uploads = image_workflows.uploads


def conditioning(settings):
    return dict(
        id='ipadapter-plus-vit-h',
        version=1,
        mode=settings['reference_mode'],
        weight_type='style transfer' if settings['reference_mode'] == 'style' else 'linear',
        combine_embeds='concat',
        embeds_scaling='V only',
        image_size=224,
        encoder_preprocessing='original-engine comfy.clip_vision.clip_preprocess',
        node_version=None,
    )


def build(settings, job_id):
    graph = workflows.build(settings)
    target = location(job_id)
    graph['12'] = dict(
        class_type='LoadImage', inputs=dict(image=target['subfolder'] + '/' + target['name'])
    )
    graph['13'] = dict(
        class_type='IPAdapterModelLoader', inputs=dict(ipadapter_file=settings['ipadapter_name'])
    )
    graph['14'] = dict(
        class_type='CLIPVisionLoader', inputs=dict(clip_name=settings['clip_vision_name'])
    )
    spec = conditioning(settings)
    graph['15'] = dict(
        class_type='IPAdapterAdvanced',
        inputs=dict(
            model=['1', 0],
            ipadapter=['13', 0],
            image=['12', 0],
            clip_vision=['14', 0],
            weight=settings['reference_weight'],
            weight_type=spec['weight_type'],
            combine_embeds=spec['combine_embeds'],
            embeds_scaling=spec['embeds_scaling'],
            start_at=settings['reference_start'],
            end_at=settings['reference_end'],
        ),
    )
    graph['5']['inputs']['model'] = ['15', 0]
    return graph


def prepare(db, folder, settings):
    if settings['width'] * settings['height'] > 16_000_000:
        raise ValueError('輸出尺寸不可超過 1600 萬像素')
    source, encoded = image_workflows.prepare(
        db, folder, settings | dict(width=224, height=224, reference_resize='fit')
    )
    source['input_role'] = 'source'
    source['generation_preprocessing'].update(id='ipadapter-square-input', version=1)
    source['adapter_preprocessing'] = conditioning(settings)
    return source, encoded


async def check_nodes(client, engine, *, settings):
    specs = [
        ('LoadImage', {'image': None}, {}, ['IMAGE', 'MASK']),
        ('IPAdapterModelLoader', {'ipadapter_file': None}, {}, ['IPADAPTER']),
        ('CLIPVisionLoader', {'clip_name': None}, {}, ['CLIP_VISION']),
        (
            'IPAdapterAdvanced',
            dict(
                model='MODEL',
                ipadapter='IPADAPTER',
                image='IMAGE',
                weight='FLOAT',
                weight_type=None,
                combine_embeds=None,
                start_at='FLOAT',
                end_at='FLOAT',
                embeds_scaling=None,
            ),
            dict(image_negative='IMAGE', attn_mask='MASK', clip_vision='CLIP_VISION'),
            ['MODEL'],
        ),
    ]
    spec = conditioning(settings)
    values = dict(
        ipadapter_file=settings['ipadapter_name'],
        clip_name=settings['clip_vision_name'],
        weight=settings['reference_weight'],
        start_at=settings['reference_start'],
        end_at=settings['reference_end'],
        weight_type=spec['weight_type'],
        combine_embeds='concat',
        embeds_scaling='V only',
    )

    async def inspect(name, required, optional, outputs):
        response = await client.get(engine + '/object_info/' + name)
        response.raise_for_status()
        if len(response.content) > 1024 * 1024:
            raise ValueError('參考節點定義過大')
        body = response.json()
        if not isinstance(body, dict) or name not in body:
            raise node_preflight.MissingNodes('ComfyUI 缺少參考節點：' + name)
        node = body[name]
        inputs = node.get('input') if isinstance(node, dict) else None
        req = inputs.get('required') if isinstance(inputs, dict) else None
        opt = inputs.get('optional', {}) if isinstance(inputs, dict) else None
        if (
            not isinstance(req, dict)
            or not isinstance(opt, dict)
            or set(req) != set(required)
            or set(opt) != set(optional)
            or node.get('output') != outputs
        ):
            raise ArithmeticError('參考節點介面不相容：' + name)
        for key, kind in (required | optional).items():
            definition = (req | opt)[key]
            if not isinstance(definition, list) or not definition:
                raise ArithmeticError('參考節點輸入定義無效')
            if kind is None:
                choices = definition[0]
                if not isinstance(choices, list) or any(not isinstance(v, str) for v in choices):
                    raise ArithmeticError('參考節點選項無效')
                if key in values and values[key] not in choices:
                    raise LookupError('參考元件或模式不在原引擎即時選項：' + key)
            elif definition[0] != kind:
                raise ArithmeticError('參考節點型別不相容：' + key)
            if kind == 'FLOAT':
                bounds = (
                    definition[1] if len(definition) > 1 and isinstance(definition[1], dict) else {}
                )
                low, high = bounds.get('min'), bounds.get('max')
                if (
                    type(low) not in (int, float)
                    or type(high) not in (int, float)
                    or not math.isfinite(low)
                    or not math.isfinite(high)
                    or not low <= values[key] <= high
                ):
                    raise ArithmeticError('參考參數超出原節點範圍：' + key)

    results = await asyncio.gather(*(inspect(*spec) for spec in specs), return_exceptions=True)
    for result in results:
        if isinstance(result, BaseException):
            raise result


def extract(item, validate):
    message = '參考圖流程、前處理或元件快照不完整；請下載原流程，未載入部分設定'
    try:
        settings = validate(deepcopy(item['reference_settings']))
        refs, components = item['reference_metadata'], item['component_metadata']
        if (
            settings['engine_url'] != item['engine_url']
            or settings['checkpoint'] != item['checkpoint']
            or item['source']['node_id'] != '7'
            or item['model_metadata']['architecture'] != 'sdxl'
        ):
            raise ValueError(message)
        if (
            len(refs) != 1
            or refs[0]['id'] != settings['image_asset_id']
            or settings['reference_ids'] != [refs[0]['id']]
            or refs[0]['input_role'] != 'source'
            or refs[0]['adapter_preprocessing'] != conditioning(settings)
            or type(refs[0]['adapter_preprocessing'].get('version')) is not int
        ):
            raise ValueError(message)
        if len(components) != 2:
            raise ValueError(message)
        for record, role, key, family, architecture in zip(
            components,
            ['ipadapter', 'clip_vision'],
            ['ipadapter_name', 'clip_vision_name'],
            ['sdxl-plus-vit-h', 'clip-vit-h-14'],
            ['sdxl', 'other'],
        ):
            if (
                record['role'] != role
                or record['name'] != settings[key]
                or record['family'] != family
                or record['architecture'] != architecture
            ):
                raise ValueError(message)
        prep = refs[0]['generation_preprocessing']
        if (
            any(
                prep[k] != v
                for k, v in dict(
                    id='ipadapter-square-input',
                    version=1,
                    width=224,
                    height=224,
                    resize='fit',
                    resampling='LANCZOS',
                    background='#ffffff',
                    output_mode='RGB',
                    output_format='PNG',
                ).items()
            )
            or type(prep['version']) is not int
            or not isinstance(prep['sha256'], str)
            or not re.fullmatch(r'[0-9a-f]{64}', prep['sha256'])
            or type(prep.get('size')) is not int
            or not 0 < prep['size'] <= image_workflows.MAX_ENCODED
        ):
            raise ValueError(message)
        graph = {
            k: {n: v for n, v in node.items() if n != '_meta'}
            for k, node in item['workflow'].items()
        }
        if json.dumps(graph, sort_keys=True, allow_nan=False) != json.dumps(
            build(settings, item.get('job_id', item['id'])), sort_keys=True, allow_nan=False
        ):
            raise ValueError(message)
        return settings
    except (KeyError, TypeError, ValueError, AttributeError) as exc:
        raise ValueError(message) from exc
