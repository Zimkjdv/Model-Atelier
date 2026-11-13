"""Bounded, explicitly started inventory of platform-owned storage paths."""

from contextlib import closing
import hashlib
import json
import logging
import os
from pathlib import Path
import sqlite3
import stat
from threading import Event, Lock, Thread
from time import monotonic, time
from uuid import UUID, uuid4

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict

from backend import environment, model_paths, storage

logger = logging.getLogger(__name__)
CACHE_KEY = 'storage-category-scan-v1'
TTL_SECONDS = 3600
MAX_ENTRIES = 200_000
MAX_SECONDS = 30
ACTIVE = {'queued', 'running'}
CATEGORIES = ('models', 'artworks')


class ScanRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')


class Cancelled(Exception):
    pass


def scope(host):
    managed = host.ROOT / 'runtime' / 'ComfyUI' / 'models'
    roots = [('models', managed, False), ('artworks', host.DATA / 'artworks', True)]
    errors = []
    revision = None
    if host.deployment.kind == 'native':
        try:
            records = model_paths.read(host.DB)
            revision = records['revision']
            roots.extend(('models', Path(path), False) for path in records['paths'])
        except (OSError, ValueError, sqlite3.Error):
            errors.append('models')
    else:
        roots = [item for item in roots if item[0] == 'artworks']
        errors.append('models')
    engine = host.engine_url()
    content = dict(
        roots=[
            dict(category=category, path=str(path), absent_is_empty=optional)
            for category, path, optional in roots
        ],
        revision=revision,
        unavailable=errors,
        engine_url=engine,
        external_engine=engine != model_paths.MANAGED_ENGINE or host.deployment.kind != 'native',
    )
    return content | dict(
        version=hashlib.sha256(json.dumps(content, sort_keys=True).encode()).hexdigest()
    )


def linked(info):
    return stat.S_ISLNK(info.st_mode) or bool(
        getattr(info, 'st_file_attributes', 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT
    )


def directory(path):
    if not path.is_absolute() or '..' in path.parts:
        raise ValueError('目錄路徑無效')
    # Validate each ancestor before reading its descendants. Managed paths and
    # registered extra roots use the same local-disk policy.
    model_paths._local(path)
    for part in (*reversed(path.parents), path):
        info = part.lstat()
        if linked(info) or not stat.S_ISDIR(info.st_mode):
            raise ValueError('目錄包含連結、重新分析點或非目錄項目')
    return info


def measure(scan_scope, stop, progress):
    deadline = monotonic() + MAX_SECONDS
    issues = []
    issue_count = 0
    incomplete = set(scan_scope['unavailable'])
    volumes = {}
    sizes = {}
    # Directory identity avoids revisiting overlapping roots; file identity also
    # catches hard links. Separate categories retain ownership until totals.
    visited = set()
    count = 0
    limited = False
    existing = set()

    def issue(category, path, message):
        nonlocal issue_count
        incomplete.add(category)
        issue_count += 1
        if len(issues) < 12:
            issues.append(dict(category=category, path=str(path), message=message))

    def check():
        if stop.is_set():
            raise Cancelled()
        return count < MAX_ENTRIES and monotonic() < deadline

    for root in scan_scope['roots']:
        category, path = root['category'], Path(root['path'])
        if not check():
            limited = True
            break
        try:
            info = directory(path)
            volume, label = storage.volume_identity(path)
        except FileNotFoundError:
            try:
                if not root['absent_is_empty']:
                    raise FileNotFoundError()
                directory(path.parent)
            except (OSError, ValueError):
                issue(category, path, '目錄尚不存在或磁碟未掛載。')
            else:
                existing.add(category)
            continue
        except (OSError, ValueError) as exc:
            issue(category, path, str(exc) if isinstance(exc, ValueError) else '無法讀取目錄。')
            continue
        existing.add(category)
        volumes.setdefault(volume, dict(id=volume, path=label, models=0, artworks=0))
        pending = [(path, info)]
        while pending:
            if not check():
                limited = True
                break
            current, previous = pending.pop()
            try:
                now = current.lstat()
                if (
                    linked(now)
                    or not stat.S_ISDIR(now.st_mode)
                    or current.resolve(strict=True) != current
                    or (now.st_dev, now.st_ino) != (previous.st_dev, previous.st_ino)
                ):
                    raise ValueError('掃描期間目錄已移動或改為連結。')
                directory_key = (category, volume, now.st_dev, now.st_ino)
                if not now.st_ino:
                    raise ValueError('無法識別目錄，已略過。')
                if directory_key in visited:
                    continue
                visited.add(directory_key)
                with os.scandir(current) as entries:
                    for entry in entries:
                        if not check():
                            limited = True
                            break
                        count += 1
                        if count == 1 or count % 128 == 0:
                            progress(count)
                        child = Path(entry.path)
                        try:
                            # DirEntry.stat can omit Windows file IDs.
                            info = child.lstat()
                            if linked(info) or info.st_dev != now.st_dev:
                                issue(category, child, '已略過連結、重新分析點或跨磁碟項目。')
                            elif stat.S_ISDIR(info.st_mode):
                                pending.append((child, info))
                            elif stat.S_ISREG(info.st_mode):
                                if info.st_ino == 0:
                                    issue(category, child, '無法識別檔案，未計入以避免重複。')
                                    continue
                                key = (volume, info.st_dev, info.st_ino)
                                old_size, owners = sizes.setdefault(key, (info.st_size, set()))
                                if info.st_size != old_size:
                                    for owner in owners | {category}:
                                        issue(owner, child, '掃描期間檔案大小已變更。')
                                owners.add(category)
                        except OSError:
                            issue(category, child, '檔案已移動或無法讀取。')
            except (OSError, ValueError, RuntimeError) as exc:
                issue(
                    category, current, str(exc) if isinstance(exc, ValueError) else '無法讀取目錄。'
                )
        if limited:
            break

    if stop.is_set():
        raise Cancelled()
    for category in scan_scope['unavailable']:
        issue(category, '', '此部署無法統計模型目錄，或額外目錄設定無法讀取。')
    if limited:
        for category in CATEGORIES:
            issue(category, '', '已達掃描時間或項目數上限。')
    conflicts = 0
    for (volume, _, _), (size, owners) in sizes.items():
        if len(owners) == 1:
            volumes[volume][next(iter(owners))] += size
        else:
            conflicts += 1
    # A cross-category root overlap is still incomplete if the overlap is empty.
    registered_roots = [(item['category'], Path(item['path'])) for item in scan_scope['roots']]
    overlap = any(
        left_kind != right_kind and (left.is_relative_to(right) or right.is_relative_to(left))
        for index, (left_kind, left) in enumerate(registered_roots)
        for right_kind, right in registered_roots[index + 1 :]
    )
    if overlap and not conflicts:
        for category in CATEGORIES:
            issue(category, '', '模型與作品目錄範圍重疊。')
    if conflicts:
        for category in CATEGORIES:
            issue(category, '', f'{conflicts} 個檔案同屬模型與作品範圍，未計入任一分類。')

    categories = {}
    for category in CATEGORIES:
        known = sum(volume[category] for volume in volumes.values())
        status = (
            'unavailable'
            if category not in existing
            else 'partial'
            if category in incomplete
            else 'complete'
        )
        categories[category] = dict(
            status=status,
            observed_bytes=known if category in existing else None,
            bytes=known if status == 'complete' else None,
        )
    return dict(
        status='partial'
        if any(row['status'] != 'complete' for row in categories.values())
        else 'completed',
        visited=count,
        issue_count=issue_count,
        issues=issues,
        categories=categories,
        volumes=list(volumes.values()),
        other_bytes=None,
        metric='logical_bytes',
    )


class Scans:
    def __init__(self, host):
        self.host = host
        self.owner = str(uuid4())
        self.lock = Lock()
        self.stop = Event()
        self.worker = None
        self.visited = 0
        self.closed = False

    def shutdown(self):
        with self.lock:
            self.closed = True
            self.stop.set()
            worker = self.worker
        if worker:
            worker.join(timeout=2)

    def read(self, db):
        row = db.execute('SELECT value FROM settings WHERE key=?', (CACHE_KEY,)).fetchone()
        return (
            json.loads(row[0])
            if row
            else dict(scan=None, last_completed=None, last_result=None, known={})
        )

    def write(self, db, state):
        db.execute(
            'INSERT OR REPLACE INTO settings VALUES (?,?)',
            (CACHE_KEY, json.dumps(state, ensure_ascii=False)),
        )

    def view(self, scan_scope):
        with self.lock, closing(sqlite3.connect(self.host.DB)) as db:
            return self.snapshot(self.read(db), scan_scope)

    def snapshot(self, state, scan_scope):
        scan = state['scan']
        if scan and scan['status'] in ACTIVE:
            if scan['owner'] != self.owner:
                scan.update(status='failed', finished_at=None, error='平台重新啟動，原掃描已中斷。')
            elif self.worker:
                scan['visited'] = self.visited
            else:
                scan.update(status='failed', error='無法保存掃描狀態。')

        def freshness(version, finished):
            if version != scan_scope['version']:
                return '目錄或引擎設定已變更。'
            if finished and time() - finished >= TTL_SECONDS:
                return '距離上次掃描已超過一小時。'
            return None

        last = state['last_completed']
        recent = state.get('last_result')
        known = {}
        for category, value in state.get('known', {}).items():
            known[category] = {
                key: value[key] for key in ('bytes', 'checked_at', 'volumes')
            } | dict(stale_reason=freshness(value['scope_version'], value['finished_epoch']))
        for entry in (scan, last, recent):
            if entry:
                entry['stale_reason'] = freshness(
                    entry['scope']['version'], entry.pop('finished_epoch', None)
                )
                entry.pop('owner', None)
        return dict(
            scan=scan, last_completed=last, last_result=recent, known=known, scope=scan_scope
        )

    def start(self, scan_scope):
        with self.lock, closing(sqlite3.connect(self.host.DB)) as db:
            if self.closed:
                raise HTTPException(503, '平台正在停止。')
            if self.worker:
                return self.snapshot(self.read(db), scan_scope)
            with db:
                db.execute('BEGIN IMMEDIATE')
                state = self.read(db)
                scan = dict(
                    id=str(uuid4()),
                    owner=self.owner,
                    scope=scan_scope,
                    status='queued',
                    started_at=environment.now(),
                    finished_at=None,
                    visited=0,
                    error=None,
                )
                state['scan'] = scan
                self.write(db, state)
            self.visited = 0
            self.stop = Event()
            self.worker = Thread(target=self.run, args=(scan,), daemon=True)
            try:
                self.worker.start()
            except RuntimeError:
                self.worker = None
                self.finish(scan, dict(status='failed', error='無法啟動背景掃描。'))
            return self.snapshot(self.read(db), scan_scope)

    def finish(self, scan, result):
        with closing(sqlite3.connect(self.host.DB)) as db, db:
            db.execute('BEGIN IMMEDIATE')
            state = self.read(db)
            if not state['scan'] or state['scan']['id'] != scan['id']:
                return
            final = scan | result
            if result['status'] not in ACTIVE:
                final.update(finished_at=environment.now(), finished_epoch=time())
            state['scan'] = final
            if final['status'] in ('completed', 'partial'):
                state['last_result'] = final
            if final['status'] == 'completed':
                state['last_completed'] = final
            for name, category in final.get('categories', {}).items():
                if category['status'] == 'complete':
                    state.setdefault('known', {})[name] = dict(
                        bytes=category['bytes'],
                        checked_at=final['finished_at'],
                        finished_epoch=final['finished_epoch'],
                        scope_version=scan['scope']['version'],
                        volumes=[
                            dict(id=volume['id'], path=volume['path'], bytes=volume[name])
                            for volume in final['volumes']
                        ],
                    )
            self.write(db, state)

    def run(self, scan):
        try:
            with self.lock:
                if self.closed:
                    return
                self.finish(scan, dict(status='running'))
            result = measure(
                scan['scope'], self.stop, lambda count: setattr(self, 'visited', count)
            )
        except Cancelled:
            result = dict(status='cancelled', visited=self.visited)
        except Exception:
            logger.exception('Storage scan failed')
            result = dict(status='failed', visited=self.visited, error='無法完成分類容量掃描。')
        with self.lock:
            try:
                if not self.closed:
                    if self.stop.is_set():
                        result = dict(
                            status='cancelled', visited=result.get('visited', self.visited)
                        )
                    self.finish(scan, result)
            except sqlite3.Error:
                logger.exception('Unable to save storage scan')
            finally:
                self.worker = None

    def cancel(self, identifier):
        with self.lock, closing(sqlite3.connect(self.host.DB)) as db:
            scan = self.read(db)['scan']
            if not scan or scan['id'] != identifier:
                raise HTTPException(404, '找不到此掃描。')
            if scan['owner'] == self.owner and scan['status'] in ACTIVE:
                self.stop.set()


def install(app, host):
    scans = Scans(host)

    @app.get('/api/storage/categories')
    def categories():
        return scans.view(scope(host))

    @app.post('/api/storage/scans', status_code=202)
    def start(_body: ScanRequest):
        return scans.start(scope(host))

    @app.get('/api/storage/scans/{identifier}')
    def scan(identifier: UUID):
        view = categories()
        if not view['scan'] or view['scan']['id'] != str(identifier):
            raise HTTPException(404, '找不到此掃描。')
        return view

    @app.post('/api/storage/scans/{identifier}/cancel')
    def cancel(identifier: UUID, _body: ScanRequest):
        scans.cancel(str(identifier))
        return categories()

    return scans
