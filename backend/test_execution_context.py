import copy
import unittest
from backend import execution_context as context,runtime_metadata,test_runtime_metadata as old


class ContextTests(unittest.TestCase):
    def job(self):
        return dict(engine_url='http://127.0.0.1:8188',checkpoint='model',model_version='v1',
            workflow={'4':dict(class_type='EmptyLatentImage',inputs=dict(width=768,height=512,batch_size=1)),
                      '5':dict(class_type='KSampler',inputs=dict(steps=20,cfg=5.5,denoise=1.,seed=2**64-1,sampler_name='euler',scheduler='normal',private='secret'))},
            lora_metadata=[dict(name='a',version='1',strength_model=.5),dict(name='b',version='2',strength_model=.8)])
    def test_frozen_geometry_ordered_models_and_exact_seed(self):
        job=self.job();before=copy.deepcopy(job);result=context.capture(job,None,'checkpoint-text2image-v1')
        self.assertEqual(result['geometry']['batch_size'],1);self.assertEqual(result['geometry']['width'],768)
        self.assertEqual(result['parameters'][0]['settings']['seed'],str(2**64-1));self.assertNotIn('private',result['parameters'][0]['settings'])
        self.assertEqual([m['name'] for m in result['loras']],['a','b']);result['loras'].reverse();self.assertEqual(job,before)
    def test_only_allowlisted_flags_never_tokens_paths_or_requested_dtype_as_actual(self):
        stats=dict(system=dict(argv=['main.py','--lowvram','--fp16-unet','--cpu-vae','--api-key','private-token','C:/private/model','--async-offload','2','--fp32-unet']))
        result=context.capture(self.job(),stats,'checkpoint-text2image-v1');policy=result['launch_policy']
        self.assertEqual(policy['precision_flags'],['--fp16-unet','--fp32-unet']);self.assertEqual(policy['memory_flags'],['--async-offload','--cpu-vae','--lowvram'])
        self.assertNotIn('private',str(result));self.assertIsNone(result['actual_precision']);self.assertIsNone(result['actual_offload']);self.assertEqual(result['cache_state'],'unknown')
    def test_missing_invalid_or_empty_argv_preserve_unknown_policy(self):
        for argv in (None,'--lowvram',[True],['x']*257):
            result=context.capture(self.job(),dict(system=dict(argv=argv)),'test')['launch_policy']
            self.assertFalse(result['reported']);self.assertEqual(result['memory_flags'],[])
        result=context.capture(self.job(),dict(system=dict(argv=[])),'test')['launch_policy'];self.assertTrue(result['reported']);self.assertEqual(result['memory_flags'],[])
    def test_reference_dimensions_and_components_without_implicit_gpu_or_cache(self):
        job=self.job()|dict(reference_settings=dict(width=1024,height=768),component_metadata=[dict(role='controlnet',name='canny',version='v1',architecture='sdxl')])
        result=context.capture(job,None,'checkpoint-canny-controlnet-edge-v2')
        self.assertEqual(result['geometry'],dict(width=1024,height=768,batch_size=1,source='frozen reference settings'))
        self.assertEqual(result['models'][1]['role'],'controlnet');self.assertIsNone(result['models'][1]['sha256'])
    def test_unknown_graph_and_invalid_dimensions_do_not_invent_workload_values(self):
        job=self.job();job['workflow']['4']['inputs']['batch_size']=True
        result=context.capture(job,None,'unknown');self.assertIsNone(result['geometry']['batch_size'])
        self.assertEqual(result['workload'],'inference')


class ContextApiTests(unittest.TestCase):
    setUp=old.RuntimeMetadataTests.setUp
    tearDown=old.RuntimeMetadataTests.tearDown
    payload=old.RuntimeMetadataTests.payload
    remote=old.RuntimeMetadataTests.remote
    engine=old.RuntimeMetadataTests.engine
    submit=old.RuntimeMetadataTests.submit
    def test_api_freezes_context_and_original_uuid_never_refreshes_launch_flags(self):
        from unittest.mock import patch
        stats=copy.deepcopy(old.STATS);stats['system']['argv']=['main.py','--lowvram','--fp16-unet']
        body=self.payload();job=self.submit(body,self.engine(stats)).json();context=job['runtime_metadata']['execution_context']
        self.assertEqual(context['launch_policy']['memory_flags'],['--lowvram'])
        with patch('backend.submissions.httpx.AsyncClient',side_effect=AssertionError('no engine')):
            self.assertEqual(self.client.post('/api/generate',json=body).json()['runtime_metadata']['execution_context'],context)
