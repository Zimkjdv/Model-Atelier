"""Dedicated formats preserve source identity and use the original submission ledger."""

import io
import unittest
from uuid import uuid4

from PIL import Image

from backend import assets, jobs, test_api
from backend import specialized_settings as formats
from backend import inpaint_feather_workflows as feather


class SpecializedSettingsTests(unittest.TestCase):
    setUp = test_api.ApiTests.setUp
    tearDown = test_api.ApiTests.tearDown

    def asset(self, color):
        encoded = io.BytesIO()
        Image.new('RGB', (64, 64), color).save(encoded, 'PNG')
        return assets.create(self.db, self.host.DATA / 'assets', encoded.getvalue(), color + '.png')

    def capture(self, workflow=feather.ID, **changes):
        source, mask = self.asset('blue'), self.asset('white')
        schema = getattr(self.host, formats.FLOW_SCHEMAS[workflow])
        data = dict(
            title='版本化專用設定',
            checkpoint='demo.safetensors',
            engine_url=self.host.engine_url(),
            seed='18446744073709551615',
            width=64,
            height=64,
            image_asset_id=source['id'],
            reference_ids=[source['id']],
        )
        if 'mask_asset_id' in schema.model_fields:
            data.update(reference_ids=[source['id'], mask['id']], mask_asset_id=mask['id'])
        if 'control_net_name' in schema.model_fields:
            data['control_net_name'] = 'control.safetensors'
        if 'control_kind' in schema.model_fields:
            data['control_kind'] = 'pose'
        if 'reference_mode' in schema.model_fields:
            data.update(reference_mode='style', ipadapter_name='plus', clip_vision_name='vision')
        if 'inpaint_model' in schema.model_fields:
            data.update(inpaint_model='fooocus-v2.6', checkpoint='animagine-xl-4.0-opt.safetensors')
        data.update(changes)
        value = schema.model_validate(data).model_dump(mode='json', exclude={'revision'})
        response = self.client.post(
            formats.PREFIX + '/settings/capture', json=dict(workflow_id=workflow, settings=value)
        )
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def test_all_versions_capture_without_writing_and_round_trip(self):
        for identifier in formats.FLOW_SCHEMAS:
            with self.subTest(identifier=identifier):
                doc = self.capture(identifier)
                before = self.db.read_bytes()
                preview = self.client.post(formats.PREFIX + '/settings/import-preview', json=doc)
                self.assertEqual(preview.status_code, 200, preview.text)
                self.assertTrue(preview.json()['loadable'])
                self.assertEqual(preview.json()['document'], doc)
                self.assertEqual(doc['settings']['seed'], '18446744073709551615')
                self.assertEqual(self.db.read_bytes(), before)

    def test_partial_draft_update_conflict_and_changed_source(self):
        schema = self.host.InpaintFeatherInput
        partial = {
            key: field.get_default(call_default_factory=True)
            for key, field in schema.model_fields.items()
            if key != 'revision'
        }
        partial.update(
            title='尚未選圖',
            engine_url=self.host.engine_url(),
            mask_asset_id=None,
            image_asset_id=None,
            reference_ids=[],
        )
        response = self.client.post(
            formats.PREFIX + '/settings/capture',
            json=dict(workflow_id=feather.ID, settings=partial),
        )
        self.assertEqual(response.status_code, 200, response.text)
        draft = self.client.post(formats.PREFIX + '/drafts', json=dict(document=response.json()))
        self.assertEqual(draft.status_code, 201, draft.text)
        self.assertEqual(self.client.get('/api/drafts').json(), [])
        path = formats.PREFIX + '/drafts/' + draft.json()['id']
        complete = self.capture(feather_radius=4)
        changed = self.client.put(path, json=dict(document=complete, revision=1))
        self.assertEqual(changed.status_code, 200, changed.text)
        self.assertEqual(changed.json()['revision'], 2)
        self.assertEqual(
            self.client.put(path, json=dict(document=complete, revision=1)).status_code, 409
        )
        source_id = complete['input_assets'][0]['id']
        self.assertIn(draft.json()['id'], assets.usage(self.db, source_id)['drafts'])
        (self.host.DATA / 'assets' / (source_id + '.png')).write_bytes(b'replaced')
        preview = self.client.post(formats.PREFIX + '/settings/import-preview', json=complete)
        self.assertFalse(preview.json()['loadable'])
        self.assertEqual(
            self.client.put(path, json=dict(document=complete, revision=2)).status_code, 409
        )

    def test_comparison_rejects_forged_settings_and_links_original_job(self):
        doc = self.capture()
        comparison = formats.PREFIX + '/comparisons'
        response = self.client.post(
            comparison + '/preview', json=dict(document=doc, axis='feather_radius', values=[0, 4])
        )
        self.assertEqual(response.status_code, 200, response.text)
        plan = response.json()
        first, second = plan['variants']
        self.assertEqual(first['settings'], doc['settings'])
        self.assertEqual(second['settings'], doc['settings'] | dict(feather_radius=4))
        self.assertEqual(
            self.client.post(comparison + '/import-preview', json=plan).json()['plan'], plan
        )
        identifier = str(uuid4())
        save = self.client.post(comparison, json=dict(request_id=identifier, plan=plan))
        self.assertEqual(save.status_code, 201, save.text)
        self.assertEqual(
            self.client.post(comparison, json=dict(request_id=identifier, plan=plan)).json(),
            save.json(),
        )
        self.assertEqual(
            self.client.post(
                comparison, json=dict(request_id=identifier, plan=plan | dict(title='fake'))
            ).status_code,
            422,
        )
        job_id = str(uuid4())
        settings = second['settings']
        snapshots, _ = feather.prepare(self.db, self.host.DATA, settings)
        selection = dict(
            plan_id=identifier, plan_sha256=plan['plan_sha256'], variant_id=second['id']
        )

        def reserve(request_id, active_settings):
            return jobs.reserve(
                self.db,
                request_id,
                settings['engine_url'],
                feather.build(active_settings, request_id),
                settings['checkpoint'],
                workflow_id=feather.ID,
                reference_settings=active_settings,
                reference_metadata=snapshots,
                experiment=selection,
                generation_settings=active_settings,
            )

        with self.assertRaisesRegex(ValueError, '設定與比較組'):
            reserve(job_id, settings | dict(prompt='not the comparison'))
        job, fresh = reserve(job_id, settings)
        self.assertTrue(fresh)
        self.assertEqual(job['experiment_context']['variant_id'], second['id'])
        self.assertEqual(reserve(job_id, settings)[1], False)
        results = self.client.get(comparison + '/' + identifier + '/results').json()
        self.assertEqual(results['variants'][1]['runs'][0]['id'], job_id)
        jobs.compare_update(self.db, job, status='completed')
        original = self.client.get(formats.PREFIX + '/jobs/' + job_id + '/settings')
        self.assertEqual(original.status_code, 200, original.text)
        self.assertIn('18446744073709551615', original.json()['source_snapshot']['workflow_json'])
        self.assertEqual(
            self.client.put(
                comparison + '/' + identifier, json=dict(revision=1, archived=True)
            ).status_code,
            200,
        )
        self.assertFalse(reserve(job_id, settings)[1])
        with self.assertRaisesRegex(ValueError, '方案已封存'):
            reserve(str(uuid4()), settings)

    def test_unknown_versions_wrong_roles_and_injected_fields_are_rejected(self):
        doc = self.capture()
        path = formats.PREFIX + '/settings/import-preview'
        for invalid in (
            doc | dict(schema_version=2),
            doc | dict(workflow_id='checkpoint-inpaint-feather-v9'),
            doc | dict(input_assets=list(reversed(doc['input_assets']))),
            doc | dict(settings=doc['settings'] | dict(request_id=str(uuid4()))),
        ):
            with self.subTest(invalid=invalid):
                self.assertEqual(self.client.post(path, json=invalid).status_code, 422)
