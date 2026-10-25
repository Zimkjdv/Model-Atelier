"""Read-only F02 preparation; --run explicitly measures one fixed 512px GPU workload."""

import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from uuid import uuid4

import httpx

from backend import compute_lease, flux_observation, flux_workflows
from scripts import install_flux, install_pony

ROOT = Path(__file__).resolve().parents[1]


def source_snapshot(root):
    files = [
        'scripts/flux_runtime_worker.py',
        'backend/flux_observation.py',
        'backend/flux_workflows.py',
        'runtime/ComfyUI/nodes.py',
        'runtime/ComfyUI/comfy/ops.py',
        'runtime/ComfyUI/comfy/model_management.py',
        'runtime/ComfyUI/comfy/model_patcher.py',
        'runtime/ComfyUI/comfy/sd.py',
        'runtime/ComfyUI/comfy_extras/nodes_sd3.py',
    ]
    hashes = {
        name: hashlib.sha256((root / name).read_bytes()).hexdigest()
        if (root / name).is_file()
        else None
        for name in files
    }
    comfy = root / 'runtime/ComfyUI'
    try:
        version = subprocess.run(
            [
                'git',
                '-c',
                f'safe.directory={comfy.as_posix()}',
                '-C',
                str(comfy),
                'rev-parse',
                'HEAD',
            ],
            capture_output=True,
            text=True,
            check=True,
            timeout=10,
        ).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        version = None
    return dict(comfy_commit=version, file_sha256=hashes)


def ensure_engine_stopped():
    try:
        with httpx.Client(trust_env=False, timeout=5) as client:
            client.get('http://127.0.0.1:8188/queue')
    except httpx.ConnectError:
        return
    except httpx.HTTPError:
        raise RuntimeError('Cannot confirm the managed engine is stopped.') from None
    raise RuntimeError('Finish existing work and stop managed ComfyUI before this GPU check.')


def preparation(*, verify=False):
    report = install_flux.local_report(ROOT, verify=verify)
    for row in report['components']:
        path = Path(row['target'])
        if path.is_file():
            row['file_precision'] = flux_observation.header_observation(path)
            row['mtime_ns'] = path.stat().st_mtime_ns
    return report


def run():
    ensure_engine_stopped()
    python = ROOT / 'runtime/ComfyUI/.venv/Scripts/python.exe'
    if not python.is_file():
        raise RuntimeError('Managed Windows ComfyUI Python is required.')
    run_id = str(uuid4())
    with compute_lease.Reservation(ROOT, 'inference', run_id):
        report = preparation(verify=True)
        if not report['current_files_verified'] or any(
            row['installation_locked'] for row in report['components']
        ):
            raise RuntimeError(
                'All four pinned weights must pass full SHA256 and have no installer lock.'
            )
        ensure_engine_stopped()
        output = ROOT / 'runtime/flux-runtime-checks' / run_id
        if output.parent.resolve() != ROOT / 'runtime/flux-runtime-checks':
            raise RuntimeError('Unsafe runtime path')
        output.mkdir(parents=True, exist_ok=False)
        settings = copy.deepcopy(flux_observation.SETTINGS)
        request = dict(
            schema_version=1,
            run_id=run_id,
            profile=flux_observation.PROFILE,
            settings=settings,
            workflow=flux_workflows.build(flux_workflows.Input(**settings)),
            weights=report['components'],
            source_manifest_sha256=hashlib.sha256(
                (ROOT / 'models/flux1-schnell-plan.json').read_bytes()
            ).hexdigest(),
            filesystem_cache='unknown; weights were fully read for verification before process start',
            execution='native nodes in isolated process; encoders first; models unloaded between stages',
            sources=source_snapshot(ROOT),
        )
        (output / 'request.json').write_text(
            json.dumps(request, ensure_ascii=False, indent=2) + '\n', encoding='utf-8'
        )
        environment = dict(os.environ, PYTHONUTF8='1', HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1')
        for key in ('HF_TOKEN', 'HUGGING_FACE_HUB_TOKEN'):
            environment.pop(key, None)
        process, code, status = None, None, 'starting'
        print('F02 observation directory: ' + str(output), flush=True)
        try:
            with (output / 'worker.log').open('wb') as log:
                process = subprocess.Popen(
                    [str(python), str(ROOT / 'scripts/flux_runtime_worker.py'), '--run-id', run_id],
                    cwd=ROOT,
                    env=environment,
                    stdout=log,
                    stderr=subprocess.STDOUT,
                    creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0),
                )
                code = process.wait(timeout=1800)
                status = 'completed' if code == 0 else 'failed'
        except KeyboardInterrupt:
            status = 'interrupted'
            raise
        except BaseException:
            status = 'failed'
            raise
        finally:
            if process is not None and process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=10)
            receipt = dict(
                run_id=run_id,
                status=status,
                exit_code=process.poll() if process is not None else None,
                worker_process_exited=process is not None and process.poll() is not None,
                observation_available=(output / 'observation.json').is_file(),
                request_sha256=hashlib.sha256((output / 'request.json').read_bytes()).hexdigest(),
            )
            (output / 'run.json').write_text(json.dumps(receipt, indent=2) + '\n', encoding='utf-8')
        print(
            json.dumps(
                dict(
                    run_id=run_id,
                    exit_code=code,
                    resources_released=True,
                    observation=str(output / 'observation.json'),
                ),
                indent=2,
            )
        )
        return code


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', action='store_true')
    args = parser.parse_args(argv)
    try:
        if args.run:
            return run()
        print(json.dumps(preparation(), ensure_ascii=False, indent=2))
        return 0
    except KeyboardInterrupt:
        print('F02 check interrupted; only its own worker was stopped.', file=sys.stderr)
        return 130
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as exc:
        print('F02 check failed: ' + str(exc), file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
    raise SystemExit(main())
