"""Fresh standard LoraLoader validation. Registration is not weight verification."""
import math
import sqlite3
from contextlib import closing

from backend import catalog, loras, lora_compatibility, node_preflight


def registration(db_path, url, checkpoint, name):
    base, values = registrations(db_path, url, checkpoint, [dict(name=name)])
    return base, values[0][1], values[0][2]


def registrations(db_path, url, checkpoint, choices):
    with closing(sqlite3.connect(db_path)) as db:
        db.execute('BEGIN')
        base = next((item for item in catalog._read(db, url)['models'] if item['name'] == checkpoint), {})
        records = loras._read(db, url)['loras']
    values = []
    for choice in choices:
        record = next((item for item in records if item['name'] == choice['name']), {})
        values.append((choice, record, lora_compatibility.compare(base, record)))
    return base, values


async def check(client, url, choice):
    return await check_many(client, url, [choice])


async def check_many(client, url, choices):
    response = await client.get(url + '/object_info/LoraLoader')
    response.raise_for_status()
    if len(response.content) > 1024 * 1024:
        raise ValueError('LoRA 節點回應過大')
    payload = response.json()
    if isinstance(payload, dict) and 'LoraLoader' not in payload:
        raise node_preflight.MissingNodes('ComfyUI 缺少必要節點：LoraLoader；尚未提交任務')
    try:
        names = loras.names_from(payload)
        definition = payload['LoraLoader']
        required = definition['input']['required']
        if (set(required) != {'model', 'clip', 'lora_name', 'strength_model', 'strength_clip'}
                or required['model'][0] != 'MODEL' or required['clip'][0] != 'CLIP'
                or definition['output'] != ['MODEL', 'CLIP']):
            raise ValueError('LoraLoader 介面不相容')
        bounds = {}
        for field in ('strength_model', 'strength_clip'):
            data = required[field]
            low, high = data[1]['min'], data[1]['max']
            if (data[0] != 'FLOAT' or any(type(number) not in (int, float) or not math.isfinite(number)
                                        for number in (low, high)) or low > high):
                raise ValueError('LoRA 強度範圍無效')
            bounds[field] = max(-20, low), min(20, high)
    except (KeyError, IndexError, TypeError) as exc:
        raise ValueError('LoraLoader 定義格式無效') from exc
    for choice in choices:
        if choice['name'] not in names:
            raise LookupError('所選 LoRA ' + choice['name'] + ' 已不在 ComfyUI 即時清單，請安裝並重新同步；尚未提交任務')
        for field, (low, high) in bounds.items():
            if not low <= choice[field] <= high:
                raise ArithmeticError(f"{choice['name']} {field} 超出平台與引擎交集 {low}～{high}；尚未提交任務")
