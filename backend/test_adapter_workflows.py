import copy
from contextlib import closing
import io
import sqlite3
import unittest
from unittest.mock import patch

import httpx
from PIL import Image

from backend import (
    adapter_catalog as records,
    adapter_workflows as flow,
    catalog,
    gallery,
    jobs,
    test_api,
    test_image_workflows,
)


def definitions():
    return {
        'LoadImage': dict(input=dict(required=dict(image=[[]])), output=['IMAGE', 'MASK']),
        'IPAdapterModelLoader': dict(
            input=dict(required=dict(ipadapter_file=[['plus.safetensors']])), output=['IPADAPTER']
        ),
        'CLIPVisionLoader': dict(
            input=dict(required=dict(clip_name=[['vision.safetensors']])), output=['CLIP_VISION']
        ),
        'IPAdapterAdvanced': dict(
            input=dict(
                required=dict(
                    model=['MODEL'],
                    ipadapter=['IPADAPTER'],
                    image=['IMAGE'],
                    weight=['FLOAT', dict(min=-1, max=5)],
                    weight_type=[['linear', 'style transfer']],
                    combine_embeds=[['concat']],
                    start_at=['FLOAT', dict(min=0, max=1)],
                    end_at=['FLOAT', dict(min=0, max=1)],
                    embeds_scaling=[['V only']],
                ),
                optional=dict(
                    image_negative=['IMAGE'], attn_mask=['MASK'], clip_vision=['CLIP_VISION']
                ),
            ),
            output=['MODEL'],
        ),
    }


class AdapterTests(unittest.TestCase):
    setUp = test_api.ApiTests.setUp
    tearDown = test_api.ApiTests.tearDown

    def test_catalog_reads_are_offline_sync_is_atomic_and_metadata_explicit(self):
        body = self.body()
        before = self.db.read_bytes()
        with patch.object(
            self.host, 'engine_client_factory', side_effect=AssertionError('no engine')
        ):
            self.assertEqual(self.client.get('/api/reference-components').status_code, 200)
        self.assertEqual(self.db.read_bytes(), before)

        def handler(request):
            name = request.url.path.rsplit('/', 1)[-1]
            return httpx.Response(
                200, json={name: definitions()[name]} if name != 'CLIPVisionLoader' else {}
            )

        with patch.object(
            self.host,
            'engine_client_factory',
            lambda **kw: httpx.AsyncClient(transport=httpx.MockTransport(handler), **kw),
        ):
            result = self.client.post(
                '/api/reference-components/sync', json=dict(comfy_url=body['engine_url'])
            )
        self.assertEqual(result.status_code, 200, result.text)
        self.assertTrue(result.json()['sync_error'])
        self.assertEqual(
            [r['name'] for r in result.json()['components']],
            ['vision.safetensors', 'plus.safetensors'],
        )
        self.assertTrue(
            all(r['listed'] and r['version'] == '1' for r in result.json()['components'])
        )
        self.assertEqual(
            self.client.put(
                '/api/reference-components/metadata',
                json=dict(
                    engine_url=body['engine_url'],
                    name='plus.safetensors',
                    role='ipadapter',
                    family='sd15',
                ),
            ).status_code,
            422,
        )

    def test_catalog_sync_engine_drift_cannot_publish_stale_list(self):
        body = self.body()

        def handler(request):
            name = request.url.path.rsplit('/', 1)[-1]
            if name == 'CLIPVisionLoader':
                with closing(sqlite3.connect(self.db)) as db, db:
                    db.execute(
                        "INSERT OR REPLACE INTO settings VALUES ('comfy_url', ?)",
                        ('http://127.0.0.1:9999',),
                    )
            return httpx.Response(200, json={name: definitions()[name]})

        original = records.read(self.db, body['engine_url'])
        with patch.object(
            self.host,
            'engine_client_factory',
            lambda **kw: httpx.AsyncClient(transport=httpx.MockTransport(handler), **kw),
        ):
            result = self.client.post(
                '/api/reference-components/sync', json=dict(comfy_url=body['engine_url'])
            )
        self.assertEqual(result.status_code, 409, result.text)
        self.assertEqual(records.read(self.db, body['engine_url']), original)

    def body(self):
        body = test_image_workflows.ImageWorkflowTests.body(self)
        records.merge(
            self.db,
            body['engine_url'],
            dict(ipadapter=['plus.safetensors'], clip_vision=['vision.safetensors']),
        )
        for role, name in [
            ('ipadapter', 'plus.safetensors'),
            ('clip_vision', 'vision.safetensors'),
        ]:
            spec = records.ROLES[role]
            records.update_metadata(
                self.db,
                body['engine_url'],
                role,
                name,
                dict(family=spec[2], architecture=spec[3], version='1', sha256='a' * 64),
            )
        return body | dict(
            workflow_mode='text2image',
            denoise=1,
            reference_mode='style',
            ipadapter_name='plus.safetensors',
            clip_vision_name='vision.safetensors',
            reference_weight=0.6,
            reference_start=0,
            reference_end=1,
        )

    def remote(self, body, change=None):
        remote = test_image_workflows.ImageWorkflowTests.remote(self, body)
        original = remote.get.side_effect

        async def get(url):
            name = url.rsplit('/', 1)[-1]
            if name in definitions():
                node = definitions()[name]
                if change:
                    node = change(name, node)
                return httpx.Response(
                    200,
                    request=httpx.Request('GET', url),
                    json={} if node is None else {name: node},
                )
            return await original(url)

        remote.get.side_effect = get
        return remote

    def submit(self, body, remote):
        with patch('backend.submissions.httpx.AsyncClient', return_value=remote):
            return self.client.post('/api/reference/generate', json=body)

    def test_modes_owned_source_empty_latent_exact_seed_and_snapshots(self):
        for mode, weight_type in [('style', 'style transfer'), ('character', 'linear')]:
            body = self.body() | dict(reference_mode=mode)
            remote = self.remote(body)
            response = self.submit(body, remote)
            self.assertEqual(response.status_code, 200, response.text)
            job = response.json()
            graph = job['workflow']
            self.assertEqual(len(graph), 11)
            self.assertEqual(graph['4']['class_type'], 'EmptyLatentImage')
            self.assertEqual(graph['5']['inputs']['model'], ['15', 0])
            self.assertEqual(graph['15']['inputs']['weight_type'], weight_type)
            self.assertEqual(graph['5']['inputs']['seed'], 2**64 - 1)
            self.assertEqual(job['workflow_id'], flow.ID)
            self.assertEqual(
                [r['role'] for r in job['component_metadata']], ['ipadapter', 'clip_vision']
            )
            self.assertEqual(job['reference_metadata'][0]['adapter_preprocessing']['mode'], mode)
            encoded = remote.post.await_args_list[0].kwargs['files']['image'][1]
            with Image.open(io.BytesIO(encoded)) as image:
                self.assertEqual(image.size, (224, 224))
                self.assertEqual(image.getpixel((0, 0)), (255, 255, 255))
            self.assertEqual(
                self.client.get('/api/jobs/' + job['id'] + '/reference-image').content, encoded
            )
            page = self.client.get('/api/library/jobs?workflow=reference').json()
            self.assertIn(job['id'], [j['id'] for j in page['items']])
            self.assertNotIn(
                job['id'],
                [
                    j['id']
                    for j in self.client.get('/api/library/jobs?workflow=checkpoint').json()[
                        'items'
                    ]
                ],
            )

    def test_invalid_inputs_never_contact_engine(self):
        body = self.body()
        for change in [
            dict(reference_mode='faceid'),
            dict(reference_start=1),
            dict(reference_end=0),
            dict(reference_weight=True),
            dict(reference_weight=2.1),
            dict(reference_resize='stretch'),
            dict(reference_ids=[]),
            dict(denoise=0.5),
            dict(width=8192, height=8192),
            dict(loras=[dict(name='a', enabled=False, strength_model=1, strength_clip=1)]),
            dict(unknown='x'),
        ]:
            with patch(
                'backend.submissions.httpx.AsyncClient', side_effect=AssertionError('no engine')
            ):
                self.assertEqual(
                    self.client.post('/api/reference/generate', json=body | change).status_code,
                    422,
                    change,
                )

    def test_wrong_architecture_family_and_unsynced_catalog_block_atomically(self):
        for change in [
            dict(family='unknown'),
            dict(family='clip-vit-h-14'),
            dict(architecture='sd1'),
        ]:
            body = self.body()
            records.update_metadata(
                self.db, body['engine_url'], 'ipadapter', body['ipadapter_name'], change
            )
            with patch(
                'backend.submissions.httpx.AsyncClient', side_effect=AssertionError('no engine')
            ):
                result = self.client.post('/api/reference/generate', json=body)
            self.assertEqual(result.status_code, 409, result.text)
        body = self.body()
        catalog.update_metadata(
            self.db, body['engine_url'], body['checkpoint'], dict(architecture='flux')
        )
        self.assertEqual(self.submit(body, self.remote(body)).status_code, 409)
        self.assertEqual(jobs.list_all(self.db), [])

    def test_snapshot_changed_before_reservation_leaves_no_job(self):
        body = self.body()
        settings = self.host.ReferenceInput.model_validate(
            {k: v for k, v in body.items() if k != 'request_id'}
        ).model_dump(mode='json', exclude={'revision'})
        components = [
            records.capture(r)
            for role in records.ROLES
            for r in records.read(self.db, body['engine_url'])['components']
            if r['role'] == role
        ]
        source, _ = flow.prepare(self.db, self.db.parent, settings)
        records.update_metadata(
            self.db, body['engine_url'], 'ipadapter', body['ipadapter_name'], dict(version='2')
        )
        model = catalog.capture(
            catalog.read(self.db, body['engine_url'])['models'][0], body['checkpoint']
        )
        with self.assertRaises(ValueError):
            jobs.reserve(
                self.db,
                body['request_id'],
                body['engine_url'],
                flow.build(settings, body['request_id']),
                body['checkpoint'],
                model_metadata=model,
                workflow_id=flow.ID,
                component_metadata=components,
                reference_metadata=[source],
                reference_settings=settings,
            )
        self.assertEqual(jobs.list_all(self.db), [])

    def test_changed_interface_enum_and_bounds_never_upload(self):
        for problem in ['missing', 'required', 'optional', 'weight', 'enum', 'file']:
            body = self.body()

            def change(name, node):
                if name == 'IPAdapterAdvanced':
                    if problem == 'missing':
                        return None
                    if problem == 'required':
                        node['input']['required']['extra'] = ['MODEL']
                    if problem == 'optional':
                        node['input']['optional'] = {}
                    if problem == 'weight':
                        node['input']['required']['weight'][1]['max'] = 0.1
                    if problem == 'enum':
                        node['input']['required']['weight_type'] = [['linear']]
                if name == 'CLIPVisionLoader' and problem == 'file':
                    node['input']['required']['clip_name'] = [[]]
                return node

            remote = self.remote(body, change)
            result = self.submit(body, remote)
            self.assertIn(result.status_code, [409, 422], result.text)
            remote.post.assert_not_awaited()

    def test_changed_during_validation_and_upload_never_prompt(self):
        for phase in ['validation', 'upload']:
            body = self.body()
            remote = self.remote(body)
            get, post = remote.get.side_effect, remote.post.side_effect

            def edit():
                records.update_metadata(
                    self.db,
                    body['engine_url'],
                    'ipadapter',
                    body['ipadapter_name'],
                    dict(version='2'),
                )

            async def changed_get(url):
                result = await get(url)
                if phase == 'validation' and url.endswith('/IPAdapterAdvanced'):
                    edit()
                return result

            async def changed_post(url, **kwargs):
                result = await post(url, **kwargs)
                if phase == 'upload':
                    edit()
                return result

            remote.get.side_effect, remote.post.side_effect = changed_get, changed_post
            result = self.submit(body, remote)
            self.assertEqual(result.status_code, 409, result.text)
            self.assertEqual(remote.post.await_count, 0 if phase == 'validation' else 1)

    def test_lost_response_and_original_recovery_precede_current_assets_engine_catalog(self):
        body = self.body()
        remote = self.remote(body)
        post = remote.post.side_effect

        async def lost(url, **kwargs):
            if url.endswith('/prompt'):
                raise httpx.ReadTimeout('unknown')
            return await post(url, **kwargs)

        remote.post.side_effect = lost
        first = self.submit(body, remote).json()
        self.assertEqual(first['status'], 'unknown')
        (self.db.parent / 'assets' / (self.asset['id'] + '.png')).unlink()
        self.client.put('/api/settings', json=dict(comfy_url='http://127.0.0.1:9999'))
        with patch(
            'backend.submissions.httpx.AsyncClient', side_effect=AssertionError('no engine')
        ):
            self.assertEqual(self.client.post('/api/reference/generate', json=body).json(), first)
            self.assertEqual(
                self.client.post(
                    '/api/reference/generate', json=body | dict(reference_mode='character')
                ).status_code,
                409,
            )
        self.assertEqual(remote.post.await_count, 2)

    def test_full_offline_job_and_artwork_restore_reject_partial_or_unknown_version(self):
        body = self.body()
        job = self.submit(body, self.remote(body)).json()
        self.assertIn('workflow', job, job)
        job = jobs.update(self.db, job['id'], status='completed')
        stream = io.BytesIO()
        Image.new('RGB', (512, 512), 'green').save(stream, format='PNG')
        item, _ = gallery.save(
            self.db,
            self.db.parent / 'artworks',
            job,
            dict(node_id='7', filename='test.png', subfolder='', type='output'),
            stream.getvalue(),
        )
        records.merge(self.db, body['engine_url'], dict(ipadapter=[], clip_vision=[]))
        with patch(
            'backend.submissions.httpx.AsyncClient', side_effect=AssertionError('no network')
        ):
            for path in ['/api/jobs/' + job['id'], '/api/artworks/' + item['id']]:
                result = self.client.get(path + '/creation-settings')
                self.assertEqual(result.status_code, 200, result.text)
                self.assertEqual(result.json()['settings'], job['reference_settings'])
                self.assertEqual(result.json()['component_metadata'], job['component_metadata'])
                self.assertTrue(any('參考元件' in w for w in result.json()['warnings']))
        for part in ['graph', 'preprocess', 'component', 'version']:
            value = copy.deepcopy(item)
            if part == 'graph':
                value['workflow']['15']['inputs']['weight_type'] = 'linear'
            if part == 'preprocess':
                value['reference_metadata'][0]['generation_preprocessing']['width'] = 512
            if part == 'component':
                value['component_metadata'].pop()
            if part == 'version':
                value['workflow_id'] = 'checkpoint-ipadapter-reference-v9'
            from backend import workflows

            with self.assertRaises(ValueError):
                workflows.extract(value, lambda v: v)
