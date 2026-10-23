"""Anime suite selection and prompt comparisons preserve frozen old/new plans."""

import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from backend import experiment_plans as plans
from backend import test_extended_experiments as extended


class AnimeExperimentTests(unittest.TestCase):
    setUp = extended.ExtendedExperiments.setUp
    tearDown = extended.ExtendedExperiments.tearDown
    settings = extended.ExtendedExperiments.settings
    preview = extended.ExtendedExperiments.preview
    save = extended.ExtendedExperiments.save

    def test_anime_and_legacy_selection_export_import_preserve_snapshots(self):
        legacy = self.client.get('/api/experiments/suite').json()
        anime = self.client.get('/api/experiments/suite?suite_id=anime-illustration').json()
        self.assertEqual(legacy['sha256'], hashlib.sha256(plans.SUITE.read_bytes()).hexdigest())
        self.assertEqual(
            anime['sha256'], hashlib.sha256(plans.ANIME_SUITE.read_bytes()).hexdigest()
        )
        self.assertEqual(len(anime['cases']), 3)
        self.assertEqual(len({v['character_key'] for v in anime['cases']}), 1)
        for suite in (legacy, anime):
            response = self.preview(
                suite_id=suite['id'],
                case_ids=[suite['cases'][0]['id']],
            )
            self.assertEqual(response.status_code, 200, response.text)
            plan = response.json()
            record = self.save(plan)
            self.assertEqual(record['plan']['plan_sha256'], plan['plan_sha256'])
            changed = copy.deepcopy(suite)
            changed.pop('sha256')
            changed['cases'][0]['prompt'] = 'changed'
            with tempfile.TemporaryDirectory() as folder:
                path = Path(folder) / 'suite.json'
                path.write_text(json.dumps(changed), encoding='utf-8')
                with patch.object(plans, 'SUITE' if suite == legacy else 'ANIME_SUITE', path):
                    imported = self.client.post('/api/experiments/import-preview', json=plan)
            self.assertEqual(imported.status_code, 200, imported.text)
            self.assertEqual(imported.json()['plan_sha256'], plan['plan_sha256'])
            self.assertEqual(imported.json()['suite'], plan['suite'])
            self.assertTrue(any('保留原案例' in w for w in imported.json()['warnings']))

    def test_prompt_axes_change_only_one_field_with_precise_seed_and_model_snapshot(self):
        for image in (False, True):
            settings = self.settings(image)
            for axis, values in (
                ('prompt', ['adult traveler, red scarf', 'score_9, adult traveler, red scarf']),
                ('negative_prompt', ['', 'low quality, text, watermark']),
            ):
                response = self.preview(settings, axis, values)
                self.assertEqual(response.status_code, 200, response.text)
                plan = response.json()
                self.assertEqual(plan['schema_version'], 2)
                self.assertEqual(len(plan['model_snapshots']), 1)
                for row, value in zip(plan['variants'], values):
                    self.assertEqual(
                        row['settings'], settings | {axis: value, 'title': row['settings']['title']}
                    )

                # Simulate JS JSON serialization of integral floats before save/export.
                def js_numbers(value):
                    if isinstance(value, dict):
                        return {k: js_numbers(v) for k, v in value.items()}
                    if isinstance(value, list):
                        return [js_numbers(v) for v in value]
                    return int(value) if isinstance(value, float) and value.is_integer() else value

                saved = self.save(js_numbers(plan))
                self.assertEqual(saved['plan']['plan_sha256'], plan['plan_sha256'])
                self.assertEqual(
                    self.client.post('/api/experiments/document-export', json=plan).status_code, 200
                )
        self.assertEqual(self.client.get('/api/jobs').json(), [])

    def test_bad_selection_and_ambiguous_or_invalid_prompt_comparisons_never_write(self):
        settings = self.settings()
        before = self.db.read_bytes()
        for changes in (
            dict(suite_id='../../other', axis='cfg', values=[1, 2]),
            dict(suite_id='anime-illustration', case_ids=['chair'], axis='cfg', values=[1]),
            dict(axis='prompt', values=['one', 'two'], case_ids=['chair']),
            dict(axis='prompt', values=[' ']),
            dict(axis='prompt', values=[True]),
            dict(axis='negative_prompt', values=[1]),
            dict(axis='negative_prompt', values=['x' * 20001]),
            dict(axis='prompt', values=['a', 'a']),
        ):
            response = self.preview(settings, **changes)
            self.assertEqual(response.status_code, 422, response.text)
        self.assertEqual(self.client.get('/api/experiments/suite?suite_id=other').status_code, 422)
        self.assertEqual(self.db.read_bytes(), before)
