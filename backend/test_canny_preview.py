import hashlib
import io
import json
import subprocess
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch
from PIL import Image
from backend import canny_preview as preview, jobs, main, test_control_workflows as old


def output(raw, settings, **changes):
    stream = io.BytesIO()
    Image.new('RGB', (settings['width'], settings['height']), 'black').save(stream, format='PNG')
    encoded = stream.getvalue()
    info = dict(method=preview.METHOD, device='cpu', dtype='float32', native_sha256=preview.NATIVE_SHA256,
        torch='test', kornia='test', pillow='test', input_sha256=hashlib.sha256(raw).hexdigest(),
        sha256=hashlib.sha256(encoded).hexdigest(),
        **{k: settings[k] for k in ('width', 'height', 'canny_low', 'canny_high')})
    info.update(changes)
    return json.dumps(info).encode() + b'\n' + encoded


class PreviewTests(unittest.TestCase):
    setUp = old.ControlTests.setUp
    tearDown = old.ControlTests.tearDown

    def body(self):
        body = old.ControlTests.body(self)
        return {k: body[k] for k in ('image_asset_id', 'reference_resize', 'width', 'height', 'canny_low', 'canny_high')}

    def test_preview_has_independent_schema_and_no_engine_job_or_disk_writes(self):
        body = self.body()
        files = sorted(str(p) for p in self.db.parent.rglob('*'))
        with patch.object(preview, 'run_worker', side_effect=lambda root, raw, settings: output(raw, settings)), patch('backend.submissions.httpx.AsyncClient', side_effect=AssertionError('no engine')):
            result = self.client.post('/api/control/preview', json=body)
        self.assertEqual(result.status_code, 200, result.text)
        self.assertEqual(result.headers['cache-control'], 'no-store')
        self.assertEqual(result.headers['x-atelier-sha256'], hashlib.sha256(result.content).hexdigest())
        import base64
        info = json.loads(base64.b64decode(result.headers['x-atelier-canny-provenance']))
        self.assertEqual(info['image_asset_id'], body['image_asset_id'])
        self.assertEqual(info['preprocessing']['sha256'], info['input_sha256'])
        self.assertEqual(info['device'], 'cpu')
        self.assertEqual(jobs.list_all(self.db), [])
        self.assertEqual(sorted(str(p) for p in self.db.parent.rglob('*')), files)

    def test_invalid_inputs_rejected_before_worker(self):
        body = self.body()
        with patch.object(preview, 'run_worker', side_effect=AssertionError('no process')):
            for change in (dict(canny_low=True), dict(canny_low='0.4'), dict(canny_low=.8), dict(canny_high=1), dict(width=True), dict(width=65), dict(width=2048, height=2048), dict(image_asset_id='bad'), dict(reference_resize='crop'), dict(engine_url='http://example.test'), dict(checkpoint='anything'), dict(request_id='anything')):
                response = self.client.post('/api/control/preview', json=body | change)
                self.assertEqual(response.status_code, 422, change)

    def test_missing_archived_or_changed_asset_rejected_without_worker(self):
        body = self.body()
        path = self.db.parent / 'assets' / (body['image_asset_id'] + '.png')
        with patch.object(preview, 'run_worker', side_effect=AssertionError('no process')):
            raw = path.read_bytes()
            path.write_bytes(b'x' * len(raw))
            self.assertEqual(self.client.post('/api/control/preview', json=body).status_code, 422)
            path.write_bytes(raw)
            self.client.put('/api/assets/' + body['image_asset_id'], json=dict(title='archived', archived=True))
            self.assertEqual(self.client.post('/api/control/preview', json=body).status_code, 422)
            path.unlink()
            self.assertEqual(self.client.post('/api/control/preview', json=body).status_code, 422)

    def test_bad_worker_proof_never_becomes_preview(self):
        body = self.body()
        for change in (dict(method='unknown'), dict(device='cuda'), dict(width=True), dict(canny_low=.5), dict(input_sha256='a'*64), dict(sha256='b'*64), dict(native_sha256='c'*64), dict(torch='trace\ninvalid')):
            with patch.object(preview, 'run_worker', side_effect=lambda root, raw, settings: output(raw, settings, **change)):
                self.assertEqual(self.client.post('/api/control/preview', json=body).status_code, 503, change)
        for malformed in (b'invalid', b'{}\ninvalid', b'x'*4097+b'\ninvalid'):
            with patch.object(preview, 'run_worker', return_value=malformed):
                self.assertEqual(self.client.post('/api/control/preview', json=body).status_code, 503)

    def test_lock_owned_by_worker_and_released_on_failure(self):
        body = self.body()
        state = preview.Preview()
        state.lock.acquire()
        with self.assertRaises(preview.PreviewBusy):
            state.run(main.ROOT, self.db, self.db.parent, preview.Input.model_validate(body))
        state.lock.release()
        with patch.object(preview, 'run_worker', side_effect=preview.PreviewError('failed')):
            with self.assertRaises(preview.PreviewError):
                state.run(main.ROOT, self.db, self.db.parent, preview.Input.model_validate(body))
        self.assertTrue(state.lock.acquire(blocking=False))
        state.lock.release()

    def test_modified_or_missing_install_does_not_launch_process(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(preview.subprocess, 'Popen', side_effect=AssertionError('no process')):
            with self.assertRaises(preview.PreviewError):
                preview.run_worker(Path(folder), b'png', {})

    def test_fit_and_stretch_use_generation_preprocessing_and_thresholds(self):
        body = self.body() | dict(width=512, height=256)
        captured = []
        def worker(root, raw, settings):
            captured.append((raw, settings.copy()))
            return output(raw, settings)
        with patch.object(preview, 'run_worker', side_effect=worker):
            for resize, low in (('fit', .2), ('stretch', .4)):
                result = self.client.post('/api/control/preview', json=body | dict(reference_resize=resize, canny_low=low))
                self.assertEqual(result.status_code, 200, result.text)
        self.assertNotEqual(captured[0][0], captured[1][0])
        self.assertEqual(captured[0][1]['canny_low'], .2)


class ProcessTests(unittest.TestCase):
    def run_process(self, program, **limits):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = root / 'runtime/ComfyUI/comfy_extras/nodes_canny.py'
            source.parent.mkdir(parents=True)
            source.write_bytes(b'audited')
            python = root / 'runtime/ComfyUI/.venv' / ('Scripts/python.exe' if preview.os.name == 'nt' else 'bin/python')
            python.parent.mkdir(parents=True)
            python.touch()
            script = root / 'scripts/preview_canny.py'
            script.parent.mkdir()
            script.touch()
            original = subprocess.Popen
            processes = []
            def spawn(command, **kwargs):
                self.assertEqual(command, [str(python), '-I', '-B', str(script)])
                self.assertEqual(kwargs['env']['CUDA_VISIBLE_DEVICES'], '')
                process = original([sys.executable, '-I', '-c', program], **kwargs)
                processes.append(process)
                return process
            with patch.object(preview, 'NATIVE_SHA256', hashlib.sha256(b'audited').hexdigest()), patch.object(preview.subprocess, 'Popen', side_effect=spawn), patch.multiple(preview, **({'TIMEOUT': preview.TIMEOUT} | limits)):
                try:
                    return preview.run_worker(root, b'input', dict(width=64, height=64, canny_low=.4, canny_high=.8))
                finally:
                    self.assertEqual(len(processes), 1)
                    self.assertIsNotNone(processes[0].poll())
                    self.assertTrue(processes[0].stdout.closed)
                    self.assertTrue(processes[0].stdin.closed)

    def test_timeout_kills_and_reaps_child(self):
        with self.assertRaises(preview.PreviewError):
            self.run_process('import sys,time;sys.stdin.buffer.read();time.sleep(5)', TIMEOUT=.05)

    def test_output_overflow_kills_and_reaps_child(self):
        with self.assertRaises(preview.PreviewError):
            self.run_process('import sys;sys.stdin.buffer.read();sys.stdout.buffer.write(b"x"*20000);sys.stdout.flush()', MAX_BYTES=1024)

    def test_bounded_pipe_completes_and_suppresses_stderr(self):
        result = self.run_process('import sys;sys.stdin.buffer.read();sys.stderr.write("private paths");sys.stdout.buffer.write(b"ok")')
        self.assertEqual(result, b'ok')
