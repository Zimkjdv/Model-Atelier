import copy
import io
import unittest
from unittest.mock import patch
from uuid import uuid4

import httpx
from PIL import Image

from backend import failures, flux_catalog, flux_workflows, gallery, jobs, main, test_api, test_flux_catalog, test_submissions

ENGINE = test_flux_catalog.ENGINE


def definitions():
    value = test_flux_catalog.definitions()
    value.update({
        'CLIPTextEncode': dict(input=dict(required=dict(clip=['CLIP'], text=['STRING'])), output=['CONDITIONING']),
        'EmptySD3LatentImage': dict(input=dict(required={key: ['INT', dict(min=16 if key != 'batch_size' else 1, max=8192)]
                                                     for key in ('width', 'height', 'batch_size')}), output=['LATENT']),
        'VAEDecode': dict(input=dict(required=dict(samples=['LATENT'], vae=['VAE'])), output=['IMAGE']),
        'SaveImage': dict(input=dict(required=dict(images=['IMAGE'], filename_prefix=['STRING'])), output=[], output_node=True),
        'KSampler': test_submissions.sampler_capabilities()['KSampler']})
    sampler = value['KSampler']
    sampler['output'] = ['LATENT']
    sampler['input']['required'].update(model=['MODEL'], positive=['CONDITIONING'], negative=['CONDITIONING'],
        latent_image=['LATENT'], seed=['INT', dict(min=0, max=2**64-1)])
    sampler['input']['required']['scheduler'][0].append('simple')
    return value


class FluxWorkflowTests(unittest.TestCase):
    setUp = test_api.ApiTests.setUp
    tearDown = test_api.ApiTests.tearDown

    def body(self):
        return flux_workflows.Input(engine_url=ENGINE, diffusion_model='flux.safetensors',
            clip_l='clip.safetensors', t5xxl='t5.safetensors', vae='ae.safetensors',
            prompt='mountain lake', seed=str(2**64-1)).model_dump() | dict(request_id=str(uuid4()))

    def remote(self, defs=None, hook=None):
        remote = test_flux_catalog.remote_for(definitions() if defs is None else defs, hook)
        remote.post.return_value = httpx.Response(200, json=dict(prompt_id=str(uuid4()), number=0), request=httpx.Request('POST', ENGINE + '/prompt'))
        return remote

    def submit(self, body, remote):
        with patch('backend.flux_workflows.httpx.AsyncClient', return_value=remote):
            return self.client.post('/api/flux/generate', json=body)

    def test_dedicated_graph_preserves_seed_and_loaders(self):
        body, remote = self.body(), self.remote()
        result = self.submit(body, remote)
        self.assertEqual(result.status_code, 200, result.text)
        job = result.json()
        self.assertEqual(job['workflow_id'], flux_workflows.WORKFLOW_ID)
        self.assertEqual(len(job['workflow']), 9)
        self.assertEqual(job['workflow']['6']['class_type'], 'EmptySD3LatentImage')
        self.assertEqual(job['workflow']['7']['inputs']['seed'], 2**64-1)
        self.assertEqual(job['workflow']['7']['inputs']['cfg'], 1)
        self.assertEqual(job['workflow']['2']['inputs']['type'], 'flux')
        self.assertEqual([item['role'] for item in job['component_metadata']], [role for role, _ in flux_workflows.ROLES])
        self.assertTrue(all(item['version'] == '未知' for item in job['component_metadata']))
        self.assertEqual(remote.post.await_count, 1)
        self.assertEqual(len(remote.get.await_args_list), 8)
        request = remote.post.call_args.kwargs['json']
        self.assertEqual(request['prompt_id'], body['request_id'])
        self.assertEqual(request['extra_data']['model_atelier_job_id'], body['request_id'])

    def test_missing_dependency_or_node_or_changed_interface_never_posts(self):
        for mutate in (
            lambda d: d['DualCLIPLoader']['input']['required'].update(clip_name2=[[]]),
            lambda d: d.pop('EmptySD3LatentImage'),
            lambda d: d['UNETLoader'].update(output=['CLIP']),
            lambda d: d['DualCLIPLoader']['input']['required'].update(type=[['sdxl']]),
            lambda d: d['KSampler']['input']['required'].update(extra=['STRING']),
            lambda d: d['EmptySD3LatentImage']['input']['required']['width'][1].update(max=256),
        ):
            defs = definitions(); mutate(defs)
            body, remote = self.body(), self.remote(defs)
            result = self.submit(body, remote)
            self.assertEqual(result.status_code, 422, result.text)
            self.assertEqual(jobs.get(self.db, body['request_id'])['status'], 'failed')
            remote.post.assert_not_awaited()

    def test_native_saveimage_old_and_new_output_interfaces(self):
        for outputs in ([], ['IMAGE']):
            defs = definitions(); defs['SaveImage']['output'] = outputs
            self.assertEqual(self.submit(self.body(), self.remote(defs)).status_code, 200)
        defs['SaveImage']['output_node'] = False
        remote = self.remote(defs)
        self.assertEqual(self.submit(self.body(), remote).status_code, 422)
        remote.post.assert_not_awaited()

    def test_invalid_fields_no_network_or_ledger(self):
        with patch('backend.flux_workflows.httpx.AsyncClient', side_effect=AssertionError('network')):
            for change in (dict(seed=2**64-1), dict(seed=str(2**64)), dict(width=520), dict(steps=5),
                           dict(cfg=7), dict(negative_prompt='ignored'), dict(loras=[]), dict(reference_ids=[]),
                           dict(encoder_device='cuda'), dict(weight_dtype='fp8_e4m3fn_fast'),
                           dict(t5xxl='clip.safetensors'), dict(width=True)):
                self.assertEqual(self.client.post('/api/flux/generate', json=self.body() | change).status_code, 422)
        self.assertEqual(jobs.list_all(self.db), [])

    def test_offline_is_failed_before_dispatch_and_recovery_is_query_only(self):
        body, remote = self.body(), self.remote()
        remote.get.side_effect = httpx.ConnectError('offline')
        result = self.submit(body, remote)
        self.assertEqual(result.status_code, 503)
        self.assertEqual(result.json()['detail']['failure_info']['code'], 'engine_offline')
        remote.post.assert_not_awaited()
        with patch('backend.flux_workflows.httpx.AsyncClient', side_effect=AssertionError('no re-probe')):
            self.assertEqual(self.client.post('/api/flux/generate', json=body).json()['status'], 'failed')

    def test_lost_receipt_and_engine_change_keep_original_request(self):
        body, remote = self.body(), self.remote()
        remote.post.side_effect = httpx.ReadTimeout('lost reply')
        job = self.submit(body, remote).json()
        self.assertEqual(job['status'], 'unknown')
        self.client.put('/api/settings', json=dict(comfy_url='http://127.0.0.1:9000'))
        with patch('backend.flux_workflows.httpx.AsyncClient', side_effect=AssertionError('no network')):
            recovered = self.client.post('/api/flux/generate', json=body)
            self.assertEqual(recovered.json()['id'], job['id'])
            self.assertEqual(self.client.post('/api/flux/generate', json=body | dict(prompt='different')).status_code, 409)
        self.assertEqual(remote.post.await_count, 1)

    def test_late_engine_or_architecture_change_blocks_without_rewriting_snapshot(self):
        for change in ('engine', 'architecture'):
            self.client.put('/api/settings', json=dict(comfy_url=ENGINE))
            listed = dict(diffusion_models=['flux.safetensors'], text_encoders=['clip.safetensors','t5.safetensors'], vae=['ae.safetensors'])
            flux_catalog.merge(self.db, ENGINE, listed)
            flux_catalog.update_metadata(self.db, ENGINE, 'diffusion_models', 'flux.safetensors', dict(architecture='flux', version='old'))
            def hook(_):
                if change == 'engine':
                    self.client.put('/api/settings', json=dict(comfy_url='http://127.0.0.1:9000'))
                else:
                    flux_catalog.update_metadata(self.db, ENGINE, 'diffusion_models', 'flux.safetensors', dict(architecture='sdxl', version='new'))
            body, remote = self.body(), self.remote(hook=hook)
            result = self.submit(body, remote)
            self.assertEqual(result.status_code, 409 if change == 'engine' else 422, result.text)
            remote.post.assert_not_awaited()
            self.assertEqual(jobs.get(self.db, body['request_id'])['component_metadata'][0]['version'], 'old')

    def test_rejection_saved_and_immutable_snapshots_reach_artwork(self):
        body, remote = self.body(), self.remote()
        remote.post.return_value = httpx.Response(400, json=dict(node_errors={'1': {'errors':['bad weights']}}), request=httpx.Request('POST', ENGINE + '/prompt'))
        self.assertEqual(self.submit(body, remote).status_code, 422)
        job = jobs.get(self.db, body['request_id'])
        self.assertIn('node_errors', job['upstream_error'])
        for field in ('component_metadata','workflow_id'):
            with self.assertRaises(ValueError):
                jobs.update(self.db, job['id'], **{field: None})
        image = io.BytesIO(); Image.new('RGB', (8,8)).save(image, format='PNG')
        item, _ = gallery.save(self.db, main.DATA/'artworks', job, dict(filename='landscape.png', subfolder='', type='output', node_id='9'), image.getvalue())
        self.assertEqual(item['component_metadata'], job['component_metadata'])
        self.assertEqual(item['workflow_id'], job['workflow_id'])

    def test_restore_only_whole_terminal_workflow_and_read_only_preview(self):
        body = self.body()
        remote = self.remote(); remote.get.side_effect = httpx.ConnectError('offline')
        self.submit(body, remote)
        with patch('backend.flux_workflows.httpx.AsyncClient', side_effect=AssertionError('no network')):
            result = self.client.get('/api/flux/jobs/' + body['request_id'] + '/creation-settings')
            self.assertEqual(result.status_code, 200, result.text)
            self.assertEqual(result.json()['settings']['seed'], body['seed'])
            preview = self.client.post('/api/flux/workflow', json={k:v for k,v in body.items() if k != 'request_id'})
            self.assertEqual(preview.json()['workflow'], jobs.get(self.db, body['request_id'])['workflow'])
        self.assertEqual(len(jobs.list_all(self.db)), 1)
        modified = jobs.get(self.db, body['request_id'])
        modified['workflow']['7']['inputs']['cfg'] = 7
        with self.assertRaises(ValueError):
            flux_workflows.extract(modified)
        jobs.update(self.db, body['request_id'], status='unknown')
        self.assertEqual(self.client.get('/api/flux/jobs/' + body['request_id'] + '/creation-settings').status_code, 409)

    def test_drafts_are_separate_offline_and_revision_protected(self):
        body = self.body(); body.pop('request_id')
        with patch('backend.flux_workflows.httpx.AsyncClient', side_effect=AssertionError('no network')):
            result = self.client.post('/api/flux/drafts', json=body)
            self.assertEqual(result.status_code, 200, result.text)
            draft = result.json()
            self.assertEqual(self.client.get('/api/drafts').json(), [])
            self.assertEqual(self.client.get('/api/flux/drafts').json()[0]['seed'], body['seed'])
            path = '/api/flux/drafts/' + draft['id']
            self.assertEqual(self.client.put(path, json=body | dict(revision=1)).json()['revision'], 2)
            self.assertEqual(self.client.put(path, json=body | dict(revision=1)).status_code, 409)
        self.assertEqual(jobs.list_all(self.db), [])

    def test_flux_failure_nodes_are_trusted_by_history_identity(self):
        body = self.body(); graph = flux_workflows.build(body)
        job = dict(id=body['request_id'], prompt_id=body['request_id'], workflow=graph)
        data = dict(prompt_id=job['id'], node_id='2', node_type='DualCLIPLoader', exception_type='ValueError')
        entry = dict(status=dict(status_str='error', messages=[['execution_error', data]]))
        self.assertEqual(failures.from_history(job, entry)['code'], 'model_load_failed')
        data['exception_type'] = 'torch.cuda.OutOfMemoryError'
        self.assertEqual(failures.from_history(job, entry)['code'], 'cuda_oom')
