import copy
import hashlib
import json
import unittest
import httpx
from PIL import Image
from backend import inpaint_feather_workflows as flow,test_inpaint_acceptance as old
from scripts import verify_inpaint_feather as check


class FeatherPlatform(old.InpaintPlatform):
    def __init__(self,radius=0,**kwargs):
        super().__init__(**kwargs);self.radius=radius
        self.runner=type('Fixed',(check.FeatherAcceptance,),dict(source_id=self.source_id,mask_id=self.mask_id,radius=radius));self.settings=self.runner(None,self.engine,self.checkpoint).expected_settings()
        mask=Image.new('L',(768,768),0);mask.paste(255,(160,160,608,608));self.mask=old.png(mask.convert('RGB'));alpha=flow.feather(mask,radius);self.blend=old.png(alpha.convert('RGB'))
        source=Image.open(__import__('io').BytesIO(self.source)).copy();generated=Image.new('RGB',(768,768),'red');self.image=old.png(Image.composite(generated,source,alpha))
        prep=self.refs[1]['generation_preprocessing'];prep.update(id='checkpoint-inpaint-mask-input',transparency='white-background',black='preserve',background='#000000',output_format='PNG',size=len(self.mask),sha256=hashlib.sha256(self.mask).hexdigest())
        self.refs[1].update(size=len(self.mask),sha256=prep['sha256'])
        self.refs[1]['blend_preprocessing']=flow.policy(self.settings,prep['sha256'])|dict(size=len(self.blend),sha256=hashlib.sha256(self.blend).hexdigest())
    def snapshots(self): return super().snapshots()|dict(workflow_id=flow.ID)
    def handle(self,request):
        path=request.url.path
        if path=='/api/inpaint-feather/preview':
            self.seen.append((request.method,path));return httpx.Response(200,content=self.blend,headers={'X-Atelier-SHA256':hashlib.sha256(self.blend).hexdigest()})
        if path=='/api/inpaint-feather/generate':
            self.seen.append((request.method,path));self.submissions+=1;body=json.loads(request.content);self.job_id=body.pop('request_id');assert body==self.settings;self.workflow=flow.build(self.settings,self.job_id)
            if self.lose_submission: raise httpx.ReadTimeout('lost',request=request)
            return httpx.Response(200,json=self.job())
        if path=='/api/jobs/'+str(self.job_id)+'/reference-blend-mask':
            self.seen.append((request.method,path));return httpx.Response(200,content=self.blend)
        return super().handle(request)


class FeatherAcceptanceTests(unittest.TestCase):
    run_check=old.InpaintAcceptanceTests.run_check
    def test_two_radii_preserve_exact_seed_preview_and_get_only_verification(self):
        for radius in (0,16):
            p=FeatherPlatform(radius,lose_submission=True);report,_=self.run_check(p);self.assertEqual(report['status'],'passed',report.get('error'));self.assertEqual(p.submissions,1);self.assertEqual(report['mask_metrics']['outside_max_delta'],0);self.assertEqual(report['settings']['seed'],'9007199254740993')
            p.seen.clear();value,_=self.run_check(p,report);self.assertEqual(value['status'],'passed',value);self.assertTrue(all(m=='GET' for m,_ in p.seen));self.assertEqual(p.submissions,1)
    def test_invalid_blend_report_is_rejected_without_any_request_or_emit(self):
        p=FeatherPlatform(16);report,_=self.run_check(p)
        for change in ('radius','alpha','preview','hash','graph','metadata','mean'):
            value=copy.deepcopy(report)
            if change=='radius': value['settings']['feather_radius']=True
            elif change=='alpha': value['feather_metrics']['outside_alpha_nonzero_pixels']=1
            elif change=='preview': value['preview_sha256']='a'*64
            elif change=='hash': value['blend_mask_proof']['decoded_luma_sha256']='bad'
            elif change=='graph': value['workflow']['14']['inputs']['mask']=['13',0]
            elif change=='metadata': value['reference_metadata'][1]['blend_preprocessing']['binary_sha256']='a'*64
            else: value['feather_metrics']['boundary_mean_delta']=False
            p.seen.clear();result,emitted=self.run_check(p,value);self.assertEqual(result['stage'],'validate_report',result);self.assertEqual(p.seen,[]);self.assertEqual(emitted,[])
    def test_changed_saved_blend_fails_with_gets_only(self):
        p=FeatherPlatform(16);report,_=self.run_check(p);p.blend=old.png(Image.new('RGB',(768,768),'black'));p.seen.clear();result,_=self.run_check(p,report)
        self.assertEqual(result['status'],'failed');self.assertTrue(all(m=='GET' for m,_ in p.seen));self.assertEqual(p.submissions,1)
    def test_metrics_measure_fixed_boundary_and_reject_outward_blend(self):
        a=FeatherPlatform(0);b=FeatherPlatform(16)
        hard=check.feather_metrics(a.mask,a.blend,a.source,a.image);soft=check.feather_metrics(b.mask,b.blend,b.source,b.image)
        self.assertEqual(hard['boundary_pixels'],soft['boundary_pixels']);self.assertLess(soft['boundary_mean_delta'],hard['boundary_mean_delta']);self.assertGreater(soft['alpha_transition_pixels'],0)
        with self.assertRaisesRegex(ValueError,'leaks'): check.feather_metrics(a.mask,old.png(Image.new('RGB',(768,768),'white')),a.source,a.image)
    def test_wrong_radius_report_never_submits_or_repairs_missing_input(self):
        p=FeatherPlatform();report,_=self.run_check(p);p.runner=type('Changed',(p.runner,),dict(radius=16));p.seen.clear();result,emitted=self.run_check(p,report)
        self.assertEqual(result['stage'],'validate_report');self.assertEqual(p.seen,[]);self.assertEqual(emitted,[])
