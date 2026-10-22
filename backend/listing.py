"""Bounded snapshot membership over legacy JSON records; no data migration.

Only keys are cached. Each page projects small SQL summaries, and mutable
details are always read afresh. Cache eviction/expiry is explicit to clients.
"""
from collections import OrderedDict
from contextlib import closing
from dataclasses import dataclass
import json
import sqlite3
import threading
import time
from uuid import uuid4

MAX_KEYS = 50000
TTL = 600


class ListingError(ValueError):
    def __init__(self, status, message):
        super().__init__(message)
        self.status = status


@dataclass
class Snapshot:
    keys: tuple[str, ...]
    query: tuple
    expires: float
    models: list[str]


class Pager:
    def __init__(self, path, clock=time.monotonic):
        self.path, self.clock = path, clock
        self.snapshots = OrderedDict()
        self.lock = threading.Lock()

    def page(self, kind, *, limit=40, cursor=None, q='', scope='active', favorites_only=False, model='', status='', workflow='all', purpose=''):
        if kind not in ('artworks', 'jobs', 'assets') or not 1 <= limit <= 100:
            raise ListingError(422, '不支援的清單或頁面大小')
        query = (kind, limit, q.strip().casefold(), scope, favorites_only, model, status, workflow, purpose)
        with self.lock:
            now = self.clock()
            for key in list(self.snapshots):
                if self.snapshots[key].expires <= now:
                    del self.snapshots[key]
            if cursor:
                try:
                    token, raw_offset = cursor.split(':')
                    offset = int(raw_offset)
                    if offset < 0 or str(offset) != raw_offset:
                        raise ValueError()
                except (ValueError, AttributeError):
                    raise ListingError(400, '清單游標無效')
                snapshot = self.snapshots.get(token)
                if snapshot is None:
                    raise ListingError(410, '清單已過期，請重新整理取得最新清單')
                if snapshot.query != query or offset >= max(1, len(snapshot.keys)) or offset % limit:
                    raise ListingError(409, '清單條件已變更或游標無效，請重新整理')
                self.snapshots.move_to_end(token)
            else:
                snapshot = self._snapshot(query, now)
                token, offset = str(uuid4()), 0
                while self.snapshots and (len(self.snapshots) >= 8 or sum(len(v.keys) for v in self.snapshots.values()) + len(snapshot.keys) > MAX_KEYS):
                    self.snapshots.popitem(last=False)
                self.snapshots[token] = snapshot
        page_keys = snapshot.keys[offset:offset + limit]
        items, missing = self._summaries(kind, page_keys)
        return dict(items=items, missing_ids=missing, total=len(snapshot.keys), offset=offset, limit=limit,
                    next_cursor=f'{token}:{offset + limit}' if offset + limit < len(snapshot.keys) else None,
                    previous_cursor=f'{token}:{max(0, offset-limit)}' if offset else None,
                    models=snapshot.models[:500], models_truncated=len(snapshot.models) > 500)

    def _snapshot(self, query, now):
        kind, limit, q, scope, favorite, model, status, workflow, purpose = query
        prefix = {'artworks': 'artwork', 'jobs': 'job', 'assets': 'asset'}[kind]
        clauses, values = ['key GLOB ?'], [prefix + ':*']
        if kind != 'jobs' and scope != 'all':
            clauses.append("COALESCE(json_extract(value,'$.archived'),0)=?")
            values.append(int(scope == 'archived'))
        if favorite:
            clauses.append("json_extract(value,'$.favorite')=1")
        if model:
            clauses.append("json_extract(value,'$.checkpoint')=?"); values.append(model)
        if status:
            clauses.append("json_extract(value,'$.status')=?"); values.append(status)
        if purpose:
            clauses.append("COALESCE(json_extract(value,'$.purpose'),'unspecified')=?"); values.append(purpose)
        if workflow != 'all':
            families = dict(flux=['flux1-schnell-text2image-v1'], inpaint=['checkpoint-inpaint-v1', 'checkpoint-inpaint-feather-v2'], control=['checkpoint-canny-controlnet-v1', 'checkpoint-canny-controlnet-edge-v2'])
            if workflow == 'checkpoint':
                clauses.append("COALESCE(json_extract(value,'$.workflow_id'),'') IN ('','checkpoint-image2image-v1')")
            else:
                ids = families[workflow]
                clauses.append("json_extract(value,'$.workflow_id') IN (" + ','.join('?' for _ in ids) + ')'); values.extend(ids)
        if q:
            fields = ['title', 'checkpoint', 'model_version', 'notes', 'parameters.prompt', 'loras', 'lora_metadata']
            text = " || ' ' || ".join("COALESCE(json_extract(value,'$." + key + "'),'')" for key in fields)
            clauses.append('instr(casefold(' + text + '),?)>0'); values.append(q)
        date = 'imported_at' if kind == 'artworks' else 'created_at'
        with closing(sqlite3.connect(self.path)) as db:
            db.create_function('casefold', 1, lambda value: str(value).casefold(), deterministic=True)
            # A read transaction fixes membership and metadata at the same point.
            db.execute('BEGIN')
            rows = db.execute('SELECT key FROM settings WHERE ' + ' AND '.join(clauses) +
                              f" ORDER BY json_extract(value,'$.{date}') DESC,key DESC LIMIT ?", values + [MAX_KEYS + 1]).fetchall()
            if len(rows) > MAX_KEYS:
                raise ListingError(413, '符合項目超過 50,000 筆，請縮小搜尋或篩選')
            models = [row[0] for row in db.execute("SELECT DISTINCT json_extract(value,'$.checkpoint') FROM settings WHERE key GLOB 'artwork:*' AND json_extract(value,'$.checkpoint') IS NOT NULL ORDER BY 1 LIMIT 501")] if kind == 'artworks' else []
        return Snapshot(tuple(row[0] for row in rows), query, now + TTL, models)

    def _summaries(self, kind, keys):
        if not keys:
            return [], []
        common = ['id', 'title', 'created_at', 'revision']
        fields = {
            'artworks': common + ['job_id', 'checkpoint', 'model_version', 'workflow_id', 'width', 'height', 'size', 'extension', 'imported_at', 'favorite', 'archived'],
            'jobs': common + ['prompt_id', 'checkpoint', 'workflow_id', 'engine_url', 'status', 'error', 'failure_info', 'updated_at'],
            'assets': common + ['width', 'height', 'size', 'archived', 'purpose', 'sha256'],
        }[kind]
        projection = ','.join(f"'{key}',json_extract(value,'$.{key}')" for key in fields)
        if kind == 'artworks':
            projection += ", 'notes',substr(COALESCE(json_extract(value,'$.notes'),''),1,160)"
            projection += ", 'notes_truncated',length(COALESCE(json_extract(value,'$.notes'),''))>160"
        if kind == 'assets':
            projection += ", 'preprocessing',CASE WHEN json_type(value,'$.preprocessing')='object' THEN json_object('version',json_extract(value,'$.preprocessing.version'),'library_version',json_extract(value,'$.preprocessing.library_version')) ELSE NULL END"
        with closing(sqlite3.connect(self.path)) as db:
            rows = db.execute('SELECT key,json_object(' + projection + ') FROM settings WHERE key IN (' + ','.join('?' for _ in keys) + ')', keys).fetchall()
        by_key = {key: json.loads(raw) for key, raw in rows}
        for item in by_key.values():
            if kind == 'assets' and item['purpose'] is None:
                item['purpose'] = 'unspecified'
            for field in ['revision', 'favorite', 'archived']:
                if field in item and item[field] is None:
                    item[field] = 0
        return [by_key[key] for key in keys if key in by_key], [key.split(':', 1)[1] for key in keys if key not in by_key]
