import copy
import io
import unittest
from unittest.mock import patch
from uuid import uuid4
import httpx
from PIL import Image
from backend import (
    test_control_workflows as old,
    control_catalog,
    structure_workflows as flow,
    jobs,
    gallery,
)


class StructureTests(unittest.TestCase):
    setUp = old.ControlTests.setUp
    tearDown = old.ControlTests.tearDown

    def body(self, kind='pose'):
        body = old.ControlTests.body(self)
        body.pop('canny_low')
        body.pop('canny_high')
        body['control_kind'] = kind
        control_catalog.update_metadata(
            self.db, body['engine_url'], body['control_net_name'], dict(kind=kind)
        )
        return self.host.StructureInput.model_validate(
            {k: v for k, v in body.items() if k != 'request_id'}
        ).model_dump(mode='json', exclude={'revision'}) | dict(request_id=body['request_id'])

    def remote(self, body, missing=False):
        remote = old.ControlTests.remote(self, body)
        original = remote.get.side_effect

        async def get(url):
            name = url.rsplit('/', 1)[-1]
            for key in ('13', '17'):
                node = flow.build(body, body['request_id'])[key]
                if name == node['class_type']:
                    inputs = {
                        k: (
                            [[v]]
                            if isinstance(v, str)
                            else ['IMAGE']
                            if isinstance(v, list)
                            else ['INT', dict(min=0, max=8192)]
                        )
                        for k, v in node['inputs'].items()
                    }
                    inputs = {k: ([v] if isinstance(v, str) else v) for k, v in inputs.items()}
                    return httpx.Response(
                        200,
                        request=httpx.Request('GET', url),
                        json={}
                        if missing
                        else {
                            name: dict(
                                input=dict(required=inputs),
                                output=['IMAGE', 'POSE_KEYPOINT']
                                if name == 'DWPreprocessor'
                                else ['IMAGE'],
                            )
                        },
                    )
            return await original(url)

        remote.get.side_effect = get
        return remote

    def submit(self, body, remote):
        with patch('backend.submissions.httpx.AsyncClient', return_value=remote):
            return self.client.post('/api/structure/generate', json=body)

    def test_both_kinds_exact_graph_and_offline_restoration(self):
        for kind in ('pose', 'depth'):
            body = self.body(kind)
            remote = self.remote(body)
            response = self.submit(body, remote)
            self.assertEqual(response.status_code, 200, response.text)
            job = response.json()
            self.assertEqual(job['workflow']['5']['inputs']['seed'], 2**64 - 1)
            self.assertEqual(
                job['reference_metadata'][0]['control_preprocessing'], flow.policy(body)
            )
            self.assertEqual(job['workflow']['16']['inputs']['images'], ['13', 0])
            self.assertEqual(job['workflow']['15']['inputs']['image'], ['13', 0])
            jobs.update(self.db, job['id'], status='failed')
            with patch(
                'backend.submissions.httpx.AsyncClient', side_effect=AssertionError('offline')
            ):
                restored = self.client.get('/api/jobs/' + job['id'] + '/creation-settings')
                self.assertEqual(restored.status_code, 200, restored.text)
                self.assertEqual(restored.json()['settings']['control_kind'], kind)
                self.assertEqual(restored.json()['settings']['seed'], str(2**64 - 1))
                again = self.client.post('/api/structure/generate', json=body)
                self.assertEqual(again.status_code, 200)
                self.assertEqual(
                    self.client.post(
                        '/api/structure/generate', json=body | dict(control_strength=0.7)
                    ).status_code,
                    409,
                )

    def test_missing_node_never_uploads_or_prompts(self):
        body = self.body()
        remote = self.remote(body, missing=True)
        self.assertEqual(self.submit(body, remote).status_code, 422)
        self.assertEqual(remote.post.await_count, 0)

    def test_kind_mismatch_and_sd1_rejected_before_upload(self):
        body = self.body()
        control_catalog.update_metadata(
            self.db, body['engine_url'], body['control_net_name'], dict(kind='depth')
        )
        remote = self.remote(body)
        self.assertEqual(self.submit(body, remote).status_code, 409)
        self.assertEqual(remote.post.await_count, 0)

    def test_legacy_and_general_endpoints_reject_structure_parameters(self):
        body = self.body()
        for path in ('control/generate', 'control-edge/generate', 'generate'):
            self.assertEqual(self.client.post('/api/' + path, json=body).status_code, 422)
        self.assertEqual(
            self.client.post(
                '/api/structure/generate', json=body | dict(canny_low=0.4)
            ).status_code,
            422,
        )

    def test_actual_condition_output_is_saved_once_and_verified_offline(self):
        body = self.body('depth')
        job = self.submit(body, self.remote(body)).json()
        identifier = job['id']
        image = Image.new('RGB', (body['width'], body['height']), (100, 20, 30))
        stream = io.BytesIO()
        image.save(stream, format='PNG')
        raw = stream.getvalue()
        history = dict(
            status=dict(completed=True, status_str='success'),
            outputs={
                '16': dict(
                    images=[
                        dict(
                            filename='condition_00001_.png',
                            subfolder='model_atelier/' + identifier,
                            type='output',
                        )
                    ]
                ),
                '7': dict(images=[dict(filename='result.png', subfolder='', type='output')]),
            },
        )
        jobs.update(self.db, identifier, status='completed', history=history)
        self.assertEqual(len(gallery.outputs(jobs.get(self.db, identifier))), 1)
        transport = httpx.MockTransport(lambda r: httpx.Response(200, content=raw))
        factory = lambda **kw: httpx.AsyncClient(transport=transport, **kw)
        with patch.object(self.host, 'http_client', factory):
            result = self.client.post('/api/jobs/' + identifier + '/structure-output')
            self.assertEqual(result.status_code, 200, result.text)
        with patch.object(self.host, 'http_client', side_effect=AssertionError('offline')):
            self.assertEqual(
                self.client.get('/api/jobs/' + identifier + '/structure-output/image').content, raw
            )
            self.assertFalse(
                self.client.post('/api/jobs/' + identifier + '/structure-output').json()['imported']
            )
        from backend import structure_outputs

        target = structure_outputs.path(self.host.DATA, identifier)
        from backend import backup

        self.assertTrue(backup.inspect(self.host.DATA, database=self.db)['ok'])
        target.write_bytes(b'broken')
        self.assertFalse(backup.inspect(self.host.DATA, database=self.db)['ok'])
        self.assertEqual(
            self.client.get('/api/jobs/' + identifier + '/structure-output').json()['state'],
            'unavailable',
        )

    def test_tampered_condition_graph_or_preprocessing_cannot_restore(self):
        body = self.body()
        job = self.submit(body, self.remote(body)).json()
        for field in ('workflow', 'reference_metadata', 'version'):
            value = copy.deepcopy(job)
            value['source'] = dict(node_id='7')
            if field == 'workflow':
                value[field]['13']['inputs']['image'] = ['12', 0]
            elif field == 'version':
                value['reference_metadata'][0]['control_preprocessing']['version'] = True
            else:
                value[field][0]['control_preprocessing']['kind'] = 'depth'
            with self.assertRaises(ValueError):
                flow.extract(value, lambda v: v)
