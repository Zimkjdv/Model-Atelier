"""Durable submission ledger; ambiguous upstream requests are never retried."""
import json
import sqlite3
from contextlib import closing
from datetime import datetime, timezone


def reserve(path, job_id, engine_url, workflow, checkpoint):
    with closing(sqlite3.connect(path)) as db, db:
        db.execute('BEGIN IMMEDIATE')
        row = db.execute('SELECT value FROM settings WHERE key=?', ('job:' + job_id,)).fetchone()
        if row:
            value = json.loads(row[0])
            if any(value[k] != v for k, v in dict(engine_url=engine_url, workflow=workflow, checkpoint=checkpoint).items()):
                raise ValueError('此請求 ID 已用於其他工作流程')
            return value, False
        value = dict(id=job_id, prompt_id=job_id, engine_url=engine_url, workflow=workflow,
                     checkpoint=checkpoint, status='validating', error=None, history=None,
                     created_at=datetime.now(timezone.utc).isoformat())
        db.execute('INSERT INTO settings VALUES (?, ?)', ('job:' + job_id, json.dumps(value, ensure_ascii=False)))
        return value, True


def get(path, job_id):
    with closing(sqlite3.connect(path)) as db:
        row = db.execute('SELECT value FROM settings WHERE key=?', ('job:' + job_id,)).fetchone()
    if not row:
        raise KeyError(job_id)
    return json.loads(row[0])


def update(path, job_id, **changes):
    with closing(sqlite3.connect(path)) as db, db:
        db.execute('BEGIN IMMEDIATE')
        value = json.loads(db.execute('SELECT value FROM settings WHERE key=?', ('job:' + job_id,)).fetchone()[0])
        value.update(changes, updated_at=datetime.now(timezone.utc).isoformat())
        db.execute('UPDATE settings SET value=? WHERE key=?', (json.dumps(value, ensure_ascii=False), 'job:' + job_id))
    return value


def list_all(path):
    with closing(sqlite3.connect(path)) as db:
        rows = db.execute("SELECT value FROM settings WHERE key LIKE 'job:%'").fetchall()
    return sorted((json.loads(row[0]) for row in rows), key=lambda item: item['created_at'], reverse=True)
