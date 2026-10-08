"""Immutable comparison plans; idempotent creation and revision-checked archive."""
import json
import sqlite3
from contextlib import closing
from datetime import datetime, timezone

PREFIX = 'experiment:'


def get(path, identifier):
    with closing(sqlite3.connect(path)) as db:
        row = db.execute('SELECT value FROM settings WHERE key=?', (PREFIX+identifier,)).fetchone()
    if not row:
        raise KeyError('找不到比較方案')
    return json.loads(row[0])


def summaries(path):
    result = []
    with closing(sqlite3.connect(path)) as db:
        for row in db.execute('SELECT value FROM settings WHERE key LIKE ?', (PREFIX+'%',)):
            value = json.loads(row[0]); plan = value['plan']
            result.append({key:value[key] for key in ('id','revision','archived','created_at','updated_at')} |
                          {key:plan[key] for key in ('title','workflow_id','axis','plan_sha256','expected_job_count')})
    return sorted(result, key=lambda v:(v['updated_at'],v['id']), reverse=True)


def save(path, identifier, plan):
    with closing(sqlite3.connect(path)) as db, db:
        db.execute('BEGIN IMMEDIATE')
        row = db.execute('SELECT value FROM settings WHERE key=?', (PREFIX+identifier,)).fetchone()
        if row:
            original = json.loads(row[0])
            if original['plan']['plan_sha256'] != plan['plan_sha256']:
                raise ValueError('同一保存 ID 已使用不同方案；未覆寫，請另存新方案')
            return original, False
        # Source existence is checked in the same transaction as archive protection.
        source = plan['baseline'].get('image_asset_id')
        if source:
            row = db.execute('SELECT value FROM settings WHERE key=?', ('asset:'+source,)).fetchone()
            if row and json.loads(row[0]).get('archived'):
                raise ValueError('原素材已封存；請先還原素材再保存方案，原預覽保留')
        now = datetime.now(timezone.utc).isoformat()
        result = dict(id=identifier, revision=1, archived=False, created_at=now, updated_at=now, plan=plan)
        db.execute('INSERT INTO settings VALUES (?,?)', (PREFIX+identifier,json.dumps(result,ensure_ascii=False,allow_nan=False)))
    return result, True


def archive(path, identifier, revision, archived):
    with closing(sqlite3.connect(path)) as db, db:
        db.execute('BEGIN IMMEDIATE')
        row = db.execute('SELECT value FROM settings WHERE key=?', (PREFIX+identifier,)).fetchone()
        if not row:
            raise KeyError('找不到比較方案')
        result = json.loads(row[0])
        if result['revision'] != revision:
            raise ValueError('方案已在其他視窗更新，請重新讀取；未覆寫原方案')
        result.update(revision=revision+1, archived=archived, updated_at=datetime.now(timezone.utc).isoformat())
        db.execute('UPDATE settings SET value=? WHERE key=?', (json.dumps(result,ensure_ascii=False,allow_nan=False),PREFIX+identifier))
    return result
