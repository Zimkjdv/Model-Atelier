import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from uuid import uuid4
from backend import experiment_plans as plans, main, test_api


class ExperimentPlanTests(unittest.TestCase):
    setUp = test_api.ApiTests.setUp
    tearDown = test_api.ApiTests.tearDown

    def payload(self):
        settings=main.DraftInput(title='基準',engine_url='http://127.0.0.1:8188',checkpoint='model',
            prompt='mountain lake',seed='18446744073709551615',steps=4,cfg=1.0,
            sampler_name='lcm',scheduler='sgm_uniform',loras=[dict(name='one',strength_model=1,strength_clip=0),
                dict(name='two',enabled=False,strength_model=.7,strength_clip=.3)]).model_dump(mode='json',exclude={'revision'})
        return dict(title='比較',settings=settings,axis='steps',values=[4,8],case_ids=[])

    def test_readonly_current_prompt_preview_preserves_unvaried_fields_and_export(self):
        body=self.payload(); before=self.db.read_bytes()
        with patch('backend.main.httpx.AsyncClient',side_effect=AssertionError('no engine')):
            response=self.client.post('/api/experiments/preview',json=body)
            self.assertEqual(response.status_code,200,response.text)
            value=response.json(); self.assertEqual(value['expected_job_count'],2)
            self.assertIsNone(value['suite'])
            for original,row in zip(body['values'],value['variants']):
                self.assertEqual(row['settings']['steps'],original)
                self.assertEqual(row['settings']['seed'],'18446744073709551615')
                for key,v in body['settings'].items():
                    if key not in ('title','steps'): self.assertEqual(row['settings'][key],v,key)
            exported=self.client.post('/api/experiments/export',json=body|dict(expected_plan_sha256=value['plan_sha256']))
            self.assertEqual(exported.status_code,200,exported.text)
            self.assertEqual(exported.json(),value)
            self.assertIn('attachment',exported.headers['content-disposition'])
        self.assertEqual(before,self.db.read_bytes())
        self.assertEqual(self.client.get('/api/jobs').json(),[])
        self.assertEqual(self.client.get('/api/drafts').json(),[])

    def test_fixed_suite_version_hash_prompts_character_pair_and_counts(self):
        suite=self.client.get('/api/experiments/suite').json()
        self.assertEqual(suite['version'],1)
        self.assertEqual(suite['sha256'],hashlib.sha256(plans.SUITE.read_bytes()).hexdigest())
        ids=['traveler-bookshop','traveler-station']
        body=self.payload()|dict(case_ids=ids,axis='cfg',values=[1,5])
        result=self.client.post('/api/experiments/preview',json=body).json()
        self.assertEqual(result['expected_job_count'],4)
        self.assertEqual([v['id'] for v in result['suite']['cases']],ids)
        self.assertEqual(len({v['character_key'] for v in result['suite']['cases']}),1)
        for row in result['variants']:
            case=next(v for v in suite['cases'] if v['id']==row['case_id'])
            self.assertEqual(row['settings']['prompt'],case['prompt'])
            self.assertEqual(row['settings']['steps'],4)
            self.assertEqual(row['settings']['loras'],body['settings']['loras'])
        altered=body|dict(axis='steps',values=[4,8,12],case_ids=[v['id'] for v in suite['cases']])
        self.assertEqual(self.client.post('/api/experiments/preview',json=altered).status_code,422)

    def test_full_seed_axis_is_precise_and_normalized_duplicates_rejected(self):
        body=self.payload()|dict(axis='seed',values=['9007199254740993','18446744073709551615'])
        result=self.client.post('/api/experiments/preview',json=body).json()
        self.assertEqual([v['settings']['seed'] for v in result['variants']],body['values'])
        for axis,values in [('seed',['01','1']),('steps',[4,4]),('cfg',[1,1.0])]:
            self.assertEqual(self.client.post('/api/experiments/preview',json=body|dict(axis=axis,values=values)).status_code,422)

    def test_invalid_or_injected_settings_never_enqueue_write_or_clamp(self):
        body=self.payload(); before=self.db.read_bytes()
        invalid=[dict(axis='loras'),dict(values=[]),dict(values=[1,2,3,4,5]),dict(values=[True]),dict(values=[4.0]),
            dict(axis='seed',values=[9007199254740993]),dict(axis='cfg',values=['5']),dict(values=[151]),
            dict(case_ids=['unknown']),dict(case_ids=['chair','chair']),dict(request_id=str(uuid4())),
            dict(settings=body['settings']|dict(workflow_mode='image2image')),
            dict(settings=body['settings']|dict(reference_ids=[str(uuid4())])),
            dict(settings=body['settings']|dict(workflow={})),dict(settings=body['settings']|dict(checkpoint='')),
            dict(settings=body['settings']|dict(engine_url='http://user:password@localhost')),
            dict(settings=body['settings']|dict(revision=1)),dict(settings={k:v for k,v in body['settings'].items() if k!='cfg'})]
        for change in invalid:
            response=self.client.post('/api/experiments/preview',json=body|change)
            self.assertEqual(response.status_code,422,response.text)
        self.assertEqual(self.client.post('/api/experiments/preview',content=b'x'*262145).status_code,413)
        self.assertEqual(before,self.db.read_bytes())

    def test_export_rejects_changed_preview_and_broken_or_duplicate_suite(self):
        body=self.payload()|dict(case_ids=['chair'])
        value=self.client.post('/api/experiments/preview',json=body).json()
        result=self.client.post('/api/experiments/export',json=body|dict(values=[4,12],expected_plan_sha256=value['plan_sha256']))
        self.assertEqual(result.status_code,409)
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'suite.json'
            original=json.loads(plans.SUITE.read_text(encoding='utf-8'))
            changed=copy.deepcopy(original); changed['cases'][0]['prompt']='changed prompt'
            path.write_text(json.dumps(changed),encoding='utf-8')
            with patch.object(plans,'SUITE',path):
                self.assertEqual(self.client.post('/api/experiments/export',json=body|dict(expected_plan_sha256=value['plan_sha256'])).status_code,409)
            for bad in [original|dict(version=True),original|dict(cases=[original['cases'][0]]*2),dict(other=[]),original|dict(extra=True)]:
                path.write_text(json.dumps(bad),encoding='utf-8')
                with patch.object(plans,'SUITE',path):
                    self.assertEqual(self.client.get('/api/experiments/suite').status_code,503)
                    self.assertEqual(self.client.post('/api/experiments/preview',json=body).status_code,503)
