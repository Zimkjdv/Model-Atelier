"""Bounded local tensor audit and non-inference of upstream rights."""

import hashlib
import json
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest

from scripts import inspect_weight_provenance as audit


class WeightProvenanceTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.path = Path(self.temporary.name) / 'fixture.safetensors'

    def file(self, header, data=b'\0\0'):
        raw = header if isinstance(header, bytes) else json.dumps(header).encode()
        content = struct.pack('<Q', len(raw)) + raw + data
        self.path.write_bytes(content)
        return len(content), hashlib.sha256(content).hexdigest()

    def inspect(self, header, data=b'\0\0'):
        return audit.inspect_file(self.path, *self.file(header, data))

    def test_metadata_cannot_promote_source_revision_or_license(self):
        header = {
            'conditioner.embedders.0.weight': dict(dtype='F16', shape=[1], data_offsets=[0, 2]),
            '__metadata__': dict(license='Apache-2.0', upstream_revision='f' * 40),
        }
        before = self.file(header)
        original = self.path.read_bytes()
        value = audit.inspect_file(self.path, *before)
        self.assertEqual(value['tensor_count'], 1)
        self.assertEqual(value['components']['clip_l']['payload_bytes'], 2)
        self.assertIsNone(value['components']['clip_l']['upstream_revision'])
        self.assertFalse(value['components']['clip_l']['upstream_license_verified'])
        self.assertFalse(value['terms_verified'])
        self.assertFalse(value['conversion_lineage_verified'])
        self.assertEqual(self.path.read_bytes(), original)

    def test_component_fingerprint_is_independent_of_header_order_and_metadata(self):
        tensor = dict(dtype='F16', shape=[1], data_offsets=[0, 2])
        first = self.inspect({'model.diffusion_model.x': tensor})
        second = self.inspect(
            {'__metadata__': {'title': 'another title'}, 'model.diffusion_model.x': tensor}
        )
        self.assertNotEqual(first['sha256'], second['sha256'])
        self.assertEqual(first['components'], second['components'])
        third = self.inspect({'model.diffusion_model.x': tensor}, b'\1\0')
        self.assertNotEqual(first['components'], third['components'])

    def test_wrong_whole_weight_identity_is_rejected(self):
        size, digest = self.file({'x': dict(dtype='F16', shape=[1], data_offsets=[0, 2])})
        for wrong_size, wrong_digest in ((size + 1, digest), (size, '0' * 64)):
            with self.assertRaises(ValueError):
                audit.inspect_file(self.path, wrong_size, wrong_digest)

    def test_duplicate_json_keys_are_rejected(self):
        with self.assertRaisesRegex(ValueError, 'Duplicate'):
            self.inspect(b'{"x":{"dtype":"F16","shape":[1],"data_offsets":[0,2]},"x":{}}')

    def test_gap_overlap_bad_shape_and_invalid_metadata_are_rejected(self):
        cases = [
            ({'x': dict(dtype='F16', shape=[1], data_offsets=[1, 3])}, b'\0' * 3),
            (
                {
                    'x': dict(dtype='F16', shape=[1], data_offsets=[0, 2]),
                    'y': dict(dtype='F16', shape=[1], data_offsets=[1, 3]),
                },
                b'\0' * 3,
            ),
            ({'x': dict(dtype='F16', shape=[True], data_offsets=[0, 2])}, b'\0' * 2),
            ({'x': dict(dtype='F16', shape=[2], data_offsets=[0, 2])}, b'\0' * 2),
            (
                {
                    '__metadata__': {'revision': 1},
                    'x': dict(dtype='F16', shape=[1], data_offsets=[0, 2]),
                },
                b'\0' * 2,
            ),
        ]
        for header, data in cases:
            with self.subTest(header=header), self.assertRaises(ValueError):
                self.inspect(header, data)

    def test_oversize_or_truncated_header_is_rejected_before_allocation(self):
        for content in (b'\0', struct.pack('<Q', audit.MAX_HEADER + 1) + b'{}'):
            self.path.write_bytes(content)
            with self.assertRaises(ValueError):
                audit.inspect_file(self.path, len(content), hashlib.sha256(content).hexdigest())

    def test_empty_and_scalar_tensors_are_preserved(self):
        value = self.inspect(
            {
                'empty': dict(dtype='F16', shape=[0], data_offsets=[0, 0]),
                'scalar': dict(dtype='F16', shape=[], data_offsets=[0, 2]),
            }
        )
        self.assertEqual(value['tensor_count'], 2)

    def test_standalone_scaled_format_does_not_imply_conversion_recipe(self):
        header = {
            'encoder.block.0.scale_weight': dict(dtype='F32', shape=[], data_offsets=[0, 4]),
            'scaled_fp8': dict(dtype='F8_E4M3', shape=[0], data_offsets=[4, 4]),
        }
        value = audit.inspect_file(
            self.path, *self.file(header, b'\0' * 4), standalone_component='t5xxl'
        )
        self.assertEqual(value['components']['t5xxl']['tensor_count'], 2)
        observations = value['format_observations']
        self.assertEqual(observations['scalar_f32_scale_weight_count'], 1)
        self.assertEqual(observations['scaled_fp8_marker'][0]['size_bytes'], 0)
        self.assertFalse(observations['conversion_algorithm_inferred'])
        self.assertFalse(value['conversion_lineage_verified'])

    def test_import_does_not_load_gpu_libraries(self):
        result = subprocess.run(
            [
                sys.executable,
                '-c',
                'import sys;from scripts import inspect_weight_provenance;'
                'assert not any(n in sys.modules for n in ("torch","transformers","safetensors"))',
            ],
            cwd=Path(__file__).resolve().parents[1],
            capture_output=True,
            timeout=20,
        )
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == '__main__':
    unittest.main()
