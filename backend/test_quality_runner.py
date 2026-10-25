from types import SimpleNamespace
from contextlib import redirect_stderr, redirect_stdout
import io
import unittest
from unittest.mock import patch

from scripts.check_quality import ROOT, browser_stages, run_checks


class QualityRunnerTests(unittest.TestCase):
    @patch('scripts.check_quality.shutil.which', return_value='npm')
    def test_every_stage_failure_is_nonzero_and_stops_subsequent_stages(self, _):
        for failure in range(4 + len(browser_stages(ROOT, 'npm'))):
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

    def test_browser_batches_cover_every_file_once_with_distinct_ports_and_evidence(self):
        stages = browser_stages(ROOT, 'npm')
        files = [
            argument
            for _, command, _, _ in stages
            for argument in command
            if argument.endswith('.spec.ts')
        ]
        expected = [
            'tests/' + path.name for path in sorted((ROOT / 'frontend/tests').glob('*.spec.ts'))
        ]
        self.assertEqual(files, expected)
        self.assertEqual(len(files), len(set(files)))
        self.assertGreater(len(stages), 1)
        self.assertEqual(len(stages), len({env['ATELIER_TEST_PORT'] for *_, env in stages}))
        self.assertEqual(
            len(stages), len({env['ATELIER_BROWSER_REPORT_DIR'] for *_, env in stages})
        )
        for _, command, cwd, _ in stages:
            self.assertEqual(cwd, ROOT / 'frontend')
            self.assertLessEqual(sum(arg.endswith('.spec.ts') for arg in command), 6)
            self.assertIn('--output', command)

    @patch('scripts.check_quality.shutil.which', return_value='npm')
    def test_later_batch_failure_stops_without_retry_or_discarding_prior_evidence(self, _):
        seen = []

        def run(command, **options):
            seen.append((command, options))
            return SimpleNamespace(returncode=9 if len(seen) == 6 else 0)

        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            self.assertEqual(run_checks(run=run), 9)
        self.assertEqual(len(seen), 6)
        self.assertNotEqual(
            seen[4][1]['env']['ATELIER_TEST_PORT'], seen[5][1]['env']['ATELIER_TEST_PORT']
        )
