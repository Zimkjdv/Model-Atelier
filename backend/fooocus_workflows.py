"""Fixed Fooocus SDXL inpaint patch, binary noise mask and inner blend mask."""

from copy import deepcopy
import json
from pathlib import Path
from backend import inpaint_feather_workflows as feather, catalog, node_preflight

ID = 'checkpoint-fooocus-inpaint-v3'
ROOT = Path(__file__).resolve().parents[1]
BASE = json.loads((ROOT / 'models/animagine-xl-4.0-opt.json').read_text(encoding='utf-8'))
WEIGHTS = [
    json.loads((ROOT / 'models' / name).read_text(encoding='utf-8'))
    for name in ('fooocus-inpaint-head.json', 'fooocus-inpaint-v26.json')
]
CHECKED_NODES = feather.CHECKED_NODES + (
    'INPAINT_LoadFooocusInpaint',
    'INPAINT_ApplyFooocusInpaint',
)
location = feather.location
uploads = feather.uploads
save_input = feather.save_input


def policy():
    return dict(
        id='fooocus-v2.6',
        required_node_revision='5b7681746fe19e563113d27366ba85236bc1ba5b',
        node_version=None,
        weights=[
            {k: w[k] for k in ('id', 'filename', 'version', 'sha256', 'size_bytes', 'source')}
            for w in WEIGHTS
        ],
    )


def validate_model(model):
    if not isinstance(model, dict) or any(
        model.get(k) != v
        for k, v in dict(
            name=BASE['filename'],
            architecture='sdxl',
            sha256=BASE['sha256'],
            size_bytes=BASE['size_bytes'],
        ).items()
    ):
        raise ValueError(
            '專用修補首版只支援固定來源 Animagine 4.0 Opt；需登記其 SDXL 架構、SHA256 與大小，不支援蒸餾版或 LoRA'
        )


def recheck(host, value, job=None):
    model = next(
        (
            m
            for m in catalog.read(host.DB, value.engine_url)['models']
            if m['name'] == value.checkpoint
        ),
        None,
    )
    validate_model(model)
    if job and any(
        catalog.capture(model, value.checkpoint).get(k) != v
        for k, v in job['model_metadata'].items()
        if k != 'captured_at'
    ):
        raise ValueError('專用修補基底登記已變更，尚未提交')


def build(settings, job_id):
    graph = feather.build(settings, job_id)
    graph['16'] = dict(
        class_type='INPAINT_LoadFooocusInpaint',
        inputs=dict(head=WEIGHTS[0]['filename'], patch=WEIGHTS[1]['filename']),
    )
    graph['17'] = dict(
        class_type='INPAINT_ApplyFooocusInpaint',
        inputs=dict(model=graph['5']['inputs']['model'], patch=['16', 0], latent=['4', 0]),
    )
    graph['5']['inputs']['model'] = ['17', 0]
    return graph


def prepare(db, folder, settings):
    refs, encoded = feather.prepare(db, folder, settings)
    refs[0]['dedicated_inpaint'] = policy()
    return refs, encoded


async def check_nodes(client, engine, *, settings):
    await feather.check_nodes(client, engine, settings=settings)
    specs = [
        (
            'INPAINT_LoadFooocusInpaint',
            dict(head=WEIGHTS[0]['filename'], patch=WEIGHTS[1]['filename']),
            ['INPAINT_PATCH'],
        ),
        (
            'INPAINT_ApplyFooocusInpaint',
            dict(model='MODEL', patch='INPAINT_PATCH', latent='LATENT'),
            ['MODEL'],
        ),
    ]
    for name, fields, outputs in specs:
        r = await client.get(engine + '/object_info/' + name)
        r.raise_for_status()
        if len(r.content) > 1024 * 1024:
            raise ValueError('節點定義過大')
        body = r.json()
        node = body.get(name) if isinstance(body, dict) else None
        if not isinstance(node, dict):
            raise node_preflight.MissingNodes('缺少專用修補節點：' + name)
        inputs = node.get('input', {})
        required = inputs.get('required', {}) if isinstance(inputs, dict) else None
        optional = inputs.get('optional', {}) if isinstance(inputs, dict) else None
        if (
            not isinstance(required, dict)
            or set(required) != set(fields)
            or optional
            or node.get('output') != outputs
        ):
            raise ValueError('專用修補節點介面不相容')
        for field, expected in fields.items():
            spec = required[field]
            if not isinstance(spec, list) or not spec:
                raise ValueError('專用修補節點參數無效')
            if name == 'INPAINT_LoadFooocusInpaint':
                options = (
                    spec[0]
                    if isinstance(spec[0], list)
                    else spec[1].get('options')
                    if spec[0] == 'COMBO' and len(spec) > 1 and isinstance(spec[1], dict)
                    else None
                )
                if not isinstance(options, list) or expected not in options:
                    raise ValueError('缺少固定 Fooocus head／patch 權重')
            elif spec[0] != expected:
                raise ValueError('專用修補節點型別不相容')


def extract(item, validate):
    try:
        settings = validate(deepcopy(item['reference_settings']))
        validate_model(item['model_metadata'])
        if (
            item.get('workflow_id') != ID
            or settings['inpaint_model'] != 'fooocus-v2.6'
            or settings['denoise'] != 1
            or settings['loras']
        ):
            raise ValueError()
        if json.dumps(
            item['reference_metadata'][0]['dedicated_inpaint'], sort_keys=True, allow_nan=False
        ) != json.dumps(policy(), sort_keys=True, allow_nan=False):
            raise ValueError()
        owner = item.get('job_id', item['id'])
        actual = {
            k: {n: v for n, v in node.items() if n != '_meta'}
            for k, node in item['workflow'].items()
        }
        if json.dumps(actual, sort_keys=True, allow_nan=False) != json.dumps(
            build(settings, owner), sort_keys=True, allow_nan=False
        ):
            raise ValueError()
        previous = deepcopy(item)
        previous['workflow_id'] = feather.ID
        previous['workflow'] = feather.build(settings, owner)
        feather.extract(previous, lambda value: value)
        return settings
    except (KeyError, ValueError, TypeError, AttributeError, IndexError) as exc:
        raise ValueError('專用修補模型／流程／來源快照不完整，未部分還原') from exc
