import copy
import hashlib
import io
import unittest
from unittest.mock import patch
from uuid import uuid4

import httpx
from PIL import Image
from backend import assets, catalog, gallery, inpaint_workflows as flow, jobs, main, test_api, test_image_workflows, test_lora_submissions, loras


def definitions():
    return {
        'LoadImage': dict(input=dict(required=dict(image=[[]])),output=['IMAGE','MASK']),
        'LoadImageMask': dict(input=dict(required=dict(image=[[]],channel=[['alpha','red','green','blue']])),output=['MASK']),
        'VAEEncodeForInpaint': dict(input=dict(required=dict(pixels=['IMAGE'],vae=['VAE'],mask=['MASK'],grow_mask_by=['INT',dict(min=0,max=64)])),output=['LATENT']),
        'ImageCompositeMasked': dict(input=dict(required=dict(destination=['IMAGE'],source=['IMAGE'],x=['INT',dict(min=0,max=8192)],y=['INT',dict(min=0,max=8192)],resize_source=['BOOLEAN']),optional=dict(mask=['MASK'])),output=['IMAGE'])}


class InpaintTests(unittest.TestCase):
    setUp=test_api.ApiTests.setUp
    tearDown=test_api.ApiTests.tearDown

    def body(self, size=(80,64), color=0):
        body=test_image_workflows.ImageWorkflowTests.body(self)
        image=Image.new('L',size,color)
        image.paste(255,(size[0]//2,0,size[0],size[1]))
        stream=io.BytesIO();image.save(stream,format='PNG')
        self.mask=assets.create(self.db,self.db.parent/'assets',stream.getvalue(),'mask.png')
        return body|dict(mask_asset_id=self.mask['id'],reference_ids=[self.asset['id'],self.mask['id']],grow_mask_by=6)

    def remote(self,body,change=None):
        remote=test_image_workflows.ImageWorkflowTests.remote(self,body)
        original=remote.get.side_effect
        async def get(url):
            name=url.rsplit('/',1)[-1]
            if name in definitions():
                value=definitions()[name]
                if change: value=change(name,value)
                return httpx.Response(200,request=httpx.Request('GET',url),json={} if value is None else {name:value})
            return await original(url)
        async def post(url,**kwargs):
            value=flow.location(body['request_id'],'mask' if kwargs.get('files',{}).get('image',('',''))[0]=='mask.png' else 'source') if url.endswith('/upload/image') else dict(prompt_id=body['request_id'],number=0)
            return httpx.Response(200,request=httpx.Request('POST',url),json=value)
        remote.get.side_effect=get;remote.post.side_effect=post
        return remote

    def submit(self,body,remote):
        with patch('backend.submissions.httpx.AsyncClient',return_value=remote):
            return self.client.post('/api/inpaint/generate',json=body)

    def test_two_owned_uploads_exact_graph_and_frozen_assets(self):
        body=self.body();remote=self.remote(body);result=self.submit(body,remote)
        self.assertEqual(result.status_code,200,result.text);job=result.json();graph=job['workflow']
        self.assertEqual(len(graph),10);self.assertEqual(graph['4']['class_type'],'VAEEncodeForInpaint')
        self.assertEqual(graph['13']['inputs']['channel'],'red');self.assertEqual(graph['14']['inputs']['destination'],['12',0])
        self.assertEqual(graph['7']['inputs']['images'],['14',0]);self.assertEqual(graph['5']['inputs']['seed'],2**64-1)
        self.assertEqual([c.args[0].rsplit('/',1)[-1] for c in remote.post.await_args_list],['image','image','prompt'])
        self.assertEqual([r['input_role'] for r in job['reference_metadata']],['source','mask'])
        for i,suffix in enumerate(('reference-image','reference-mask')):
            upload=remote.post.await_args_list[i].kwargs;encoded=upload['files']['image'][1]
            self.assertEqual(upload['data']['overwrite'],'false')
            prep=job['reference_metadata'][i]['generation_preprocessing']
            self.assertEqual(prep['sha256'],hashlib.sha256(encoded).hexdigest())
            self.assertEqual(self.client.get('/api/jobs/'+job['id']+'/'+suffix).content,encoded)
            self.assertEqual(self.client.put('/api/assets/'+body['reference_ids'][i],json=dict(title='x',archived=True)).status_code,409)
        with Image.open(io.BytesIO(remote.post.await_args_list[1].kwargs['files']['image'][1])) as mask:
            self.assertEqual(mask.getpixel((0,0)),(0,0,0));self.assertEqual(mask.getpixel((400,256)),(255,255,255))
            self.assertEqual(set(mask.getdata()),{(0,0,0),(255,255,255)})
        self.assertEqual(job['input_uploads'],[flow.location(body['request_id']),flow.location(body['request_id'],'mask')])

    def test_strict_schema_and_unavailable_assets_never_call_engine(self):
        body=self.body()
        changes=[dict(reference_ids=[]),dict(reference_ids=list(reversed(body['reference_ids']))),dict(mask_asset_id=body['image_asset_id']),dict(grow_mask_by=True),dict(grow_mask_by=65),dict(workflow_mode='text2image'),dict(width=8192,height=8192),dict(experiment={})]
        with patch('backend.submissions.httpx.AsyncClient',side_effect=AssertionError('no engine')):
            for change in changes: self.assertEqual(self.client.post('/api/inpaint/generate',json=body|change).status_code,422,change)
            self.assertEqual(self.client.post('/api/generate',json=body).status_code,422)
            (self.db.parent/'assets'/(self.mask['id']+'.png')).write_bytes(b'changed')
            self.assertEqual(self.client.post('/api/inpaint/generate',json=body).status_code,422)
        self.assertEqual(jobs.list_all(self.db),[])

    def test_wrong_geometry_and_empty_mask_rejected(self):
        body=self.body(size=(64,64));remote=self.remote(body)
        self.assertEqual(self.submit(body,remote).status_code,422);remote.post.assert_not_awaited()
        body=self.body();stream=io.BytesIO();Image.new('RGB',(80,64),'black').save(stream,format='PNG')
        black=assets.create(self.db,self.db.parent/'assets',stream.getvalue(),'black.png')
        body.update(mask_asset_id=black['id'],reference_ids=[self.asset['id'],black['id']])
        self.assertEqual(self.submit(body,self.remote(body)).status_code,422)
        self.assertEqual(jobs.list_all(self.db),[])

    def test_missing_nodes_malformed_interface_and_narrow_range_no_upload(self):
        for problem in ('missing','none','list','channel','range'):
            body=self.body()
            def change(name,value):
                if name=='LoadImageMask' and problem=='missing': return None
                if name=='VAEEncodeForInpaint':
                    if problem=='none': value['input']['required']=None
                    if problem=='list': value['input']['required']=[]
                    if problem=='range': value['input']['required']['grow_mask_by'][1]['max']=5
                if name=='LoadImageMask' and problem=='channel': value['input']['required']['channel']=[['alpha']]
                return value
            remote=self.remote(body,change);response=self.submit(body,remote)
            self.assertEqual(response.status_code,422,(problem,response.text));remote.post.assert_not_awaited()
            self.assertEqual(jobs.get(self.db,body['request_id'])['status'],'failed')

    def test_offline_or_missing_checkpoint_or_unknown_architecture_no_upload(self):
        for problem in ('offline','checkpoint','architecture'):
            body=self.body();remote=self.remote(body);original=remote.get.side_effect
            async def get(url):
                if problem=='offline': raise httpx.ConnectError('offline')
                if problem=='checkpoint' and url.endswith('/CheckpointLoaderSimple'):
                    return httpx.Response(200,request=httpx.Request('GET',url),json={'CheckpointLoaderSimple':{'input':{'required':{'ckpt_name':[[]]}}}})
                return await original(url)
            remote.get.side_effect=get
            if problem=='architecture': catalog.update_metadata(self.db,body['engine_url'],body['checkpoint'],dict(architecture='unknown'))
            self.assertGreaterEqual(self.submit(body,remote).status_code,400);remote.post.assert_not_awaited()

    def test_recovery_before_files_engine_and_mask_changes_conflict(self):
        body=self.body();remote=self.remote(body);first=self.submit(body,remote).json()
        for asset_id in body['reference_ids']: (self.db.parent/'assets'/(asset_id+'.png')).unlink()
        self.client.put('/api/settings',json=dict(comfy_url='http://127.0.0.1:9000'))
        with patch('backend.submissions.httpx.AsyncClient',side_effect=AssertionError('no engine')):
            self.assertEqual(self.client.post('/api/inpaint/generate',json=body).json(),first)
            for change in (dict(grow_mask_by=0),dict(prompt='changed'),dict(denoise=1)):
                self.assertEqual(self.client.post('/api/inpaint/generate',json=body|change).status_code,409)
        self.assertEqual(remote.post.await_count,3)

    def test_second_upload_failure_never_posts_prompt_or_retries(self):
        for timeout in (False,True):
            body=self.body();remote=self.remote(body);original=remote.post.side_effect
            async def post(url,**kwargs):
                if kwargs.get('files',{}).get('image',('',''))[0]=='mask.png':
                    if timeout: raise httpx.ReadTimeout('uncertain mask upload')
                    return httpx.Response(200,request=httpx.Request('POST',url),json=dict(name='mask.png',subfolder='../wrong',type='input'))
                return await original(url,**kwargs)
            remote.post.side_effect=post
            self.assertEqual(self.submit(body,remote).status_code,502)
            self.assertEqual(self.submit(body,remote).json()['status'],'failed');self.assertEqual(remote.post.await_count,2)

    def test_engine_change_after_source_upload_stops_before_mask(self):
        body=self.body();remote=self.remote(body);original=remote.post.side_effect
        async def post(url,**kwargs):
            value=await original(url,**kwargs)
            self.client.put('/api/settings',json=dict(comfy_url='http://127.0.0.1:9000'))
            return value
        remote.post.side_effect=post
        self.assertEqual(self.submit(body,remote).status_code,409);self.assertEqual(remote.post.await_count,1)

    def test_lost_prompt_response_is_unknown_and_never_resubmitted(self):
        body=self.body();remote=self.remote(body);original=remote.post.side_effect
        async def post(url,**kwargs):
            if url.endswith('/prompt'): raise httpx.ReadTimeout('unknown')
            return await original(url,**kwargs)
        remote.post.side_effect=post
        self.assertEqual(self.submit(body,remote).json()['status'],'unknown')
        self.assertEqual(self.submit(body,remote).json()['status'],'unknown');self.assertEqual(remote.post.await_count,3)

    def test_atomic_reservation_checks_both_assets(self):
        body=self.body();settings=main.InpaintInput.model_validate({k:v for k,v in body.items() if k!='request_id'}).model_dump(mode='json',exclude={'revision'})
        snapshots,_=flow.prepare(self.db,self.db.parent,settings)
        assets.update(self.db,self.mask['id'],'mask',True)
        with self.assertRaises(ValueError): jobs.reserve(self.db,body['request_id'],body['engine_url'],flow.build(settings,body['request_id']),body['checkpoint'],workflow_id=flow.ID,reference_metadata=snapshots,reference_settings=settings)
        self.assertEqual(jobs.list_all(self.db),[])

    def test_terminal_job_and_artwork_restore_offline_with_composite_parameters(self):
        body=self.body();job=self.submit(body,self.remote(body)).json();job=jobs.update(self.db,job['id'],status='completed')
        stream=io.BytesIO();Image.new('RGB',(512,512),'green').save(stream,format='PNG')
        item,_=gallery.save(self.db,self.db.parent/'artworks',job,dict(node_id='7',filename='edit.png',subfolder='',type='output'),stream.getvalue())
        self.assertEqual(item['parameters']['seed'],body['seed']);self.assertEqual(item['parameters']['prompt'],body['prompt'])
        with patch('backend.submissions.httpx.AsyncClient',side_effect=AssertionError('offline')):
            for prefix in ('/api/jobs/'+job['id'],'/api/artworks/'+item['id']):
                restored=self.client.get(prefix+'/creation-settings');self.assertEqual(restored.status_code,200,restored.text)
                self.assertEqual(restored.json()['settings'],job['reference_settings']);self.assertEqual(restored.json()['reference_metadata'],job['reference_metadata'])
        for target in ('graph','mask_policy','role'):
            changed=copy.deepcopy(item)
            if target=='graph': changed['workflow']['14']['inputs']['mask']=['12',1]
            if target=='mask_policy': changed['reference_metadata'][1]['generation_preprocessing']['white']='preserve'
            if target=='role': changed['reference_metadata'][1]['input_role']='source'
            with self.assertRaises(ValueError): flow.extract(changed,lambda s:main.InpaintInput.model_validate(s).model_dump(mode='json',exclude={'revision'}))

    def test_lora_preserves_clip_vae_and_exact_restore(self):
        body=self.body();name=test_lora_submissions.NAME
        loras.merge(self.db,body['engine_url'],[name]);loras.update_metadata(self.db,body['engine_url'],name,dict(architecture='sdxl'))
        body['loras']=[dict(name=name,enabled=True,strength_model=0.8,strength_clip=0.7)]
        result=self.submit(body,self.remote(body));self.assertEqual(result.status_code,200,result.text);job=result.json();graph=job['workflow']
        self.assertEqual(graph['5']['inputs']['model'],['8',0]);self.assertEqual(graph['2']['inputs']['clip'],['8',1]);self.assertEqual(graph['4']['inputs']['vae'],['1',2])
        self.assertEqual(flow.extract(dict(job,source=dict(node_id='7')),lambda s:main.InpaintInput.model_validate(s).model_dump(mode='json',exclude={'revision'}))['loras'],body['loras'])

    def test_exclusive_files_never_overwrite_and_cleanup_partial_write(self):
        job_id=str(uuid4());folder=self.db.parent;inputs=folder/'job_inputs';inputs.mkdir()
        mask=inputs/(job_id+'.mask.png');mask.write_bytes(b'original')
        with self.assertRaises(FileExistsError): flow.save_input(folder,job_id,dict(source=b'source',mask=b'mask'))
        self.assertEqual(mask.read_bytes(),b'original');self.assertFalse((inputs/(job_id+'.png')).exists())

    def test_transparency_and_threshold_are_explicit(self):
        body=self.body();image=Image.new('RGBA',(80,64),(0,0,0,255))
        image.paste((127,127,127,255),(0,0,20,64));image.paste((128,128,128,255),(20,0,40,64));image.paste((0,0,0,0),(60,0,80,64))
        stream=io.BytesIO();image.save(stream,format='PNG');mask=assets.create(self.db,self.db.parent/'assets',stream.getvalue(),'alpha.png')
        body.update(mask_asset_id=mask['id'],reference_ids=[self.asset['id'],mask['id']],reference_resize='stretch')
        settings=main.InpaintInput.model_validate({k:v for k,v in body.items() if k!='request_id'}).model_dump(mode='json')
        _,encoded=flow.prepare(self.db,self.db.parent,settings)
        with Image.open(io.BytesIO(encoded['mask'])) as result:
            self.assertEqual([result.getpixel((x,256))[0] for x in (32,160,288,448)],[0,255,0,255])
