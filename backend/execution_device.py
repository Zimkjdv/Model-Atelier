"""Fresh evidence from the selected ComfyUI process, never from platform GPUs."""
import asyncio
from datetime import datetime, timezone
import re
from uuid import uuid4

import httpx

PATH = '/model_atelier/execution-device'
PRODUCER = 'model-atelier-execution-device-v1'
BACKENDS = frozenset({'cuda', 'mps', 'xpu', 'npu', 'mlu'})


def unknown(engine_url, reason='not_reported', probe_id=None):
    return dict(schema_version=1, engine_url=engine_url, source=engine_url + PATH,
                checked_at=datetime.now(timezone.utc).isoformat(), probe_id=probe_id,
                status='unknown', reason=reason, device=None, backend_available=None)


def normalize(payload, engine_url, probe_id):
    result = unknown(engine_url, 'invalid_report', probe_id)
    if (not isinstance(payload, dict) or type(payload.get('schema_version')) is not int
            or payload['schema_version'] != 1 or payload.get('producer') != PRODUCER
            or payload.get('probe_id') != probe_id
            or not {'status', 'reason', 'device', 'backend_available'} <= payload.keys()):
        return result
    status, reason = payload.get('status'), payload.get('reason')
    device, available = payload.get('device'), payload.get('backend_available')
    if available is not None and type(available) is not bool:
        return result
    if status == 'unavailable' and reason == 'device_selection_failed':
        if device is not None or available is not None:
            return result
    else:
        if (not isinstance(device, dict) or not isinstance(device.get('type'), str)
                or re.fullmatch(r'[a-z][a-z0-9_]{0,39}', device['type']) is None):
            return result
        index = device.get('index')
        if index is not None and (type(index) is not int or not 0 <= index <= 65535):
            return result
        device = dict(type=device['type'], index=index)
        if status == 'unavailable' and reason == 'backend_unavailable':
            if device['type'] not in BACKENDS or available is not False:
                return result
        elif status == 'available' and reason == 'device_selected':
            if available is False:
                return result
        else:
            return result
    return result | dict(status=status, reason=reason, device=device, backend_available=available)


async def fetch(client, engine_url):
    probe_id = str(uuid4())
    result = unknown(engine_url, probe_id=probe_id)
    try:
        # Nonce prevents cached/stale evidence from authorizing a device block.
        response = await asyncio.wait_for(client.get(result['source'] + '?probe_id=' + probe_id), timeout=2)
        response.raise_for_status()
        if len(response.content) > 16 * 1024:
            return result
        return normalize(response.json(), engine_url, probe_id)
    except (httpx.HTTPError, ValueError, TypeError, asyncio.TimeoutError):
        return result


def scoped(report, selected_url):
    if report['engine_url'] != selected_url:
        return unknown(report['engine_url'], 'engine_changed', report['probe_id'])
    return report
