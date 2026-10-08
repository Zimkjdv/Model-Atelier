import copy
from contextlib import closing
import json
import sqlite3
import unittest
from unittest.mock import patch
from uuid import uuid4
import httpx
from backend import main, jobs, gallery, progress, experiment_store, test_api, test_submissions, test_image_workflows, test_gallery


class ExperimentRunTests(unittest.TestCase):
    setUp = test_api.ApiTests.setUp
    tearDown = test_api.ApiTests.tearDown
    remote = test_submissions.SubmissionTests.remote

    def saved(self, settings=None):
        if settings is None:
            settings = main.DraftInput.model_validate(test_submissions.SubmissionTests.payload(self)).model_dump(mode='json',exclude={'revision'})
        preview = self.client.post('/api/experiments/preview',json=dict(title='精確比較',settings=settings,axis='seed',
            values=['9007199254740993','18446744073709551615'],case_ids=[]))
        self.assertEqual(preview.status_code,200,preview.text)
        response = self.client.post('/api/experiments/plans',json=dict(request_id=str(uuid4()),plan=preview.json()))
        self.assertEqual(response.status_code,201,response.text)
        return response.json()

    def body(self, record, index=0):
        variant = record['plan']['variants'][index]
        return copy.deepcopy(variant['settings']) | dict(request_id=str(uuid4()),experiment=dict(
            plan_id=record['id'],plan_sha256=record['plan']['plan_sha256'],variant_id=variant['id']))

    def submit(self, body, remote=None):
        with patch('backend.submissions.httpx.AsyncClient',return_value=remote or self.remote()):
            return self.client.post('/api/generate',json=body)

    def test_submission_freezes_exact_context_and_never_replays_archived_or_offline(self):
        record=self.saved(); body=self.body(record); remote=self.remote()
        response=self.submit(body,remote); self.assertEqual(response.status_code,200,response.text)
        job=response.json(); context=job['experiment_context']
        self.assertEqual(context['settings'],record['plan']['variants'][0]['settings'])
        self.assertEqual(context['settings']['seed'],'9007199254740993')
        self.assertEqual(context['plan_title'],'精確比較')
        self.assertEqual(progress.summary(job)['experiment_context'],context)
        experiment_store.archive(self.db,record['id'],1,True)
        self.client.put('/api/settings',json=dict(comfy_url='http://127.0.0.1:9999'))
        with patch('backend.submissions.httpx.AsyncClient',side_effect=AssertionError('no replay/probe')):
            self.assertEqual(self.client.post('/api/generate',json=body).json(),job)
            for change in [dict(title='changed'),dict(seed='1'),dict(experiment=None),dict(experiment=body['experiment']|dict(variant_id='variant-2'))]:
                self.assertEqual(self.client.post('/api/generate',json=body|change).status_code,409)
        self.assertEqual(remote.post.await_count,1)
        with self.assertRaises(ValueError): jobs.update(self.db,job['id'],experiment_context=None)

    def test_invalid_missing_archived_hash_variant_settings_reject_without_jobs_or_engine(self):
        record=self.saved(); body=self.body(record)
        invalid=[body|dict(experiment=body['experiment']|dict(plan_id=str(uuid4()))),
            body|dict(experiment=body['experiment']|dict(plan_sha256='f'*64)),
            body|dict(experiment=body['experiment']|dict(variant_id='variant-8')),body|dict(cfg=2),body|dict(title='changed'),
            body|dict(loras=[dict(name='unused',enabled=False,strength_model=1,strength_clip=0)])]
        with patch('backend.submissions.httpx.AsyncClient',side_effect=AssertionError('no engine')):
            for candidate in invalid:
                response=self.client.post('/api/generate',json=candidate)
                self.assertEqual(response.status_code,409,response.text)
            experiment_store.archive(self.db,record['id'],1,True)
            self.assertEqual(self.client.post('/api/generate',json=body).status_code,409)
        self.assertEqual(self.client.get('/api/jobs').json(),[])

    def test_context_shape_and_raw_graph_cannot_inject_association(self):
        body=self.body(self.saved())
        with patch('backend.submissions.httpx.AsyncClient',side_effect=AssertionError('no engine')):
            for context in [True,[],body['experiment']|dict(plan_id='bad'),body['experiment']|dict(settings={})]:
                self.assertEqual(self.client.post('/api/generate',json=body|dict(experiment=context)).status_code,422)
            raw={k:body[k] for k in ('request_id','engine_url','checkpoint','experiment')}
            raw['workflow']={'7':dict(class_type='SaveImage',inputs=dict(filename_prefix='ModelAtelier'))}
            self.assertEqual(self.client.post('/api/jobs',json=raw).status_code,422)
        self.assertEqual(self.client.get('/api/jobs').json(),[])

    def test_archive_race_is_rechecked_in_reservation_transaction(self):
        record=self.saved(); body=self.body(record); reserve=jobs.reserve
        def race(*args,**kwargs):
            experiment_store.archive(self.db,record['id'],1,True)
            return reserve(*args,**kwargs)
        with patch('backend.jobs.reserve',side_effect=race), patch('backend.submissions.httpx.AsyncClient',side_effect=AssertionError('no engine')):
            self.assertEqual(self.client.post('/api/generate',json=body).status_code,409)
        self.assertEqual(self.client.get('/api/jobs').json(),[])

    def test_corrupted_stored_variant_hash_is_not_trusted(self):
        record=self.saved(); body=self.body(record)
        with closing(sqlite3.connect(self.db)) as db, db:
            record['plan']['variants'][0]['settings']['prompt']='injected'
            db.execute('UPDATE settings SET value=? WHERE key=?',(json.dumps(record),'experiment:'+record['id']))
        body['prompt']='injected'
        with patch('backend.submissions.httpx.AsyncClient',side_effect=AssertionError('no engine')):
            self.assertEqual(self.client.post('/api/generate',json=body).status_code,409)
        self.assertEqual(self.client.get('/api/jobs').json(),[])

    def test_failed_and_ambiguous_jobs_remain_associated_without_resubmission(self):
        record=self.saved()
        for failed in [True,False]:
            body=self.body(record,1); remote=self.remote()
            if failed: remote.get.side_effect=httpx.ConnectError('offline')
            else: remote.post.side_effect=httpx.ReadTimeout('unknown')
            response=self.submit(body,remote)
            job=self.client.get('/api/jobs/'+body['request_id']).json()
            self.assertEqual(job['status'],'failed' if failed else 'unknown')
            self.assertEqual(job['experiment_context']['settings']['seed'],'18446744073709551615')
            with patch('backend.submissions.httpx.AsyncClient',side_effect=AssertionError('no retry')):
                self.assertEqual(self.client.post('/api/generate',json=body).json()['id'],job['id'])
        values=self.client.get('/api/experiments/plans/'+record['id']+'/results').json()['variants']
        self.assertEqual(values[0]['runs'],[])
        self.assertEqual({r['status'] for r in values[1]['runs']},{'failed','unknown'})

    def test_artwork_context_copy_results_and_archive_are_readonly_offline(self):
        record=self.saved(); body=self.body(record); job=self.submit(body).json()
        job=jobs.update(self.db,job['id'],status='completed',history=dict(status=dict(completed=True,status_str='success')))
        source=dict(node_id='7',filename='result.png',subfolder='',type='output')
        artwork,_=gallery.save(self.db,self.db.parent/'artworks',job,source,test_gallery.GalleryTests.image(self))
        self.assertEqual(artwork['experiment_context'],job['experiment_context'])
        job['experiment_context']['settings']['seed']='0'
        self.assertEqual(gallery.get(self.db,artwork['id'])['experiment_context']['settings']['seed'],'9007199254740993')
        gallery.organize(self.db,artwork['id'],0,dict(archived=True))
        experiment_store.archive(self.db,record['id'],1,True)
        before=self.db.read_bytes()
        with patch('backend.main.httpx.AsyncClient',side_effect=AssertionError('read only')):
            result=self.client.get('/api/experiments/plans/'+record['id']+'/results')
            self.assertEqual(result.status_code,200,result.text)
            row=result.json()['variants'][0]['runs'][0]
            self.assertEqual(row['status'],'completed')
            self.assertEqual(row['artworks'][0]['id'],artwork['id'])
            self.assertTrue(row['artworks'][0]['archived'])
            self.assertTrue(row['artworks'][0]['image_available'])
            self.assertEqual(self.client.get('/api/artworks/'+artwork['id']).json()['experiment_context'],artwork['experiment_context'])
        self.assertEqual(before,self.db.read_bytes())

    def test_legacy_same_workflow_is_not_inferred_or_backfilled(self):
        record=self.saved(); body=self.body(record); plain=body|dict(experiment=None)
        job=self.submit(plain).json()
        with closing(sqlite3.connect(self.db)) as db, db:
            job.pop('experiment_context')
            db.execute('UPDATE settings SET value=? WHERE key=?',(json.dumps(job),'job:'+job['id']))
        before=self.db.read_bytes()
        with patch('backend.main.httpx.AsyncClient',side_effect=AssertionError('no engine')):
            self.assertIsNone(self.client.get('/api/jobs/'+job['id']).json()['experiment_context'])
            self.assertEqual(self.client.post('/api/generate',json=body).status_code,409)
            result=self.client.get('/api/experiments/plans/'+record['id']+'/results').json()
            self.assertTrue(all(not v['runs'] for v in result['variants']))
            self.assertEqual(self.client.get('/api/experiments/plans/'+str(uuid4())+'/results').status_code,404)
        self.assertEqual(before,self.db.read_bytes())

    def test_identical_content_saved_under_another_id_is_not_linked(self):
        first=self.saved()
        second=self.client.post('/api/experiments/plans',json=dict(request_id=str(uuid4()),plan=first['plan'])).json()
        self.assertEqual(first['plan']['plan_sha256'],second['plan']['plan_sha256'])
        job=self.submit(self.body(second)).json()
        original=self.client.get('/api/experiments/plans/'+first['id']+'/results').json()
        self.assertTrue(all(not v['runs'] for v in original['variants']))
        copied=self.client.get('/api/experiments/plans/'+second['id']+'/results').json()
        self.assertEqual(copied['variants'][0]['runs'][0]['id'],job['id'])

    def test_artwork_with_different_snapshot_is_not_grouped(self):
        record=self.saved(); job=self.submit(self.body(record)).json()
        source=dict(node_id='7',filename='result.png',subfolder='',type='output')
        job['experiment_context']['settings']['seed']='0'
        gallery.save(self.db,self.db.parent/'artworks',job,source,test_gallery.GalleryTests.image(self))
        result=self.client.get('/api/experiments/plans/'+record['id']+'/results').json()
        self.assertEqual(result['variants'][0]['runs'][0]['artworks'],[])

    def test_image_variant_context_and_original_input_recovery(self):
        image_body=test_image_workflows.ImageWorkflowTests.body(self)
        settings=main.DraftInput.model_validate(image_body).model_dump(mode='json',exclude={'revision'})
        record=self.saved(settings); body=self.body(record)
        remote=test_image_workflows.ImageWorkflowTests.remote(self,body)
        response=self.submit(body,remote); self.assertEqual(response.status_code,200,response.text)
        job=response.json()
        self.assertEqual(job['reference_settings'],job['experiment_context']['settings'])
        self.assertEqual(remote.post.await_count,2)
        (self.db.parent/'assets'/ (self.asset['id']+'.png')).unlink()
        experiment_store.archive(self.db,record['id'],1,True)
        with patch('backend.submissions.httpx.AsyncClient',side_effect=AssertionError('no probe/upload')):
            self.assertEqual(self.client.post('/api/generate',json=body).json(),job)
            self.assertEqual(self.client.post('/api/generate',json=body|dict(experiment=None)).status_code,409)
