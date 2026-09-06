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

MAX_BYTES = 20 * 1024 * 1024
MAX_PIXELS = 16_000_000


def list_all(db_path):
    with closing(sqlite3.connect(db_path)) as db:
        rows = db.execute("SELECT value FROM settings WHERE key LIKE 'asset:%'").fetchall()
    return sorted([json.loads(row[0]) for row in rows], key=lambda item: item['created_at'], reverse=True)


def get(db_path, asset_id):
    with closing(sqlite3.connect(db_path)) as db:
        row = db.execute('SELECT value FROM settings WHERE key=?', ('asset:' + asset_id,)).fetchone()
    if not row:
        raise KeyError('找不到素材')
    return json.loads(row[0])


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
                 archived=False, created_at=datetime.now(timezone.utc).isoformat())
    try:
        target.write_bytes(encoded)
        with closing(sqlite3.connect(db_path)) as db, db:
            db.execute('INSERT INTO settings VALUES (?, ?)', ('asset:' + asset_id, json.dumps(value, ensure_ascii=False)))
    except Exception:
        target.unlink(missing_ok=True)
        raise
    return value


def update(db_path, asset_id, title, archived):
    with closing(sqlite3.connect(db_path)) as db, db:
        db.execute('BEGIN IMMEDIATE')
        row = db.execute('SELECT value FROM settings WHERE key=?', ('asset:' + asset_id,)).fetchone()
        if not row:
            raise KeyError('找不到素材')
        value = json.loads(row[0])
        if archived:
            rows = db.execute("SELECT value FROM settings WHERE key LIKE 'draft:%'").fetchall()
            if any(asset_id in json.loads(row[0]).get('reference_ids', []) for row in rows):
                raise ValueError('素材正被草稿引用，請先在草稿移除參考並保存，再封存素材')
        value.update(title=title, archived=archived)
        db.execute('UPDATE settings SET value=? WHERE key=?', (json.dumps(value, ensure_ascii=False), 'asset:' + asset_id))
    return value
