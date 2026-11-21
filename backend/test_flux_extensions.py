import io
import json
import sqlite3
import unittest
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from threading import Barrier
from unittest.mock import patch
from uuid import uuid4

import httpx
from PIL import Image

from backend import (
    assets,
    flux_extensions as flow,
    flux_observation,
    flux_workflows,
    gallery,
    jobs,
    loras,
    test_api,
    test_flux_catalog,
)
from scripts import flux_fixture


class FluxExtensionTests(unittest.TestCase):
    setUp = test_api.ApiTests.setUp
    tearDown = test_api.ApiTests.tearDown

    def body(self, image=False):
        flux_fixture.register(self.host, self.host.engine_url())
        value = flux_observation.SETTINGS | dict(
            engine_url=self.host.engine_url(), request_id=str(uuid4())
        )
        if image:
            raw = io.BytesIO()
            Image.new('RGB', (48, 64), 'red').save(raw, format='PNG')
            asset = assets.create(self.db, self.host.DATA / 'assets', raw.getvalue(), 'input.png')
            return value | dict(
                workflow_id=flow.IMAGE_ID,
                image_asset_id=asset['id'],
                denoise=0.6,
                reference_resize='fit',
            )
        return value | dict(
            workflow_id=flow.LORA_ID,
            lora_name='flux-schnell-pvc-style.safetensors',
            lora_strength=0.7,
        )

    def remote(self):
        remote = test_flux_catalog.remote_for(flux_fixture.definitions())

        async def post(url, **options):
            if url.endswith('/upload/image'):
                target = options['data']
                return httpx.Response(
                    200,
                    request=httpx.Request('POST', url),
                    json=dict(
                        name=options['files']['image'][0],
                        type=target['type'],
                        subfolder=target['subfolder'],
                    ),
                )
            return httpx.Response(
                200,
                request=httpx.Request('POST', url),
                json={'prompt_id': options['json']['prompt_id']},
            )

        remote.post.side_effect = post
        return remote

    def submit(self, body, remote):
        with patch('backend.flux_workflows.httpx.AsyncClient', return_value=remote):
            return self.client.post('/api/flux/extensions/generate', json=body)

    def test_lora_graph_snapshot_and_unknown_or_other_architecture_block(self):
        body = self.body()
        remote = self.remote()
        result = self.submit(body, remote)
        self.assertEqual(result.status_code, 200, result.text)
        job = result.json()
        self.assertEqual(job['workflow']['10']['class_type'], 'LoraLoaderModelOnly')
        self.assertEqual(job['workflow']['7']['inputs']['model'], ['10', 0])
        self.assertEqual(job['lora_metadata'][0]['strength_clip'], 0)
        self.assertEqual(remote.post.await_count, 1)
        self.assertEqual(
            self.client.get('/api/library/jobs?workflow=flux-addon').json()['items'][0]['id'],
            job['id'],
        )
        self.assertEqual(self.client.get('/api/library/jobs?workflow=flux').json()['items'], [])
        with patch(
            'backend.flux_workflows.httpx.AsyncClient', side_effect=AssertionError('replay')
        ):
            self.assertEqual(
                self.client.post('/api/flux/extensions/generate', json=body).json()['id'], job['id']
            )
        for changes in (dict(architecture='sdxl'), dict(sha256='f' * 64), dict(version='unknown')):
            body = self.body()
            loras.update_metadata(self.db, body['engine_url'], body['lora_name'], changes)
            remote = self.remote()
            self.assertEqual(self.submit(body, remote).status_code, 422)
            remote.post.assert_not_awaited()

    def test_image_preserves_upload_receipt_local_input_and_exact_restoration_offline(self):
        body = self.body(image=True)
        remote = self.remote()
        result = self.submit(body, remote)
        self.assertEqual(result.status_code, 200, result.text)
        job = result.json()
        self.assertEqual(job['workflow']['6']['class_type'], 'VAEEncode')
        self.assertEqual(job['workflow']['7']['inputs']['denoise'], 0.6)
        self.assertEqual(job['reference_metadata'][0]['id'], body['image_asset_id'])
        self.assertTrue((self.host.DATA / 'job_inputs' / (job['id'] + '.png')).is_file())
        saved_input = self.client.get('/api/jobs/' + job['id'] + '/reference-image')
        self.assertEqual(saved_input.status_code, 200)
        self.assertEqual(
            saved_input.content, (self.host.DATA / 'job_inputs' / (job['id'] + '.png')).read_bytes()
        )
        self.assertEqual(remote.post.await_count, 2)
        self.assertEqual(
            remote.post.await_args_list[0].args[0].rsplit('/', 2)[-2:], ['upload', 'image']
        )
        jobs.update(self.db, job['id'], status='failed')
        with patch(
            'backend.flux_workflows.httpx.AsyncClient', side_effect=AssertionError('offline')
        ):
            restored = self.client.get('/api/flux/jobs/' + job['id'] + '/creation-settings')
            self.assertEqual(restored.status_code, 200, restored.text)
            self.assertEqual(restored.json()['settings']['seed'], body['seed'])
            self.assertEqual(restored.json()['settings']['image_asset_id'], body['image_asset_id'])
        raw = io.BytesIO()
        Image.new('RGB', (512, 512)).save(raw, format='PNG')
        item, _ = gallery.save(
            self.db,
            self.host.DATA / 'artworks',
            jobs.get(self.db, job['id']),
            dict(filename='image.png', subfolder='', type='output', node_id='9'),
            raw.getvalue(),
        )
        self.assertEqual(flux_workflows.extract(item)['denoise'], 0.6)
        item['workflow']['7']['inputs']['denoise'] = 1
        with self.assertRaises(ValueError):
            flux_workflows.extract(item)

    def test_failed_upload_never_dispatches_and_same_uuid_never_uploads_again(self):
        body, remote = self.body(image=True), self.remote()
        remote.post.side_effect = httpx.ReadTimeout('receipt lost')
        self.assertEqual(self.submit(body, remote).status_code, 502)
        job = jobs.get(self.db, body['request_id'])
        self.assertEqual(job['failure_info']['code'], 'reference_input_failed')
        self.assertEqual(remote.post.await_count, 1)
        self.assertEqual(self.submit(body, remote).json()['id'], job['id'])
        self.assertEqual(remote.post.await_count, 1)

    def test_union_rejects_mixed_modes_and_unvalidated_profile_before_writes(self):
        body = self.body()
        for change in (
            dict(image_asset_id=str(uuid4())),
            dict(loras=[]),
            dict(lora_strength=float('inf')),
        ):
            if any(isinstance(v, float) for v in change.values()):
                continue  # JSON itself rejects nonfinite values; Pydantic checked below.
            self.assertEqual(
                self.client.post('/api/flux/extensions/generate', json=body | change).status_code,
                422,
            )
        with self.assertRaises(ValueError):
            flow.LoraInput(
                **{k: v for k, v in body.items() if k != 'request_id'}
                | dict(lora_strength=float('inf'))
            )
        for change in (
            dict(width=1024),
            dict(encoder_device='default'),
            dict(weight_dtype='default'),
        ):
            remote = self.remote()
            self.assertEqual(self.submit(body | change, remote).status_code, 422)
            remote.post.assert_not_awaited()

    def test_versioned_drafts_preview_and_general_format_refusal(self):
        body = self.body(image=True)
        body.pop('request_id')
        draft = self.client.post('/api/flux/extensions/drafts', json=body)
        self.assertEqual(draft.status_code, 200, draft.text)
        saved = draft.json()
        self.assertEqual(self.client.get('/api/flux/drafts').json(), [])
        self.assertEqual(
            self.client.put(
                '/api/flux/extensions/drafts/' + saved['id'], json=body | {'revision': 1}
            ).json()['revision'],
            2,
        )
        self.assertEqual(
            self.client.put(
                '/api/flux/extensions/drafts/' + saved['id'], json=body | {'revision': 1}
            ).status_code,
            409,
        )
        preview = self.client.post('/api/flux/extensions/workflow', json=body)
        self.assertEqual(preview.status_code, 200, preview.text)
        self.assertIn('"seed": 9007199254740993', preview.json()['workflow_json'])
        self.assertEqual(self.client.post('/api/flux/drafts', json=body).status_code, 422)
        self.assertEqual(jobs.list_all(self.db), [])

    def test_image_drafts_protect_the_current_asset_and_allow_rename(self):
        drafts_url = '/api/flux/extensions/drafts'
        for existing in (False, True):
            with self.subTest(existing=existing):
                body = self.body(image=True)
                body.pop('request_id')
                replacement_id = self.body(image=True)['image_asset_id']
                source_url = '/api/assets/' + body['image_asset_id']
                replacement_url = '/api/assets/' + replacement_id
                if existing:
                    draft_id = str(uuid4())
                    timestamp = '2026-10-25T00:00:00+00:00'
                    record = dict(
                        body, id=draft_id, revision=1, created_at=timestamp, updated_at=timestamp
                    )
                    with closing(sqlite3.connect(self.db)) as db, db:
                        db.execute(
                            'INSERT INTO settings VALUES (?, ?)',
                            ('flux_extension_draft:' + draft_id, json.dumps(record)),
                        )
                else:
                    saved = self.client.post(drafts_url, json=body)
                    self.assertEqual(saved.status_code, 200, saved.text)
                    draft_id = saved.json()['id']
                self.assertEqual(
                    self.client.get(source_url + '/usage').json()['drafts'], [draft_id]
                )

                source = self.client.get(source_url).json()
                update = dict(title='Renamed input', revision=source['revision'])
                blocked = self.client.put(source_url, json=dict(update, archived=True))
                self.assertEqual(blocked.status_code, 409, blocked.text)
                renamed = self.client.put(source_url, json=dict(update, archived=False))
                self.assertEqual(renamed.status_code, 200, renamed.text)
                self.assertEqual(renamed.json()['title'], update['title'])
                self.assertFalse(renamed.json()['archived'])

                draft_url = drafts_url + '/' + draft_id
                changed = self.client.put(
                    draft_url, json=dict(body, image_asset_id=replacement_id, revision=1)
                )
                self.assertEqual(changed.status_code, 200, changed.text)
                self.assertEqual(changed.json()['image_asset_id'], replacement_id)
                self.assertEqual(self.client.get(source_url + '/usage').json()['drafts'], [])
                self.assertEqual(
                    self.client.get(replacement_url + '/usage').json()['drafts'], [draft_id]
                )
                blocked = self.client.put(
                    replacement_url, json=dict(title='Replacement', revision=1, archived=True)
                )
                self.assertEqual(blocked.status_code, 409, blocked.text)
                archived = self.client.put(
                    source_url,
                    json=dict(update, revision=renamed.json()['revision'], archived=True),
                )
                self.assertEqual(archived.status_code, 200, archived.text)
                self.assertTrue(archived.json()['archived'])
                restored_binding = self.client.put(
                    draft_url, json=dict(body, revision=changed.json()['revision'])
                )
                self.assertEqual(restored_binding.status_code, 409, restored_binding.text)

    def test_image_draft_save_racing_archive_keeps_the_asset_binding_consistent(self):
        drafts_url = '/api/flux/extensions/drafts'
        body = self.body(image=True)
        body.pop('request_id')
        source_url = '/api/assets/' + body['image_asset_id']
        source = self.client.get(source_url).json()
        ready = Barrier(2, timeout=5)

        def save_draft():
            ready.wait()
            return self.client.post(drafts_url, json=body)

        def archive_asset():
            ready.wait()
            return self.client.put(
                source_url,
                json=dict(title=source['title'], revision=source['revision'], archived=True),
            )

        with ThreadPoolExecutor(max_workers=2) as pool:
            saving = pool.submit(save_draft)
            archiving = pool.submit(archive_asset)
            saved = saving.result()
            archived = archiving.result()
        self.assertCountEqual(
            [saved.status_code, archived.status_code], [200, 409], (saved.text, archived.text)
        )
        current = self.client.get(source_url).json()
        usage = self.client.get(source_url + '/usage').json()['drafts']
        if saved.status_code == 200:
            self.assertFalse(current['archived'])
            self.assertEqual(usage, [saved.json()['id']])
        else:
            self.assertTrue(current['archived'])
            self.assertEqual(usage, [])
            self.assertEqual(self.client.get(drafts_url).json(), [])
