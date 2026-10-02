"""Engine-scoped snapshots; listing a checkpoint does not verify compatibility."""
import json
import sqlite3
from contextlib import closing
from datetime import datetime, timezone


METADATA_DEFAULTS = dict(version='', notes='', source_url='', architecture='unknown', size_bytes=None,
                         sha256='', license_name='', license_url='', metadata_updated_at=None)
METADATA_ORIGIN = 'user_registered'


def _read(db, url):
    row = db.execute('SELECT value FROM settings WHERE key=?', ('catalog:' + url,)).fetchone()
    value = json.loads(row[0]) if row else dict(engine_url=url, models=[], selected=None, synced_at=None, sync_error=None)
    # Older catalogs receive display defaults only. Names never imply an
    # architecture, file inspection, verified provenance, or a license.
    value['models'] = [METADATA_DEFAULTS | item | dict(origin=METADATA_ORIGIN) for item in value['models']]
    return value


def read(db_path, url):
    with closing(sqlite3.connect(db_path)) as db:
        return _read(db, url)


def mutate(db_path, url, change):
    """Serialize partial edits with syncs across processes, not just ASGI tasks."""
    with closing(sqlite3.connect(db_path)) as db, db:
        db.execute('BEGIN IMMEDIATE')
        value = _read(db, url)
        change(value)
        db.execute('INSERT OR REPLACE INTO settings VALUES (?, ?)',
                   ('catalog:' + url, json.dumps(value, ensure_ascii=False)))
    return value


def update_metadata(db_path, url, name, changes):
    def change(value):
        model = next((item for item in value['models'] if item['name'] == name), None)
        if model is None:
            raise KeyError('模型未登記，請先同步清單')
        if changes:
            model.update(changes, metadata_updated_at=datetime.now(timezone.utc).isoformat(), origin=METADATA_ORIGIN)
    return mutate(db_path, url, change)


def select(db_path, url, name):
    def change(value):
        model = next((item for item in value['models'] if item['name'] == name), None)
        if model is None:
            raise KeyError('模型未登記，請先同步清單')
        if not model['listed']:
            raise ValueError('模型已不在最近同步清單中，請重新同步確認')
        value['selected'] = name
    return mutate(db_path, url, change)


def sync_error(db_path, url, message):
    return mutate(db_path, url, lambda value: value.update(sync_error=message))


def capture(model, checkpoint):
    """Capture registered information once; do not consult it again on replay."""
    fields = ('source_url', 'architecture', 'size_bytes', 'sha256', 'license_name', 'license_url', 'metadata_updated_at')
    value = {name: model.get(name, METADATA_DEFAULTS[name]) for name in fields}
    return dict(name=checkpoint, version=model.get('version') or '未知', **value,
                origin=METADATA_ORIGIN, captured_at=datetime.now(timezone.utc).isoformat())


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
    def change(value):
        models = {item['name']: item for item in value['models']}
        for item in models.values():
            item['listed'] = False
        for name in names:
            models.setdefault(name, METADATA_DEFAULTS | dict(name=name, origin=METADATA_ORIGIN))['listed'] = True
        value.update(models=sorted(models.values(), key=lambda item: item['name'].casefold()),
                     synced_at=datetime.now(timezone.utc).isoformat(), sync_error=None)
    return mutate(db_path, url, change)
