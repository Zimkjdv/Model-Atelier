"""Submission-time version observations; never infer unavailable GPU versions."""
import asyncio
import hashlib
import json
import platform
from datetime import datetime, timezone
from importlib import metadata

import httpx
from backend import workflows

PACKAGES = ('fastapi', 'starlette', 'pydantic', 'httpx', 'Pillow', 'uvicorn', 'websockets')
ENGINE_PACKAGES = frozenset({'comfyui-frontend-package', 'comfyui-workflow-templates',
                            'comfyui-embedded-docs', 'comfy-kitchen', 'comfy-aimdo'})


def text(value, limit=256):
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        return None
    return value.strip() if not any(ord(c) < 32 for c in value) else None


def engine_versions(value, engine_url):
    system = value.get('system') if isinstance(value, dict) else None
    if not isinstance(system, dict):
        raise ValueError('Invalid engine system stats')
    packages = []
    seen = set()
    entries = system.get('comfy_package_versions', [])
    if isinstance(entries, list):
        for entry in entries[:100]:
            if not isinstance(entry, dict) or not isinstance(entry.get('name'), str):
                continue
            name = entry['name']
            if name in ENGINE_PACKAGES and name not in seen:
                seen.add(name)
                packages.append(dict(name=name, installed=text(entry.get('installed')), required=text(entry.get('required'))))
    return dict(status='reported', source=engine_url + '/system_stats',
                comfyui=text(system.get('comfyui_version')), python=text(system.get('python_version')),
                pytorch=text(system.get('pytorch_version')), packages=packages,
                cuda=None, driver=None, git_revision=None,
                note='引擎回報值；CUDA、驅動及 Git revision 未由此介面提供，不從 PyTorch 後綴或平台環境推定。')


def workflow_identity(job):
    if job.get('workflow_id'):
        return job['workflow_id']
    outputs = [key for key, node in job['workflow'].items() if node['class_type'] == 'SaveImage']
    try:
        if len(outputs) != 1:
            raise ValueError('Not a single-output template')
        workflows.extract(job | dict(title='流程版本', source=dict(node_id=outputs[0])), lambda value: value)
        return 'checkpoint-text2image-v1'
    except (KeyError, TypeError, ValueError):
        return 'checkpoint-api-workflow-v1'


async def capture(client, job):
    timestamp = datetime.now(timezone.utc).isoformat()
    packages = []
    for name in PACKAGES:
        try:
            version = metadata.version(name)
        except metadata.PackageNotFoundError:
            version = None
        packages.append(dict(name=name, version=version))
    engine = dict(status='unavailable', source=job['engine_url'] + '/system_stats',
                  comfyui=None, python=None, pytorch=None, packages=[], cuda=None, driver=None, git_revision=None,
                  note='提交前未能取得版本；此欄位保持未知，不影響已通過的流程驗證。')
    try:
        response = await asyncio.wait_for(client.get(engine['source']), timeout=2)
        response.raise_for_status()
        if len(response.content) > 256 * 1024:
            raise ValueError('Oversized system stats')
        engine = engine_versions(response.json(), job['engine_url'])
    except (httpx.HTTPError, ValueError, TypeError, asyncio.TimeoutError):
        pass
    graph = json.dumps(job['workflow'], ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)
    return dict(schema_version=1, captured_at=timestamp,
                workflow=dict(id=workflow_identity(job),
                              sha256=hashlib.sha256(graph.encode()).hexdigest(),
                              nodes=sorted({node['class_type'] for node in job['workflow'].values()}),
                              node_versions=None, note='原生節點未提供各別版本；流程 ID 是平台模板規格版本。'),
                platform=dict(source='platform Python process', python=platform.python_version(), packages=packages),
                engine=engine)
