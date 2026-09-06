"""Engine-scoped snapshots; listing a checkpoint does not verify compatibility."""
import json
import sqlite3
from contextlib import closing
from datetime import datetime, timezone


def read(db_path, url):
    with closing(sqlite3.connect(db_path)) as db:
        row = db.execute('SELECT value FROM settings WHERE key=?', ('catalog:' + url,)).fetchone()
    return json.loads(row[0]) if row else dict(engine_url=url, models=[], selected=None, synced_at=None, sync_error=None)


def write(db_path, value):
    with closing(sqlite3.connect(db_path)) as db, db:
        db.execute('INSERT OR REPLACE INTO settings VALUES (?, ?)',
                   ('catalog:' + value['engine_url'], json.dumps(value, ensure_ascii=False)))


def checkpoint_names(payload):
    try:
        names = payload['CheckpointLoaderSimple']['input']['required']['ckpt_name'][0]
    except (KeyError, IndexError, TypeError) as exc:
        raise ValueError('ComfyUI 未提供有效的 checkpoint 清單') from exc
    if not isinstance(names, list) or any(not isinstance(name, str) or not name.strip() for name in names):
        raise ValueError('ComfyUI checkpoint 清單格式不正確')
    return sorted(set(names), key=str.casefold)


def merge(db_path, url, names):
    value = read(db_path, url)
    models = {item['name']: item for item in value['models']}
    for item in models.values():
        item['listed'] = False
    for name in names:
        models.setdefault(name, dict(name=name, notes='', source_url=''))['listed'] = True
    value.update(models=sorted(models.values(), key=lambda item: item['name'].casefold()),
                 synced_at=datetime.now(timezone.utc).isoformat(), sync_error=None)
    write(db_path, value)
    return value
