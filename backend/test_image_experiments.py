import unittest
from unittest.mock import patch
from uuid import uuid4
from backend import main, test_api, test_image_workflows, workflows


class ImageExperimentTests(unittest.TestCase):
    setUp = test_api.ApiTests.setUp
    tearDown = test_api.ApiTests.tearDown
    upload = test_api.ApiTests.upload

    def payload(self):
        asset = self.upload()
        settings = main.DraftInput(title='圖生圖',engine_url='http://127.0.0.1:8188',checkpoint='model',
            workflow_mode='image2image', image_asset_id=asset['id'],reference_ids=[asset['id']],
            reference_resize='stretch',prompt='mountain lake',seed='9007199254740993',denoise=.45,
            loras=[dict(name='first',strength_model=.5,strength_clip=0)]).model_dump(mode='json',exclude={'revision'})
        return dict(title='圖生圖比較',settings=settings,axis='denoise',values=[0,.6,1],case_ids=[])

    def test_denoise_preview_export_preserve_source_and_unvaried_settings_without_dispatch(self):
        body=self.payload(); before=self.db.read_bytes()
        with patch('backend.main.httpx.AsyncClient',side_effect=AssertionError('no engine')):
            response=self.client.post('/api/experiments/preview',json=body)
            self.assertEqual(response.status_code,200,response.text)
            plan=response.json()
            self.assertEqual(plan['workflow_id'],'checkpoint-image2image-v1')
            for v,row in zip(body['values'],plan['variants']):
                self.assertEqual(row['settings']['denoise'],v)
                self.assertEqual({k:x for k,x in row['settings'].items() if k not in ('denoise','title')},
                                 {k:x for k,x in body['settings'].items() if k not in ('denoise','title')})
            exported=self.client.post('/api/experiments/export',json=body|dict(expected_plan_sha256=plan['plan_sha256']))
            self.assertEqual(exported.json(),plan)
        self.assertEqual(before,self.db.read_bytes())
        self.assertEqual(self.client.get('/api/jobs').json(),[])

    def test_malformed_source_text_denoise_and_invalid_values_never_create_jobs(self):
        body=self.payload()
        for change in [dict(image_asset_id=None),dict(reference_ids=[]),dict(reference_ids=[str(uuid4())]),
                       dict(reference_ids=body['settings']['reference_ids']+[str(uuid4())]),dict(reference_resize='crop')]:
            self.assertEqual(self.client.post('/api/experiments/preview',json=body|dict(settings=body['settings']|change)).status_code,422)
        text=body['settings']|dict(workflow_mode='text2image',image_asset_id=None,reference_ids=[])
        self.assertEqual(self.client.post('/api/experiments/preview',json=body|dict(settings=text)).status_code,422)
        for values in [[True],['0.5'],[-.1],[1.1],[0,0.0]]:
            self.assertEqual(self.client.post('/api/experiments/preview',json=body|dict(values=values)).status_code,422)
        self.assertEqual(self.client.get('/api/jobs').json(),[])

    def test_missing_image_warns_and_fixed_cases_keep_source_and_precise_seed(self):
        body=self.payload()|dict(case_ids=['chair','lake'],axis='seed',values=['9007199254740993','18446744073709551615'])
        (main.DATA/'assets'/(body['settings']['image_asset_id']+'.png')).unlink()
        plan=self.client.post('/api/experiments/preview',json=body).json()
        self.assertTrue(any('本機不可用' in v for v in plan['warnings']))
        self.assertEqual(plan['expected_job_count'],4)
        for row in plan['variants']:
            self.assertEqual(row['settings']['image_asset_id'],body['settings']['image_asset_id'])
            self.assertEqual(row['settings']['reference_resize'],'stretch')
            self.assertEqual(row['settings']['denoise'],.45)
        lora=self.client.post('/api/experiments/preview',json=body|dict(axis='lora_strength_clip',target_lora='first',values=[0,.5]))
        self.assertEqual(lora.status_code,200,lora.text)

    def test_loaded_variant_requires_explicit_new_generation_then_restores_exact_image_settings(self):
        raw=test_image_workflows.ImageWorkflowTests.body(self)
        settings=main.DraftInput.model_validate(raw).model_dump(mode='json',exclude={'revision'})
        body=dict(title='實驗',settings=settings,axis='denoise',values=[.3,.6],case_ids=[])
        plan=self.client.post('/api/experiments/preview',json=body).json()
        self.assertEqual(self.client.get('/api/jobs').json(),[])
        selected=plan['variants'][1]['settings']
        request=selected|dict(request_id=str(uuid4()))
        remote=test_image_workflows.ImageWorkflowTests.remote(self,request)
        with patch('backend.submissions.httpx.AsyncClient',return_value=remote):
            result=self.client.post('/api/generate',json=request)
        self.assertEqual(result.status_code,200,result.text)
        job=result.json()
        self.assertEqual(job['workflow']['5']['inputs']['denoise'],.6)
        restored=workflows.extract(job|dict(source=dict(node_id='7')),lambda v:main.DraftInput.model_validate(v).model_dump(mode='json',exclude={'revision'}))
        self.assertEqual(restored,selected)
        self.assertEqual(remote.post.await_count,2)
