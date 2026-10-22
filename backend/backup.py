"""Offline, complete DATA backups. Never repair, delete, or overwrite user data."""
from contextlib import closing, contextmanager
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import sqlite3
import stat

from backend.data_lease import DataLease

VERSION = 1
INCOMPLETE = '.incomplete'
MANIFEST_LIMIT = 32 * 1024**2
MAX_FILES = 100000


class BackupError(ValueError):
    pass


def relative_name(raw):
    if not isinstance(raw, str) or not raw or len(raw) > 4096 or '\\' in raw or ':' in raw or '\x00' in raw:
        raise BackupError('備份包含不安全路徑')
    value = PurePosixPath(raw)
    if value.is_absolute() or str(value) != raw or any(part in ('', '.', '..') or part.endswith((' ', '.')) or
            re.fullmatch(r'(?i)(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\..*)?', part) for part in value.parts):
        raise BackupError('備份包含不安全路徑')
    return value


def regular(path, *, directory=False):
    info = path.lstat()
    if stat.S_ISLNK(info.st_mode) or getattr(info, 'st_file_attributes', 0) & getattr(stat, 'FILE_ATTRIBUTE_REPARSE_POINT', 1024):
        raise BackupError('不接受 symlink、junction 或外部重解析目錄')
    if not (stat.S_ISDIR(info.st_mode) if directory else stat.S_ISREG(info.st_mode)):
        raise BackupError('備份只接受一般目錄與檔案')
    return info


def checksum(path):
    before = regular(path)
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        while chunk := stream.read(1024**2):
            digest.update(chunk)
    after = regular(path)
    if (before.st_size, before.st_mtime_ns, before.st_ino) != (after.st_size, after.st_mtime_ns, after.st_ino):
        raise BackupError('檔案於檢查期間變動；請停止所有寫入再重試')
    return dict(size=after.st_size, sha256=digest.hexdigest())


def tree(root, prefix):
    regular(root, directory=True)
    files, directories = {}, [prefix]
    for folder, dirs, names in os.walk(root, followlinks=False):
        folder = Path(folder)
        for name in sorted(dirs):
            target = folder / name
            regular(target, directory=True)
            key = prefix + '/' + target.relative_to(root).as_posix()
            relative_name(key); directories.append(key)
        for name in sorted(names):
            target = folder / name
            key = prefix + '/' + target.relative_to(root).as_posix()
            relative_name(key); files[key] = checksum(target)
            if len(files) > MAX_FILES:
                raise BackupError('檔案數超過 100,000；請另行規劃備份')
    return files, directories


def database_path(data, database=None):
    source = Path(data)
    regular(source, directory=True)
    data = source.resolve()
    database = Path(database).resolve() if database is not None else data / 'atelier.sqlite3'
    regular(database)
    return data, database


def no_sidecars(database):
    for suffix in ('-wal', '-shm', '-journal'):
        path = Path(str(database) + suffix)
        if path.exists() and path.stat().st_size:
            raise BackupError('SQLite 尚有 WAL／journal；請正常停止平台並完成資料庫關閉，不自動 checkpoint 或修復')


@contextmanager
def stopped(data, database, *, exclusive):
    with DataLease([data, database], maintenance=True):
        no_sidecars(database)
        uri = database.as_uri() + ('?mode=rw' if exclusive else '?mode=ro')
        with closing(sqlite3.connect(uri, uri=True, timeout=0)) as db:
            try:
                db.execute('BEGIN EXCLUSIVE' if exclusive else 'BEGIN')
                no_sidecars(database)
                if db.execute('PRAGMA quick_check').fetchone() != ('ok',):
                    raise BackupError('SQLite 健全性檢查失敗，保留原資料')
                yield db
            except sqlite3.Error as exc:
                raise BackupError('SQLite 無法取得一致讀取；請停機並檢查資料庫') from exc
            finally:
                db.rollback()


def inspect_records(db, files, database_key):
    counts, problems = {}, []
    assets, job_ids = {}, set()
    kinds = ('asset', 'artwork', 'job', 'draft', 'flux_draft', 'experiment', 'control_edge')
    def problem(code, key):
        if len(problems) < 1000:
            problems.append(dict(code=code, record=str(key)[:256]))
    def records():
        for key, raw in db.execute('SELECT key,value FROM settings ORDER BY key'):
            prefix = key.split(':', 1)[0]
            if prefix not in kinds:
                continue
            try:
                value = json.loads(raw)
                if not isinstance(value, dict):
                    raise ValueError()
            except (ValueError, TypeError):
                value = None
            yield prefix, key, value
    for prefix, key, value in records():
        counts[prefix] = counts.get(prefix, 0) + 1
        if value is None:
            problem('invalid_record_json', key); continue
        identifier = value.get('id', value.get('job_id', ''))
        if not isinstance(identifier, str) or not identifier:
            problem('invalid_identifier', key); continue
        if prefix == 'asset':
            assets[identifier] = value.get('sha256')
        if prefix == 'job':
            job_ids.add(identifier)

    def expected(name, digest=None, size=None, *, owner):
        try:
            relative_name(name)
        except BackupError:
            problem('unsafe_record_path', owner); return
        item = files.get(name)
        if item is None:
            problem('missing_file', name)
        elif (digest is not None and item['sha256'] != digest) or (size is not None and item['size'] != size):
            problem('record_hash_or_size_mismatch', name)

    for kind, key, value in records():
        if value is None:
            continue
        identifier = value.get('id', value.get('job_id', ''))
        if not isinstance(identifier, str):
            problem('invalid_identifier', key); continue
        if kind == 'asset':
            expected(f'data/assets/{identifier}.png', value.get('sha256'), value.get('size'), owner=key)
        elif kind == 'artwork':
            extension = value.get('extension', '')
            expected(f'data/artworks/{identifier}.{extension}', value.get('sha256'), value.get('size'), owner=key)
            expected(f'data/artworks/{identifier}.thumb.png', owner=key)
        elif kind == 'control_edge':
            expected(f'data/control_edges/{identifier}.png', value.get('sha256'), value.get('size_bytes'), owner=key)
        refs = value.get('reference_metadata') or []
        if not isinstance(refs, list) or any(not isinstance(ref, dict) for ref in refs):
            problem('invalid_references', key); refs = []
        for reference in refs:
            asset_id = reference.get('id')
            if not isinstance(asset_id, str) or asset_id not in assets:
                problem('missing_reference_record', key)
            elif reference.get('sha256') and reference['sha256'] != assets[asset_id]:
                problem('reference_snapshot_mismatch', key)
        reference_owner = value.get('plan', {}).get('baseline', {}) if kind == 'experiment' and isinstance(value.get('plan'), dict) else value
        ids = reference_owner.get('reference_ids', []) if isinstance(reference_owner, dict) else None
        if not isinstance(ids, list) or any(not isinstance(item, str) or item not in assets for item in ids):
            problem('missing_reference_record', key)
        if kind in ('artwork', 'control_edge') and (not isinstance(value.get('job_id'), str) or value.get('job_id') not in job_ids):
            problem('missing_original_job', key)
        if kind == 'job' and (value.get('input_upload') or value.get('input_uploads') or value.get('status') in ('queued', 'running', 'completed', 'stopped')):
            for reference in refs:
                prep = reference.get('generation_preprocessing')
                if not isinstance(prep, dict):
                    continue
                role = reference.get('input_role', 'source')
                suffix = '.mask.png' if role == 'mask' else '.png'
                expected(f'data/job_inputs/{identifier}{suffix}', prep.get('sha256'), prep.get('size'), owner=key)
                blend = reference.get('blend_preprocessing')
                if isinstance(blend, dict):
                    expected(f'data/job_inputs/{identifier}.blend.png', blend.get('sha256'), blend.get('size'), owner=key)
    return dict(ok=not problems, counts=counts, problems=problems, database=database_key)


def inventory(data, database, db, evidence=()):
    files, directories = tree(data, 'data')
    database_key = 'data/' + database.relative_to(data).as_posix() if database.is_relative_to(data) else 'database/atelier.sqlite3'
    if not database.is_relative_to(data):
        files[database_key] = checksum(database); directories.append('database')
    sources = {'data': data}
    for index, raw in enumerate(evidence):
        source = Path(raw)
        prefix = f'evidence/{index:03d}'
        if source.is_dir():
            entries, folders = tree(source, prefix)
        else:
            relative_name(source.name)
            entries, folders = {prefix + '/' + source.name: checksum(source)}, [prefix]
        files.update(entries); directories.extend(folders); sources[prefix] = source.resolve()
    if evidence:
        directories.append('evidence')
    report = inspect_records(db, files, database_key)
    return dict(schema_version=VERSION, database=database_key, files=dict(sorted(files.items())),
                directories=sorted(set(directories)), inspection=report), sources


def inspect(data, database=None):
    data, database = database_path(data, database)
    with stopped(data, database, exclusive=False) as db:
        manifest, _ = inventory(data, database, db)
    return manifest['inspection'] | dict(file_count=len(manifest['files']), total_bytes=sum(v['size'] for v in manifest['files'].values()))


def prepare_destination(destination, manifest, source_roots):
    raw = Path(destination)
    if raw.exists() or raw.is_symlink():
        raise BackupError('目的地已存在；只接受新的目錄，不覆寫原資料')
    parent = raw.parent.resolve(strict=True)
    target = parent / raw.name
    for source in source_roots:
        if target == source or target.is_relative_to(source):
            raise BackupError('目的地不可位於來源內')
    size = sum(item['size'] for item in manifest['files'].values()) + MANIFEST_LIMIT
    if shutil.disk_usage(parent).free < size:
        raise BackupError('可用空間不足；未建立目的地或修改原資料')
    target.mkdir(exist_ok=False)
    (target / INCOMPLETE).write_text('Incomplete operation; never use this directory as a backup or active DATA.\n', encoding='utf-8')
    return target


def copy_checked(source, target, metadata):
    regular(source)
    target.parent.mkdir(parents=True, exist_ok=True)
    with source.open('rb') as src, target.open('xb') as dst:
        shutil.copyfileobj(src, dst, 1024**2)
        dst.flush(); os.fsync(dst.fileno())
    if checksum(target) != metadata:
        raise BackupError('複製後 hash 不符；目的地保持 incomplete，原資料保留')


def backup(data, destination, *, database=None, platform_stopped=False, evidence=()):
    if not platform_stopped:
        raise BackupError('請先停止所有平台／寫入者，再明確指定 --platform-stopped；不提供線上備份')
    data, database = database_path(data, database)
    with stopped(data, database, exclusive=True) as db:
        manifest, sources = inventory(data, database, db, evidence)
        if not manifest['inspection']['ok']:
            raise BackupError('資料有缺檔或紀錄不一致；請先執行 check 檢視，不建立不完整備份')
        target = prepare_destination(destination, manifest, [data, *sources.values()])
        try:
            for folder in manifest['directories']:
                (target / folder).mkdir(parents=True, exist_ok=True)
            for name, metadata in manifest['files'].items():
                if name == 'database/atelier.sqlite3':
                    source = database
                elif name.startswith('data/'):
                    source = data / name[5:]
                else:
                    prefix = '/'.join(name.split('/')[:2]); root = sources[prefix]
                    source = root / '/'.join(name.split('/')[2:]) if root.is_dir() else root
                copy_checked(source, target / name, metadata)
            after, _ = inventory(data, database, db, evidence)
            if after != manifest:
                raise BackupError('來源於備份期間變動；目的地保持 incomplete，請停機再重試')
            manifest['created_at'] = datetime.now(timezone.utc).isoformat()
            encoded = json.dumps(manifest, ensure_ascii=False, indent=2).encode('utf-8')
            if len(encoded) > MANIFEST_LIMIT:
                raise BackupError('manifest 過大，目的地保持 incomplete')
            with (target / 'manifest.json').open('xb') as stream:
                stream.write(encoded); stream.flush(); os.fsync(stream.fileno())
            (target / INCOMPLETE).unlink()
        except BaseException as exc:
            reason = '可用空間不足' if isinstance(exc, OSError) and exc.errno == 28 else str(exc)
            raise BackupError(f'備份未完成（{reason}）；目的地保留 incomplete，不可使用：{target}') from exc
    return dict(ok=True, destination=str(target), inspection=manifest['inspection'], files=len(manifest['files']))


def verify(archive):
    root = Path(archive)
    regular(root, directory=True)
    if (root / INCOMPLETE).exists():
        raise BackupError('備份仍為 incomplete，拒絕還原')
    path = root / 'manifest.json'
    if regular(path).st_size > MANIFEST_LIMIT:
        raise BackupError('manifest 過大')
    try:
        manifest = json.loads(path.read_text(encoding='utf-8'))
        if manifest['schema_version'] != VERSION or not isinstance(manifest['files'], dict) or len(manifest['files']) > MAX_FILES:
            raise BackupError('不支援的 manifest')
        seen = set()
        for name, info in manifest['files'].items():
            relative_name(name)
            if not name.startswith(('data/', 'database/', 'evidence/')) or name.casefold() in seen:
                raise BackupError('manifest 路徑重複或超出範圍')
            seen.add(name.casefold())
            if type(info['size']) is not int or info['size'] < 0 or not re.fullmatch('[0-9a-f]{64}', info['sha256']):
                raise BackupError('manifest hash／大小無效')
            if checksum(root / name) != info:
                raise BackupError('備份缺檔或 SHA256／大小不符')
        if manifest['database'] not in manifest['files'] or not manifest['database'].startswith(('data/', 'database/')):
            raise BackupError('manifest 資料庫位置無效')
        if not isinstance(manifest['directories'], list):
            raise BackupError('manifest 目錄清單無效')
        for folder in manifest['directories']:
            relative_name(folder)
            if folder.split('/')[0] not in ('data', 'database', 'evidence'):
                raise BackupError('manifest 目錄超出範圍')
            regular(root / folder, directory=True)
        actual, _ = tree(root, 'archive')
        if {name[len('archive/'):] for name in actual} != set(manifest['files']) | {'manifest.json'}:
            raise BackupError('備份內有未登記檔案')
    except (KeyError, TypeError, json.JSONDecodeError) as exc:
        raise BackupError('manifest 格式損壞') from exc
    return manifest


def restore(archive, destination):
    archive = Path(archive).resolve()
    manifest = verify(archive)
    target = prepare_destination(destination, manifest, [archive])
    try:
        for folder in manifest['directories']:
            (target / folder).mkdir(parents=True, exist_ok=True)
        for name, metadata in manifest['files'].items():
            copy_checked(archive / name, target / name, metadata)
        database = target / manifest['database']
        report = inspect(target / 'data', database)
        if not report['ok'] or report['counts'] != manifest['inspection']['counts']:
            raise BackupError('還原後資料健全性或數量不同')
        copy_checked(archive / 'manifest.json', target / 'backup-manifest.json', checksum(archive / 'manifest.json'))
        (target / INCOMPLETE).unlink()
    except BaseException as exc:
        reason = '可用空間不足' if isinstance(exc, OSError) and exc.errno == 28 else str(exc)
        raise BackupError(f'還原未完成（{reason}）；新目錄保留 incomplete，不切換原資料：{target}') from exc
    return dict(ok=True, destination=str(target), data=str(target / 'data'), database=str(database), inspection=report)
