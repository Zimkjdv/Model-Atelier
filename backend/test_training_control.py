import json
import shutil
import threading
import time
from pathlib import Path
from uuid import uuid4
from unittest.mock import patch
from fastapi.testclient import TestClient
from backend import compute_lease, training_runs as runs, training_data as data
from backend import training_control, training_artifacts
from backend.main import create_app
from backend.deployment_profile import Profile
from backend.test_training_runs import RunFixture


class ControlTests(RunFixture):
    def setUp(self):
        super().setUp()
        managed = self.root / 'runtime/ComfyUI/models/checkpoints'
        managed.mkdir(parents=True)
        shutil.copy(self.checkpoint, managed / 'animagine-xl-4.0-opt.safetensors')
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

    def exported(self):
        response = self.client.post(
            '/api/training/datasets',
            json=dict(
                request_id=str(uuid4()),
                source_root=str(self.source),
                manifest_json=self.dataset.model_dump_json(),
            ),
        )
        self.assertEqual(response.status_code, 201, response.text)
        response = self.client.post(
            '/api/training/datasets/' + response.json()['id'] + '/exports',
            json=dict(request_id=str(uuid4()), revision=1),
        )
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def payload(self):
        return dict(
            request_id=str(uuid4()),
            export_id=self.exported()['request_id'],
            label='API technical fixture',
            purpose='technical-smoke',
            resolution=512,
            max_steps=3,
            save_every_steps=1,
        )

    def wait_request(self, uid):
        for _ in range(200):
            result = self.client.get('/api/training/requests/' + uid).json()
            if result['status'] != 'preparing':
                return result
            time.sleep(0.01)
        self.fail('Preparation did not finish')

    def prepared(self):
        payload = self.payload()
        response = self.client.post('/api/training/requests', json=payload)
        self.assertEqual(response.status_code, 202, response.text)
        result = self.wait_request(payload['request_id'])
        self.assertEqual(result['status'], 'prepared', result)
        return payload, result

    def test_prepare_and_recovery_never_launch_or_change_frozen_settings(self):
        with patch.object(runs, 'launch', side_effect=AssertionError('No launch on prepare')):
            payload, result = self.prepared()
            self.assertEqual(
                self.client.post('/api/training/requests', json=payload).json(), result
            )
            changed = payload | dict(label='different')
            self.assertEqual(
                self.client.post('/api/training/requests', json=changed).status_code, 409
            )
            detail = self.client.get('/api/training/runs/' + result['run_id']).json()
            self.assertEqual(detail['status'], 'prepared')
            self.assertTrue(detail['resources_released'])
            self.assertFalse(detail['start_requested'])

    def test_unreviewed_export_cannot_be_prepared_and_failure_does_not_replay(self):
        self.dataset.images[0].caption.status = 'pending'
        payload = self.payload()
        self.client.post('/api/training/requests', json=payload)
        result = self.wait_request(payload['request_id'])
        self.assertEqual(result['status'], 'failed')
        with patch.object(runs, 'prepare', side_effect=AssertionError('No automatic retry')):
            self.assertEqual(
                self.client.post('/api/training/requests', json=payload).json(), result
            )

    def test_online_engine_blocks_without_start_marker_then_duplicate_dispatch_is_once(self):
        _, prepared = self.prepared()
        uid = prepared['run_id']
        endpoint = '/api/training/runs/' + uid
        with (
            patch.object(training_control, 'engine_online', return_value=True),
            patch.object(runs, 'launch') as launch,
        ):
            self.assertEqual(self.client.post(endpoint + '/start').status_code, 409)
            launch.assert_not_called()
        finish = threading.Event()
        entered = threading.Event()
        calls = []

        def worker(run_id, *, root):
            calls.append(run_id)
            folder = runs.run_directory(run_id, root)
            state = runs.read_json(folder / 'state.json')
            with compute_lease.Reservation(root, 'training', run_id):
                compute_lease.atomic_json(folder / 'state.json', state | dict(status='running'))
                entered.set()
                finish.wait(3)
            compute_lease.atomic_json(folder / 'state.json', state | dict(status='completed'))

        with (
            patch.object(training_control, 'engine_online', return_value=False),
            patch.object(runs, 'launch', side_effect=worker),
        ):
            try:
                self.assertEqual(self.client.post(endpoint + '/start').status_code, 202)
                self.assertTrue(entered.wait(1))
                self.assertFalse(self.client.get(endpoint).json()['resources_released'])
                self.assertEqual(self.client.post(endpoint + '/stop').status_code, 200)
                self.assertEqual(self.client.post(endpoint + '/stop').status_code, 200)
                self.assertEqual(self.client.post(endpoint + '/start').status_code, 202)
                self.assertEqual(calls, [uid])
            finally:
                finish.set()
                self.app.state.context.training_control.threads['run:' + uid].join(2)
        self.assertTrue(self.client.get(endpoint).json()['resources_released'])

    def test_worker_spawn_failure_releases_long_lived_controller_identity(self):
        _, prepared = self.prepared()
        uid = prepared['run_id']
        with (
            patch.object(training_control, 'engine_online', return_value=False),
            patch.object(
                runs.subprocess, 'Popen', side_effect=OSError('missing training interpreter')
            ),
        ):
            self.client.post('/api/training/runs/' + uid + '/start')
            self.app.state.context.training_control.threads['run:' + uid].join(2)
        result = self.client.get('/api/training/runs/' + uid).json()
        self.assertEqual(result['status'], 'failed', result)
        self.assertTrue(result['resources_released'])
        self.assertIn('could not start', result['state']['message'])

    def test_resume_requires_registered_original_and_creates_new_prepared_attempt(self):
        old, folder, _ = self.saved()
        uid = old['run_id']
        payload = dict(request_id=str(uuid4()), resume_run_id=uid, checkpoint='step-1')
        self.client.post('/api/training/resume-requests', json=payload)
        self.assertEqual(self.wait_request(payload['request_id'])['status'], 'failed')
        self.assertEqual(
            self.client.post('/api/training/runs/import', json=dict(run_id=uid)).status_code, 200
        )
        payload['request_id'] = str(uuid4())
        self.client.post('/api/training/resume-requests', json=payload)
        result = self.wait_request(payload['request_id'])
        self.assertEqual(result['status'], 'prepared', result)
        self.assertNotEqual(result['run_id'], uid)
        self.assertEqual(
            runs.read_json(runs.run_directory(result['run_id'], self.root) / 'manifest.json')[
                'resume'
            ]['step'],
            1,
        )
        self.assertEqual(runs.read_json(folder / 'state.json')['status'], 'stopped')

    def test_r02_study_is_carried_into_frozen_work_and_manifest(self):
        study, sha = self.study()
        self.dataset.parent_study = data.StudyAnchor(id=study['study_id'], sha256=sha)
        self.dataset.images[2].split = 'excluded'
        self.dataset.images[2].exclusion_reason = 'study fixture'
        for index, row in enumerate(self.dataset.images):
            row.exposure = ['r02_contact_sheet'] + (['inference_reference'] if index == 0 else [])
        response = self.client.post(
            '/api/training/datasets',
            json=dict(
                request_id=str(uuid4()),
                source_root=str(self.source),
                manifest_json=self.dataset.model_dump_json(),
                study_json=data.canonical(study).decode(),
            ),
        )
        self.assertEqual(response.status_code, 201, response.text)
        exported = self.client.post(
            '/api/training/datasets/' + response.json()['id'] + '/exports',
            json=dict(request_id=str(uuid4()), revision=1),
        ).json()
        self.assertEqual(exported['status'], 'completed', exported)
        payload = dict(
            request_id=str(uuid4()),
            export_id=exported['request_id'],
            label='R02 source continuity',
            max_steps=3,
        )
        self.client.post('/api/training/requests', json=payload)
        result = self.wait_request(payload['request_id'])
        self.assertEqual(result['status'], 'prepared', result)
        frozen = runs.read_json(runs.run_directory(result['run_id'], self.root) / 'manifest.json')
        self.assertEqual(frozen['parent_study']['sha256'], sha)
        self.assertIn('parent-study.json', frozen['frozen_files'])

    def test_evaluation_request_is_explicit_idempotent_and_uses_listener_origin(self):
        _, prepared = self.prepared()
        payload = dict(request_id=str(uuid4()), run_id=prepared['run_id'])
        with (
            patch.object(training_artifacts, 'evaluation') as evaluation,
            patch.object(
                training_artifacts,
                'save_plans',
                return_value=dict(plans=[], generation_started=False),
            ) as save,
        ):
            self.client.post(
                '/api/training/evaluation-requests',
                json=payload,
                headers={'Host': 'localhost:9999'},
            )
            result = self.wait_request(payload['request_id'])
            self.assertEqual(result['status'], 'completed', result)
            self.assertEqual(result['platform_url'], 'http://127.0.0.1:8000')
            self.client.post('/api/training/evaluation-requests', json=payload)
            self.assertEqual(evaluation.call_count, 1)
            self.assertEqual(save.call_count, 1)

    def test_container_arbitrary_flags_and_unknown_run_are_rejected(self):
        payload = self.payload()
        self.assertEqual(
            self.client.post(
                '/api/training/requests', json=payload | dict(extra_arguments=['--anything'])
            ).status_code,
            422,
        )
        self.assertEqual(
            self.client.post('/api/training/runs/' + str(uuid4()) + '/stop').status_code, 404
        )
        self.app.state.context.deployment = Profile('container', ('172.18.0.1',))
        self.assertFalse(self.client.get('/api/training/control').json()['available'])
        self.assertEqual(self.client.post('/api/training/requests', json=payload).status_code, 409)
