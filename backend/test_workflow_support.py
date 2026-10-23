"""Specialized formats must fail closed while complete originals remain recoverable."""

import io
import unittest
from unittest.mock import patch
from uuid import uuid4

from PIL import Image
from backend import assets, catalog, control_catalog, gallery, jobs, test_api
from backend import workflow_support as support, settings_transfer
from backend import (
    inpaint_workflows,
    inpaint_feather_workflows,
    control_workflows,
    control_edge_workflows,
)


class WorkflowSupportTests(unittest.TestCase):
    setUp = test_api.ApiTests.setUp
    tearDown = test_api.ApiTests.tearDown

    def settings(self, identifier):
        source, mask = str(uuid4()), str(uuid4())
        common = dict(
            title='專用格式',
            engine_url='http://127.0.0.1:8188',
            checkpoint='demo.safetensors',
            prompt='forest',
            width=64,
            height=64,
            seed='18446744073709551615',
        )
        if 'inpaint' in identifier:
            schema = (
                self.host.InpaintFeatherInput
                if identifier == inpaint_feather_workflows.ID
                else self.host.InpaintInput
            )
            fields = dict(
                image_asset_id=source,
                mask_asset_id=mask,
                reference_ids=[source, mask],
                grow_mask_by=17,
            )
            if schema is self.host.InpaintFeatherInput:
                fields['feather_radius'] = 4
        else:
            schema = self.host.ControlInput
            fields = dict(
                image_asset_id=source,
                reference_ids=[source],
                control_net_name='canny.safetensors',
                control_strength=0.75,
                control_start=0.1,
                control_end=0.9,
                canny_low=0.2,
                canny_high=0.8,
            )
        return schema(**common, **fields).model_dump(mode='json', exclude={'revision'})

    def test_descriptions_are_readonly_versioned_and_do_not_claim_engine_readiness(self):
        before = self.db.read_bytes()
        with patch('backend.main.httpx.AsyncClient', side_effect=AssertionError('no engine')):
            all_ids = []
            for family in ('inpaint', 'control'):
                response = self.client.get(
                    '/api/reference-workflows/support', params={'family': family}
                )
                self.assertEqual(response.status_code, 200)
                value = response.json()
                self.assertEqual(value['scope'], 'platform_formats')
                self.assertEqual([row['version'] for row in value['workflows']], [1, 2])
                for row in value['workflows']:
                    all_ids.append(row['id'])
                    self.assertFalse(row['capabilities']['draft'])
                    self.assertFalse(row['capabilities']['settings_import'])
                    self.assertFalse(row['capabilities']['settings_export'])
                    self.assertFalse(row['capabilities']['comparison_plan'])
                    self.assertTrue(row['capabilities']['restore_saved_settings'])
                    self.assertTrue(row['capabilities']['download_workflow'])
            self.assertEqual(set(all_ids), support.IDS)
            self.assertEqual(
                self.client.get('/api/reference-workflows/support?family=unknown').status_code, 422
            )
        self.assertEqual(self.db.read_bytes(), before)

    def test_general_draft_create_and_update_reject_specialized_or_unknown_fields_atomically(self):
        normal = dict(
            title='原草稿', engine_url='http://127.0.0.1:8188', seed='18446744073709551615'
        )
        saved = self.client.post('/api/drafts', json=normal).json()
        before = self.db.read_bytes()
        cases = [self.settings(identifier) for identifier in support.IDS]
        cases += [normal | {key: 0} for key in support.SPECIAL_FIELDS]
        cases += [
            normal | dict(workflow_id='checkpoint-inpaint-feather-v999'),
            normal | dict(new_unrecognized_parameter=3),
        ]
        with patch('backend.main.httpx.AsyncClient', side_effect=AssertionError('no engine')):
            for body in cases:
                for path, method in [
                    ('/api/drafts', self.client.post),
                    ('/api/drafts/' + saved['id'], self.client.put),
                ]:
                    response = method(path, json=body | dict(revision=saved['revision']))
                    self.assertEqual(response.status_code, 422, response.text)
        self.assertEqual(self.db.read_bytes(), before)
        self.assertEqual(self.client.get('/api/drafts').json()[0]['seed'], normal['seed'])

    def test_current_transfer_preview_export_save_and_import_do_not_drop_specialized_fields(self):
        before = self.db.read_bytes()
        for identifier in support.IDS:
            settings = self.settings(identifier)
            for declared in (
                identifier,
                settings_transfer.IMAGE if 'inpaint' in identifier else settings_transfer.STANDARD,
            ):
                bundle = settings_transfer.document(declared, settings)
                response = self.client.post('/api/creation-settings/import', json=bundle)
                self.assertEqual(response.status_code, 422, response.text)
                self.assertIn('未部分', response.json()['detail'])
                response = self.client.post(
                    '/api/creation-settings/export',
                    json=dict(workflow_id=declared, settings=settings),
                )
                self.assertEqual(response.status_code, 422, response.text)
            body = dict(
                title='不能降級', settings=settings, axis='steps', values=[4, 8], case_ids=[]
            )
            for endpoint in ('preview', 'export'):
                response = self.client.post('/api/experiments/' + endpoint, json=body)
                self.assertEqual(response.status_code, 422, response.text)
                self.assertIn('未部分', response.json()['detail'])
            invalid = dict(
                kind='model-atelier-comparison-plan',
                schema_version=1,
                workflow_id=identifier,
                baseline=settings,
            )
            for endpoint in ('import-preview', 'document-export'):
                self.assertEqual(
                    self.client.post('/api/experiments/' + endpoint, json=invalid).status_code, 422
                )
            self.assertEqual(
                self.client.post(
                    '/api/experiments/plans', json=dict(request_id=str(uuid4()), plan=invalid)
                ).status_code,
                422,
            )
        self.assertEqual(self.db.read_bytes(), before)
        self.assertEqual(self.client.get('/api/jobs').json(), [])

    def test_legacy_draft_envelopes_remain_compatible_without_selecting_record_or_job_ids(self):
        requested_id = str(uuid4())
        body = dict(
            title='相容回讀',
            engine_url='http://127.0.0.1:8188',
            seed='18446744073709551615',
            id=requested_id,
            request_id=requested_id,
            created_at='forged',
            updated_at='forged',
            model_version='forged',
        )
        response = self.client.post('/api/drafts', json=body)
        self.assertEqual(response.status_code, 201, response.text)
        saved = response.json()
        self.assertNotEqual(saved['id'], requested_id)
        self.assertNotEqual(saved['created_at'], 'forged')
        self.assertNotEqual(saved['model_version'], 'forged')
        self.assertNotIn('request_id', saved)
        updated = self.client.put(
            '/api/drafts/' + saved['id'], json=saved | dict(prompt='retained')
        )
        self.assertEqual(updated.status_code, 200, updated.text)
        self.assertEqual(updated.json()['seed'], body['seed'])
        self.assertEqual(updated.json()['revision'], 2)
        self.assertEqual(self.client.get('/api/jobs').json(), [])

    def original(self, adapter):
        settings = self.settings(adapter.ID)
        for index, identifier in enumerate(settings['reference_ids']):
            stream = io.BytesIO()
            image = Image.new('RGB', (64, 64), '#718d76' if index == 0 else 'black')
            if index:
                image.paste('white', (32, 0, 64, 64))
            image.save(stream, 'PNG')
            actual = assets.create(
                self.db, self.host.DATA / 'assets', stream.getvalue(), str(index) + '.png'
            )
            settings['reference_ids'][index] = actual['id']
        settings['image_asset_id'] = settings['reference_ids'][0]
        if 'mask_asset_id' in settings:
            settings['mask_asset_id'] = settings['reference_ids'][1]
        engine, checkpoint = settings['engine_url'], settings['checkpoint']
        catalog.merge(self.db, engine, [checkpoint])
        catalog.update_metadata(
            self.db, engine, checkpoint, dict(architecture='sdxl', version='fixture-v1')
        )
        model = catalog.capture(catalog.read(self.db, engine)['models'][0], checkpoint)
        references, _ = adapter.prepare(self.db, self.host.DATA, settings)
        components = None
        if 'control_net_name' in settings:
            references = [references]
            control_catalog.merge(self.db, engine, [settings['control_net_name']])
            control_catalog.update_metadata(
                self.db,
                engine,
                settings['control_net_name'],
                dict(architecture='sdxl', kind='canny'),
            )
            components = [
                control_catalog.capture(control_catalog.read(self.db, engine)['controlnets'][0])
            ]
        identifier = str(uuid4())
        job = jobs.reserve(
            self.db,
            identifier,
            engine,
            adapter.build(settings, identifier),
            checkpoint,
            model_metadata=model,
            workflow_id=adapter.ID,
            component_metadata=components,
            reference_metadata=references,
            reference_settings=settings,
        )[0]
        job = jobs.update(self.db, identifier, status='completed')
        stream = io.BytesIO()
        Image.new('RGB', (64, 64), '#718d76').save(stream, 'PNG')
        artwork = gallery.save(
            self.db,
            self.host.DATA / 'artworks',
            job,
            dict(node_id='7', filename='original.png', subfolder='', type='output'),
            stream.getvalue(),
        )[0]
        return job, artwork, settings

    def test_all_four_originals_retain_full_workflow_exact_seed_and_complete_restoration(self):
        for adapter in (
            inpaint_workflows,
            inpaint_feather_workflows,
            control_workflows,
            control_edge_workflows,
        ):
            job, artwork, settings = self.original(adapter)
            before = self.db.read_bytes()
            with patch('backend.main.httpx.AsyncClient', side_effect=AssertionError('no engine')):
                for family, item in [('jobs', job), ('artworks', artwork)]:
                    path = '/api/' + family + '/' + item['id']
                    denied = self.client.get(path + '/settings-export')
                    self.assertEqual(denied.status_code, 422, denied.text)
                    self.assertIn('完整工作流程', denied.json()['detail'])
                    raw = self.client.get(path + '/workflow')
                    self.assertEqual(raw.json(), job['workflow'])
                    self.assertIn('18446744073709551615', raw.text)
                    restored = self.client.get(path + '/creation-settings')
                    self.assertEqual(restored.status_code, 200, restored.text)
                    self.assertEqual(restored.json()['settings'], settings)
            self.assertEqual(self.db.read_bytes(), before)
            self.assertEqual(jobs.get(self.db, job['id'])['workflow_id'], adapter.ID)


if __name__ == '__main__':
    unittest.main()
