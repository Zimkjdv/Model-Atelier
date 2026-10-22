from types import SimpleNamespace
from contextlib import redirect_stderr, redirect_stdout
import io
import unittest
from unittest.mock import patch

from scripts.check_quality import run_checks


class QualityRunnerTests(unittest.TestCase):
    @patch('scripts.check_quality.shutil.which', return_value='npm')
    def test_every_stage_failure_is_nonzero_and_stops_subsequent_stages(self, _):
        for failure in range(4):
            seen = []
            def run(command, **options):
                seen.append((command, options))
                return SimpleNamespace(returncode=7 if len(seen) == failure + 1 else 0)
            output = io.StringIO()
            with redirect_stdout(output), redirect_stderr(output):
                self.assertEqual(run_checks(run=run), 7)
            self.assertIn('FAILED:', output.getvalue())
            self.assertEqual(len(seen), failure + 1)
            self.assertTrue(all('ATELIER_TEST_PYTHON' in options['env'] for _, options in seen))

    @patch('scripts.check_quality.shutil.which', return_value=None)
    def test_missing_npm_fails(self, _):
        with redirect_stderr(io.StringIO()):
            self.assertEqual(run_checks(), 1)
