import copy
import unittest
from unittest.mock import AsyncMock, patch
from uuid import uuid4

from backend import catalog, environment, jobs, loras, main, workflows
from backend import test_api, test_lora_submissions as single, test_lora_records as records

ENGINE = single.ENGINE
NAMES = [single.NAME, 'styles/color.safetensors', 'styles/line.safetensors', 'styles/detail.safetensors']


class MultiLoraTests(unittest.TestCase):
    setUp = test_api.ApiTests.setUp
    tearDown = test_api.ApiTests.tearDown
    remote = single.LoraSubmissionTests.remote
    submit = single.LoraSubmissionTests.submit
    artwork = records.LoraRecordTests.artwork

    def body(self, count=2):
        value = single.LoraSubmissionTests.body(self)
        value['loras'] = [dict(name=name, enabled=True, strength_model=0.75 - index / 4, strength_clip=-index / 8)
                          for index, name in enumerate(NAMES[:count])]
        return value

    def prepare(self):
        catalog.merge(self.db, ENGINE, ['test.safetensors'])
        catalog.update_metadata(self.db, ENGINE, 'test.safetensors', dict(architecture='sdxl'))
        loras.merge(self.db, ENGINE, NAMES)
        for index, name in enumerate(NAMES):
            loras.update_metadata(self.db, ENGINE, name, dict(architecture='sdxl', version=f'v{index}', sha256=str(index + 1)*64))

    def engine(self, names=NAMES, hook=None):
        return self.remote(single.loader_definition(names), hook=hook)

    def settings(self, graph):
        return workflows.extract(dict(workflow=graph, checkpoint='test.safetensors', engine_url=ENGINE,
            title='multi', source=dict(node_id='7')), lambda v: main.DraftInput.model_validate(v).model_dump())

    def test_ordered_chain_routes_both_clip_paths_and_vae_without_precision_loss(self):
        self.prepare()
        for count in (2, 3, 4):
            body, remote = self.body(count), self.engine()
            result = self.submit(body, remote)
            self.assertEqual(result.status_code, 200, result.text)
            graph = result.json()['workflow']
            self.assertEqual(len(graph), 7 + count)
            for index, choice in enumerate(body['loras']):
                previous = '1' if index == 0 else str(7 + index)
                node = graph[str(8 + index)]['inputs']
                self.assertEqual(node['model'], [previous, 0])
                self.assertEqual(node['clip'], [previous, 1])
                self.assertEqual(node['lora_name'], choice['name'])
            end = str(7 + count)
            self.assertEqual(graph['5']['inputs']['model'], [end, 0])
            self.assertEqual(graph['2']['inputs']['clip'], [end, 1])
            self.assertEqual(graph['3']['inputs']['clip'], [end, 1])
            self.assertEqual(graph['6']['inputs']['vae'], ['1', 2])
            self.assertEqual(graph['5']['inputs']['seed'], 2**64-1)
            self.assertEqual(self.settings(graph)['loras'], body['loras'])
            self.assertEqual(sum(call.args[0].endswith('/object_info/LoraLoader') for call in remote.get.await_args_list), 1)

    def test_chain_order_is_not_json_order_and_disabled_choices_are_not_executed(self):
        body = self.body(4)
        body['loras'][1]['enabled'] = False
        graph = workflows.build(main.DraftInput.model_validate(body).model_dump())
        graph = dict(reversed(list(graph.items())))
        self.assertEqual(self.settings(graph)['loras'], [c for c in body['loras'] if c['enabled']])
        ids = dict(zip(workflows.ROLES, ['a', 'b', 'c', 'd', 'e', 'f', '7'])) | dict(lora='first', lora_2='second', lora_3='third')
        graph = workflows.build(main.DraftInput.model_validate(body).model_dump(), ids)
        self.assertEqual(self.settings(graph)['loras'], [c for c in body['loras'] if c['enabled']])

    def test_duplicate_or_excessive_choices_reject_without_network(self):
        body = self.body(4)
        with patch('backend.submissions.httpx.AsyncClient', side_effect=AssertionError('no network')):
            for choices in (body['loras'] + [dict(body['loras'][0], name='fifth')],
                            [body['loras'][0], dict(body['loras'][0], enabled=False)]):
                response = self.client.post('/api/generate', json=body | dict(loras=choices))
                self.assertEqual(response.status_code, 422)
        self.assertEqual(jobs.list_all(self.db), [])

    def test_second_lora_missing_or_incompatible_prevents_submission(self):
        self.prepare()
        remote = self.engine(NAMES[:1])
        self.assertEqual(self.submit(self.body(), remote).status_code, 409)
        remote.post.assert_not_awaited()
        loras.update_metadata(self.db, ENGINE, NAMES[1], dict(architecture='flux'))
        remote = self.engine()
        self.assertEqual(self.submit(self.body(), remote).status_code, 422)
        remote.get.assert_not_awaited()
        remote.post.assert_not_awaited()

    def test_late_second_lora_architecture_change_rejects_and_preserves_snapshot(self):
        self.prepare()
        def change(url):
            if url.endswith('/object_info/LoraLoader'):
                loras.update_metadata(self.db, ENGINE, NAMES[1], dict(architecture='sd1', version='new'))
        remote = self.engine(hook=change)
        result = self.submit(self.body(), remote)
        self.assertEqual(result.status_code, 422)
        remote.post.assert_not_awaited()
        item = jobs.get(self.db, result.json()['detail']['job_id'])
        self.assertEqual(item['lora_metadata'][1]['version'], 'v1')
        self.assertEqual(item['lora_metadata'][1]['architecture'], 'sdxl')

    def test_broken_branch_cycle_or_partial_clip_chain_rejects_raw_workflow(self):
        self.prepare()
        graph = workflows.build(main.DraftInput.model_validate(self.body()).model_dump())
        variants = []
        for node, field, link in [('8', 'model', ['9', 0]), ('9', 'clip', ['1', 1]), ('2', 'clip', ['8', 1])]:
            variant = copy.deepcopy(graph)
            variant[node]['inputs'][field] = link
            variants.append(variant)
        extra = copy.deepcopy(graph)
        extra['10'] = copy.deepcopy(extra['8'])
        variants.append(extra)
        remote = self.engine()
        with patch('backend.submissions.httpx.AsyncClient', return_value=remote):
            for value in variants:
                response = self.client.post('/api/jobs', json=dict(request_id=str(uuid4()), engine_url=ENGINE,
                    checkpoint='test.safetensors', workflow=value))
                self.assertEqual(response.status_code, 422)
        remote.post.assert_not_awaited()

    def test_artwork_restore_snapshots_and_request_recovery_preserve_order(self):
        self.prepare()
        body = self.body(3)
        body['loras'].reverse()
        result = self.submit(body, self.engine())
        self.assertEqual(result.status_code, 200, result.text)
        item = result.json()
        self.assertEqual([v['name'] for v in item['lora_metadata']], [v['name'] for v in body['loras']])
        artwork = self.artwork(item)
        loras.update_metadata(self.db, ENGINE, NAMES[1], dict(version='edited'))
        restored = self.client.get('/api/artworks/' + artwork['id'] + '/creation-settings').json()
        self.assertEqual(restored['settings']['loras'], body['loras'])
        self.assertEqual(restored['lora_metadata'], item['lora_metadata'])
        with patch('backend.submissions.httpx.AsyncClient', side_effect=AssertionError('no replay')):
            self.assertEqual(self.client.post('/api/generate', json=body).json()['lora_metadata'], item['lora_metadata'])
        jobs.update(self.db, item['id'], status='failed')
        restored = self.client.get('/api/jobs/' + item['id'] + '/creation-settings').json()
        self.assertEqual(restored['settings']['loras'], body['loras'])

    def test_draft_preserves_disabled_entries_order_and_strengths(self):
        body = self.body(4)
        body['loras'][0]['enabled'] = False
        body['loras'].reverse()
        result = self.client.post('/api/drafts', json=body)
        self.assertEqual(result.status_code, 201, result.text)
        self.assertEqual(self.client.get('/api/drafts').json()[0]['loras'], body['loras'])

    def test_multi_advice_does_not_reuse_single_or_base_evidence(self):
        self.prepare()
        body = self.body()
        fields = dict(width=512, height=512, steps=4, cfg=1, sampler_name='lcm', scheduler='sgm_uniform', denoise=1)
        with patch.object(main, 'engine', AsyncMock(return_value=dict(url=ENGINE, diagnostics=environment.engine_diagnostics(status='offline')))):
            result = self.client.post('/api/generation-advice', json=fields | dict(engine_url=ENGINE, checkpoint=body['checkpoint'], loras=body['loras']))
        self.assertEqual(result.status_code, 200, result.text)
        self.assertEqual(result.json()['validation_status'], 'unverified')
        self.assertEqual(result.json()['matching_parameter_records'], [])
        self.assertTrue(any('多 LoRA' in v for v in result.json()['warnings']))
