"""Format/lint only the reviewed Q10 scope; check mode never rewrites sources."""

import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def run_checks(*, write=False, run=subprocess.run):
    scope = json.loads((ROOT / 'quality-scope.json').read_text(encoding='utf-8'))
    npm = shutil.which('npm.cmd' if sys.platform == 'win32' else 'npm')
    if not npm:
        print('Node.js/npm is required for scoped style checks.', file=sys.stderr)
        return 1
    stages = [
        (
            [
                sys.executable,
                '-m',
                'ruff',
                'format',
                *([] if write else ['--check']),
                *scope['python'],
            ],
            ROOT,
        ),
        ([sys.executable, '-m', 'ruff', 'check', *scope['python']], ROOT),
        ([npm, 'run', 'format' if write else 'format:check'], ROOT / 'frontend'),
        ([npm, 'run', 'lint'], ROOT / 'frontend'),
    ]
    for command, cwd in stages:
        result = run(command, cwd=cwd)
        if result.returncode:
            return result.returncode if result.returncode > 0 else 1
    return 0


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        '--write',
        action='store_true',
        help='Explicitly format the reviewed scope, without lint autofixes',
    )
    try:
        raise SystemExit(run_checks(write=parser.parse_args().write))
    except (OSError, ValueError) as exc:
        print(f'Style check failed: {exc}', file=sys.stderr)
        raise SystemExit(1)
