"""Prevent misleading cross-machine ratios and mutation of historical jobs."""

import copy
import unittest

from backend import workflows
from scripts import compare_hardware as compare, verify_local_generation as base


def fixture():
    settings = base.settings('http://127.0.0.1:8188', 'pony-v6-xl.safetensors')
    workflow = workflows.build(settings)
    job = dict(
        id='original',
        prompt_id='original',
        engine_url=settings['engine_url'],
        status='completed',
        workflow=workflow,
        history=dict(
            status=dict(
                completed=True,
                status_str='success',
                messages=[
                    ['execution_start', dict(prompt_id='original', timestamp=1000)],
                    ['execution_success', dict(prompt_id='original', timestamp=21000)],
                ],
            )
        ),
    )
    report = dict(
        status='passed',
        job_id=job['id'],
        expected_engine=job['engine_url'],
        workflow=workflow,
        settings=settings,
        verified_artworks=[],
    )
    conditions = dict(
        model_sha256='a' * 64,
        model_dtype='float16',
        clip_dtype='float16',
        vae_dtype='bfloat16',
        cache_state='fresh-process',
        offload_policy='dynamic-vram-cpu',
        comfy_commit='pinned',
        torch_version='2.14.0+cu130',
        component_sha256=[],
    )
    return report, job, conditions


class HardwareComparisonTests(unittest.TestCase):
    def observation(self):
        report, job, conditions = fixture()
        return compare.observation(
            report,
            job,
            conditions=conditions,
            condition_sources={k: 'explicit evidence' for k in conditions},
        )

    def test_same_conditions_produce_ratio_and_keep_unknown_memory(self):
        left = self.observation()
        right = copy.deepcopy(left)
        right['metrics']['engine_execution_seconds'] = 10
        result = compare.compare(left, right)
        self.assertTrue(result['matched_conditions'])
        self.assertEqual(result['engine_time_ratio_left_over_right'], 2)
        self.assertIsNone(result['left_metrics']['task_vram_peak_bytes'])
        self.assertIsNone(result['left_metrics']['nvidia_whole_device_sampled_max_bytes'])

    def test_changed_precision_cache_model_or_components_cannot_get_ratio(self):
        for key in ('model_sha256', 'model_dtype', 'cache_state', 'component_sha256'):
            left = self.observation()
            right = copy.deepcopy(left)
            right['conditions'][key] = ['other'] if key == 'component_sha256' else 'other'
            with self.subTest(key=key):
                result = compare.compare(left, right)
                self.assertFalse(result['matched_conditions'])
                self.assertIsNone(result['engine_time_ratio_left_over_right'])

    def test_unknown_conditions_or_missing_source_cannot_get_ratio(self):
        for value in (None, '', 'unknown'):
            left = self.observation()
            right = copy.deepcopy(left)
            right['conditions']['cache_state'] = value
            self.assertIsNone(compare.compare(left, right)['engine_time_ratio_left_over_right'])
        right = self.observation()
        right['condition_sources']['model_dtype'] = ''
        self.assertFalse(compare.compare(self.observation(), right)['matched_conditions'])

    def test_higher_load_or_different_exact_seed_is_separate(self):
        for field, value in (('width', 1536), ('seed', '9007199254740994')):
            left = self.observation()
            right = copy.deepcopy(left)
            right['settings'][field] = value
            self.assertFalse(compare.compare(left, right)['matched_conditions'])
        right = self.observation()
        right['workflow']['4']['inputs']['batch_size'] = 2
        self.assertFalse(compare.compare(self.observation(), right)['matched_conditions'])

    def test_legacy_history_timing_does_not_backfill_job(self):
        report, job, conditions = fixture()
        original = copy.deepcopy(job)
        result = compare.observation(
            report,
            job,
            conditions=conditions,
            condition_sources={k: 'evidence' for k in conditions},
        )
        self.assertEqual(result['metrics']['engine_execution_seconds'], 20)
        self.assertEqual(job, original)
        self.assertNotIn('measurements', job)

    def test_wrong_workflow_or_lossy_seed_fails_admission(self):
        for change in ('workflow', 'seed'):
            report, job, conditions = fixture()
            if change == 'workflow':
                report['workflow'] = {'different': {}}
            else:
                report['settings']['seed'] = 9007199254740992
            with self.assertRaises(ValueError):
                compare.observation(
                    report,
                    job,
                    conditions=conditions,
                    condition_sources={k: 'evidence' for k in conditions},
                )

    def test_training_observations_never_mix_with_inference(self):
        right = self.observation()
        right['workload_kind'] = 'training'
        with self.assertRaises(ValueError):
            compare.compare(self.observation(), right)


if __name__ == '__main__':
    unittest.main()
