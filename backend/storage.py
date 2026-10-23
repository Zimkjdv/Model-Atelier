"""Directory volume inventory and explicit local folder opening; no recursive scans."""

import ctypes
import hashlib
import ipaddress
import os
import shutil
import sqlite3
from pathlib import Path
from urllib.parse import urlsplit

from fastapi import HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field
from backend import environment, model_paths


class OpenDirectory(BaseModel):
    model_config = ConfigDict(extra='forbid')
    directory_id: str = Field(min_length=1, max_length=80)
    expected_path: str = Field(min_length=1, max_length=2048)


def folder_open_supported():
    return os.name == 'nt' and hasattr(os, 'startfile')


def directories(root, data, db):
    entries = [
        ('data', '平台資料', data),
        ('assets', '參考素材', data / 'assets'),
        ('artworks', '作品庫輸出', data / 'artworks'),
        ('checkpoints', '受管理本機 checkpoint', model_paths.default_directory(root)),
        ('comfy-output', '受管理本機 ComfyUI 輸出', root / 'runtime' / 'ComfyUI' / 'output'),
    ]
    invalid = False
    try:
        for path in model_paths.read(db)['paths']:
            identifier = 'extra-' + hashlib.sha256(path.encode('utf-8')).hexdigest()
            entries.append((identifier, '額外本機 checkpoint', Path(path)))
    except (OSError, ValueError, sqlite3.Error):
        invalid = True
    return entries, invalid


def require_local_request(request):
    def loopback(host):
        if host == 'localhost':
            return True
        try:
            return ipaddress.ip_address(host).is_loopback
        except ValueError:
            return False

    if (
        not request.client
        or not loopback(request.client.host)
        or not loopback(request.url.hostname or '')
    ):
        raise HTTPException(403, '請從平台主機的本機瀏覽器開啟資料夾。')
    origin = request.headers.get('origin')
    if origin:
        try:
            source = urlsplit(origin)
            target = urlsplit(str(request.base_url))
            if (
                (source.scheme, source.netloc.lower(), source.path)
                not in (
                    (target.scheme, target.netloc.lower(), ''),
                    (target.scheme, target.netloc.lower(), '/'),
                )
                or source.query
                or source.fragment
            ):
                raise ValueError()
        except ValueError:
            raise HTTPException(403, '資料夾開啟要求必須來自目前平台頁面。') from None
    if request.headers.get('sec-fetch-site') == 'cross-site':
        raise HTTPException(403, '資料夾開啟要求必須來自目前平台頁面。')
    if request.headers.get('content-type', '').split(';')[0].strip().lower() != 'application/json':
        raise HTTPException(415, '資料夾開啟要求必須使用 JSON。')


def volume_identity(path):
    if os.name != 'nt':
        return str(path.stat().st_dev), str(path.anchor)
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    root = ctypes.create_unicode_buffer(32768)
    get_path = kernel.GetVolumePathNameW
    get_path.argtypes = [ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_uint32]
    get_path.restype = ctypes.c_int
    if not get_path(str(path), root, len(root)):
        raise OSError('Volume path unavailable')
    name = ctypes.create_unicode_buffer(1024)
    get_name = kernel.GetVolumeNameForVolumeMountPointW
    get_name.argtypes = [ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_uint32]
    get_name.restype = ctypes.c_int
    if not get_name(root.value, name, len(name)):
        raise OSError('Volume identity unavailable')
    return name.value.casefold(), root.value


def inventory(directories):
    entries, volumes = [], {}
    for role, path in directories:
        entry = dict(
            role=role,
            path=str(path),
            resolved_path=None,
            volume_id=None,
            status='unknown',
            error=None,
        )
        entries.append(entry)
        try:
            if not Path(path).is_absolute():
                raise ValueError('Absolute path required')
            resolved = model_paths.canonical_directory(str(path), require_existing=False).resolve(
                strict=True
            )
            if not resolved.is_dir():
                raise NotADirectoryError()
            with os.scandir(resolved):
                pass
            entry['resolved_path'] = str(resolved)
            identity, label = volume_identity(resolved)
            entry['volume_id'] = identity
            if identity not in volumes:
                volume = dict(
                    id=identity, path=label, total=None, used=None, free=None, status='unknown'
                )
                volumes[identity] = volume
                try:
                    usage = shutil.disk_usage(resolved)
                    if (
                        any(type(v) is not int or v < 0 for v in usage)
                        or usage.total <= 0
                        or usage.used > usage.total
                        or usage.free > usage.total
                        or usage.used + usage.free > usage.total
                    ):
                        raise ValueError('Invalid disk capacity')
                    volume.update(
                        total=usage.total, used=usage.used, free=usage.free, status='available'
                    )
                except (OSError, ValueError):
                    pass
            entry['status'] = volumes[identity]['status']
            if entry['status'] != 'available':
                entry['error'] = '磁碟容量無法取得'
        except FileNotFoundError:
            entry.update(status='missing', error='目錄尚不存在，容量未知')
        except (OSError, ValueError, RuntimeError):
            entry.update(error='目錄不可讀或無法辨識實際磁碟區，容量未知')
    known = [v for v in volumes.values() if v['status'] == 'available']
    return dict(
        directories=entries,
        volumes=list(volumes.values()),
        totals=dict(
            total=sum(v['total'] for v in known) if known else None,
            free=sum(v['free'] for v in known) if known else None,
            volume_count=len(known),
            partial=any(e['status'] != 'available' for e in entries),
        ),
    )


def report(root, data, db, engine_url):
    registered, invalid_registry = directories(root, data, db)
    warnings = [
        '容量指目錄所在磁碟區的整體容量，不是資料夾大小；同一磁碟區只加總一次。',
        '只讀取平台及本專案管理的本機路徑；遠端引擎、自訂啟動輸出路徑與手動 YAML 目錄不在此清單內。',
    ]
    if invalid_registry:
        warnings.append('額外模型目錄設定無法讀取，此次清單不完整。')
    result = inventory([(role, path) for _, role, path in registered])
    supported = folder_open_supported()
    for entry, (identifier, _, _) in zip(result['directories'], registered):
        entry.update(id=identifier, can_open=supported and entry['resolved_path'] is not None)
    result['totals']['partial'] |= invalid_registry
    return dict(
        **result,
        scope='platform_and_managed_local_paths',
        selected_engine_url=engine_url,
        checked_at=environment.now(),
        warnings=warnings,
        folder_open_supported=supported,
    )


def install(app, host):
    @app.get('/api/storage')
    def get_storage():
        return report(host.ROOT, host.DATA, host.DB, host.engine_url())

    @app.post('/api/storage/open-directory')
    def open_directory(body: OpenDirectory, request: Request):
        require_local_request(request)
        if not folder_open_supported():
            raise HTTPException(501, '開啟資料夾目前僅支援 Windows 本機平台。')
        registered, _ = directories(host.ROOT, host.DATA, host.DB)
        target = next(
            (path for identifier, _, path in registered if identifier == body.directory_id), None
        )
        if target is None:
            raise HTTPException(404, '此目錄已不在清單中，請更新目錄資訊。')
        try:
            resolved = model_paths.canonical_directory(str(target))
        except (OSError, ValueError, RuntimeError):
            raise HTTPException(409, '目錄不存在或無法讀取，請更新目錄資訊後重試。') from None
        if str(resolved) != body.expected_path:
            raise HTTPException(409, '目錄位置已變更，請更新目錄資訊後重試。')
        try:
            os.startfile(str(resolved), 'open')
        except OSError:
            raise HTTPException(503, '檔案總管無法開啟此目錄，請檢查權限後重試。') from None
        return dict(opened=True, directory_id=body.directory_id)
