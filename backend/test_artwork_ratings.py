import unittest
from contextlib import closing
import json
import sqlite3
from backend import gallery, test_artwork_organization, test_api, test_gallery


class RatingTests(unittest.TestCase):
    setUp = test_api.ApiTests.setUp
    tearDown = test_api.ApiTests.tearDown
    job = test_gallery.GalleryTests.job
    image = test_gallery.GalleryTests.image
    prepare = test_artwork_organization.ArtworkOrganizationTests.prepare

    def test_scores_clear_noop_and_reimport_preserve_graph_and_image(self):
        job,item,path=self.prepare()
        scores=dict(prompt_adherence=4,character_consistency=None,visual_style=2,composition=5)
        raw=self.client.get(path+'/image').content
        value=self.client.patch(path+'/organization',json=dict(revision=0,ratings=scores))
        self.assertEqual(value.status_code,200,value.text)
        self.assertEqual(value.json()['ratings'],scores)
        self.assertEqual(value.json()['revision'],1)
        self.assertEqual(self.client.get(path+'/workflow').json(),item['workflow'])
        self.assertEqual(self.client.get(path+'/image').content,raw)
        for k,v in item.items():
            if k not in gallery.ORGANIZATION_DEFAULTS: self.assertEqual(gallery.get(self.db,item['id'])[k],v)
        before=self.db.read_bytes()
        self.assertEqual(self.client.patch(path+'/organization',json=dict(revision=1,ratings=scores)).json()['revision'],1)
        self.assertEqual(self.db.read_bytes(),before)
        old,created=gallery.save(self.db,self.db.parent/'artworks',job,gallery.outputs(job)[0],self.image())
        self.assertFalse(created); self.assertEqual(old['ratings'],scores)
        cleared=self.client.patch(path+'/organization',json=dict(revision=1,ratings=gallery.RATING_DEFAULTS)).json()
        self.assertEqual(cleared['ratings'],gallery.RATING_DEFAULTS); self.assertEqual(cleared['revision'],2)

    def test_bad_partial_boolean_or_fractional_scores_never_write(self):
        _,_,path=self.prepare(); before=self.db.read_bytes()
        for bad in [None,{},dict(prompt_adherence=4),gallery.RATING_DEFAULTS|dict(composition=True),
                    gallery.RATING_DEFAULTS|dict(composition=0),gallery.RATING_DEFAULTS|dict(composition=6),
                    gallery.RATING_DEFAULTS|dict(composition=3.5),gallery.RATING_DEFAULTS|dict(composition='4'),
                    gallery.RATING_DEFAULTS|dict(extra='injection')]:
            response=self.client.patch(path+'/organization',json=dict(revision=0,ratings=bad))
            self.assertEqual(response.status_code,422,response.text); self.assertEqual(before,self.db.read_bytes())

    def test_legacy_defaults_no_write_and_stale_revision_retains_current_scores(self):
        _,item,path=self.prepare(); item.pop('ratings')
        with closing(sqlite3.connect(self.db)) as db,db:
            db.execute('UPDATE settings SET value=? WHERE key=?',(json.dumps(item),'artwork:'+item['id']))
        before=self.db.read_bytes()
        self.assertEqual(self.client.get(path).json()['ratings'],gallery.RATING_DEFAULTS)
        self.assertEqual(before,self.db.read_bytes())
        scores=gallery.RATING_DEFAULTS|dict(visual_style=1)
        self.assertEqual(self.client.patch(path+'/organization',json=dict(revision=0,ratings=scores)).status_code,200)
        before=self.db.read_bytes()
        self.assertEqual(self.client.patch(path+'/organization',json=dict(revision=0,ratings=gallery.RATING_DEFAULTS)).status_code,409)
        self.assertEqual(before,self.db.read_bytes()); self.assertEqual(self.client.get(path).json()['ratings'],scores)
