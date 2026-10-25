"""Fail-fast local/CI checks; use the interpreter from the active locked venv."""

import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def browser_stages(root, npm, *, batch_size=6):
    files = sorted((root / 'frontend/tests').glob('*.spec.ts'))
    if not files:
        raise ValueError('No browser test files found.')
    port = int(os.environ.get('ATELIER_TEST_PORT', '18765'))
    groups = [files[index : index + batch_size] for index in range(0, len(files), batch_size)]
    if not 1024 <= port <= 65535 - len(groups):
        raise ValueError('Browser fixture port range is invalid.')
    stages = []
    for index, group in enumerate(groups, 1):
        name = f'browser group {index}/{len(groups)}'
        evidence = root / 'runtime/quality'
        command = [
            npm,
            'run',
            'test:browser',
            '--',
            *['tests/' + path.name for path in group],
            '--output',
            str(evidence / 'browser-results' / f'group-{index}'),
        ]
        environment = dict(
            ATELIER_TEST_PORT=str(port + index - 1),
            ATELIER_BROWSER_REPORT_DIR=str(evidence / 'browser-report' / f'group-{index}'),
        )
        stages.append((name, command, root / 'frontend', environment))
    return stages


def run_checks(*, skip_browser=False, run=subprocess.run):
    npm = shutil.which('npm.cmd' if os.name == 'nt' else 'npm')
    if not npm:
        print('Node.js/npm is required.', file=sys.stderr)
        return 1
    stages = [
        ('style and static checks', [sys.executable, 'scripts/check_style.py'], ROOT),
        (
            'backend',
            [sys.executable, '-m', 'unittest', 'discover', '-s', 'backend', '-p', 'test_*.py'],
            ROOT,
        ),
        ('frontend build', [npm, 'run', 'build'], ROOT / 'frontend'),
        ('frontend contracts', [npm, 'test'], ROOT / 'frontend'),
    ]
    stages = [(name, command, cwd, {}) for name, command, cwd in stages]
    if not skip_browser:
        stages.extend(browser_stages(ROOT, npm))
    env = dict(os.environ, ATELIER_TEST_PYTHON=sys.executable)
    for name, command, cwd, overrides in stages:
        print(f'\nChecking {name}', flush=True)
        result = run(command, cwd=cwd, env=env | overrides)
        if result.returncode:
            print(f'FAILED: {name} (exit {result.returncode})', file=sys.stderr)
            return result.returncode if result.returncode > 0 else 1
    if skip_browser:
        print(
            'SKIPPED: browser explicitly disabled with --skip-browser; this is not a full quality pass.'
        )
    return 0


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        '--skip-browser', action='store_true', help='Explicitly run only backend/build/contracts'
    )
    args = parser.parse_args()
    try:
        raise SystemExit(run_checks(skip_browser=args.skip_browser))
    except (OSError, ValueError, KeyboardInterrupt) as exc:
        print(f'Quality checks interrupted: {exc}', file=sys.stderr)
        raise SystemExit(1)
