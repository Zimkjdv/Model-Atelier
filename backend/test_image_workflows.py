import copy
import io
import json
import unittest
from unittest.mock import patch
from uuid import uuid4

import httpx
from PIL import Image
from backend import assets, catalog, gallery, image_workflows, jobs, loras, main, test_api, test_lora_submissions, test_submissions
from backend.reference_workflows import IMG2IMG_ID


class ImageWorkflowTests(unittest.TestCase):
    setUp = test_api.ApiTests.setUp
    tearDown = test_api.ApiTests.tearDown

    def body(self):
        stream = io.BytesIO()
        Image.new('RGBA', (80, 64), (90, 130, 100, 128)).save(stream, format='PNG')
        self.asset = assets.create(self.db, self.db.parent / 'assets', stream.getvalue(), '風景.png')
        body = test_submissions.SubmissionTests.payload(self)
        catalog.merge(self.db, body['engine_url'], [body['checkpoint']])
        catalog.update_metadata(self.db, body['engine_url'], body['checkpoint'], dict(architecture='sdxl', version='v1'))
        return body | dict(workflow_mode='image2image', reference_ids=[self.asset['id']], image_asset_id=self.asset['id'], reference_resize='fit', denoise=0.45)

    def remote(self, body, *, receipt=None, hook=None):
        remote = test_submissions.SubmissionTests.remote(self)
        original = remote.get.side_effect
        async def get(url):
            if hook:
                hook(url)
            kind = url.rsplit('/', 1)[-1]
            definitions = {
                'LoadImage': dict(input=dict(required=dict(image=[[]])), output=['IMAGE', 'MASK']),
                'VAEEncode': dict(input=dict(required=dict(pixels=['IMAGE'], vae=['VAE'])), output=['LATENT']),
            }
            if kind in definitions:
                return httpx.Response(200, request=httpx.Request('GET', url), json={kind: definitions[kind]})
            if kind == 'LoraLoader':
                return httpx.Response(200, request=httpx.Request('GET', url), json=test_lora_submissions.loader_definition())
            return original(url)
        async def post(url, **kwargs):
            if url.endswith('/upload/image'):
                target = image_workflows.location(body['request_id']) if receipt is None else receipt
                return httpx.Response(200, request=httpx.Request('POST', url), json=target)
            return httpx.Response(200, request=httpx.Request('POST', url), json=dict(prompt_id=body['request_id'], number=0))
        remote.get.side_effect = get
        remote.post.side_effect = post
        return remote

    def submit(self, body, remote):
        with patch('backend.submissions.httpx.AsyncClient', return_value=remote):
            return self.client.post('/api/generate', json=body)

    def test_owned_input_exact_graph_and_provenance(self):
        body = self.body(); remote = self.remote(body)
        result = self.submit(body, remote)
        self.assertEqual(result.status_code, 200, result.text)
        job = result.json()
        self.assertEqual(job['workflow_id'], IMG2IMG_ID)
        self.assertEqual(job['workflow']['4']['class_type'], 'VAEEncode')
        self.assertEqual(job['workflow']['12']['inputs']['image'], 'model_atelier/' + body['request_id'] + '/reference.png')
        self.assertEqual(job['workflow']['5']['inputs']['seed'], 2**64 - 1)
        self.assertEqual(job['workflow']['5']['inputs']['denoise'], 0.45)
        self.assertEqual([c.args[0].rsplit('/', 1)[-1] for c in remote.post.await_args_list], ['image', 'prompt'])
        upload = remote.post.await_args_list[0].kwargs
        self.assertEqual(upload['data']['overwrite'], 'false')
        encoded = upload['files']['image'][1]
        with Image.open(io.BytesIO(encoded)) as image:
            self.assertEqual(image.size, (512, 512)); self.assertEqual(image.mode, 'RGB')
            self.assertEqual(image.getpixel((0, 0)), (255, 255, 255))
        frozen = job['reference_metadata'][0]
        self.assertEqual(frozen['sha256'], self.asset['sha256'])
        self.assertEqual(frozen['generation_preprocessing']['resize'], 'fit')
        self.assertEqual(frozen['generation_preprocessing']['version'], 1)
        self.assertEqual(self.client.get('/api/jobs/' + job['id'] + '/reference-image').content, encoded)
        self.assertNotIn('reference_settings', self.client.get('/api/jobs').json()[0])
        self.assertEqual(self.client.put('/api/assets/' + self.asset['id'], json=dict(title='x', archived=True)).status_code, 409)
        with self.assertRaises(ValueError):
            jobs.update(self.db, job['id'], reference_metadata=[])

    def test_recovery_precedes_files_and_engine_validation_and_conflicts_on_asset(self):
        body = self.body(); remote = self.remote(body)
        first = self.submit(body, remote).json()
        (self.db.parent / 'assets' / (self.asset['id'] + '.png')).unlink()
        self.client.put('/api/settings', json={'comfy_url': 'http://127.0.0.1:9000'})
        with patch('backend.submissions.httpx.AsyncClient', side_effect=AssertionError('no request')):
            self.assertEqual(self.client.post('/api/generate', json=body).json(), first)
            self.assertEqual(self.client.post('/api/generate', json=body | dict(image_asset_id=str(uuid4()))).status_code, 409)
        self.assertEqual(remote.post.await_count, 2)

    def test_invalid_missing_archived_or_changed_asset_never_calls_engine(self):
        body = self.body()
        with patch('backend.submissions.httpx.AsyncClient', side_effect=AssertionError('no engine')):
            for change in (dict(image_asset_id=None), dict(reference_ids=[]), dict(reference_ids=[self.asset['id'], str(uuid4())]), dict(width=8192, height=8192)):
                self.assertEqual(self.client.post('/api/generate', json=body | change).status_code, 422)
            (self.db.parent / 'assets' / (self.asset['id'] + '.png')).write_bytes(b'changed')
            self.assertEqual(self.client.post('/api/generate', json=body).status_code, 422)
        self.assertEqual(jobs.list_all(self.db), [])

    def test_missing_checkpoint_offline_or_reference_node_never_uploads(self):
        for failure in ('offline', 'checkpoint', 'node', 'interface'):
            with self.subTest(failure=failure):
                body = self.body(); remote = self.remote(body)
                original = remote.get.side_effect
                async def get(url):
                    if failure == 'offline':
                        raise httpx.ConnectError('offline')
                    if failure == 'checkpoint' and url.endswith('/CheckpointLoaderSimple'):
                        data = {'CheckpointLoaderSimple': {'input': {'required': {'ckpt_name': [[]]}}}}
                    elif failure in ('node', 'interface') and url.endswith('/LoadImage'):
                        data = {} if failure == 'node' else {'LoadImage': dict(input=dict(required=dict(image=[[]])), output=['MASK', 'IMAGE'])}
                    else:
                        return await original(url)
                    return httpx.Response(200, request=httpx.Request('GET', url), json=data)
                remote.get.side_effect = get
                response = self.submit(body, remote)
                self.assertGreaterEqual(response.status_code, 400, response.text)
                remote.post.assert_not_awaited()
                self.assertEqual(jobs.get(self.db, body['request_id'])['status'], 'failed')

    def test_invalid_receipt_or_upload_timeout_never_submits_generation(self):
        for failure in ('path', 'timeout'):
            body = self.body(); remote = self.remote(body, receipt=dict(name='../x.png', subfolder='bad', type='output'))
            if failure == 'timeout':
                remote.post.side_effect = httpx.ReadTimeout('uncertain upload')
            result = self.submit(body, remote)
            self.assertEqual(result.status_code, 502, result.text)
            self.assertEqual(remote.post.await_count, 1)
            self.assertEqual(self.submit(body, remote).json()['status'], 'failed')
            self.assertEqual(remote.post.await_count, 1)

    def test_lost_prompt_response_never_reuploads_or_reposts(self):
        body = self.body(); remote = self.remote(body)
        original = remote.post.side_effect
        async def post(url, **kwargs):
            if url.endswith('/prompt'):
                raise httpx.ReadTimeout('ambiguous')
            return await original(url, **kwargs)
        remote.post.side_effect = post
        self.assertEqual(self.submit(body, remote).json()['status'], 'unknown')
        self.assertEqual(self.submit(body, remote).json()['status'], 'unknown')
        self.assertEqual(remote.post.await_count, 2)

    def test_archiving_during_validation_is_blocked_and_snapshot_stays_frozen(self):
        body = self.body()
        observed = []
        def hook(url):
            if url.endswith('/CheckpointLoaderSimple'):
                observed.append(self.client.put('/api/assets/' + self.asset['id'], json=dict(title='x', archived=True)).status_code)
                self.client.put('/api/assets/' + self.asset['id'], json=dict(title='renamed', purpose='style'))
        job = self.submit(body, self.remote(body, hook=hook)).json()
        self.assertEqual(observed, [409])
        self.assertEqual(job['reference_metadata'][0]['title'], '風景.png')
        self.assertEqual(job['reference_metadata'][0]['purpose'], 'unspecified')

    def test_archived_between_prepare_and_reserve_or_conflicting_source_is_rejected(self):
        body = self.body(); settings = main.DraftInput.model_validate(body).model_dump(mode='json', exclude={'revision'})
        snapshot, _ = image_workflows.prepare(self.db, self.db.parent, settings)
        assets.update(self.db, self.asset['id'], self.asset['title'], True)
        with self.assertRaises(ValueError):
            jobs.reserve(self.db, body['request_id'], body['engine_url'], image_workflows.build(settings, body['request_id']), body['checkpoint'], workflow_id=IMG2IMG_ID, reference_metadata=[snapshot], reference_settings=settings)
        self.assertEqual(jobs.list_all(self.db), [])

    def test_engine_changed_after_upload_does_not_post_prompt(self):
        body = self.body(); remote = self.remote(body); original = remote.post.side_effect
        async def post(url, **kwargs):
            result = await original(url, **kwargs)
            self.client.put('/api/settings', json={'comfy_url': 'http://127.0.0.1:9000'})
            return result
        remote.post.side_effect = post
        self.assertEqual(self.submit(body, remote).status_code, 409)
        self.assertEqual(remote.post.await_count, 1)

    def test_artwork_and_terminal_job_restore_exact_settings_offline(self):
        body = self.body(); job = self.submit(body, self.remote(body)).json()
        job = jobs.update(self.db, job['id'], status='completed')
        stream = io.BytesIO(); Image.new('RGB', (512, 512), 'green').save(stream, format='PNG')
        source = dict(node_id='7', filename='landscape.png', subfolder='', type='output')
        item, _ = gallery.save(self.db, self.db.parent / 'artworks', job, source, stream.getvalue())
        with patch('backend.submissions.httpx.AsyncClient', side_effect=AssertionError('offline restore')):
            for path in ('/api/artworks/' + item['id'], '/api/jobs/' + job['id']):
                response = self.client.get(path + '/creation-settings')
                self.assertEqual(response.status_code, 200, response.text)
                self.assertEqual(response.json()['settings'], job['reference_settings'])
                self.assertEqual(response.json()['reference_metadata'], job['reference_metadata'])
        tampered = copy.deepcopy(item); tampered['workflow']['12']['inputs']['image'] = '../unknown.png'
        with self.assertRaises(ValueError):
            image_workflows.extract(tampered, lambda data: main.DraftInput.model_validate(data).model_dump(mode='json'))

    def test_lora_routes_clip_and_keeps_vae_and_whole_restoration(self):
        body = self.body(); name = test_lora_submissions.NAME
        loras.merge(self.db, body['engine_url'], [name])
        loras.update_metadata(self.db, body['engine_url'], name, dict(architecture='sdxl'))
        body['loras'] = [dict(name=name, enabled=True, strength_model=0.8, strength_clip=0.7)]
        result = self.submit(body, self.remote(body)); self.assertEqual(result.status_code, 200, result.text)
        job = result.json(); graph = job['workflow']
        self.assertEqual(graph['5']['inputs']['model'], ['8', 0])
        self.assertEqual(graph['2']['inputs']['clip'], ['8', 1])
        self.assertEqual(graph['4']['inputs']['vae'], ['1', 2])
        restored = image_workflows.extract(dict(job, source=dict(node_id='7')), lambda data: main.DraftInput.model_validate(data).model_dump(mode='json', exclude={'revision'}))
        self.assertEqual(restored['loras'], body['loras'])

    def test_draft_modes_and_raw_filename_submission_rejected(self):
        body = self.body()
        draft = self.client.post('/api/drafts', json=body)
        self.assertEqual(draft.status_code, 201)
        self.assertEqual(self.client.get('/api/drafts').json()[0]['image_asset_id'], self.asset['id'])
        raw = dict(request_id=body['request_id'], engine_url=body['engine_url'], checkpoint=body['checkpoint'], workflow=image_workflows.build(main.DraftInput.model_validate(body).model_dump(mode='json'), body['request_id']))
        self.assertEqual(self.client.post('/api/jobs', json=raw).status_code, 422)

    def test_reservation_detects_source_conflict_even_when_graph_is_identical(self):
        body = self.body(); job = self.submit(body, self.remote(body)).json()
        settings = dict(job['reference_settings'], image_asset_id=str(uuid4()))
        with self.assertRaises(ValueError):
            jobs.reserve(self.db, job['id'], job['engine_url'], job['workflow'], job['checkpoint'],
                         workflow_id=IMG2IMG_ID, reference_metadata=job['reference_metadata'], reference_settings=settings)

    def test_stretch_opaque_resize_and_unknown_architecture_rejection(self):
        body = self.body() | dict(reference_resize='stretch')
        settings = main.DraftInput.model_validate(body).model_dump(mode='json')
        snapshot, encoded = image_workflows.prepare(self.db, self.db.parent, settings)
        self.assertEqual(snapshot['generation_preprocessing']['resize'], 'stretch')
        with Image.open(io.BytesIO(encoded)) as image:
            self.assertNotEqual(image.getpixel((0, 0)), (255, 255, 255))
        catalog.update_metadata(self.db, body['engine_url'], body['checkpoint'], dict(architecture='unknown'))
        remote = self.remote(body)
        self.assertEqual(self.submit(body, remote).status_code, 422)
        remote.post.assert_not_awaited()

    def test_missing_source_during_restoration_is_warned_without_losing_settings(self):
        body = self.body(); job = self.submit(body, self.remote(body)).json()
        jobs.update(self.db, job['id'], status='failed')
        (self.db.parent / 'assets' / (self.asset['id'] + '.png')).unlink()
        restored = self.client.get('/api/jobs/' + job['id'] + '/creation-settings').json()
        self.assertEqual(restored['settings']['image_asset_id'], self.asset['id'])
        self.assertTrue(any('遺失' in message for message in restored['warnings']))
