"""Pinned, isolated SDXL trainer installation and read-only verification."""

import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import urllib.request

from backend.compute_lease import atomic_json
from backend.training_files import digest

ROOT = Path(__file__).resolve().parents[1]


def locations(root=ROOT):
    root = Path(root).resolve()
    base = root / 'runtime' / 'training'
    return dict(
        root=root,
        base=base,
        source=base / 'sd-scripts',
        python=base / '.venv' / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python'),
        tokenizers=base / 'tokenizers',
        profile=root / 'training/environment.json',
        lock=root / 'training/requirements-win-py312.lock.txt',
    )


def profile(root=ROOT):
    return json.loads(locations(root)['profile'].read_text(encoding='utf-8'))


def command(arguments, **options):
    return subprocess.run(
        [str(item) for item in arguments],
        capture_output=True,
        text=True,
        encoding='utf-8',
        errors='replace',
        timeout=options.pop('timeout', 60),
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0,
        env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1', GIT_OPTIONAL_LOCKS='0'),
        **options,
    )


def git(source, *arguments):
    return command(['git', '-c', 'safe.directory=' + source.as_posix(), '-C', source, *arguments])


def packages(root=ROOT):
    expected = {}
    for line in locations(root)['lock'].read_text(encoding='utf-8').splitlines():
        if not line or line.startswith(('#', '--')):
            continue
        name, version = line.split('==')
        expected[re.sub(r'[-_.]+', '-', name).lower()] = version
    return expected


def check(root=ROOT):
    paths, value, issues = locations(root), profile(root), []
    snapshot = dict(
        ready=False,
        profile=value['id'],
        profile_sha256=digest(paths['profile']),
        dependencies_sha256=digest(paths['lock']),
        trainer_revision=value['trainer']['revision'],
        python_path=str(paths['python']),
        issues=issues,
    )
    if os.name != 'nt':
        issues.append('This profile is verified only on Windows x64 / Python 3.12.')
    if not paths['python'].is_file():
        issues.append('The isolated training Python is missing.')
    else:
        probe = command(
            [
                paths['python'],
                '-I',
                '-c',
                'import importlib.metadata as m,json,sys;print(json.dumps(dict('
                'python=list(sys.version_info[:2]),prefix=sys.prefix,packages={'
                'd.metadata["Name"]:d.version for d in m.distributions()})))',
            ]
        )
        try:
            actual = json.loads(probe.stdout)
            observed = {
                re.sub(r'[-_.]+', '-', name).lower(): version
                for name, version in actual['packages'].items()
                if name.lower() != 'library'
            }
            if (
                probe.returncode
                or actual['python'] != value['python']
                or observed != packages(root)
            ):
                raise ValueError()
            if Path(actual['prefix']).resolve() != paths['python'].parents[1].resolve():
                raise ValueError()
            snapshot['packages'] = observed
        except (ValueError, KeyError, TypeError):
            issues.append(
                'The isolated interpreter or dependencies differ from the pinned profile.'
            )
    if not (paths['source'] / '.git').is_dir():
        issues.append('The pinned trainer checkout is missing.')
    else:
        revision = git(paths['source'], 'rev-parse', 'HEAD')
        dirty = git(paths['source'], 'status', '--porcelain', '--untracked-files=normal')
        if (
            revision.returncode
            or revision.stdout.strip() != value['trainer']['revision']
            or dirty.returncode
            or dirty.stdout.strip()
        ):
            issues.append('The trainer checkout differs from the pinned clean source.')
    for tokenizer in value['tokenizers']:
        folder = paths['tokenizers'] / tokenizer['repository'].replace('/', '_')
        for name, identity in tokenizer['files'].items():
            path = folder / name
            if (
                path.is_symlink()
                or not path.is_file()
                or path.stat().st_size != identity['size_bytes']
                or digest(path) != identity['sha256']
            ):
                issues.append('Tokenizer cache differs: ' + tokenizer['repository'] + '/' + name)
    snapshot['ready'] = not issues
    return snapshot


def install(root=ROOT):
    paths, value = locations(root), profile(root)
    if os.name != 'nt' or list(sys.version_info[:2]) != value['python']:
        raise ValueError('Use Windows x64 / Python 3.12 for this profile.')
    for target in (paths['base'], paths['source'], paths['python'].parents[1], paths['tokenizers']):
        if target.is_symlink() or (hasattr(target, 'is_junction') and target.is_junction()):
            raise ValueError('Training environment paths cannot be links.')
    paths['base'].mkdir(parents=True, exist_ok=True)
    if not paths['source'].exists():
        result = command(
            [
                'git',
                'clone',
                '--no-checkout',
                '--filter=blob:none',
                value['trainer']['repository'],
                paths['source'],
            ],
            timeout=180,
        )
        if result.returncode:
            raise ValueError('Could not fetch the pinned trainer source.')
        result = git(paths['source'], 'checkout', '--detach', value['trainer']['revision'])
        if result.returncode:
            raise ValueError('Could not select the pinned trainer source.')
    else:
        revision = git(paths['source'], 'rev-parse', 'HEAD')
        dirty = git(paths['source'], 'status', '--porcelain', '--untracked-files=normal')
        if (
            revision.returncode
            or revision.stdout.strip() != value['trainer']['revision']
            or dirty.returncode
            or dirty.stdout.strip()
        ):
            raise ValueError('Existing trainer source differs; it was not reset or overwritten.')
    if not paths['python'].exists():
        result = command([sys.executable, '-m', 'venv', paths['python'].parents[1]], timeout=90)
        if result.returncode:
            raise ValueError('Could not create the isolated training environment.')
    for arguments, cwd in [
        (
            ['-m', 'pip', 'install', '--disable-pip-version-check', '-r', paths['lock']],
            paths['root'],
        ),
        (
            [
                '-m',
                'pip',
                'install',
                '--disable-pip-version-check',
                '--no-deps',
                '--no-build-isolation',
                '-e',
                '.',
            ],
            paths['source'],
        ),
        (['-m', 'pip', 'check'], paths['root']),
    ]:
        result = command([paths['python'], *arguments], cwd=cwd, timeout=1800)
        if result.returncode:
            raise ValueError('Training dependency installation failed: ' + result.stderr[-1200:])
    for tokenizer in value['tokenizers']:
        folder = paths['tokenizers'] / tokenizer['repository'].replace('/', '_')
        folder.mkdir(parents=True, exist_ok=True)
        for name, identity in tokenizer['files'].items():
            target = folder / name
            if target.exists():
                if target.is_symlink() or digest(target) != identity['sha256']:
                    raise ValueError('Existing tokenizer cache differs; it was not overwritten.')
                continue
            url = f'https://huggingface.co/{tokenizer["repository"]}/resolve/{tokenizer["revision"]}/{name}'
            with urllib.request.urlopen(url, timeout=60) as response:
                raw = response.read(identity['size_bytes'] + 1)
            if (
                len(raw) != identity['size_bytes']
                or hashlib.sha256(raw).hexdigest() != identity['sha256']
            ):
                raise ValueError('Tokenizer size or hash differs from the pinned source.')
            with target.open('xb') as stream:
                stream.write(raw)
    result = check(root)
    if not result['ready']:
        raise ValueError('; '.join(result['issues']))
    atomic_json(paths['base'] / 'environment-receipt.json', result)
    return result
