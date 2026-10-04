"""Fresh standard LoraLoader validation. Registration is not weight verification."""
import math
import sqlite3
from contextlib import closing

from backend import catalog, loras, lora_compatibility, node_preflight


def registration(db_path, url, checkpoint, name):
    with closing(sqlite3.connect(db_path)) as db:
        db.execute('BEGIN')
        base = next((item for item in catalog._read(db, url)['models'] if item['name'] == checkpoint), {})
        choice = next((item for item in loras._read(db, url)['loras'] if item['name'] == name), {})
    return base, choice, lora_compatibility.compare(base, choice)


async def check(client, url, choice):
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
    if choice['name'] not in names:
        raise LookupError('所選 LoRA 已不在 ComfyUI 即時清單，請安裝並重新同步；尚未提交任務')
    for field, (low, high) in bounds.items():
        if not low <= choice[field] <= high:
            raise ArithmeticError(f'{field} 超出平台與引擎交集 {low}～{high}；尚未提交任務')
