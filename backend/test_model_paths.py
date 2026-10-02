import contextlib
import io
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

from backend import catalog, main, model_paths, test_api
from scripts import comfy_model_paths

REPOSITORY = Path(__file__).resolve().parents[1]


class ModelPathTests(unittest.TestCase):
    def setUp(self):
        test_api.ApiTests.setUp(self)
        self.root = Path(self.temp.name) / 'managed workspace with spaces'
        self.root.mkdir()
        self.root_patcher = patch.object(main, 'ROOT', self.root)
        self.root_patcher.start()
        model_paths.default_directory(self.root).mkdir(parents=True)
        self.first = self.root / 'models one'
        self.second = self.root / 'models two'
        self.first.mkdir()
        self.second.mkdir()

    def tearDown(self):
        self.root_patcher.stop()
        test_api.ApiTests.tearDown(self)

    def save(self, paths, revision=0):
        return self.client.put('/api/local-model-paths', json=dict(revision=revision, paths=[str(path) for path in paths]))

    def rows(self):
        with contextlib.closing(sqlite3.connect(self.db)) as db:
            return db.execute('SELECT key, value FROM settings ORDER BY key').fetchall()

    def cli_database(self, value):
        database = self.root / 'data' / 'atelier.sqlite3'
        database.parent.mkdir(exist_ok=True)
        with contextlib.closing(sqlite3.connect(database)) as db, db:
            db.execute('CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL)')
            db.execute('INSERT OR REPLACE INTO settings VALUES (?, ?)', (model_paths.KEY, json.dumps(value)))
        return database

    def test_get_is_readonly_and_reports_managed_scope_actual_disk_and_unverified_application(self):
        self.client.put('/api/settings', json={'comfy_url': 'https://remote.example/comfy'})
        before = self.rows()
        with patch('backend.main.httpx.AsyncClient', side_effect=AssertionError('no engine probe')):
            response = self.client.get('/api/local-model-paths')
        self.assertEqual(response.status_code, 200, response.text)
        result = response.json()
        self.assertEqual(result['revision'], 0)
        self.assertIsNone(result['updated_at'])
        self.assertEqual(result['paths'], [])
        self.assertEqual(result['directories'], [])
        self.assertEqual(result['scope'], 'managed_local_comfyui')
        self.assertEqual(result['managed_engine_url'], 'http://127.0.0.1:8188')
        self.assertEqual(result['selected_engine_url'], 'https://remote.example/comfy')
        self.assertEqual(result['default_directory']['status'], 'existing')
        self.assertEqual(result['default_directory']['path'], str(model_paths.default_directory(self.root)))
        self.assertGreater(result['default_directory']['disk']['total'], 0)
        self.assertEqual(result['application_status'], 'unverified')
        self.assertTrue(result['restart_required'])
        self.assertEqual(self.rows(), before)

    def test_local_save_is_independent_of_remote_selection_and_preserves_metadata_and_weights(self):
        self.client.put('/api/settings', json={'comfy_url': 'https://remote.example/comfy'})
        catalog.merge(self.db, 'https://remote.example/comfy', ['example.safetensors'])
        catalog.update_metadata(self.db, 'https://remote.example/comfy', 'example.safetensors', {'version': 'v1', 'sha256': 'a' * 64})
        before = dict(self.rows())
        marker = self.first / 'weights.safetensors'
        marker.write_bytes(b'not-a-model-test-marker')
        response = self.save([self.second, self.first])
        self.assertEqual(response.status_code, 200, response.text)
        result = response.json()
        self.assertEqual(result['revision'], 1)
        self.assertEqual(result['paths'], [str(self.second.resolve()), str(self.first.resolve())])
        self.assertTrue(all(item['status'] == 'existing' for item in result['directories']))
        self.assertTrue(all(item['disk']['total'] > 0 for item in result['directories']))
        for key, value in before.items():
            self.assertEqual(dict(self.rows())[key], value)
        self.assertEqual(marker.read_bytes(), b'not-a-model-test-marker')
        self.assertFalse((self.root / 'runtime' / model_paths.EXPORT_NAME).exists())
        self.assertEqual(self.client.get('/api/settings').json()['comfy_url'], 'https://remote.example/comfy')

    def test_invalid_new_paths_are_rejected_without_database_or_filesystem_mutation(self):
        file = self.root / 'not-directory.safetensors'
        file.write_bytes(b'test')
        before = self.rows()
        invalid = ['relative/path', 'C:relative', str(file), str(self.root / 'missing'),
                   '\\\\server\\share\\models', '//server/share/models', '\\\\?\\C:\\models',
                   '%USERPROFILE%\\models', '$HOME/models', '${HOME}/models', '~/models',
                   str(self.first) + '\n', str(self.first) + '\r', str(self.first) + '\x00',
                   str(self.first) + '\t', str(self.first) + '\u0085', str(self.first) + '\u2028',
                   str(self.first) + '\u2029', ' ' + str(self.first), str(self.first) + ' ']
        for value in invalid:
            with self.subTest(value=value):
                response = self.client.put('/api/local-model-paths', json=dict(revision=0, paths=[value]))
                self.assertEqual(response.status_code, 422, response.text)
                self.assertEqual(self.rows(), before)
        self.assertFalse((self.root / 'missing').exists())
        self.assertEqual(file.read_bytes(), b'test')

    def test_strict_revisions_path_types_and_eight_directory_limit(self):
        for body in [dict(revision=value, paths=[]) for value in (True, False, 0.0, '0', -1)] + [
                dict(revision=0, paths=[True]), dict(revision=0, paths=[123]),
                dict(revision=0, paths=[str(self.first)] * 9), dict(revision=0, paths='not-a-list')]:
            self.assertEqual(self.client.put('/api/local-model-paths', json=body).status_code, 422, body)
        directories = [self.root / ('extra-' + str(number)) for number in range(8)]
        for directory in directories:
            directory.mkdir()
        self.assertEqual(self.save(directories).status_code, 200)

    def test_canonical_aliases_case_and_builtin_directory_are_not_registered_twice(self):
        for paths in ([self.first, self.first], [self.first, self.first / '..' / self.first.name],
                      [model_paths.default_directory(self.root)]):
            self.assertEqual(self.save(paths).status_code, 422)
        alias = self.root / 'symbolic alias'
        original_resolve = Path.resolve
        def resolve(path, *args, **kwargs):
            return self.first.resolve() if path == alias else original_resolve(path, *args, **kwargs)
        with patch.object(Path, 'resolve', resolve):
            self.assertEqual(self.save([self.first, alias]).status_code, 422)
            saved = self.save([alias])
            self.assertEqual(saved.status_code, 200, saved.text)
            self.assertEqual(saved.json()['paths'], [str(self.first.resolve())])
        if os.name == 'nt':
            self.assertEqual(self.save([str(self.first).upper()], revision=1).status_code, 200)
            self.assertEqual(self.save([self.first, str(self.first).upper()], revision=2).status_code, 422)

    @unittest.skipUnless(os.name == 'nt', 'Windows mapped-drive guard')
    def test_mapped_network_drive_is_rejected_before_directory_access(self):
        with (patch('backend.model_paths.ctypes.windll.kernel32.GetDriveTypeW', return_value=4),
              patch('backend.model_paths.os.scandir', side_effect=AssertionError('must not access network path'))):
            self.assertEqual(self.save([self.first]).status_code, 422)
            with self.assertRaises(ValueError):
                model_paths.canonical_directory(str(self.first))

    def test_cas_conflict_and_concurrent_save_allow_only_one_revision_winner(self):
        gate = threading.Barrier(2)
        def saved(directory):
            gate.wait(timeout=5)
            try:
                return model_paths.save(self.db, self.root, [str(directory)], 0)
            except model_paths.RevisionConflict as exc:
                return exc
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = [future.result(timeout=10) for future in [pool.submit(saved, self.first), pool.submit(saved, self.second)]]
        self.assertEqual(sum(isinstance(value, dict) for value in results), 1)
        self.assertEqual(sum(isinstance(value, model_paths.RevisionConflict) for value in results), 1)
        before = self.rows()
        response = self.save([self.first], revision=0)
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()['detail']['code'], 'revision_conflict')
        self.assertEqual(response.json()['detail']['current_revision'], 1)
        self.assertEqual(self.rows(), before)
        self.assertEqual(self.save([], revision=1).json()['revision'], 2)

    def test_missing_unreadable_and_unknown_capacity_status_are_distinct_and_do_not_block_readable_paths(self):
        self.assertEqual(self.save([self.first]).status_code, 200)
        self.first.rmdir()
        before = self.rows()
        result = self.client.get('/api/local-model-paths').json()
        self.assertEqual(result['directories'][0]['status'], 'missing')
        self.assertIsNone(result['directories'][0]['disk'])
        self.assertEqual(self.rows(), before)
        self.first.mkdir()
        with patch('backend.model_paths.os.scandir', side_effect=PermissionError('test permission')):
            result = self.client.get('/api/local-model-paths').json()
            self.assertEqual(result['directories'][0]['status'], 'unreadable')
            self.assertEqual(self.save([self.first], revision=1).status_code, 422)
        with patch('backend.model_paths.shutil.disk_usage', side_effect=OSError('unknown capacity')):
            response = self.save([self.first], revision=1)
            self.assertEqual(response.status_code, 200, response.text)
            self.assertEqual(response.json()['directories'][0]['status'], 'existing')
            self.assertIsNone(response.json()['directories'][0]['disk'])
            self.assertIn('容量', response.json()['directories'][0]['error'])
            exported = model_paths.export(self.db, self.root)
            self.assertTrue(exported.is_file())

    def test_export_is_ordered_nondefault_json_as_yaml_and_never_changes_original_yaml_or_weights(self):
        builtin = model_paths.default_directory(self.root)
        weight = builtin / 'test-weight.safetensors'
        weight.write_bytes(b'weights must remain unchanged')
        custom_yaml = self.root / 'runtime' / 'ComfyUI' / 'extra_model_paths.yaml'
        custom_yaml.write_text('custom_existing:\n  checkpoints: untouched\n', encoding='utf-8')
        old_yaml = custom_yaml.read_bytes()
        model_paths.save(self.db, self.root, [str(self.second), str(self.first)], 0)
        before = self.rows()
        target = model_paths.export(self.db, self.root)
        config = json.loads(target.read_text(encoding='utf-8'))
        self.assertEqual(config, {'model_atelier': dict(is_default=False, checkpoints=str(self.second.resolve()) + '\n' + str(self.first.resolve()))})
        self.assertNotIn('base_path', config['model_atelier'])
        self.assertNotIn(str(builtin), config['model_atelier']['checkpoints'])
        self.assertEqual(custom_yaml.read_bytes(), old_yaml)
        self.assertEqual(weight.read_bytes(), b'weights must remain unchanged')
        self.assertEqual(self.rows(), before)

    def test_absent_database_exports_empty_object_without_creating_database(self):
        absent = self.root / 'data' / 'missing.sqlite3'
        target = model_paths.export(absent, self.root)
        self.assertEqual(json.loads(target.read_text(encoding='utf-8')), {})
        self.assertFalse(absent.exists())
        self.assertFalse(absent.parent.exists())

    def test_invalid_stored_schema_paths_and_missing_directories_preserve_previous_export(self):
        model_paths.save(self.db, self.root, [str(self.first)], 0)
        target = model_paths.export(self.db, self.root)
        before = target.read_bytes()
        for value in [dict(revision=True, updated_at=None, paths=[]), dict(revision=1, updated_at='not-a-date', paths=[]),
                      dict(revision=1, updated_at=None, paths=[str(self.first) + '\n']),
                      dict(revision=1, updated_at=None, paths=[str(self.root / 'missing')]),
                      dict(revision=1, updated_at=None, paths=[str(self.first)] * 2)]:
            with contextlib.closing(sqlite3.connect(self.db)) as db, db:
                db.execute('UPDATE settings SET value=? WHERE key=?', (json.dumps(value), model_paths.KEY))
            with self.assertRaises(ValueError):
                model_paths.export(self.db, self.root)
            self.assertEqual(target.read_bytes(), before)

    def test_export_rejects_symlink_targets_and_resolved_runtime_escape(self):
        target = self.root / 'runtime' / model_paths.EXPORT_NAME
        target.write_text('old config', encoding='utf-8')
        actual_symlink = Path.is_symlink
        def is_symlink(path):
            return path == target or actual_symlink(path)
        with patch.object(Path, 'is_symlink', is_symlink):
            with self.assertRaises(ValueError):
                model_paths.export(self.db, self.root)
        self.assertEqual(target.read_text(encoding='utf-8'), 'old config')
        outside = Path(self.temp.name) / 'outside.json'
        outside.write_text('outside unchanged', encoding='utf-8')
        actual_resolve = Path.resolve
        def resolve(path, *args, **kwargs):
            return outside if path == target else actual_resolve(path, *args, **kwargs)
        with patch.object(Path, 'resolve', resolve):
            with self.assertRaises(ValueError):
                model_paths.export(self.db, self.root)
        self.assertEqual(outside.read_text(encoding='utf-8'), 'outside unchanged')

    def test_export_ignores_predictable_tmp_and_cleans_atomic_temporary_file_on_replace_failure(self):
        target = self.root / 'runtime' / model_paths.EXPORT_NAME
        predictable = target.with_suffix(target.suffix + '.tmp')
        predictable.write_text('untouched user file', encoding='utf-8')
        target.write_text('old config', encoding='utf-8')
        with patch('backend.model_paths.os.replace', side_effect=OSError('test failure')):
            with self.assertRaises(OSError):
                model_paths.export(self.db, self.root)
        self.assertEqual(target.read_text(encoding='utf-8'), 'old config')
        self.assertEqual(predictable.read_text(encoding='utf-8'), 'untouched user file')
        self.assertEqual(list(target.parent.glob('comfy-extra-model-paths.*.tmp')), [predictable])

    def test_cli_is_standard_library_only_and_preserves_space_paths_as_single_arguments(self):
        self.cli_database(dict(revision=1, updated_at=None, paths=[str(self.first), str(self.second)]))
        code = ('import runpy,sys; from pathlib import Path; '
                'module=runpy.run_path(sys.argv[1],run_name="test_exporter"); '
                'result=module["main"]([],root=Path(sys.argv[2])); '
                'assert not any(name in sys.modules for name in ("backend.main","fastapi","torch")); '
                'raise SystemExit(result)')
        response = subprocess.run([sys.executable, '-I', '-c', code, str(REPOSITORY / 'scripts' / 'comfy_model_paths.py'), str(self.root)],
                                  capture_output=True, text=True, timeout=30,
                                  creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0,
                                  env=os.environ | {'PYTHONDONTWRITEBYTECODE': '1'})
        self.assertEqual(response.returncode, 0, response.stderr)
        target = self.root / 'runtime' / model_paths.EXPORT_NAME
        self.assertEqual(response.stdout.strip(), str(target.resolve()))
        self.assertEqual(json.loads(target.read_text(encoding='utf-8'))['model_atelier']['checkpoints'].split('\n'),
                         [str(self.first.resolve()), str(self.second.resolve())])
        self.cli_database(dict(revision=2, updated_at=None, paths=[str(self.root / 'missing')]))
        stdout, stderr = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            self.assertEqual(comfy_model_paths.main([], root=self.root), 1)
        self.assertEqual(stdout.getvalue(), '')
        self.assertIn('ComfyUI was not started', stderr.getvalue())

    def test_sqlite_failure_is_reported_safely_without_model_file_changes(self):
        before = self.rows()
        with patch('backend.model_paths.save', side_effect=sqlite3.OperationalError('PRIVATE_DATABASE_TRACE')):
            response = self.save([self.first])
        self.assertEqual(response.status_code, 500)
        self.assertNotIn('PRIVATE_DATABASE_TRACE', response.text)
        self.assertEqual(self.rows(), before)

    @unittest.skipUnless(os.name == 'nt', 'PowerShell launch argument verification')
    def test_start_script_preserves_spaces_and_stops_before_main_on_export_failure(self):
        shell = shutil.which('pwsh') or shutil.which('powershell')
        if not shell:
            self.skipTest('PowerShell is unavailable')
        scripts = self.root / 'scripts'
        scripts.mkdir()
        backend = self.root / 'backend'
        backend.mkdir()
        shutil.copy2(REPOSITORY / 'scripts' / 'comfy_model_paths.py', scripts)
        shutil.copy2(REPOSITORY / 'backend' / 'model_paths.py', backend)
        (backend / '__init__.py').write_text('', encoding='utf-8')
        shutil.copy2(REPOSITORY / 'start-comfyui.ps1', self.root)
        comfy = self.root / 'runtime' / 'ComfyUI'
        python = comfy / '.venv' / 'Scripts' / 'python.exe'
        python.parent.mkdir(parents=True)
        shutil.copy2(sys.executable, python)
        shutil.copy2(Path(sys.executable).parents[1] / 'pyvenv.cfg', comfy / '.venv' / 'pyvenv.cfg')
        (comfy / 'main.py').write_text('import json,sys\nfrom pathlib import Path\nPath("observed-arguments.json").write_text(json.dumps(sys.argv[1:]),encoding="utf-8")\n', encoding='utf-8')
        self.cli_database(dict(revision=1, updated_at=None, paths=[str(self.first)]))
        command = [shell, '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', str(self.root / 'start-comfyui.ps1')]
        result = subprocess.run(command, capture_output=True, text=True, errors="replace", timeout=30, creationflags=subprocess.CREATE_NO_WINDOW,
                                env=os.environ | {'PYTHONDONTWRITEBYTECODE': '1'})
        self.assertEqual(result.returncode, 0, result.stderr)
        marker = comfy / 'observed-arguments.json'
        arguments = json.loads(marker.read_text(encoding='utf-8'))
        index = arguments.index('--extra-model-paths-config')
        self.assertEqual(arguments[index + 1], str((self.root / 'runtime' / model_paths.EXPORT_NAME).resolve()))
        previous = marker.read_bytes()
        self.cli_database(dict(revision=2, updated_at=None, paths=[str(self.root / 'missing')]))
        result = subprocess.run(command, capture_output=True, text=True, errors="replace", timeout=30, creationflags=subprocess.CREATE_NO_WINDOW,
                                env=os.environ | {'PYTHONDONTWRITEBYTECODE': '1'})
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(marker.read_bytes(), previous)

    def test_generated_json_roundtrips_through_installed_comfy_yaml_loader_without_gpu_imports(self):
        python = REPOSITORY / 'runtime' / 'ComfyUI' / '.venv' / 'Scripts' / 'python.exe'
        loader = REPOSITORY / 'runtime' / 'ComfyUI' / 'utils' / 'extra_config.py'
        if not python.is_file() or not loader.is_file():
            self.skipTest('Installed ComfyUI parser is unavailable')
        model_paths.save(self.db, self.root, [str(self.second), str(self.first)], 0)
        target = model_paths.export(self.db, self.root)
        code = ('import importlib.util,sys,types,json; '
                'calls=[]; sys.modules["folder_paths"]=types.SimpleNamespace(add_model_folder_path=lambda *args:calls.append(args)); '
                'spec=importlib.util.spec_from_file_location("extra_config",sys.argv[1]); module=importlib.util.module_from_spec(spec); '
                'spec.loader.exec_module(module); module.load_extra_path_config(sys.argv[2]); '
                'assert "torch" not in sys.modules; print(json.dumps(calls))')
        result = subprocess.run([str(python), '-I', '-c', code, str(loader), str(target)], capture_output=True, text=True, timeout=30,
                                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0,
                                env=os.environ | {'PYTHONDONTWRITEBYTECODE': '1'})
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), [['checkpoints', str(self.second.resolve()), False], ['checkpoints', str(self.first.resolve()), False]])
