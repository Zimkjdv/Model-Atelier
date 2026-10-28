import sqlite3
import unittest
from contextlib import closing
from unittest.mock import patch

import httpx

from backend import gallery, jobs, test_gallery


class JobResultTests(unittest.TestCase):
    setUp = test_gallery.GalleryTests.setUp
    tearDown = test_gallery.GalleryTests.tearDown
    job = test_gallery.GalleryTests.job
    image = test_gallery.GalleryTests.image
    remote = test_gallery.GalleryTests.remote

    def test_unsaved_preview_uses_recorded_engine_and_does_not_import(self):
        job, raw = self.job(), self.image()
        path = '/api/jobs/' + job['id'] + '/results'
        self.client.put('/api/settings', json={'comfy_url': 'http://localhost:9000'})
        with closing(sqlite3.connect(self.db)) as db:
            before = db.execute('SELECT key,value FROM settings ORDER BY key').fetchall()
        with self.remote(
            lambda request: (_ for _ in ()).throw(AssertionError('manifest is offline'))
        ):
            result = self.client.get(path).json()
        self.assertFalse(result['items'][0]['saved'])
        seen = []

        def handle(request):
            seen.append(request)
            return httpx.Response(200, content=raw)

        with self.remote(handle):
            response = self.client.get(path + '/0/image')
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.content, raw)
        self.assertEqual(str(seen[0].url).split('/view')[0], job['engine_url'])
        self.assertEqual(seen[0].url.params['filename'], 'result.png')
        self.assertEqual(gallery.list_all(self.db), [])
        with closing(sqlite3.connect(self.db)) as db:
            self.assertEqual(
                db.execute('SELECT key,value FROM settings ORDER BY key').fetchall(), before
            )

    def test_saved_result_is_available_without_engine_and_has_real_dimensions(self):
        job, raw = self.job(), self.image()
        with self.remote(lambda request: httpx.Response(200, content=raw)):
            self.client.post('/api/jobs/' + job['id'] + '/artworks').raise_for_status()
        path = '/api/jobs/' + job['id'] + '/results'
        with self.remote(
            lambda request: (_ for _ in ()).throw(AssertionError('saved result stays offline'))
        ):
            item = self.client.get(path).json()['items'][0]
            self.assertTrue(item['saved'])
            self.assertEqual((item['width'], item['height']), (800, 600))
            self.assertEqual(self.client.get(path + '/0/image').content, raw)

    def test_invalid_incomplete_missing_and_unavailable_outputs(self):
        job = self.job()
        path = '/api/jobs/' + job['id'] + '/results'
        self.assertEqual(self.client.get(path + '/-1/image').status_code, 404)
        self.assertEqual(self.client.get(path + '/64/image').status_code, 404)
        with self.remote(lambda request: httpx.Response(404)):
            self.assertEqual(self.client.get(path + '/0/image').status_code, 404)
        with self.remote(lambda request: httpx.Response(200, content=b'not an image')):
            self.assertEqual(self.client.get(path + '/0/image').status_code, 422)
        with self.remote(lambda request: (_ for _ in ()).throw(httpx.ConnectError('offline'))):
            self.assertEqual(self.client.get(path + '/0/image').status_code, 502)
        jobs.update(self.db, job['id'], status='running')
        self.assertEqual(self.client.get(path).status_code, 409)
        self.assertEqual(self.client.get('/api/jobs/not-a-uuid/results').status_code, 422)

    def test_untrusted_output_path_and_oversize_do_not_fetch_or_save(self):
        job = self.job(('../escape.png',))
        with self.remote(lambda request: (_ for _ in ()).throw(AssertionError('invalid path'))):
            self.assertEqual(
                self.client.get('/api/jobs/' + job['id'] + '/results/0/image').status_code, 409
            )
        job = self.job()
        with (
            patch('backend.job_results.gallery.MAX_BYTES', 4),
            self.remote(lambda request: httpx.Response(200, content=b'12345')),
        ):
            self.assertEqual(
                self.client.get('/api/jobs/' + job['id'] + '/results/0/image').status_code, 422
            )
        self.assertEqual(gallery.list_all(self.db), [])

    def test_missing_saved_original_is_not_reported_as_never_imported(self):
        job, raw = self.job(), self.image()
        with self.remote(lambda request: httpx.Response(200, content=raw)):
            item = self.client.post('/api/jobs/' + job['id'] + '/artworks').json()['imported'][0]
        (self.host.DATA / 'artworks' / (item['id'] + '.' + item['extension'])).unlink()
        path = '/api/jobs/' + job['id'] + '/results'
        result = self.client.get(path).json()['items'][0]
        self.assertTrue(result['saved'])
        self.assertFalse(result['local_available'])
        with self.remote(lambda request: httpx.Response(200, content=raw)):
            self.assertEqual(self.client.get(path + '/0/image').content, raw)
        self.assertEqual(len(gallery.list_all(self.db)), 1)
