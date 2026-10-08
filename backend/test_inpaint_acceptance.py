import copy
import hashlib
import io
import json
import unittest
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4
import httpx
from PIL import Image
from backend import inpaint_workflows
from backend.test_generation_acceptance import Platform,Clock
from scripts import verify_inpaint_generation as check


def png(image):
    stream=io.BytesIO();image.save(stream,format='PNG');return stream.getvalue()


class InpaintPlatform(Platform):
    def __init__(self,**kwargs):
        super().__init__(**kwargs)
        self.source_id,self.mask_id=str(uuid4()),str(uuid4())
        self.runner=type('Fixed',(check.InpaintAcceptance,),dict(source_id=self.source_id,mask_id=self.mask_id))
        runner=self.runner(None,self.engine,self.checkpoint)
        self.settings=runner.expected_settings();manifest=runner.manifest
        self.model=dict(name=manifest['filename'],version=manifest['version'],architecture='sdxl',sha256=manifest['sha256'],size_bytes=manifest['size_bytes'],listed=True)
        self.job_version=self.artwork_version=manifest['version']
        image=Image.new('RGB',(768,768),'green');self.source=png(image)
        mask=Image.new('RGB',(768,768),'black');mask.putpixel((10,10),(255,255,255));self.mask=png(mask)
        image.putpixel((10,10),(255,0,0));self.image=png(image)
        self.refs=[]
        for index,(identifier,raw) in enumerate(((self.source_id,self.source),(self.mask_id,self.mask))):
            prep=dict(width=768,height=768,resize='fit',version=1,sha256=hashlib.sha256(raw).hexdigest(),size=len(raw))
            if index: prep.update(threshold=128,white='edit',black='preserve',resampling='NEAREST',output_mode='RGB')
            self.refs.append(dict(id=identifier,width=1024,height=1024,size=len(raw),sha256=hashlib.sha256(raw).hexdigest(),input_role='mask' if index else 'source',generation_preprocessing=prep,archived=False))
        self.runtime=dict(platform=dict(python='3.12'),engine=dict(comfyui_version='0.34.0'))
    def snapshots(self):
        return dict(workflow_id=inpaint_workflows.ID,reference_settings=self.settings,reference_metadata=self.refs,model_metadata=self.model,runtime_metadata=self.runtime,measurements=None,lora_metadata=[])
    def job(self): return super().job()|self.snapshots()
    def artwork(self): return super().artwork()|self.snapshots()
    def handle(self,request):
        path=request.url.path
        special=True
        if path=='/api/inpaint/generate':
            self.submissions+=1;body=json.loads(request.content);self.job_id=body['request_id'];self.workflow=inpaint_workflows.build(self.settings,self.job_id)
            if self.lose_submission: raise httpx.ReadTimeout('lost',request=request)
            value=self.job()
        elif path=='/api/models': value=dict(engine_url=self.engine,sync_error=None,models=[self.model])
        elif path=='/api/assets': value=self.refs
        elif path=='/api/jobs/'+str(self.job_id)+'/creation-settings' or path=='/api/artworks/'+self.artwork_id+'/creation-settings':
            value=dict(settings=self.settings|self.restore_override,model_version=self.job_version,reference_metadata=self.refs,runtime_metadata=self.runtime)
        elif path=='/api/jobs/'+str(self.job_id)+'/reference-image': value=self.source
        elif path=='/api/jobs/'+str(self.job_id)+'/reference-mask': value=self.mask
        else: special=False
        if not special: return super().handle(request)
        self.seen.append((request.method,path))
        return httpx.Response(200,content=value) if isinstance(value,bytes) else httpx.Response(200,json=value)


class InpaintAcceptanceTests(unittest.TestCase):
    def run_check(self,platform,previous=None):
        clock=Clock();emitted=[]
        with httpx.Client(base_url='http://127.0.0.1:8000',transport=httpx.MockTransport(platform.handle)) as client, patch.object(check.downloader,'_paths',return_value=(Path(__file__),None,None,None)),patch.object(check.downloader,'_verified',return_value=True):
            runner=platform.runner(client,platform.engine,platform.checkpoint,clock=clock.now,sleep=clock.sleep,emit=lambda value:emitted.append(copy.deepcopy(value)))
            return runner.run(previous),emitted
    def test_one_submission_owned_graph_and_offline_get_only(self):
        platform=InpaintPlatform(lose_submission=True);report,emitted=self.run_check(platform)
        self.assertEqual(report['status'],'passed',report);self.assertEqual(platform.submissions,1)
        self.assertEqual(report['mask_metrics']['outside_changed_pixels'],0);self.assertEqual(report['mask_metrics']['inside_changed_pixels'],1)
        self.assertEqual(report['workflow']['13']['inputs']['channel'],'red')
        before=next(v for v in emitted if v['stage']=='submit_once');self.assertEqual(before['workflow'],inpaint_workflows.build(report['settings'],report['job_id']))
        platform.seen.clear();verified,_=self.run_check(platform,report)
        self.assertEqual(verified['status'],'passed',verified);self.assertTrue(all(method=='GET' for method,_ in platform.seen));self.assertEqual(platform.submissions,1)
    def test_wrong_input_checksum_during_recovery_never_writes(self):
        platform=InpaintPlatform();report,_=self.run_check(platform);self.assertEqual(report['status'],'passed')
        platform.mask=png(Image.new('RGB',(768,768),'white'));platform.seen.clear()
        value,_=self.run_check(platform,report);self.assertEqual(value['status'],'failed');self.assertIn('checksum',value['error']);self.assertTrue(all(method=='GET' for method,_ in platform.seen))
    def test_invalid_report_cannot_contact_platform_or_replace_original(self):
        platform=InpaintPlatform();report,_=self.run_check(platform)
        for change in ('workflow','mask','seed','metrics','policy','role','type'):
            value=copy.deepcopy(report)
            if change=='workflow': value['workflow']['13']['inputs']['channel']='alpha'
            if change=='mask': value['reference_metadata'][1]['generation_preprocessing']['sha256']='wrong'
            if change=='seed': value['settings']['seed']='9007199254740992'
            if change=='metrics': value['mask_metrics']['outside_max_delta']=2
            if change=='policy': value['reference_metadata'][1]['generation_preprocessing']['white']='preserve'
            if change=='role': value['reference_metadata'][1]['input_role']='source'
            if change=='type': value['mask_metrics']['outside_max_delta']=False
            platform.seen.clear();result,emitted=self.run_check(platform,value)
            self.assertEqual(result['stage'],'validate_report',result);self.assertEqual(platform.seen,[]);self.assertEqual(emitted,[])
    def test_snapshot_and_exact_mask_restoration_changes_are_detected(self):
        platform=InpaintPlatform();report,_=self.run_check(platform)
        platform.restore_override={'mask_asset_id':str(uuid4())};platform.seen.clear()
        result,_=self.run_check(platform,report);self.assertEqual(result['status'],'failed');self.assertTrue(all(m=='GET' for m,_ in platform.seen));self.assertEqual(platform.submissions,1)
    def test_preservation_metric_rejects_outside_changes_gray_masks_and_no_edits(self):
        source=Image.new('RGB',(8,8),(50,60,70));mask=Image.new('RGB',(8,8),'black');mask.putpixel((0,0),(255,255,255));result=source.copy();result.putpixel((0,0),(255,0,0))
        self.assertEqual(check.mask_metrics(png(source),png(mask),png(result))['outside_max_delta'],0)
        result.putpixel((7,7),(51,60,70));self.assertEqual(check.mask_metrics(png(source),png(mask),png(result))['outside_max_delta'],1)
        result.putpixel((7,7),(52,60,70))
        with self.assertRaisesRegex(ValueError,'outside'): check.mask_metrics(png(source),png(mask),png(result))
        mask.putpixel((1,1),(128,128,128))
        with self.assertRaisesRegex(ValueError,'binary'): check.mask_metrics(png(source),png(mask),png(source))
        mask.putpixel((1,1),(0,0,0))
        with self.assertRaisesRegex(ValueError,'No change'): check.mask_metrics(png(source),png(mask),png(source))
