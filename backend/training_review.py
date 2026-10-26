"""Human dataset reviews: immutable versions, source checks and sealed exports."""

from contextlib import closing
from datetime import datetime, timezone
import io
import json
import sqlite3
from uuid import UUID

from PIL import Image, ImageOps
from backend import model_paths, training_data as data, training_bundle as bundle
from backend.training_runs import base

PREFIX = 'training_review:'


class Conflict(ValueError):
    pass


def now():
    return datetime.now(timezone.utc).isoformat()


def identifier(value):
    return str(UUID(str(value)))


class Reviews:
    def __init__(self, host):
        self.host = host

    def native(self):
        if self.host.deployment.kind != 'native':
            raise Conflict('訓練資料審查需使用原生平台；容器無法讀取 Windows 原圖。')

    def get(self, value, revision=None):
        key = PREFIX + identifier(value)
        if revision is not None:
            if not 1 <= revision <= 100:
                raise ValueError('修訂超出範圍')
            key += f':v{revision}'
        with closing(sqlite3.connect(self.host.DB)) as db:
            row = db.execute('SELECT value FROM settings WHERE key=?', (key,)).fetchone()
        if row is None:
            raise KeyError('找不到資料集／修訂')
        return json.loads(row[0])

    def listing(self):
        with closing(sqlite3.connect(self.host.DB)) as db:
            rows = db.execute(
                'SELECT key,value FROM settings WHERE key GLOB ? AND key NOT GLOB ?',
                (PREFIX + '*', PREFIX + '*:*'),
            )
            values = [json.loads(raw) for key, raw in rows if key.count(':') == 1]
        return sorted(
            [self.summary(v) for v in values], key=lambda v: v['updated_at'], reverse=True
        )

    @staticmethod
    def summary(value):
        dataset = value['dataset']
        return {k: value[k] for k in ('id', 'revision', 'updated_at', 'manifest_sha256')} | dict(
            dataset_id=dataset['dataset_id'],
            version=dataset['version'],
            kind=dataset['kind'],
            counts=value['readiness']['counts'],
            data_ready=value['readiness']['data_ready'],
        )

    def inspect_sources(self, dataset, source, study_json):
        study = data.parse_json(study_json.encode('utf-8')) if study_json else None
        try:
            report = data.audit(dataset, source, base(self.host.ROOT)[1], study)
        except (KeyError, TypeError, AttributeError) as exc:
            raise ValueError('前序 study 格式不完整') from exc
        if any(
            i['code'].startswith('parent_study') or i['code'] == 'base_model_differs_from_t01'
            for i in report['issues']
        ):
            raise ValueError('基底或前序 study 與固定清單不符')
        return report

    def create(self, request):
        self.native()
        uid = identifier(request.request_id)
        source = str(model_paths.canonical_directory(request.source_root))
        dataset = data.Dataset.model_validate(
            data.parse_json(request.manifest_json.encode('utf-8'))[0]
        )
        report = self.inspect_sources(dataset, source, request.study_json)
        if any(i['code'] == 'source_integrity' for i in report['issues']):
            raise ValueError('原圖與清單不符；請核對來源目錄及完整性')
        value = dict(
            id=uid,
            revision=1,
            source_root=source,
            study_json=request.study_json,
            dataset=dataset.model_dump(mode='json'),
            readiness=report,
            updated_at=now(),
            manifest_sha256=data.digest(data.manifest_bytes(dataset)),
        )
        with closing(sqlite3.connect(self.host.DB)) as db, db:
            db.execute('BEGIN IMMEDIATE')
            old = db.execute('SELECT value FROM settings WHERE key=?', (PREFIX + uid,)).fetchone()
            if old:
                old = json.loads(old[0])
                first = json.loads(
                    db.execute(
                        'SELECT value FROM settings WHERE key=?', (PREFIX + uid + ':v1',)
                    ).fetchone()[0]
                )
                if any(
                    first[k] != value[k] for k in ('source_root', 'study_json', 'manifest_sha256')
                ):
                    raise Conflict('原匯入 UUID 已用於不同資料；請查回原資料集')
                return old
            count = db.execute(
                "SELECT COUNT(*) FROM settings WHERE key GLOB 'training_review:*' AND key NOT GLOB 'training_review:*:*'"
            ).fetchone()[0]
            if count >= 100:
                raise ValueError('本機介面最多登記 100 組資料；請先備份整理')
            for key in (PREFIX + uid, PREFIX + uid + ':v1'):
                db.execute(
                    'INSERT INTO settings VALUES (?,?)',
                    (key, json.dumps(value, ensure_ascii=False)),
                )
        return value

    def save(self, uid, request):
        old = self.get(uid)
        if old['revision'] != request.revision:
            raise Conflict('資料已在其他視窗更新；先保留目前編輯，再重新載入')
        if old['revision'] >= 100:
            raise ValueError('此資料集已達 100 個修訂；請另立資料集')
        document = json.loads(json.dumps(old['dataset']))
        edits = {row.id: row.model_dump(mode='json', exclude={'id'}) for row in request.images}
        if len(edits) != len(request.images) or set(edits) != {v['id'] for v in document['images']}:
            raise ValueError('圖片集合必須與匯入版本完全相同')
        for row in document['images']:
            edit = edits[row['id']]
            if not set(row['exposure']).issubset(edit['exposure']):
                raise ValueError('不可移除既有圖片曝光紀錄')
            if edit['split'] == 'test' and row['split'] != 'test':
                raise ValueError('最終評估圖須在匯入前獨立分割；審查候選不可轉為未曝光 test')
            if row['split'] in ('validation', 'test', 'excluded') and edit['split'] not in (
                row['split'],
                'excluded',
            ):
                raise ValueError('不可將保留／排除圖改為訓練來源或重新分割')
            row.update(edit)
        if request.version == document['version']:
            raise ValueError('保存需使用新的資料版本名稱')
        document['version'] = request.version
        dataset = data.Dataset.model_validate(document)
        report = self.inspect_sources(dataset, old['source_root'], old['study_json'])
        value = old | dict(
            revision=old['revision'] + 1,
            dataset=dataset.model_dump(mode='json'),
            readiness=report,
            updated_at=now(),
            manifest_sha256=data.digest(data.manifest_bytes(dataset)),
        )
        with closing(sqlite3.connect(self.host.DB)) as db, db:
            db.execute('BEGIN IMMEDIATE')
            current = json.loads(
                db.execute(
                    'SELECT value FROM settings WHERE key=?', (PREFIX + identifier(uid),)
                ).fetchone()[0]
            )
            if current['revision'] != old['revision']:
                raise Conflict('資料已在其他視窗更新；目前編輯未覆蓋其他版本')
            if db.execute(
                "SELECT 1 FROM settings WHERE key GLOB ? AND json_extract(value,'$.dataset.version')=?",
                (PREFIX + identifier(uid) + ':v*', request.version),
            ).fetchone():
                raise Conflict('此版本名稱已存在；請使用新名稱')
            raw = json.dumps(value, ensure_ascii=False)
            db.execute('UPDATE settings SET value=? WHERE key=?', (raw, PREFIX + identifier(uid)))
            db.execute(
                'INSERT INTO settings VALUES (?,?)',
                (PREFIX + identifier(uid) + f':v{value["revision"]}', raw),
            )
        return value

    def check(self, uid):
        value = self.get(uid)
        return dict(
            revision=value['revision'],
            checked_at=now(),
            **self.inspect_sources(
                data.Dataset.model_validate(value['dataset']),
                value['source_root'],
                value['study_json'],
            ),
        )

    def thumbnail(self, uid, image_id, revision):
        value = self.get(uid, revision)
        dataset = data.Dataset.model_validate(value['dataset'])
        row = next((r for r in dataset.images if r.id == image_id), None)
        if row is None:
            raise KeyError('圖片不存在')
        if row.split == 'test':
            raise Conflict('最終評估圖保留未曝光，資料審查不提供預覽')
        _, raw = data.read_source(value['source_root'], row.path, row)
        with Image.open(io.BytesIO(raw)) as source:
            image = ImageOps.exif_transpose(source).convert('RGB')
            image.thumbnail((640, 640))
            output = io.BytesIO()
            image.save(output, format='PNG')
        return output.getvalue()

    def export_status(self, request_id):
        with closing(sqlite3.connect(self.host.DB)) as db:
            row = db.execute(
                'SELECT value FROM settings WHERE key=?',
                ('training_export:' + identifier(request_id),),
            ).fetchone()
        if row is None:
            raise KeyError('找不到原匯出 UUID')
        return json.loads(row[0])

    def export(self, uid, request):
        value = self.get(uid)
        if value['revision'] != request.revision:
            raise Conflict('資料修訂已變更，請載入最新版本後再匯出')
        key = 'training_export:' + identifier(request.request_id)
        target = self.host.DATA / 'training_bundles' / identifier(request.request_id)
        result = dict(
            request_id=str(request.request_id),
            dataset_id=identifier(uid),
            revision=request.revision,
            manifest_sha256=value['manifest_sha256'],
            status='exporting',
            path=str(target),
            updated_at=now(),
        )
        with closing(sqlite3.connect(self.host.DB)) as db, db:
            db.execute('BEGIN IMMEDIATE')
            old = db.execute('SELECT value FROM settings WHERE key=?', (key,)).fetchone()
            if old:
                old = json.loads(old[0])
                if any(old[k] != result[k] for k in ('dataset_id', 'revision', 'manifest_sha256')):
                    raise Conflict('此匯出 UUID 已有不同來源')
                return old
            db.execute('INSERT INTO settings VALUES (?,?)', (key, json.dumps(result)))
        try:
            study = (
                data.parse_json(value['study_json'].encode('utf-8'))
                if value['study_json']
                else None
            )
            report = bundle.export(
                data.Dataset.model_validate(value['dataset']),
                value['source_root'],
                target,
                base(self.host.ROOT)[1],
                study,
            )
            result.update(status='completed', report=report)
        except (OSError, ValueError) as exc:
            result.update(status='failed', error=str(exc))
        result['updated_at'] = now()
        with closing(sqlite3.connect(self.host.DB)) as db, db:
            db.execute(
                'UPDATE settings SET value=? WHERE key=?',
                (json.dumps(result, ensure_ascii=False), key),
            )
        return result
