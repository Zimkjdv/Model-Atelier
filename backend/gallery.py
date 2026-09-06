"""Import verified ComfyUI outputs into a durable, offline artwork library."""
import hashlib
import io
import json
import os
import sqlite3
import tempfile
import warnings
from contextlib import closing
from datetime import datetime, timezone
from uuid import UUID, uuid5

from PIL import Image, ImageOps, UnidentifiedImageError

MAX_BYTES = 32 * 1024 * 1024
MAX_PIXELS = 32_000_000
FORMATS = {'PNG': ('png', 'image/png'), 'JPEG': ('jpg', 'image/jpeg'), 'WEBP': ('webp', 'image/webp')}


def get(path, artwork_id):
    with closing(sqlite3.connect(path)) as db:
        row = db.execute('SELECT value FROM settings WHERE key=?', ('artwork:' + artwork_id,)).fetchone()
    if not row:
        raise KeyError('找不到作品')
    return json.loads(row[0])


def list_all(path):
    with closing(sqlite3.connect(path)) as db:
        rows = db.execute("SELECT value FROM settings WHERE key LIKE 'artwork:%'").fetchall()
    return sorted((json.loads(row[0]) for row in rows), key=lambda item: item['imported_at'], reverse=True)


def output_id(job, source):
    return str(uuid5(UUID(job['id']), json.dumps(source, sort_keys=True, ensure_ascii=False)))


def outputs(job):
    history = job.get('history') or {}
    state = history.get('status', {}) if isinstance(history, dict) else {}
    if not isinstance(state, dict):
        raise ValueError('任務狀態資料格式不正確')
    if job['status'] != 'completed' or state.get('status_str') != 'success' or state.get('completed') is not True:
        raise ValueError('僅能匯入已確認成功的任務，請先更新任務狀態')
    result = []
    raw = history.get('outputs', {})
    if not isinstance(raw, dict):
        raise ValueError('任務輸出資料格式不正確')
    for node_id, output in raw.items():
        if job['workflow'].get(node_id, {}).get('class_type') != 'SaveImage':
            continue
        images = output.get('images', []) if isinstance(output, dict) else None
        if not isinstance(images, list):
            raise ValueError('任務圖片清單格式不正確')
        for image in images:
            if not isinstance(image, dict) or image.get('type') != 'output':
                raise ValueError('僅能匯入 output 圖片，不接受暫存或輸入檔案')
            filename, subfolder = image.get('filename'), image.get('subfolder', '')
            if not isinstance(filename, str) or not filename or len(filename) > 255 or any(c in filename for c in '/\\:\x00') or '..' in filename or filename == '.' or filename.endswith(('[input]', '[temp]', '[output]')):
                raise ValueError('輸出檔名無效')
            if not isinstance(subfolder, str) or len(subfolder) > 2048 or any(c in subfolder for c in '\\:\x00') or (subfolder and any(p in ('', '.', '..') for p in subfolder.split('/'))):
                raise ValueError('輸出子目錄無效')
            source = dict(node_id=node_id, filename=filename, subfolder=subfolder, type='output')
            if source not in result:
                result.append(source)
            if len(result) > 64:
                raise ValueError('單一任務最多匯入 64 張圖片')
    if not result:
        raise ValueError('此任務沒有可匯入的 SaveImage 輸出')
    return result


def parameters(workflow, output_node):
    """Follow the output's links; never guess parameters from unrelated branches."""
    def inputs(link, kind):
        if not isinstance(link, list) or len(link) != 2:
            return {}
        node = workflow.get(str(link[0]), {})
        return node.get('inputs', {}) if node.get('class_type') == kind else {}
    output = workflow.get(output_node, {}).get('inputs', {})
    decoder = inputs(output.get('images'), 'VAEDecode')
    sampler = inputs(decoder.get('samples'), 'KSampler')
    positive = inputs(sampler.get('positive'), 'CLIPTextEncode')
    negative = inputs(sampler.get('negative'), 'CLIPTextEncode')
    return dict(prompt=positive.get('text'), negative_prompt=negative.get('text'),
                seed=str(sampler['seed']) if isinstance(sampler.get('seed'), int) else None,
                steps=sampler.get('steps'), cfg=sampler.get('cfg'),
                sampler=sampler.get('sampler_name'), scheduler=sampler.get('scheduler'),
                denoise=sampler.get('denoise'))


def decode(raw):
    if len(raw) > MAX_BYTES:
        raise ValueError('單張作品不可超過 32 MiB')
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('error', Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(raw)) as image:
                if image.format not in FORMATS or getattr(image, 'n_frames', 1) != 1:
                    raise ValueError('僅支援單張 PNG、JPEG 或 WebP 圖片')
                if image.width * image.height > MAX_PIXELS:
                    raise ValueError('單張作品不可超過 3200 萬像素')
                extension, media_type = FORMATS[image.format]
                image.load()
                preview = ImageOps.exif_transpose(image).convert('RGBA')
                width, height = preview.size
                preview.thumbnail((512, 512))
                preview.info.clear()
                stream = io.BytesIO()
                preview.save(stream, format='PNG')
                return extension, media_type, width, height, stream.getvalue()
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError, Image.DecompressionBombWarning) as exc:
        raise ValueError('作品圖片損壞或尺寸過大，未保存檔案') from exc


def save(path, folder, job, source, raw):
    extension, media_type, width, height, thumbnail = decode(raw)
    artwork_id = output_id(job, source)
    value = dict(id=artwork_id, job_id=job['id'], prompt_id=job['prompt_id'],
                 title=source['filename'], source=source, engine_url=job['engine_url'],
                 checkpoint=job['checkpoint'], model_version=job.get('model_version') or '未知',
                 parameters=parameters(job['workflow'], source['node_id']), workflow=job['workflow'],
                 width=width, height=height, size=len(raw), extension=extension, media_type=media_type,
                 sha256=hashlib.sha256(raw).hexdigest(), created_at=job['created_at'],
                 imported_at=datetime.now(timezone.utc).isoformat())
    folder.mkdir(parents=True, exist_ok=True)
    written = []
    try:
        with closing(sqlite3.connect(path)) as db, db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT value FROM settings WHERE key=?', ('artwork:' + artwork_id,)).fetchone()
            if row:
                return json.loads(row[0]), False
            for name, content in [(artwork_id + '.' + extension, raw), (artwork_id + '.thumb.png', thumbnail)]:
                target = folder / name
                temp_name = None
                try:
                    with tempfile.NamedTemporaryFile(dir=folder, delete=False) as stream:
                        temp_name = stream.name
                        stream.write(content)
                    os.replace(temp_name, target)
                    written.append(target)
                finally:
                    if temp_name and os.path.exists(temp_name):
                        os.unlink(temp_name)
            db.execute('INSERT INTO settings VALUES (?, ?)', ('artwork:' + artwork_id, json.dumps(value, ensure_ascii=False)))
    except Exception:
        for target in written:
            target.unlink(missing_ok=True)
        raise
    return value, True
