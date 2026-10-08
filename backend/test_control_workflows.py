import copy
import io
import unittest
from unittest.mock import patch
from uuid import uuid4
import httpx
from PIL import Image
from backend import catalog,control_catalog as records,control_workflows as flow,gallery,jobs,main,test_api,test_image_workflows,test_lora_submissions,loras


def definitions(name='canny.safetensors'):
    floats=lambda low,high:['FLOAT',dict(min=low,max=high)]
    return {
      'LoadImage':dict(input=dict(required=dict(image=[[]])),output=['IMAGE','MASK']),
      'Canny':dict(input=dict(required=dict(image=['IMAGE'],low_threshold=floats(.01,.99),high_threshold=floats(.01,.99))),output=['IMAGE']),
      'ControlNetLoader':dict(input=dict(required=dict(control_net_name=[[name]])),output=['CONTROL_NET']),
      'ControlNetApplyAdvanced':dict(input=dict(required=dict(positive=['CONDITIONING'],negative=['CONDITIONING'],control_net=['CONTROL_NET'],image=['IMAGE'],strength=floats(0,10),start_percent=floats(0,1),end_percent=floats(0,1)),optional=dict(vae=['VAE'])),output=['CONDITIONING','CONDITIONING'])}


class ControlTests(unittest.TestCase):
    setUp=test_api.ApiTests.setUp
    tearDown=test_api.ApiTests.tearDown
    def body(self):
        body=test_image_workflows.ImageWorkflowTests.body(self)
        records.merge(self.db,body['engine_url'],['canny.safetensors'])
        records.update_metadata(self.db,body['engine_url'],'canny.safetensors',dict(architecture='sdxl',kind='canny',version='1',sha256='a'*64))
        return body|dict(workflow_mode='text2image',denoise=1,control_net_name='canny.safetensors',control_strength=.5,control_start=0,control_end=1,canny_low=.4,canny_high=.8)
    def remote(self,body,change=None):
        remote=test_image_workflows.ImageWorkflowTests.remote(self,body);original=remote.get.side_effect
        async def get(url):
            name=url.rsplit('/',1)[-1]
            if name in definitions():
                node=definitions()[name]
                if change: node=change(name,node)
                return httpx.Response(200,request=httpx.Request('GET',url),json={} if node is None else {name:node})
            return await original(url)
        remote.get.side_effect=get;return remote
    def submit(self,body,remote):
        with patch('backend.submissions.httpx.AsyncClient',return_value=remote): return self.client.post('/api/control/generate',json=body)
    def test_exact_owned_graph_empty_latent_precise_seed_and_component_snapshot(self):
        body=self.body();remote=self.remote(body);response=self.submit(body,remote);self.assertEqual(response.status_code,200,response.text)
        job=response.json();g=job['workflow'];self.assertEqual(len(g),11);self.assertEqual(g['4']['class_type'],'EmptyLatentImage')
        self.assertEqual(g['5']['inputs']['positive'],['15',0]);self.assertEqual(g['5']['inputs']['negative'],['15',1]);self.assertEqual(g['15']['inputs']['vae'],['1',2]);self.assertEqual(g['5']['inputs']['seed'],2**64-1)
        self.assertEqual(job['workflow_id'],flow.ID);self.assertEqual(job['component_metadata'][0]['role'],'controlnet');self.assertEqual(job['component_metadata'][0]['version'],'1');self.assertEqual(job['component_metadata'][0]['sha256'],'a'*64)
        self.assertEqual(job['reference_metadata'][0]['control_preprocessing']['node_version'],None);self.assertEqual(job['reference_metadata'][0]['input_role'],'structure')
        self.assertEqual([c.args[0].rsplit('/',1)[-1] for c in remote.post.await_args_list],['image','prompt'])
        self.assertEqual(self.client.get('/api/jobs/'+job['id']+'/reference-image').status_code,200)
        self.assertEqual(self.client.put('/api/assets/'+self.asset['id'],json=dict(title='x',archived=True)).status_code,409)
        with self.assertRaises(ValueError): jobs.update(self.db,job['id'],component_metadata=[])
    def test_strict_bounds_reference_and_wrong_endpoint_do_not_create_job(self):
        body=self.body()
        with patch('backend.submissions.httpx.AsyncClient',side_effect=AssertionError('no engine')):
            for change in (dict(control_strength=0),dict(control_strength=True),dict(control_start=.8,control_end=.8),dict(canny_low=.9,canny_high=.8),dict(canny_high=1),dict(denoise=.9),dict(workflow_mode='image2image'),dict(reference_ids=[]),dict(mask_asset_id=str(uuid4())),dict(width=8192,height=8192)):
                self.assertEqual(self.client.post('/api/control/generate',json=body|change).status_code,422,change)
            self.assertEqual(self.client.post('/api/generate',json=body).status_code,422)
        self.assertEqual(jobs.list_all(self.db),[])
    def test_unknown_incompatible_kind_and_failed_sync_rejected_before_engine(self):
        for change in (dict(architecture='sd1'),dict(architecture='unknown'),dict(kind='depth')):
            body=self.body();records.update_metadata(self.db,body['engine_url'],body['control_net_name'],change)
            with patch('backend.submissions.httpx.AsyncClient',side_effect=AssertionError('no engine')): self.assertEqual(self.client.post('/api/control/generate',json=body).status_code,409)
        body=self.body();records.mutate(self.db,body['engine_url'],lambda v:v.update(sync_error='offline'))
        self.assertEqual(self.submit(body,self.remote(body)).status_code,409);self.assertEqual(jobs.list_all(self.db),[])
    def test_registration_changed_between_capture_and_reserve_is_atomic(self):
        body=self.body();settings=main.ControlInput.model_validate({k:v for k,v in body.items() if k!='request_id'}).model_dump(mode='json',exclude={'revision'})
        snapshot=records.capture(records.read(self.db,body['engine_url'])['controlnets'][0]);source,_=flow.prepare(self.db,self.db.parent,settings)
        records.update_metadata(self.db,body['engine_url'],body['control_net_name'],dict(version='2'))
        with self.assertRaises(ValueError): jobs.reserve(self.db,body['request_id'],body['engine_url'],flow.build(settings,body['request_id']),body['checkpoint'],model_metadata=catalog.capture(catalog.read(self.db,body['engine_url'])['models'][0],body['checkpoint']),workflow_id=flow.ID,component_metadata=[snapshot],reference_metadata=[source],reference_settings=settings)
        self.assertEqual(jobs.list_all(self.db),[])
    def test_changed_during_validation_and_after_upload_never_prompt(self):
        for phase in ('validation','upload'):
            body=self.body();remote=self.remote(body);get=remote.get.side_effect;post=remote.post.side_effect
            async def changed_get(url):
                result=await get(url)
                if phase=='validation' and url.endswith('/Canny'): records.update_metadata(self.db,body['engine_url'],body['control_net_name'],dict(sha256='b'*64))
                return result
            async def changed_post(url,**kwargs):
                result=await post(url,**kwargs)
                if phase=='upload': records.update_metadata(self.db,body['engine_url'],body['control_net_name'],dict(version='new'))
                return result
            remote.get.side_effect=changed_get;remote.post.side_effect=changed_post
            response=self.submit(body,remote);self.assertEqual(response.status_code,409,response.text)
            self.assertEqual(remote.post.await_count,0 if phase=='validation' else 1)
            self.assertEqual(jobs.get(self.db,body['request_id'])['component_metadata'][0]['version'],'1')
    def test_missing_live_control_nodes_or_changed_interface_never_upload(self):
        for problem in ('name','missing','malformed','range'):
            body=self.body()
            def change(name,node):
                if name=='ControlNetLoader' and problem=='name': node['input']['required']['control_net_name']=[[]]
                if name=='Canny' and problem=='missing': return None
                if name=='Canny' and problem=='malformed': node['input']['required']=None
                if name=='ControlNetApplyAdvanced' and problem=='range': node['input']['required']['strength'][1]['max']=.1
                return node
            remote=self.remote(body,change);result=self.submit(body,remote)
            self.assertEqual(result.status_code,409 if problem=='name' else 422,result.text);remote.post.assert_not_awaited()
    def test_offline_and_lost_response_do_not_replay(self):
        body=self.body();remote=self.remote(body);remote.get.side_effect=httpx.ConnectError('offline')
        self.assertEqual(self.submit(body,remote).status_code,503);remote.post.assert_not_awaited()
        body=self.body();remote=self.remote(body);post=remote.post.side_effect
        async def lost(url,**kwargs):
            if url.endswith('/prompt'): raise httpx.ReadTimeout('unknown')
            return await post(url,**kwargs)
        remote.post.side_effect=lost
        self.assertEqual(self.submit(body,remote).json()['status'],'unknown');self.assertEqual(self.submit(body,remote).json()['status'],'unknown');self.assertEqual(remote.post.await_count,2)
    def test_original_request_before_engine_files_and_metadata(self):
        body=self.body();remote=self.remote(body);job=self.submit(body,remote).json()
        (self.db.parent/'assets'/(self.asset['id']+'.png')).unlink();records.merge(self.db,body['engine_url'],[]);self.client.put('/api/settings',json=dict(comfy_url='http://127.0.0.1:9999'))
        with patch('backend.submissions.httpx.AsyncClient',side_effect=AssertionError('no engine')):
            self.assertEqual(self.client.post('/api/control/generate',json=body).json(),job)
            self.assertEqual(self.client.post('/api/control/generate',json=body|dict(control_strength=1)).status_code,409)
    def test_full_offline_restore_and_prompt_extraction(self):
        body=self.body();job=self.submit(body,self.remote(body)).json();job=jobs.update(self.db,job['id'],status='completed')
        stream=io.BytesIO();Image.new('RGB',(512,512),'green').save(stream,format='PNG')
        item,_=gallery.save(self.db,self.db.parent/'artworks',job,dict(node_id='7',filename='test.png',subfolder='',type='output'),stream.getvalue())
        self.assertEqual(item['parameters']['prompt'],body['prompt']);self.assertEqual(item['parameters']['negative_prompt'],job['reference_settings']['negative_prompt']);self.assertEqual(item['parameters']['seed'],body['seed'])
        records.merge(self.db,body['engine_url'],[])
        with patch('backend.submissions.httpx.AsyncClient',side_effect=AssertionError('no network')):
            for prefix in ('/api/jobs/'+job['id'],'/api/artworks/'+item['id']):
                response=self.client.get(prefix+'/creation-settings');self.assertEqual(response.status_code,200,response.text);v=response.json()
                self.assertEqual(v['settings'],job['reference_settings']);self.assertEqual(v['component_metadata'],job['component_metadata']);self.assertTrue(any('ControlNet' in w for w in v['warnings']))
        for part in ('graph','control','component','resize_version','canny_version'):
            altered=copy.deepcopy(item)
            if part=='graph': altered['workflow']['15']['inputs']['strength']=2
            if part=='control': altered['reference_metadata'][0]['control_preprocessing']['high_threshold']=.9
            if part=='component': altered['component_metadata'][0]['architecture']='sd1'
            if part=='resize_version': altered['reference_metadata'][0]['generation_preprocessing']['version']=True
            if part=='canny_version': altered['reference_metadata'][0]['control_preprocessing']['version']=True
            with self.assertRaises(ValueError): flow.extract(altered,lambda d:main.ControlInput.model_validate(d).model_dump(mode='json',exclude={'revision'}))
    def test_lora_keeps_order_clip_control_conditioning_and_vae(self):
        body=self.body();name=test_lora_submissions.NAME;loras.merge(self.db,body['engine_url'],[name]);loras.update_metadata(self.db,body['engine_url'],name,dict(architecture='sdxl'));body['loras']=[dict(name=name,enabled=True,strength_model=.8,strength_clip=.7)]
        response=self.submit(body,self.remote(body));self.assertEqual(response.status_code,200,response.text);g=response.json()['workflow']
        self.assertEqual(len(g),12);self.assertEqual(g['2']['inputs']['clip'],['8',1]);self.assertEqual(g['5']['inputs']['model'],['8',0]);self.assertEqual(g['15']['inputs']['positive'],['2',0]);self.assertEqual(g['15']['inputs']['vae'],['1',2])
    def test_catalog_sync_preserves_metadata_offline_and_engine_isolation(self):
        body=self.body();remote=self.remote(body)
        with patch('backend.control_catalog.httpx.AsyncClient',return_value=remote):
            result=self.client.post('/api/controlnets/sync',json=dict(engine_url=body['engine_url']));self.assertEqual(result.status_code,200,result.text);self.assertEqual(result.json()['controlnets'][0]['version'],'1')
            remote.get.side_effect=httpx.ConnectError('offline');failed=self.client.post('/api/controlnets/sync',json=dict(engine_url=body['engine_url'])).json()
            self.assertTrue(failed['sync_error']);self.assertEqual(failed['controlnets'][0]['sha256'],'a'*64)
        self.assertEqual(records.read(self.db,'http://127.0.0.1:9000')['controlnets'],[])
        self.assertEqual(self.client.put('/api/controlnets/metadata',json=dict(engine_url='http://127.0.0.1:9000',name='canny.safetensors',version='2')).status_code,409)
        self.assertEqual(self.client.put('/api/controlnets/metadata',json=dict(engine_url=body['engine_url'],name='canny.safetensors',kind='canny',architecture='sdxl',version='3')).status_code,200)
    def test_catalog_missing_names_bad_definition_and_removed_names_keep_registration(self):
        body=self.body();records.merge(self.db,body['engine_url'],[]);v=records.read(self.db,body['engine_url'])['controlnets'][0]
        self.assertFalse(v['listed']);self.assertEqual(v['version'],'1');self.assertEqual(v['kind'],'canny')
        for payload in ({},{'ControlNetLoader':{'input':{'required':{'control_net_name':[['bad',None]]}}}}):
            with self.assertRaises(ValueError): records.names_from(payload)
