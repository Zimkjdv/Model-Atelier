"""Read saved associations only: no engine requests, inferred matches or replay."""
import json
import sqlite3
from contextlib import closing
from backend import gallery


def read(path, record, folder):
    plan = record['plan']
    def belongs(context):
        return isinstance(context, dict) and context.get('plan_id') == record['id'] and context.get('plan_sha256') == plan['plan_sha256']
    with closing(sqlite3.connect(path)) as db:
        rows = db.execute("SELECT key,value FROM settings WHERE key LIKE 'job:%' OR key LIKE 'artwork:%'").fetchall()
    jobs, artworks = {}, []
    for key, raw in rows:
        item = json.loads(raw)
        if not belongs(item.get('experiment_context')):
            continue
        if key.startswith('job:'):
            jobs[item['id']] = item
        else:
            artworks.append(gallery.organization_defaults(item))
    by_job = {}
    for item in artworks:
        job = jobs.get(item['job_id'])
        if not job or item['experiment_context'] != job['experiment_context']:
            continue
        output = {k:item[k] for k in ('id','title','width','height','sha256','archived','ratings')} | dict(
            image_available=(folder / (item['id'] + '.' + item['extension'])).is_file(),
            thumbnail_available=(folder / (item['id'] + '.thumb.png')).is_file())
        by_job.setdefault(job['id'], []).append(output)
    groups = [dict(variant_id=v['id'], case_id=v['case_id'], value=v['value'], runs=[]) for v in plan['variants']]
    by_variant = {v['variant_id']:v for v in groups}
    for job in sorted(jobs.values(), key=lambda j:j['created_at'], reverse=True):
        group = by_variant.get(job['experiment_context'].get('variant_id'))
        if group is None:
            continue
        group['runs'].append({k:job.get(k) for k in ('id','prompt_id','status','error','failure_info','revision',
            'created_at','updated_at','engine_url','model_version','measurements')} | dict(artworks=by_job.get(job['id'], [])))
    return dict(plan_id=record['id'], plan_sha256=plan['plan_sha256'], archived=record['archived'], variants=groups)
