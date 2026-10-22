import copy
import io
import unittest
from pathlib import Path
from uuid import uuid4
from unittest.mock import patch
import httpx
from PIL import Image
from backend import execution_context,image_workflows,experiment_plans
from backend.test_inpaint_acceptance import InpaintPlatform
from backend.test_generation_acceptance import Clock
from scripts import verify_image_comparison as check


class Platform(InpaintPlatform):
    def __init__(self,denoise=.3,**kwargs):
        super().__init__(**kwargs);self.plan_id=str(uuid4());self.archived=False
        self.runner=type('FixedImage',(check.ImageAcceptance,),dict(source_id=self.source_id,plan_id=self.plan_id,denoise=denoise))
        self.settings=self.runner(None,self.engine,self.checkpoint).expected_settings();self.refs=self.refs[:1]
        self.job_id=str(uuid4());self.workflow=image_workflows.build(self.settings,self.job_id)
        baseline=check.baseline(self.engine,'pony-v6-xl',self.source_id)
        variants=[]
        for i,value in enumerate(check.DENOISE):
            cls=type('Variant',(self.runner,),dict(denoise=value))
            variants.append(dict(id='variant-'+str(i+1),case_id='current-prompt',value=value,settings=cls(None,self.engine,self.checkpoint).expected_settings()))
        plan=dict(kind='model-atelier-comparison-plan',schema_version=1,title=baseline['title'],workflow_id='checkpoint-image2image-v1',baseline=baseline,axis='denoise',values=list(check.DENOISE),suite=None,variants=variants,expected_job_count=2,batch_size=1)
        plan['plan_sha256']=experiment_plans.digest(plan);plan['warnings']=[];self.plan=plan
    def snapshots(self):
        value=super().snapshots();value['workflow_id']='checkpoint-image2image-v1'
        rt=copy.deepcopy(self.runtime);rt['execution_context']=execution_context.capture(dict(engine_url=self.engine,workflow=self.workflow,reference_settings=self.settings),None,'checkpoint-image2image-v1')
        value['runtime_metadata']=rt
        value['experiment_context']=dict(plan_id=self.plan_id,plan_sha256=self.plan['plan_sha256'],variant_id='variant-'+str(check.DENOISE.index(self.settings['denoise'])+1),settings=self.settings)
        return value
    def handle(self,request):
        path=request.url.path
        if path=='/api/generate':
            self.seen.append((request.method,path));self.submissions+=1;body=__import__('json').loads(request.content)
            self.job_id=body.pop('request_id');selection=body.pop('experiment');assert body==self.settings
            assert selection=={k:self.snapshots()['experiment_context'][k] for k in ('plan_id','plan_sha256','variant_id')}
            self.workflow=image_workflows.build(self.settings,self.job_id)
            if self.lose_submission:raise httpx.ReadTimeout('lost',request=request)
            return httpx.Response(200,json=self.job())
        if path=='/api/experiments/plans/'+self.plan_id:
            self.seen.append((request.method,path));return httpx.Response(200,json=dict(id=self.plan_id,archived=self.archived,plan=self.plan))
        if path=='/api/experiments/plans/'+self.plan_id+'/results':
            self.seen.append((request.method,path));return httpx.Response(200,json=dict(variants=[dict(variant_id=v['id'],runs=[dict(id=self.job_id,artworks=[dict(id=self.artwork_id)])] if v['settings']['denoise']==self.settings['denoise'] else []) for v in self.plan['variants']]))
        return super().handle(request)


class ImageComparisonTests(unittest.TestCase):
    def run_check(self,p,previous=None,verified=True):
        clock=Clock();emitted=[]
        with httpx.Client(base_url='http://127.0.0.1:8000',transport=httpx.MockTransport(p.handle)) as client,patch.object(check.downloader,'_paths',return_value=(Path(__file__),None,None,None)),patch.object(check.downloader,'_verified',return_value=verified):
            runner=p.runner(client,p.engine,p.checkpoint,clock=clock.now,sleep=clock.sleep,emit=lambda v:emitted.append(copy.deepcopy(v)))
            return runner.run(previous),emitted
    def test_each_variant_submits_once_and_lost_response_recovers_original(self):
        for value in check.DENOISE:
            p=Platform(value,lose_submission=True);report,_=self.run_check(p)
            self.assertEqual(report['status'],'passed',report);self.assertEqual(p.submissions,1)
            self.assertEqual(report['workflow']['5']['inputs']['denoise'],value)
            self.assertEqual(report['experiment_context']['settings']['seed'],'9007199254740993')
            p.archived=True;p.seen.clear();restored,_=self.run_check(p,report)
            self.assertEqual(restored['status'],'passed',restored);self.assertTrue(all(method=='GET' for method,_ in p.seen));self.assertEqual(p.submissions,1)
    def test_archived_or_bad_weights_block_before_generation(self):
        p=Platform();p.archived=True;report,_=self.run_check(p);self.assertEqual(report['status'],'failed');self.assertEqual(p.submissions,0)
        p=Platform();report,_=self.run_check(p,verified=False);self.assertEqual(report['status'],'failed');self.assertEqual(p.submissions,0)
    def test_altered_report_rejects_before_contact_or_replacement(self):
        p=Platform();report,_=self.run_check(p);self.assertEqual(report['status'],'passed',report)
        for field in ('plan','source','seed','weight'):
            bad=copy.deepcopy(report)
            if field=='plan':bad['plan']['values']=[.1,.6]
            elif field=='source':bad['original_asset']['id']=str(uuid4())
            elif field=='seed':bad['settings']['seed']='1'
            else:bad['weight_anchor']['sha256']='a'*64
            p.seen.clear();result,emitted=self.run_check(p,bad)
            self.assertEqual(result['status'],'failed');self.assertEqual(p.seen,[]);self.assertEqual(emitted,[])
    def test_changed_saved_source_or_association_never_replays(self):
        p=Platform();report,_=self.run_check(p);p.source=b'changed';p.seen.clear();result,_=self.run_check(p,report)
        self.assertEqual(result['status'],'failed');self.assertTrue(all(method=='GET' for method,_ in p.seen));self.assertEqual(p.submissions,1)
    def test_rgb_difference_is_measurement_not_quality(self):
        def png(color):
            stream=io.BytesIO();Image.new('RGB',(64,64),color).save(stream,format='PNG');return stream.getvalue()
        result=check.difference(png('black'),png('white'));self.assertEqual(result['changed_pixels'],4096);self.assertEqual(result['mean_absolute_rgb_delta'],255)
        self.assertIn('not a quality',result['scope'])
