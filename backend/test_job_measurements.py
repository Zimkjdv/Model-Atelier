import copy
import json
import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from unittest.mock import patch
from uuid import uuid4
import unittest
from backend import jobs, gallery, job_measurements as metrics, test_api, test_gallery, test_runtime_metadata, progress

class MeasurementTests(unittest.TestCase):
    setUp=test_api.ApiTests.setUp
    tearDown=test_api.ApiTests.tearDown
    def reserve(self):
        return jobs.reserve(self.db,str(uuid4()),'http://127.0.0.1:8188',{},'base')[0]
    def history(self, job, end='execution_success'):
        return dict(status=dict(completed=True,status_str='success' if end=='execution_success' else 'error',messages=[
            ['execution_start',dict(prompt_id=job['prompt_id'],timestamp=1000)],
            [end,dict(prompt_id=job['prompt_id'],timestamp=3500)]]))
    def test_dispatch_and_terminal_measurements_are_frozen_with_cas_and_no_extra_source(self):
        job=self.reserve()
        with patch('backend.jobs.datetime') as clock:
            clock.now.return_value=datetime(2026,10,8,0,0,0,tzinfo=timezone.utc)
            dispatched=jobs.update(self.db,job['id'],status='submitting')
            clock.now.return_value=datetime(2026,10,8,0,0,7,tzinfo=timezone.utc)
            done=jobs.update(self.db,job['id'],status='completed',history=self.history(job))
        item=done['measurements']
        self.assertEqual(item['dispatch_to_observation_seconds'],7)
        self.assertEqual(item['engine_execution_seconds'],2.5)
        self.assertIsNone(item['task_vram_peak_bytes'])
        self.assertEqual(progress.summary(done)['measurements'],item)
        self.assertFalse(jobs.compare_update(self.db,dispatched,status='failed')[1])
        self.assertEqual(jobs.update(self.db,job['id'],error='later')['measurements'],item)
        with self.assertRaises(ValueError): jobs.update(self.db,job['id'],measurements={})
    def test_invalid_history_identity_numbers_order_and_outcomes_remain_unknown(self):
        job=self.reserve()|dict(status='completed')
        good=self.history(job)
        bad=[{},good|dict(status={}),good|dict(status=good['status']|dict(status_str='error'))]
        for kind in ['bool','float','wrong_id','reverse','duplicate','unhashable','huge','negative']:
            value=copy.deepcopy(good);messages=value['status']['messages']
            if kind=='bool': messages[0][1]['timestamp']=True
            elif kind=='float': messages[0][1]['timestamp']=1000.0
            elif kind=='wrong_id': messages[1][1]['prompt_id']=str(uuid4())
            elif kind=='reverse': messages.reverse()
            elif kind=='duplicate': messages.insert(0,copy.deepcopy(messages[0]))
            elif kind=='unhashable': messages[0][0]=[]
            elif kind=='huge': messages[1][1]['timestamp']=10**40
            elif kind=='negative': messages[1][1]['timestamp']=0
            bad.append(value)
        for value in bad:self.assertIsNone(metrics.engine_timing(job|dict(history=value)))
        for status,event in [('failed','execution_error'),('stopped','execution_interrupted')]:
            self.assertEqual(metrics.engine_timing(job|dict(status=status,history=self.history(job,event))),dict(start=1000,end=3500))
        self.assertIsNone(metrics.elapsed('2026-10-08T00:00:10+00:00','2026-10-08T00:00:00+00:00'))
        self.assertIsNone(metrics.elapsed('2026-10-08T00:00:00','2026-10-08T00:00:10'))
    def test_old_jobs_are_readonly_and_updates_do_not_backfill(self):
        job=self.reserve()
        with closing(sqlite3.connect(self.db)) as db,db:
            raw=json.loads(db.execute('select value from settings where key=?',('job:'+job['id'],)).fetchone()[0]);raw.pop('measurements')
            db.execute('update settings set value=? where key=?',(json.dumps(raw),'job:'+job['id']))
        before=self.db.read_bytes()
        self.assertIsNone(self.client.get('/api/jobs/'+job['id']).json()['measurements'])
        self.assertEqual(before,self.db.read_bytes())
        self.assertIsNone(jobs.update(self.db,job['id'],status='completed',history=self.history(job))['measurements'])
    def test_resource_types_zero_and_invalid_values_are_scoped_to_original_engine(self):
        stats=dict(system=dict(ram_total=100,ram_free=0),devices=[dict(name='CPU',type='cpu',index=0,vram_total=100,vram_free=20),
            dict(name='GPU',type='cuda',index=1,vram_total=True,vram_free=1000)])
        value=metrics.resources(stats,'http://remote:8188','time')
        self.assertEqual(value['ram']['used'],100)
        self.assertEqual(value['devices'][0]['vram']['used'],80)
        self.assertIsNone(value['devices'][1]['vram']['total'])
        self.assertEqual(value['source'],'http://remote:8188/system_stats')
        self.assertEqual(metrics.resources(None,'http://remote:8188','time')['devices'],[])
    def test_import_keeps_original_measurements_and_dedup_does_not_replace_them(self):
        source=test_gallery.GalleryTests.job(self)
        raw=test_gallery.GalleryTests.image(self)
        item=gallery.save(self.db,self.db.parent / "artworks",source,dict(node_id='7',filename='result.png',subfolder='batch/one',type='output'),raw)[0]
        self.assertEqual(item['measurements'],source['measurements'])
        stored=gallery.get(self.db,item['id'])
        self.assertEqual(stored['measurements'],source['measurements'])
        changed=source|dict(measurements=None)
        again=gallery.save(self.db,self.db.parent / "artworks",changed,source=dict(node_id='7',filename='result.png',subfolder='batch/one',type='output'),raw=raw)[0]
        self.assertEqual(again['measurements'],stored['measurements'])

class CaptureMeasurementTests(unittest.TestCase):
    setUp=test_api.ApiTests.setUp
    tearDown=test_api.ApiTests.tearDown
    payload=test_runtime_metadata.RuntimeMetadataTests.payload
    remote=test_runtime_metadata.RuntimeMetadataTests.remote
    engine=test_runtime_metadata.RuntimeMetadataTests.engine
    submit=test_runtime_metadata.RuntimeMetadataTests.submit
    def test_resource_snapshot_uses_the_same_bounded_version_request_and_freezes_once(self):
        stats=test_runtime_metadata.STATS|dict(devices=[dict(name='GPU',type='cuda',index=0,vram_total=100,vram_free=30)])
        remote=self.engine(stats);body=self.payload()
        value=self.submit(body,remote).json()
        item=value['measurements']['resources_before_submission']
        self.assertEqual(item['devices'][0]['vram']['used'],70)
        self.assertEqual(item['source'],body['engine_url']+'/system_stats')
        self.assertNotIn('resource_observation',value['runtime_metadata'])
        with patch('backend.submissions.httpx.AsyncClient',side_effect=AssertionError('no repeated capture')):
            self.assertEqual(self.client.post('/api/generate',json=body).json()['measurements'],value['measurements'])
