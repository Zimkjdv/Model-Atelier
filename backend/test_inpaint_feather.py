import copy
import hashlib
import io
import unittest
from unittest.mock import patch
from uuid import uuid4
import httpx
from PIL import Image,ImageChops,ImageOps
from backend import assets,gallery,jobs,main,inpaint_feather_workflows as flow,test_inpaint_workflows as old


class FeatherTests(unittest.TestCase):
    setUp=old.InpaintTests.setUp
    tearDown=old.InpaintTests.tearDown
    def body(self): return old.InpaintTests.body(self)|dict(feather_radius=16)
    def remote(self,body):
        remote=old.InpaintTests.remote(self,body)
        async def post(url,**kwargs):
            if url.endswith('/upload/image'):
                name=kwargs['files']['image'][0];role={'reference.png':'source','mask.png':'mask','blend.png':'blend'}[name];value=flow.location(body['request_id'],role)
            else: value=dict(prompt_id=body['request_id'],number=0)
            return httpx.Response(200,request=httpx.Request('POST',url),json=value)
        remote.post.side_effect=post;return remote
    def submit(self,body,remote=None):
        remote=remote or self.remote(body)
        with patch('backend.submissions.httpx.AsyncClient',return_value=remote): return self.client.post('/api/inpaint-feather/generate',json=body)
    def validate(self,value): return self.host.InpaintFeatherInput.model_validate(value).model_dump(mode='json',exclude={'revision'})
    def test_three_uploads_separate_noise_and_blend_and_frozen_hashes(self):
        body=self.body();remote=self.remote(body);result=self.submit(body,remote);self.assertEqual(result.status_code,200,result.text);job=result.json()
        self.assertEqual(job['workflow_id'],flow.ID);self.assertEqual(len(job['workflow']),11);self.assertEqual(job['workflow']['4']['inputs']['mask'],['13',0]);self.assertEqual(job['workflow']['14']['inputs']['mask'],['15',0]);self.assertEqual(job['workflow']['5']['inputs']['seed'],2**64-1)
        calls=remote.post.await_args_list;self.assertEqual([c.args[0].rsplit('/',1)[-1] for c in calls],['image','image','image','prompt'])
        raw=calls[2].kwargs['files']['image'][1];prep=job['reference_metadata'][1]['blend_preprocessing'];self.assertEqual(prep['sha256'],hashlib.sha256(raw).hexdigest());self.assertEqual(prep['radius'],16)
        self.assertEqual(self.client.get('/api/jobs/'+job['id']+'/reference-blend-mask').content,raw)
        self.assertEqual(job['input_uploads'],[flow.location(job['id'],r) for r in ('source','mask','blend')])
        for identifier in body['reference_ids']: self.assertEqual(self.client.put('/api/assets/'+identifier,json=dict(title='x',archived=True)).status_code,409)
    def test_preview_is_exact_submission_input_without_engine_or_persistence(self):
        body=self.body();value={k:v for k,v in body.items() if k!='request_id'}
        with patch('backend.submissions.httpx.AsyncClient',side_effect=AssertionError('no engine')):
            response=self.client.post('/api/inpaint-feather/preview',json=value)
        self.assertEqual(response.status_code,200,response.text);self.assertEqual(response.headers['x-atelier-sha256'],hashlib.sha256(response.content).hexdigest());self.assertEqual(response.headers['cache-control'],'no-store');self.assertEqual(jobs.list_all(self.db),[]);self.assertFalse((self.db.parent/'job_inputs').exists())
        job=self.submit(body).json();self.assertEqual(self.client.get('/api/jobs/'+job['id']+'/reference-blend-mask').content,response.content)
    def test_inward_feather_zeroes_black_pixels_and_keeps_white_core(self):
        binary=Image.new('L',(128,128),0);binary.paste(255,(16,16,112,112));soft=flow.feather(binary,8)
        self.assertEqual(ImageChops.multiply(soft,ImageOps.invert(binary)).getextrema()[1],0);self.assertEqual(soft.getpixel((64,64)),255)
        self.assertTrue(sum(soft.histogram()[1:255])>0);self.assertEqual(flow.feather(binary,0).tobytes(),binary.tobytes())
        thin=Image.new('L',(64,64),0);thin.paste(255,(30,0,31,64))
        with self.assertRaises(ValueError): flow.feather(thin,64)
    def test_zero_radius_reuses_exact_binary_png(self):
        body=self.body();body['feather_radius']=0;settings=self.validate({k:v for k,v in body.items() if k!='request_id'});refs,encoded=flow.prepare(self.db,self.db.parent,settings)
        self.assertEqual(encoded['blend'],encoded['mask']);self.assertEqual(refs[1]['blend_preprocessing']['binary_sha256'],refs[1]['blend_preprocessing']['sha256'])
    def test_schema_and_legacy_routes_reject_unknown_or_invalid_radius(self):
        body=self.body()
        with patch('backend.submissions.httpx.AsyncClient',side_effect=AssertionError('no engine')):
            for change in (dict(feather_radius=True),dict(feather_radius=1.5),dict(feather_radius=-1),dict(feather_radius=65),dict(mask_asset_id=body['image_asset_id'])):
                self.assertEqual(self.client.post('/api/inpaint-feather/generate',json=body|change).status_code,422)
            self.assertEqual(self.client.post('/api/inpaint/generate',json=body).status_code,422)
        legacy={k:v for k,v in body.items() if k!='feather_radius'}
        with patch('backend.submissions.httpx.AsyncClient',return_value=old.InpaintTests.remote(self,legacy)): previous=self.client.post('/api/inpaint/generate',json=legacy).json()
        self.assertEqual(self.submit(body).status_code,409);self.assertEqual(self.client.get('/api/jobs/'+previous['id']+'/reference-blend-mask').status_code,404)
    def test_original_uuid_recovers_before_assets_or_engine_and_changed_radius_conflicts(self):
        body=self.body();job=self.submit(body).json()
        for identifier in body['reference_ids']: (self.db.parent/'assets'/(identifier+'.png')).unlink()
        self.client.put('/api/settings',json=dict(comfy_url='http://127.0.0.1:9000'))
        with patch('backend.submissions.httpx.AsyncClient',side_effect=AssertionError('no engine')):
            self.assertEqual(self.client.post('/api/inpaint-feather/generate',json=body).json(),job);self.assertEqual(self.client.post('/api/inpaint-feather/generate',json=body|dict(feather_radius=0)).status_code,409)
    def test_third_upload_error_never_posts_prompt_or_retries(self):
        body=self.body();remote=self.remote(body);original=remote.post.side_effect
        async def post(url,**kwargs):
            if kwargs.get('files',{}).get('image',('',''))[0]=='blend.png': raise httpx.ReadTimeout('uncertain blend upload')
            return await original(url,**kwargs)
        remote.post.side_effect=post;self.assertEqual(self.submit(body,remote).status_code,502);self.assertEqual(self.submit(body,remote).json()['status'],'failed');self.assertEqual(remote.post.await_count,3)
    def test_lost_prompt_response_never_replays_three_uploads(self):
        body=self.body();remote=self.remote(body);original=remote.post.side_effect
        async def post(url,**kwargs):
            if url.endswith('/prompt'): raise httpx.ReadTimeout('uncertain prompt')
            return await original(url,**kwargs)
        remote.post.side_effect=post;self.assertEqual(self.submit(body,remote).status_code,200);self.assertEqual(self.submit(body,remote).json()['status'],'unknown');self.assertEqual(remote.post.await_count,4)
    def test_exclusive_three_file_save_rolls_back_owned_files_only(self):
        identifier=str(uuid4());folder=self.db.parent;inputs=folder/'job_inputs';inputs.mkdir();last=inputs/(identifier+'.blend.png');last.write_bytes(b'original')
        with self.assertRaises(FileExistsError): flow.save_input(folder,identifier,dict(source=b's',mask=b'm',blend=b'b'))
        self.assertEqual(last.read_bytes(),b'original');self.assertEqual(list(inputs.iterdir()),[last]);last.unlink()
        with patch.object(flow.os,'fsync',side_effect=OSError('disk')):
            with self.assertRaises(OSError): flow.save_input(folder,identifier,dict(source=b's',mask=b'm',blend=b'b'))
        self.assertEqual(list(inputs.iterdir()),[])
    def test_restore_job_artwork_and_reject_modified_blend_graph_or_policy(self):
        body=self.body();job=self.submit(body).json();job=jobs.update(self.db,job['id'],status='completed');stream=io.BytesIO();Image.new('RGB',(512,512),'green').save(stream,format='PNG')
        art,_=gallery.save(self.db,self.db.parent/'artworks',job,dict(node_id='7',filename='edit.png',subfolder='',type='output'),stream.getvalue())
        with patch('backend.submissions.httpx.AsyncClient',side_effect=AssertionError('offline')):
            for prefix in ('/api/jobs/'+job['id'],'/api/artworks/'+art['id']):
                result=self.client.get(prefix+'/creation-settings');self.assertEqual(result.status_code,200,result.text);self.assertEqual(result.json()['settings'],job['reference_settings']);self.assertEqual(result.json()['reference_metadata'],job['reference_metadata'])
        for change in ('node','port','radius','binary','version','missing'):
            item=copy.deepcopy(art)
            if change=='node': item['workflow']['14']['inputs']['mask']=['13',0]
            elif change=='port': item['workflow']['15']['inputs']['channel']='alpha'
            elif change=='radius': item['reference_metadata'][1]['blend_preprocessing']['radius']=True
            elif change=='binary': item['reference_metadata'][1]['blend_preprocessing']['binary_sha256']='a'*64
            elif change=='version': item['reference_metadata'][1]['generation_preprocessing']['version']=True
            else: item['reference_metadata'][1].pop('blend_preprocessing')
            with self.assertRaises(ValueError): flow.extract(item,self.validate)
    def test_saved_blend_missing_or_changed_is_not_recomputed(self):
        job=self.submit(self.body()).json();target=flow.input_path(self.db.parent,job['id'],'blend');raw=target.read_bytes();target.write_bytes(b'x'*len(raw))
        with patch('backend.submissions.httpx.AsyncClient',side_effect=AssertionError('no engine')): self.assertEqual(self.client.get('/api/jobs/'+job['id']+'/reference-blend-mask').status_code,409)
        self.assertEqual(target.read_bytes(),b'x'*len(raw));target.unlink();self.assertEqual(self.client.get('/api/jobs/'+job['id']+'/reference-blend-mask').status_code,404)

    def test_lora_and_missing_node_preflight_preserve_original_chain(self):
        from backend import loras,test_lora_submissions
        body=self.body();name=test_lora_submissions.NAME
        loras.merge(self.db,body['engine_url'],[name]);loras.update_metadata(self.db,body['engine_url'],name,dict(architecture='sdxl'))
        body['loras']=[dict(name=name,enabled=True,strength_model=0.8,strength_clip=0.7)]
        response=self.submit(body);self.assertEqual(response.status_code,200,response.text);job=response.json();self.assertEqual(job['workflow']['4']['inputs']['vae'],['1',2]);self.assertEqual(job['workflow']['5']['inputs']['model'],['8',0]);self.assertEqual(flow.extract(dict(job,source=dict(node_id='7')),self.validate)['loras'],body['loras'])
        body=self.body();remote=self.remote(body);original=remote.get.side_effect
        async def get(url):
            if url.endswith('/LoadImageMask'): return httpx.Response(200,request=httpx.Request('GET',url),json={})
            return await original(url)
        remote.get.side_effect=get;self.assertEqual(self.submit(body,remote).status_code,422);remote.post.assert_not_awaited()
