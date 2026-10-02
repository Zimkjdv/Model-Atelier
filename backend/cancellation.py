"""Cancel only a proven pending prompt on its original ComfyUI engine.

ComfyUI's legacy /queue delete is safe for pending jobs but acknowledges no
deletion result. Never interrupt, clear the queue, or infer success from HTTP
200 alone. Queue-before-history reconciliation detects a prompt that finished
between observations; absent records cannot prove that it never executed.
"""
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import httpx
from fastapi import HTTPException

from backend import jobs

TERMINAL = {'completed', 'failed', 'cancelled'}
CANCEL_STATES = {'cancelling', 'cancel_unknown'}
UNCERTAIN = '取消結果待確認；未確認任務已移除，請查詢狀態；請勿重新提交相同任務'
UNOBSERVED = object()


def now():
    return datetime.now(timezone.utc)


def persist(host, job, **changes):
    current, changed = jobs.compare_update(host.DB, job, **changes)
    if not changed:
        raise HTTPException(409, '任務狀態已由另一個請求更新，請重新查詢；未覆蓋新狀態')
    return current


def active(job):
    """A short durable lease prevents another worker from racing live deletion."""
    if job['status'] != 'cancelling':
        return False
    try:
        return datetime.fromisoformat(job['cancel_attempt']['active_until']) > now()
    except (KeyError, TypeError, ValueError):
        return False


def attempt_update(job, **changes):
    return dict(job.get('cancel_attempt') or {}, **changes)


async def queue_state(client, job):
    response = await client.get(job['engine_url'] + '/queue')
    response.raise_for_status()
    data = response.json()
    if not isinstance(data, dict):
        raise ValueError('invalid queue')
    matches = []
    seen = set()
    for key, state in [('queue_running', 'running'), ('queue_pending', 'queued')]:
        if not isinstance(data.get(key), list):
            raise ValueError('invalid queue list')
        for item in data[key]:
            if (not isinstance(item, list) or len(item) < 4 or
                    not isinstance(item[1], str) or not item[1] or
                    not isinstance(item[2], dict) or not isinstance(item[3], dict)):
                raise ValueError('invalid queue item')
            if item[1] in seen:
                raise ValueError('duplicate prompt identity')
            seen.add(item[1])
            if item[1] == job['prompt_id']:
                # Metadata alone is never a cancellation identity. A matching ID
                # with another workflow/owner is unsafe and must not be deleted.
                owner = item[3].get('model_atelier_job_id')
                if item[2] != job['workflow'] or (owner is not None and owner != job['id']):
                    raise ValueError('prompt ownership mismatch')
                matches.append(state)
    return matches[0] if matches else None


async def history_state(client, job):
    response = await client.get(job['engine_url'] + '/history/' + job['prompt_id'])
    response.raise_for_status()
    data = response.json()
    if not isinstance(data, dict):
        raise ValueError('invalid history')
    if job['prompt_id'] not in data:
        return None, None
    entry = data[job['prompt_id']]
    if not isinstance(entry, dict) or not isinstance(entry.get('status'), dict):
        raise ValueError('invalid history status')
    state = entry['status']
    if type(state.get('completed')) is not bool or state.get('status_str') not in ('success', 'error'):
        raise ValueError('invalid history outcome')
    if state.get('status_str') == 'error':
        status = 'failed'
    elif state.get('completed') is True:
        status = 'completed'
    else:
        status = 'unknown'
    return status, entry


async def reconcile(host, client, job, state=UNOBSERVED):
    if state is UNOBSERVED:
        state = await queue_state(client, job)
    historical, entry = await history_state(client, job)
    attempt = attempt_update(job, active_until=None, checked_at=now().isoformat())
    if historical is not None:
        # Preserve any result produced in the dequeue race; never label it cancelled.
        return persist(host, job, status=historical if historical in TERMINAL else 'cancel_unknown', history=entry,
                       cancel_attempt=attempt | {'result': 'already_finished' if historical in TERMINAL else 'unconfirmed'},
                       error='ComfyUI 執行失敗，請查看任務 JSON' if historical == 'failed' else
                             UNCERTAIN if historical == 'unknown' else None)
    if state is not None:
        return persist(host, job, status=state, cancel_attempt=attempt | {'result': 'not_removed'},
                       error='任務已開始執行；未中斷任務' if state == 'running' else
                             '任務仍在原引擎佇列中；取消尚未生效，可以再次取消排隊')
    if attempt.get('phase') == 'acknowledged':
        return persist(host, job, status='cancelled', cancel_attempt=attempt | {
                       'result': 'absent_after_ack', 'confirmation': 'legacy_ack_then_queue_then_history',
                       'limitation': 'No deletion receipt; absence cannot prove it never executed or that history was not cleared.'},
                       error='取消請求已接受，確認任務不在原引擎排隊、執行與歷史中；此結果不保證任務未曾執行或歷史未被清除')
    return persist(host, job, status='cancel_unknown', cancel_attempt=attempt | {'result': 'unconfirmed'}, error=UNCERTAIN)


def uncertain(host, job):
    return persist(host, job, status='cancel_unknown', error=UNCERTAIN,
                   cancel_attempt=attempt_update(job, active_until=None, checked_at=now().isoformat(), result='unconfirmed'))


async def refresh(host, job):
    """Confirm an ambiguous deletion without ever sending it again."""
    if active(job):
        return job
    try:
        async with httpx.AsyncClient(timeout=10, trust_env=False) as client:
            return await reconcile(host, client, job)
    except (httpx.HTTPError, ValueError, KeyError, IndexError, TypeError):
        uncertain(host, job)
        raise HTTPException(503, '無法確認原 ComfyUI 引擎的取消結果；保留取消紀錄與完整工作流程')


async def cancel(host, job):
    if job['status'] in TERMINAL:
        return job
    if job['status'] in CANCEL_STATES:
        return await refresh(host, job)
    if job['status'] != 'queued':
        raise HTTPException(409, '只可取消已確認排隊的任務；執行中或提交結果待確認的任務不會被中斷')
    timestamp = now()
    job = persist(host, job, status='cancelling', error=None, cancel_attempt={
        'id': str(uuid4()), 'phase': 'prepared', 'started_at': timestamp.isoformat(),
        'active_until': (timestamp + timedelta(seconds=60)).isoformat(), 'result': 'checking'})
    try:
        async with httpx.AsyncClient(timeout=10, trust_env=False) as client:
            state = await queue_state(client, job)
            if state != 'queued':
                # No request is sent when the exact prompt is absent or running.
                job = await reconcile(host, client, job, state)
                if job['status'] in TERMINAL:
                    return job
                raise HTTPException(409, '原引擎未確認此任務仍在排隊；未發送取消或中斷指令，請重新查詢')
            job = persist(host, job, cancel_attempt=attempt_update(job, phase='dispatched', result='awaiting_ack'))
            response = await client.post(job['engine_url'] + '/queue', json={'delete': [job['prompt_id']]})
            response.raise_for_status()
            job = persist(host, job, cancel_attempt=attempt_update(job, phase='acknowledged', acknowledged_at=now().isoformat(), result='verifying'))
            job = await reconcile(host, client, job)
            if job['status'] == 'running':
                raise HTTPException(409, '任務在取消排隊期間已開始執行；未中斷任務，請繼續查詢')
            return job
    except (httpx.HTTPError, ValueError, KeyError, IndexError, TypeError):
        uncertain(host, job)
        raise HTTPException(503, '無法確認取消結果；已保留取消紀錄，請查詢原任務，不要重新生成')
