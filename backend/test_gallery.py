import io
import json
import unittest
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4
from unittest.mock import patch

import httpx
from PIL import Image, PngImagePlugin

from backend import gallery, jobs, test_api

CLIENT = httpx.AsyncClient


class GalleryTests(unittest.TestCase):
    setUp = test_api.ApiTests.setUp
    tearDown = test_api.ApiTests.tearDown

    def image(self):
        stream = io.BytesIO()
        info = PngImagePlugin.PngInfo()
        info.add_text('prompt', 'original metadata')
        Image.new('RGB', (800, 600), '#718d76').save(stream, 'PNG', pnginfo=info)
        return stream.getvalue()

    def job(self, filenames=('result.png',), version='v1'):
        job_id = str(uuid4())
        workflow = {
            '1': {'class_type': 'CheckpointLoaderSimple', 'inputs': {'ckpt_name': 'sample.safetensors'}},
            '2': {'class_type': 'CLIPTextEncode', 'inputs': {'text': 'a forest'}},
            '3': {'class_type': 'CLIPTextEncode', 'inputs': {'text': 'blurry'}},
            '5': {'class_type': 'KSampler', 'inputs': {'positive': ['2', 0], 'negative': ['3', 0], 'seed': 2**64-1, 'steps': 20, 'cfg': 7, 'sampler_name': 'euler', 'scheduler': 'normal'}},
            '6': {'class_type': 'VAEDecode', 'inputs': {'samples': ['5', 0]}},
            '7': {'class_type': 'SaveImage', 'inputs': {'images': ['6', 0]}},
        }
        jobs.reserve(self.db, job_id, 'http://127.0.0.1:8188', workflow, 'sample.safetensors', version)
        return jobs.update(self.db, job_id, status='completed', history={
            'status': {'completed': True, 'status_str': 'success'},
            'outputs': {'7': {'images': [dict(filename=f, subfolder='batch/one', type='output') for f in filenames]}}})

    def remote(self, handler):
        return patch('backend.gallery_api.httpx.AsyncClient', side_effect=lambda **kwargs: CLIENT(transport=httpx.MockTransport(handler), **kwargs))

    def test_import_original_thumbnail_parameters_and_offline_dedup(self):
        job, raw = self.job(), self.image()
        seen = []
        def handle(request):
            seen.append(request)
            return httpx.Response(200, content=raw)
        self.client.put('/api/settings', json={'comfy_url': 'http://localhost:9000'})
        with self.remote(handle):
            result = self.client.post('/api/jobs/' + job['id'] + '/artworks')
        self.assertEqual(result.status_code, 200, result.text)
        item = result.json()['imported'][0]
        self.assertEqual(str(seen[0].url).split('/view')[0], job['engine_url'])
        self.assertEqual(seen[0].url.params['subfolder'], 'batch/one')
        self.assertEqual(item['parameters']['seed'], str(2**64-1))
        self.assertEqual(item['parameters']['prompt'], 'a forest')
        self.assertEqual(item['parameters']['negative_prompt'], 'blurry')
        self.assertEqual(item['model_version'], 'v1')
        path = '/api/artworks/' + item['id']
        with self.remote(lambda request: (_ for _ in ()).throw(AssertionError('must stay offline'))):
            self.assertEqual(self.client.get(path + '/image').content, raw)
            self.assertIn('attachment;', self.client.get(path + '/image?download=true').headers['content-disposition'])
            thumb = Image.open(io.BytesIO(self.client.get(path + '/image?thumbnail=true').content))
            self.assertEqual(thumb.size, (512, 384))
            self.assertNotIn('prompt', thumb.info)
            self.assertEqual(json.loads(self.client.get(path + '/workflow').text), job['workflow'])
            repeated = self.client.post('/api/jobs/' + job['id'] + '/artworks').json()
        self.assertEqual(len(repeated['existing']), 1)
        self.assertEqual(repeated['imported'], [])
        self.assertEqual(len(self.client.get('/api/artworks').json()), 1)

    def test_partial_failure_retry_retains_success(self):
        job, raw = self.job(('one.png', 'two.png')), self.image()
        def handle(request):
            return httpx.Response(200, content=raw) if request.url.params['filename'] == 'one.png' else httpx.Response(404)
        with self.remote(handle):
            result = self.client.post('/api/jobs/' + job['id'] + '/artworks').json()
        self.assertEqual(len(result['imported']), 1)
        self.assertEqual(len(result['errors']), 1)
        with self.remote(lambda request: httpx.Response(200, content=raw)):
            retry = self.client.post('/api/jobs/' + job['id'] + '/artworks').json()
        self.assertEqual(len(retry['existing']), 1)
        self.assertEqual(len(retry['imported']), 1)

    def test_unfinished_and_invalid_paths_do_not_download(self):
        job = self.job()
        endpoint = '/api/jobs/' + job['id'] + '/artworks'
        with self.remote(lambda request: (_ for _ in ()).throw(AssertionError('unexpected request'))):
            for status in ('running', 'failed', 'unknown'):
                jobs.update(self.db, job['id'], status=status)
                self.assertEqual(self.client.post(endpoint).status_code, 409)
            jobs.update(self.db, job['id'], status='completed')
            for change in [dict(filename='../secret.png'), dict(subfolder='../'), dict(subfolder='C:/data'), dict(filename='x\\y.png'), dict(filename='secret.png [input]'), dict(type='input')]:
                history = {'status': {'completed': True, 'status_str': 'success'}, 'outputs': {'7': {'images': [dict(filename='ok.png', subfolder='', type='output') | change]}}}
                jobs.update(self.db, job['id'], history=history)
                self.assertEqual(self.client.post(endpoint).status_code, 409)
        self.assertEqual(self.client.get('/api/artworks').json(), [])

    def test_corrupt_oversized_offline_and_redirect_responses(self):
        job = self.job()
        endpoint = '/api/jobs/' + job['id'] + '/artworks'
        for handler in [lambda request: httpx.Response(200, content=b'not an image'),
                        lambda request: httpx.Response(302, headers={'Location': 'http://untrusted.invalid/'}),
                        lambda request: (_ for _ in ()).throw(httpx.ConnectError('offline'))]:
            with self.remote(handler):
                self.assertEqual(len(self.client.post(endpoint).json()['errors']), 1)
        with self.remote(lambda request: httpx.Response(200, content=self.image())), patch.object(gallery, 'MAX_BYTES', 5):
            self.assertEqual(len(self.client.post(endpoint).json()['errors']), 1)
        with self.remote(lambda request: httpx.Response(200, content=self.image())), patch.object(gallery, 'MAX_PIXELS', 5):
            self.assertEqual(len(self.client.post(endpoint).json()['errors']), 1)
        self.assertEqual(self.client.get('/api/artworks').json(), [])
        self.assertFalse((self.db.parent / 'artworks').exists())

    def test_concurrent_save_deduplicates_and_missing_file_is_explicit(self):
        job, raw = self.job(version=None), self.image()
        folder = self.db.parent / 'artworks'
        source = gallery.outputs(job)[0]
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: gallery.save(self.db, folder, job, source, raw), range(2)))
        self.assertEqual(sum(created for _, created in results), 1)
        item = results[0][0]
        self.assertEqual(item['model_version'], '未知')
        (folder / (item['id'] + '.png')).unlink()
        self.assertFalse(self.client.get('/api/artworks/' + item['id']).json()['image_available'])
        self.assertEqual(self.client.get('/api/artworks/' + item['id'] + '/image').status_code, 404)
        self.assertEqual(self.client.get('/api/artworks/' + item['id'] + '/workflow').status_code, 200)
        self.assertEqual(self.client.get('/api/artworks/' + str(uuid4())).status_code, 404)

    def test_disk_failure_rolls_back_import(self):
        job = self.job()
        folder = self.db.parent / 'artworks'
        import os
        original = os.replace
        calls = 0
        def fail_second(*args):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise OSError('disk full')
            return original(*args)
        with patch('backend.gallery.os.replace', side_effect=fail_second):
            with self.assertRaises(OSError):
                gallery.save(self.db, folder, job, gallery.outputs(job)[0], self.image())
        self.assertEqual(gallery.list_all(self.db), [])
        self.assertEqual(list(folder.iterdir()), [])
