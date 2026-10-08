import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4
import httpx
from backend import control_workflows as flow
from backend.test_generation_acceptance import Platform,Clock
from scripts import verify_control_generation as check,install_model


class ControlPlatform(Platform):
    def __init__(self,**kwargs):
        super().__init__(**kwargs);self.source_id=str(uuid4())
        self.runner=type('Fixed',(check.ControlAcceptance,),dict(source_id=self.source_id))
        runner=self.runner(None,self.engine,self.checkpoint);self.settings=runner.expected_settings()
        def record(m): return dict(name=m['filename'],version=m['version'],architecture='sdxl',sha256=m['sha256'],size_bytes=m['size_bytes'],source_url=m['source']['page_url'],listed=True)
        self.model=record(runner.manifest);self.control=record(check.CONTROL)|dict(kind='canny',role='controlnet')
        self.job_version=self.artwork_version=runner.manifest['version'];self.source=self.image
        prep=dict(width=768,height=768,resize='fit',version=1,sha256=hashlib.sha256(self.source).hexdigest(),size=len(self.source))
        self.refs=[dict(id=self.source_id,width=768,height=768,size=len(self.source),sha256=prep['sha256'],input_role='structure',generation_preprocessing=prep,archived=False,control_preprocessing=dict(id='comfy-native-canny',version=1,low_threshold=0.4,high_threshold=0.8,execution='original-engine',node_version=None))]
        self.runtime=dict(platform=dict(python='3.12'),engine=dict(comfyui_version='0.34.0'))
    def snapshots(self): return dict(workflow_id=flow.ID,reference_settings=self.settings,reference_metadata=self.refs,model_metadata=self.model,component_metadata=[self.control],runtime_metadata=self.runtime,measurements=None,lora_metadata=[])
    def job(self): return super().job()|self.snapshots()
    def artwork(self): return super().artwork()|self.snapshots()
    def handle(self,request):
        path=request.url.path
        if path=='/api/control/generate':
            self.submissions+=1;body=json.loads(request.content);self.job_id=body['request_id'];self.workflow=flow.build(self.settings,self.job_id)
            if self.lose_submission: raise httpx.ReadTimeout('lost',request=request)
            value=self.job()
        elif path=='/api/models': value=dict(engine_url=self.engine,sync_error=None,models=[self.model])
        elif path=='/api/controlnets/sync': value=dict(engine_url=self.engine,synced_at='time',sync_error=None,controlnets=[self.control])
        elif path=='/api/assets': value=self.refs
        elif path in ('/api/jobs/'+str(self.job_id)+'/creation-settings','/api/artworks/'+self.artwork_id+'/creation-settings'):
            value=dict(settings=self.settings|self.restore_override,model_version=self.job_version,reference_metadata=self.refs,component_metadata=[self.control],runtime_metadata=self.runtime)
        elif path=='/api/jobs/'+str(self.job_id)+'/reference-image': value=self.source
        else: return super().handle(request)
        self.seen.append((request.method,path))
        return httpx.Response(200,content=value) if isinstance(value,bytes) else httpx.Response(200,json=value)


class ControlAcceptanceTests(unittest.TestCase):
    def run_check(self,p,previous=None,verified=True):
        clock=Clock();emitted=[]
        with httpx.Client(base_url='http://127.0.0.1:8000',transport=httpx.MockTransport(p.handle)) as client,patch.object(check.downloader,'_paths',return_value=(Path(__file__),None,None,None)),patch.object(check.downloader,'_verified',return_value=verified):
            runner=p.runner(client,p.engine,p.checkpoint,clock=clock.now,sleep=clock.sleep,emit=lambda v:emitted.append(copy.deepcopy(v)))
            return runner.run(previous),emitted
    def test_one_submission_original_graph_and_get_only_offline_evidence(self):
        p=ControlPlatform(lose_submission=True);report,emitted=self.run_check(p)
        self.assertEqual(report['status'],'passed',report);self.assertEqual(p.submissions,1)
        self.assertEqual(next(r for r in emitted if r['stage']=='submit_once')['workflow'],flow.build(report['settings'],report['job_id']))
        self.assertEqual(report['workflow']['4']['class_type'],'EmptyLatentImage');self.assertEqual(report['component_metadata'][0]['sha256'],check.CONTROL['sha256'])
        p.seen.clear();value,_=self.run_check(p,report,verified=False)
        self.assertEqual(value['status'],'passed',value);self.assertTrue(all(m=='GET' for m,_ in p.seen));self.assertEqual(p.submissions,1)
    def test_bad_control_or_source_report_never_contacts_platform_or_replaces_report(self):
        p=ControlPlatform();report,_=self.run_check(p)
        for change in ('graph','role','kind','hash','seed','prep','source','types','revision','extra'):
            value=copy.deepcopy(report)
            if change=='graph': value['workflow']['15']['inputs']['positive']=['3',0]
            elif change=='role': value['reference_metadata'][0]['input_role']='source'
            elif change=='kind': value['component_metadata'][0]['kind']='depth'
            elif change=='hash': value['component_metadata'][0]['sha256']='a'*64
            elif change=='seed': value['settings']['seed']='9007199254740992'
            elif change=='prep': value['reference_metadata'][0]['control_preprocessing']['version']=True
            elif change=='source': value['reference_metadata'][0]['generation_preprocessing']['sha256']='wrong'
            elif change=='types': value['settings']['control_start']=False
            elif change=='revision': value['local_weights_verified'][1]['revision']='a'*40
            elif change=='extra': value['component_metadata'].append(value['component_metadata'][0])
            p.seen.clear();result,emitted=self.run_check(p,value)
            self.assertEqual(result['stage'],'validate_report',result);self.assertEqual(p.seen,[]);self.assertEqual(emitted,[])
    def test_changed_saved_input_or_restore_is_detected_without_writes(self):
        p=ControlPlatform();report,_=self.run_check(p);p.source=b'other';p.seen.clear()
        result,_=self.run_check(p,report);self.assertEqual(result['status'],'failed');self.assertIn('checksum',result['error']);self.assertTrue(all(m=='GET' for m,_ in p.seen))
        p=ControlPlatform();report,_=self.run_check(p);p.restore_override=dict(control_strength=0.9);p.seen.clear()
        result,_=self.run_check(p,report);self.assertEqual(result['status'],'failed');self.assertTrue(all(m=='GET' for m,_ in p.seen));self.assertEqual(p.submissions,1)
    def test_missing_fixed_weight_blocks_before_generation(self):
        p=ControlPlatform();result,_=self.run_check(p,verified=False)
        self.assertEqual(result['status'],'failed');self.assertEqual(p.submissions,0);self.assertIsNone(result['job_id'])
    def test_cpu_fallback_and_unknown_control_registry_cannot_pass_gpu_acceptance(self):
        p=ControlPlatform();p.device_type='cpu';result,_=self.run_check(p);self.assertEqual(result['status'],'failed');self.assertEqual(p.submissions,0)
        p=ControlPlatform();p.control['kind']='unknown';result,_=self.run_check(p);self.assertEqual(result['status'],'failed');self.assertEqual(p.submissions,0)


class ControlInstallTests(unittest.TestCase):
    def test_control_target_is_scoped_and_check_is_readonly(self):
        with tempfile.TemporaryDirectory() as d:
            workspace=Path(d);value=install_model.manifest(check.CONTROL['id']);report=install_model.plan(value,workspace=workspace)
            self.assertEqual(Path(report['target']).parent,workspace/'runtime/ComfyUI/models/controlnet');self.assertEqual(list(workspace.iterdir()),[])
            for identifier in ('pony-v6-xl','animagine-xl-4.0-opt','lcm-lora-sdxl'):
                target=check.downloader._paths(workspace,install_model.manifest(identifier)['filename'],create=False)[0]
                self.assertNotEqual(target.parent,Path(report['target']).parent)
    def test_stream_resume_publishes_only_control_and_never_overwrites(self):
        with tempfile.TemporaryDirectory() as d:
            workspace=Path(d);raw=b'control weight fixture';value=check.CONTROL|dict(size_bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())
            target,partial,_,_=check.downloader._paths(workspace,value['filename']);partial.write_bytes(raw[:5])
            def handle(r):
                self.assertEqual(r.headers['range'],'bytes=5-');return httpx.Response(206,stream=httpx.ByteStream(raw[5:]),headers={'Content-Range':f'bytes 5-{len(raw)-1}/{len(raw)}'})
            with httpx.Client(transport=httpx.MockTransport(handle)) as client:
                result=check.downloader.install(workspace=workspace,manifest=value,client=client,output=lambda _:None)
            self.assertEqual(target.read_bytes(),raw);self.assertTrue(result['verified']);self.assertFalse((workspace/'runtime/ComfyUI/models/checkpoints').exists())
            target.write_bytes(b'wrong')
            with self.assertRaises(check.downloader.InstallationError): check.downloader.install(workspace=workspace,manifest=value,output=lambda _:None)
            self.assertEqual(target.read_bytes(),b'wrong')
    def test_unpinned_control_source_rejected_before_writes(self):
        with tempfile.TemporaryDirectory() as d:
            workspace=Path(d)
            for change in [dict(filename='../x.safetensors'),dict(source=check.CONTROL['source']|dict(revision='main')),dict(source=check.CONTROL['source']|dict(download_url='https://example.com/other'))]:
                with self.assertRaises(check.downloader.InstallationError): check.downloader.install(workspace=workspace,manifest=check.CONTROL|change)
            self.assertEqual(list(workspace.iterdir()),[])
