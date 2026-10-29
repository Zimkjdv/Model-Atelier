"""Recipe origin is server-authored, immutable, replay-bound and preserved offline."""

import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

from fastapi.testclient import TestClient

from backend import jobs, template_context
from scripts.browser_fixture import ENGINE, fixture


class TemplateContextTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.client = TestClient(
            fixture(Path(self.temp.name)),
            base_url='http://127.0.0.1:8000',
            client=('127.0.0.1', 50000),
        )
        self.client.__enter__()
        self.client.post('/qa/simple-creation')
        self.client.post('/qa/engine/success')

    def tearDown(self):
        self.client.__exit__(None, None, None)
        self.temp.cleanup()

    def checkpoint(self, name='animagine'):
        choice = dict(template_id=name, template_version=1)
        source = template_context.recipe(choice)
        self.client.put(
            '/api/models/metadata',
            json=dict(
                engine_url=ENGINE,
                name='demo.safetensors',
                architecture='sdxl',
                sha256=source['requirements'][0]['sha256'],
            ),
        )
        return dict(
            source['baseline'],
            title=source['title'],
            engine_url=ENGINE,
            checkpoint='demo.safetensors',
            request_id=str(uuid4()),
            template_selection=choice,
        )

    def submit(self, body, path='/api/generate'):
        response = self.client.post(path, json=body)
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def test_server_recipe_and_actual_modifications_are_separate(self):
        body = self.checkpoint()
        original = self.submit(body)['template_context']
        self.assertFalse(original['modified'])
        self.assertEqual(original['selection'], body['template_selection'])
        self.assertEqual(len(original['recipe_sha256']), 64)
        self.assertIn('animagine', original['reference'])
        body.update(request_id=str(uuid4()), prompt='new scene', seed='18446744073709551615')
        changed = self.submit(body)['template_context']
        self.assertTrue(changed['modified'])
        self.assertEqual(changed['changed_fields'], ['prompt', 'seed'])
        self.assertEqual(changed['recipe_sha256'], original['recipe_sha256'])
        self.assertNotEqual(changed['baseline']['prompt'], body['prompt'])

    def test_same_uuid_cannot_change_or_remove_template_origin_and_replay_never_reloads_recipe(
        self,
    ):
        body = self.checkpoint()
        first = self.submit(body)
        with patch.object(
            template_context, 'recipe', side_effect=AssertionError('replay read recipe')
        ):
            self.assertEqual(self.submit(body)['template_context'], first['template_context'])
        altered = copy.deepcopy(body)
        altered['template_selection']['template_id'] = 'pony'
        self.assertEqual(self.client.post('/api/generate', json=altered).status_code, 409)
        altered.pop('template_selection')
        self.assertEqual(self.client.post('/api/generate', json=altered).status_code, 409)
        self.assertEqual(self.client.get('/qa/state').json()['prompts'], 1)

    def test_unknown_version_and_forged_snapshot_fields_are_rejected(self):
        for field, value in [
            ('template_version', 2),
            ('template_version', True),
            ('modified', False),
            ('reference', 'untrusted'),
        ]:
            body = self.checkpoint()
            body['template_selection'][field] = value
            self.assertEqual(self.client.post('/api/generate', json=body).status_code, 422)
        self.assertEqual(self.client.get('/qa/state').json()['prompts'], 0)

    def test_artwork_and_restoration_keep_frozen_source_when_catalog_and_recipe_change(self):
        body = self.checkpoint()
        job = self.submit(body)
        self.client.post('/api/jobs/' + job['id'] + '/refresh')
        result = self.client.post('/api/jobs/' + job['id'] + '/artworks').json()
        artwork = result['imported'][0]
        self.assertEqual(artwork['template_context'], job['template_context'])
        self.client.put(
            '/api/models/metadata',
            json=dict(
                engine_url=ENGINE, name='demo.safetensors', architecture='sdxl', sha256='f' * 64
            ),
        )
        self.client.post('/qa/engine/offline')
        with patch.object(
            template_context, 'recipe', side_effect=AssertionError('historical read recipe')
        ):
            saved = self.client.get('/api/artworks/' + artwork['id']).json()
            restored = self.client.get(
                '/api/artworks/' + artwork['id'] + '/creation-settings'
            ).json()
        self.assertEqual(saved['template_context'], job['template_context'])
        self.assertEqual(restored['template_context'], job['template_context'])
        self.assertEqual(restored['settings']['seed'], body['seed'])
        self.assertEqual(
            self.client.get('/api/artworks/' + artwork['id'] + '/image').status_code, 200
        )

    def test_schnell_original_and_conflicting_replay_use_four_component_snapshot(self):
        self.client.post('/qa/flux-extensions')
        choice = dict(template_id='flux', template_version=1)
        source = template_context.recipe(choice)
        components = json.loads(
            (template_context.ROOT / 'models/flux1-schnell-plan.json').read_text(encoding='utf-8')
        )['components']
        body = dict(
            source['baseline'],
            title='flux recipe',
            engine_url=ENGINE,
            workflow_id=source['workflow_id'],
            request_id=str(uuid4()),
            template_selection=choice,
            **{part['role']: part['filename'] for part in components},
        )
        job = self.submit(body, '/api/flux/generate')
        self.assertFalse(job['template_context']['modified'])
        self.assertEqual(len(job['template_context']['requirements']), 4)
        changed = copy.deepcopy(body)
        changed['template_selection']['template_id'] = 'pony'
        self.assertEqual(self.client.post('/api/flux/generate', json=changed).status_code, 409)
        body.pop('template_selection')
        self.assertEqual(self.client.post('/api/flux/generate', json=body).status_code, 409)

    def test_drafts_preserve_origin_and_removing_it_does_not_invent_a_source(self):
        body = self.checkpoint()
        body.pop('request_id')
        record = self.client.post('/api/drafts', json=body).json()
        self.assertEqual(record['template_selection'], body['template_selection'])
        body.pop('template_selection')
        updated = self.client.put(
            '/api/drafts/' + record['id'], json=body | dict(revision=record['revision'])
        ).json()
        self.assertNotIn('template_selection', updated)
        body.update(request_id=str(uuid4()))
        self.assertIsNone(self.submit(body)['template_context'])

    def test_reserved_source_cannot_be_updated(self):
        body = self.checkpoint()
        job = self.submit(body)
        database = next(Path(self.temp.name).glob('*.sqlite3'))
        with self.assertRaisesRegex(ValueError, '不可變更'):
            jobs.update(database, job['id'], template_context=None)

    def test_every_new_model_recipe_has_its_own_immutable_source_and_exact_seed(self):
        entries = json.loads(
            (template_context.ROOT / template_context.EXTRA_REGISTRY).read_text(encoding='utf-8')
        )['templates']
        self.assertEqual(len(entries), 12)
        self.assertEqual(
            {
                model: sum(item['model_id'] == model for item in entries)
                for model in ('animagine', 'pony', 'flux')
            },
            dict(animagine=4, pony=4, flux=4),
        )
        self.client.post('/qa/flux-extensions')
        digests = set()
        for entry in entries:
            with self.subTest(template=entry['id']):
                source = template_context.recipe(dict(template_id=entry['id'], template_version=1))
                if entry['family'] == 'flux':
                    components = json.loads(
                        (template_context.ROOT / 'models/flux1-schnell-plan.json').read_text(
                            encoding='utf-8'
                        )
                    )['components']
                    body = dict(
                        source['baseline'],
                        engine_url=ENGINE,
                        title=entry['title'],
                        request_id=str(uuid4()),
                        template_selection=source['selection'],
                        **{part['role']: part['filename'] for part in components},
                    )
                    job = self.submit(body, '/api/flux/generate')
                else:
                    job = self.submit(self.checkpoint(entry['id']))
                self.assertFalse(job['template_context']['modified'])
                self.assertEqual(job['template_context']['source'], template_context.EXTRA_REGISTRY)
                self.assertEqual(job['template_context']['selection'], source['selection'])
                self.assertEqual(job['template_context']['baseline']['seed'], entry['seed'])
                digests.add(job['template_context']['recipe_sha256'])
        self.assertEqual(len(digests), 12)

    def test_style_lora_snapshot_and_reference_variable_input_survive_artwork_restoration(self):
        self.client.post('/qa/simple-style')
        for id in ('style-lora', 'style-reference'):
            with self.subTest(template=id):
                body = self.checkpoint(id)
                if id == 'style-reference':
                    asset = self.client.get('/qa/state').json()['asset_id']
                    body.update(image_asset_id=asset, reference_ids=[asset])
                path = '/api/reference/generate' if id == 'style-reference' else '/api/generate'
                job = self.submit(body, path)
                self.assertFalse(job['template_context']['modified'])
                self.assertEqual(job['template_context']['source'], template_context.STYLE_REGISTRY)
                self.assertEqual(
                    self.submit(body, path)['template_context'], job['template_context']
                )
                changed = copy.deepcopy(body)
                changed.pop('template_selection')
                self.assertEqual(self.client.post(path, json=changed).status_code, 409)
                self.client.post('/api/jobs/' + job['id'] + '/refresh')
                artwork = self.client.post('/api/jobs/' + job['id'] + '/artworks').json()[
                    'imported'
                ][0]
                restored = self.client.get(
                    '/api/artworks/' + artwork['id'] + '/creation-settings'
                ).json()
                self.assertEqual(restored['template_context'], job['template_context'])
                self.assertEqual(artwork['template_context'], job['template_context'])
                if id == 'style-reference':
                    self.assertEqual(restored['settings']['image_asset_id'], asset)
                    changed = dict(body, request_id=str(uuid4()), reference_weight=0.4)
                    self.assertIn(
                        'reference_weight',
                        self.submit(changed, path)['template_context']['changed_fields'],
                    )

    def test_style_reference_cannot_be_claimed_by_an_ordinary_text_workflow(self):
        body = self.checkpoint('style-reference')
        self.assertEqual(self.client.post('/api/generate', json=body).status_code, 409)
        self.assertEqual(self.client.get('/qa/state').json()['prompts'], 0)
