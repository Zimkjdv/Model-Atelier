"""One finite R03 comparison case; an existing report only permits --verify."""

import argparse
import hashlib
import io
import json
from pathlib import Path
import time
from uuid import uuid4
from PIL import Image, ImageChops, ImageOps, ImageDraw
from fastapi.testclient import TestClient
from backend.main import create_app
from backend import assets, catalog, fooocus_workflows
from scripts import install_model, install_pony


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source', type=Path)
    p.add_argument('--target', choices=['park', 'coat'], default='park')
    p.add_argument('--radius', type=int, choices=[0, 16], default=16)
    p.add_argument(
        '--seed', choices=['9007199254740993', '18446744073709551615'], default='9007199254740993'
    )
    p.add_argument('--baseline', action='store_true')
    p.add_argument('--report', type=Path, required=True)
    p.add_argument('--verify', action='store_true')
    a = p.parse_args()
    root = Path(__file__).resolve().parents[1]
    report = a.report.resolve()
    if not report.is_relative_to(root / 'runtime'):
        raise ValueError('Report outside runtime')
    data = root / 'runtime/r03-live-20261023/data'
    app = create_app(data_root=data)
    host = app.state.context
    with TestClient(app) as client:

        def call(method, path, **kw):
            r = client.request(method, '/api/' + path, **kw)
            r.raise_for_status()
            return r.json()

        if a.verify:
            value = json.loads(report.read_text(encoding='utf-8'))
            job = call('GET', 'jobs/' + value['job_id'])
            assert (
                job['workflow'] == value['workflow']
                and job['reference_settings'] == value['settings']
                and job['reference_metadata'] == value['reference_metadata']
            )
            for prefix in ['jobs/' + job['id']] + ['artworks/' + i for i in value['artwork_ids']]:
                assert call('GET', prefix + '/creation-settings')['settings'] == value['settings']
            for suffix, key in [
                ('reference-image', 'input_sha256'),
                ('reference-mask', 'mask_sha256'),
                ('reference-blend-mask', 'blend_sha256'),
            ]:
                raw = client.get('/api/jobs/' + job['id'] + '/' + suffix)
                raw.raise_for_status()
                assert hashlib.sha256(raw.content).hexdigest() == value[key]
            result = client.get('/api/artworks/' + value['artwork_ids'][0] + '/image')
            result.raise_for_status()
            assert hashlib.sha256(result.content).hexdigest() == value['output_sha256']
            print('GET-only verification passed')
            return
        if report.exists():
            raise ValueError('Report exists; only --verify allowed')
        if not a.source:
            p.error('--source required for generation')
        for m in [install_model.manifest('animagine-xl-4.0-opt')] + (
            [] if a.baseline else fooocus_workflows.WEIGHTS
        ):
            if not install_pony._verified(
                install_pony._paths(root, m['filename'], create=False)[0], m
            ):
                raise ValueError('Fixed weight mismatch')
        model = fooocus_workflows.BASE
        call('POST', 'models/sync', json=dict(comfy_url=host.engine_url()))
        catalog.update_metadata(
            host.DB,
            host.engine_url(),
            model['filename'],
            dict(
                architecture='sdxl',
                version=model['version'],
                sha256=model['sha256'],
                size_bytes=model['size_bytes'],
                source_url=model['source']['page_url'],
            ),
        )
        source = assets.create(host.DB, data / 'assets', a.source.read_bytes(), a.source.name)
        mask = Image.new('RGB', (source['width'], source['height']), 'black')
        draw = ImageDraw.Draw(mask)
        box = (70, 390, 270, 650) if a.target == 'park' else (300, 450, 520, 670)
        draw.rectangle(box, fill='white')
        out = io.BytesIO()
        mask.save(out, format='PNG')
        mask_record = assets.create(
            host.DB, data / 'assets', out.getvalue(), 'r03-' + a.target + '-mask.png'
        )
        fields = dict(
            title='R03 ' + a.target + (' baseline' if a.baseline else ' Fooocus'),
            engine_url=host.engine_url(),
            checkpoint=model['filename'],
            prompt='masterpiece, best quality, anime illustration, '
            + (
                'a flowering shrub with small white flowers beside a park path, green foliage'
                if a.target == 'park'
                else 'long elegant dark blue coat with small gold embroidered flower patterns'
            ),
            negative_prompt='text, watermark, blurry, bad anatomy',
            width=768,
            height=768,
            steps=20,
            cfg=5.0,
            sampler_name='euler_ancestral',
            scheduler='normal',
            seed=a.seed,
            denoise=1.0,
            image_asset_id=source['id'],
            mask_asset_id=mask_record['id'],
            reference_ids=[source['id'], mask_record['id']],
            grow_mask_by=6,
            feather_radius=a.radius,
        )
        if not a.baseline:
            fields['inpaint_model'] = 'fooocus-v2.6'
        schema = host.InpaintFeatherInput if a.baseline else host.FooocusInput
        settings = schema(**fields).model_dump(mode='json', exclude={'revision'})
        value = dict(
            status='submitted',
            job_id=str(uuid4()),
            settings=settings,
            target=a.target,
            baseline=a.baseline,
            source_sha256=source['sha256'],
        )
        report.parent.mkdir(parents=True, exist_ok=True)
        with report.open('x', encoding='utf-8') as f:
            json.dump(value, f, ensure_ascii=False, indent=2)
        job = call(
            'POST',
            ('inpaint-feather' if a.baseline else 'fooocus-inpaint') + '/generate',
            json=settings | dict(request_id=value['job_id']),
        )
        end = time.monotonic() + 900
        while (
            job['status'] not in ('completed', 'failed', 'cancelled', 'stopped')
            and time.monotonic() < end
        ):
            time.sleep(2)
            job = call('POST', 'jobs/' + job['id'] + '/refresh')
        value.update(
            status=job['status'],
            workflow=job['workflow'],
            reference_metadata=job['reference_metadata'],
            runtime_metadata=job.get('runtime_metadata'),
            error=job.get('error'),
        )
        report.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')
        if job['status'] != 'completed':
            raise ValueError(str(job.get('history') or job))
        imported = call('POST', 'jobs/' + job['id'] + '/artworks')
        value['artwork_ids'] = [i['id'] for i in imported['imported'] + imported['existing']]
        assert len(value['artwork_ids']) == 1, imported
        assert call('GET', 'jobs/' + job['id'] + '/creation-settings')['settings'] == settings
        raw_inputs = {}
        for suffix, key in [
            ('reference-image', 'input_sha256'),
            ('reference-mask', 'mask_sha256'),
            ('reference-blend-mask', 'blend_sha256'),
        ]:
            raw = client.get('/api/jobs/' + job['id'] + '/' + suffix)
            raw.raise_for_status()
            value[key] = hashlib.sha256(raw.content).hexdigest()
            raw_inputs[suffix] = raw.content
        result = client.get('/api/artworks/' + value['artwork_ids'][0] + '/image')
        result.raise_for_status()
        original = Image.open(io.BytesIO(raw_inputs['reference-image'])).convert('RGB')
        output = Image.open(io.BytesIO(result.content)).convert('RGB')
        binary = Image.open(io.BytesIO(raw_inputs['reference-mask'])).convert('L')
        diff = ImageChops.difference(original, output)
        outside = ImageChops.multiply(diff, ImageOps.invert(binary).convert('RGB'))
        value['outside_mask_max_rgb_difference'] = max(v[1] for v in outside.getextrema())
        value['output_sha256'] = hashlib.sha256(result.content).hexdigest()
        value['status'] = 'passed'
        assert value['outside_mask_max_rgb_difference'] == 0
        report.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')
        print('passed', value['job_id'])


if __name__ == '__main__':
    main()
