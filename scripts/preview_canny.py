"""Fixed CPU-only worker. stdin: JSON line + prepared PNG; stdout: JSON line + RGB PNG.

Run only in this workspace's ComfyUI venv. No Comfy imports, network, models or files written.
The audited native node uses kornia.filters.canny on float32 BCHW input in exactly this order.
"""
import hashlib
import io
import json
import math
from pathlib import Path
import sys

MAX_PIXELS = 1_048_576
MAX_BYTES = 16 * 1024 * 1024
NATIVE_SHA256 = '5efd352d92d7749b7b9734a1676fee18f4431d44a8e9477822a7a8f38ad26051'
METHOD = 'comfy-kornia-canny-cpu-v1'


def main():
    root = Path(__file__).resolve().parents[1]
    native = root / 'runtime/ComfyUI/comfy_extras/nodes_canny.py'
    if hashlib.sha256(native.read_bytes().replace(b'\r\n', b'\n')).hexdigest() != NATIVE_SHA256:
        raise ValueError('Unsupported native Canny source')
    line = sys.stdin.buffer.readline(4097)
    if len(line) > 4096 or not line.endswith(b'\n'):
        raise ValueError('Invalid request header')
    settings = json.loads(line)
    if set(settings) != {'width', 'height', 'canny_low', 'canny_high'}:
        raise ValueError('Invalid fields')
    w, h = settings['width'], settings['height']
    if any(type(n) is not int or not 64 <= n <= 8192 or n % 8 for n in (w, h)) or w*h > MAX_PIXELS:
        raise ValueError('Invalid geometry')
    low, high = settings['canny_low'], settings['canny_high']
    if any(type(n) not in (int, float) or not math.isfinite(n) for n in (low, high)) or not .01 <= low < high <= .99:
        raise ValueError('Invalid thresholds')
    raw = sys.stdin.buffer.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        raise ValueError('Input too large')
    import numpy as np
    import torch
    import kornia
    from PIL import Image, __version__ as pillow_version
    torch.set_num_threads(2)
    torch.set_num_interop_threads(1)
    with Image.open(io.BytesIO(raw)) as image:
        if image.format != 'PNG' or image.mode != 'RGB' or image.size != (w, h) or getattr(image, 'n_frames', 1) != 1:
            raise ValueError('Invalid input PNG')
        pixels = np.array(image).astype(np.float32) / 255.0
    with torch.inference_mode():
        source = torch.from_numpy(pixels)[None, ...].to(device='cpu', dtype=torch.float32).movedim(-1, 1)
        edge = kornia.filters.canny(source, low, high)[1].repeat(1, 3, 1, 1).movedim(1, -1)
        output = np.clip(255.0 * edge[0].cpu().numpy(), 0, 255).astype(np.uint8)
    stream = io.BytesIO()
    Image.fromarray(output).save(stream, format='PNG')
    encoded = stream.getvalue()
    if len(encoded) > MAX_BYTES:
        raise ValueError('Output too large')
    provenance = dict(method=METHOD, device='cpu', dtype='float32', native_sha256=NATIVE_SHA256,
                      torch=str(torch.__version__), kornia=kornia.__version__, pillow=pillow_version,
                      input_sha256=hashlib.sha256(raw).hexdigest(), sha256=hashlib.sha256(encoded).hexdigest(), **settings)
    sys.stdout.buffer.write(json.dumps(provenance, separators=(',', ':')).encode('ascii') + b'\n' + encoded)


if __name__ == '__main__':
    main()
