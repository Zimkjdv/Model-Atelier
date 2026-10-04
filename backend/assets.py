"""Validated local reference images and recoverable archive records."""
import hashlib
import io
import json
import sqlite3
import warnings
from contextlib import closing
from datetime import datetime, timezone
from uuid import uuid4

from PIL import Image, ImageOps, UnidentifiedImageError
from PIL import __version__ as pillow_version

MAX_BYTES = 20 * 1024 * 1024
MAX_PIXELS = 16_000_000
PURPOSES = ('unspecified', 'style', 'character', 'composition')


def display(value):
    # Unknown provenance in old records stays unknown; reads never rewrite it.
    return dict(value, purpose=value.get('purpose', 'unspecified'), revision=value.get('revision', 0),
                preprocessing=value.get('preprocessing'))


def references(db, asset_id):
    result = dict(drafts=[], jobs=[], artworks=[])
    for key, raw in db.execute("SELECT key, value FROM settings WHERE key LIKE 'draft:%' OR key LIKE 'job:%' OR key LIKE 'artwork:%'"):
        value = json.loads(raw)
        ids = value.get('reference_ids', [])
        snapshots = value.get('reference_metadata') or []
        if asset_id in ids or value.get('image_asset_id') == asset_id or any(item.get('id') == asset_id for item in snapshots):
            group = {'draft': 'drafts', 'job': 'jobs', 'artwork': 'artworks'}[key.split(':', 1)[0]]
            result[group].append(value.get('id', key.split(':', 1)[1]))
    return result


def usage(db_path, asset_id):
    get(db_path, asset_id)
    with closing(sqlite3.connect(db_path)) as db:
        return references(db, asset_id)


def list_all(db_path):
    with closing(sqlite3.connect(db_path)) as db:
        rows = db.execute("SELECT value FROM settings WHERE key LIKE 'asset:%'").fetchall()
    return sorted([display(json.loads(row[0])) for row in rows], key=lambda item: item['created_at'], reverse=True)


def get(db_path, asset_id):
    with closing(sqlite3.connect(db_path)) as db:
        row = db.execute('SELECT value FROM settings WHERE key=?', ('asset:' + asset_id,)).fetchone()
    if not row:
        raise KeyError('找不到素材')
    return display(json.loads(row[0]))


def create(db_path, folder, raw, filename):
    if len(raw) > MAX_BYTES:
        raise ValueError('圖片不可超過 20 MiB')
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('error', Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(raw)) as image:
                if image.format not in ('PNG', 'JPEG', 'WEBP') or getattr(image, 'n_frames', 1) != 1:
                    raise ValueError('僅支援單張 PNG、JPEG 或 WebP 圖片')
                if image.width * image.height > MAX_PIXELS:
                    raise ValueError('圖片不可超過 1600 萬像素')
                image.load()
                source_format, source_size = image.format, list(image.size)
                clean = ImageOps.exif_transpose(image).convert('RGBA')
                clean.info.clear()
                output = io.BytesIO()
                clean.save(output, format='PNG')
                encoded = output.getvalue()
                width, height = clean.size
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError, Image.DecompressionBombWarning) as exc:
        raise ValueError('無法讀取圖片，檔案可能損壞或尺寸過大') from exc
    asset_id = str(uuid4())
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / (asset_id + '.png')
    value = dict(id=asset_id, title=filename.replace('\\', '/').split('/')[-1][:100] or '未命名素材',
                 width=width, height=height, size=len(encoded), sha256=hashlib.sha256(encoded).hexdigest(),
                 archived=False, purpose='unspecified', revision=1,
                 preprocessing=dict(id='asset-normalize', version=1, library='Pillow', library_version=pillow_version,
                                    source_format=source_format, source_size=source_size, source_sha256=hashlib.sha256(raw).hexdigest(),
                                    operations=['exif_transpose', 'convert_rgba', 'remove_metadata', 'encode_png']),
                 created_at=datetime.now(timezone.utc).isoformat())
    try:
        target.write_bytes(encoded)
        with closing(sqlite3.connect(db_path)) as db, db:
            db.execute('INSERT INTO settings VALUES (?, ?)', ('asset:' + asset_id, json.dumps(value, ensure_ascii=False)))
    except Exception:
        target.unlink(missing_ok=True)
        raise
    return value


def update(db_path, asset_id, title, archived, purpose=None, revision=None):
    if purpose is not None and purpose not in PURPOSES:
        raise ValueError('未知的素材用途')
    with closing(sqlite3.connect(db_path)) as db, db:
        db.execute('BEGIN IMMEDIATE')
        row = db.execute('SELECT value FROM settings WHERE key=?', ('asset:' + asset_id,)).fetchone()
        if not row:
            raise KeyError('找不到素材')
        value = json.loads(row[0])
        if revision is not None and revision != value.get('revision', 0):
            raise ValueError('素材已在其他視窗更新，請重新整理後再保存')
        if archived:
            used = references(db, asset_id)
            if used['jobs'] or used['artworks']:
                raise ValueError('素材正被任務或作品引用，為保留來源與重建能力，無法封存')
            if used['drafts']:
                raise ValueError('素材正被草稿引用，請先在草稿移除參考並保存，再封存素材')
        value.update(title=title, archived=archived, purpose=purpose if purpose is not None else value.get('purpose', 'unspecified'),
                     revision=value.get('revision', 0) + 1, updated_at=datetime.now(timezone.utc).isoformat())
        db.execute('UPDATE settings SET value=? WHERE key=?', (json.dumps(value, ensure_ascii=False), 'asset:' + asset_id))
    return display(value)
