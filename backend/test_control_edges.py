import copy
import hashlib
import io
import json
import sqlite3
import unittest
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from unittest.mock import patch
from uuid import uuid4
import httpx
from PIL import Image
from backend import jobs,gallery,main,control_edges as edges,control_edge_workflows as flow,test_control_workflows as old,control_catalog


class ControlEdgeTests(unittest.TestCase):
    setUp=old.ControlTests.setUp
    tearDown=old.ControlTests.tearDown
    body=old.ControlTests.body
    remote=old.ControlTests.remote
    def submit(self,body):
        with patch('backend.submissions.httpx.AsyncClient',return_value=self.remote(body)):
            response=self.client.post('/api/control-edge/generate',json=body)
        self.assertEqual(response.status_code,200,response.text);return response.json()
    def complete(self):
        body=self.body();job=self.submit(body)
        source=dict(node_id='16',filename='canny_00001_.png',subfolder='model_atelier/'+job['id'],type='output')
        history=dict(status=dict(completed=True,status_str='success'),outputs={'7':dict(images=[dict(filename='final.png',subfolder='',type='output')]),'16':dict(images=[{k:v for k,v in source.items() if k!='node_id'}])})
        job=jobs.update(self.db,job['id'],status='completed',history=history)
        image=Image.new('RGB',(body['width'],body['height']),'black');image.putpixel((10,10),(255,255,255))
        stream=io.BytesIO();image.save(stream,format='PNG');return body,job,source,stream.getvalue()
    def validate(self,value): return main.ControlInput.model_validate(value).model_dump(mode='json',exclude={'revision'})
    def import_response(self,job,raw,status=200):
        seen=[]
        def handle(request):
            seen.append(request);self.assertEqual(request.method,'GET');self.assertEqual(request.url.path,'/view');self.assertEqual(request.url.params['subfolder'],'model_atelier/'+job['id'])
            return httpx.Response(status,content=raw)
        remote=httpx.AsyncClient(transport=httpx.MockTransport(handle))
        with patch('backend.control_edges_api.httpx.AsyncClient',return_value=remote): response=self.client.post('/api/jobs/'+job['id']+'/control-edge')
        return response,seen
    def test_new_graph_preserves_conditioning_and_old_uuid_route(self):
        body=self.body();job=self.submit(body);graph=job['workflow'];expected=old.flow.build(job['reference_settings'],job['id'])
        self.assertEqual({k:v for k,v in graph.items() if k!='16'},expected);self.assertEqual(graph['16']['inputs']['images'],['13',0]);self.assertEqual(job['workflow_id'],flow.ID)
        self.assertEqual(self.client.get('/api/jobs/'+job['id']+'/reference-image').status_code,200)
        control_catalog.merge(self.db,body['engine_url'],[])
        with patch('backend.submissions.httpx.AsyncClient',side_effect=AssertionError('no engine')):
            self.assertEqual(self.client.post('/api/control-edge/generate',json=body).json(),job)
            self.assertEqual(self.client.post('/api/control/generate',json=body).status_code,409)
        description=self.client.get('/api/control-edge/workflow').json();self.assertEqual(description['outputs'],dict(artwork='7',control_edge='16'))
    def test_edges_are_excluded_from_artworks_and_full_restore_keeps_second_output(self):
        body,job,_,raw=self.complete();sources=gallery.outputs(job);self.assertEqual([s['node_id'] for s in sources],['7'])
        item,_=gallery.save(self.db,self.db.parent/'artworks',job,sources[0],raw)
        for prefix in ('/api/jobs/'+job['id'],'/api/artworks/'+item['id']):
            result=self.client.get(prefix+'/creation-settings');self.assertEqual(result.status_code,200,result.text);self.assertEqual(result.json()['settings'],job['reference_settings']);self.assertEqual(result.json()['component_metadata'],job['component_metadata'])
        altered=copy.deepcopy(job);altered['workflow']['16']['inputs']['images']=['6',0]
        with self.assertRaises(ValueError): gallery.outputs(altered)
        altered=copy.deepcopy(job);altered['workflow']['16']['inputs']['images']=['13',False]
        with self.assertRaises(ValueError): gallery.outputs(altered)
        altered=copy.deepcopy(job);altered['workflow']['17']=copy.deepcopy(altered['workflow']['7'])
        with self.assertRaises(ValueError): gallery.outputs(altered)
    def test_explicit_import_deduplicates_and_all_saved_reads_are_offline(self):
        _,job,_,raw=self.complete();before=jobs.get(self.db,job['id'])
        with patch('backend.control_edges_api.httpx.AsyncClient',side_effect=AssertionError('GET cannot contact engine')):
            value=self.client.get('/api/jobs/'+job['id']+'/control-edge').json();self.assertEqual(value['state'],'not_saved');self.assertEqual(self.client.get('/api/jobs/'+job['id']+'/control-edge/image').status_code,404)
        response,seen=self.import_response(job,raw);self.assertEqual(response.status_code,200,response.text);value=response.json();self.assertTrue(value['imported']);self.assertEqual(value['edge_pixels'],1);self.assertEqual(value['sha256'],hashlib.sha256(raw).hexdigest());self.assertEqual(len(seen),1)
        with patch('backend.control_edges_api.httpx.AsyncClient',side_effect=AssertionError('no network')):
            self.assertFalse(self.client.post('/api/jobs/'+job['id']+'/control-edge').json()['imported']);self.assertEqual(self.client.get('/api/jobs/'+job['id']+'/control-edge/image').content,raw)
            download=self.client.get('/api/jobs/'+job['id']+'/control-edge/image?download=true');self.assertIn('attachment',download.headers['content-disposition'])
        self.assertEqual(jobs.get(self.db,job['id']),before);self.assertEqual(gallery.list_all(self.db),[])
    def test_not_confirmed_legacy_and_wrong_output_sources_do_not_contact_engine(self):
        _,job,_,_=self.complete()
        for history in ({},dict(status=dict(completed=True,status_str='success'),outputs={}),dict(status=dict(completed=True,status_str='success'),outputs={'16':dict(images=[dict(filename='../bad.png',subfolder='',type='output')])})):
            jobs.update(self.db,job['id'],history=history)
            with patch('backend.control_edges_api.httpx.AsyncClient',side_effect=AssertionError('no fetch')): self.assertEqual(self.client.post('/api/jobs/'+job['id']+'/control-edge').status_code,409)
        jobs.update(self.db,job['id'],status='unknown')
        with patch('backend.control_edges_api.httpx.AsyncClient',side_effect=AssertionError('no fetch')): self.assertEqual(self.client.post('/api/jobs/'+job['id']+'/control-edge').status_code,409)
        body=self.body();body['request_id']=str(uuid4())
        with patch('backend.submissions.httpx.AsyncClient',return_value=self.remote(body)): old_job=self.client.post('/api/control/generate',json=body).json()
        self.assertEqual(self.client.get('/api/jobs/'+old_job['id']+'/control-edge').status_code,409)
        self.assertEqual(self.client.get('/api/jobs/'+str(uuid4())+'/control-edge').status_code,404)
    def test_offline_or_missing_remote_output_never_creates_local_snapshot(self):
        _,job,_,_=self.complete();remote=httpx.AsyncClient(transport=httpx.MockTransport(lambda r:(_ for _ in ()).throw(httpx.ConnectError('offline',request=r))))
        with patch('backend.control_edges_api.httpx.AsyncClient',return_value=remote): self.assertEqual(self.client.post('/api/jobs/'+job['id']+'/control-edge').status_code,502)
        response,_=self.import_response(job,b'',404);self.assertEqual(response.status_code,404);self.assertIsNone(edges.get(self.db,job['id']));self.assertFalse((self.db.parent/'control_edges').exists())
    def test_invalid_png_color_binary_and_dimensions_are_rejected(self):
        _,job,_,_=self.complete()
        for image in (Image.new('RGB',(8,8),'black'),Image.new('RGB',(job['reference_settings']['width'],job['reference_settings']['height']),'red'),Image.new('RGB',(job['reference_settings']['width'],job['reference_settings']['height']),(128,128,128))):
            stream=io.BytesIO();image.save(stream,format='PNG');response,_=self.import_response(job,stream.getvalue());self.assertEqual(response.status_code,422,response.text)
        response,_=self.import_response(job,b'bad');self.assertEqual(response.status_code,422);self.assertIsNone(edges.get(self.db,job['id']))
    def test_missing_or_corrupted_cached_file_is_not_replaced(self):
        _,job,_,raw=self.complete();response,_=self.import_response(job,raw);self.assertEqual(response.status_code,200)
        stored=edges.get(self.db,job['id']);target=edges.path(self.db.parent,job['id']);target.write_bytes(b'x'*len(raw))
        with patch('backend.control_edges_api.httpx.AsyncClient',side_effect=AssertionError('no refetch')):
            self.assertEqual(self.client.get('/api/jobs/'+job['id']+'/control-edge').json()['state'],'unavailable');self.assertEqual(self.client.post('/api/jobs/'+job['id']+'/control-edge').status_code,409)
        self.assertEqual(edges.get(self.db,job['id']),stored);target.unlink()
        self.assertEqual(self.client.get('/api/jobs/'+job['id']+'/control-edge/image').status_code,404)
    def test_orphan_file_and_storage_failures_do_not_overwrite_or_publish(self):
        _,job,_,raw=self.complete();target=edges.path(self.db.parent,job['id'],True);target.write_bytes(b'orphan')
        response,_=self.import_response(job,raw);self.assertEqual(response.status_code,507);self.assertEqual(target.read_bytes(),b'orphan');self.assertIsNone(edges.get(self.db,job['id']))
        target.unlink()
        with patch.object(edges.os,'fsync',side_effect=OSError('disk')): response,_=self.import_response(job,raw)
        self.assertEqual(response.status_code,507);self.assertFalse(target.exists());self.assertIsNone(edges.get(self.db,job['id']))
    def test_database_failure_rolls_back_and_removes_only_owned_png(self):
        _,job,_,raw=self.complete()
        with closing(sqlite3.connect(self.db)) as db,db: db.execute("CREATE TRIGGER reject_edge BEFORE INSERT ON settings WHEN NEW.key LIKE 'control_edge:%' BEGIN SELECT RAISE(ABORT,'database failure'); END")
        response,_=self.import_response(job,raw);self.assertEqual(response.status_code,507);self.assertFalse(edges.path(self.db.parent,job['id']).exists());self.assertIsNone(edges.get(self.db,job['id']))
    def test_concurrent_save_publishes_one_immutable_png(self):
        _,job,source,raw=self.complete();anchors,_=edges.source(job,self.validate)
        def save(_): return edges.save(self.db,self.db.parent,job,anchors,source,raw)
        with ThreadPoolExecutor(max_workers=2) as executor: results=list(executor.map(save,range(2)))
        self.assertEqual(sorted(created for _,created in results),[False,True]);self.assertEqual(results[0][0],results[1][0]);self.assertEqual(edges.path(self.db.parent,job['id']).read_bytes(),raw)
    def test_stream_size_bound_and_source_anchor_corruption_are_rejected(self):
        _,job,_,raw=self.complete()
        with patch.object(edges,'MAX_BYTES',len(raw)-1): response,_=self.import_response(job,raw)
        self.assertEqual(response.status_code,422);self.assertIsNone(edges.get(self.db,job['id']))
        response,_=self.import_response(job,raw);self.assertEqual(response.status_code,200)
        item=edges.get(self.db,job['id']);item['anchor']['workflow_sha256']='changed'
        with closing(sqlite3.connect(self.db)) as db,db: db.execute('UPDATE settings SET value=? WHERE key=?',(json.dumps(item),'control_edge:'+job['id']))
        self.assertEqual(self.client.get('/api/jobs/'+job['id']+'/control-edge').status_code,409)
    def test_artwork_points_to_original_job_edge_and_preserves_missing_artwork_error(self):
        _,job,_,raw=self.complete();self.import_response(job,raw);item,_=gallery.save(self.db,self.db.parent/'artworks',job,gallery.outputs(job)[0],raw)
        value=self.client.get('/api/artworks/'+item['id']+'/control-edge');self.assertEqual(value.status_code,200,value.text);self.assertEqual(value.json()['job_id'],job['id'])
        self.assertEqual(self.client.get('/api/artworks/'+str(uuid4())+'/control-edge').status_code,404)
