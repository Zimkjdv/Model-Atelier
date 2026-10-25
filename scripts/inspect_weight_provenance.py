"""Fingerprint a pinned safetensors file without importing GPU/model libraries.

Local bytes and publisher declarations are evidence, never automatic proof of
license applicability or a model's exact upstream revision/conversion history.
"""

import argparse
from collections import Counter
import hashlib
import json
import math
import os
from pathlib import Path
import struct

from scripts import install_model, install_pony
from scripts import verify_local_generation as reports

MAX_HEADER = 16 * 1024**2
CHUNK = 1024**2
DTYPE_BYTES = {
    'BOOL': 1,
    'U8': 1,
    'I8': 1,
    'F8_E4M3': 1,
    'F8_E5M2': 1,
    'I16': 2,
    'U16': 2,
    'F16': 2,
    'BF16': 2,
    'I32': 4,
    'U32': 4,
    'F32': 4,
    'I64': 8,
    'U64': 8,
    'F64': 8,
}
GROUPS = (
    ('diffusion_model', 'model.diffusion_model.'),
    ('clip_l', 'conditioner.embedders.0.'),
    ('clip_g', 'conditioner.embedders.1.'),
    ('vae', 'first_stage_model.'),
)


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('Duplicate safetensors header key')
        result[key] = value
    return result


def read_header(stream, size):
    prefix = stream.read(8)
    if len(prefix) != 8:
        raise ValueError('Truncated safetensors length')
    length = struct.unpack('<Q', prefix)[0]
    if not 0 < length <= min(MAX_HEADER, size - 8):
        raise ValueError('Safetensors header exceeds the supported bound')
    raw = stream.read(length)
    if not raw.startswith(b'{') or len(raw) != length:
        raise ValueError('Invalid safetensors header bytes')
    header = json.loads(raw.decode('utf-8'), object_pairs_hook=unique_object)
    if not isinstance(header, dict) or len(header) > 100001:
        raise ValueError('Invalid safetensors tensor count')
    metadata = header.pop('__metadata__', {})
    if not isinstance(metadata, dict) or any(
        not isinstance(k, str) or not isinstance(v, str) for k, v in metadata.items()
    ):
        raise ValueError('Safetensors metadata must map strings to strings')
    entries = []
    for name, value in header.items():
        if not isinstance(value, dict) or not isinstance(name, str) or len(name) > 2048:
            raise ValueError('Invalid tensor entry')
        dtype, shape, offsets = value.get('dtype'), value.get('shape'), value.get('data_offsets')
        if (
            not isinstance(dtype, str)
            or dtype not in DTYPE_BYTES
            or not isinstance(shape, list)
            or len(shape) > 16
            or any(type(d) is not int or not 0 <= d <= 2**40 for d in shape)
            or not isinstance(offsets, list)
            or len(offsets) != 2
            or any(type(d) is not int or d < 0 for d in offsets)
            or offsets[1] - offsets[0] != math.prod(shape) * DTYPE_BYTES[dtype]
            or offsets[1] > size - 8 - length
        ):
            raise ValueError('Invalid tensor dtype, shape or offsets')
        entries.append((offsets[0], offsets[1], name, dtype, shape))
    entries.sort()
    cursor = 0
    for start, end, *_ in entries:
        if start != cursor:
            raise ValueError('Tensor buffer has a gap or overlap')
        cursor = end
    if cursor != size - 8 - length:
        raise ValueError('Tensor buffer does not cover the complete file')
    return prefix + raw, metadata, entries


def component(name):
    return next((group for group, prefix in GROUPS if name.startswith(prefix)), 'other')


def inspect_file(path, expected_size, expected_sha256):
    path = Path(path)
    if path.is_symlink() or not path.is_file():
        raise ValueError('A regular local safetensors file is required')
    groups = {}
    with path.open('rb') as stream:
        before = os.fstat(stream.fileno())
        if before.st_size != expected_size:
            raise ValueError('Pinned weight size differs')
        raw, metadata, entries = read_header(stream, expected_size)
        full = hashlib.sha256(raw)
        for start, end, name, dtype, shape in entries:
            tensor, remaining = hashlib.sha256(), end - start
            while remaining:
                data = stream.read(min(CHUNK, remaining))
                if not data:
                    raise ValueError('Truncated tensor payload')
                full.update(data)
                tensor.update(data)
                remaining -= len(data)
            group = groups.setdefault(component(name), [])
            group.append(
                dict(
                    name=name,
                    dtype=dtype,
                    shape=shape,
                    size_bytes=end - start,
                    sha256=tensor.hexdigest(),
                )
            )
        after = os.fstat(stream.fileno())
        if (before.st_size, before.st_mtime_ns, before.st_ino) != (
            after.st_size,
            after.st_mtime_ns,
            after.st_ino,
        ) or full.hexdigest() != expected_sha256:
            raise ValueError('Pinned weight checksum differs or file changed during inspection')
    components = {}
    for key, tensors in groups.items():
        ordered = sorted(tensors, key=lambda t: t['name'])
        components[key] = dict(
            tensor_count=len(tensors),
            payload_bytes=sum(t['size_bytes'] for t in tensors),
            dtypes=dict(Counter(t['dtype'] for t in tensors)),
            fingerprint_sha256=hashlib.sha256(
                json.dumps(ordered, sort_keys=True, separators=(',', ':')).encode()
            ).hexdigest(),
            upstream_revision=None,
            upstream_license_verified=False,
        )
    return dict(
        schema_version=1,
        checked_at=reports.utc_now(),
        filename=path.name,
        size_bytes=expected_size,
        sha256=full.hexdigest(),
        header_bytes=len(raw) - 8,
        header_sha256=hashlib.sha256(raw[8:]).hexdigest(),
        metadata=metadata,
        components=components,
        tensor_count=len(entries),
        terms_verified=False,
        conversion_lineage_verified=False,
        scope='Exact local file/tensor fingerprints only; metadata is an unverified embedded '
        'declaration, and no upstream revision or legal applicability is inferred.',
    )


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model', choices=['pony-v6-xl'], required=True)
    parser.add_argument('--report', required=True)
    args = parser.parse_args(argv)
    target = reports.report_path(args.report)
    reports.reserve_report(target)
    try:
        manifest = install_model.manifest(args.model)
        weight = install_pony._paths(install_pony.WORKSPACE, manifest['filename'], create=False)[0]
        result = inspect_file(weight, manifest['size_bytes'], manifest['sha256'])
        result['model_id'] = manifest['id']
        result['source'] = manifest['source']
        reports.write_report(target, result)
    except Exception as exc:
        reports.write_report(target, dict(status='failed', error=str(exc)))
        raise
    print(
        json.dumps(dict(model=args.model, tensor_count=result['tensor_count'], report=str(target)))
    )
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
