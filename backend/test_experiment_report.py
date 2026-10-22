import copy
import hashlib
import json
import sqlite3
import unittest
from contextlib import closing
from unittest.mock import patch
from uuid import uuid4
from backend import experiment_report as report,experiment_store,jobs,gallery,test_gallery
from backend import test_experiment_runs as old


class ReportTests(unittest.TestCase):
    setUp=old.ExperimentRunTests.setUp
    tearDown=old.ExperimentRunTests.tearDown
    saved=old.ExperimentRunTests.saved
    body=old.ExperimentRunTests.body
    remote=old.ExperimentRunTests.remote
    submit=old.ExperimentRunTests.submit
    def finished(self,record):
        job=self.submit(self.body(record)).json();job=jobs.update(self.db,job['id'],status='completed',history=dict(status=dict(completed=True,status_str='success')))
        art,_=gallery.save(self.db,self.db.parent/'artworks',job,dict(node_id='7',filename='result.png',subfolder='',type='output'),test_gallery.GalleryTests.image(self))
        return job,art
    def get(self,record,**kwargs):
        return self.client.get('/api/experiments/plans/'+record['id']+'/report',params=dict(expected_plan_sha256=record['plan']['plan_sha256']),**kwargs)
    def mutate(self,key,transform):
        with closing(sqlite3.connect(self.db)) as db,db:
            item=json.loads(db.execute('SELECT value FROM settings WHERE key=?',(key,)).fetchone()[0]);transform(item)
            db.execute('UPDATE settings SET value=? WHERE key=?',(json.dumps(item),key))
    def test_complete_offline_snapshot_workflow_hash_notes_and_exact_seed_no_writes(self):
        record=self.saved();job,art=self.finished(record);gallery.organize(self.db,art['id'],0,dict(notes='manual observation',ratings=dict(prompt_adherence=3,character_consistency=None,style_similarity=None,composition=None)))
        before=self.db.read_bytes()
        with patch('backend.main.httpx.AsyncClient',side_effect=AssertionError('offline')):response=self.get(record)
        self.assertEqual(response.status_code,200,response.text);self.assertEqual(response.headers['cache-control'],'no-store');self.assertEqual(response.headers['x-atelier-sha256'],hashlib.sha256(response.content).hexdigest())
        value=response.json();run=value['variants'][0]['runs'][0]
        self.assertEqual(run['workflow'],job['workflow']);self.assertEqual(run['experiment_context']['settings']['seed'],'9007199254740993')
        self.assertEqual(run['artworks'][0]['notes'],'manual observation');self.assertFalse(run['artworks'][0]['current_file_hash_verified'])
        self.assertEqual(before,self.db.read_bytes())
    def test_empty_and_archived_plans_are_readable_without_inferred_runs(self):
        record=self.saved();other=self.client.post('/api/experiments/plans',json=dict(request_id=str(uuid4()),plan=record['plan'])).json();self.finished(other)
        self.assertTrue(all(not group['runs'] for group in self.get(record).json()['variants']))
        experiment_store.archive(self.db,record['id'],1,True);self.assertTrue(self.get(record).json()['plan']['archived'])
    def test_wrong_hash_missing_plan_and_missing_anchor_are_explicit_errors(self):
        record=self.saved();prefix='/api/experiments/plans/'+record['id']+'/report'
        self.assertEqual(self.client.get(prefix).status_code,422)
        self.assertEqual(self.client.get(prefix,params=dict(expected_plan_sha256='a'*64)).status_code,409)
        missing=copy.deepcopy(record);missing['id']=str(uuid4());self.assertEqual(self.get(missing).status_code,404)
    def test_changed_context_or_workflow_rejects_whole_report(self):
        for target in ('context','graph','missing'):
            record=self.saved();job,art=self.finished(record)
            def change(value):
                if target=='context':value['experiment_context']['settings']['seed']='1'
                elif target=='graph':value['workflow']['5']['inputs']['seed']=True
                else:value.pop('id')
            self.mutate('job:'+job['id'],change)
            self.assertEqual(self.get(record).status_code,409)
    def test_orphan_or_mismatched_artwork_never_omitted_silently(self):
        record=self.saved();job,art=self.finished(record)
        self.mutate('artwork:'+art['id'],lambda value:value.update(job_id=str(uuid4())))
        self.assertEqual(self.get(record).status_code,409)
    def test_limits_reject_without_truncating_or_persisting(self):
        record=self.saved();self.finished(record);before=self.db.read_bytes()
        with patch.object(report,'MAX_ENTRIES',1):self.assertEqual(self.get(record).status_code,413)
        with patch.object(report,'MAX_BYTES',100):self.assertEqual(self.get(record).status_code,413)
        self.assertEqual(before,self.db.read_bytes())
    def test_unexported_artwork_fields_do_not_consume_report_budget(self):
        record=self.saved();job,art=self.finished(record);limit=len(self.get(record).content)+4096
        self.mutate('artwork:'+art['id'],lambda value:value.update(unrelated_metadata='x'*100000))
        with patch.object(report,'MAX_BYTES',limit):response=self.get(record)
        self.assertEqual(response.status_code,200,response.text);self.assertNotIn('unrelated_metadata',response.text)
    def test_missing_old_runtime_stays_null_and_missing_file_is_explicit(self):
        record=self.saved();job,art=self.finished(record)
        self.mutate('job:'+job['id'],lambda value:(value.pop('runtime_metadata'),value.pop('measurements')))
        (self.db.parent/'artworks'/(art['id']+'.'+art['extension'])).unlink()
        before=self.db.read_bytes();value=self.get(record).json()['variants'][0]['runs'][0]
        self.assertIsNone(value['runtime_metadata']);self.assertIsNone(value['measurements']);self.assertFalse(value['artworks'][0]['image_available']);self.assertEqual(before,self.db.read_bytes())
    def test_single_sqlite_snapshot_survives_concurrent_archive_and_status_change(self):
        record=self.saved();job,art=self.finished(record)
        with closing(sqlite3.connect(self.db)) as db:db.execute('PRAGMA journal_mode=WAL')
        def validate(plan):
            experiment_store.archive(self.db,record['id'],1,True);jobs.update(self.db,job['id'],status='failed');return plan
        raw=report.create(self.db,self.db.parent/'artworks',record['id'],record['plan']['plan_sha256'],validate)
        value=json.loads(raw);self.assertFalse(value['plan']['archived']);self.assertEqual(value['variants'][0]['runs'][0]['status'],'completed')
        self.assertTrue(experiment_store.get(self.db,record['id'])['archived']);self.assertEqual(jobs.get(self.db,job['id'])['status'],'failed')
