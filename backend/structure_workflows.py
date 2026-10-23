"""Owned SDXL pose/depth templates using pinned controlnet_aux interfaces.

Upstream node implementations remain in the independent ComfyUI environment.
"""

from copy import deepcopy
import json
from backend import control_workflows as legacy, node_preflight

ID = 'checkpoint-structure-controlnet-v3'
AUX_REVISION = 'a587a4c1594524c1d2de5cd1a86cd868ff448e1c'
location = legacy.location
save_input = legacy.save_input
uploads = legacy.uploads
CHECKED_NODES = (
    'LoadImage',
    'ControlNetLoader',
    'ControlNetApplyAdvanced',
    'DWPreprocessor',
    'DepthAnythingV2Preprocessor',
    'ImageScale',
)


def processor(kind):
    if kind == 'pose':
        return dict(
            class_type='DWPreprocessor',
            inputs=dict(
                image=['12', 0],
                detect_hand='enable',
                detect_body='enable',
                detect_face='enable',
                resolution=512,
                bbox_detector='yolox_l.onnx',
                pose_estimator='dw-ll_ucoco_384.onnx',
                scale_stick_for_xinsr_cn='enable',
            ),
        )
    if kind == 'depth':
        return dict(
            class_type='DepthAnythingV2Preprocessor',
            inputs=dict(image=['12', 0], ckpt_name='depth_anything_v2_vits.pth', resolution=512),
        )
    raise ValueError('結構類型需為 pose 或 depth')


def policy(settings):
    node = processor(settings['control_kind'])
    return dict(
        id=node['class_type'],
        version=1,
        parameters={k: v for k, v in node['inputs'].items() if k != 'image'},
        execution='original-engine',
        expected_package_revision=AUX_REVISION,
        node_version=None,
        output_resize='bicubic-to-output-size',
        kind=settings['control_kind'],
    )


def build(settings, job_id):
    graph = legacy.build(settings | dict(canny_low=0.4, canny_high=0.8), job_id)
    graph['17'] = processor(settings['control_kind'])
    graph['13'] = dict(
        class_type='ImageScale',
        inputs=dict(
            image=['17', 0],
            upscale_method='bicubic',
            width=settings['width'],
            height=settings['height'],
            crop='disabled',
        ),
    )
    graph['16'] = dict(
        class_type='SaveImage',
        inputs=dict(
            images=['13', 0], filename_prefix='model_atelier/' + str(job_id) + '/condition'
        ),
    )
    return graph


def prepare(db, folder, settings):
    ref, raw = legacy.prepare(db, folder, settings | dict(canny_low=0.4, canny_high=0.8))
    ref['control_preprocessing'] = policy(settings)
    return ref, raw


async def check_nodes(client, engine, *, settings):
    # Reuse strict native ControlNet validation; Canny itself is not used here.
    await legacy.check_nodes(
        client, engine, settings=settings | dict(canny_low=0.4, canny_high=0.8), include_canny=False
    )
    graph = build(settings, '00000000-0000-0000-0000-000000000001')
    for key, outputs in (
        ('17', ['IMAGE', 'POSE_KEYPOINT'] if settings['control_kind'] == 'pose' else ['IMAGE']),
        ('13', ['IMAGE']),
    ):
        node = graph[key]
        name = node['class_type']
        response = await client.get(engine + '/object_info/' + name)
        response.raise_for_status()
        if len(response.content) > 1024 * 1024:
            raise ValueError('節點定義過大')
        body = response.json()
        definition = body.get(name) if isinstance(body, dict) else None
        if not isinstance(definition, dict):
            raise node_preflight.MissingNodes('缺少結構前處理節點：' + name)
        input_schema = definition.get('input')
        if not isinstance(input_schema, dict):
            raise ValueError('結構節點輸入定義無效')
        required = input_schema.get('required', {})
        optional = input_schema.get('optional', {})
        if (
            not isinstance(required, dict)
            or not isinstance(optional, dict)
            or set(required) - set(node['inputs'])
            or definition.get('output') != outputs
        ):
            raise ValueError('結構節點介面不相容：' + name)
        inputs = required | optional
        for field, value in node['inputs'].items():
            spec = inputs.get(field)
            if not isinstance(spec, list) or not spec:
                raise ValueError('缺少結構節點參數：' + field)
            if isinstance(spec[0], list):
                if value not in spec[0]:
                    raise ValueError('結構節點不支援選項：' + field)
            elif field == 'image':
                if spec[0] != 'IMAGE':
                    raise ValueError('條件圖型別不相容')
            elif type(value) is int:
                bounds = spec[1] if len(spec) > 1 else {}
                if spec[0] != 'INT' or not bounds.get('min', value) <= value <= bounds.get(
                    'max', value
                ):
                    raise ValueError('結構數值超出範圍')
            else:
                raise ValueError('結構節點參數型別不相容')


def extract(item, validate):
    message = '姿勢／深度流程或快照不完整，未部分還原'
    try:
        settings = validate(deepcopy(item['reference_settings']))
        refs = item['reference_metadata']
        comp = item['component_metadata']
        if (
            item.get('workflow_id') != ID
            or json.dumps(refs[0]['control_preprocessing'], sort_keys=True, allow_nan=False)
            != json.dumps(policy(settings), sort_keys=True, allow_nan=False)
            or comp[0]['kind'] != settings['control_kind']
            or comp[0]['architecture'] != 'sdxl'
            or item['model_metadata']['architecture'] != 'sdxl'
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
        previous = deepcopy(item)
        old = settings | dict(canny_low=0.4, canny_high=0.8)
        old.pop('control_kind')
        previous['reference_settings'] = old
        previous['workflow'] = legacy.build(old, item.get('job_id', item['id']))
        previous['reference_metadata'][0]['control_preprocessing'] = dict(
            id='comfy-native-canny',
            version=1,
            low_threshold=0.4,
            high_threshold=0.8,
            execution='original-engine',
            node_version=None,
        )
        previous['component_metadata'][0]['kind'] = 'canny'
        legacy.extract(previous, lambda value: value)
        return settings
    except (KeyError, ValueError, TypeError, AttributeError, IndexError) as exc:
        raise ValueError(message) from exc
