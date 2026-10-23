"""Explicitly prepare the three fixed R01 estimator files in the aux cache."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import httpx

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    spec = json.loads((ROOT / 'models/structure-preprocessors.json').read_text(encoding='utf-8'))
    base = ROOT / 'runtime/ComfyUI/custom_nodes/comfyui_controlnet_aux/ckpts'
    allowed = {
        ('yzd-v/DWPose', 'yolox_l.onnx'),
        ('yzd-v/DWPose', 'dw-ll_ucoco_384.onnx'),
        ('depth-anything/Depth-Anything-V2-Small', 'depth_anything_v2_vits.pth'),
    }
    for item in spec['weights']:
        if (item['repository'], item['filename']) not in allowed:
            raise ValueError('Unexpected estimator')
        target = base / item['repository'] / item['filename']
        if any(
            p.is_symlink() or (hasattr(p, 'is_junction') and p.is_junction())
            for p in [target, *target.parents]
            if p != ROOT.parent
        ) or not target.resolve().is_relative_to(ROOT):
            raise ValueError('External estimator path')
        if target.exists():
            with target.open('rb') as f:
                digest = hashlib.file_digest(f, 'sha256').hexdigest()
            if target.stat().st_size != item['size_bytes'] or digest != item['sha256']:
                raise ValueError('Existing estimator differs; never overwritten')
            print('verified', item['filename'])
            continue
        if args.check:
            print('missing', item['filename'])
            continue
        if shutil.disk_usage(ROOT).free < item['size_bytes'] + 2 * 1024**3:
            raise ValueError('Insufficient free disk space')
        target.parent.mkdir(parents=True, exist_ok=True)
        partial = target.with_suffix(target.suffix + '.partial')
        url = f'https://huggingface.co/{item["repository"]}/resolve/{item["revision"]}/{item["filename"]}'
        with (
            httpx.stream('GET', url, follow_redirects=True, timeout=120) as response,
            partial.open('xb') as out,
        ):
            response.raise_for_status()
            for chunk in response.iter_bytes(1024 * 1024):
                out.write(chunk)
        with partial.open('rb') as f:
            digest = hashlib.file_digest(f, 'sha256').hexdigest()
        if partial.stat().st_size != item['size_bytes'] or digest != item['sha256']:
            raise ValueError('Downloaded estimator mismatch')
        # Windows rename does not replace an existing destination.
        partial.rename(target)
        print('installed', item['filename'])


if __name__ == '__main__':
    main()
