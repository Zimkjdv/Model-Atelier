"""Versioned creation drafts stored locally, without submitting GPU work."""
import json
import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from uuid import uuid4


def list_all(path):
    with closing(sqlite3.connect(path)) as db:
        rows = db.execute("SELECT value FROM settings WHERE key LIKE 'draft:%'").fetchall()
    return sorted((json.loads(row[0]) for row in rows), key=lambda item: item['updated_at'], reverse=True)


def save(path, payload, draft_id=None, revision=None):
    with closing(sqlite3.connect(path)) as db, db:
        db.execute('BEGIN IMMEDIATE')
        now = datetime.now(timezone.utc).isoformat()
        if draft_id:
            row = db.execute('SELECT value FROM settings WHERE key=?', ('draft:' + draft_id,)).fetchone()
            if not row:
                raise KeyError('草稿不存在')
            old = json.loads(row[0])
            if revision != old['revision']:
                raise ValueError('草稿已在其他視窗更新，請載入最新版本或另存新草稿')
        else:
            draft_id = str(uuid4())
            old = dict(created_at=now, revision=0)
        result = dict(**payload, id=draft_id, revision=old['revision'] + 1,
                      created_at=old['created_at'], updated_at=now)
        db.execute('INSERT OR REPLACE INTO settings VALUES (?, ?)', ('draft:' + draft_id, json.dumps(result, ensure_ascii=False)))
    return result
