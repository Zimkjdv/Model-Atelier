"""Read PyTorch/CUDA device properties; never load models or allocate tensors."""
import contextlib
import json
import os
import platform
import re
import subprocess
import sys


def safe_text(value, limit=240):
    if not isinstance(value, str) or not value.strip() or len(value) > limit or any(ord(c) < 32 or 127 <= ord(c) <= 159 for c in value):
        return None
    return value.strip()


def driver_version():
    try:
        result = subprocess.run(['nvidia-smi', '--query-gpu=driver_version', '--format=csv,noheader,nounits'],
                                capture_output=True, text=True, timeout=3,
                                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
        if result.returncode or len(result.stdout) > 4096:
            return None
        versions = {line.strip() for line in result.stdout.splitlines() if line.strip()}
        if len(versions) == 1:
            value = versions.pop()
            return value if len(value) <= 80 and re.fullmatch(r'[0-9]+(?:\.[0-9]+)*', value) else None
    except (OSError, ValueError, subprocess.SubprocessError):
        pass
    return None


def collect():
    report = dict(schema_version=1, python_path=sys.executable, status='unavailable',
                  system=dict(python=platform.python_version(), pytorch=None, cuda_runtime=None, cuda_available=None,
                              driver=driver_version()), devices=[], warnings=[])
    # Suppress Python import warnings/diagnostics: stdout is a single bounded
    # JSON report, and raw exception messages/tracebacks are never returned.
    try:
        with open(os.devnull, 'w') as sink, contextlib.redirect_stdout(sink), contextlib.redirect_stderr(sink):
            import torch
    except Exception:
        report['warnings'].append('PyTorch 無法匯入；未確認本機 CUDA 可用性，也未載入任何模型。')
        return report
    report['status'] = 'available'
    report['system']['pytorch'] = safe_text(str(torch.__version__))
    report['system']['cuda_runtime'] = safe_text(getattr(torch.version, 'cuda', None), 80)
    try:
        available = torch.cuda.is_available()
        report['system']['cuda_available'] = available if type(available) is bool else None
        if available is True:
            count = torch.cuda.device_count()
            if type(count) is not int or not 0 <= count <= 1024:
                raise ValueError('invalid device count')
            for index in range(min(count, 16)):
                properties = torch.cuda.get_device_properties(index)
                total = properties.total_memory
                total = total if type(total) is int and 0 < total <= 9007199254740991 else None
                report['devices'].append(dict(name=safe_text(properties.name), type='cuda', index=index,
                                              vram=dict(total=total, free=None, used=None),
                                              torch_vram=dict(total=None, free=None, used=None)))
            if count > 16:
                report['warnings'].append('裝置清單超出顯示上限，最多回報 16 個 CUDA API 裝置。')
        elif available is False:
            report['warnings'].append('此 ComfyUI Python 的 PyTorch 明確回報 CUDA 不可用；不以驅動存在推定可用。')
    except Exception:
        report['warnings'].append('CUDA 裝置查詢未完成；未取得的欄位保持未知，不回傳原始例外。')
    if report['system']['driver'] is None:
        report['warnings'].append('本機 nvidia-smi 未提供可確認的 NVIDIA 驅動版本；保持未知。')
    report['warnings'].append('只讀取裝置屬性，未配置張量；未查詢即時可用顯存或特定模型的顯存需求。')
    return report


def main():
    with open(os.devnull, 'w') as sink, contextlib.redirect_stdout(sink), contextlib.redirect_stderr(sink):
        report = collect()
    print(json.dumps(report, ensure_ascii=True, allow_nan=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
