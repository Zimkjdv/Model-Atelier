import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from backend import training_environment as environment
from scripts import training_fixture


class EnvironmentTests(unittest.TestCase):
    def test_missing_runtime_is_not_reported_ready(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / 'training').mkdir()
            for name in ('environment.json', 'requirements-win-py312.lock.txt'):
                (root / 'training' / name).write_bytes(
                    (environment.ROOT / 'training' / name).read_bytes()
                )
            result = environment.check(root)
            self.assertFalse(result['ready'])
            self.assertIn('The isolated training Python is missing.', result['issues'])
            self.assertIn('The pinned trainer checkout is missing.', result['issues'])

    def test_existing_modified_trainer_is_not_reset_or_installed_over(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = environment.locations(root)['source']
            source.mkdir(parents=True)
            marker = source / 'local-change.txt'
            marker.write_text('Keep this change', encoding='utf-8')
            value = dict(
                python=list(__import__('sys').version_info[:2]), trainer=dict(revision='a' * 40)
            )
            outcome = type('Result', (), dict(returncode=0, stdout='local modification'))()
            with (
                patch.object(environment, 'profile', return_value=value),
                patch.object(environment, 'git', return_value=outcome),
                patch.object(environment, 'command') as command,
            ):
                with self.assertRaises(ValueError):
                    environment.install(root)
                command.assert_not_called()
            self.assertEqual(marker.read_text(encoding='utf-8'), 'Keep this change')

    def test_technical_fixture_has_disjoint_splits_and_does_not_overwrite(self):
        with tempfile.TemporaryDirectory() as temporary:
            target = training_fixture.create(Path(temporary) / 'technical')
            dataset = json.loads((target / 'dataset.json').read_text(encoding='utf-8'))
            self.assertEqual(
                [row['split'] for row in dataset['images']], ['train', 'validation', 'test']
            )
            self.assertEqual(len(list((target / 'bundle/train').glob('*.png'))), 1)
            with self.assertRaises(ValueError):
                training_fixture.create(target)
