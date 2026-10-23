import copy
import unittest
from unittest.mock import patch
import httpx
from backend import test_inpaint_feather as old, catalog, jobs, fooocus_workflows as flow


def definitions():
    return {
        'INPAINT_LoadFooocusInpaint': dict(
            input=dict(
                required={
                    k: ['COMBO', dict(options=[w['filename'] for w in flow.WEIGHTS])]
                    for k in ('head', 'patch')
                }
            ),
            output=['INPAINT_PATCH'],
        ),
        'INPAINT_ApplyFooocusInpaint': dict(
            input=dict(required=dict(model=['MODEL'], patch=['INPAINT_PATCH'], latent=['LATENT'])),
            output=['MODEL'],
        ),
    }


class FooocusTests(unittest.TestCase):
    setUp = old.FeatherTests.setUp
    tearDown = old.FeatherTests.tearDown

    def body(self):
        body = old.FeatherTests.body(self) | dict(
            checkpoint=flow.BASE['filename'], denoise=1.0, inpaint_model='fooocus-v2.6'
        )
        catalog.merge(self.db, body['engine_url'], [body['checkpoint']])
        catalog.update_metadata(
            self.db,
            body['engine_url'],
            body['checkpoint'],
            dict(
                architecture='sdxl', sha256=flow.BASE['sha256'], size_bytes=flow.BASE['size_bytes']
            ),
        )
        return self.host.FooocusInput.model_validate(
            {k: v for k, v in body.items() if k != 'request_id'}
        ).model_dump(mode='json', exclude={'revision'}) | dict(request_id=body['request_id'])

    def remote(self, body, missing=False):
        remote = old.FeatherTests.remote(self, body)
        original = remote.get.side_effect

        async def get(url):
            name = url.rsplit('/', 1)[-1]
            if name == 'CheckpointLoaderSimple':
                return httpx.Response(
                    200,
                    request=httpx.Request('GET', url),
                    json={name: dict(input=dict(required=dict(ckpt_name=[[body['checkpoint']]])))},
                )
            if name in definitions():
                return httpx.Response(
                    200,
                    request=httpx.Request('GET', url),
                    json={} if missing else {name: definitions()[name]},
                )
            return await original(url)

        remote.get.side_effect = get
        return remote

    def submit(self, body, remote=None):
        with patch(
            'backend.submissions.httpx.AsyncClient', return_value=remote or self.remote(body)
        ):
            return self.client.post('/api/fooocus-inpaint/generate', json=body)

    def test_fixed_patch_exact_seed_original_masks_and_offline_restore(self):
        body = self.body()
        r = self.submit(body)
        self.assertEqual(r.status_code, 200, r.text)
        job = r.json()
        self.assertEqual(job['workflow']['5']['inputs']['model'], ['17', 0])
        self.assertEqual(job['workflow']['17']['inputs']['latent'], ['4', 0])
        self.assertEqual(job['workflow']['5']['inputs']['seed'], 2**64 - 1)
        self.assertEqual(job['reference_metadata'][0]['dedicated_inpaint'], flow.policy())
        jobs.update(self.db, job['id'], status='failed')
        with patch('backend.submissions.httpx.AsyncClient', side_effect=AssertionError('offline')):
            for suffix in (
                'creation-settings',
                'reference-image',
                'reference-mask',
                'reference-blend-mask',
            ):
                restored = self.client.get('/api/jobs/' + job['id'] + '/' + suffix)
                self.assertEqual(restored.status_code, 200, restored.text)
                if suffix == 'creation-settings':
                    self.assertEqual(restored.json()['settings'], job['reference_settings'])
            self.assertEqual(
                self.client.post('/api/fooocus-inpaint/generate', json=body).status_code, 200
            )

    def test_wrong_base_lora_denoise_or_old_endpoint_rejected(self):
        body = self.body()
        for change in (
            dict(checkpoint='other.safetensors'),
            dict(denoise=0.5),
            dict(inpaint_model='unknown'),
            dict(loras=[dict(name='lcm', enabled=True, strength_model=1.0, strength_clip=1.0)]),
        ):
            self.assertEqual(self.submit(body | change).status_code, 422)
        self.assertEqual(
            self.client.post('/api/inpaint-feather/generate', json=body).status_code, 422
        )

    def test_missing_nodes_or_changed_model_never_upload(self):
        body = self.body()
        remote = self.remote(body, missing=True)
        self.assertEqual(self.submit(body, remote).status_code, 422)
        self.assertEqual(remote.post.await_count, 0)
        body = self.body()
        catalog.update_metadata(
            self.db, body['engine_url'], body['checkpoint'], dict(sha256='a' * 64)
        )
        remote = self.remote(body)
        self.assertEqual(self.submit(body, remote).status_code, 409)
        self.assertEqual(remote.post.await_count, 0)

    def test_lost_response_recovers_without_replay(self):
        body = self.body()
        remote = self.remote(body)
        post = remote.post.side_effect

        async def lost(url, **kw):
            if url.endswith('/prompt'):
                raise httpx.ReadTimeout('unknown')
            return await post(url, **kw)

        remote.post.side_effect = lost
        self.assertEqual(self.submit(body, remote).json()['status'], 'unknown')
        self.assertEqual(self.submit(body, remote).json()['status'], 'unknown')
        self.assertEqual(remote.post.await_count, 4)

    def test_registration_changed_after_upload_never_prompts(self):
        body = self.body()
        remote = self.remote(body)
        post = remote.post.side_effect

        async def changed(url, **kw):
            result = await post(url, **kw)
            if url.endswith('/upload/image'):
                catalog.update_metadata(
                    self.db, body['engine_url'], body['checkpoint'], dict(version='changed')
                )
            return result

        remote.post.side_effect = changed
        self.assertEqual(self.submit(body, remote).status_code, 409)
        self.assertFalse(any(c.args[0].endswith('/prompt') for c in remote.post.await_args_list))

    def test_tampered_head_patch_or_snapshot_cannot_restore(self):
        body = self.body()
        job = self.submit(body).json()
        for part in ('graph', 'snapshot'):
            item = copy.deepcopy(job)
            item['source'] = dict(node_id='7')
            if part == 'graph':
                item['workflow']['16']['inputs']['patch'] = 'other.patch'
            else:
                item['reference_metadata'][0]['dedicated_inpaint']['weights'][0]['sha256'] = (
                    'a' * 64
                )
            with self.assertRaises(ValueError):
                flow.extract(item, lambda v: v)
