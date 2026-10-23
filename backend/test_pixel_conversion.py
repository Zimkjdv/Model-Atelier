"""Known safetensors key mapping is lossless, bounded and refuses unknown inputs."""

import copy
import json
import hashlib
import io
from contextlib import redirect_stdout
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch
from scripts import convert_pixel_lora as conversion, install_pony


class PixelConversionTests(unittest.TestCase):
    def fixture(self):
        stem = 'unet.down_blocks.1.attentions.0.transformer_blocks.0.attn1.to_k'
        header = {
            '__metadata__': {'format': 'pt'},
            stem + '.lora.down.weight': dict(dtype='F32', shape=[2, 3], data_offsets=[0, 24]),
            stem + '.lora.up.weight': dict(dtype='F32', shape=[4, 2], data_offsets=[24, 56]),
        }
        return header, bytes(range(56))

    def raw(self, header, data):
        encoded = json.dumps(header).encode()
        return struct.pack('<Q', len(encoded)) + encoded + data

    def test_deterministic_aliases_preserve_all_tensor_data_shape_dtype_offsets(self):
        header, data = self.fixture()
        raw = self.raw(header, data)
        result, info = conversion.convert(raw)
        self.assertEqual(conversion.convert(raw), (result, info))
        n = int.from_bytes(result[:8], 'little')
        changed = json.loads(result[8 : 8 + n])
        self.assertEqual(n % 8, 0)
        self.assertEqual(result[8 + n :], data)
        self.assertEqual(info['tensors'], 2)
        self.assertEqual(info['clip_tensors'], 0)
        for original, value in header.items():
            if original == '__metadata__':
                continue
            direction = 'down' if '.down.' in original else 'up'
            target = (
                'lora_unet_down_blocks_1_attentions_0_transformer_blocks_0_attn1_to_k.lora_'
                + direction
                + '.weight'
            )
            self.assertEqual(changed[target], value)

    def test_unknown_keys_missing_pairs_wrong_rank_or_offsets_fail_closed(self):
        header, data = self.fixture()
        keys = [k for k in header if k != '__metadata__']
        invalid = []
        changed = copy.deepcopy(header)
        changed['arbitrary.script'] = changed.pop(keys[0])
        invalid.append(changed)
        changed = copy.deepcopy(header)
        changed.pop(keys[0])
        invalid.append(changed)
        for field, value in [
            ('shape', [True, 3]),
            ('shape', [1, 6]),
            ('data_offsets', [0, 999]),
            ('data_offsets', [24, 48]),
            ('dtype', 'PICKLE'),
        ]:
            changed = copy.deepcopy(header)
            changed[keys[0]][field] = value
            invalid.append(changed)
        for value in invalid:
            with self.assertRaises(ValueError):
                conversion.convert(self.raw(value, data))
        for raw in (b'', struct.pack('<Q', 2**30) + b'{}', self.raw(header, data + b'extra')):
            with self.assertRaises(ValueError):
                conversion.convert(raw)

    def test_duplicate_header_keys_and_non_string_metadata_are_rejected(self):
        duplicate = b'{"a":{},"a":{}}'
        with self.assertRaises(ValueError):
            conversion.convert(struct.pack('<Q', len(duplicate)) + duplicate + b'payload')
        header, data = self.fixture()
        header['__metadata__']['bad'] = 3
        with self.assertRaises(ValueError):
            conversion.convert(self.raw(header, data))

    def test_derived_identity_has_own_hash_path_and_is_not_a_remote_download_alias(self):
        manifest = conversion.manifest()
        self.assertNotEqual(manifest['sha256'], conversion.SOURCE['sha256'])
        self.assertEqual(
            install_pony._paths(conversion.ROOT, manifest['filename'], create=False)[0].parent.name,
            'loras',
        )
        with self.assertRaises(install_pony.InstallationError):
            install_pony.validate_manifest(manifest)

    def local_fixture(self, folder):
        header, data = {}, bytearray()
        for index in range(560):
            stem = f'unet.down_blocks.1.attentions.0.transformer_blocks.{index}.attn1.to_k'
            for direction in ('down', 'up'):
                start = len(data)
                data.extend(b'\x00\x00\x80\x3f')
                header[stem + '.lora.' + direction + '.weight'] = dict(
                    dtype='F32', shape=[1, 1], data_offsets=[start, len(data)]
                )
        raw = self.raw(header, bytes(data))
        result, info = conversion.convert(raw)
        source = Path(folder) / 'original.safetensors'
        source.write_bytes(raw)
        manifest = conversion.manifest() | dict(
            sha256=info['output_sha256'],
            size_bytes=info['output_size_bytes'],
            source_sha256=info['source_sha256'],
            derivation=info,
        )
        return source, raw, result, info, manifest

    def test_check_is_readonly_conversion_is_exclusive_and_reuses_only_exact_bytes(self):
        with tempfile.TemporaryDirectory() as folder:
            source, raw, result, info, manifest = self.local_fixture(folder)
            pinned = conversion.SOURCE | dict(sha256=info['source_sha256'], size_bytes=len(raw))
            with (
                patch.object(conversion, 'SOURCE', pinned),
                patch.object(conversion, 'manifest', return_value=manifest),
                patch.object(install_pony, '_paths', return_value=(source, None, None, None)),
                redirect_stdout(io.StringIO()),
            ):
                self.assertEqual(conversion.main(['--check']), 0)
                self.assertEqual(len(list(Path(folder).iterdir())), 1)
                self.assertEqual(conversion.main([]), 0)
                target = source.with_name(conversion.FILENAME)
                self.assertEqual(target.read_bytes(), result)
                self.assertEqual(source.read_bytes(), raw)
                self.assertEqual(conversion.main([]), 0)
                target.write_bytes(b'changed by another process')
                self.assertEqual(conversion.main([]), 1)
                self.assertEqual(target.read_bytes(), b'changed by another process')
                self.assertEqual(source.read_bytes(), raw)

    def test_promotion_failure_leaves_no_final_or_partial_derived_weight(self):
        with tempfile.TemporaryDirectory() as folder:
            source, raw, _, info, manifest = self.local_fixture(folder)
            pinned = conversion.SOURCE | dict(
                sha256=hashlib.sha256(raw).hexdigest(), size_bytes=len(raw)
            )
            with (
                patch.object(conversion, 'SOURCE', pinned),
                patch.object(conversion, 'manifest', return_value=manifest),
                patch.object(install_pony, '_paths', return_value=(source, None, None, None)),
                patch.object(install_pony, '_promote', side_effect=OSError('promotion denied')),
                redirect_stdout(io.StringIO()),
            ):
                self.assertEqual(conversion.main([]), 1)
            self.assertEqual([p.name for p in Path(folder).iterdir()], [source.name])
