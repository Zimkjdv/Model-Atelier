"""CPU-only candidate comparison: bounded ranges and complete byte equality."""

import hashlib
import io
import json
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

from scripts import compare_clip_provenance as compare


class Response(io.BytesIO):
    def __init__(self, data, *, status=206, headers=None):
        super().__init__(data)
        self.status = status
        self.headers = headers or {'Content-Range': 'bytes 0-3/100'}
        self.read_calls = 0

    def read(self, length=-1):
        self.read_calls += 1
        return super().read(length)


class ClipProvenanceTests(unittest.TestCase):
    def test_ignored_range_wrong_total_or_encoded_response_is_not_read(self):
        for response in (
            Response(b'x' * 4, status=200),
            Response(b'x' * 4, headers={'Content-Range': 'bytes 0-3/99'}),
            Response(b'x' * 4, headers={'Content-Range': 'bytes 1-4/100'}),
            Response(
                b'x' * 4, headers={'Content-Range': 'bytes 0-3/100', 'Content-Encoding': 'gzip'}
            ),
            Response(b'x' * 4, headers={'Content-Range': 'bytes 0-3/100', 'Content-Length': '100'}),
        ):
            with self.subTest(headers=response.headers), self.assertRaises(ValueError):
                with compare.open_range(0, 3, total=100, opener=lambda *a, **kw: response):
                    self.fail('Unverified response accepted')
            self.assertEqual(response.read_calls, 0)

    def test_range_bounds_are_rejected_before_network(self):
        for start, end, total in (
            (-1, 1, 100),
            (4, 3, 100),
            (0, 100, 100),
            (0, compare.MAX_RANGE, compare.MAX_RANGE + 1),
        ):
            with self.subTest(start=start, end=end), self.assertRaises(ValueError):
                with compare.open_range(start, end, total=total, opener=self.fail):
                    self.fail('Invalid bounds accepted')

    def test_exact_range_and_truncation_or_excess_are_distinguished(self):
        response = Response(b'abcd')
        requests = []

        def opener(request, **kwargs):
            requests.append(request)
            return response

        with compare.open_range(0, 3, total=100, opener=opener) as stream:
            self.assertEqual(compare.read_exact(stream, 4), b'abcd')
        self.assertEqual(requests[0].get_header('Range'), 'bytes=0-3')
        self.assertEqual(requests[0].get_header('Accept-encoding'), 'identity')
        for data in (b'abc', b'abcde'):
            response = Response(data)
            with self.assertRaises(ValueError):
                with compare.open_range(
                    0, 3, total=100, opener=lambda *a, **kw: response
                ) as stream:
                    compare.read_exact(stream, 4)

    def entries(self):
        buffer = (0, 616, 'text_model.embeddings.position_ids', 'I64', [1, 77])
        weight = (616, 624, 'text_model.weight', 'F32', [2])
        target = (0, 4, 'text_model.weight', 'F16', [2])
        return buffer, weight, target

    def test_plan_requires_complete_names_shapes_and_contiguous_f32_source(self):
        buffer, weight, target = self.entries()
        self.assertEqual(compare.comparison_plan([buffer, weight], [target]), [(weight, target)])
        cases = [
            ([weight], [target]),
            ([buffer, weight, (624, 628, 'text_model.extra', 'F32', [1])], [target]),
            ([buffer, weight], [(0, 4, 'text_model.other', 'F16', [2])]),
            ([buffer, weight], [(0, 4, 'text_model.weight', 'F16', [1, 2])]),
            ([buffer, (616, 624, 'text_model.weight', 'BF16', [2])], [target]),
            (
                [buffer, weight, (628, 632, 'text_model.next', 'F32', [1])],
                [target, (4, 6, 'text_model.next', 'F16', [1])],
            ),
        ]
        for sources, targets in cases:
            with self.subTest(targets=targets), self.assertRaises(ValueError):
                compare.comparison_plan(sources, targets)

    def test_every_tensor_byte_is_compared_and_digested(self):
        _, weight, target = self.entries()
        raw = struct.pack('<ff', 1.0, -2.0)
        half = struct.pack('<ee', 1.0, -2.0)

        def convert(data):
            return struct.pack('<ee', *struct.unpack('<ff', data))

        for local, expected in ((half, True), (half[:-1] + b'\0', False)):
            with self.subTest(expected=expected):
                result = compare.compare_payload(
                    io.BytesIO(raw), io.BytesIO(b'HEAD' + local), [(weight, target)], 4, convert
                )
                self.assertEqual(result['all_tensors_bitwise_equal'], expected)
                self.assertEqual(
                    result['source_payload_range_sha256'], hashlib.sha256(raw).hexdigest()
                )
                self.assertEqual(
                    result['tensors'][0]['local_f16_sha256'], hashlib.sha256(local).hexdigest()
                )
        with self.assertRaises(ValueError):
            compare.compare_payload(
                io.BytesIO(raw[:-1]), io.BytesIO(half), [(weight, target)], 0, convert
            )
        with self.assertRaises(ValueError):
            compare.compare_payload(
                io.BytesIO(raw), io.BytesIO(half), [(weight, target)], 0, lambda b: b
            )

    def test_http_redirect_cannot_downgrade_https(self):
        with self.assertRaisesRegex(ValueError, 'HTTPS'):
            compare.HTTPSRedirect().redirect_request(None, None, 302, '', {}, 'http://example.com')

    def test_complete_candidate_match_never_promotes_lineage_or_license(self):
        buffer, weight, target = self.entries()
        payload = struct.pack('<ee', 1.0, -2.0)
        raw = json.dumps({target[2]: dict(dtype='F16', shape=[2], data_offsets=[0, 4])}).encode()
        content = struct.pack('<Q', len(raw)) + raw + payload
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'clip.safetensors'
            path.write_bytes(content)
            digest = hashlib.sha256(content).hexdigest()
            with (
                mock.patch.object(
                    compare, 'candidate_header', return_value=(b'HEADER', [buffer, weight])
                ),
                mock.patch.object(
                    compare, 'open_range', return_value=io.BytesIO(struct.pack('<ff', 1.0, -2.0))
                ),
            ):
                result = compare.compare_candidate(path, len(content), digest, lambda raw: payload)
            self.assertTrue(result['comparison']['all_tensors_bitwise_equal'])
            for flag in (
                'historical_publisher_recipe_verified',
                'terms_verified',
                'conversion_lineage_verified',
            ):
                self.assertFalse(result[flag])
            self.assertFalse(result['candidate']['full_file_sha256_verified'])
            self.assertEqual(path.read_bytes(), content)
            with mock.patch.object(compare, 'candidate_header') as network:
                with self.assertRaises(ValueError):
                    compare.compare_candidate(path, len(content), '0' * 64, lambda raw: payload)
                network.assert_not_called()

    def test_import_does_not_require_numpy_or_load_gpu_libraries(self):
        result = subprocess.run(
            [
                sys.executable,
                '-c',
                'import sys;from scripts import compare_clip_provenance;'
                'assert not any(n in sys.modules for n in ("torch","numpy","transformers","safetensors"))',
            ],
            cwd=Path(__file__).resolve().parents[1],
            capture_output=True,
            timeout=20,
        )
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == '__main__':
    unittest.main()
