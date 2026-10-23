"""Install only the reviewed, pinned IPAdapter node files; never run upstream installers."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import tempfile

import httpx

ROOT = Path(__file__).resolve().parents[1]
REVISION = 'a0f451a5113cf9becb0847b92884cb10cbdec0ef'
REPOSITORY = 'cubiq/ComfyUI_IPAdapter_plus'


def install(*, workspace=ROOT, check=False, client=None):
    manifest = json.loads((ROOT / 'models/ipadapter-nodes.json').read_text(encoding='utf-8'))
    if manifest['revision'] != REVISION or manifest['repository'] != REPOSITORY:
        raise ValueError('Unsupported node source')
    files = manifest['files']
    if {f['path'] for f in files} != {
        '__init__.py',
        'IPAdapterPlus.py',
        'CrossAttentionPatch.py',
        'image_proj_models.py',
        'utils.py',
        'LICENSE',
        'README.md',
        'pyproject.toml',
    }:
        raise ValueError('Unexpected upstream files')
    workspace = Path(workspace).resolve()
    root = (workspace / 'runtime').resolve()
    if not root.is_relative_to(workspace):
        raise ValueError('Runtime outside workspace')
    parent = root / 'ComfyUI/custom_nodes'
    target = parent / 'ComfyUI_IPAdapter_plus'
    if not target.resolve().is_relative_to(root) or target.is_symlink():
        raise ValueError('Node target outside runtime')

    def verify(folder):
        for item in files:
            path = folder / item['path']
            if path.is_symlink():
                raise ValueError('Symlink node file')
            raw = path.read_bytes()
            blob = b'blob ' + str(len(raw)).encode() + b'\0' + raw
            if hashlib.sha1(blob).hexdigest() != item['git_blob_sha1']:
                raise ValueError('Node source differs: ' + item['path'])

    if target.exists():
        verify(target)
        return dict(path=str(target), revision=REVISION, reused=True)
    if check:
        raise FileNotFoundError('Pinned IPAdapter nodes not installed')
    parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='ipadapter-install-', dir=parent) as tmp:
        staging = Path(tmp) / 'nodes'
        staging.mkdir()
        owned = client is None
        client = client or httpx.Client(timeout=60, follow_redirects=True)
        try:
            for item in files:
                response = client.get(
                    f'https://raw.githubusercontent.com/{REPOSITORY}/{REVISION}/{item["path"]}'
                )
                response.raise_for_status()
                if len(response.content) > 1024 * 1024:
                    raise ValueError('Node source too large')
                (staging / item['path']).write_bytes(response.content)
            verify(staging)
            if target.exists():
                raise FileExistsError('Node target appeared; refusing overwrite')
            os.rename(staging, target)
        finally:
            if owned:
                client.close()
    return dict(path=str(target), revision=REVISION, reused=False)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    print(json.dumps(install(check=args.check)))
