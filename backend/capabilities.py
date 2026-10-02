"""Live standard KSampler capabilities, with engine-scoped display snapshots.

A stale snapshot is useful for editing, never for authorizing a submission.
Widget increments are not numeric validation lattices (CFG 5.55 remains valid).
"""
import asyncio
import json
import math
import re
import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from weakref import WeakValueDictionary

import httpx

PLATFORM = dict(steps=(1, 150), cfg=(0, 30), denoise=(0, 1))
TOKEN = re.compile(r'^[a-z][a-z0-9_]{0,63}$')
MAX_RESPONSE = 1024 * 1024


def options(required, name):
    item = required[name]
    if (not isinstance(item, list) or not item or not isinstance(item[0], list) or
            not 1 <= len(item[0]) <= 512 or
            any(not isinstance(value, str) or not TOKEN.fullmatch(value) for value in item[0])):
        raise ValueError('ComfyUI ' + name + ' 選項清單格式無效，或含本平台不支援的命名格式')
    return list(dict.fromkeys(item[0]))


def parse(payload):
    try:
        required = payload['KSampler']['input']['required']
        if not isinstance(required, dict):
            raise ValueError('invalid required inputs')
        names = options(required, 'sampler_name')
        schedulers = options(required, 'scheduler')
        bounds, engine_bounds = {}, {}
        for name, (platform_min, platform_max) in PLATFORM.items():
            item = required[name]
            expected_type = 'INT' if name == 'steps' else 'FLOAT'
            if not isinstance(item, list) or len(item) < 2 or item[0] != expected_type or not isinstance(item[1], dict):
                raise ValueError('invalid parameter type')
            values = {field: item[1][field] for field in ('min', 'max', 'default')}
            allowed = (int,) if name == 'steps' else (int, float)
            if any(type(value) not in allowed or not math.isfinite(value) for value in values.values()):
                raise ValueError('invalid numeric bound')
            if not values['min'] <= values['default'] <= values['max']:
                raise ValueError('invalid bound order/default')
            minimum, maximum = max(values['min'], platform_min), min(values['max'], platform_max)
            if minimum > maximum:
                raise ValueError('engine range incompatible with platform limits')
            bounds[name] = dict(min=minimum, max=maximum)
            engine_bounds[name] = values
        return dict(sampler_names=names, schedulers=schedulers, bounds=bounds, engine_bounds=engine_bounds)
    except (KeyError, IndexError, TypeError, ValueError, OverflowError) as exc:
        raise ValueError('ComfyUI KSampler 能力格式無效或與平台範圍不相容，尚未提交任務') from exc


def read(path, engine_url):
    with closing(sqlite3.connect(path)) as db:
        row = db.execute('SELECT value FROM settings WHERE key=?', ('capabilities:' + engine_url,)).fetchone()
    return json.loads(row[0]) if row else dict(engine_url=engine_url, available=False, sampler_names=[], schedulers=[],
                                             bounds={}, engine_bounds={}, synced_at=None)


def write(path, engine_url, value):
    snapshot = value | dict(engine_url=engine_url, available=True, synced_at=datetime.now(timezone.utc).isoformat())
    with closing(sqlite3.connect(path)) as db, db:
        db.execute('INSERT OR REPLACE INTO settings VALUES (?, ?)',
                   ('capabilities:' + engine_url, json.dumps(snapshot, ensure_ascii=False, allow_nan=False)))
    return snapshot


async def fetch(client, engine_url):
    response = await client.get(engine_url + '/object_info/KSampler')
    response.raise_for_status()
    if len(response.content) > MAX_RESPONSE:
        raise ValueError('ComfyUI KSampler 能力回應過大，尚未提交任務')
    return parse(response.json())


def validate_workflow(workflow, value):
    samplers = [(node_id, node['inputs']) for node_id, node in workflow.items() if node['class_type'] == 'KSampler']
    if not samplers:
        raise ValueError('工作流程缺少標準 KSampler 節點，尚未提交任務')
    for node_id, inputs in samplers:
        for name, choices in [('sampler_name', value['sampler_names']), ('scheduler', value['schedulers'])]:
            option = inputs.get(name)
            if not isinstance(option, str) or option not in choices:
                raise ValueError('KSampler ' + str(node_id) + ' 的 ' + name + ' 不在原引擎目前支援清單中，尚未提交任務')
        for name, bounds in value['bounds'].items():
            parameter = inputs.get(name)
            allowed = (int,) if name == 'steps' else (int, float)
            if (type(parameter) not in allowed or not bounds['min'] <= parameter <= bounds['max'] or
                    not math.isfinite(parameter)):
                raise ValueError('KSampler ' + str(node_id) + ' 的 ' + name + ' 超出平台與原引擎有效範圍，尚未提交任務')
        seed = inputs.get('seed')
        if type(seed) is not int or not 0 <= seed <= 18446744073709551615:
            raise ValueError('KSampler ' + str(node_id) + ' 的 seed 必須是有效的 64 位非負整數，尚未提交任務')
    for node_id, node in workflow.items():
        if node['class_type'] != 'EmptyLatentImage':
            continue
        inputs = node['inputs']
        for name in ('width', 'height'):
            size = inputs.get(name)
            if type(size) is not int or not 64 <= size <= 8192 or size % 8:
                raise ValueError('EmptyLatentImage ' + str(node_id) + ' 的 ' + name + ' 必須是 64 至 8192 且為 8 的倍數，尚未提交任務')
        if type(inputs.get('batch_size')) is not int or inputs['batch_size'] != 1:
            raise ValueError('第一版工作流程的 EmptyLatentImage batch_size 必須為 1，尚未提交任務')


def install(app, host):
    locks = WeakValueDictionary()

    async def sync():
        engine_url = host.engine_url()
        async with locks.setdefault(engine_url, asyncio.Lock()):
            error = None
            try:
                async with httpx.AsyncClient(timeout=10, trust_env=False) as client:
                    value = write(host.DB, engine_url, await fetch(client, engine_url))
            except httpx.RequestError:
                error = 'ComfyUI 離線或連線逾時；顯示上次能力快照，生成時仍需重新確認'
                value = read(host.DB, engine_url)
            except httpx.HTTPStatusError as exc:
                code = exc.response.status_code
                error = (f'ComfyUI 能力服務暫時不可用（HTTP {code}）；顯示上次快照，生成時仍需重新確認' if code >= 500 else
                         f'無法讀取 ComfyUI KSampler 能力（HTTP {code}）；請檢查引擎版本與存取權限，保留上次快照')
                value = read(host.DB, engine_url)
            except ValueError:
                error = 'ComfyUI KSampler 能力格式無效或不相容；保留上次快照，生成時仍需重新確認'
                value = read(host.DB, engine_url)
            current = host.engine_url()
            if current != engine_url:
                error = '查詢期間引擎設定已變更；請重新載入目前引擎的能力清單'
            return value | dict(current_engine_url=current, engine_matches=current == engine_url,
                                stale=error is not None, sync_error=error)

    app.get('/api/engine/capabilities')(sync)
    app.post('/api/engine/capabilities/sync')(sync)
