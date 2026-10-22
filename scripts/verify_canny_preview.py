"""Compare one ephemeral CPU preview with an existing saved native Canny edge.

Never submits a workflow, syncs a catalog, imports an edge or changes a job.
--verify-report is strictly GET-only and checks the saved CPU evidence offline.
"""
import argparse
import base64
import hashlib
import io
import json
from pathlib import Path
from uuid import UUID
import httpx
from PIL import Image, ImageChops
from backend import canny_preview as preview, control_edge_workflows, control_edges
from scripts.verify_local_generation import local_url

ROOT = Path(__file__).resolve().parents[1]


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def compare(cpu, native, width, height):
    control_edges.pixels(cpu, width, height)
    control_edges.pixels(native, width, height)
    with Image.open(io.BytesIO(cpu)) as left, Image.open(io.BytesIO(native)) as right:
        left.load(); right.load()
        changed = sum(ImageChops.difference(left, right).getchannel('R').histogram()[1:])
        return dict(differing_pixels=changed, total_pixels=width*height,
                    cpu_rgb_sha256=digest(left.tobytes()), native_rgb_sha256=digest(right.tobytes()),
                    cpu_edge_pixels=left.getchannel('R').histogram()[255], native_edge_pixels=right.getchannel('R').histogram()[255])


def get(client, path):
    response = client.get(path)
    response.raise_for_status()
    return response


def capture(client, job_id):
    job = get(client, '/api/jobs/'+job_id).json()
    if job.get('id') != job_id or job.get('status') != 'completed' or job.get('workflow_id') != control_edge_workflows.ID:
        raise ValueError('A completed v2 job is required')
    edge = get(client, '/api/jobs/'+job_id+'/control-edge').json()
    anchor, source = control_edges.source(job, lambda value: value)
    if edge.get('state') != 'saved' or edge.get('image_available') is not True or edge.get('anchor') != anchor or edge.get('source') != source:
        raise ValueError('Original edge evidence is unavailable or mismatched; never import or recompute it here')
    raw = get(client, '/api/jobs/'+job_id+'/control-edge/image').content
    if digest(raw) != edge.get('sha256') or len(raw) != edge.get('size_bytes'):
        raise ValueError('Saved native edge checksum differs')
    return job, edge, raw


def run(client, job_id, previous=None, cpu=None):
    job, edge, native = capture(client, job_id)
    settings = {k: job['reference_settings'][k] for k in ('image_asset_id','reference_resize','width','height','canny_low','canny_high')}
    value = preview.Input.model_validate(settings)
    if previous is None:
        response = client.post('/api/control/preview', json=settings, timeout=55)
        response.raise_for_status()
        encoded = response.headers.get('X-Atelier-Canny-Provenance', '')
        info = json.loads(base64.b64decode(encoded, validate=True))
        cpu = response.content
    else:
        info = previous['preview']
        if digest(cpu) != previous['cpu_png_sha256']:
            raise ValueError('Saved CPU preview checksum differs')
    extras = {'image_asset_id','asset_sha256','reference_resize','preprocessing'}
    preview.checked_output(json.dumps({k:v for k,v in info.items() if k not in extras}).encode()+b'\n'+cpu,
        # Only the digest is required by the validator; validate it against the saved input below.
        get(client, '/api/jobs/'+job_id+'/reference-image').content, value.model_dump(mode='json'))
    reference = job['reference_metadata'][0]
    if info.get('image_asset_id') != settings['image_asset_id'] or info.get('asset_sha256') != reference['sha256'] or info.get('preprocessing') != reference['generation_preprocessing'] or info.get('reference_resize') != settings['reference_resize']:
        raise ValueError('CPU input differs from original immutable generation input')
    report = dict(schema='canny-preview-comparison-v1',job_id=job_id,job_sha256=control_edges.digest(job),
        edge=edge,preview=info,cpu_png_sha256=digest(cpu),native_png_sha256=digest(native),
        comparison=compare(cpu,native,value.width,value.height))
    if previous is not None and report != previous:
        raise ValueError('Saved comparison, original workflow or source changed')
    # A preview must not update even a completed original record.
    if get(client, '/api/jobs/'+job_id).json() != job:
        raise ValueError('Original job changed during preview')
    return report, cpu


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--platform',default='http://127.0.0.1:8000')
    parser.add_argument('--job-id',required=True)
    parser.add_argument('--report',required=True)
    parser.add_argument('--verify-report',action='store_true')
    args = parser.parse_args(argv)
    job_id = str(UUID(args.job_id))
    if args.job_id != job_id:
        raise ValueError('Job ID must be a canonical UUID')
    target = (ROOT/args.report).resolve()
    if not target.is_relative_to((ROOT/'runtime').resolve()) or target.suffix != '.json' or not target.parent.is_dir():
        raise ValueError('Report must be an existing runtime directory with a .json filename')
    png = target.with_suffix('.cpu.png')
    with httpx.Client(base_url=local_url(args.platform),trust_env=False,follow_redirects=False,timeout=15) as client:
        if args.verify_report:
            previous = json.loads(target.read_text(encoding='utf-8'))
            if previous.get('job_id') != job_id:
                raise ValueError('Original report job ID differs')
            if png.stat().st_size > preview.MAX_BYTES:
                raise ValueError('Saved CPU PNG too large')
            report, _ = run(client,job_id,previous,png.read_bytes())
        else:
            if target.exists() or png.exists():
                raise ValueError('Evidence already exists; use --verify-report, never overwrite or regenerate')
            report, cpu = run(client,job_id)
            # Only clean up files exclusively created by this invocation.
            owned=[]
            try:
                for path, raw in ((png,cpu),(target,(json.dumps(report,ensure_ascii=False,indent=2)+'\n').encode('utf-8'))):
                    with path.open('xb') as stream:
                        owned.append(path); stream.write(raw)
            except BaseException:
                for path in owned: path.unlink(missing_ok=True)
                raise
    print(json.dumps(dict(job_id=job_id,mode='GET-only' if args.verify_report else 'CPU-preview-only',**report['comparison'])))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
