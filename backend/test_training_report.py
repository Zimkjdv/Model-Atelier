import copy
from pathlib import Path
from uuid import uuid4
from unittest.mock import patch

from fastapi.testclient import TestClient
from backend import (
    compute_lease,
    training_files,
    training_runs as runs,
    training_report,
    training_control,
)
from backend.main import create_app
from backend.deployment_profile import Profile
from backend.test_training_runs import RunFixture


class ReportTests(RunFixture):
    def setUp(self):
        super().setUp()
        self.app = create_app(root=self.root, data_root=self.root / 'data')
        self.app.state.context.initialize()
        support = patch.object(
            training_control, 'supported', lambda host: host.deployment.kind == 'native'
        )
        support.start()
        self.addCleanup(support.stop)
        self.client = TestClient(
            self.app, base_url='http://127.0.0.1:8000', client=('127.0.0.1', 1)
        )
        self.addCleanup(self.client.close)
        self.run = self.prepare()
        self.uid = self.run['run_id']
        self.folder = runs.run_directory(self.uid, self.root)
        response = self.client.post('/api/training/runs/import', json=dict(run_id=self.uid))
        self.assertEqual(response.status_code, 200, response.text)
        self.endpoint = '/api/training/runs/' + self.uid + '/report'

    def test_default_report_is_read_only_and_omits_payload_paths_and_logs(self):
        compute_lease.atomic_json(
            self.folder / 'resources.json',
            dict(
                torch_peak_allocated_bytes=123,
                samples=[
                    dict(rss_bytes=100, whole_gpu_used_bytes=200, gpu_uuid='private-gpu-uuid')
                ],
                unknown=dict(secret='private-value'),
            ),
        )
        (self.folder / 'worker.log').write_text(
            'C:\\private\\user\\images api-key=private-log', encoding='utf-8'
        )
        before = training_files.file_manifest(self.folder)
        db = self.app.state.context.DB.read_bytes()
        original_open = Path.open

        def guarded(path, *args, **kwargs):
            if (
                path.name == 'worker.log'
                or 'work' in path.parts
                or 'output' in path.parts
                or path == self.checkpoint
            ):
                raise AssertionError('Reports must not read payload files or default logs')
            return original_open(path, *args, **kwargs)

        with (
            patch.object(Path, 'open', guarded),
            patch.object(runs, 'launch', side_effect=AssertionError('No worker')),
        ):
            response = self.client.get(self.endpoint)
        self.assertEqual(response.status_code, 200, response.text)
        value = response.json()
        self.assertEqual(value['kind'], 'model-atelier-training-report')
        self.assertEqual(value['observation']['status'], 'prepared')
        self.assertTrue(value['observation']['resources_released'])
        self.assertTrue(value['manifest']['matches_state'])
        self.assertFalse(value['scope']['logs_included'])
        self.assertFalse(value['scope']['payload_files_verified'])
        self.assertNotIn('log', value)
        for private in (
            'private-log',
            'private-gpu-uuid',
            'private-value',
            str(self.root),
            'Synthetic technical test',
        ):
            self.assertNotIn(private, response.text)
        self.assertEqual(value['resources']['samples'][0]['rss_bytes'], 100)
        self.assertEqual(training_files.file_manifest(self.folder), before)
        self.assertEqual(self.app.state.context.DB.read_bytes(), db)
        self.assertEqual(response.headers['cache-control'], 'no-store')
        self.assertIn(self.uid, response.headers['content-disposition'])

    def test_opt_in_log_tail_is_bounded_and_declares_local_text(self):
        text = '日誌測試\n' * 20000 + '最後一行'
        (self.folder / 'worker.log').write_bytes(text.encode('utf-8'))
        value = self.client.get(self.endpoint + '?include_logs=true').json()
        self.assertTrue(value['scope']['logs_included'])
        self.assertEqual(value['scope']['local_paths_included'], 'possible_in_log_or_message')
        self.assertTrue(value['log']['truncated'])
        self.assertEqual(value['log']['captured_bytes'], training_report.MAX_LOG)
        self.assertTrue(value['log']['text'].endswith('最後一行'))

    def test_missing_and_corrupt_records_keep_unknown_instead_of_claiming_release(self):
        (self.folder / 'state.json').write_text('{broken', encoding='utf-8')
        (self.folder / 'resources.json').write_bytes(b' ' * (training_report.MAX_JSON + 1))
        response = self.client.get(self.endpoint)
        self.assertEqual(response.status_code, 200, response.text)
        value = response.json()
        self.assertEqual(value['observation']['status'], 'unknown')
        self.assertIsNone(value['observation']['resources_released'])
        self.assertIsNone(value['resources'])
        self.assertEqual(value['metadata_files']['resources.json']['status'], 'unreadable')
        self.assertIsNone(value['manifest']['matches_state'])
        compute_lease.atomic_json(
            self.folder / 'state.json',
            dict(status='new-unknown-state', manifest_sha256=self.run['manifest_sha256']),
        )
        value = self.client.get(self.endpoint).json()
        self.assertEqual(value['observation']['status'], 'unknown')
        self.assertIsNone(value['observation']['resources_released'])
        (self.folder / 'manifest.json').unlink()
        self.assertEqual(self.client.get(self.endpoint).status_code, 200)

    def test_metadata_receipts_and_samples_are_limited_without_verifying_weights(self):
        for step in range(1, 121):
            compute_lease.atomic_json(
                self.folder / f'checkpoints/step-{step}.json',
                dict(
                    run_id=self.uid,
                    step=step,
                    manifest_sha256=self.run['manifest_sha256'],
                    files={'optimizer.bin': dict(sha256='a' * 64, size_bytes=123)},
                ),
            )
        compute_lease.atomic_json(
            self.folder / 'resources.json', dict(samples=[dict(rss_bytes=i) for i in range(120)])
        )
        compute_lease.atomic_json(
            self.folder / 'artifacts.json',
            dict(
                run_id=self.uid,
                manifest_sha256=self.run['manifest_sha256'],
                technical_only=True,
                files={'model.safetensors': dict(sha256='b' * 64, size_bytes=123)},
            ),
        )
        value = self.client.get(self.endpoint).json()
        self.assertEqual(value['checkpoints']['record_count'], 120)
        self.assertEqual(value['checkpoints']['retained'], 100)
        self.assertEqual(value['checkpoints']['receipts'][0]['step'], 21)
        self.assertEqual(value['resources']['sample_count'], 120)
        self.assertEqual(value['resources']['samples'][0]['rss_bytes'], 20)
        self.assertEqual(value['artifact']['final_weight']['sha256'], 'b' * 64)
        self.assertTrue(value['artifact']['matches_run'])
        self.assertFalse(value['scope']['payload_files_verified'])
        self.assertLess(len(training_report.encode(value)), training_report.MAX_REPORT)

    def test_manifest_mismatch_and_incomplete_start_are_reported_not_replayed(self):
        service = self.app.state.context.training_control
        service.put('training_start:' + self.uid, dict(requested_at=runs.now()))
        self.assertEqual(
            self.client.get(self.endpoint).json()['observation']['status'], 'start_unknown'
        )
        manifest = runs.read_json(self.folder / 'manifest.json')
        manifest['configuration']['rank'] = 16
        compute_lease.atomic_json(self.folder / 'manifest.json', manifest)
        value = self.client.get(self.endpoint).json()
        self.assertFalse(value['manifest']['matches_state'])
        self.assertIsNone(value['observation']['resources_released'])
        self.assertIn('manifest_state_mismatch', [v['code'] for v in value['issues']])

    def test_duplicate_keys_links_unknown_runs_and_container_boundary(self):
        (self.folder / 'resources.json').write_text('{"samples":[],"samples":[]}', encoding='utf-8')
        self.assertIsNone(self.client.get(self.endpoint).json()['resources'])
        original = training_report.Snapshot.path

        def linked(snapshot, name):
            if name == 'worker.log':
                raise ValueError('linked_record')
            return original(snapshot, name)

        with patch.object(training_report.Snapshot, 'path', linked):
            value = self.client.get(self.endpoint + '?include_logs=true').json()
        self.assertEqual(value['log']['status'], 'unreadable')
        self.assertEqual(
            self.client.get('/api/training/runs/' + str(uuid4()) + '/report').status_code, 404
        )
        self.app.state.context.deployment = Profile('container', ('172.18.0.1',))
        self.assertEqual(self.client.get(self.endpoint).status_code, 409)

    def test_encoder_rejects_oversize_and_nonfinite_report_values(self):
        report = self.client.get(self.endpoint).json()
        changed = copy.deepcopy(report)
        changed['oversize'] = 'x' * training_report.MAX_REPORT
        with self.assertRaises(ValueError):
            training_report.encode(changed)
        report['unknown'] = float('nan')
        with self.assertRaises(ValueError):
            training_report.encode(report)
