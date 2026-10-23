"""Bounded, read-only report from one SQLite snapshot; never infer job associations."""

import hashlib
import json
import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from copy import deepcopy
from uuid import UUID
from backend import gallery, image_workflows, workflows

MAX_BYTES = 8 * 1024 * 1024
MAX_ENTRIES = 100
JOB_FIELDS = (
    'id',
    'prompt_id',
    'status',
    'error',
    'failure_info',
    'revision',
    'created_at',
    'updated_at',
    'engine_url',
    'checkpoint',
    'model_version',
    'model_metadata',
    'lora_metadata',
    'component_metadata',
    'reference_metadata',
    'reference_settings',
    'workflow_id',
    'workflow',
    'experiment_context',
    'runtime_metadata',
    'measurements',
)
ART_FIELDS = (
    'id',
    'job_id',
    'title',
    'width',
    'height',
    'sha256',
    'size',
    'created_at',
    'archived',
    'favorite',
    'notes',
    'ratings',
    'revision',
)


def encoded(value):
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False
    ).encode('utf-8')


class ReportTooLarge(ValueError):
    pass


class ReportMissing(KeyError):
    pass


def create(path, folder, identifier, expected_hash, validate):
    with closing(sqlite3.connect(path.resolve().as_uri() + '?mode=ro', uri=True)) as db:
        db.execute('BEGIN')
        row = db.execute(
            'SELECT value FROM settings WHERE key=?', ('experiment:' + identifier,)
        ).fetchone()
        if not row:
            raise ReportMissing(identifier)
        record = json.loads(row[0])
        plan = validate(record['plan'])
        if record.get('id') != identifier or plan['plan_sha256'] != expected_hash:
            raise ValueError('報告來源與目前方案不同，請重載方案')
        record = record | dict(plan=plan)
        variants = {v['id']: v for v in plan['variants']}
        selected_jobs = {}
        selected_art = []
        budget = len(encoded(record))
        entries = 0

        def expected_context(context):
            variant = variants.get(context.get('variant_id'))
            if not variant:
                raise ValueError('比較關聯指向不存在的組別，未匯出部分報告')
            expected = dict(
                plan_id=identifier,
                plan_sha256=expected_hash,
                variant_id=variant['id'],
                schema_version=1,
                plan_title=plan['title'],
                workflow_id=plan['workflow_id'],
                axis=plan['axis'],
                target_lora=plan.get('target_lora'),
                case_id=variant['case_id'],
                value=variant['value'],
                settings=variant['settings'],
            )
            if encoded(context) != encoded(expected):
                raise ValueError('保存的比較關聯與原組設定不同，未匯出部分報告')
            return variant

        for key, raw in db.execute(
            "SELECT key,value FROM settings WHERE key LIKE 'job:%' OR key LIKE 'artwork:%'"
        ):
            item = json.loads(raw)
            if not isinstance(item, dict):
                raise ValueError('保存的任務或作品格式損壞，未匯出部分報告')
            context = item.get('experiment_context')
            if not isinstance(context, dict) or context.get('plan_id') != identifier:
                continue
            variant = expected_context(context)
            entries += 1
            if entries > MAX_ENTRIES:
                raise ReportTooLarge(
                    '報告最多包含 100 筆任務與作品，請使用各任務 JSON 分別匯出；未截斷報告'
                )
            if key.startswith('job:'):
                if key != 'job:' + str(UUID(item['id'])):
                    raise ValueError('任務 ID 不符')
                settings = variant['settings']
                graph = (
                    image_workflows.build(settings, item['id'])
                    if plan['workflow_id'] == 'checkpoint-image2image-v1'
                    else workflows.build(settings)
                )
                if (
                    encoded(item.get('workflow')) != encoded(graph)
                    or item.get('checkpoint') != settings['checkpoint']
                    or item.get('engine_url') != settings['engine_url']
                ):
                    raise ValueError('原任務流程與比較組不同，未匯出部分報告')
                if plan['workflow_id'] == 'checkpoint-image2image-v1' and encoded(
                    item.get('reference_settings')
                ) != encoded(settings):
                    raise ValueError('原圖生圖設定不同')
                output = {k: deepcopy(item.get(k)) for k in JOB_FIELDS}
                output['workflow_sha256'] = hashlib.sha256(encoded(item['workflow'])).hexdigest()
                selected_jobs[item['id']] = output
                budget += len(encoded(output))
            else:
                if key != 'artwork:' + str(UUID(item['id'])) or item.get('extension') not in (
                    'png',
                    'jpg',
                    'jpeg',
                    'webp',
                ):
                    raise ValueError('作品 ID 或格式不符')
                projected = {
                    k: deepcopy(gallery.organization_defaults(item).get(k)) for k in ART_FIELDS
                }
                selected_art.append(
                    projected
                    | dict(
                        extension=item['extension'], experiment_context=item['experiment_context']
                    )
                )
                budget += len(encoded(projected)) + 256
            if budget > MAX_BYTES:
                raise ReportTooLarge('比較報告超過 8 MiB，請分別下載原任務 JSON；未截斷報告')
    # Filesystem flags are existence-only observations outside the DB snapshot.
    outputs = {}
    for item in selected_art:
        job = selected_jobs.get(item.get('job_id'))
        if not job or encoded(item['experiment_context']) != encoded(job['experiment_context']):
            raise ValueError('作品缺少相符的原任務，未匯出部分報告')
        output = {k: deepcopy(gallery.organization_defaults(item).get(k)) for k in ART_FIELDS}
        output.update(
            image_available=(folder / (item['id'] + '.' + item['extension'])).is_file(),
            thumbnail_available=(folder / (item['id'] + '.thumb.png')).is_file(),
            current_file_hash_verified=False,
        )
        outputs.setdefault(job['id'], []).append(output)
    groups = [
        dict(variant_id=v['id'], case_id=v['case_id'], value=v['value'], runs=[])
        for v in plan['variants']
    ]
    index = {v['variant_id']: v for v in groups}
    for job in sorted(
        selected_jobs.values(), key=lambda v: (v['created_at'], v['id']), reverse=True
    ):
        index[job['experiment_context']['variant_id']]['runs'].append(
            job | dict(artworks=sorted(outputs.get(job['id'], []), key=lambda a: a['id']))
        )
    report = dict(
        kind='model-atelier-comparison-results',
        schema_version=1,
        generated_at=datetime.now(timezone.utc).isoformat(),
        source='saved-platform-records',
        plan=record,
        variants=groups,
        notes=[
            '同一 SQLite 讀取快照；不查詢引擎、不生成、不回填歷史。',
            '任務狀態、耗時與版本是平台保存值，不保證目前引擎狀態。',
            '檔案存在旗標於匯出時另行檢查，未重新校驗 PNG；人工評分與筆記是目前保存值。',
            '報告不含圖片 bytes，不能匯入作為生成請求或還原資料備份。',
        ],
    )
    raw = encoded(report)
    if len(raw) > MAX_BYTES:
        raise ReportTooLarge('比較報告超過 8 MiB，未截斷報告')
    return raw
