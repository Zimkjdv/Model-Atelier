"""Synthetic V04 browser data; never load weights or contact an engine."""

from contextlib import closing
import io
import json
import sqlite3
from uuid import uuid4

from PIL import Image

from backend import catalog, gallery, job_measurements, jobs, loras, workflows
from backend.schemas import DraftInput


def prepare(context, root, engine):
    manifests = [
        json.loads((root / 'models' / (name + '.json')).read_text(encoding='utf-8'))
        for name in (
            'animagine-xl-4.0-opt',
            'pony-v6-xl',
            'lcm-lora-sdxl',
            'ikea-instructions-lora-sdxl',
            'pixel-art-lora-sdxl-comfy-v1',
        )
    ]
    catalog.merge(context.DB, engine, ['demo.safetensors'] + [v['filename'] for v in manifests[:2]])
    for model in manifests[:2]:
        catalog.update_metadata(
            context.DB,
            engine,
            model['filename'],
            dict(version=model['version'], architecture='sdxl', sha256=model['sha256']),
        )
    loras.merge(context.DB, engine, [v['filename'] for v in manifests[2:]] + ['fixture-disabled'])
    for model in manifests[2:]:
        loras.update_metadata(
            context.DB,
            engine,
            model['filename'],
            dict(version=model['version'], architecture='sdxl', sha256=model['sha256']),
        )
    choices = [
        dict(name=manifests[2]['filename'], enabled=True, strength_model=1, strength_clip=0),
        dict(name=manifests[3]['filename'], enabled=True, strength_model=1, strength_clip=1),
    ]
    settings = DraftInput(
        title='V04 synthetic baseline',
        engine_url=engine,
        checkpoint=manifests[0]['filename'],
        prompt='black and white line drawing, instruction manual, assembling a wooden chair, white background, no humans',
        negative_prompt='fixture negative',
        seed='9007199254740993',
        steps=8,
        cfg=1,
        sampler_name='lcm',
        scheduler='sgm_uniform',
        loras=choices,
    ).model_dump(mode='json', exclude={'revision'})
    outputs = []
    original_engine = 'http://original-measurement.invalid:8188'
    for kind in ('measured', 'zero', 'legacy'):
        identifier = str(uuid4())
        current = settings | dict(
            title='v04-' + kind,
            engine_url=original_engine,
            width=64,
            height=64,
            loras=[],
        )
        jobs.reserve(
            context.DB,
            identifier,
            original_engine,
            workflows.build(current),
            current['checkpoint'],
            'fixture-v04',
        )
        value = jobs.get(context.DB, identifier)
        value['status'] = 'submitting'
        job_measurements.advance(value, '2026-10-08T00:00:00+00:00')
        value.update(status='completed', prompt_id=identifier)
        value['history'] = dict(
            status=dict(
                completed=True,
                status_str='success',
                messages=[
                    ['execution_start', dict(prompt_id=identifier, timestamp=1000)],
                    [
                        'execution_success',
                        dict(prompt_id=identifier, timestamp=1000 if kind == 'zero' else 3500),
                    ],
                ],
            ),
            outputs={
                '7': dict(
                    images=[dict(filename='v04-' + kind + '.png', subfolder='', type='output')]
                )
            },
        )
        stats = dict(
            system=dict(ram_total=8 * 1024**3, ram_free=6 * 1024**3),
            devices=[
                dict(
                    name='Fixture GPU',
                    type='cuda',
                    index=0,
                    vram_total=4 * 1024**3,
                    vram_free=3 * 1024**3,
                ),
                dict(
                    name='Fixture CPU', type='cpu', index=1, vram_total=256 * 1024**2, vram_free=0
                ),
            ],
        )
        value['measurements']['resources_before_submission'] = job_measurements.resources(
            stats if kind == 'measured' else None,
            original_engine,
            '2026-10-08T00:00:00+00:00',
        )
        job_measurements.advance(
            value,
            '2026-10-08T00:00:00+00:00' if kind == 'zero' else '2026-10-08T00:00:07+00:00',
        )
        if kind == 'legacy':
            value.pop('measurements')
        with closing(sqlite3.connect(context.DB)) as db, db:
            db.execute(
                'UPDATE settings SET value=? WHERE key=?', (json.dumps(value), 'job:' + identifier)
            )
        encoded = io.BytesIO()
        Image.new('RGB', (64, 64), '#718d76').save(encoded, 'PNG')
        artwork, _ = gallery.save(
            context.DB,
            context.DATA / 'artworks',
            value,
            gallery.outputs(value)[0],
            encoded.getvalue(),
        )
        outputs.append(dict(kind=kind, job=jobs.get(context.DB, identifier), artwork=artwork))
    return dict(settings=settings, models=[v['filename'] for v in manifests[:2]], outputs=outputs)
