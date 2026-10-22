"""Ephemeral CPU preview with a fixed interpreter, source audit and bounded worker lifecycle."""
import base64
import hashlib
import io
import json
import os
import subprocess
import threading
from typing import Literal
from uuid import UUID

from fastapi import HTTPException, Response
from PIL import Image
from pydantic import BaseModel, ConfigDict, Field, model_validator
from starlette.concurrency import run_in_threadpool
from backend import image_workflows

MAX_PIXELS = 1_048_576
MAX_BYTES = 16 * 1024 * 1024
TIMEOUT = 45
NATIVE_SHA256 = '5efd352d92d7749b7b9734a1676fee18f4431d44a8e9477822a7a8f38ad26051'
METHOD = 'comfy-kornia-canny-cpu-v1'


class Input(BaseModel):
    model_config = ConfigDict(extra='forbid')
    image_asset_id: UUID
    reference_resize: Literal['fit', 'stretch']
    width: int = Field(strict=True, ge=64, le=8192, multiple_of=8)
    height: int = Field(strict=True, ge=64, le=8192, multiple_of=8)
    canny_low: float = Field(strict=True, ge=.01, le=.99, allow_inf_nan=False)
    canny_high: float = Field(strict=True, ge=.01, le=.99, allow_inf_nan=False)

    @model_validator(mode='after')
    def bounds(self):
        if self.width*self.height > MAX_PIXELS:
            raise ValueError('CPU 預覽最多 1,048,576 像素；生成尺寸上限不受此預覽限制影響')
        if self.canny_low >= self.canny_high:
            raise ValueError('Canny 低閾值必須小於高閾值')
        return self


class PreviewError(Exception):
    pass


class PreviewBusy(Exception):
    pass


def run_worker(root, raw, settings):
    python = root / 'runtime/ComfyUI/.venv' / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
    script = root / 'scripts/preview_canny.py'
    native = root / 'runtime/ComfyUI/comfy_extras/nodes_canny.py'
    try:
        supported = hashlib.sha256(native.read_bytes().replace(b'\r\n', b'\n')).hexdigest() == NATIVE_SHA256
    except OSError:
        supported = False
    if not python.is_file() or not script.is_file() or not supported:
        raise PreviewError('本機 ComfyUI Python 未安裝或 Canny 原始碼版本未驗證；僅停用 CPU 預覽')
    header = {k: settings[k] for k in ('width', 'height', 'canny_low', 'canny_high')}
    payload = json.dumps(header).encode('ascii') + b'\n' + raw
    if len(raw) > MAX_BYTES:
        raise ValueError('預覽輸入 PNG 超過 16 MiB')
    env = dict(os.environ, CUDA_VISIBLE_DEVICES='', PYTHONDONTWRITEBYTECODE='1')
    process = subprocess.Popen([str(python), '-I', '-B', str(script)], cwd=root, env=env,
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, bufsize=0,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
    output = bytearray()
    overflow = threading.Event()
    def read():
        try:
            while True:
                chunk = process.stdout.read(min(8192, MAX_BYTES + 4098 - len(output)))
                if not chunk:
                    break
                output.extend(chunk)
                if len(output) >= MAX_BYTES + 4098:
                    overflow.set()
                    process.kill()
                    break
        except OSError:
            pass
    def send():
        try:
            # A pipe write may be short even for a blocking descriptor.
            view = memoryview(payload)
            while view:
                written = process.stdin.write(view)
                if not written:
                    break
                view = view[written:]
        except (OSError, ValueError):
            pass
        finally:
            process.stdin.close()
    reader = threading.Thread(target=read, daemon=True)
    writer = threading.Thread(target=send, daemon=True)
    reader.start()
    writer.start()
    try:
        try:
            process.wait(timeout=TIMEOUT)
        except subprocess.TimeoutExpired as exc:
            raise PreviewError('CPU Canny 預覽超過 45 秒，已停止子程序；可降低預覽尺寸') from exc
        reader.join(timeout=2)
        writer.join(timeout=2)
        if reader.is_alive() or writer.is_alive() or overflow.is_set() or process.returncode != 0:
            raise PreviewError('本機 CPU Canny 預覽失敗，未使用不完整輸出；請檢查 ComfyUI Python 環境')
        return bytes(output)
    finally:
        if process.poll() is None:
            process.kill()
            process.wait(timeout=5)
        reader.join(timeout=2)
        writer.join(timeout=2)
        process.stdout.close()
        if not process.stdin.closed:
            process.stdin.close()


def checked_output(output, raw, settings):
    try:
        line, encoded = output.split(b'\n', 1)
        if len(line) > 4096 or len(encoded) > MAX_BYTES:
            raise ValueError()
        info = json.loads(line)
        expected = dict(method=METHOD, device='cpu', dtype='float32', native_sha256=NATIVE_SHA256,
            input_sha256=hashlib.sha256(raw).hexdigest(), sha256=hashlib.sha256(encoded).hexdigest(),
            **{k: settings[k] for k in ('width', 'height', 'canny_low', 'canny_high')})
        if not isinstance(info, dict) or set(info) != set(expected) | {'torch', 'kornia', 'pillow'}:
            raise ValueError()
        if any(type(info[k]) is not type(v) or info[k] != v for k, v in expected.items()):
            raise ValueError()
        if any(not isinstance(info[k], str) or not 0 < len(info[k]) < 100 or not info[k].isascii() or any(ord(c) < 32 for c in info[k]) for k in ('torch', 'kornia', 'pillow')):
            raise ValueError()
        with Image.open(io.BytesIO(encoded)) as image:
            if image.format != 'PNG' or image.mode != 'RGB' or image.size != (settings['width'], settings['height']) or getattr(image, 'n_frames', 1) != 1:
                raise ValueError()
            image.load()
            red, green, blue = image.split()
            if red.tobytes() != green.tobytes() or red.tobytes() != blue.tobytes() or sum(red.histogram()[1:255]):
                raise ValueError()
        return info, encoded
    except (ValueError, KeyError, TypeError, OSError) as exc:
        raise PreviewError('CPU 預覽輸出版本、尺寸、hash 或二值 RGB 格式不符，未顯示') from exc


class Preview:
    def __init__(self):
        self.lock = threading.Lock()

    def run(self, root, db, folder, value):
        # This worker owns the lock until child termination, including HTTP disconnects.
        if not self.lock.acquire(blocking=False):
            raise PreviewBusy()
        try:
            settings = value.model_dump(mode='json')
            settings['reference_ids'] = [settings['image_asset_id']]
            snapshot, raw = image_workflows.prepare(db, folder, settings)
            info, encoded = checked_output(run_worker(root, raw, settings), raw, settings)
            info.update(image_asset_id=snapshot['id'], asset_sha256=snapshot['sha256'],
                        reference_resize=settings['reference_resize'], preprocessing=snapshot['generation_preprocessing'])
            return info, encoded
        finally:
            self.lock.release()


def install(app, host):
    state = Preview()
    @app.post('/api/control/preview')
    async def preview(value: Input):
        try:
            info, encoded = await run_in_threadpool(state.run, host.ROOT, host.DB, host.DATA, value)
        except PreviewBusy:
            raise HTTPException(409, 'CPU Canny 預覽正在計算，請稍候；未建立第二個程序')
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        except (PreviewError, OSError) as exc:
            message = str(exc) if isinstance(exc, PreviewError) else '本機預覽程序無法啟動；未連線引擎或提交任務'
            raise HTTPException(503, message) from exc
        provenance = base64.b64encode(json.dumps(info, separators=(',', ':')).encode('ascii')).decode('ascii')
        return Response(encoded, media_type='image/png', headers={'Cache-Control': 'no-store',
            'X-Content-Type-Options': 'nosniff', 'X-Atelier-SHA256': info['sha256'],
            'X-Atelier-Width': str(info['width']), 'X-Atelier-Height': str(info['height']),
            'X-Atelier-Canny-Provenance': provenance})
