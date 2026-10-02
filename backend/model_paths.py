"""Local checkpoint directory registration and isolated ComfyUI config export.

Core helpers use only the standard library so ComfyUI's Python can export the
saved configuration without importing the platform, FastAPI, or GPU libraries.
"""
import ctypes
import json
import os
import re
import shutil
import sqlite3
import stat
import tempfile
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

KEY = 'local_checkpoint_paths'
MAX_PATHS = 8
MAX_REVISION = 9007199254740991
MANAGED_ENGINE = 'http://127.0.0.1:8188'
EXPORT_NAME = 'comfy-extra-model-paths.json'


class RevisionConflict(ValueError):
    def __init__(self, revision):
        super().__init__('目錄設定已由另一個請求更新，請重新載入後確認；未覆蓋儲存內容')
        self.revision = revision


def defaults():
    return dict(revision=0, updated_at=None, paths=[])


def validate_record(value):
    if (not isinstance(value, dict) or set(value) != {'revision', 'updated_at', 'paths'}
            or type(value.get('revision')) is not int or not 0 <= value['revision'] <= MAX_REVISION
            or not isinstance(value.get('paths'), list) or len(value['paths']) > MAX_PATHS
            or any(not isinstance(path, str) or not path or len(path) > 2048 for path in value['paths'])):
        raise ValueError('儲存的本機模型目錄設定格式無效；未更動設定或模型檔案')
    timestamp = value['updated_at']
    if timestamp is not None:
        try:
            parsed = datetime.fromisoformat(timestamp) if isinstance(timestamp, str) else None
            if parsed is None or parsed.utcoffset() is None or parsed.utcoffset().total_seconds() != 0:
                raise ValueError()
        except (TypeError, ValueError):
            raise ValueError('儲存的本機模型目錄時間格式無效；未更動設定或模型檔案')
    return value


def _read(db):
    row = db.execute('SELECT value FROM settings WHERE key=?', (KEY,)).fetchone()
    return validate_record(json.loads(row[0])) if row else defaults()


def read(db_path):
    """Read-only SQLite access never creates a database at startup."""
    path = Path(db_path)
    if not path.exists():
        return defaults()
    with closing(sqlite3.connect(path.resolve().as_uri() + '?mode=ro', uri=True)) as db:
        return _read(db)


def default_directory(workspace):
    return Path(workspace) / 'runtime' / 'ComfyUI' / 'models' / 'checkpoints'


def _local(path):
    text = str(path)
    if text.startswith(('\\\\', '//')):
        raise ValueError('不接受 UNC、網路或裝置路徑；請使用本機磁碟的絕對目錄')
    if os.name == 'nt':
        function = ctypes.windll.kernel32.GetDriveTypeW
        function.argtypes = [ctypes.c_wchar_p]
        function.restype = ctypes.c_uint
        drive_type = function(path.anchor)
        if drive_type == 4:
            raise ValueError('不接受映射網路磁碟；請使用本機磁碟目錄')
        if drive_type in (0, 1):
            raise ValueError('無法確認目錄位於有效的本機磁碟')


def canonical_directory(value, require_existing=True):
    if not isinstance(value, str) or not value or len(value) > 2048:
        raise ValueError('每個目錄必須是 1 至 2048 字元的絕對路徑')
    if any(ord(character) < 32 or 127 <= ord(character) <= 159 or character in '\u2028\u2029' for character in value):
        raise ValueError('目錄不可包含換行、NUL 或控制字元')
    if value != value.strip() or re.search(r'%[^%]+%|\$\{[^}]+\}|\$[A-Za-z_][A-Za-z0-9_]*', value) or value.startswith('~'):
        raise ValueError('請使用未加引號、不含環境變數或前後空白的完整絕對目錄')
    path = Path(value)
    if not path.is_absolute():
        raise ValueError('目錄必須是本機磁碟的絕對路徑；不接受相對或磁碟相對路徑')
    _local(path)
    try:
        path = path.resolve()
    except (OSError, RuntimeError) as exc:
        raise ValueError('無法解析目錄的實際本機路徑') from exc
    _local(path)
    if require_existing:
        try:
            if not stat.S_ISDIR(path.stat().st_mode):
                raise ValueError('指定的路徑不是目錄')
            # Open at most one entry; do not scan recursively or inspect weights.
            with os.scandir(path) as entries:
                next(entries, None)
        except FileNotFoundError as exc:
            raise ValueError('目錄不存在；請先建立或掛載本機目錄再保存') from exc
        except OSError as exc:
            raise ValueError('目錄無法讀取；請檢查權限與磁碟狀態') from exc
    return path


def validate_paths(paths, workspace):
    if not isinstance(paths, list) or len(paths) > MAX_PATHS:
        raise ValueError('最多登記 8 個額外 checkpoint 目錄')
    builtin = canonical_directory(str(default_directory(workspace)), require_existing=False)
    seen = {os.path.normcase(str(builtin))}
    result = []
    for value in paths:
        path = canonical_directory(value)
        key = os.path.normcase(str(path))
        if key in seen:
            raise ValueError('目錄解析後重複，或已是 ComfyUI 內建 checkpoint 目錄；未保存')
        seen.add(key)
        result.append(str(path))
    return result


def save(db_path, workspace, paths, expected_revision):
    if type(expected_revision) is not int or not 0 <= expected_revision < MAX_REVISION:
        raise ValueError('目錄設定 revision 必須是有效的非負整數')
    paths = validate_paths(paths, workspace)
    with closing(sqlite3.connect(db_path)) as db, db:
        db.execute('BEGIN IMMEDIATE')
        current = _read(db)
        if current['revision'] != expected_revision:
            raise RevisionConflict(current['revision'])
        value = dict(paths=paths, revision=current['revision'] + 1, updated_at=datetime.now(timezone.utc).isoformat())
        db.execute('INSERT OR REPLACE INTO settings VALUES (?, ?)', (KEY, json.dumps(value, ensure_ascii=False)))
    return value


def directory_status(value):
    result = dict(path=str(value), status='unreadable', disk=None, error=None)
    try:
        path = canonical_directory(str(value), require_existing=False)
        path.stat()
        canonical_directory(str(path))
    except FileNotFoundError:
        return result | dict(status='missing', error='目錄目前不存在；啟動前需還原或移除此登記')
    except (OSError, ValueError):
        return result | dict(error='目錄目前無法讀取，或已不符合本機目錄規則；請檢查權限與位置')
    try:
        disk = shutil.disk_usage(path)
        return result | dict(status='existing', disk=dict(total=disk.total, used=disk.used, free=disk.free))
    except OSError:
        return result | dict(status='existing', error='磁碟容量無法取得；目錄存在且可讀，不會因此禁止使用')


def status(value, workspace, selected_engine):
    return dict(scope='managed_local_comfyui', managed_engine_url=MANAGED_ENGINE, selected_engine_url=selected_engine,
                **value, default_directory=directory_status(default_directory(workspace)),
                directories=[directory_status(path) for path in value['paths']],
                application_status='unverified', restart_required=True,
                warnings=['此設定僅供本專案 runtime/ComfyUI 與固定 8188 啟動腳本使用，不會更動目前選取的遠端引擎檔案系統。',
                          '保存後需手動重新啟動本機 ComfyUI，再同步模型庫；目前未驗證執行中的引擎是否已載入此設定。',
                          '額外目錄依保存順序附加；同一相對檔名可能被先前目錄遮蔽，模型清單不提供完整來源路徑或檔案驗證。'])


def _export_path(workspace):
    root = Path(workspace).resolve()
    target = root / 'runtime' / EXPORT_NAME
    for part in (target, *target.parents):
        if part == root:
            break
        if part.is_symlink() or (hasattr(part, 'is_junction') and part.is_junction()):
            raise ValueError('匯出設定的 runtime 路徑不可是符號連結或 junction')
    resolved = target.resolve()
    if not resolved.is_relative_to(root / 'runtime'):
        raise ValueError('匯出設定必須留在本專案 runtime 目錄')
    return resolved


def export(db_path, workspace):
    value = read(db_path)
    paths = validate_paths(value['paths'], workspace)
    config = {'model_atelier': dict(is_default=False, checkpoints='\n'.join(paths))} if paths else {}
    target = _export_path(workspace)
    target.parent.mkdir(parents=True, exist_ok=True)
    target = _export_path(workspace)
    temp_name = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=target.parent,
                                         prefix='comfy-extra-model-paths.', suffix='.tmp', delete=False) as stream:
            temp_name = Path(stream.name)
            json.dump(config, stream, ensure_ascii=False, indent=2, allow_nan=False)
            stream.write('\n')
            stream.flush()
            os.fsync(stream.fileno())
        if temp_name.is_symlink() or not temp_name.resolve().is_relative_to(Path(workspace).resolve() / 'runtime'):
            raise ValueError('匯出暫存檔超出本專案 runtime 目錄')
        os.replace(temp_name, _export_path(workspace))
    finally:
        if temp_name is not None and temp_name.exists() and temp_name.resolve().is_relative_to(Path(workspace).resolve() / 'runtime'):
            temp_name.unlink()
    return target


def install(app, host):
    from fastapi import HTTPException
    from pydantic import BaseModel, Field, StrictStr

    class PathsInput(BaseModel):
        revision: int = Field(strict=True, ge=0, lt=MAX_REVISION)
        paths: list[StrictStr] = Field(max_length=MAX_PATHS)

    @app.get('/api/local-model-paths')
    def get_paths():
        try:
            return status(read(host.DB), host.ROOT, host.engine_url())
        except (ValueError, sqlite3.Error):
            raise HTTPException(422, '儲存的本機模型目錄設定無法讀取；未更動任何設定或模型檔案')

    @app.put('/api/local-model-paths')
    def put_paths(value: PathsInput):
        try:
            saved = save(host.DB, host.ROOT, value.paths, value.revision)
            return status(saved, host.ROOT, host.engine_url())
        except RevisionConflict as exc:
            raise HTTPException(409, dict(code='revision_conflict', message=str(exc), current_revision=exc.revision))
        except ValueError as exc:
            raise HTTPException(422, str(exc))
        except sqlite3.Error:
            raise HTTPException(500, '本機目錄設定保存失敗；請檢查平台資料庫狀態，未更動模型檔案')
