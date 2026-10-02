"""Directory volume inventory; no recursive scans, file writes or remote inference."""
import ctypes
import os
import shutil
import sqlite3
from pathlib import Path
from backend import environment, model_paths


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
        entry = dict(role=role, path=str(path), resolved_path=None, volume_id=None, status='unknown', error=None)
        entries.append(entry)
        try:
            if not Path(path).is_absolute():
                raise ValueError('Absolute path required')
            resolved = Path(path).resolve(strict=True)
            if not resolved.is_dir():
                raise NotADirectoryError()
            with os.scandir(resolved):
                pass
            entry['resolved_path'] = str(resolved)
            identity, label = volume_identity(resolved)
            entry['volume_id'] = identity
            if identity not in volumes:
                volume = dict(id=identity, path=label, total=None, used=None, free=None, status='unknown')
                volumes[identity] = volume
                try:
                    usage = shutil.disk_usage(resolved)
                    if (any(type(v) is not int or v < 0 for v in usage) or usage.total <= 0
                            or usage.used > usage.total or usage.free > usage.total
                            or usage.used + usage.free > usage.total):
                        raise ValueError('Invalid disk capacity')
                    volume.update(total=usage.total, used=usage.used, free=usage.free, status='available')
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
    return dict(directories=entries, volumes=list(volumes.values()),
                totals=dict(total=sum(v['total'] for v in known) if known else None,
                            free=sum(v['free'] for v in known) if known else None,
                            volume_count=len(known), partial=any(e['status'] != 'available' for e in entries)))


def report(root, data, db, engine_url):
    directories = [('平台資料', data), ('參考素材', data / 'assets'), ('作品庫輸出', data / 'artworks'),
                   ('受管理本機 checkpoint', model_paths.default_directory(root)),
                   ('受管理本機 ComfyUI 輸出', root / 'runtime' / 'ComfyUI' / 'output')]
    warnings = ['容量指目錄所在磁碟區的整體容量，不是資料夾大小；同一磁碟區只加總一次。',
                '只讀取平台及本專案管理的本機路徑；遠端引擎、自訂啟動輸出路徑與手動 YAML 目錄不在此清單內。']
    invalid_registry = False
    try:
        directories.extend(('額外本機 checkpoint', Path(p)) for p in model_paths.read(db)['paths'])
    except (OSError, ValueError, sqlite3.Error):
        invalid_registry = True
        warnings.append('額外模型目錄設定無法讀取，此次清單不完整。')
    result = inventory(directories)
    result['totals']['partial'] |= invalid_registry
    return dict(**result, scope='platform_and_managed_local_paths', selected_engine_url=engine_url,
                checked_at=environment.now(), warnings=warnings)


def install(app, host):
    @app.get('/api/storage')
    def get_storage():
        return report(host.ROOT, host.DATA, host.DB, host.engine_url())
