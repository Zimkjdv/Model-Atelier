"""Resource scopes, completion admission and unknowns for training evidence."""

import copy
import unittest

from scripts import hardware_resources as resources


def fixture():
    manifest = dict(
        run_id='run',
        configuration=dict(max_steps=3, resolution=1024),
        dataset=dict(train_count=1),
        base=dict(sha256='a' * 64),
        environment=dict(trainer_revision='pinned'),
        resume=None,
    )
    inspection = dict(
        run_id='run',
        status='completed',
        resources_released=True,
        manifest_sha256='b' * 64,
        state=dict(steps_completed=3),
    )
    metrics = dict(
        elapsed_seconds=42,
        samples=[
            dict(rss_bytes=100, whole_gpu_used_bytes=300),
            dict(rss_bytes=200, whole_gpu_used_bytes=None),
        ],
    )
    artifacts = dict(
        run_id='run',
        manifest_sha256='b' * 64,
        files={'model.safetensors': dict(sha256='c' * 64, size_bytes=100)},
    )
    return manifest, inspection, metrics, artifacts, {}


class HardwareResourceTests(unittest.TestCase):
    def test_unknown_allocator_and_working_set_are_not_inferred_from_device(self):
        values = fixture()
        original = copy.deepcopy(values)
        row = resources.training_record(*values)
        self.assertEqual(row['workload_kind'], 'training')
        self.assertEqual(row['observed_max_rss_bytes'], 200)
        self.assertEqual(row['observed_max_whole_gpu_used_bytes'], 300)
        self.assertIsNone(row['torch_peak_allocated_bytes'])
        self.assertIsNone(row['observed_max_process_peak_working_set_bytes'])
        self.assertIsNone(row['task_vram_peak_bytes'])
        self.assertEqual(values, original)

    def test_empty_or_invalid_samples_stay_unknown_but_real_zero_is_kept(self):
        self.assertIsNone(resources.sampled_max([], 'rss_bytes'))
        self.assertIsNone(
            resources.sampled_max([{'rss_bytes': True}, {'rss_bytes': -1}], 'rss_bytes')
        )
        self.assertEqual(
            resources.sampled_max([{'rss_bytes': None}, {'rss_bytes': 0}], 'rss_bytes'), 0
        )

    def test_running_worker_or_unreached_steps_cannot_be_promoted(self):
        for change in ('status', 'resources_released', 'steps_completed'):
            values = fixture()
            if change == 'status':
                values[1]['status'] = 'running'
            elif change == 'resources_released':
                values[1][change] = False
            else:
                values[1]['state'][change] = 2
            with self.subTest(change=change), self.assertRaises(ValueError):
                resources.training_record(*values)

    def test_artifact_receipt_from_another_manifest_is_rejected(self):
        values = fixture()
        values[3]['manifest_sha256'] = 'd' * 64
        with self.assertRaises(ValueError):
            resources.training_record(*values)


if __name__ == '__main__':
    unittest.main()
