"""Source-scoped runtime diagnostics without model loading or implicit probes."""
import copy
import json
import math
import os
import subprocess
import threading
from datetime import datetime, timezone
from pathlib import Path

MAX_NUMBER = 9007199254740991
MAX_DEVICES = 16
MAX_OUTPUT = 64 * 1024
PROBE_TIMEOUT = 20
LOCAL_SOURCE = '本專案 ComfyUI Python'


def now():
    return datetime.now(timezone.utc).isoformat()


def text(value, limit=240):
    if (not isinstance(value, str) or not value.strip() or len(value) > limit
            or any(ord(c) < 32 or 127 <= ord(c) <= 159 or c in '\u2028\u2029' for c in value)
            or 'traceback' in value.casefold()):
        return None
    return value.strip()


def number(value, positive=False):
    if type(value) not in (int, float) or not 0 <= value <= MAX_NUMBER:
        return None
    if not math.isfinite(value) or (positive and value == 0):
        return None
    return value


def memory(total=None, free=None):
    total = number(total, positive=True)
    free = number(free) if total is not None else None
    if free is not None and free > total:
        free = None
    return dict(total=total, free=free, used=total - free if total is not None and free is not None else None)


def safe_stats(value, depth=0):
    """Keep compatible JSON fields while dropping unsafe or unbounded values."""
    if depth > 8:
        return None
    if value is None or type(value) is bool:
        return value
    if isinstance(value, str):
        return text(value, 512) if value else ''
    if type(value) in (int, float):
        return number(value)
    if isinstance(value, list):
        return [safe_stats(item, depth + 1) for item in value[:64]]
    if isinstance(value, dict):
        return {key: safe_stats(item, depth + 1) for key, item in list(value.items())[:128]
                if text(key, 200) is not None and key.casefold() not in ('traceback', 'exception_message', 'current_inputs')}
    return None


def compatible_stats(stats):
    system_fields = {'os', 'ram_total', 'ram_free', 'comfyui_version', 'python_version', 'pytorch_version',
                     'required_frontend_version', 'installed_templates_version', 'required_templates_version',
                     'comfy_package_versions', 'embedded_python', 'deploy_environment'}
    device_fields = {'name', 'type', 'index', 'vram_total', 'vram_free', 'torch_vram_total', 'torch_vram_free'}
    return dict(system=safe_stats({key: value for key, value in stats['system'].items() if key in system_fields}),
                devices=[safe_stats({key: value for key, value in device.items() if key in device_fields})
                         for device in stats['devices'][:MAX_DEVICES] if isinstance(device, dict)])


def engine_diagnostics(stats=None, status='available'):
    report = dict(scope='selected_engine', source='ComfyUI /system_stats', checked_at=now(), status=status,
                  system=dict(os=None, python=None, pytorch=None, comfyui=None, cuda_runtime=None, cuda_available=None, driver=None),
                  ram=memory(), devices=[], warnings=[])
    if status != 'available':
        report['warnings'] = ['無法取得目前選取引擎的有效系統資訊；CUDA、驅動與裝置資訊保持未知，不以平台主機資訊替代。']
        return report
    if not isinstance(stats, dict) or not isinstance(stats.get('system'), dict) or not isinstance(stats.get('devices'), list):
        return engine_diagnostics(status='invalid')
    source = stats['system']
    report['system'].update(os=text(source.get('os')), python=text(source.get('python_version')),
                            pytorch=text(source.get('pytorch_version')), comfyui=text(source.get('comfyui_version')))
    report['ram'] = memory(source.get('ram_total'), source.get('ram_free'))
    for device in stats['devices'][:MAX_DEVICES]:
        if not isinstance(device, dict):
            continue
        index = device.get('index')
        report['devices'].append(dict(name=text(device.get('name')), type=text(device.get('type'), 40),
                                      index=index if type(index) is int and number(index) is not None else None,
                                      vram=memory(device.get('vram_total'), device.get('vram_free')),
                                      torch_vram=memory(device.get('torch_vram_total'), device.get('torch_vram_free'))))
    report['warnings'] = ['此資料僅來自選取引擎的 /system_stats；該來源未提供可靠的 CUDA Runtime、CUDA 可用性或 NVIDIA 驅動資訊，保持未知。',
                          '顯存數字是引擎回報值，可能包含可回收快取；不是平台主機 nvidia-smi 的即時數字，也不代表特定模型可執行。']
    if len(stats['devices']) > MAX_DEVICES:
        report['warnings'].append('裝置清單超出顯示上限，目前最多顯示 16 個裝置。')
    return report


def scoped_engine_diagnostics(stats, requested_url, selected_url, status='available'):
    matches = requested_url == selected_url
    report = engine_diagnostics(stats if matches else None, status if matches else 'invalid')
    report.update(engine_url=requested_url, selected_engine_url=selected_url, matches_selected_engine=matches)
    if not matches:
        report['warnings'].append('查詢期間引擎設定已變更，請重新整理；回應位址仍保留原來源，不顯示舊引擎裝置作為新引擎資訊。')
    return report


def local_identity(root):
    workspace = Path(root).resolve()
    python = workspace / 'runtime' / 'ComfyUI' / '.venv' / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
    script = workspace / 'scripts' / 'check_local_environment.py'
    return workspace, python, script


def local_report(root, status='not_checked', checked_at=None, warnings=None):
    _, python, _ = local_identity(root)
    return dict(scope='managed_local_comfyui', source=LOCAL_SOURCE, python_path=str(python), checked_at=checked_at, status=status,
                system=dict(python=None, pytorch=None, cuda_runtime=None, cuda_available=None, driver=None),
                devices=[], warnings=list(warnings or []))


def normalize_probe(root, payload):
    report = local_report(root, status='unavailable', checked_at=now(),
                          warnings=['本機 Python 檢查未取得有效的診斷資料；未啟動引擎、載入模型或生成圖片。'])
    _, python, _ = local_identity(root)
    if (not isinstance(payload, dict) or type(payload.get('schema_version')) is not int or payload['schema_version'] != 1
            or payload.get('status') not in ('available', 'unavailable') or not isinstance(payload.get('system'), dict)
            or not isinstance(payload.get('devices'), list) or not isinstance(payload.get('python_path'), str)):
        return report
    try:
        if os.path.normcase(str(Path(payload['python_path']).resolve())) != os.path.normcase(str(python.resolve())):
            return report
    except (OSError, ValueError, RuntimeError):
        return report
    system = payload['system']
    report['status'] = payload['status']
    report['system'] = dict(python=text(system.get('python')), pytorch=text(system.get('pytorch')),
                            cuda_runtime=text(system.get('cuda_runtime'), 80),
                            cuda_available=system.get('cuda_available') if type(system.get('cuda_available')) is bool else None,
                            driver=text(system.get('driver'), 80))
    if report['status'] == 'available':
        for device in payload['devices'][:MAX_DEVICES]:
            if not isinstance(device, dict):
                continue
            index = device.get('index')
            vram = device.get('vram') if isinstance(device.get('vram'), dict) else {}
            torch_vram = device.get('torch_vram') if isinstance(device.get('torch_vram'), dict) else {}
            report['devices'].append(dict(name=text(device.get('name')), type=text(device.get('type'), 40),
                                          index=index if type(index) is int and number(index) is not None else None,
                                          vram=memory(vram.get('total'), vram.get('free')),
                                          torch_vram=memory(torch_vram.get('total'), torch_vram.get('free'))))
    report['warnings'] = ['此檢查只使用本專案 ComfyUI Python；不代表目前選取的遠端引擎，也不保證所有模型可執行。',
                          'CUDA Runtime 欄位來自 PyTorch 的 CUDA 建置版本，不能當作系統 CUDA Toolkit 版本；驅動欄位另由本機 nvidia-smi 查詢。']
    warning_list = payload.get('warnings')
    if isinstance(warning_list, list):
        report['warnings'].extend(value for raw in warning_list[:8] if (value := text(raw)) is not None)
    return report


def bounded_process(command):
    """Bound output while waiting, kill/reap on timeout, never expose stderr."""
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, bufsize=0,
                               creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
    output = []
    overflow = threading.Event()
    def read_output():
        chunks = []
        remaining = MAX_OUTPUT + 1
        try:
            while remaining > 0:
                chunk = process.stdout.read(min(8192, remaining))
                if not chunk:
                    break
                chunks.append(chunk)
                remaining -= len(chunk)
            if remaining == 0:
                overflow.set()
                process.kill()
        except OSError:
            pass
        finally:
            output.append(b''.join(chunks))
    reader = threading.Thread(target=read_output, daemon=True)
    reader.start()
    timed_out = False
    try:
        try:
            process.wait(timeout=PROBE_TIMEOUT)
        except subprocess.TimeoutExpired:
            timed_out = True
            process.kill()
            process.wait(timeout=5)
        reader.join(timeout=2)
        if reader.is_alive():
            process.stdout.close()
            reader.join(timeout=2)
            return 'invalid', None
        if timed_out:
            return 'timeout', None
        if overflow.is_set() or process.returncode != 0:
            return 'invalid', None
        return 'ok', output[0] if output else b''
    finally:
        if process.poll() is None:
            process.kill()
            process.wait(timeout=5)
        process.stdout.close()


def probe_local(root):
    _, python, script = local_identity(root)
    if not python.is_file() or not script.is_file():
        return local_report(root, status='unavailable', checked_at=now(),
                            warnings=['本專案 ComfyUI Python 環境或固定診斷腳本尚未安裝；未啟動任何引擎或模型。'])
    try:
        outcome, output = bounded_process([str(python), '-I', str(script)])
        if outcome == 'timeout':
            return local_report(root, status='timeout', checked_at=now(),
                                warnings=['本機 Python 檢查逾時，診斷子程序已停止；尚未確認 CUDA、驅動或裝置資訊。'])
        if outcome != 'ok' or output is None or len(output) > MAX_OUTPUT:
            raise ValueError('invalid diagnostic output')
        return normalize_probe(root, json.loads(output.decode('utf-8')))
    except (OSError, ValueError, UnicodeError, subprocess.SubprocessError):
        return local_report(root, status='unavailable', checked_at=now(),
                            warnings=['本機 Python、PyTorch 匯入或診斷輸出無法使用；未啟動引擎、載入模型或生成圖片。'])


class LocalChecks:
    def __init__(self):
        self.probe_lock = threading.Lock()
        self.cache_lock = threading.Lock()
        self.last = None

    def key(self, root):
        workspace, python, _ = local_identity(root)
        return str(workspace), str(python)

    def get(self, root):
        key = self.key(root)
        with self.cache_lock:
            if self.last is not None and self.last[0] == key:
                return copy.deepcopy(self.last[1])
        return local_report(root)

    def run(self, root):
        # The worker, rather than the HTTP awaiter, owns the whole subprocess
        # lifecycle so disconnecting a client cannot release the probe early.
        if not self.probe_lock.acquire(blocking=False):
            raise BusyProbe()
        try:
            report = probe_local(root)
            with self.cache_lock:
                self.last = (self.key(root), copy.deepcopy(report))
            return report
        finally:
            self.probe_lock.release()


class BusyProbe(Exception):
    pass


def install(app, host):
    from fastapi import HTTPException, Request
    from starlette.concurrency import run_in_threadpool

    state = LocalChecks()
    host.local_environment_state = state

    @app.get('/api/local-environment')
    def cached():
        return state.get(host.ROOT)

    @app.post('/api/local-environment')
    async def check(request: Request):
        if request.query_params or await request.body():
            raise HTTPException(422, '本機檢查只使用固定 ComfyUI Python 與固定腳本；不接受執行參數或請求內容')
        try:
            return await run_in_threadpool(state.run, host.ROOT)
        except BusyProbe:
            raise HTTPException(409, '本機 Python 檢查正在執行，請等待完成；未啟動第二個檢查程序')
