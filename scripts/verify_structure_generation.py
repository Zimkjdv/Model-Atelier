"""One explicitly selected R01 GPU run; --verify performs local GET checks only."""

import argparse
import hashlib
import json
from pathlib import Path
import time
from uuid import uuid4
from fastapi.testclient import TestClient
from backend.main import create_app
from backend import assets, catalog, control_catalog
from scripts import install_model, install_pony


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--kind', choices=['pose', 'depth'], required=True)
    parser.add_argument('--source', type=Path)
    parser.add_argument('--report', type=Path, required=True)
    parser.add_argument('--verify', action='store_true')
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    report = args.report.resolve()
    if not report.is_relative_to(root / 'runtime'):
        raise ValueError('Report must be inside runtime')
    data = root / 'runtime' / 'r01-live-20261023' / 'data'
    app = create_app(data_root=data)
    host = app.state.context
    with TestClient(app) as client:

        def call(method, path, **kw):
            r = client.request(method, '/api/' + path, **kw)
            r.raise_for_status()
            return r.json()

        if args.verify:
            value = json.loads(report.read_text(encoding='utf-8'))
            job = call('GET', 'jobs/' + value['job_id'])
            assert (
                job['reference_settings'] == value['settings']
                and job['workflow'] == value['workflow']
            )
            for prefix in ['jobs/' + job['id']] + ['artworks/' + i for i in value['artwork_ids']]:
                restored = call('GET', prefix + '/creation-settings')
                assert restored['settings'] == value['settings']
            raw = client.get('/api/jobs/' + job['id'] + '/structure-output/image')
            raw.raise_for_status()
            assert hashlib.sha256(raw.content).hexdigest() == value['condition']['sha256']
            print('GET-only verification passed')
            return
        if report.exists():
            raise ValueError('Report already exists; use --verify')
        model = install_model.manifest('animagine-xl-4.0-opt')
        control = install_model.manifest(
            'controlnet-openpose-sdxl-1.0'
            if args.kind == 'pose'
            else 'controlnet-depth-sdxl-1.0-fp16'
        )
        for m in (model, control):
            target = install_pony._paths(root, m['filename'], create=False)[0]
            if not install_pony._verified(target, m):
                raise ValueError('Fixed weight mismatch')
        call('POST', 'models/sync', json=dict(comfy_url='http://127.0.0.1:8188'))
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
        call('POST', 'controlnets/sync', json=dict(engine_url=host.engine_url()))
        control_catalog.update_metadata(
            host.DB,
            host.engine_url(),
            control['filename'],
            dict(
                architecture='sdxl',
                kind=args.kind,
                version=control['version'],
                sha256=control['sha256'],
                size_bytes=control['size_bytes'],
                source_url=control['source']['page_url'],
            ),
        )
        source = assets.create(host.DB, data / 'assets', args.source.read_bytes(), args.source.name)
        settings = host.StructureInput(
            title='R01 ' + args.kind,
            engine_url=host.engine_url(),
            checkpoint=model['filename'],
            prompt='masterpiece, best quality, anime illustration, one adult woman, brown hair, green eyes, long blue coat, fully clothed, standing in a park',
            negative_prompt='text, watermark, blurry, multiple people',
            width=768,
            height=768,
            steps=20,
            cfg=5.0,
            sampler_name='euler_ancestral',
            scheduler='normal',
            seed='9007199254740993',
            image_asset_id=source['id'],
            reference_ids=[source['id']],
            control_kind=args.kind,
            control_net_name=control['filename'],
        ).model_dump(mode='json', exclude={'revision'})
        value = dict(
            status='submitted',
            kind=args.kind,
            job_id=str(uuid4()),
            settings=settings,
            source_sha256=source['sha256'],
        )
        report.parent.mkdir(parents=True, exist_ok=True)
        with report.open('x', encoding='utf-8') as f:
            json.dump(value, f, ensure_ascii=False, indent=2)
        # The durable UUID is written before the only generation request.
        job = call('POST', 'structure/generate', json=settings | dict(request_id=value['job_id']))
        end = time.monotonic() + 900
        while (
            job['status'] not in ('completed', 'failed', 'cancelled', 'stopped')
            and time.monotonic() < end
        ):
            time.sleep(2)
            job = call('POST', 'jobs/' + value['job_id'] + '/refresh')
        value.update(
            status=job['status'],
            workflow=job['workflow'],
            reference_metadata=job['reference_metadata'],
            component_metadata=job['component_metadata'],
            runtime_metadata=job.get('runtime_metadata'),
            error=job.get('error'),
        )
        report.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')
        if job['status'] != 'completed':
            raise ValueError(str(job.get('history') or job))
        condition = call('POST', 'jobs/' + job['id'] + '/structure-output')
        imported = call('POST', 'jobs/' + job['id'] + '/artworks')
        value['artwork_ids'] = [i['id'] for i in imported['imported'] + imported['existing']]
        assert len(value['artwork_ids']) == 1, imported
        assert call('GET', 'jobs/' + job['id'] + '/creation-settings')['settings'] == settings
        value['condition'] = condition
        value['status'] = 'passed'
        report.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')
        print('passed', args.kind, job['id'])


if __name__ == '__main__':
    main()
