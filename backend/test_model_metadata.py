import copy
import io
import json
import sqlite3
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from datetime import datetime, timezone
from unittest.mock import patch
from uuid import uuid4

import httpx
from PIL import Image

from backend import catalog, gallery, jobs, test_api, test_submissions, workflows

CLIENT = httpx.AsyncClient
ENGINE = 'http://127.0.0.1:8188'
CHECKPOINT = 'test.safetensors'


class ModelMetadataTests(unittest.TestCase):
    setUp = test_api.ApiTests.setUp
    tearDown = test_api.ApiTests.tearDown
    sync = test_api.ApiTests.sync
    remote = test_submissions.SubmissionTests.remote

    def target(self, **changes):
        return dict(engine_url=ENGINE, name=CHECKPOINT) | changes

    def metadata(self, **changes):
        return dict(version=' V6 XL ', notes='manually registered', source_url='https://example.com/model/',
                    architecture='sdxl', size_bytes=6938078334, sha256='A' * 64,
                    license_name='Example license', license_url='https://example.com/license/') | changes

    def register(self, **changes):
        response = self.client.put('/api/models/metadata', json=self.target() | changes)
        self.assertEqual(response.status_code, 200, response.text)
        return next(item for item in response.json()['models'] if item['name'] == CHECKPOINT)

    def body(self):
        return dict(request_id=str(uuid4()), engine_url=ENGINE, checkpoint=CHECKPOINT, title='metadata test',
                    prompt='a forest', negative_prompt='blurry', width=512, height=512, seed='9007199254740993',
                    steps=20, cfg=7.0, sampler_name='euler', scheduler='normal', denoise=1.0)

    def submit(self, body):
        remote = self.remote()
        with patch('backend.submissions.httpx.AsyncClient', return_value=remote):
            response = self.client.post('/api/generate', json=body)
        self.assertEqual(response.status_code, 200, response.text)
        return response.json(), remote

    def complete(self, job):
        return jobs.update(self.db, job['id'], status='completed', history={
            'status': {'completed': True, 'status_str': 'success'},
            'outputs': {'7': {'images': [dict(filename='result.png', subfolder='', type='output')]}}})

    def import_artwork(self, job):
        image = io.BytesIO()
        Image.new('RGB', (512, 512), '#718d76').save(image, 'PNG')
        with patch('backend.gallery_api.httpx.AsyncClient', side_effect=lambda **kwargs:
                   CLIENT(transport=httpx.MockTransport(lambda request: httpx.Response(200, content=image.getvalue())), **kwargs)):
            response = self.client.post('/api/jobs/' + job['id'] + '/artworks')
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()['errors'], [])
        return (response.json()['imported'] or response.json()['existing'])[0]

    def stored(self, key):
        with closing(sqlite3.connect(self.db)) as db:
            return db.execute('SELECT value FROM settings WHERE key=?', (key,)).fetchone()[0]

    def write_stored(self, key, value):
        with closing(sqlite3.connect(self.db)) as db, db:
            db.execute('INSERT OR REPLACE INTO settings VALUES (?, ?)', (key, json.dumps(value)))

    def test_legacy_catalog_defaults_are_unknown_and_reads_do_not_rewrite(self):
        legacy = dict(engine_url=ENGINE, models=[dict(name='flux-sdxl-v6.safetensors', listed=True)],
                      selected=None, synced_at=None, sync_error=None)
        self.write_stored('catalog:' + ENGINE, legacy)
        before = self.stored('catalog:' + ENGINE)
        model = self.client.get('/api/models').json()['models'][0]
        for key, value in catalog.METADATA_DEFAULTS.items():
            self.assertEqual(model[key], value, key)
        self.assertEqual(model['architecture'], 'unknown')
        self.assertEqual(model['origin'], 'user_registered')
        self.assertEqual(self.stored('catalog:' + ENGINE), before)

    def test_registration_normalizes_and_timestamp_and_origin_are_server_controlled(self):
        self.sync([CHECKPOINT])
        model = self.register(**self.metadata(), metadata_updated_at='2000-01-01', origin='verified_file')
        self.assertEqual(model['version'], 'V6 XL')
        self.assertEqual(model['sha256'], 'a' * 64)
        self.assertEqual(model['size_bytes'], 6938078334)
        self.assertEqual(model['source_url'], 'https://example.com/model')
        self.assertEqual(model['license_url'], 'https://example.com/license')
        self.assertEqual(model['origin'], 'user_registered')
        updated = datetime.fromisoformat(model['metadata_updated_at'])
        self.assertEqual(updated.utcoffset(), timezone.utc.utcoffset(updated))
        self.assertLess(abs((datetime.now(timezone.utc) - updated).total_seconds()), 30)
        self.assertNotIn('verified_file', json.dumps(model))

    def test_old_client_and_partial_updates_preserve_omitted_fields(self):
        self.sync([CHECKPOINT])
        first = self.register(**self.metadata())
        updated = self.register(version='v2')
        for field in ('notes', 'source_url', 'architecture', 'size_bytes', 'sha256', 'license_name', 'license_url'):
            self.assertEqual(updated[field], first[field], field)
        unchanged = self.register()
        self.assertEqual(unchanged, updated)
        self.assertEqual(self.register(notes='new notes')['version'], 'v2')

    def test_explicit_null_and_empty_clear_only_requested_fields(self):
        self.sync([CHECKPOINT])
        first = self.register(**self.metadata())
        cleared = self.register(size_bytes=None, sha256=None, license_url='', architecture=None, source_url=None)
        self.assertIsNone(cleared['size_bytes'])
        self.assertEqual(cleared['sha256'], '')
        self.assertEqual(cleared['license_url'], '')
        self.assertEqual(cleared['source_url'], '')
        self.assertEqual(cleared['architecture'], 'unknown')
        self.assertEqual(cleared['version'], first['version'])
        self.assertEqual(cleared['license_name'], first['license_name'])
        final = self.register(version=None, notes=None, license_name=None, architecture='', size_bytes='')
        self.assertEqual(final['version'], '')
        self.assertEqual(final['notes'], '')
        self.assertEqual(final['license_name'], '')
        self.assertIsNone(final['size_bytes'])

    def test_invalid_metadata_is_rejected_without_any_write(self):
        self.sync([CHECKPOINT])
        self.register(**self.metadata())
        before = self.stored('catalog:' + ENGINE)
        invalid = [dict(size_bytes=value) for value in (0, -1, True, False, 1.0, '123', 9007199254740992)]
        invalid += [dict(sha256=value) for value in ('a' * 63, 'a' * 65, 'z' * 64, 'sha256:' + 'a' * 64)]
        invalid += [dict(architecture=value) for value in ('SDXL', 'pony', True)]
        invalid += [dict(license_name='x' * 201)]
        invalid += [dict(**{field: value}) for field in ('source_url', 'license_url') for value in (
            'javascript:alert(1)', 'file:///x', 'http://user:pass@localhost', 'https://example.com/a?q=1',
            'https://example.com/#fragment', 'http://localhost:99999')]
        for changes in invalid:
            with self.subTest(changes=changes):
                response = self.client.put('/api/models/metadata', json=self.target() | changes)
                self.assertEqual(response.status_code, 422, response.text)
                self.assertEqual(self.stored('catalog:' + ENGINE), before)
        self.assertEqual(self.register(size_bytes=9007199254740991)['size_bytes'], 9007199254740991)

    def test_metadata_is_engine_scoped_and_stale_edits_fail(self):
        self.sync([CHECKPOINT])
        original = self.register(**self.metadata())
        other = 'http://127.0.0.1:9000'
        self.client.put('/api/settings', json={'comfy_url': other})
        self.assertEqual(self.client.put('/api/models/metadata', json=self.target(version='wrong')).status_code, 409)
        self.sync([CHECKPOINT])
        response = self.client.put('/api/models/metadata', json=self.target(engine_url=other, version='other', architecture='sd1'))
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(catalog.read(self.db, ENGINE)['models'][0], original)
        self.assertEqual(catalog.read(self.db, other)['models'][0]['architecture'], 'sd1')
        self.assertEqual(self.client.put('/api/models/metadata', json=self.target(engine_url=other, name='missing')).status_code, 404)

    def test_success_empty_sync_and_failure_preserve_registered_fields(self):
        self.sync([CHECKPOINT])
        first = self.register(**self.metadata())
        for response in (self.sync(['new.safetensors']), self.sync(broken=True), self.sync()):
            model = next(item for item in response['models'] if item['name'] == CHECKPOINT)
            self.assertFalse(model['listed'])
            self.assertEqual({key: value for key, value in model.items() if key != 'listed'},
                             {key: value for key, value in first.items() if key != 'listed'})
        restored = next(item for item in self.sync([CHECKPOINT])['models'] if item['name'] == CHECKPOINT)
        self.assertTrue(restored['listed'])
        self.assertEqual(restored['metadata_updated_at'], first['metadata_updated_at'])

    def test_cross_process_style_partial_edits_and_syncs_do_not_lose_metadata(self):
        self.sync([CHECKPOINT])
        start = threading.Barrier(3)
        def change(field, value):
            start.wait(timeout=5)
            for _ in range(10):
                catalog.update_metadata(self.db, ENGINE, CHECKPOINT, {field: value})
        def sync():
            start.wait(timeout=5)
            for _ in range(10):
                catalog.merge(self.db, ENGINE, [CHECKPOINT])
                catalog.sync_error(self.db, ENGINE, 'offline')
        with ThreadPoolExecutor(max_workers=3) as pool:
            futures = [pool.submit(change, 'version', 'v1'), pool.submit(change, 'sha256', 'b' * 64), pool.submit(sync)]
            for future in futures:
                future.result(timeout=15)
        model = catalog.read(self.db, ENGINE)['models'][0]
        self.assertEqual(model['version'], 'v1')
        self.assertEqual(model['sha256'], 'b' * 64)

    def test_submission_and_import_capture_original_metadata_and_keep_generation_parameters(self):
        self.sync([CHECKPOINT])
        model = self.register(**self.metadata())
        body = self.body()
        job, remote = self.submit(body)
        snapshot = job['model_metadata']
        expected = {key: model[key] for key in ('name', 'version', 'source_url', 'architecture', 'size_bytes', 'sha256',
                                               'license_name', 'license_url', 'metadata_updated_at', 'origin')}
        self.assertEqual({key: snapshot[key] for key in expected}, expected)
        self.assertEqual(snapshot['version'], job['model_version'])
        self.assertEqual(datetime.fromisoformat(snapshot['captured_at']).utcoffset(), timezone.utc.utcoffset(None))
        self.assertEqual(remote.post.call_args.kwargs['json']['prompt'], workflows.build(body))
        self.register(version='new', architecture='flux', sha256='b' * 64, license_name='changed')
        item = self.import_artwork(self.complete(job))
        self.assertEqual(item['model_metadata'], snapshot)
        self.assertEqual(item['model_version'], 'V6 XL')
        detail = self.client.get('/api/artworks/' + item['id']).json()
        self.assertEqual(detail['model_metadata'], snapshot)
        self.assertEqual(self.client.get('/api/artworks').json()[0]['model_metadata'], snapshot)
        restored = self.client.get('/api/artworks/' + item['id'] + '/creation-settings').json()
        self.assertEqual(restored['model_metadata'], snapshot)
        for key, value in body.items():
            if key not in ('request_id', 'title'):
                self.assertEqual(restored['settings'][key], value)
        self.assertEqual(self.import_artwork(job | dict(status='completed', history=self.complete(job)['history']))['model_metadata'], snapshot)

    def test_replay_returns_original_snapshot_without_new_catalog_or_engine_probe(self):
        self.sync([CHECKPOINT])
        self.register(**self.metadata())
        body = self.body()
        job, _ = self.submit(body)
        self.register(version='v2', sha256='b' * 64)
        self.client.put('/api/settings', json={'comfy_url': 'http://127.0.0.1:9000'})
        with (patch('backend.submissions.catalog.read', side_effect=AssertionError('must not recapture')),
              patch('backend.submissions.httpx.AsyncClient', side_effect=AssertionError('must not submit'))):
            response = self.client.post('/api/generate', json=body)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()['model_metadata'], job['model_metadata'])
        self.assertEqual(response.json()['model_version'], job['model_version'])

    def test_unknown_new_submission_still_has_a_complete_unknown_snapshot(self):
        job, _ = self.submit(self.body())
        metadata = job['model_metadata']
        self.assertEqual(metadata['name'], CHECKPOINT)
        self.assertEqual(metadata['version'], '未知')
        self.assertEqual(metadata['architecture'], 'unknown')
        self.assertIsNone(metadata['size_bytes'])
        self.assertIsNone(metadata['metadata_updated_at'])
        self.assertEqual(metadata['sha256'], '')
        self.assertEqual(metadata['origin'], 'user_registered')

    def test_legacy_job_and_artwork_metadata_are_not_backfilled(self):
        body = self.body()
        job, _ = jobs.reserve(self.db, body['request_id'], ENGINE, workflows.build(body), CHECKPOINT, 'old-v1')
        job.pop('model_metadata')
        self.write_stored('job:' + job['id'], job)
        self.sync([CHECKPOINT])
        self.register(**self.metadata())
        with patch('backend.submissions.httpx.AsyncClient', side_effect=AssertionError('must not submit')):
            replay = self.client.post('/api/generate', json=body).json()
        self.assertNotIn('model_metadata', replay)
        item = self.import_artwork(self.complete(job))
        self.assertIsNone(item['model_metadata'])
        original_artwork = gallery.get(self.db, item['id'])
        original_artwork.pop('model_metadata')
        self.write_stored('artwork:' + item['id'], original_artwork)
        before = self.stored('artwork:' + item['id'])
        restored = self.client.get('/api/artworks/' + item['id'] + '/creation-settings')
        self.assertEqual(restored.status_code, 200, restored.text)
        self.assertIsNone(restored.json()['model_metadata'])
        repeated = self.import_artwork(self.complete(job))
        self.assertNotIn('model_metadata', repeated)
        self.assertEqual(self.stored('artwork:' + item['id']), before)

    def test_ledger_refuses_snapshot_replacement_and_reservation_copies_the_input(self):
        self.sync([CHECKPOINT])
        model = self.register(**self.metadata())
        body = self.body()
        metadata = catalog.capture(model, CHECKPOINT)
        original = copy.deepcopy(metadata)
        job, _ = jobs.reserve(self.db, body['request_id'], ENGINE, workflows.build(body), CHECKPOINT, 'V6 XL', metadata)
        metadata['sha256'] = 'c' * 64
        self.assertEqual(job['model_metadata'], original)
        repeated, fresh = jobs.reserve(self.db, body['request_id'], ENGINE, workflows.build(body), CHECKPOINT, 'v2', metadata)
        self.assertFalse(fresh)
        self.assertEqual(repeated['model_metadata'], original)
        for changes in (dict(model_metadata=metadata), dict(model_metadata=None), dict(model_version='new')):
            with self.assertRaises(ValueError):
                jobs.update(self.db, job['id'], **changes)
            with self.assertRaises(ValueError):
                jobs.compare_update(self.db, job, **changes)
        self.assertEqual(jobs.get(self.db, job['id'])['model_metadata'], original)
