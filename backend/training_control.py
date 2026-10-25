"""Web control of explicit native T03 attempts, with durable request recovery."""

from contextlib import closing
import json
import os
from pathlib import Path
import socket
import sqlite3
import threading
import httpx

from backend import (
    compute_lease,
    training_runs as runs,
    training_data as data,
    training_artifacts as artifacts,
)
from backend.training_files import read_json
from backend.training_review import Reviews, Conflict, identifier, now


def supported(host):
    return host.deployment.kind == 'native' and os.name == 'nt'


def engine_online():
    with socket.socket() as connection:
        connection.settimeout(0.3)
        return connection.connect_ex(('127.0.0.1', 8188)) == 0


class Control:
    def __init__(self, host):
        self.host = host
        self.reviews = Reviews(host)
        self.guard = threading.RLock()
        self.threads = {}

    def native(self):
        if not supported(self.host):
            raise Conflict('訓練控制僅支援 Windows 原生平台；容器與其他 OS 不啟動 trainer。')

    def read(self, key):
        with closing(sqlite3.connect(self.host.DB)) as db:
            row = db.execute('SELECT value FROM settings WHERE key=?', (key,)).fetchone()
        if row is None:
            raise KeyError('找不到原訓練請求／已登記 run')
        return json.loads(row[0])

    def put(self, key, value):
        with closing(sqlite3.connect(self.host.DB)) as db, db:
            db.execute(
                'INSERT OR REPLACE INTO settings VALUES (?,?)',
                (key, json.dumps(value, ensure_ascii=False)),
            )

    def records(self, prefix):
        with closing(sqlite3.connect(self.host.DB)) as db:
            return [
                json.loads(v)
                for (v,) in db.execute(
                    "SELECT value FROM settings WHERE key GLOB ? ORDER BY json_extract(value,'$.updated_at') DESC,key LIMIT 1000",
                    (prefix + '*',),
                )
            ]

    def exports(self):
        result = []
        for value in self.records('training_export:'):
            if value['status'] != 'completed':
                continue
            review = self.reviews.get(value['dataset_id'], value['revision'])
            result.append(
                value
                | dict(
                    dataset_label=review['dataset']['dataset_id'], kind=review['dataset']['kind']
                )
            )
        return sorted(result, key=lambda v: v['updated_at'], reverse=True)

    def request(self, uid):
        with self.guard:
            value = self.read('training_request:' + identifier(uid))
            thread = self.threads.get(identifier(uid))
            if value['status'] == 'preparing' and (thread is None or not thread.is_alive()):
                return value | dict(
                    status='interrupted',
                    error='準備程序已中斷；保留原請求，不自動重做。請檢查 runtime 後明確建立新請求。',
                )
        return value

    def link(self, uid):
        runs.inspect(identifier(uid), root=self.host.ROOT)
        self.put(
            'training_run_link:' + identifier(uid), dict(run_id=identifier(uid), updated_at=now())
        )
        return self.detail(uid)

    def detail(self, uid):
        uid = identifier(uid)
        self.read('training_run_link:' + uid)
        status = runs.inspect(uid, root=self.host.ROOT)
        directory = runs.run_directory(uid, self.host.ROOT)
        manifest = read_json(directory / 'manifest.json')
        result = status | dict(
            configuration=manifest['configuration'],
            dataset=manifest['dataset'],
            base=manifest['base'],
            environment=manifest['environment'],
            resume=manifest['resume'],
            checkpoints=[],
        )
        for path in sorted((directory / 'checkpoints').glob('step-*.json')):
            receipt = self.optional(directory, 'checkpoints/' + path.name)
            if (
                receipt
                and receipt.get('manifest_sha256') == status['manifest_sha256']
                and receipt.get('run_id') == uid
            ):
                result['checkpoints'].append(dict(id=path.stem, step=receipt['step']))
        for name in ('resources', 'artifacts'):
            result[name] = self.optional(directory, name + '.json')
        try:
            start = self.read('training_start:' + uid)
        except KeyError:
            start = None
        result['start_requested'] = start is not None
        if start:
            result['dispatch_error'] = start.get('error')
            if status['status'] == 'prepared':
                running = self.threads.get('run:' + uid)
                result.update(
                    status='starting' if running and running.is_alive() else 'start_unknown',
                    resources_released=not (running and running.is_alive()),
                )
        path = directory / 'worker.log'
        if path.exists():
            if path.is_symlink() or (hasattr(path, 'is_junction') and path.is_junction()):
                raise ValueError('訓練日誌不能是連結')
            with path.open('rb') as stream:
                stream.seek(max(0, path.stat().st_size - 65536))
                result['log_tail'] = stream.read(65536).decode('utf-8', errors='replace')
        else:
            result['log_tail'] = ''
        return result

    @staticmethod
    def optional(directory, name):
        path = directory / name
        if not path.exists():
            return None
        for part in (path, path.parent):
            if part.is_symlink() or (hasattr(part, 'is_junction') and part.is_junction()):
                raise ValueError('訓練紀錄不能是連結')
        return read_json(path)

    def begin(self, request, platform_url=None):
        self.native()
        uid = identifier(request.request_id)
        payload = request.model_dump(mode='json')
        key = 'training_request:' + uid
        with self.guard, closing(sqlite3.connect(self.host.DB)) as db, db:
            db.execute('BEGIN IMMEDIATE')
            old = db.execute('SELECT value FROM settings WHERE key=?', (key,)).fetchone()
            if old:
                old = json.loads(old[0])
                if old['request'] != payload:
                    raise Conflict('此 UUID 已有不同設定，請查回原訓練請求')
                return self.request(uid)
            if len(self.records('training_request:')) >= 1000:
                raise ValueError('訓練請求已達 1000 筆，請先備份整理')
            value = dict(
                request_id=uid,
                status='preparing',
                request=payload,
                run_id=None,
                updated_at=now(),
                platform_url=platform_url,
            )
            db.execute('INSERT INTO settings VALUES (?,?)', (key, json.dumps(value)))
            # Commit reservation before the background task can access it.
            db.commit()
            thread = threading.Thread(target=self.prepare, args=(uid,), daemon=True)
            self.threads[uid] = thread
            thread.start()
        return value

    def prepare(self, uid):
        key = 'training_request:' + uid
        value = self.read(key)
        request = value['request']
        try:
            if request.get('action') == 'evaluation':
                self.read('training_run_link:' + request['run_id'])
                target = self.host.ROOT / 'runtime/training/evaluations' / uid
                value.update(run_id=request['run_id'], evaluation_path=str(target))
                with httpx.Client(
                    base_url=value['platform_url'], timeout=30, trust_env=False
                ) as client:
                    artifacts.evaluation(client, request['run_id'], target, root=self.host.ROOT)
                    plans = artifacts.save_plans(client, target)
                value.update(
                    status='completed',
                    run_id=request['run_id'],
                    evaluation_path=str(target),
                    evaluation=plans,
                )
                self.put(key, value | dict(updated_at=now()))
                return
            elif request.get('resume_run_id'):
                self.read('training_run_link:' + request['resume_run_id'])
                previous = read_json(
                    runs.run_directory(request['resume_run_id'], self.host.ROOT) / 'manifest.json'
                )
                original_study = previous.get('parent_study')
                study = (
                    (original_study['document'], original_study['sha256'])
                    if original_study
                    else None
                )
                result = runs.prepare(
                    previous['configuration'],
                    root=self.host.ROOT,
                    resume=dict(run_id=request['resume_run_id'], checkpoint=request['checkpoint']),
                    study=study,
                )
            else:
                exported = self.reviews.export_status(request['export_id'])
                if exported['status'] != 'completed':
                    raise ValueError('只有已封存完成的資料出口可準備訓練')
                review = self.reviews.get(exported['dataset_id'], exported['revision'])
                if review['manifest_sha256'] != exported['manifest_sha256']:
                    raise ValueError('資料出口與原審查修訂不同')
                study = (
                    data.parse_json(review['study_json'].encode('utf-8'))
                    if review['study_json']
                    else None
                )
                config = {
                    k: request[k]
                    for k in (
                        'label',
                        'purpose',
                        'gpu_index',
                        'resolution',
                        'rank',
                        'learning_rate',
                        'max_steps',
                        'save_every_steps',
                        'seed',
                    )
                }
                model = runs.base(self.host.ROOT)[0]
                config.update(
                    bundle=exported['path'],
                    checkpoint=str(
                        self.host.ROOT / 'runtime/ComfyUI/models/checkpoints' / model['filename']
                    ),
                )
                result = runs.prepare(config, root=self.host.ROOT, study=study)
            value.update(status='prepared', run_id=result['run_id'])
            self.put(
                'training_run_link:' + result['run_id'],
                dict(run_id=result['run_id'], request_id=uid, updated_at=now()),
            )
        except Exception as exc:
            value.update(status='failed', error=str(exc)[:2000])
        value['updated_at'] = now()
        self.put(key, value)

    def start(self, uid):
        self.native()
        uid = identifier(uid)
        current = self.detail(uid)
        key = 'training_start:' + uid
        with self.guard, closing(sqlite3.connect(self.host.DB)) as db, db:
            db.execute('BEGIN IMMEDIATE')
            if db.execute('SELECT 1 FROM settings WHERE key=?', (key,)).fetchone():
                return self.detail(uid)
            if current['status'] != 'prepared' or not current['resources_released']:
                raise Conflict('只可明確啟動尚未開始且已釋放資源的 prepared run')
            if engine_online():
                raise Conflict(
                    '受管理 ComfyUI 8188 仍在運行；先完成工作並停止引擎，容器平台也須先停止。'
                )
            if compute_lease.status(self.host.ROOT)['active']:
                raise Conflict('本專案運算仍被其他訓練或生成使用；請查閱原任務')
            if any(
                key.startswith('run:') and thread.is_alive() for key, thread in self.threads.items()
            ):
                raise Conflict('另一個訓練控制程序仍在啟動或收尾；請先查回原 run')
            db.execute(
                'INSERT INTO settings VALUES (?,?)', (key, json.dumps(dict(requested_at=now())))
            )
            db.commit()
            thread = threading.Thread(target=self.launch, args=(uid,), daemon=True)
            self.threads['run:' + uid] = thread
            thread.start()
        return dict(run_id=uid, status='start_requested')

    def launch(self, uid):
        try:
            runs.launch(uid, root=self.host.ROOT)
        except Exception as exc:
            value = self.read('training_start:' + uid)
            self.put('training_start:' + uid, value | dict(error=str(exc)[:2000]))
