import json
import sqlite3
import unittest
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from uuid import uuid4

from backend import gallery, test_api, test_gallery


class ArtworkOrganizationTests(unittest.TestCase):
    setUp = test_api.ApiTests.setUp
    tearDown = test_api.ApiTests.tearDown
    job = test_gallery.GalleryTests.job
    image = test_gallery.GalleryTests.image

    def prepare(self):
        job = self.job()
        item, _ = gallery.save(self.db, self.db.parent / 'artworks', job, gallery.outputs(job)[0], self.image())
        return job, item, '/api/artworks/' + item['id']

    def test_legacy_read_defaults_do_not_rewrite_history(self):
        _, item, path = self.prepare()
        for field in gallery.ORGANIZATION_DEFAULTS:
            item.pop(field)
        with closing(sqlite3.connect(self.db)) as db, db:
            db.execute('UPDATE settings SET value=? WHERE key=?', (json.dumps(item), 'artwork:'+item['id']))
        before = self.db.read_bytes()
        value = self.client.get(path).json()
        self.assertEqual({k: value[k] for k in gallery.ORGANIZATION_DEFAULTS}, gallery.ORGANIZATION_DEFAULTS)
        self.assertEqual(len(self.client.get('/api/artworks').json()), 1)
        self.assertEqual(self.db.read_bytes(), before)

    def test_mutable_fields_preserve_every_historical_field_and_files(self):
        job, original, path = self.prepare()
        raw = self.client.get(path + '/image').content
        thumb = self.client.get(path + '/image?thumbnail=true').content
        notes = '風景測試\n<script>literal notes</script>\n seed 比較'
        value = self.client.patch(path + '/organization', json=dict(revision=0, favorite=True, notes=notes, archived=True))
        self.assertEqual(value.status_code, 200, value.text)
        value = value.json()
        for key, content in original.items():
            if key not in gallery.ORGANIZATION_DEFAULTS:
                self.assertEqual(gallery.get(self.db, original['id'])[key], content, key)
        self.assertEqual(value['notes'], notes)
        self.assertEqual(value['revision'], 1)
        self.assertEqual(self.client.get(path + '/image').content, raw)
        self.assertEqual(self.client.get(path + '/image?thumbnail=true').content, thumb)
        self.assertEqual(self.client.get(path + '/workflow').json(), job['workflow'])
        self.assertEqual(self.client.get('/api/artworks').json(), [])
        self.assertEqual(len(self.client.get('/api/artworks?scope=archived&favorites_only=true').json()), 1)
        self.assertEqual(len(self.client.get('/api/artworks?scope=all').json()), 1)
        restored = self.client.patch(path + '/organization', json=dict(revision=1, archived=False)).json()
        self.assertEqual(restored['revision'], 2)
        self.assertTrue(restored['favorite'])
        self.assertEqual(restored['notes'], notes)

    def test_stale_revision_and_concurrent_writers_never_silently_overwrite(self):
        _, item, path = self.prepare()
        def update(text):
            try:
                return gallery.organize(self.db, item['id'], 0, dict(notes=text))
            except gallery.RevisionConflict:
                return None
        with ThreadPoolExecutor(max_workers=2) as pool:
            result = list(pool.map(update, ['first', 'second']))
        self.assertEqual(sum(v is not None for v in result), 1)
        current = self.client.get(path).json()
        self.assertEqual(current['revision'], 1)
        self.assertIn(current['notes'], ['first', 'second'])
        before = self.db.read_bytes()
        response = self.client.patch(path+'/organization', json=dict(revision=0, notes='lost update'))
        self.assertEqual(response.status_code, 409)
        self.assertEqual(self.db.read_bytes(), before)

    def test_invalid_inputs_and_immutable_graph_injection_do_not_write(self):
        _, _, path = self.prepare()
        before = self.db.read_bytes()
        for body in [dict(revision=0), dict(notes='no revision'), dict(revision=True, favorite=True),
                     dict(revision=-1, notes='bad'), dict(revision=0, favorite=1), dict(revision=0, notes=None),
                     dict(revision=0, notes='x'*10001), dict(revision=0, archived=None),
                     dict(revision=0, notes='x', workflow={}), dict(revision=0, favorite=True, sha256='fake')]:
            response = self.client.patch(path + '/organization', json=body)
            self.assertEqual(response.status_code, 422, response.text)
            self.assertEqual(self.db.read_bytes(), before)
        self.assertEqual(self.client.get('/api/artworks?scope=invalid').status_code, 422)
        self.assertEqual(self.client.patch('/api/artworks/'+str(uuid4())+'/organization',
                                         json=dict(revision=0, favorite=True)).status_code, 404)

    def test_noop_does_not_bump_revision_and_reimport_does_not_reset_organization(self):
        job, item, path = self.prepare()
        response = self.client.patch(path+'/organization', json=dict(revision=0, notes='keep', favorite=True, archived=True))
        self.assertEqual(response.status_code, 200)
        before = self.db.read_bytes()
        noop = self.client.patch(path+'/organization', json=dict(revision=1, notes='keep'))
        self.assertEqual(noop.json()['revision'], 1)
        self.assertEqual(self.db.read_bytes(), before)
        value, created = gallery.save(self.db, self.db.parent/'artworks', job, gallery.outputs(job)[0], self.image())
        self.assertFalse(created)
        self.assertTrue(value['archived'])
        self.assertTrue(value['favorite'])
        self.assertEqual(value['notes'], 'keep')
        self.assertEqual(value['revision'], 1)

    def test_archived_artwork_still_protects_referenced_asset(self):
        _, item, path = self.prepare()
        response = self.client.post('/api/assets?filename=source.png', content=self.image())
        self.assertEqual(response.status_code, 201, response.text)
        asset = response.json()
        with closing(sqlite3.connect(self.db)) as db, db:
            raw = json.loads(db.execute('SELECT value FROM settings WHERE key=?', ('artwork:'+item['id'],)).fetchone()[0])
            raw['reference_metadata'] = [dict(id=asset['id'])]
            db.execute('UPDATE settings SET value=? WHERE key=?', (json.dumps(raw), 'artwork:'+item['id']))
        self.assertEqual(self.client.patch(path+'/organization', json=dict(revision=0, archived=True)).status_code, 200)
        response = self.client.put('/api/assets/'+asset['id'], json=dict(title=asset['title'], archived=True))
        self.assertEqual(response.status_code, 409)

    def test_missing_image_does_not_block_notes_or_workflow_access(self):
        _, item, path = self.prepare()
        (self.db.parent/'artworks'/(item['id']+'.png')).unlink()
        value = self.client.patch(path+'/organization', json=dict(revision=0, notes='restore from backup')).json()
        self.assertFalse(value['image_available'])
        self.assertEqual(value['notes'], 'restore from backup')
        self.assertEqual(self.client.get(path+'/image').status_code, 404)
        self.assertEqual(self.client.get(path+'/workflow').status_code, 200)
