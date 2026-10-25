"""Explicit --run F03 GPU acceptance with fresh DATA and an owned HTTP engine.

No production DATA, input/output, custom nodes or engine settings are modified.
Reports remain under runtime/flux-acceptance/<UUID>, including failed runs.
"""

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import time
from uuid import UUID, uuid4

import httpx

from backend import compute_lease, flux_workflows
from scripts import install_flux
from scripts.verify_flux_generation import Acceptance
from scripts.verify_flux_runtime import ROOT, ensure_engine_stopped, preparation, source_snapshot
from scripts.verify_local_generation import write_report


def free_port():
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        return sock.getsockname()[1]


def wait_ready(url, process, seconds=180):
    deadline = time.monotonic() + seconds
    with httpx.Client(trust_env=False, timeout=2) as client:
        while time.monotonic() < deadline and process.poll() is None:
            try:
                client.get(url).raise_for_status()
                return
            except httpx.HTTPError:
                time.sleep(1)
    raise RuntimeError('Owned service did not become ready: ' + url)


def stop(process):
    if process is not None and process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=15)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=10)


def serve(directory):
    import uvicorn
    from backend.main import create_app

    config = json.loads((directory / 'config.json').read_text(encoding='utf-8'))

    class ObservedClient(httpx.AsyncClient):
        async def post(self, url, **kwargs):
            if url.endswith('/prompt'):
                payload = kwargs.get('json', {})
                with (directory / 'dispatch.jsonl').open('a', encoding='utf-8') as file:
                    file.write(json.dumps(dict(id=payload.get('prompt_id'))) + '\n')
                result = await super().post(url, **kwargs)
                if (
                    payload.get('prompt', {})
                    .get('4', {})
                    .get('inputs', {})
                    .get('text', '')
                    .startswith('F03 lost receipt:')
                ):
                    raise httpx.ReadTimeout(
                        'F03 deliberately lost receipt after real engine response'
                    )
                return result
            return await super().post(url, **kwargs)

    app = create_app(
        root=directory,
        data_root=directory / 'data',
        initial_engine_url=config['engine'],
        engine_client_factory=ObservedClient,
    )
    uvicorn.run(app, host='127.0.0.1', port=config['platform_port'])


def f03_cases(directory, runner, report, engine):
    for name, changes, failure in (
        ('baseline', {}, None),
        (
            'load_failure',
            {'diffusion_model': 'f03-corrupt.safetensors'},
            'model_load_failed',
        ),
        (
            'cuda_oom',
            {'diffusion_model': 'f03-quota-oom.safetensors'},
            'cuda_oom',
        ),
        ('explicit_retry', {}, None),
        (
            'lost_receipt',
            {'prompt': 'F03 lost receipt: a small red house on a green hill'},
            None,
        ),
    ):
        print('F03 case: ' + name, flush=True)
        runner.emit = lambda value, name=name: write_report(directory / (name + '.json'), value)
        report['cases'][name] = runner.run(changes=changes, expected_failure=failure)
    if report['cases']['lost_receipt']['initial_status'] != 'unknown':
        raise ValueError('Lost receipt was not preserved as unknown')
    dispatches = [
        json.loads(line)['id'] for line in (directory / 'dispatch.jsonl').read_text().splitlines()
    ]
    if len(dispatches) != 5 or len(set(dispatches)) != 5:
        raise ValueError('Each case must dispatch exactly once')
    report['dispatches'] = dispatches
    stop(engine)
    report['offline_verification'] = runner.verify(report['cases']['baseline'])
    if len((directory / 'dispatch.jsonl').read_text().splitlines()) != 5:
        raise ValueError('Offline reads dispatched work')


def run(*, case_runner=None):
    ensure_engine_stopped()
    run_id = str(uuid4())
    directory = ROOT / 'runtime/flux-acceptance' / run_id
    directory.mkdir(parents=True, exist_ok=False)
    engine_port, platform_port = free_port(), free_port()
    config = dict(
        run_id=run_id,
        engine=f'http://127.0.0.1:{engine_port}',
        platform_port=platform_port,
        platform=f'http://127.0.0.1:{platform_port}',
    )
    write_report(directory / 'config.json', config)
    engine, platform = None, None
    environment = dict(
        os.environ,
        PYTHONUTF8='1',
        HF_HUB_OFFLINE='1',
        TRANSFORMERS_OFFLINE='1',
        ATELIER_F03_FIXTURE='1',
    )
    for key in ('HF_TOKEN', 'HUGGING_FACE_HUB_TOKEN'):
        environment.pop(key, None)
    report = dict(status='running', config=config, sources=source_snapshot(ROOT), cases={})
    report['tool_sha256'] = {
        name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
        for name in (
            'scripts/flux_acceptance_fixture.py',
            'scripts/flux_failure_node.py',
            'scripts/verify_flux_generation.py',
        )
    }
    original_db = ROOT / 'runtime/ComfyUI/user/comfyui.db'
    report['managed_db_before'] = (
        hashlib.sha256(original_db.read_bytes()).hexdigest() if original_db.is_file() else None
    )
    try:
        with compute_lease.Reservation(ROOT, 'inference', run_id):
            verified = preparation(verify=True)
            if not verified['current_files_verified'] or any(
                row['installation_locked'] for row in verified['components']
            ):
                raise RuntimeError('Pinned component full hash verification failed')
            report['weights'] = verified['components']
            base = directory / 'engine'
            extension = base / 'custom_nodes/f03_fixture'
            extension.mkdir(parents=True)
            shutil.copyfile(ROOT / 'scripts/flux_failure_node.py', extension / '__init__.py')
            whitelist = ['f03_fixture']
            if case_runner is not None:
                device_extension = base / 'custom_nodes/model_atelier_execution_device'
                device_extension.mkdir()
                for filename in ('__init__.py', 'probe.py'):
                    shutil.copyfile(
                        ROOT / 'comfyui_extensions/model_atelier_execution_device' / filename,
                        device_extension / filename,
                    )
                observer = base / 'custom_nodes/f04_observer'
                observer.mkdir()
                shutil.copyfile(ROOT / 'scripts/flux_lora_observer.py', observer / '__init__.py')
                environment['ATELIER_F04_OBSERVATIONS'] = str(directory / 'lora-observation.jsonl')
                whitelist.extend(['model_atelier_execution_device', 'f04_observer'])
            faults = directory / 'fault-models'
            faults.mkdir()
            for name in ('f03-corrupt.safetensors', 'f03-quota-oom.safetensors'):
                (faults / name).write_bytes(b'F03 intentionally invalid fixture weights')
            # JSON is valid YAML; all paths are literal, never shell-expanded.
            extra = directory / 'extra-model-paths.json'
            write_report(extra, dict(f03=dict(diffusion_models=str(faults))))
            with (
                (directory / 'engine.log').open('wb') as engine_log,
                (directory / 'platform.log').open('wb') as platform_log,
            ):
                try:
                    command = [
                        str(ROOT / 'runtime/ComfyUI/.venv/Scripts/python.exe'),
                        str(ROOT / 'runtime/ComfyUI/main.py'),
                        '--listen',
                        '127.0.0.1',
                        '--port',
                        str(engine_port),
                        '--base-directory',
                        str(base),
                        '--database-url',
                        'sqlite:///' + (directory / 'engine.sqlite3').as_posix(),
                        '--models-directory',
                        str(ROOT / 'runtime/ComfyUI/models'),
                        '--extra-model-paths-config',
                        str(extra),
                        '--disable-auto-launch',
                        '--disable-api-nodes',
                        '--disable-all-custom-nodes',
                        '--whitelist-custom-nodes',
                        *whitelist,
                    ]
                    engine = subprocess.Popen(
                        command,
                        cwd=ROOT / 'runtime/ComfyUI',
                        env=environment,
                        stdout=engine_log,
                        stderr=subprocess.STDOUT,
                        creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0),
                    )
                    wait_ready(config['engine'] + '/system_stats', engine)
                    platform = subprocess.Popen(
                        [
                            sys.executable,
                            '-m',
                            'scripts.flux_acceptance_fixture',
                            '--serve',
                            run_id,
                        ],
                        cwd=ROOT,
                        env=environment,
                        stdout=platform_log,
                        stderr=subprocess.STDOUT,
                        creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0),
                    )
                    wait_ready(config['platform'] + '/api/health', platform)
                    with httpx.Client(base_url=config['platform'], trust_env=False) as client:
                        runner = Acceptance(client, config['engine'])
                        inventory = runner.api(
                            'POST', 'flux/components/sync', json={'engine_url': config['engine']}
                        )
                        if inventory['sync_error']:
                            raise RuntimeError(inventory['sync_error'])
                        for item in verified['components']:
                            manifest = next(
                                m
                                for m in install_flux.component_manifests()
                                if m['filename'] == Path(item['target']).name
                            )
                            role, group = next(
                                (role, group)
                                for role, group in flux_workflows.ROLES
                                if role == item['role']
                            )
                            runner.api(
                                'PUT',
                                'flux/components/metadata',
                                json=dict(
                                    engine_url=config['engine'],
                                    category=group,
                                    name=Path(item['target']).name,
                                    version=manifest['version'],
                                    sha256=item['sha256'],
                                    architecture='flux' if role == 'diffusion_model' else 'unknown',
                                    source_url=manifest['source']['page_url'],
                                ),
                            )
                        (case_runner or f03_cases)(directory, runner, report, engine)
                        report['status'] = 'passed'
                finally:
                    stop(platform)
                    stop(engine)
    except BaseException as exc:
        report.update(status='failed', error=str(exc))
        raise
    finally:
        report['managed_db_after'] = (
            hashlib.sha256(original_db.read_bytes()).hexdigest() if original_db.is_file() else None
        )
        if report['managed_db_before'] != report['managed_db_after']:
            report.update(
                status='failed', error='Managed engine database changed during isolated test'
            )
        report['owned_processes_stopped'] = all(
            p is None or p.poll() is not None for p in (engine, platform)
        )
        write_report(directory / 'report.json', report)
        print(
            json.dumps(
                dict(run_id=run_id, status=report['status'], report=str(directory / 'report.json'))
            ),
            flush=True,
        )
    return 0 if report['status'] == 'passed' else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', action='store_true')
    parser.add_argument('--serve')
    args = parser.parse_args()
    if args.serve:
        serve(ROOT / 'runtime/flux-acceptance' / str(UUID(args.serve)))
        return 0
    if not args.run:
        parser.error('Use --run to explicitly start the isolated GPU acceptance')
    return run()


if __name__ == '__main__':
    raise SystemExit(main())
