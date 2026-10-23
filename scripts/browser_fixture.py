"""Local browser fixture: fresh temporary DATA and an in-process fake engine.

No option accepts a production DATA path or engine URL. Never run as a service.
"""

import argparse
import asyncio
from contextlib import closing
from email import policy
from email.parser import BytesParser
import hashlib
import io
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
from uuid import uuid4
from typing import Literal

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import httpx
from PIL import Image
import uvicorn
from fastapi import FastAPI
from backend import assets, catalog, gallery, jobs, workflows
from backend.main import create_app
from scripts.structure_fixture import STRUCTURE_NODES

ENGINE = 'http://mock-engine.invalid:8188'


INPAINT_NODES = {
    'LoadImage': dict(input=dict(required=dict(image=[[]])), output=['IMAGE', 'MASK']),
    'VAEEncode': dict(input=dict(required=dict(pixels=['IMAGE'], vae=['VAE'])), output=['LATENT']),
    'LoadImageMask': dict(
        input=dict(required=dict(image=[[]], channel=[['alpha', 'red', 'green', 'blue']])),
        output=['MASK'],
    ),
    'VAEEncodeForInpaint': dict(
        input=dict(
            required=dict(
                pixels=['IMAGE'],
                vae=['VAE'],
                mask=['MASK'],
                grow_mask_by=['INT', dict(min=0, max=64)],
            )
        ),
        output=['LATENT'],
    ),
    'ImageCompositeMasked': dict(
        input=dict(
            required=dict(
                destination=['IMAGE'],
                source=['IMAGE'],
                x=['INT', dict(min=0, max=8192)],
                y=['INT', dict(min=0, max=8192)],
                resize_source=['BOOLEAN'],
            ),
            optional=dict(mask=['MASK']),
        ),
        output=['IMAGE'],
    ),
}

REFERENCE_NODES = {
    'IPAdapterModelLoader': dict(
        input=dict(required=dict(ipadapter_file=[['plus.safetensors']])), output=['IPADAPTER']
    ),
    'CLIPVisionLoader': dict(
        input=dict(required=dict(clip_name=[['vision.safetensors']])), output=['CLIP_VISION']
    ),
    'IPAdapterAdvanced': dict(
        input=dict(
            required=dict(
                model=['MODEL'],
                ipadapter=['IPADAPTER'],
                image=['IMAGE'],
                weight=['FLOAT', dict(min=-1, max=5)],
                weight_type=[['linear', 'style transfer']],
                combine_embeds=[['concat']],
                start_at=['FLOAT', dict(min=0, max=1)],
                end_at=['FLOAT', dict(min=0, max=1)],
                embeds_scaling=[['V only']],
            ),
            optional=dict(
                image_negative=['IMAGE'], attn_mask=['MASK'], clip_vision=['CLIP_VISION']
            ),
        ),
        output=['MODEL'],
    ),
}


def uploaded_image(request):
    envelope = (
        b'Content-Type: '
        + request.headers['content-type'].encode('ascii')
        + b'\r\nMIME-Version: 1.0\r\n\r\n'
        + request.content
    )
    message = BytesParser(policy=policy.default).parsebytes(envelope)
    fields, image = {}, None
    for part in message.iter_parts():
        name = part.get_param('name', header='content-disposition')
        raw = part.get_payload(decode=True)
        if name == 'image':
            image = dict(name=part.get_filename(), sha256=hashlib.sha256(raw).hexdigest())
        else:
            fields[name] = raw.decode('utf-8')
    assert image and fields['overwrite'] == 'false' and fields['type'] == 'input'
    return image | fields


def fixture(data, count=None, legacy_ui=False):
    state = {'prompts': 0, 'uploads': 0, 'engine_requests': 0, 'mode': 'uncertain'}
    generated = {}
    audit = []

    def engine(request):
        assert request.url.host == 'mock-engine.invalid', 'fixture cannot contact another engine'
        state['engine_requests'] += 1
        record = dict(
            sequence=state['engine_requests'], method=request.method, path=request.url.path
        )
        audit.append(record)
        del audit[:-1000]
        if state['mode'] == 'offline':
            raise httpx.ConnectError('fixture offline')
        name = request.url.path.rsplit('/', 1)[-1]
        if request.url.path == '/prompt':
            state['prompts'] += 1
            payload = json.loads(request.content)
            record['job_id'] = payload['prompt_id']
            if state['mode'] == 'uncertain':
                raise httpx.ReadTimeout('fixture: lost upstream response')
            identifier = payload['prompt_id']
            generated[identifier] = {
                'status': {'completed': True, 'status_str': 'success'},
                'outputs': {
                    '7': {
                        'images': [
                            {'filename': identifier + '.png', 'subfolder': '', 'type': 'output'}
                        ]
                    }
                },
            }
            return httpx.Response(200, json={'prompt_id': identifier})
        if request.url.path == '/upload/image':
            state['uploads'] += 1
            uploaded = uploaded_image(request)
            record.update(uploaded)
            return httpx.Response(
                200, json={key: uploaded[key] for key in ('name', 'subfolder', 'type')}
            )
        if request.url.path.startswith('/history/'):
            return httpx.Response(200, json={name: generated[name]} if name in generated else {})
        if request.url.path == '/view':
            return httpx.Response(
                200, content=raw.getvalue(), headers={'content-type': 'image/png'}
            )
        if name == 'CheckpointLoaderSimple':
            value = {name: {'input': {'required': {'ckpt_name': [['demo.safetensors']]}}}}
        elif name == 'KSampler':
            value = {
                name: {
                    'input': {
                        'required': {
                            'sampler_name': [['euler']],
                            'scheduler': [['normal']],
                            'steps': ['INT', {'min': 1, 'max': 10000, 'default': 20}],
                            'cfg': ['FLOAT', {'min': 0, 'max': 100, 'default': 7}],
                            'denoise': ['FLOAT', {'min': 0, 'max': 1, 'default': 1}],
                        }
                    }
                }
            }
        elif request.url.path.startswith('/object_info/') and name in STRUCTURE_NODES:
            value = {name: STRUCTURE_NODES[name]}
        elif request.url.path.startswith('/object_info/') and name in INPAINT_NODES:
            value = {name: INPAINT_NODES[name]}
        elif request.url.path.startswith('/object_info/') and name in REFERENCE_NODES:
            value = {name: REFERENCE_NODES[name]}
        elif request.url.path.startswith('/object_info/'):
            value = {name: {'input': {'required': {}}}}
        elif name == 'system_stats':
            value = {'system': {}, 'devices': []}
        elif name == 'execution-device':
            return httpx.Response(404, json={})
        elif name == 'queue':
            value = {'queue_running': [], 'queue_pending': []}
        else:
            value = {}
        return httpx.Response(200, json=value)

    app = create_app(
        data_root=data,
        root=ROOT / 'runtime' / 'q04-baseline-ui' if legacy_ui else ROOT,
        engine_client_factory=lambda **kw: httpx.AsyncClient(
            transport=httpx.MockTransport(engine), **kw
        ),
    )
    context = app.state.context
    context.initialize()
    context.gpu_info = lambda: ([], None)
    with closing(sqlite3.connect(context.DB)) as db, db:
        db.execute('INSERT OR REPLACE INTO settings VALUES (?, ?)', ('comfy_url', ENGINE))
    catalog.merge(context.DB, ENGINE, ['demo.safetensors'])
    catalog.select(context.DB, ENGINE, 'demo.safetensors')
    catalog.update_metadata(context.DB, ENGINE, 'demo.safetensors', {'architecture': 'sdxl'})
    raw = io.BytesIO()
    Image.new('RGB', (64, 64), '#718d76').save(raw, 'PNG')
    asset = assets.create(context.DB, data / 'assets', raw.getvalue(), 'qa-source.png')
    mask_image = Image.new('RGB', (64, 64), 'black')
    mask_image.paste('white', (32, 0, 64, 64))
    mask_bytes = io.BytesIO()
    mask_image.save(mask_bytes, 'PNG')
    mask_asset = assets.create(context.DB, data / 'assets', mask_bytes.getvalue(), 'qa-mask.png')
    graph = workflows.build(
        dict(
            checkpoint='demo.safetensors',
            prompt='fixture forest',
            negative_prompt='blurry',
            width=64,
            height=64,
            seed=str(2**64 - 1),
            steps=20,
            cfg=7,
            sampler_name='euler',
            scheduler='normal',
            denoise=1,
        )
    )
    job_id = str(uuid4())
    jobs.reserve(context.DB, job_id, ENGINE, graph, 'demo.safetensors', 'fixture-v1')
    job = jobs.update(
        context.DB,
        job_id,
        status='completed',
        prompt_id=str(uuid4()),
        history={
            'status': {'completed': True, 'status_str': 'success'},
            'outputs': {
                '7': {'images': [{'filename': 'qa-artwork.png', 'subfolder': '', 'type': 'output'}]}
            },
        },
    )
    artwork, _ = gallery.save(
        context.DB, data / 'artworks', job, gallery.outputs(job)[0], raw.getvalue()
    )
    if count is not None:
        from scripts.listing_dataset import seed

        with closing(sqlite3.connect(context.DB)) as db, db:
            db.execute(
                "DELETE FROM settings WHERE key GLOB 'artwork:*' OR key GLOB 'job:*' OR key GLOB 'asset:*'"
            )
        seed(context, count)

    @app.middleware('http')
    async def delayed_save(request, call_next):
        if request.url.path in ('/api/drafts', '/api/flux/drafts') and request.method == 'POST':
            await asyncio.sleep(0.5)
        return await call_next(request)

    wrapper = FastAPI(lifespan=app.router.lifespan_context)

    @wrapper.get('/qa/state')
    def status():
        return dict(
            state, artwork_id=artwork['id'], asset_id=asset['id'], mask_asset_id=mask_asset['id']
        )

    @wrapper.get('/qa/engine-audit')
    def engine_audit(after: int = 0):
        return [entry for entry in audit if entry['sequence'] > after]

    @wrapper.post('/qa/conflict')
    def conflict():
        value = gallery.get(context.DB, artwork['id'])
        gallery.organize(context.DB, artwork['id'], value['revision'], {'notes': 'another window'})
        return {'ok': True}

    @wrapper.post('/qa/artwork-set')
    def artwork_set():
        group = 'v03-' + uuid4().hex[:8]
        records = []
        for index, size in enumerate(((128, 64), (64, 128), (96, 96), (128, 96), (64, 64))):
            choices = [
                dict(
                    name='fixture-alpha.safetensors',
                    enabled=True,
                    strength_model=0.5,
                    strength_clip=1,
                ),
                dict(
                    name='fixture-beta.safetensors',
                    enabled=True,
                    strength_model=0.8,
                    strength_clip=0.25,
                ),
            ]
            if index % 2:
                choices.reverse()
            checkpoint = 'fixture-model-' + ('a' if index % 2 == 0 else 'b') + '.safetensors'
            settings = dict(
                title=group + '-' + str(index + 1),
                prompt=group + ' scene ' + str(index + 1),
                negative_prompt='fixture negative ' + str(index),
                checkpoint=checkpoint,
                width=size[0],
                height=size[1],
                seed=str(2**64 - 1 - index),
                steps=12 + 4 * index,
                cfg=5 + index,
                sampler_name='euler',
                scheduler='normal',
                denoise=0.5 + index / 10,
                loras=choices,
            )
            identifier = str(uuid4())
            metadata = [
                dict(
                    name=choice['name'],
                    version='fixture-v1',
                    strength_model=choice['strength_model'],
                    strength_clip=choice['strength_clip'],
                )
                for choice in choices
            ]
            jobs.reserve(
                context.DB,
                identifier,
                ENGINE,
                workflows.build(settings),
                checkpoint,
                'fixture-v03',
                lora_metadata=metadata,
                workflow_id='checkpoint-text2image-v1',
            )
            job = jobs.update(
                context.DB,
                identifier,
                status='completed',
                history={
                    'status': {'completed': True, 'status_str': 'success'},
                    'outputs': {
                        '7': {
                            'images': [
                                {
                                    'filename': settings['title'] + '.png',
                                    'subfolder': '',
                                    'type': 'output',
                                }
                            ]
                        }
                    },
                },
            )
            image = Image.new(
                'RGB', size, ('#718d76', '#a18d71', '#718da1', '#9871a1', '#a17171')[index]
            )
            image.paste('white', (0, 0, size[0] // 4, size[1] // 4))
            encoded = io.BytesIO()
            image.save(encoded, 'PNG')
            record, _ = gallery.save(
                context.DB, data / 'artworks', job, gallery.outputs(job)[0], encoded.getvalue()
            )
            records.append(record)
        return dict(group=group, items=records)

    @wrapper.post('/qa/resource-samples')
    def resource_samples():
        from backend import resource_sampling
        from datetime import datetime, timedelta, timezone

        identifier = str(uuid4())
        jobs.reserve(context.DB, identifier, ENGINE, graph, 'demo.safetensors', 'fixture-v1')
        jobs.update(context.DB, identifier, status='submitting')
        owner = 'fixture-resource-samples'
        resource_sampling.claim(context.DB, owner, resource_sampling.now())
        for seconds in (0, 2, 4):
            stamp = (datetime.now(timezone.utc) + timedelta(seconds=seconds)).isoformat()
            resource_sampling.record(
                context.DB,
                owner,
                [identifier],
                dict(
                    system=dict(ram_total=16 * 1024**3, ram_free=8 * 1024**3),
                    devices=[
                        dict(
                            name='測試 GPU',
                            type='cuda',
                            index=0,
                            vram_total=12 * 1024**3,
                            vram_free=5 * 1024**3,
                        )
                    ],
                ),
                stamp,
            )
        history = json.loads(json.dumps(job['history']))
        history['outputs']['7']['images'][0]['filename'] = 'e05-' + identifier + '.png'
        done = jobs.update(context.DB, identifier, status='completed', history=history)
        record, _ = gallery.save(
            context.DB, data / 'artworks', done, gallery.outputs(done)[0], raw.getvalue()
        )
        return record

    extended_registration = None

    @wrapper.post('/qa/extended-models')
    def extended_models():
        nonlocal extended_registration
        if extended_registration is None:
            with closing(sqlite3.connect(context.DB)) as db:
                extended_registration = db.execute(
                    'SELECT value FROM settings WHERE key=?', ('catalog:' + ENGINE,)
                ).fetchone()[0]
        catalog.merge(context.DB, ENGINE, ['demo.safetensors', 'alternate.safetensors'])
        for index, name in enumerate(('demo.safetensors', 'alternate.safetensors')):
            catalog.update_metadata(
                context.DB,
                ENGINE,
                name,
                dict(
                    architecture='sdxl',
                    version='fixture-r06-' + str(index + 1),
                    sha256=str(index + 1) * 64,
                ),
            )
        return {'ok': True}

    @wrapper.post('/qa/extended-models/reset')
    def reset_extended_models():
        nonlocal extended_registration
        if extended_registration is not None:
            with closing(sqlite3.connect(context.DB)) as db, db:
                db.execute(
                    'UPDATE settings SET value=? WHERE key=?',
                    (extended_registration, 'catalog:' + ENGINE),
                )
            extended_registration = None
        return {'ok': True}

    comparison_context = None
    comparison_registration = None

    @wrapper.post('/qa/comparison-context')
    def comparison_data():
        nonlocal comparison_context, comparison_registration
        if comparison_context is None:
            from scripts.comparison_fixture import prepare

            with closing(sqlite3.connect(context.DB)) as db:
                comparison_registration = {
                    key: db.execute('SELECT value FROM settings WHERE key=?', (key,)).fetchone()
                    for key in ('catalog:' + ENGINE, 'loras:' + ENGINE)
                }
            comparison_context = prepare(context, ROOT, ENGINE)
        return comparison_context

    @wrapper.post('/qa/comparison-context/reset')
    def reset_comparison_data():
        nonlocal comparison_context, comparison_registration
        with closing(sqlite3.connect(context.DB)) as db, db:
            for key, row in (comparison_registration or {}).items():
                if row:
                    db.execute('INSERT OR REPLACE INTO settings VALUES (?, ?)', (key, row[0]))
                else:
                    db.execute('DELETE FROM settings WHERE key=?', (key,))
            for entry in (comparison_context or {}).get('outputs', []):
                for key in ('job:' + entry['job']['id'], 'artwork:' + entry['artwork']['id']):
                    db.execute('DELETE FROM settings WHERE key=?', (key,))
        comparison_context = comparison_registration = None
        return {'ok': True}

    @wrapper.post('/qa/engine/{mode}')
    def engine_mode(mode: Literal['offline', 'success', 'uncertain']):
        state['mode'] = mode
        return {'ok': True}

    @wrapper.post('/qa/model-selection/reset')
    def reset_selection():
        catalog.mutate(context.DB, ENGINE, lambda value: value.update(selected=None))
        return {'ok': True}

    @wrapper.post('/qa/populate')
    def populate():
        from scripts.listing_dataset import seed

        seed(context, 125)
        return {'ok': True}

    wrapper.mount('/', app)
    return wrapper


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, required=True)
    parser.add_argument('--count', type=int, choices=[100, 1000, 10000])
    parser.add_argument(
        '--legacy-ui',
        action='store_true',
        help='Use the fixed Q06 UI archived under runtime/q04-baseline-ui',
    )
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix='atelier-browser-') as folder:
        uvicorn.run(
            fixture(Path(folder), args.count, args.legacy_ui),
            host='127.0.0.1',
            port=args.port,
            log_level='warning',
        )
