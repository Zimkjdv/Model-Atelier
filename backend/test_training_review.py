import copy
import io
import json
import shutil
from uuid import uuid4
from unittest.mock import patch
from PIL import Image
from fastapi.testclient import TestClient
from backend.main import create_app
from backend import training_review, training_bundle
from backend.deployment_profile import Profile
from backend.test_training_data import DatasetFixture


class ReviewTests(DatasetFixture):
    def setUp(self):
        super().setUp()
        (self.root / 'models').mkdir()
        shutil.copy('models/animagine-xl-4.0-opt.json', self.root / 'models')
        self.app = create_app(root=self.root, data_root=self.root / 'data')
        self.app.state.context.initialize()
        self.client = TestClient(
            self.app, base_url='http://127.0.0.1:8000', client=('127.0.0.1', 1)
        )
        self.addCleanup(self.client.close)

    def importing(self, **changes):
        payload = (
            dict(
                request_id=str(uuid4()),
                source_root=str(self.source),
                manifest_json=self.dataset.model_dump_json(),
            )
            | changes
        )
        return self.client.post('/api/training/datasets', json=payload)

    def saved(self):
        result = self.importing()
        self.assertEqual(result.status_code, 201, result.text)
        return result.json()

    def update(self, value, **changes):
        editable = (
            'id',
            'group_id',
            'split',
            'exclusion_reason',
            'exposure',
            'identity',
            'character_ids',
            'caption',
            'provenance',
        )
        return (
            dict(
                revision=value['revision'],
                version='v2',
                images=[
                    {k: copy.deepcopy(row[k]) for k in editable}
                    for row in value['dataset']['images']
                ],
            )
            | changes
        )

    def test_import_is_idempotent_without_approving_or_modifying_source(self):
        before = {p.name: p.read_bytes() for p in self.source.iterdir()}
        self.dataset.images[0].caption.status = 'pending'
        request_id = str(uuid4())
        first = self.importing(request_id=request_id).json()
        second = self.importing(request_id=request_id).json()
        self.assertEqual(first, second)
        self.assertEqual(first['dataset']['images'][0]['caption']['status'], 'pending')
        self.assertFalse(first['readiness']['data_ready'])
        self.assertEqual(before, {p.name: p.read_bytes() for p in self.source.iterdir()})
        self.assertEqual(len(self.client.get('/api/training/datasets').json()['datasets']), 1)
        self.assertEqual(
            self.importing(request_id=request_id, source_root=str(self.root)).status_code, 400
        )

    def test_immutable_versions_and_stale_edit_conflict(self):
        old = self.saved()
        endpoint = '/api/training/datasets/' + old['id']
        update = self.update(old)
        update['images'][0]['caption']['content'] = 'reviewed new caption'
        result = self.client.put(endpoint, json=update)
        self.assertEqual(result.status_code, 200, result.text)
        self.assertEqual(result.json()['revision'], 2)
        self.assertEqual(self.client.get(endpoint + '?revision=1').json(), old)
        self.assertEqual(self.client.put(endpoint, json=update).status_code, 409)
        downloaded = self.client.get(endpoint + '/manifest?revision=1').json()
        self.assertEqual(downloaded['version'], 'v1')
        self.assertNotEqual(downloaded['images'][0]['caption']['content'], 'reviewed new caption')

    def test_no_holdout_promotion_exposure_removal_or_forged_image_fields(self):
        self.dataset.images[0].exposure = ['tuning']
        old = self.saved()
        endpoint = '/api/training/datasets/' + old['id']
        for edit in (
            lambda v: v['images'][1].update(split='train'),
            lambda v: v['images'][0].update(exposure=[]),
            lambda v: v['images'][0].update(split='test'),
            lambda v: v['images'][0].update(path='../secret.png'),
            lambda v: v['images'][0].update(id=v['images'][1]['id']),
        ):
            update = self.update(old)
            edit(update)
            self.assertIn(self.client.put(endpoint, json=update).status_code, (400, 422))
        self.assertEqual(self.client.get(endpoint).json(), old)

    def test_exact_study_bytes_and_frozen_r02_holdout(self):
        document, sha = self.study()
        from backend import training_data as data

        raw = data.canonical(document).decode()
        self.dataset.parent_study = data.StudyAnchor(id=document['study_id'], sha256=sha)
        for row in self.dataset.images:
            row.exposure = ['r02_contact_sheet'] + (
                ['inference_reference'] if row.id == self.dataset.images[0].id else []
            )
        self.dataset.images[2].split = 'train'
        self.assertEqual(self.importing().status_code, 400)
        self.assertEqual(self.importing(study_json=raw + '\n').status_code, 400)
        response = self.importing(study_json=raw)
        self.assertEqual(response.status_code, 201, response.text)
        update = self.update(response.json())
        update['images'][1]['split'] = 'train'
        self.assertEqual(
            self.client.put(
                '/api/training/datasets/' + response.json()['id'], json=update
            ).status_code,
            400,
        )

    def test_previews_only_registered_images_and_fail_after_source_tamper(self):
        value = self.saved()
        endpoint = '/api/training/datasets/' + value['id']
        image_id = value['dataset']['images'][0]['id']
        result = self.client.get(endpoint + '/images/' + image_id + '?revision=1')
        self.assertEqual(result.status_code, 200)
        with Image.open(io.BytesIO(result.content)) as image:
            self.assertEqual(image.size, (48, 64))
        self.assertEqual(self.client.get(endpoint + '/images/missing?revision=1').status_code, 404)
        final_id = value['dataset']['images'][2]['id']
        self.assertEqual(
            self.client.get(endpoint + '/images/' + final_id + '?revision=1').status_code, 409
        )
        (self.source / 'a.png').write_bytes(b'changed')
        self.assertEqual(
            self.client.get(endpoint + '/images/' + image_id + '?revision=1').status_code, 400
        )
        self.assertFalse(self.client.post(endpoint + '/check').json()['data_ready'])

    def test_export_only_train_and_original_receipt_recovery(self):
        value = self.saved()
        endpoint = '/api/training/datasets/' + value['id'] + '/exports'
        request = dict(request_id=str(uuid4()), revision=1)
        first = self.client.post(endpoint, json=request).json()
        self.assertEqual(first['status'], 'completed', first)
        self.assertEqual(first['report']['train_count'], 1)
        path = self.root / 'data/training_bundles' / request['request_id']
        self.assertEqual(
            {p.name for p in (path / 'train').iterdir()}, {'img-0001.png', 'img-0001.txt'}
        )
        with patch.object(training_bundle, 'export', side_effect=AssertionError('must not replay')):
            self.assertEqual(self.client.post(endpoint, json=request).json(), first)
        self.assertEqual(
            self.client.get('/api/training/exports/' + request['request_id']).json(), first
        )

    def test_failed_export_preserves_id_and_never_seals_or_retries(self):
        value = self.saved()
        endpoint = '/api/training/datasets/' + value['id'] + '/exports'
        request = dict(request_id=str(uuid4()), revision=1)
        with patch.object(training_bundle, 'write_new', side_effect=OSError('disk unavailable')):
            result = self.client.post(endpoint, json=request).json()
        self.assertEqual(result['status'], 'failed')
        path = self.root / 'data/training_bundles' / request['request_id']
        self.assertFalse((path / 'bundle.json').exists())
        with patch.object(training_bundle, 'export', side_effect=AssertionError('must not replay')):
            self.assertEqual(self.client.post(endpoint, json=request).json(), result)

    def test_bad_json_duplicate_keys_and_container_profile(self):
        raw = self.dataset.model_dump_json().replace(
            '"schema_version":1', '"schema_version":1,"schema_version":1'
        )
        self.assertEqual(self.importing(manifest_json=raw).status_code, 400)
        self.app.state.context.deployment = Profile('container', ('172.18.0.1',))
        self.assertFalse(self.client.get('/api/training/datasets').json()['available'])
        self.assertEqual(self.importing().status_code, 409)

    def test_backup_checks_review_identity_and_completed_export_references(self):
        from backend import backup

        value = self.saved()
        result = self.client.post(
            '/api/training/datasets/' + value['id'] + '/exports',
            json=dict(request_id=str(uuid4()), revision=1),
        ).json()
        self.assertTrue(backup.inspect(self.root / 'data')['ok'])
        from pathlib import Path

        (Path(result['path']) / 'dataset.json').unlink()
        report = backup.inspect(self.root / 'data')
        self.assertFalse(report['ok'])
        self.assertIn('missing_file', {v['code'] for v in report['problems']})
