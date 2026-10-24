"""Bounded metadata and complete file identities for training attempts/checkpoints."""

import hashlib
import json
from pathlib import Path


def digest(path):
    result = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(4 * 1024 * 1024), b''):
            result.update(block)
    return result.hexdigest()


def read_json(path):
    raw = Path(path).read_bytes()
    if len(raw) > 4 * 1024 * 1024:
        raise ValueError('Training metadata is too large.')

    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError('Duplicate training metadata key.')
            result[key] = value
        return result

    value = json.loads(raw, object_pairs_hook=unique)
    if not isinstance(value, dict):
        raise ValueError('Training metadata must be an object.')
    return value


def file_manifest(folder):
    folder = Path(folder).absolute()
    for part in (folder, *folder.parents):
        if part.is_symlink() or (hasattr(part, 'is_junction') and part.is_junction()):
            raise ValueError('Training files cannot be links.')
    folder = folder.resolve(strict=True)
    files, total = {}, 0
    for path in folder.rglob('*'):
        if path.is_symlink() or (hasattr(path, 'is_junction') and path.is_junction()):
            raise ValueError('Training files cannot be links.')
        if not path.is_file():
            continue
        size = path.stat().st_size
        total += size
        if len(files) >= 10000 or total > 4 * 1024**3:
            raise ValueError('Training files exceed the supported limits.')
        files[path.relative_to(folder).as_posix()] = dict(size_bytes=size, sha256=digest(path))
    if not files:
        raise ValueError('Training files are empty.')
    return files


def verify_files(folder, expected):
    if file_manifest(folder) != expected:
        raise ValueError('Training files are incomplete or changed.')


def step_budget(manifest):
    total = manifest['configuration']['max_steps']
    offset = manifest['resume']['step'] if manifest['resume'] else 0
    if type(total) is not int or type(offset) is not int or not 0 <= offset < total:
        raise ValueError('Invalid frozen training step budget.')
    return offset, total - offset
