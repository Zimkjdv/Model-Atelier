import copy
from pathlib import Path
import unittest
from unittest.mock import patch
import httpx
from backend import experiment_plans
from backend.test_animagine_acceptance import AnimaginePlatform
from backend.test_generation_acceptance import Clock
from backend.workflows import build
from scripts import verify_illustration_suite as suite

class SuitePlatform(AnimaginePlatform):
    def __init__(self,model,case,**options):
        super().__init__(**options)
        self.model_id,self.case_id=model,case
        manifest=suite.MODELS[model]
        self.checkpoint=manifest['filename']
        self.job_version=self.artwork_version=manifest['version']
        self.metadata=dict(name=self.checkpoint,architecture='sdxl',version=self.job_version,size_bytes=manifest['size_bytes'],sha256=manifest['sha256'])
        self.settings=suite.settings(self.engine,self.checkpoint,next(v for v in experiment_plans.suite()['cases'] if v['id']==case))
        self.workflow=build(self.settings)

class IllustrationSuiteTests(unittest.TestCase):
    def check(self,platform,previous=None,valid=True):
        clock=Clock()
        cls=type('Fixed',(suite.SuiteAcceptance,),dict(model_id=platform.model_id,case_id=platform.case_id))
        with httpx.Client(base_url='http://127.0.0.1:8001',transport=httpx.MockTransport(platform.handle)) as client,              patch.object(Path,'is_file',return_value=True),patch.object(suite.downloader,'_verified',return_value=valid):
            return cls(client,platform.engine,platform.checkpoint,clock=clock.now,sleep=clock.sleep).run(previous)
    def test_eight_model_case_combinations_are_once_only_and_offline_gets(self):
        for model in suite.MODELS:
            for case in suite.CASES:
                platform=SuitePlatform(model,case,lose_submission=True)
                original=self.check(platform)
                self.assertEqual(original['status'],'passed',original)
                self.assertEqual(original['test_suite']['sha256'],experiment_plans.suite()['sha256'])
                self.assertEqual(original['settings']['seed'],'9007199254740993')
                self.assertEqual(platform.submissions,1)
                platform.seen.clear()
                with patch.object(suite.downloader,'_verified',side_effect=AssertionError('no offline file checks')):
                    verified=self.check(platform,original)
                self.assertEqual(verified['status'],'passed',verified)
                self.assertTrue(all(method=='GET' for method,_ in platform.seen))
    def test_unverified_weight_or_metadata_never_submits_and_corrupt_reports_never_query(self):
        platform=SuitePlatform('pony-v6-xl','chair')
        self.assertEqual(self.check(platform,valid=False)['status'],'failed')
        self.assertEqual(platform.submissions,0)
        original=self.check(platform)
        for field in ['hash','case','model','measurements']:
            previous=copy.deepcopy(original)
            if field=='hash':previous['test_suite']['sha256']='f'*64
            elif field=='case':previous['test_suite']['case']['prompt']='different'
            elif field=='model':previous['model_snapshot']['sha256']='f'*64
            else:
                # A differing original measurement must fail when reading the saved job.
                previous['measurements']={'wrong':True}
            platform.seen.clear()
            value=self.check(platform,previous)
            self.assertEqual(value['status'],'failed')
            if field!='measurements':self.assertEqual(platform.seen,[])
            self.assertTrue(all(method=='GET' for method,_ in platform.seen))
    def test_common_controls_differ_only_in_model_and_case_selection(self):
        for case in suite.CASES:
            a=SuitePlatform('pony-v6-xl',case).settings
            b=SuitePlatform('animagine-xl-4.0-opt',case).settings
            self.assertEqual({k:v for k,v in a.items() if k!='checkpoint'},{k:v for k,v in b.items() if k!='checkpoint'})
            self.assertEqual(a['loras'],[])

    def test_suite_change_during_preflight_never_dispatches_a_job(self):
        platform=SuitePlatform('animagine-xl-4.0-opt','lake')
        original=experiment_plans.suite()
        with patch.object(experiment_plans,'suite',side_effect=[original,original|dict(sha256='f'*64)]):
            value=self.check(platform)
        self.assertEqual(value['status'],'failed')
        self.assertEqual(platform.submissions,0)
        self.assertIsNone(value['job_id'])
