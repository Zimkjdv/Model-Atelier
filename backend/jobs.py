"""Durable submission ledger; ambiguous upstream requests are never retried."""
import json
from copy import deepcopy
import sqlite3
from contextlib import closing
from datetime import datetime, timedelta, timezone


def display(value):
    # Old failures remain unclassified; GETs must not rewrite or guess causes.
    return dict(value, failure_info=value.get('failure_info'), lora_metadata=value.get('lora_metadata'))


def reserve(path, job_id, engine_url, workflow, checkpoint, model_version=None, model_metadata=None, lora_metadata=None,
            *, workflow_id=None, component_metadata=None, reference_metadata=None, reference_settings=None):
    with closing(sqlite3.connect(path)) as db, db:
        db.execute('BEGIN IMMEDIATE')
        row = db.execute('SELECT value FROM settings WHERE key=?', ('job:' + job_id,)).fetchone()
        if row:
            value = json.loads(row[0])
            if (any(value[k] != v for k, v in dict(engine_url=engine_url, workflow=workflow, checkpoint=checkpoint).items())
                    or value.get('workflow_id') != workflow_id or value.get('reference_settings') != reference_settings):
                raise ValueError('此請求 ID 已用於其他工作流程')
            return display(value), False
        frozen_refs = []
        for snapshot in reference_metadata or []:
            asset = db.execute('SELECT value FROM settings WHERE key=?', ('asset:' + snapshot['id'],)).fetchone()
            current = json.loads(asset[0]) if asset else None
            if not current or current.get('archived') or any(current.get(key) != snapshot.get(key) for key in ('sha256', 'size', 'width', 'height')):
                raise ValueError('輸入素材在提交期間已封存、遺失或變更，未提交任務')
            frozen_refs.append(dict(snapshot, title=current['title'], purpose=current.get('purpose', 'unspecified'), revision=current.get('revision', 0)))
        value = dict(id=job_id, prompt_id=job_id, engine_url=engine_url, workflow=workflow,
                     checkpoint=checkpoint, model_version=model_version or '未知', model_metadata=deepcopy(model_metadata),
                     lora_metadata=deepcopy(lora_metadata), workflow_id=workflow_id, component_metadata=deepcopy(component_metadata),
                     reference_metadata=deepcopy(frozen_refs) if reference_metadata is not None else None,
                     reference_settings=deepcopy(reference_settings),
                     status='validating', error=None, history=None, failure_info=None,
                     revision=0, created_at=datetime.now(timezone.utc).isoformat())
        db.execute('INSERT INTO settings VALUES (?, ?)', ('job:' + job_id, json.dumps(value, ensure_ascii=False)))
        return value, True


def get(path, job_id):
    with closing(sqlite3.connect(path)) as db:
        row = db.execute('SELECT value FROM settings WHERE key=?', ('job:' + job_id,)).fetchone()
    if not row:
        raise KeyError(job_id)
    return display(json.loads(row[0]))


def _update(path, job_id, expected_revision, changes):
    if any(name in changes for name in ('model_version', 'model_metadata', 'lora_metadata', 'workflow_id', 'component_metadata', 'reference_metadata', 'reference_settings')):
        raise ValueError('提交時的模型資料快照不可變更或回填')
    with closing(sqlite3.connect(path)) as db, db:
        db.execute('BEGIN IMMEDIATE')
        row = db.execute('SELECT value FROM settings WHERE key=?', ('job:' + job_id,)).fetchone()
        if row is None:
            raise KeyError(job_id)
        value = json.loads(row[0])
        revision = value.get('revision', 0)
        if expected_revision is not None and revision != expected_revision:
            return display(value), False
        value.update(changes, revision=revision + 1, updated_at=datetime.now(timezone.utc).isoformat())
        db.execute('UPDATE settings SET value=? WHERE key=?', (json.dumps(value, ensure_ascii=False), 'job:' + job_id))
    return display(value), True


def update(path, job_id, **changes):
    return _update(path, job_id, None, changes)[0]


def compare_update(path, snapshot, **changes):
    """Reject stale remote observations without overwriting a newer job state."""
    return _update(path, snapshot['id'], snapshot.get('revision', 0), changes)


def claim_watch(path, job_id, owner, seconds=60):
    """One upstream progress reader across workers, independent of job revision."""
    key = 'watch:' + job_id
    timestamp = datetime.now(timezone.utc)
    with closing(sqlite3.connect(path)) as db, db:
        db.execute('BEGIN IMMEDIATE')
        row = db.execute('SELECT value FROM settings WHERE key=?', (key,)).fetchone()
        if row:
            value = json.loads(row[0])
            if value['owner'] != owner and datetime.fromisoformat(value['expires']) > timestamp:
                return False
        value = dict(owner=owner, expires=(timestamp + timedelta(seconds=seconds)).isoformat())
        db.execute('INSERT OR REPLACE INTO settings VALUES (?, ?)', (key, json.dumps(value)))
    return True


def release_watch(path, job_id, owner):
    with closing(sqlite3.connect(path)) as db, db:
        db.execute('BEGIN IMMEDIATE')
        row = db.execute('SELECT value FROM settings WHERE key=?', ('watch:' + job_id,)).fetchone()
        if row and json.loads(row[0])['owner'] == owner:
            db.execute('DELETE FROM settings WHERE key=?', ('watch:' + job_id,))


def list_all(path):
    with closing(sqlite3.connect(path)) as db:
        rows = db.execute("SELECT value FROM settings WHERE key LIKE 'job:%'").fetchall()
    return sorted((display(json.loads(row[0])) for row in rows), key=lambda item: item['created_at'], reverse=True)
