import asyncio
from pathlib import Path
import os
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch
from uuid import uuid4

from backend import compute_lease as compute, test_submissions, test_flux_workflows


class ComputeLeaseTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='atelier compute lease ')
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()

    def test_training_excludes_local_dispatch_but_not_remote(self):
        async def exercise():
            with compute.Reservation(self.root, 'training', 'fixture'):
                self.assertEqual(compute.status(self.root)['run_id'], 'fixture')
                with self.assertRaises(compute.ComputeBusy):
                    compute.check_training(self.root, 'http://localhost:8188')
                with self.assertRaises(compute.ComputeBusy):
                    async with compute.dispatch(self.root, 'http://127.0.0.1:8188'):
                        self.fail('training must exclude local dispatch')
                async with compute.dispatch(self.root, 'https://engine.invalid'):
                    pass
            self.assertFalse(compute.status(self.root)['active'])

        asyncio.run(exercise())

    def test_concurrent_inference_dispatches_wait_without_rejection(self):
        events = []

        async def submit(number):
            async with compute.dispatch(self.root, 'http://[::1]:8188'):
                events.append(('start', number))
                await asyncio.sleep(0.06)
                events.append(('end', number))

        async def exercise():
            await asyncio.gather(submit(1), submit(2))

        asyncio.run(exercise())
        self.assertEqual([event[0] for event in events], ['start', 'end', 'start', 'end'])

    def test_failed_metadata_write_releases_lease(self):
        with patch.object(compute, 'atomic_json', side_effect=OSError('fixture')):
            with self.assertRaises(OSError):
                with compute.Reservation(self.root, 'training'):
                    pass
        self.assertFalse(compute.status(self.root)['active'])

    def test_abrupt_worker_exit_releases_os_lock_without_manual_reset(self):
        marker = self.root / 'ready'
        code = (
            'import os,sys,time;from pathlib import Path;'
            'from backend.compute_lease import Reservation;'
            'lease=Reservation(Path(sys.argv[1]),"training","process-fixture");'
            'lease.__enter__();Path(sys.argv[2]).write_text("ready");time.sleep(30)'
        )
        process = subprocess.Popen(
            [sys.executable, '-c', code, str(self.root), str(marker)],
            cwd=Path(__file__).resolve().parents[1],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0,
        )
        try:
            deadline = time.monotonic() + 8
            while not marker.exists() and process.poll() is None and time.monotonic() < deadline:
                time.sleep(0.02)
            self.assertTrue(marker.exists())
            self.assertTrue(compute.status(self.root)['active'])
            process.terminate()
            process.wait(timeout=10)
            self.assertFalse(compute.status(self.root)['active'])
        finally:
            if process.poll() is None:
                process.kill()
                process.wait(timeout=10)
            process.stderr.close()


class ComputeApiTests(unittest.TestCase):
    setUp = test_submissions.SubmissionTests.setUp
    tearDown = test_submissions.SubmissionTests.tearDown
    payload = test_submissions.SubmissionTests.payload
    remote = test_submissions.SubmissionTests.remote

    def test_existing_uuid_recovers_while_new_local_generation_is_blocked(self):
        self.host.ROOT = self.db.parent
        body, remote = self.payload(), self.remote()
        with patch('backend.submissions.httpx.AsyncClient', return_value=remote):
            original = self.client.post('/api/generate', json=body)
            self.assertEqual(original.status_code, 200, original.text)
            with compute.Reservation(self.host.ROOT, 'training', 'fixture'):
                self.assertEqual(
                    self.client.post('/api/generate', json=body).json()['id'], original.json()['id']
                )
                self.assertEqual(
                    self.client.post('/api/generate', json=self.payload()).status_code, 409
                )
        self.assertEqual(remote.post.await_count, 1)
        self.assertEqual(len(self.client.get('/api/jobs').json()), 1)

    def test_training_starting_after_preflight_prevents_prompt_dispatch(self):
        self.host.ROOT = self.db.parent
        remote = self.remote()
        original = remote.get.side_effect
        reservation = None

        def get(url):
            nonlocal reservation
            if reservation is None:
                reservation = compute.Reservation(self.host.ROOT, 'training', 'fixture')
                reservation.__enter__()
            return original(url)

        remote.get.side_effect = get
        try:
            with patch('backend.submissions.httpx.AsyncClient', return_value=remote):
                response = self.client.post('/api/generate', json=self.payload())
            self.assertEqual(response.status_code, 409, response.text)
            self.assertEqual(response.json()['detail']['failure_info']['code'], 'training_busy')
            remote.post.assert_not_called()
        finally:
            if reservation is not None:
                reservation.__exit__(None, None, None)

    def test_flux_preserves_recovery_and_blocks_new_local_dispatch(self):
        case = test_flux_workflows.FluxWorkflowTests(
            'test_dedicated_graph_preserves_seed_and_loaders'
        )
        case.setUp()
        self.addCleanup(case.tearDown)
        case.host.ROOT = case.db.parent
        body, remote = case.body(), case.remote()
        original = case.submit(body, remote)
        self.assertEqual(original.status_code, 200, original.text)
        with compute.Reservation(case.host.ROOT, 'training', 'fixture'):
            self.assertEqual(case.submit(body, remote).json()['id'], original.json()['id'])
            self.assertEqual(
                case.submit(body | {'request_id': str(uuid4())}, remote).status_code, 409
            )
        self.assertEqual(remote.post.await_count, 1)
