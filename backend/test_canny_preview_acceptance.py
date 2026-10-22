import base64
import copy
import hashlib
import io
import json
import unittest
from uuid import uuid4
import httpx
from PIL import Image
from backend import canny_preview as preview
from backend.test_control_edge_acceptance import EdgePlatform
from backend import control_edge_workflows as flow
from scripts import verify_canny_preview as check


class Platform(EdgePlatform):
    def __init__(self):
        super().__init__()
        self.job_id=str(uuid4());self.refreshes=2;self.edge_saved=True
        self.workflow=flow.build(self.settings,self.job_id)
        self.bad_info={}

    def handle(self,request):
        if request.url.path=='/api/control/preview':
            self.seen.append((request.method,request.url.path))
            body=json.loads(request.content)
            assert body=={k:self.settings[k] for k in ('image_asset_id','reference_resize','width','height','canny_low','canny_high')}
            info=dict(method=preview.METHOD,device='cpu',dtype='float32',native_sha256=preview.NATIVE_SHA256,
                torch='test',kornia='test',pillow='test',input_sha256=hashlib.sha256(self.source).hexdigest(),
                sha256=hashlib.sha256(self.edge).hexdigest(),**body,
                asset_sha256=self.refs[0]['sha256'],preprocessing=self.refs[0]['generation_preprocessing'])
            info.update(self.bad_info)
            return httpx.Response(200,content=self.edge,headers={'X-Atelier-Canny-Provenance':base64.b64encode(json.dumps(info).encode()).decode()})
        return super().handle(request)


class PreviewAcceptanceTests(unittest.TestCase):
    def run_check(self,p,previous=None,cpu=None):
        with httpx.Client(base_url='http://127.0.0.1:8001',transport=httpx.MockTransport(p.handle)) as client:
            return check.run(client,p.job_id,previous,cpu)

    def test_preview_only_then_get_only_preserve_original_job_and_no_generation(self):
        p=Platform();report,cpu=self.run_check(p)
        self.assertEqual(report['comparison']['differing_pixels'],0)
        self.assertEqual([path for method,path in p.seen if method!='GET'],['/api/control/preview'])
        self.assertEqual(p.submissions,0);self.assertEqual(p.edge_imports,0)
        p.seen.clear();restored,_=self.run_check(p,report,cpu)
        self.assertEqual(restored,report);self.assertTrue(all(method=='GET' for method,_ in p.seen))

    def test_missing_edge_never_imports_or_calculates_preview(self):
        p=Platform();p.edge_saved=False
        with self.assertRaises(ValueError):self.run_check(p)
        self.assertTrue(all(method=='GET' for method,_ in p.seen));self.assertEqual(p.edge_imports,0)

    def test_changed_worker_source_or_saved_cpu_evidence_rejected(self):
        for changes in (dict(input_sha256='a'*64),dict(native_sha256='b'*64),dict(asset_sha256='c'*64),dict(preprocessing={})):
            p=Platform();p.bad_info=changes
            with self.assertRaises((ValueError,preview.PreviewError)):self.run_check(p)
        p=Platform();report,cpu=self.run_check(p);p.seen.clear()
        with self.assertRaises(ValueError):self.run_check(p,report,cpu+b'changed')
        self.assertTrue(all(method=='GET' for method,_ in p.seen))

    def test_changed_report_or_original_history_rejected_during_get_only(self):
        p=Platform();report,cpu=self.run_check(p)
        changed=copy.deepcopy(report);changed['comparison']['differing_pixels']=2
        with self.assertRaises(ValueError):self.run_check(p,changed,cpu)
        p.history_success=False
        with self.assertRaises(ValueError):self.run_check(p,report,cpu)

    def test_comparison_reports_differences_instead_of_claiming_identity(self):
        def png(points):
            image=Image.new('RGB',(64,64),'black')
            for xy in points:image.putpixel(xy,(255,255,255))
            stream=io.BytesIO();image.save(stream,format='PNG');return stream.getvalue()
        result=check.compare(png([(1,1)]),png([(2,2)]),64,64)
        self.assertEqual(result['differing_pixels'],2);self.assertNotEqual(result['cpu_rgb_sha256'],result['native_rgb_sha256'])
        stream=io.BytesIO();Image.new('RGB',(64,64),'red').save(stream,format='PNG')
        with self.assertRaises(ValueError):check.compare(stream.getvalue(),png([]),64,64)
