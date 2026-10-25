"""Compare all pinned CLIP-L tensors to a candidate OpenAI revision on CPU.

Run with the managed ComfyUI Python (NumPy required), redirecting JSON stdout to
a new report. Only the candidate's header and contiguous text tensor range are
read over HTTPS; no model files are written and no GPU libraries are imported.
Numerical correspondence does not establish the publisher's historical recipe
or license applicability. This tool never promotes either verification flag.
"""

from contextlib import contextmanager
import hashlib
import io
import json
import os
from pathlib import Path
import struct
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

from scripts import inspect_weight_provenance as audit

ROOT = Path(__file__).resolve().parents[1]
REVISION = '32bd64288804d66eefd0ccbe215aa642df71cc41'
SOURCE_URL = (
    f'https://huggingface.co/openai/clip-vit-large-patch14/resolve/{REVISION}/model.safetensors'
)
SOURCE_SIZE = 1710540580
SOURCE_DECLARED_SHA256 = 'a2bf730a0c7debf160f7a6b50b3aaf3703e7e88ac73de7a314903141db026dcb'
MAX_RANGE = 512 * 1024**2


class HTTPSRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if urlsplit(newurl).scheme != 'https':
            raise ValueError('Candidate redirect must remain HTTPS')
        return super().redirect_request(req, fp, code, msg, headers, newurl)


@contextmanager
def open_range(start, end, *, opener=None, total=SOURCE_SIZE):
    if not 0 <= start <= end < total or end - start + 1 > MAX_RANGE:
        raise ValueError('Candidate range exceeds supported bounds')
    request = Request(
        SOURCE_URL,
        headers={'Range': f'bytes={start}-{end}', 'Accept-Encoding': 'identity'},
    )
    opener = opener or build_opener(HTTPSRedirect()).open
    with opener(request, timeout=60) as response:
        # Reject ignored ranges before reading any model body.
        if (
            response.status != 206
            or response.headers.get('Content-Range') != f'bytes {start}-{end}/{total}'
            or response.headers.get('Content-Encoding', 'identity') != 'identity'
            or (
                response.headers.get('Content-Length') is not None
                and response.headers['Content-Length'] != str(end - start + 1)
            )
        ):
            raise ValueError('Candidate server did not return the exact unencoded range')
        yield response
        if response.read(1):
            raise ValueError('Candidate range contains excess bytes')


def read_exact(stream, length):
    chunks, remaining = [], length
    while remaining:
        data = stream.read(min(audit.CHUNK, remaining))
        if not data:
            raise ValueError('Truncated candidate range or local tensor')
        chunks.append(data)
        remaining -= len(data)
    return b''.join(chunks)


def candidate_header(*, opener=None):
    with open_range(0, 7, opener=opener) as response:
        prefix = read_exact(response, 8)
    length = struct.unpack('<Q', prefix)[0]
    if not 0 < length <= audit.MAX_HEADER:
        raise ValueError('Candidate header exceeds supported bounds')
    with open_range(8, length + 7, opener=opener) as response:
        raw = prefix + read_exact(response, length)
    _, _, entries = audit.read_header(io.BytesIO(raw), SOURCE_SIZE)
    return raw, entries


def comparison_plan(source_entries, target_entries):
    source = {entry[2]: entry for entry in source_entries}
    target_names = {entry[2] for entry in target_entries}
    source_names = {name for name in source if name.startswith('text_model.')}
    if (
        not target_names
        or any(not name.startswith('text_model.') for name in target_names)
        or source_names - target_names != {'text_model.embeddings.position_ids'}
        or target_names - source_names
    ):
        raise ValueError('Candidate/target text tensor names differ beyond the position buffer')
    buffer = source['text_model.embeddings.position_ids']
    if buffer[3:] != ('I64', [1, 77]):
        raise ValueError('Unexpected candidate position buffer')
    selected = []
    for target in target_entries:
        upstream = source[target[2]]
        if upstream[3] != 'F32' or target[3] != 'F16' or upstream[4] != target[4]:
            raise ValueError('Candidate/target dtype or shape differs')
        selected.append((upstream, target))
    selected.sort(key=lambda pair: pair[0][0])
    if any(left[0][1] != right[0][0] for left, right in zip(selected, selected[1:])):
        raise ValueError('Candidate text tensors must occupy one contiguous range')
    if not 0 < selected[-1][0][1] - selected[0][0][0] <= MAX_RANGE:
        raise ValueError('Candidate text payload exceeds supported bounds')
    return selected


def compare_payload(remote, local, selected, target_base, convert):
    results, range_hash = [], hashlib.sha256()
    for upstream, target in selected:
        start, end, name, _, shape = upstream
        local.seek(target_base + target[0])
        source_hash, converted_hash, local_hash = (hashlib.sha256() for _ in range(3))
        remaining, equal = end - start, True
        while remaining:
            raw = read_exact(remote, min(audit.CHUNK, remaining))
            converted = convert(raw)
            if len(converted) != len(raw) // 2:
                raise ValueError('F32 to F16 conversion produced the wrong byte count')
            actual = read_exact(local, len(converted))
            equal = equal and converted == actual
            range_hash.update(raw)
            source_hash.update(raw)
            converted_hash.update(converted)
            local_hash.update(actual)
            remaining -= len(raw)
        results.append(
            dict(
                name=name,
                shape=shape,
                source_f32_sha256=source_hash.hexdigest(),
                converted_f16_sha256=converted_hash.hexdigest(),
                local_f16_sha256=local_hash.hexdigest(),
                bitwise_equal=equal,
            )
        )
    return dict(
        tensors=results,
        tensor_count=len(results),
        all_tensors_bitwise_equal=all(row['bitwise_equal'] for row in results),
        source_payload_range_sha256=range_hash.hexdigest(),
    )


def compare_candidate(path, size, digest, convert, *, opener=None):
    initial = Path(path).stat()
    identity = audit.inspect_file(path, size, digest, standalone_component='clip_l')
    with Path(path).open('rb') as local:
        before = os.fstat(local.fileno())
        if (initial.st_size, initial.st_mtime_ns, initial.st_ino) != (
            before.st_size,
            before.st_mtime_ns,
            before.st_ino,
        ):
            raise ValueError('Local weight changed since identity inspection')
        local_raw, _, targets = audit.read_header(local, size)
        source_raw, sources = candidate_header(opener=opener)
        selected = comparison_plan(sources, targets)
        start = len(source_raw) + selected[0][0][0]
        end = len(source_raw) + selected[-1][0][1] - 1
        with open_range(start, end, opener=opener) as remote:
            result = compare_payload(remote, local, selected, len(local_raw), convert)
        after = os.fstat(local.fileno())
        if (before.st_size, before.st_mtime_ns, before.st_ino) != (
            after.st_size,
            after.st_mtime_ns,
            after.st_ino,
        ) or identity['header_sha256'] != hashlib.sha256(local_raw[8:]).hexdigest():
            raise ValueError('Local weight changed during candidate comparison')
    return dict(
        schema_version=1,
        checked_at=identity['checked_at'],
        local_identity=identity,
        candidate=dict(
            repository='openai/clip-vit-large-patch14',
            revision=REVISION,
            filename='model.safetensors',
            url=SOURCE_URL,
            size_bytes=SOURCE_SIZE,
            declared_full_file_sha256=SOURCE_DECLARED_SHA256,
            full_file_sha256_verified=False,
            header_sha256=hashlib.sha256(source_raw[8:]).hexdigest(),
            payload_http_range=[start, end],
            payload_read_bytes=end - start + 1,
            excluded_text_buffer='text_model.embeddings.position_ids',
        ),
        conversion='NumPy little-endian F32 -> F16 astype; compare every target byte',
        comparison=result,
        historical_publisher_recipe_verified=False,
        terms_verified=False,
        conversion_lineage_verified=False,
        scope='Candidate numerical correspondence only. No historical input revision, '
        'publisher conversion tool or applicable license is inferred.',
    )


def main():
    import numpy as np

    plan = json.loads((ROOT / 'models/flux1-schnell-plan.json').read_text(encoding='utf-8'))
    row = next(row for row in plan['components'] if row['role'] == 'clip_l')
    path = ROOT / 'runtime/ComfyUI/models/text_encoders' / row['filename']
    result = compare_candidate(
        path,
        row['size_bytes'],
        row['sha256'],
        lambda raw: np.frombuffer(raw, dtype='<f4').astype('<f2').tobytes(),
    )
    result['numpy_version'] = np.__version__
    print(json.dumps(result, ensure_ascii=True, indent=2))
    return 0 if result['comparison']['all_tensors_bitwise_equal'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
