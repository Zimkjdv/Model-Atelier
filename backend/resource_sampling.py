"""Bounded observations from a job's original engine, independent of job revisions.

This observes shared host/device usage. It does not reset allocator counters,
attribute memory to a prompt, retry generation, or decide terminal job states.
"""

import asyncio
from contextlib import closing, suppress
from copy import deepcopy
from datetime import datetime, timezone
import json
import sqlite3
from uuid import uuid4

import httpx
from backend import environment, job_measurements

INTERVAL = 2
MAX_ACTIVE = 16
MAX_ATTEMPTS = 1800
MAX_POINTS = 120
MAX_DEVICES = 16
MAX_BYTES = 256 * 1024
ACTIVE = 'resources:active'
NOTE = (
    '每次取樣是原引擎主機 RAM／共享裝置用量，可能包含其他程序、佇列等待與可回收快取。'
    '裝置用量依引擎的 total−free 計算；CUDA free 可能包含 allocator 可回收快取，與 nvidia-smi 整卡已用量不同。'
    '觀察最高值僅涵蓋成功取樣時刻，不是連續真實峰值、任務專用峰值或最低硬體需求；'
    'PyTorch allocator 的統計也無法可靠歸屬單一任務。'
)


def now():
    return datetime.now(timezone.utc).isoformat()


def load(db, key, default=None):
    row = db.execute('SELECT value FROM settings WHERE key=?', (key,)).fetchone()
    return json.loads(row[0]) if row else default


def save(db, key, value):
    db.execute(
        'INSERT OR REPLACE INTO settings VALUES (?, ?)',
        (key, json.dumps(value, ensure_ascii=False, allow_nan=False)),
    )


def finish(db, job_id, report, timestamp, reason):
    if report['ended_at'] is None:
        report.update(ended_at=timestamp, end_reason=reason)
    active = load(db, ACTIVE, [])
    if job_id in active:
        save(db, ACTIVE, [key for key in active if key != job_id])


def transition(db, job, timestamp):
    """Called inside the existing job transaction. Never starts historical jobs."""
    metrics = job.get('measurements')
    if not isinstance(metrics, dict) or 'continuous_resources' not in metrics:
        return
    key = 'resources:' + job['id']
    journal = load(db, key)
    if (
        journal is None
        and metrics['continuous_resources'] is None
        and job['status'] == 'submitting'
    ):
        active = load(db, ACTIVE, [])
        report = dict(
            schema_version=1,
            source=job['engine_url'] + '/system_stats',
            engine_url=job['engine_url'],
            started_at=timestamp,
            ended_at=None,
            end_reason=None,
            interval_seconds=INTERVAL,
            max_attempts=MAX_ATTEMPTS,
            retained_points=MAX_POINTS,
            attempts=0,
            successes=0,
            failures=0,
            gaps=0,
            last_attempt_at=None,
            last_error=None,
            ram_max_used_bytes=None,
            devices=[],
            samples=[],
            note=NOTE,
            task_vram_peak_bytes=None,
        )
        if len(active) >= MAX_ACTIVE:
            finish(db, job['id'], report, timestamp, 'capacity_limit')
        else:
            journal = dict(report=report, owner=None, claimed_at=None)
            save(db, ACTIVE, [*active, job['id']])
            save(db, key, journal)
        metrics['continuous_resources'] = report
    if journal:
        report = journal['report']
        if job['status'] in job_measurements.TERMINAL:
            finish(db, job['id'], report, timestamp, 'job_terminal')
            db.execute('DELETE FROM settings WHERE key=?', (key,))
        metrics['continuous_resources'] = deepcopy(report)


def project(db, job):
    """GET can show fresh samples without changing the job or its revision."""
    metrics = job.get('measurements')
    if isinstance(metrics, dict) and 'continuous_resources' in metrics:
        journal = load(db, 'resources:' + job['id'])
        if journal:
            metrics['continuous_resources'] = journal['report']
    return job


def maximum(a, b):
    return b if a is None else a if b is None else max(a, b)


def observe(report, stats, timestamp, error=None):
    """Whitelist normalized numbers, retain a tail plus maxima across all attempts."""
    duration = job_measurements.elapsed(
        report['last_attempt_at'] or report['started_at'], timestamp
    )
    if duration is not None and duration > INTERVAL * 2:
        report['gaps'] += 1
    report['attempts'] += 1
    report['last_attempt_at'] = timestamp
    normalized = environment.engine_diagnostics(stats)
    error = error or (None if normalized['status'] == 'available' else 'invalid_stats')
    report['last_error'] = error
    report['failures' if error else 'successes'] += 1
    point = dict(at=timestamp, ram_used_bytes=None, devices=[], error=error)
    if not error:
        point['ram_used_bytes'] = normalized['ram']['used']
        report['ram_max_used_bytes'] = maximum(
            report['ram_max_used_bytes'], point['ram_used_bytes']
        )
        for device in normalized['devices']:
            identity = {key: device[key] for key in ('name', 'type', 'index')}
            index = next(
                (
                    i
                    for i, old in enumerate(report['devices'])
                    if all(old[key] == val for key, val in identity.items())
                ),
                None,
            )
            if index is None:
                if len(report['devices']) >= MAX_DEVICES:
                    continue
                index = len(report['devices'])
                report['devices'].append(identity | dict(max_used_bytes=None))
            used = device['vram']['used']
            report['devices'][index]['max_used_bytes'] = maximum(
                report['devices'][index]['max_used_bytes'], used
            )
            point['devices'].append(dict(device=index, used_bytes=used))
    report['samples'] = [*report['samples'], point][-MAX_POINTS:]


def claim(path, owner, timestamp):
    claimed = []
    with closing(sqlite3.connect(path)) as db, db:
        db.execute('BEGIN IMMEDIATE')
        for job_id in load(db, ACTIVE, []):
            key = 'resources:' + job_id
            journal = load(db, key)
            if not journal:
                continue
            report = journal['report']
            duration = job_measurements.elapsed(report['started_at'], timestamp)
            if report['attempts'] >= MAX_ATTEMPTS or (duration is not None and duration >= 3600):
                finish(db, job_id, report, timestamp, 'sampling_limit')
                save(db, key, journal)
                continue
            since = job_measurements.elapsed(journal['claimed_at'], timestamp)
            if since is not None and since < (INTERVAL if journal['owner'] == owner else 10):
                continue
            journal.update(owner=owner, claimed_at=timestamp)
            save(db, key, journal)
            claimed.append((job_id, report['engine_url']))
    return claimed


def record(path, owner, ids, stats, timestamp, error=None):
    with closing(sqlite3.connect(path)) as db, db:
        db.execute('BEGIN IMMEDIATE')
        for job_id in ids:
            key = 'resources:' + job_id
            journal = load(db, key)
            # A terminal transition deletes the journal; late responses are discarded.
            if not journal or journal['owner'] != owner or journal['report']['ended_at']:
                continue
            observe(journal['report'], stats, timestamp, error)
            save(db, key, journal)


class Monitor:
    def __init__(self, context):
        self.context, self.owner = context, str(uuid4())
        self.task = None

    async def __aenter__(self):
        self.task = asyncio.create_task(self.run())
        return self

    async def __aexit__(self, *args):
        self.task.cancel()
        with suppress(asyncio.CancelledError):
            await self.task
        # Preserve partial coverage after shutdown; never imply collection while offline.
        with closing(sqlite3.connect(self.context.DB)) as db, db:
            db.execute('BEGIN IMMEDIATE')
            for job_id in load(db, ACTIVE, []):
                journal = load(db, 'resources:' + job_id)
                if journal and journal['owner'] == self.owner:
                    finish(db, job_id, journal['report'], now(), 'platform_shutdown')
                    save(db, 'resources:' + job_id, journal)

    async def fetch(self, engine_url, ids):
        stats, error = None, None
        try:
            async with asyncio.timeout(2):
                async with self.context.http_client(
                    timeout=2, trust_env=False, follow_redirects=False
                ) as client:
                    async with client.stream('GET', engine_url + '/system_stats') as response:
                        response.raise_for_status()
                        raw = bytearray()
                        async for chunk in response.aiter_bytes(chunk_size=8192):
                            if len(raw) + len(chunk) > MAX_BYTES:
                                raise ValueError('size_limit')
                            raw.extend(chunk)
                        stats = json.loads(raw)
        except (httpx.HTTPError, TimeoutError, ValueError, TypeError):
            error = 'request_unavailable'
        record(self.context.DB, self.owner, ids, stats, now(), error)

    async def cycle(self):
        groups = {}
        for job_id, engine in claim(self.context.DB, self.owner, now()):
            groups.setdefault(engine, []).append(job_id)
        await asyncio.gather(*(self.fetch(engine, ids) for engine, ids in groups.items()))

    async def run(self):
        while True:
            try:
                await self.cycle()
            except sqlite3.OperationalError:
                # A temporary DB contention never turns an engine job into a failure.
                pass
            await asyncio.sleep(INTERVAL)
