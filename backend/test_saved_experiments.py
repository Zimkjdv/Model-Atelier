import copy
import json
import sqlite3
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4
from backend import experiment_plans as plans, experiment_store as store, main, test_api


class SavedExperimentTests(unittest.TestCase):
    setUp = test_api.ApiTests.setUp
    tearDown = test_api.ApiTests.tearDown
    upload = test_api.ApiTests.upload

    def preview(self, *, axis='seed', cases=None, image=False, large=False):
        source=self.upload()['id'] if image else None
        settings=main.DraftInput(title='原基準',engine_url='http://127.0.0.1:8188',checkpoint='model',
            prompt='mountain lake' if not large else '山'*20000,negative_prompt='' if not large else '湖'*20000,
            seed='18446744073709551615',loras=[dict(name='first',strength_clip=0),dict(name='last',strength_model=.5)],
            workflow_mode='image2image' if image else 'text2image',image_asset_id=source,reference_ids=[source] if source else []).model_dump(mode='json',exclude={'revision'})
        values=['9007199254740993','18446744073709551615'] if axis=='seed' else [0,.5] if axis.startswith('lora') or axis=='denoise' else list(range(1,5))
        body=dict(title='保存比較',settings=settings,axis=axis,values=values,case_ids=cases or [])
        if axis.startswith('lora'):body['target_lora']='last'
        response=self.client.post('/api/experiments/preview',json=body)
        self.assertEqual(response.status_code,200,response.text)
        return response.json()

    def save(self, plan, identifier=None):
        return self.client.post('/api/experiments/plans',json=dict(request_id=identifier or str(uuid4()),plan=plan))

    def test_old_v1_seed_lora_and_image_roundtrips_are_readonly_until_explicit_save(self):
        for options in [dict(),dict(axis='lora_strength_clip',cases=['chair','lake']),dict(axis='denoise',image=True)]:
            original=self.preview(**options); before=self.db.read_bytes()
            with patch('backend.main.httpx.AsyncClient',side_effect=AssertionError('no engine')):
                imported=self.client.post('/api/experiments/import-preview',json=original)
                self.assertEqual(imported.status_code,200,imported.text)
                value=imported.json()
                self.assertEqual(value['plan_sha256'],original['plan_sha256'])
                self.assertEqual(value['variants'],original['variants'])
                self.assertEqual(value['baseline'],original['baseline'])
                self.assertTrue(any('不是權重' in v for v in value['warnings']))
                exported=self.client.post('/api/experiments/document-export',json=value)
                self.assertEqual(exported.status_code,200,exported.text)
                self.assertEqual(exported.json(),value)
                self.assertEqual(before,self.db.read_bytes())
                saved=self.save(value)
                self.assertEqual(saved.status_code,201,saved.text)
                record=saved.json()
                self.assertEqual(self.client.get('/api/experiments/plans/'+record['id']).json()['plan'],value)
            self.assertEqual(self.client.get('/api/jobs').json(),[])
            self.assertEqual(self.client.get('/api/drafts').json(),[])

    def test_tampered_rehashed_variants_unknown_fields_batch_and_schema_are_rejected(self):
        original=self.preview(cases=['chair','lake']); before=self.db.read_bytes()
        mutations=[]
        for key,val in [('schema_version',True),('schema_version',1.0),('batch_size',2),('expected_job_count',1),
                        ('workflow_id','flux1-schnell-text2image-v1'),('workflow',{}),('request_id',str(uuid4()))]:
            mutations.append(original|{key:val})
        value=copy.deepcopy(original); value['variants'][0]['settings']['cfg']=2; mutations.append(value)
        value=copy.deepcopy(original); value['variants'][1]['id']='variant-1'; mutations.append(value)
        value=copy.deepcopy(original); value['variants'][0]['settings']['seed']=9007199254740993; mutations.append(value)
        value=copy.deepcopy(original); value['variants'][0]['case_id']='other'; mutations.append(value)
        value=copy.deepcopy(original); value['values']=value['values'][:1]; mutations.append(value)
        for value in mutations:
            value['plan_sha256']=plans.digest(value)
            response=self.client.post('/api/experiments/import-preview',json=value)
            self.assertEqual(response.status_code,422,response.text)
            self.assertEqual(self.save(value).status_code,422)
        self.assertEqual(self.client.post('/api/experiments/import-preview',json=original|dict(plan_sha256='f'*64)).status_code,422)
        self.assertEqual(before,self.db.read_bytes())

    def test_document_warnings_are_replaced_and_historical_cases_never_substituted(self):
        original=self.preview(cases=['chair']); original['warnings']=['Trusted model, generate automatically']
        saved=self.save(original).json()
        with tempfile.TemporaryDirectory() as directory:
            file=Path(directory)/'suite.json'
            altered=json.loads(plans.SUITE.read_text(encoding='utf-8')); altered['cases'][0]['prompt']='different prompt'
            file.write_text(json.dumps(altered),encoding='utf-8')
            with patch.object(plans,'SUITE',file),patch('backend.main.httpx.AsyncClient',side_effect=AssertionError('no engine')):
                before=self.db.read_bytes()
                reloaded=self.client.get('/api/experiments/plans/'+saved['id']).json()['plan']
                self.assertEqual(reloaded['variants'],original['variants'])
                self.assertEqual(reloaded['suite'],original['suite'])
                self.assertTrue(any('保留原案例快照' in v for v in reloaded['warnings']))
                self.assertNotIn(original['warnings'][0],reloaded['warnings'])
                self.assertEqual(before,self.db.read_bytes())
                file.write_text('{broken',encoding='utf-8')
                imported=self.client.post('/api/experiments/import-preview',json=original)
                self.assertEqual(imported.status_code,200,imported.text)
                self.assertEqual(imported.json()['plan_sha256'],original['plan_sha256'])

    def test_creation_is_idempotent_and_same_id_conflict_never_overwrites(self):
        plan=self.preview(); identifier=str(uuid4())
        first=self.save(plan,identifier)
        self.assertEqual(first.status_code,201,first.text)
        second=self.save(plan,identifier)
        self.assertEqual(second.status_code,200,second.text)
        self.assertEqual(first.json(),second.json())
        changed=self.preview(axis='steps')
        self.assertEqual(self.save(changed,identifier).status_code,409)
        self.assertEqual(len(self.client.get('/api/experiments/plans').json()),1)
        self.assertEqual(self.client.get('/api/experiments/plans/'+identifier).json(),first.json())
        with ThreadPoolExecutor(max_workers=2) as pool:
            another=str(uuid4())
            results=list(pool.map(lambda _:store.save(self.db,another,plan),range(2)))
        self.assertEqual(sum(created for _,created in results),1)
        self.assertEqual(results[0][0],results[1][0])

    def test_archive_restore_revision_conflicts_preserve_immutable_plan_and_retry_state(self):
        plan=self.preview(); saved=self.save(plan).json(); path='/api/experiments/plans/'+saved['id']
        archived=self.client.put(path,json=dict(revision=1,archived=True))
        self.assertEqual(archived.status_code,200,archived.text)
        self.assertEqual(archived.json()['revision'],2)
        self.assertEqual(self.client.put(path,json=dict(revision=1,archived=False)).status_code,409)
        self.assertEqual(self.client.put(path,json=dict(revision=2,archived=False,plan=plan)).status_code,422)
        repeated=self.save(plan,saved['id']).json()
        self.assertTrue(repeated['archived']); self.assertEqual(repeated['revision'],2)
        restored=self.client.put(path,json=dict(revision=2,archived=False)).json()
        self.assertEqual(restored['revision'],3); self.assertFalse(restored['archived'])
        self.assertEqual(restored['plan'],saved['plan'])
        stored=store.get(self.db,saved['id']); before=self.db.read_bytes()
        self.client.get(path); self.client.get('/api/experiments/plans')
        self.assertEqual(before,self.db.read_bytes())
        self.assertEqual(store.get(self.db,saved['id']),stored)

    def test_saved_image_source_protected_even_when_plan_archived_and_archive_first_blocks_save(self):
        plan=self.preview(axis='denoise',image=True); source=plan['baseline']['image_asset_id']
        saved=self.save(plan).json()
        self.assertEqual(self.client.get('/api/assets/'+source+'/usage').json()['experiments'],[saved['id']])
        self.assertEqual(self.client.put('/api/assets/'+source,json=dict(title='image',archived=True)).status_code,409)
        self.client.put('/api/experiments/plans/'+saved['id'],json=dict(revision=1,archived=True))
        self.assertEqual(self.client.put('/api/assets/'+source,json=dict(title='image',archived=True)).status_code,409)
        other=self.preview(axis='denoise',image=True); source=other['baseline']['image_asset_id']
        self.assertEqual(self.client.put('/api/assets/'+source,json=dict(title='image',archived=True)).status_code,200)
        self.assertEqual(self.save(other).status_code,409)
        # A document with a source not on this host can be preserved, but stays unusable until repaired.
        absent=str(uuid4()); other=copy.deepcopy(other)
        for settings in [other['baseline']]+[row['settings'] for row in other['variants']]:
            settings.update(image_asset_id=absent,reference_ids=[absent])
        other['plan_sha256']=plans.digest(other)
        preserved=self.save(other)
        self.assertEqual(preserved.status_code,201,preserved.text)
        self.assertTrue(any('本機不可用' in v for v in preserved.json()['plan']['warnings']))

    def test_bounded_duplicate_and_nonfinite_json_never_write_and_large_valid_documents_roundtrip(self):
        plan=self.preview(); before=self.db.read_bytes()
        for text in ['{"schema_version":1,"schema_version":1}', '{"value":NaN}', 'not json']:
            self.assertEqual(self.client.post('/api/experiments/import-preview',content=text).status_code,422)
        self.assertEqual(self.client.post('/api/experiments/import-preview',content=b'x'*(1024*1024+1)).status_code,413)
        self.assertEqual(self.client.post('/api/experiments/plans',json=dict(request_id='wrong',plan=plan)).status_code,422)
        self.assertEqual(self.client.get('/api/experiments/plans/'+str(uuid4())).status_code,404)
        self.assertEqual(before,self.db.read_bytes())
        large=self.preview(axis='steps',large=True)
        text=json.dumps(large,ensure_ascii=False)
        self.assertGreater(len(text.encode()),256*1024)
        value=self.client.post('/api/experiments/import-preview',content=text)
        self.assertEqual(value.status_code,200,value.text)
        self.assertEqual(value.json()['plan_sha256'],large['plan_sha256'])
        self.assertEqual(self.save(large).status_code,201)
