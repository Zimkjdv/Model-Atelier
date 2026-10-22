"""Verify the real bundled aiohttp route without loading weights or tensors.

Run with the ComfyUI Python. --managed-cpu additionally starts a temporary
CPU-only ComfyUI on an ephemeral localhost port and always stops that process.
"""
import argparse
import asyncio
import importlib.util
import json
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
from types import ModuleType, SimpleNamespace
from urllib.request import urlopen
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]


async def route_checks():
    from aiohttp import web
    from aiohttp.test_utils import TestClient, TestServer

    calls = []
    management = ModuleType('comfy.model_management')
    management.get_torch_device = lambda: SimpleNamespace(type='cuda', index=0)
    management.torch = SimpleNamespace(cuda=SimpleNamespace(is_available=lambda: False))
    comfy = ModuleType('comfy')
    comfy.model_management = management
    server = ModuleType('server')
    server.PromptServer = SimpleNamespace(instance=SimpleNamespace(routes=web.RouteTableDef()))
    sys.modules.update({'server': server, 'comfy': comfy, 'comfy.model_management': management})
    package = ROOT / 'comfyui_extensions' / 'model_atelier_execution_device'
    spec = importlib.util.spec_from_file_location('atelier_route_acceptance', package / '__init__.py', submodule_search_locations=[str(package)])
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    application = web.Application()
    application.add_routes(server.PromptServer.instance.routes)
    async with TestClient(TestServer(application, host='127.0.0.1')) as client:
        for suffix in ('', '?probe_id=bad', '?probe_id=' + str(uuid4()) + '&other=1'):
            response = await client.get('/model_atelier/execution-device' + suffix)
            assert response.status == 400
        for status in ('unavailable', 'available', 'unknown', 'selection_failed'):
            if status == 'available':
                management.get_torch_device = lambda: SimpleNamespace(type='cpu', index=None)
            elif status == 'unknown':
                management.get_torch_device = lambda: SimpleNamespace(type='cuda', index=0)
                def fail():
                    raise RuntimeError('PRIVATE_PROBE_EXCEPTION')
                management.torch.cuda.is_available = fail
            elif status == 'selection_failed':
                management.get_torch_device = fail
            nonce = str(uuid4())
            response = await client.get('/model_atelier/execution-device?probe_id=' + nonce)
            data = await response.json()
            assert response.status == 200 and response.headers['Cache-Control'] == 'no-store'
            assert data['probe_id'] == nonce
            assert data['status'] == ('unavailable' if status == 'selection_failed' else status)
            assert 'PRIVATE_PROBE_EXCEPTION' not in json.dumps(data)
            calls.append(dict(scenario=status, status=data['status'], reason=data['reason']))
    return calls


def managed_cpu_check():
    import psutil
    engine = ROOT / 'runtime' / 'ComfyUI'
    # Only select an unused loopback port; startup readiness is checked below.
    with socket.socket() as probe:
        probe.bind(('127.0.0.1', 0))
        port = probe.getsockname()[1]
    with tempfile.TemporaryDirectory(prefix='atelier-device-cpu-') as directory:
        folder = Path(directory)
        for name in ('user', 'input', 'output', 'temp'):
            (folder / name).mkdir()
        command = [sys.executable, 'main.py', '--cpu', '--listen', '127.0.0.1', '--port', str(port),
                   '--disable-auto-launch', '--disable-api-nodes', '--disable-all-custom-nodes',
                   '--whitelist-custom-nodes', 'model_atelier_execution_device',
                   '--user-directory', str(folder / 'user'), '--input-directory', str(folder / 'input'),
                   '--output-directory', str(folder / 'output'), '--temp-directory', str(folder / 'temp'),
                   '--database-url', 'sqlite:///:memory:']
        with (folder / 'startup.log').open('w', encoding='utf-8') as log:
            process = subprocess.Popen(command, cwd=engine, stdout=log, stderr=log,
                                       creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            try:
                deadline = time.monotonic() + 45
                nonce = str(uuid4())
                url = f'http://127.0.0.1:{port}/model_atelier/execution-device?probe_id={nonce}'
                while time.monotonic() < deadline:
                    if process.poll() is not None:
                        raise RuntimeError('CPU ComfyUI exited during startup')
                    try:
                        with urlopen(url, timeout=1) as response:
                            result = json.load(response)
                        assert result['probe_id'] == nonce and result['status'] == 'available'
                        assert result['device']['type'] == 'cpu'
                        return result
                    except OSError:
                        time.sleep(0.2)
                raise RuntimeError('CPU ComfyUI startup did not expose the bundled route in time')
            finally:
                # Windows venv python.exe may be a launcher with an interpreter
                # child; stop only this test process tree before cleaning files.
                try:
                    children = psutil.Process(process.pid).children(recursive=True)
                except psutil.NoSuchProcess:
                    children = []
                for child in reversed(children):
                    try:
                        child.terminate()
                    except psutil.NoSuchProcess:
                        pass
                psutil.wait_procs(children, timeout=5)
                for child in children:
                    if child.is_running():
                        child.kill()
                        child.wait(timeout=5)
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--managed-cpu', action='store_true')
    arguments = parser.parse_args()
    result = dict(route_checks=asyncio.run(route_checks()))
    if arguments.managed_cpu:
        result['managed_cpu'] = managed_cpu_check()
    print(json.dumps(result))
