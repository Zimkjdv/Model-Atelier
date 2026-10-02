import asyncio
import builtins
import json
import os
import sqlite3
import subprocess
import sys
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing, ExitStack
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import httpx

from backend import environment, main, test_api
from scripts import check_local_environment as diagnostic_script


class EnvironmentTests(unittest.TestCase):
    def setUp(self):
        test_api.ApiTests.setUp(self)
        self.root = Path(self.temp.name) / 'managed workspace with spaces'
        self.root.mkdir()
        self.root_patcher = patch.object(main, 'ROOT', self.root)
        self.root_patcher.start()
        self.state = main.local_environment_state
        with self.state.cache_lock:
            self.state.last = None

    def tearDown(self):
        with self.state.cache_lock:
            self.state.last = None
        self.root_patcher.stop()
        test_api.ApiTests.tearDown(self)

    def rows(self):
        with closing(sqlite3.connect(self.db)) as database:
            return database.execute('SELECT key, value FROM settings ORDER BY key').fetchall()

    def stats(self):
        return dict(system=dict(os='win32', ram_total=32000, ram_free=12000, python_version='3.12.10',
                                pytorch_version='2.14.0+cu999', comfyui_version='0.34',
                                cuda_runtime='UNTRUSTED_CUDA', driver='UNTRUSTED_DRIVER',
                                argv=['PRIVATE_PROMPT'], traceback='PRIVATE_TRACE'),
                    devices=[dict(name='NVIDIA Example', type='cuda', index=0, vram_total=12000, vram_free=9000,
                                  torch_vram_total=8000, torch_vram_free=6000)])

    def remote(self, payload=None, error=None, on_get=None):
        remote = AsyncMock()
        remote.__aenter__.return_value = remote
        async def get(url):
            if on_get:
                on_get(url)
            if error:
                raise error
            # Raw NaN/Infinity emulate untrusted upstream JSON rather than an
            # already-normalized mock that could hide serialization failures.
            return httpx.Response(200, content=json.dumps(payload).encode(), request=httpx.Request('GET', url))
        remote.get.side_effect = get
        return remote

    def engine(self, payload=None, **changes):
        remote = self.remote(payload, **changes)
        with patch.object(main.httpx, 'AsyncClient', return_value=remote), patch.object(main, 'gpu_info', side_effect=AssertionError('platform GPU must not fill engine data')):
            result = self.client.get('/api/engine')
        self.assertEqual(result.status_code, 200)
        return result.json(), remote

    def managed_files(self):
        _, python, script = environment.local_identity(self.root)
        python.parent.mkdir(parents=True, exist_ok=True)
        script.parent.mkdir(parents=True, exist_ok=True)
        python.touch()
        script.touch()
        return python, script

    def payload(self, cuda=False, **changes):
        _, python, _ = environment.local_identity(self.root)
        result = dict(schema_version=1, python_path=str(python), status='available',
                      system=dict(python='3.12.10', pytorch='2.14.0+cpu', cuda_runtime=None, cuda_available=cuda, driver='616.56'),
                      devices=[], warnings=[])
        result.update(changes)
        return result

    def probe(self, payload=None, outcome='ok'):
        self.managed_files()
        output = json.dumps(payload if payload is not None else self.payload()).encode()
        with patch.object(environment, 'bounded_process', return_value=(outcome, output)) as runner:
            result = self.client.post('/api/local-environment')
        self.assertEqual(result.status_code, 200)
        return result.json(), runner

    def test_engine_scope_versions_and_memory_never_infer_cuda_or_platform_driver(self):
        report, remote = self.engine(self.stats())
        diagnostic = report['diagnostics']
        self.assertTrue(report['connected'])
        self.assertEqual(report['stats']['system']['comfyui_version'], '0.34')
        self.assertEqual(diagnostic['source'], 'ComfyUI /system_stats')
        self.assertEqual(diagnostic['engine_url'], report['url'])
        self.assertEqual(diagnostic['selected_engine_url'], report['url'])
        self.assertTrue(diagnostic['matches_selected_engine'])
        self.assertEqual(diagnostic['system']['pytorch'], '2.14.0+cu999')
        for field in ('cuda_runtime', 'cuda_available', 'driver'):
            self.assertIsNone(diagnostic['system'][field])
        self.assertEqual(diagnostic['ram'], dict(total=32000, free=12000, used=20000))
        self.assertEqual(diagnostic['devices'][0]['vram'], dict(total=12000, free=9000, used=3000))
        self.assertEqual(diagnostic['devices'][0]['torch_vram']['used'], 2000)
        self.assertNotIn('argv', report['stats']['system'])
        self.assertNotIn('PRIVATE_TRACE', json.dumps(report))
        remote.get.assert_awaited_once_with('http://127.0.0.1:8188/system_stats')

    def test_engine_nonfinite_boolean_negative_huge_values_and_strings_are_unknown_json(self):
        stats = self.stats()
        stats['system'].update(ram_total=True, ram_free=float('nan'), os='private\ntrace', python_version='x' * 1000)
        stats['devices'][0].update(index=True, vram_total=float('inf'), vram_free=-1,
                                   torch_vram_total=2**64, torch_vram_free=0, name='Traceback PRIVATE_TRACE')
        report, _ = self.engine(stats)
        diagnostic = report['diagnostics']
        self.assertEqual(diagnostic['ram'], dict(total=None, free=None, used=None))
        self.assertIsNone(diagnostic['system']['os'])
        self.assertIsNone(diagnostic['system']['python'])
        device = diagnostic['devices'][0]
        for field in ('name', 'index'):
            self.assertIsNone(device[field])
        self.assertEqual(device['vram'], dict(total=None, free=None, used=None))
        self.assertEqual(device['torch_vram'], dict(total=None, free=None, used=None))
        self.assertIsNone(report['stats']['devices'][0]['vram_total'])
        self.assertIsNone(report['stats']['system']['ram_free'])
        json.dumps(report, allow_nan=False)

    def test_memory_free_exceeding_total_is_unknown_not_negative_usage(self):
        for total, free, expected in [(100, 101, dict(total=100, free=None, used=None)),
                                      (100, 0, dict(total=100, free=0, used=100)),
                                      (0, 0, dict(total=None, free=None, used=None)),
                                      (100, False, dict(total=100, free=None, used=None))]:
            with self.subTest(total=total, free=free):
                self.assertEqual(environment.memory(total, free), expected)

    def test_engine_offline_and_invalid_shapes_keep_unknown_source_scoped_data(self):
        before = self.rows()
        report, _ = self.engine(error=httpx.ConnectError('PRIVATE_TRACE'))
        self.assertFalse(report['connected'])
        self.assertEqual(report['diagnostics']['status'], 'offline')
        self.assertEqual(report['diagnostics']['devices'], [])
        self.assertNotIn('PRIVATE_TRACE', json.dumps(report))
        for malformed in ([], None, dict(system=[], devices=[]), dict(system={}, devices={})):
            with self.subTest(payload=malformed):
                report, _ = self.engine(malformed)
                self.assertFalse(report['connected'])
                self.assertEqual(report['diagnostics']['status'], 'invalid')
                self.assertEqual(report['diagnostics']['devices'], [])
        self.assertEqual(self.rows(), before)

    def test_engine_switch_during_query_does_not_claim_original_gpu_is_current_engine(self):
        replacement = 'https://remote.example/comfy'
        def change(url):
            with closing(sqlite3.connect(self.db)) as database, database:
                database.execute('INSERT OR REPLACE INTO settings VALUES (?, ?)', ('comfy_url', replacement))
        report, _ = self.engine(self.stats(), on_get=change)
        self.assertTrue(report['connected'])  # Original engine did respond.
        self.assertEqual(report['url'], 'http://127.0.0.1:8188')
        self.assertEqual(report['stats']['system']['comfyui_version'], '0.34')
        diagnostic = report['diagnostics']
        self.assertEqual(diagnostic['status'], 'invalid')
        self.assertFalse(diagnostic['matches_selected_engine'])
        self.assertEqual(diagnostic['engine_url'], report['url'])
        self.assertEqual(diagnostic['selected_engine_url'], replacement)
        self.assertEqual(diagnostic['devices'], [])
        self.assertTrue(all(value is None for value in diagnostic['system'].values()))
        self.assertIn('設定已變更', report['error'])

    def test_platform_nvidia_memory_rejects_infinity_negative_and_impossible_free(self):
        result = SimpleNamespace(returncode=0, stdout='0, NVIDIA Test, 12288, -1, 99999, 616.56\n1, NVIDIA Other, inf, NaN, 0, 616.56\n')
        with patch.object(main.subprocess, 'run', return_value=result):
            cards, error = main.gpu_info()
        self.assertIsNone(error)
        self.assertEqual(cards[0]['total'], 12288 * 1024**2)
        self.assertIsNone(cards[0]['used'])
        self.assertIsNone(cards[0]['free'])
        self.assertIsNone(cards[1]['total'])
        self.assertIsNone(cards[1]['used'])

    def test_local_get_is_readonly_unchecked_and_selected_remote_does_not_change_identity(self):
        self.client.put('/api/settings', json=dict(comfy_url='https://remote.example/comfy'))
        before = self.rows()
        with patch.object(environment, 'probe_local', side_effect=AssertionError('GET must not probe')):
            report = self.client.get('/api/local-environment').json()
        self.assertEqual(report['status'], 'not_checked')
        self.assertIsNone(report['checked_at'])
        self.assertEqual(report['source'], environment.LOCAL_SOURCE)
        self.assertEqual(report['scope'], 'managed_local_comfyui')
        self.assertEqual(report['python_path'], str(environment.local_identity(self.root)[1]))
        self.assertEqual(report['devices'], [])
        self.assertTrue(all(value is None for value in report['system'].values()))
        self.assertEqual(self.rows(), before)

    def test_missing_environment_is_explicit_and_cached_without_process_or_database_writes(self):
        before = self.rows()
        with patch.object(environment, 'bounded_process', side_effect=AssertionError('missing env cannot start subprocess')):
            result = self.client.post('/api/local-environment')
        self.assertEqual(result.status_code, 200)
        report = result.json()
        self.assertEqual(report['status'], 'unavailable')
        self.assertIsNotNone(report['checked_at'])
        self.assertEqual(self.client.get('/api/local-environment').json(), report)
        self.assertEqual(self.rows(), before)

    def test_cpu_false_is_available_diagnostics_fixed_argv_and_cached_timestamp(self):
        before = self.rows()
        report, runner = self.probe()
        _, python, script = environment.local_identity(self.root)
        runner.assert_called_once_with([str(python), '-I', str(script)])
        self.assertEqual(report['status'], 'available')
        self.assertIs(report['system']['cuda_available'], False)
        self.assertIsNone(report['system']['cuda_runtime'])
        self.assertEqual(report['devices'], [])
        with patch.object(environment, 'probe_local', side_effect=AssertionError('cache GET cannot probe')):
            self.assertEqual(self.client.get('/api/local-environment').json(), report)
        self.assertEqual(self.rows(), before)
        cached = self.state.get(self.root)
        cached['system']['driver'] = 'changed'
        self.assertEqual(self.state.get(self.root)['system']['driver'], '616.56')
        self.assertEqual(self.state.get(self.root / 'different')['status'], 'not_checked')

    def test_import_unavailable_timeout_and_invalid_output_replace_old_cached_success(self):
        self.probe()
        payload = self.payload(status='unavailable', warnings=['PyTorch 無法匯入'])
        report, _ = self.probe(payload)
        self.assertEqual(report['status'], 'unavailable')
        self.assertEqual(self.client.get('/api/local-environment').json(), report)
        timeout, _ = self.probe(outcome='timeout')
        self.assertEqual(timeout['status'], 'timeout')
        self.assertEqual(timeout['devices'], [])
        self.assertTrue(all(value is None for value in timeout['system'].values()))
        self.assertEqual(self.client.get('/api/local-environment').json(), timeout)
        for output in (b'PRIVATE_TRACE not json', b'X' * (environment.MAX_OUTPUT + 1), b'{"status":"available"}'):
            with self.subTest(output_size=len(output)), patch.object(environment, 'bounded_process', return_value=('ok', output)):
                report = self.client.post('/api/local-environment').json()
            self.assertEqual(report['status'], 'unavailable')
            self.assertNotIn('PRIVATE_TRACE', json.dumps(report))
            self.assertEqual(self.client.get('/api/local-environment').json(), report)

    def test_probe_schema_identity_values_and_warning_sanitization(self):
        for changes in (dict(schema_version=True), dict(python_path=str(self.root / 'other.exe')), dict(devices={}), dict(status='unknown')):
            with self.subTest(changes=changes):
                report, _ = self.probe(self.payload(**changes))
                self.assertEqual(report['status'], 'unavailable')
        payload = self.payload(cuda=1, warnings=['safe warning', 'Traceback PRIVATE_TRACE', 'line\nPRIVATE_PROMPT', 'x' * 1000])
        payload['devices'] = [dict(name='GPU', type='cuda', index=True,
                                   vram=dict(total=100, free=101), torch_vram=dict(total=float('inf'), free=0))]
        report, _ = self.probe(payload)
        self.assertIsNone(report['system']['cuda_available'])
        self.assertIsNone(report['devices'][0]['index'])
        self.assertEqual(report['devices'][0]['vram'], dict(total=100, free=None, used=None))
        self.assertEqual(report['devices'][0]['torch_vram'], dict(total=None, free=None, used=None))
        self.assertIn('safe warning', report['warnings'])
        self.assertNotIn('PRIVATE_', json.dumps(report))
        json.dumps(report, allow_nan=False)

    def test_api_rejects_caller_arguments_and_body_without_probing(self):
        with patch.object(environment, 'probe_local', side_effect=AssertionError('caller args cannot run')):
            for url, kwargs in [('/api/local-environment?python=elsewhere', {}),
                                ('/api/local-environment', dict(json={})),
                                ('/api/local-environment', dict(content=b'--unsafe'))]:
                with self.subTest(url=url, kwargs=kwargs):
                    self.assertEqual(self.client.post(url, **kwargs).status_code, 422)
        self.assertEqual(self.client.get('/api/local-environment').json()['status'], 'not_checked')

    def test_concurrent_http_probe_returns_conflict_and_runs_only_once(self):
        started, release = threading.Event(), threading.Event()
        def probe(root):
            started.set()
            if not release.wait(5):
                raise AssertionError('test worker was not released')
            return environment.local_report(root, status='available', checked_at=environment.now())
        before = self.rows()
        with patch.object(environment, 'probe_local', side_effect=probe) as runner, ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(self.client.post, '/api/local-environment')
            try:
                self.assertTrue(started.wait(3))
                second = self.client.post('/api/local-environment')
                self.assertEqual(second.status_code, 409)
                self.assertEqual(runner.call_count, 1)
                self.assertEqual(self.client.get('/api/local-environment').json()['status'], 'not_checked')
            finally:
                release.set()
            self.assertEqual(future.result(timeout=5).status_code, 200)
        self.assertEqual(self.rows(), before)

    def test_cancelled_async_awaiter_does_not_release_still_running_worker(self):
        state = environment.LocalChecks()
        started, release, completed = threading.Event(), threading.Event(), threading.Event()
        def probe(root):
            started.set()
            release.wait(5)
            completed.set()
            return environment.local_report(root, status='available', checked_at=environment.now())
        async def scenario():
            task = asyncio.create_task(asyncio.to_thread(state.run, self.root))
            try:
                for _ in range(100):
                    if started.is_set():
                        break
                    await asyncio.sleep(.01)
                self.assertTrue(started.is_set())
                task.cancel()
                with self.assertRaises(asyncio.CancelledError):
                    await task
                self.assertTrue(state.probe_lock.locked())
                with self.assertRaises(environment.BusyProbe):
                    state.run(self.root)
            finally:
                release.set()
            for _ in range(100):
                if not state.probe_lock.locked():
                    break
                await asyncio.sleep(.01)
            self.assertTrue(completed.is_set())
            self.assertFalse(state.probe_lock.locked())
            self.assertEqual(state.get(self.root)['status'], 'available')
        with patch.object(environment, 'probe_local', side_effect=probe):
            asyncio.run(scenario())


class DiagnosticProcessTests(unittest.TestCase):
    def bounded(self, code, **changes):
        processes = []
        original = subprocess.Popen
        def spawn(*args, **kwargs):
            process = original(*args, **kwargs)
            processes.append(process)
            return process
        with ExitStack() as stack:
            stack.enter_context(patch.object(environment.subprocess, 'Popen', side_effect=spawn))
            for name, value in changes.items():
                stack.enter_context(patch.object(environment, name, value))
            result = environment.bounded_process([sys.executable, '-I', '-c', code])
        self.assertEqual(len(processes), 1)
        self.assertIsNotNone(processes[0].poll())
        self.assertTrue(processes[0].stdout.closed)
        return result

    def test_bounded_process_success_closes_pipe_and_reaps(self):
        self.assertEqual(self.bounded("print('diagnostic')"), ('ok', b'diagnostic\r\n' if os.name == 'nt' else b'diagnostic\n'))

    def test_bounded_process_timeout_kills_reaps_and_does_not_return_private_output(self):
        outcome, output = self.bounded("import time; print('PRIVATE_TRACE', flush=True); time.sleep(10)", PROBE_TIMEOUT=.15)
        self.assertEqual(outcome, 'timeout')
        self.assertIsNone(output)

    def test_bounded_process_overflow_and_failure_kill_reap_without_stderr(self):
        outcome, output = self.bounded("import sys,time; sys.stdout.write('X'*8192); sys.stdout.flush(); time.sleep(10)", MAX_OUTPUT=256)
        self.assertEqual(outcome, 'invalid')
        self.assertIsNone(output)
        self.assertEqual(self.bounded("import sys; print('PRIVATE_TRACE',file=sys.stderr); sys.exit(1)"), ('invalid', None))

    def fake_torch(self, available=True):
        props = SimpleNamespace(name='GPU Mock', total_memory=12 * 1024**3)
        cuda = SimpleNamespace(is_available=lambda: available, device_count=lambda: 1,
                               get_device_properties=lambda index: props)
        return SimpleNamespace(__version__='2.14+cu130', version=SimpleNamespace(cuda='13.0'), cuda=cuda,
                               tensor=lambda *a, **k: self.fail('diagnostic must not allocate tensor'))

    def test_script_reads_torch_build_and_properties_without_tensor_or_free_memory_claims(self):
        with patch.dict(sys.modules, torch=self.fake_torch()), patch.object(diagnostic_script, 'driver_version', return_value='616.56'):
            report = diagnostic_script.collect()
        self.assertEqual(report['status'], 'available')
        self.assertIs(report['system']['cuda_available'], True)
        self.assertEqual(report['system']['cuda_runtime'], '13.0')
        self.assertEqual(report['system']['driver'], '616.56')
        self.assertEqual(report['devices'][0]['vram'], dict(total=12 * 1024**3, free=None, used=None))
        self.assertEqual(report['devices'][0]['torch_vram'], dict(total=None, free=None, used=None))

    def test_script_cpu_and_import_fail_are_distinct_no_raw_exception(self):
        with patch.dict(sys.modules, torch=self.fake_torch(False)), patch.object(diagnostic_script, 'driver_version', return_value=None):
            report = diagnostic_script.collect()
        self.assertEqual(report['status'], 'available')
        self.assertIs(report['system']['cuda_available'], False)
        self.assertEqual(report['devices'], [])
        original_import = builtins.__import__
        def guarded(name, *args, **kwargs):
            if name == 'torch':
                raise ImportError('PRIVATE_TRACE / PRIVATE_PROMPT')
            return original_import(name, *args, **kwargs)
        with patch.object(builtins, '__import__', side_effect=guarded), patch.object(diagnostic_script, 'driver_version', return_value=None):
            report = diagnostic_script.collect()
        self.assertEqual(report['status'], 'unavailable')
        self.assertIsNone(report['system']['cuda_available'])
        self.assertNotIn('PRIVATE_', json.dumps(report))

    def test_script_driver_fixed_query_no_caller_args_and_unparseable_unknown(self):
        result = SimpleNamespace(returncode=0, stdout='616.56\n616.56\n')
        with patch.object(diagnostic_script.subprocess, 'run', return_value=result) as runner:
            self.assertEqual(diagnostic_script.driver_version(), '616.56')
        self.assertEqual(runner.call_args.args[0], ['nvidia-smi', '--query-gpu=driver_version', '--format=csv,noheader,nounits'])
        self.assertEqual(runner.call_args.kwargs['timeout'], 3)
        for stdout in ('PRIVATE_TRACE', '616.56\n615.0', 'x' * 5000):
            with self.subTest(stdout=stdout[:40]), patch.object(diagnostic_script.subprocess, 'run', return_value=SimpleNamespace(returncode=0, stdout=stdout)):
                self.assertIsNone(diagnostic_script.driver_version())


if __name__ == '__main__':
    unittest.main()
