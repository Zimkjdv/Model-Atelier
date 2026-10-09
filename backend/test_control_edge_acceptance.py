import copy
import hashlib
import io
import json
import unittest
from PIL import Image
import httpx
from backend import control_edges as edges,control_edge_workflows as flow
from backend import test_control_acceptance as old
ControlPlatform=old.ControlPlatform
from scripts import verify_control_edge_generation as check


class EdgePlatform(ControlPlatform):
    def __init__(self,profile='seed-a-strength-05',**kwargs):
        super().__init__(**kwargs)
        self.runner=type('FixedEdge',(check.EdgeAcceptance,),dict(source_id=self.source_id,model_id='pony-v6-xl',profile=profile))
        self.settings=self.runner(None,self.engine,self.checkpoint).expected_settings()
        image=Image.new('RGB',(768,768),'black');image.putpixel((10,10),(255,255,255));stream=io.BytesIO();image.save(stream,format='PNG');self.edge=stream.getvalue();self.edge_imports=0;self.edge_saved=False
    def snapshots(self): return super().snapshots()|dict(workflow_id=flow.ID)
    def job(self):
        item=super().job();item['history']['outputs']['16']=dict(images=[dict(filename='canny_00001_.png',subfolder='model_atelier/'+str(self.job_id),type='output')]);return item
    def edge_item(self):
        anchor,source=edges.source(self.job(),lambda value:value)
        return dict(job_id=self.job_id,workflow_id=flow.ID,anchor=anchor,source=source,sha256=hashlib.sha256(self.edge).hexdigest(),size_bytes=len(self.edge),saved_at='2026-10-09T00:00:00Z',**edges.pixels(self.edge,768,768),state='saved',image_available=True,import_allowed=False)
    def handle(self,request):
        path=request.url.path
        if path=='/api/control-edge/generate':
            self.seen.append((request.method,path));self.submissions+=1;body=json.loads(request.content);self.job_id=body.pop('request_id');assert body==self.settings;self.workflow=flow.build(self.settings,self.job_id)
            if self.lose_submission: raise httpx.ReadTimeout('lost',request=request)
            return httpx.Response(200,json=self.job())
        if path in ('/api/jobs/'+str(self.job_id)+'/control-edge','/api/artworks/'+self.artwork_id+'/control-edge'):
            self.seen.append((request.method,path))
            if request.method=='POST': self.edge_imports+=1;self.edge_saved=True
            return httpx.Response(200,json=self.edge_item() if self.edge_saved else dict(state='not_saved'))
        if path=='/api/jobs/'+str(self.job_id)+'/control-edge/image':
            self.seen.append((request.method,path));return httpx.Response(200,content=self.edge)
        return super().handle(request)


class EdgeAcceptanceTests(unittest.TestCase):
    run_check=old.ControlAcceptanceTests.run_check
    def test_four_profiles_preserve_exact_settings_and_get_only_edge_verification(self):
        for profile,(seed,strength) in check.PROFILES.items():
            p=EdgePlatform(profile,lose_submission=True);report,_=self.run_check(p)
            self.assertEqual(report['status'],'passed',report);self.assertEqual(p.submissions,1);self.assertEqual(p.edge_imports,1);self.assertEqual(report['settings']['seed'],seed);self.assertEqual(report['settings']['control_strength'],strength);self.assertEqual(report['edge_output']['metrics']['edge_pixels'],1)
            p.seen.clear();result,_=self.run_check(p,report,verified=False)
            self.assertEqual(result['status'],'passed',result);self.assertTrue(all(method=='GET' for method,_ in p.seen));self.assertEqual(p.edge_imports,1);self.assertEqual(p.submissions,1)
    def test_invalid_edge_report_never_contacts_server_or_emits(self):
        p=EdgePlatform();report,_=self.run_check(p)
        for change in ('hash','pixels','negative','source','anchor','missing','graph'):
            value=copy.deepcopy(report);proof=value['edge_output']
            if change=='hash': proof['decoded_rgb_sha256']='bad'
            elif change=='pixels': proof['metrics']['edge_pixels']=True
            elif change=='negative': proof['metrics']['edge_pixels']=-1
            elif change=='source': proof['source']['node_id']='7'
            elif change=='anchor': proof['anchor']['reference_metadata']=[]
            elif change=='missing': value.pop('edge_output')
            else: value['workflow']['16']['inputs']['images']=['13',False]
            p.seen.clear();result,emitted=self.run_check(p,value)
            self.assertEqual(result['stage'],'validate_report',result);self.assertEqual(p.seen,[]);self.assertEqual(emitted,[])
    def test_offline_missing_edge_cannot_trigger_import_or_generation(self):
        p=EdgePlatform();report,_=self.run_check(p);p.edge_saved=False;p.seen.clear()
        result,_=self.run_check(p,report);self.assertEqual(result['status'],'failed');self.assertTrue(all(method=='GET' for method,_ in p.seen));self.assertEqual(p.edge_imports,1);self.assertEqual(p.submissions,1)
    def test_changed_edge_pixels_are_detected_even_when_valid_png_metadata_changes_together(self):
        p=EdgePlatform();report,_=self.run_check(p);image=Image.new('RGB',(768,768),'black');stream=io.BytesIO();image.save(stream,format='PNG');p.edge=stream.getvalue();p.seen.clear()
        result,_=self.run_check(p,report);self.assertEqual(result['status'],'failed');self.assertIn('Immutable edge proof',result['error']);self.assertTrue(all(method=='GET' for method,_ in p.seen))
    def test_profile_change_rejects_original_report_before_any_request(self):
        p=EdgePlatform();report,_=self.run_check(p);p.runner=type('Other',(p.runner,),dict(profile='seed-b-strength-10'));p.seen.clear()
        result,emitted=self.run_check(p,report);self.assertEqual(result['stage'],'validate_report');self.assertEqual(p.seen,[]);self.assertEqual(emitted,[])
