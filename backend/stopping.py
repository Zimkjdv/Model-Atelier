"""Stop an owned running prompt through an explicitly audited atomic API.

Never call legacy /interrupt, never replay an ambiguous stop, and never infer
completion from the cancellation receipt or from an absent queue entry.
"""
from datetime import timedelta
from uuid import uuid4

import httpx
from fastapi import HTTPException
from backend import cancellation as c, failures
from scripts.comfy_stop_capability import FEATURE, SOURCE_COMMIT

STATES = {'stopping', 'stop_unknown'}
UNCERTAIN = '停止結果待確認；請查詢原任務，平台不自動重送停止或生成請求。'


async def capability(client, job):
    response = await client.get(job['engine_url'] + '/features')
    if response.status_code == 404:
        return False
    response.raise_for_status()
    if len(response.content) > 256 * 1024:
        raise ValueError('invalid capabilities')
    value = response.json()
    return isinstance(value, dict) and value.get(FEATURE) == SOURCE_COMMIT


def interrupted(job, entry):
    # Unlike legacy failure display, a stopped verdict requires the full prompt
    # identity and an explicit, owned interruption event in completed history.
    if not entry or 'prompt' not in entry or not failures.history_matches(job, entry):
        return False
    state = entry['status']
    if state.get('status_str') != 'error' or not isinstance(state.get('messages'), list):
        return False
    for event in state['messages'][-64:]:
        if not isinstance(event, list) or len(event) != 2 or event[0] != 'execution_interrupted':
            continue
        data = event[1]
        if (isinstance(data, dict) and data.get('prompt_id') == job['prompt_id']
                and failures.trusted_node(job, data.get('node_id'), data.get('node_type'))):
            return True
    return False


def persist(host, job, **changes):
    return c.persist(host, job, **changes)


async def reconcile(host, client, job, state=c.UNOBSERVED):
    if state is c.UNOBSERVED:
        state = await c.queue_state(client, job)
    historical, entry = await c.history_state(client, job)
    attempt = dict(job.get('stop_attempt') or {}, active_until=None, checked_at=c.now().isoformat())
    if historical in c.TERMINAL:
        status = 'stopped' if interrupted(job, entry) else historical
        return persist(host, job, status=status, history=entry,
                       failure_info=failures.from_history(job, entry) if status == 'failed' else None,
                       stop_attempt=attempt | {'result': status},
                       error='原引擎歷史確認此任務已中斷；保留原設定與已產生的輸出。' if status == 'stopped' else
                             'ComfyUI 執行失敗，請查看任務 JSON' if status == 'failed' else None)
    return persist(host, job, status='stop_unknown', stop_attempt=attempt | {'result': 'unconfirmed', 'observed_queue': state}, error=UNCERTAIN)


async def refresh(host, job):
    try:
        if job['status'] == 'stopping' and job['stop_attempt'].get('active_until'):
            from datetime import datetime
            if datetime.fromisoformat(job['stop_attempt']['active_until']) > c.now():
                return job
        async with httpx.AsyncClient(timeout=10, trust_env=False) as client:
            return await reconcile(host, client, job)
    except (httpx.HTTPError, ValueError, KeyError, IndexError, TypeError):
        persist(host, job, status='stop_unknown', error=UNCERTAIN,
                stop_attempt=dict(job.get('stop_attempt') or {}, active_until=None, result='unconfirmed'))
        raise HTTPException(503, '無法確認原引擎的停止結果；保留紀錄，請稍後查詢。')


async def stop(host, job):
    if job['status'] in c.TERMINAL:
        return job
    if job['status'] in STATES:
        return await refresh(host, job)
    if job['status'] != 'running':
        raise HTTPException(409, '僅可停止已確認執行中的任務；請先更新狀態。')
    # Check support before mutating the ledger. Lack of support is not a failed
    # generation and must not produce a global interrupt fallback.
    async with httpx.AsyncClient(timeout=10, trust_env=False) as client:
        try:
            supported = await capability(client, job)
        except (httpx.HTTPError, ValueError):
            raise HTTPException(503, '無法確認原引擎的安全停止能力；未發送停止指令。')
        if not supported:
            raise HTTPException(409, '原引擎未提供已驗證的指定任務停止能力；未發送停止指令。')
        timestamp = c.now()
        job = persist(host, job, status='stopping', error=None, stop_attempt={
            'id': str(uuid4()), 'phase': 'prepared', 'started_at': timestamp.isoformat(),
            'active_until': (timestamp + timedelta(seconds=60)).isoformat(), 'result': 'checking'})
        try:
            state = await c.queue_state(client, job)
            if state != 'running':
                result = await reconcile(host, client, job, state)
                if result['status'] in c.TERMINAL:
                    return result
                raise HTTPException(409, '原引擎未確認此任務正在執行；未發送停止指令，請查詢原任務。')
            job = persist(host, job, stop_attempt=dict(job['stop_attempt'], phase='dispatched'))
            response = await client.post(job['engine_url'] + '/api/jobs/' + job['prompt_id'] + '/cancel')
            response.raise_for_status()
            value = response.json()
            if not isinstance(value, dict) or type(value.get('cancelled')) is not bool:
                raise ValueError('invalid stop receipt')
            job = persist(host, job, stop_attempt=dict(job['stop_attempt'], phase='acknowledged',
                          acknowledged_at=c.now().isoformat(), cancelled=value['cancelled']))
            return await reconcile(host, client, job)
        except (httpx.HTTPError, ValueError, KeyError, IndexError, TypeError):
            persist(host, job, status='stop_unknown', error=UNCERTAIN,
                    stop_attempt=dict(job['stop_attempt'], active_until=None, result='unconfirmed'))
            raise HTTPException(503, '停止結果待確認；已保留原任務，請查詢而不要重送。')
