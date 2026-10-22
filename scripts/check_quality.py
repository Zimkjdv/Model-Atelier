"""Fail-fast local/CI checks; use the interpreter from the active locked venv."""
import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def run_checks(*, skip_browser=False, run=subprocess.run):
    npm = shutil.which('npm.cmd' if os.name == 'nt' else 'npm')
    if not npm:
        print('Node.js/npm is required.', file=sys.stderr)
        return 1
    stages = [
        ('backend', [sys.executable, '-m', 'unittest', 'discover', '-s', 'backend', '-p', 'test_*.py'], ROOT),
        ('frontend build', [npm, 'run', 'build'], ROOT / 'frontend'),
        ('frontend contracts', [npm, 'test'], ROOT / 'frontend'),
    ]
    if not skip_browser:
        stages.append(('browser', [npm, 'run', 'test:browser'], ROOT / 'frontend'))
    env = dict(os.environ, ATELIER_TEST_PYTHON=sys.executable)
    for name, command, cwd in stages:
        print(f'\nChecking {name}', flush=True)
        result = run(command, cwd=cwd, env=env)
        if result.returncode:
            print(f'FAILED: {name} (exit {result.returncode})', file=sys.stderr)
            return result.returncode if result.returncode > 0 else 1
    if skip_browser:
        print('SKIPPED: browser explicitly disabled with --skip-browser; this is not a full quality pass.')
    return 0


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--skip-browser', action='store_true', help='Explicitly run only backend/build/contracts')
    args = parser.parse_args()
    try:
        raise SystemExit(run_checks(skip_browser=args.skip_browser))
    except (OSError, KeyboardInterrupt) as exc:
        print(f'Quality checks interrupted: {exc}', file=sys.stderr)
        raise SystemExit(1)
