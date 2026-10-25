import io
import json
import unittest
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
