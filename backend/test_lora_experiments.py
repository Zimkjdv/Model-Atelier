import copy
import unittest
from unittest.mock import patch
from backend import main, test_api


class LoraExperimentTests(unittest.TestCase):
    setUp = test_api.ApiTests.setUp
    tearDown = test_api.ApiTests.tearDown

    def payload(self):
        settings = main.DraftInput(title='原設定', engine_url='http://127.0.0.1:8188', checkpoint='model',
            prompt='wooden chair', seed='18446744073709551615', loras=[
                dict(name='first', strength_model=.7, strength_clip=.3),
                dict(name='off', enabled=False, strength_model=2, strength_clip=0),
                dict(name='last', strength_model=1, strength_clip=.5)]).model_dump(mode='json', exclude={'revision'})
        return dict(title='強度比較', settings=settings, axis='lora_strength_model',
                    target_lora='last', values=[0, .5, 1], case_ids=[])

    def test_model_and_clip_axes_preserve_order_other_strengths_and_readonly_export(self):
        before = self.db.read_bytes()
        for axis, field in [('lora_strength_model', 'strength_model'), ('lora_strength_clip', 'strength_clip')]:
            body = self.payload() | dict(axis=axis)
            with patch('backend.main.httpx.AsyncClient', side_effect=AssertionError('no engine')):
                result = self.client.post('/api/experiments/preview', json=body)
                self.assertEqual(result.status_code, 200, result.text)
                plan = result.json()
                self.assertEqual(plan['target_lora'], 'last')
                self.assertEqual(plan['baseline'], body['settings'])
                for v, row in zip(body['values'], plan['variants']):
                    expected = copy.deepcopy(body['settings'])
                    expected['loras'][2][field] = v
                    self.assertEqual({k:x for k,x in row['settings'].items() if k!='title'},
                                     {k:x for k,x in expected.items() if k!='title'})
                    self.assertEqual(row['value'], v)
                exported = self.client.post('/api/experiments/export', json=body | dict(expected_plan_sha256=plan['plan_sha256']))
                self.assertEqual(exported.json(), plan)
        self.assertEqual(before, self.db.read_bytes())
        self.assertEqual(self.client.get('/api/jobs').json(), [])
        self.assertEqual(self.client.get('/api/drafts').json(), [])

    def test_disabled_missing_target_invalid_values_and_axis_injection_are_rejected(self):
        body = self.payload()
        for change in [dict(target_lora=None), dict(target_lora='missing'), dict(target_lora='off'),
                       dict(values=[True]), dict(values=['0.5']), dict(values=[21]),
                       dict(values=[-21]), dict(values=[1,1.0]), dict(axis='steps'), dict(axis='loras')]:
            response = self.client.post('/api/experiments/preview', json=body | change)
            self.assertEqual(response.status_code, 422, response.text)
        for target in ['first', 'last']:
            plan = self.client.post('/api/experiments/preview', json=body | dict(target_lora=target)).json()
            other = self.client.post('/api/experiments/export', json=body | dict(target_lora='first' if target=='last' else 'last', expected_plan_sha256=plan['plan_sha256']))
            self.assertEqual(other.status_code, 409)

    def test_fixed_cases_only_replace_prompt_and_lora_axis_preserves_zero_and_negative(self):
        body = self.payload() | dict(values=[-1, 0], case_ids=['chair','lake'])
        response = self.client.post('/api/experiments/preview', json=body)
        self.assertEqual(response.status_code, 200, response.text)
        plan = response.json()
        self.assertEqual(plan['expected_job_count'], 4)
        for row in plan['variants']:
            self.assertEqual(row['settings']['seed'], '18446744073709551615')
            self.assertEqual([v['name'] for v in row['settings']['loras']], ['first','off','last'])
            self.assertEqual(row['settings']['loras'][2]['strength_model'], row['value'])
            self.assertEqual(row['settings']['loras'][2]['strength_clip'], .5)
            self.assertNotEqual(row['settings']['prompt'], body['settings']['prompt'])
        self.assertEqual(self.client.post('/api/experiments/preview', json=body | dict(values=[0,.5,1], case_ids=['chair','lake','traveler-station'])).status_code, 422)
