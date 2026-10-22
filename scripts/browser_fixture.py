"""Local browser fixture: fresh temporary DATA and an in-process fake engine.

No option accepts a production DATA path or engine URL. Never run as a service.
"""
import argparse
import asyncio
from contextlib import closing
import io
from pathlib import Path
import sqlite3
import sys
import tempfile
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import httpx
from PIL import Image
import uvicorn
from fastapi import FastAPI
from backend import assets, catalog, gallery, jobs
from backend.main import create_app

ENGINE = 'http://mock-engine.invalid:8188'


def fixture(data, count=None, legacy_ui=False):
    state = {'prompts': 0}

    def engine(request):
        assert request.url.host == 'mock-engine.invalid', 'fixture cannot contact another engine'
        name = request.url.path.rsplit('/', 1)[-1]
        if request.url.path == '/prompt':
            state['prompts'] += 1
            raise httpx.ReadTimeout('fixture: lost upstream response')
        if name == 'CheckpointLoaderSimple':
            value = {name: {'input': {'required': {'ckpt_name': [['demo.safetensors']]}}}}
        elif name == 'KSampler':
            value = {name: {'input': {'required': {
                'sampler_name': [['euler']], 'scheduler': [['normal']],
                'steps': ['INT', {'min': 1, 'max': 10000, 'default': 20}],
                'cfg': ['FLOAT', {'min': 0, 'max': 100, 'default': 7}],
                'denoise': ['FLOAT', {'min': 0, 'max': 1, 'default': 1}],
            }}}}
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

    app = create_app(data_root=data, root=ROOT / 'runtime' / 'q04-baseline-ui' if legacy_ui else ROOT,
                     engine_client_factory=lambda **kw: httpx.AsyncClient(transport=httpx.MockTransport(engine), **kw))
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
    graph = {
        '1': {'class_type': 'CheckpointLoaderSimple', 'inputs': {'ckpt_name': 'demo.safetensors'}},
        '2': {'class_type': 'CLIPTextEncode', 'inputs': {'text': 'fixture forest'}},
        '3': {'class_type': 'CLIPTextEncode', 'inputs': {'text': 'blurry'}},
        '5': {'class_type': 'KSampler', 'inputs': {'positive': ['2', 0], 'negative': ['3', 0], 'seed': 2**64-1, 'steps': 20, 'cfg': 7, 'sampler_name': 'euler', 'scheduler': 'normal', 'denoise': 1}},
        '6': {'class_type': 'VAEDecode', 'inputs': {'samples': ['5', 0]}},
        '7': {'class_type': 'SaveImage', 'inputs': {'images': ['6', 0]}},
    }
    job_id = str(uuid4())
    jobs.reserve(context.DB, job_id, ENGINE, graph, 'demo.safetensors', 'fixture-v1')
    job = jobs.update(context.DB, job_id, status='completed', prompt_id=str(uuid4()), history={'status': {'completed': True, 'status_str': 'success'}, 'outputs': {'7': {'images': [{'filename': 'qa-artwork.png', 'subfolder': '', 'type': 'output'}]}}})
    artwork, _ = gallery.save(context.DB, data / 'artworks', job, gallery.outputs(job)[0], raw.getvalue())
    if count is not None:
        from scripts.listing_dataset import seed
        with closing(sqlite3.connect(context.DB)) as db, db:
            db.execute("DELETE FROM settings WHERE key GLOB 'artwork:*' OR key GLOB 'job:*' OR key GLOB 'asset:*'")
        seed(context, count)

    @app.middleware('http')
    async def delayed_save(request, call_next):
        if request.url.path in ('/api/drafts', '/api/flux/drafts') and request.method == 'POST':
            await asyncio.sleep(.5)
        return await call_next(request)

    wrapper = FastAPI(lifespan=app.router.lifespan_context)

    @wrapper.get('/qa/state')
    def status():
        return dict(state, artwork_id=artwork['id'], asset_id=asset['id'])

    @wrapper.post('/qa/conflict')
    def conflict():
        value = gallery.get(context.DB, artwork['id'])
        gallery.organize(context.DB, artwork['id'], value['revision'], {'notes': 'another window'})
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
    parser.add_argument('--legacy-ui', action='store_true', help='Use the fixed Q06 UI archived under runtime/q04-baseline-ui')
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix='atelier-browser-') as folder:
        uvicorn.run(fixture(Path(folder), args.count, args.legacy_ui), host='127.0.0.1', port=args.port, log_level='warning')
