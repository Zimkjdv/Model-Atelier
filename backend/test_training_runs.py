import json
from pathlib import Path
import subprocess
import sys
import tomllib
from unittest.mock import patch

from backend import compute_lease, training_bundle, training_files, training_runs as runs
from backend.test_training_data import DatasetFixture


class TrainingRunTests(DatasetFixture):
    def setUp(self):
        super().setUp()
        self.checkpoint = self.root / 'base.safetensors'
        self.checkpoint.write_bytes(b'fixture base')
        metadata = json.loads(
            (runs.ROOT / 'models/animagine-xl-4.0-opt.json').read_text(encoding='utf-8')
        )
        metadata.update(
            size_bytes=self.checkpoint.stat().st_size, sha256=training_files.digest(self.checkpoint)
        )
        (self.root / 'models').mkdir()
        compute_lease.atomic_json(self.root / 'models/animagine-xl-4.0-opt.json', metadata)
        self.base.sha256 = metadata['sha256']
        self.base.size_bytes = metadata['size_bytes']
        self.dataset.base_model.sha256 = metadata['sha256']
        self.dataset.base_model.size_bytes = metadata['size_bytes']
        self.sealed = self.root / 'sealed'
        training_bundle.export(self.dataset, self.source, self.sealed, self.base)
        self.config = dict(
            label='Synthetic technical test',
            purpose='technical-smoke',
            bundle=str(self.sealed),
            checkpoint=str(self.checkpoint),
            resolution=512,
            max_steps=3,
            save_every_steps=1,
        )
        checker = patch.object(
            runs.environment,
            'check',
            return_value=dict(
                ready=True,
                issues=[],
                profile_sha256='a' * 64,
                dependencies_sha256='b' * 64,
                trainer_revision=training_bundle.TRAINER,
            ),
        )
        checker.start()
        self.addCleanup(checker.stop)

    def prepare(self, config=None, resume=None):
        return runs.prepare(config or self.config, root=self.root, resume=resume)

    def saved(self):
        result = self.prepare()
        folder = Path(result['directory'])
        state = folder / 'output/model-step00000001-state'
        state.mkdir()
        (state / 'optimizer.bin').write_bytes(b'optimizer fixture')
        compute_lease.atomic_json(state / 'train_state.json', dict(current_step=1, current_epoch=0))
        compute_lease.atomic_json(
            folder / 'checkpoints/step-1.json',
            dict(
                schema_version=1,
                run_id=result['run_id'],
                step=1,
                directory=state.name,
                manifest_sha256=result['manifest_sha256'],
                files=training_files.file_manifest(state),
            ),
        )
        compute_lease.atomic_json(
            folder / 'state.json', dict(status='stopped', manifest_sha256=result['manifest_sha256'])
        )
        return result, folder, state

    def test_frozen_work_contains_only_training_split_and_explicit_resolution(self):
        before = training_files.file_manifest(self.sealed)
        result = self.prepare()
        folder = Path(result['directory'])
        manifest = training_files.read_json(folder / 'manifest.json')
        config = tomllib.loads((folder / 'work/dataset.toml').read_text(encoding='utf-8'))
        self.assertEqual(config['datasets'][0]['resolution'], [512, 512])
        self.assertEqual(
            config['datasets'][0]['subsets'][0]['image_dir'], (folder / 'work/train').as_posix()
        )
        self.assertEqual(manifest['dataset']['train_count'], 1)
        self.assertEqual(len(list((folder / 'work/train').glob('*.png'))), 1)
        self.assertEqual(before, training_files.file_manifest(self.sealed))
        self.assertEqual(result['status'], 'prepared')
        self.assertTrue(result['resources_released'])

    def test_unpinned_base_and_arbitrary_trainer_flags_are_rejected(self):
        with self.assertRaises(ValueError):
            self.prepare(self.config | dict(extra_arguments=['--anything']))
        self.checkpoint.write_bytes(b'changed base')
        with self.assertRaises(ValueError):
            self.prepare()

    def test_tampered_bundle_and_frozen_manifest_are_detected(self):
        result = self.prepare()
        folder = Path(result['directory'])
        (folder / 'manifest.json').write_text('{}', encoding='utf-8')
        with self.assertRaises(ValueError):
            runs.inspect(result['run_id'], root=self.root)
        (self.sealed / 'train/img-0001.txt').write_text('changed', encoding='utf-8')
        with self.assertRaises(ValueError):
            self.prepare()

    def test_resume_copies_complete_state_to_new_attempt_and_preserves_old(self):
        original, folder, state = self.saved()
        before = training_files.file_manifest(folder)
        resumed = self.prepare(resume=dict(run_id=original['run_id'], checkpoint='step-1'))
        self.assertNotEqual(resumed['run_id'], original['run_id'])
        target = Path(resumed['directory'])
        self.assertEqual(
            training_files.file_manifest(target / 'resume'), training_files.file_manifest(state)
        )
        self.assertEqual(training_files.read_json(target / 'manifest.json')['resume']['step'], 1)
        self.assertEqual(before, training_files.file_manifest(folder))

    def test_resume_rejects_changes_missing_files_active_worker_and_finished_budget(self):
        original, folder, state = self.saved()
        reference = dict(run_id=original['run_id'], checkpoint='step-1')
        with self.assertRaises(ValueError):
            self.prepare(self.config | dict(max_steps=4), reference)
        with compute_lease.Reservation(self.root, 'training', original['run_id']):
            with self.assertRaises(ValueError):
                self.prepare(resume=reference)
        receipt_path = folder / 'checkpoints/step-1.json'
        receipt = training_files.read_json(receipt_path)
        compute_lease.atomic_json(receipt_path, receipt | dict(step=3))
        with self.assertRaises(ValueError):
            self.prepare(resume=reference)
        compute_lease.atomic_json(receipt_path, receipt)
        (state / 'optimizer.bin').unlink()
        with self.assertRaises(ValueError):
            self.prepare(resume=reference)

    def test_stop_is_explicit_idempotent_and_never_relaunches(self):
        result = self.prepare()
        folder = Path(result['directory'])
        with self.assertRaises(ValueError):
            runs.stop(result['run_id'], root=self.root)
        compute_lease.atomic_json(
            folder / 'state.json', dict(status='running', manifest_sha256=result['manifest_sha256'])
        )
        with compute_lease.Reservation(self.root, 'training', result['run_id']):
            for _ in range(2):
                self.assertTrue(runs.stop(result['run_id'], root=self.root)['stop_requested'])
        with self.assertRaises(ValueError):
            runs.stop(result['run_id'], root=self.root)
        with patch.object(subprocess, 'Popen') as process:
            with self.assertRaises(ValueError):
                runs.launch(result['run_id'], root=self.root)
            process.assert_not_called()

    def test_integrity_rejects_duplicate_keys_and_extra_state_files(self):
        path = self.root / 'duplicate.json'
        path.write_text('{"status":"ok","status":"changed"}', encoding='utf-8')
        with self.assertRaises(ValueError):
            training_files.read_json(path)
        expected = training_files.file_manifest(self.source)
        (self.source / 'unexpected').write_bytes(b'changed')
        with self.assertRaises(ValueError):
            training_files.verify_files(self.source, expected)

    def test_resumed_step_budget_counts_only_remaining_updates(self):
        manifest = dict(configuration=dict(max_steps=3), resume=dict(step=1))
        self.assertEqual(training_files.step_budget(manifest), (1, 2))
        manifest['resume'] = None
        self.assertEqual(training_files.step_budget(manifest), (0, 3))
        manifest['resume'] = dict(step=3)
        with self.assertRaises(ValueError):
            training_files.step_budget(manifest)

    def test_platform_training_controller_does_not_import_gpu_libraries(self):
        result = subprocess.run(
            [
                sys.executable,
                '-c',
                'import sys;from backend import training_runs;'
                'assert not any(n in sys.modules for n in ("torch","transformers","diffusers"))',
            ],
            cwd=runs.ROOT,
            capture_output=True,
            text=True,
            timeout=20,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
