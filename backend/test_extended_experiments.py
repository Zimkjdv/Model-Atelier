"""Comparison v2 preserves one changed field and frozen registered identities."""

import copy
import unittest
from unittest.mock import patch
from uuid import uuid4
from backend import catalog, experiment_plans, gallery, jobs, main, test_gallery
from backend import test_experiment_runs as old, test_image_workflows, test_submissions


class ExtendedExperiments(unittest.TestCase):
    setUp = old.ExperimentRunTests.setUp
    tearDown = old.ExperimentRunTests.tearDown
    remote = old.ExperimentRunTests.remote
    body = old.ExperimentRunTests.body
    submit = old.ExperimentRunTests.submit

    def settings(self, image=False):
        raw = (
            test_image_workflows.ImageWorkflowTests.body(self)
            if image
            else test_submissions.SubmissionTests.payload(self)
        )
        names = ['test.safetensors', 'alternate.safetensors']
        catalog.merge(self.db, raw['engine_url'], names)
        for index, name in enumerate(names):
            catalog.update_metadata(
                self.db,
                raw['engine_url'],
                name,
                dict(architecture='sdxl', version='v' + str(index + 1), sha256=str(index + 1) * 64),
            )
        return main.DraftInput.model_validate(raw).model_dump(mode='json', exclude={'revision'})

    def preview(self, settings=None, axis='checkpoint', values=None, **kwargs):
        return self.client.post(
            '/api/experiments/preview',
            json=dict(
                title='R06 frozen',
                settings=settings or self.settings(),
                axis=axis,
                values=values or ['test.safetensors', 'alternate.safetensors'],
                **kwargs,
            ),
        )

    def save(self, plan):
        response = self.client.post(
            '/api/experiments/plans', json=dict(request_id=str(uuid4()), plan=plan)
        )
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()

    def test_each_new_axis_preserves_all_other_fields_in_both_workflows(self):
        for image in (False, True):
            settings = self.settings(image)
            settings['loras'] = [
                dict(
                    name='retained.safetensors',
                    enabled=False,
                    strength_model=-0.25,
                    strength_clip=1.5,
                )
            ]
            for axis, values in [
                ('checkpoint', ['test.safetensors', 'alternate.safetensors']),
                ('sampler_name', ['euler', 'dpmpp_2m']),
                ('scheduler', ['normal', 'karras']),
            ]:
                with patch(
                    'backend.main.httpx.AsyncClient',
                    side_effect=AssertionError('preview is offline'),
                ):
                    response = self.preview(settings, axis, values)
                self.assertEqual(response.status_code, 200, response.text)
                plan = response.json()
                self.assertEqual(plan['schema_version'], 2)
                self.assertEqual(plan['baseline'], settings)
                self.assertEqual(plan['expected_job_count'], 2)
                for variant, value in zip(plan['variants'], values):
                    self.assertEqual(
                        variant['settings'],
                        settings | {axis: value, 'title': variant['settings']['title']},
                    )
                    self.assertEqual(variant['settings']['seed'], '18446744073709551615')
                self.assertEqual(len(plan['model_snapshots']), 2 if axis == 'checkpoint' else 1)
        self.assertEqual(self.client.get('/api/jobs').json(), [])
        self.assertEqual(self.client.get('/api/drafts').json(), [])

    def test_limits_types_missing_models_and_architecture_never_create_partial_plan(self):
        settings = self.settings()
        cases = [v['id'] for v in self.client.get('/api/experiments/suite').json()['cases']]
        response = self.preview(settings, case_ids=cases)
        self.assertEqual(response.json()['expected_job_count'], 8)
        for axis, values in [
            ('sampler_name', ['euler', 'dpmpp_2m', 'ddim']),
            ('checkpoint', ['absent']),
            ('scheduler', ['normal', 'normal']),
            ('sampler_name', [True]),
            ('scheduler', [' karras']),
            ('sampler_name', ['']),
        ]:
            response = self.preview(settings, axis, values, case_ids=cases)
            self.assertEqual(response.status_code, 422, response.text)
        for architecture in ('unknown', 'flux', 'sd1'):
            catalog.update_metadata(
                self.db,
                settings['engine_url'],
                'alternate.safetensors',
                dict(architecture=architecture),
            )
            self.assertEqual(self.preview(settings).status_code, 422)
        catalog.sync_error(self.db, settings['engine_url'], 'offline')
        self.assertEqual(self.preview(settings, 'scheduler', ['normal']).status_code, 422)
        self.assertEqual(self.client.get('/api/jobs').json(), [])

    def test_saved_import_and_export_retain_snapshot_offline_after_catalog_change(self):
        settings = self.settings(True)
        plan = self.preview(settings).json()
        record = self.save(plan)
        catalog.update_metadata(
            self.db,
            settings['engine_url'],
            'test.safetensors',
            dict(version='changed', sha256='f' * 64),
        )
        catalog.sync_error(self.db, settings['engine_url'], 'offline')
        before = self.db.read_bytes()
        with patch('backend.main.httpx.AsyncClient', side_effect=AssertionError('no engine')):
            candidates = [
                self.client.get('/api/experiments/plans/' + record['id']),
                self.client.post('/api/experiments/import-preview', json=plan),
                self.client.post('/api/experiments/document-export', json=plan),
            ]
        for response in candidates:
            self.assertEqual(response.status_code, 200, response.text)
            result = response.json().get('plan', response.json())
            self.assertEqual(result['plan_sha256'], plan['plan_sha256'])
            self.assertEqual(result['model_snapshots'], plan['model_snapshots'])
            self.assertEqual(result['variants'], plan['variants'])
        self.assertEqual(before, self.db.read_bytes())

    def test_import_rejects_rehashed_inconsistent_schema_identity_and_settings(self):
        plan = self.preview().json()
        for kind in ('schema', 'missing', 'engine', 'order', 'variant', 'extra'):
            raw = copy.deepcopy(plan)
            if kind == 'schema':
                raw['schema_version'] = 1
            elif kind == 'missing':
                raw.pop('model_snapshots')
            elif kind == 'engine':
                raw['model_snapshots'][0]['engine_url'] = 'http://127.0.0.1:9999'
            elif kind == 'order':
                raw['model_snapshots'].reverse()
            elif kind == 'variant':
                raw['variants'][0]['settings']['cfg'] = 1
            else:
                raw['model_snapshots'][0]['invented'] = True
            raw['plan_sha256'] = experiment_plans.digest(raw)
            self.assertEqual(
                self.client.post('/api/experiments/import-preview', json=raw).status_code, 422, kind
            )

    def test_browser_integer_serialization_preserves_v2_hash(self):
        plan = self.preview().json()
        raw = copy.deepcopy(plan)
        for settings in [raw['baseline'], *[v['settings'] for v in raw['variants']]]:
            for key in ('cfg', 'denoise'):
                settings[key] = int(settings[key])
        self.assertEqual(experiment_plans.digest(raw), plan['plan_sha256'])
        self.assertEqual(
            self.client.post('/api/experiments/import-preview', json=raw).status_code, 200
        )
        self.save(raw)

    def test_export_of_fresh_preview_refuses_changed_registration(self):
        settings = self.settings()
        plan = self.preview(settings).json()
        catalog.update_metadata(
            self.db, settings['engine_url'], settings['checkpoint'], dict(version='new')
        )
        response = self.client.post(
            '/api/experiments/export',
            json=dict(
                title=plan['title'],
                settings=settings,
                axis=plan['axis'],
                values=plan['values'],
                expected_plan_sha256=plan['plan_sha256'],
            ),
        )
        self.assertEqual(response.status_code, 409, response.text)

    def test_changed_registration_and_capture_race_block_before_engine_or_job(self):
        settings = self.settings()
        record = self.save(self.preview(settings).json())
        reserve = jobs.reserve

        def race(*args, **kwargs):
            catalog.update_metadata(
                self.db, settings['engine_url'], settings['checkpoint'], dict(sha256='f' * 64)
            )
            return reserve(*args, **kwargs)

        with (
            patch('backend.jobs.reserve', side_effect=race),
            patch('backend.submissions.httpx.AsyncClient', side_effect=AssertionError('no engine')),
        ):
            self.assertEqual(
                self.client.post('/api/generate', json=self.body(record)).status_code, 409
            )
        with patch(
            'backend.submissions.httpx.AsyncClient', side_effect=AssertionError('no engine')
        ):
            self.assertEqual(
                self.client.post('/api/generate', json=self.body(record)).status_code, 409
            )
        self.assertEqual(self.client.get('/api/jobs').json(), [])

    def test_manual_job_artwork_report_trace_and_original_uuid_recovery(self):
        settings = self.settings()
        record = self.save(self.preview(settings).json())
        body = self.body(record)
        remote = self.remote()
        response = self.submit(body, remote)
        self.assertEqual(response.status_code, 200, response.text)
        job = response.json()
        self.assertEqual(job['experiment_context']['schema_version'], 2)
        self.assertEqual(
            job['experiment_context']['expected_model_metadata'],
            record['plan']['model_snapshots'][0],
        )
        job = jobs.update(
            self.db,
            job['id'],
            status='completed',
            history=dict(status=dict(completed=True, status_str='success')),
        )
        artwork, _ = gallery.save(
            self.db,
            self.db.parent / 'artworks',
            job,
            dict(node_id='7', filename='result.png', subfolder='', type='output'),
            test_gallery.GalleryTests.image(self),
        )
        self.assertEqual(artwork['experiment_context'], job['experiment_context'])
        catalog.update_metadata(
            self.db, settings['engine_url'], settings['checkpoint'], dict(version='later')
        )
        catalog.sync_error(self.db, settings['engine_url'], 'offline')
        before = self.db.read_bytes()
        with patch(
            'backend.main.httpx.AsyncClient', side_effect=AssertionError('no resubmit or probe')
        ):
            self.assertEqual(self.client.post('/api/generate', json=body).json()['id'], job['id'])
            report = self.client.get(
                '/api/experiments/plans/' + record['id'] + '/report',
                params=dict(expected_plan_sha256=record['plan']['plan_sha256']),
            )
            result = self.client.get('/api/experiments/plans/' + record['id'] + '/results').json()
        self.assertEqual(report.status_code, 200, report.text)
        self.assertEqual(
            report.json()['variants'][0]['runs'][0]['experiment_context'], job['experiment_context']
        )
        self.assertEqual(result['variants'][1]['runs'], [])
        self.assertEqual(before, self.db.read_bytes())
        self.assertEqual(remote.post.await_count, 1)

    def test_unknown_metadata_stays_unknown_and_old_axes_keep_schema_one(self):
        settings = self.settings()
        catalog.update_metadata(
            self.db, settings['engine_url'], settings['checkpoint'], dict(version='', sha256='')
        )
        plan = self.preview(settings, 'scheduler', ['normal']).json()
        self.assertEqual(plan['model_snapshots'][0]['version'], '未知')
        self.assertEqual(plan['model_snapshots'][0]['sha256'], '')
        self.assertTrue(any('無法' in v for v in plan['warnings']))
        old_plan = self.preview(settings, 'seed', ['9007199254740993']).json()
        self.assertEqual(old_plan['schema_version'], 1)
        self.assertNotIn('model_snapshots', old_plan)
        self.assertEqual(
            self.client.post('/api/experiments/import-preview', json=old_plan).json()[
                'plan_sha256'
            ],
            old_plan['plan_sha256'],
        )
