"""Deterministic key-only conversion for one pinned SDXL LoRA; original stays intact."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import struct
import tempfile
from scripts import install_model, install_pony as downloader

ROOT = Path(__file__).resolve().parents[1]
SOURCE = install_model.manifest('pixel-art-lora-sdxl')
FILENAME = 'pixel_art_lora_sdxl_comfy_v1.safetensors'
MANIFEST = ROOT / 'models/pixel-art-lora-sdxl-comfy-v1.json'
VERSION = 'key-map-v1 / upstream 5440ac9c42ab'
KEY = re.compile(
    r'^unet\.(?:down_blocks\.[12]|up_blocks\.[01]|mid_block)\.attentions\.\d+\.transformer_blocks\.\d+\.attn[12]\.(?:to_[kqv]|to_out\.0)\.lora\.(down|up)\.weight$'
)
DTYPES = {'F32': 4, 'F16': 2, 'BF16': 2}


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('Duplicate JSON header key')
        result[key] = value
    return result


def convert(raw):
    if not 8 < len(raw) <= 512 * 1024 * 1024:
        raise ValueError('Bounded safetensors input required')
    size = int.from_bytes(raw[:8], 'little')
    if not 0 < size <= 1024 * 1024 or 8 + size >= len(raw):
        raise ValueError('Invalid safetensors header size')
    header = json.loads(raw[8 : 8 + size], object_pairs_hook=unique_object)
    if not isinstance(header, dict):
        raise ValueError('Header object required')
    payload = raw[8 + size :]
    output, mapping, intervals, pairs = {}, {}, [], {}
    metadata = header.get('__metadata__', {})
    if not isinstance(metadata, dict) or any(
        not isinstance(k, str) or not isinstance(v, str) for k, v in metadata.items()
    ):
        raise ValueError('String metadata required')
    output['__metadata__'] = metadata | {
        'model_atelier_conversion': 'sdxl-diffusers-attention-to-comfy-key-map-v1'
    }
    for key, tensor in header.items():
        if key == '__metadata__':
            continue
        match = KEY.fullmatch(key)
        if (
            not match
            or not isinstance(tensor, dict)
            or set(tensor) != {'dtype', 'shape', 'data_offsets'}
        ):
            raise ValueError('Only the known attention LoRA tensor format is supported')
        shape, offsets, dtype = tensor['shape'], tensor['data_offsets'], tensor['dtype']
        if (
            not isinstance(shape, list)
            or len(shape) != 2
            or any(type(v) is not int or not 0 < v <= 16384 for v in shape)
        ):
            raise ValueError('Invalid matrix shape')
        if (
            not isinstance(dtype, str)
            or dtype not in DTYPES
            or not isinstance(offsets, list)
            or len(offsets) != 2
            or any(type(v) is not int for v in offsets)
        ):
            raise ValueError('Invalid tensor type/offsets')
        start, end = offsets
        if (
            not 0 <= start < end <= len(payload)
            or end - start != shape[0] * shape[1] * DTYPES[dtype]
        ):
            raise ValueError('Tensor data size or bounds differ')
        direction = match.group(1)
        stem = key.removeprefix('unet.').removesuffix('.lora.' + direction + '.weight')
        target = 'lora_unet_' + stem.replace('.', '_') + '.lora_' + direction + '.weight'
        if target in output:
            raise ValueError('Converted key collision')
        output[target] = tensor
        mapping[key] = target
        intervals.append((start, end))
        pairs.setdefault(stem, {})[direction] = (dtype, shape)
    if not mapping:
        raise ValueError('No tensors')
    cursor = 0
    for start, end in sorted(intervals):
        if start != cursor:
            raise ValueError('Overlapping or incomplete tensor data')
        cursor = end
    if cursor != len(payload):
        raise ValueError('Unreferenced tensor data')
    for pair in pairs.values():
        if (
            set(pair) != {'down', 'up'}
            or pair['down'][0] != pair['up'][0]
            or pair['down'][1][0] != pair['up'][1][1]
        ):
            raise ValueError('Incomplete or incompatible LoRA pair')
    encoded = json.dumps(output, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()
    encoded += b' ' * (-len(encoded) % 8)
    result = struct.pack('<Q', len(encoded)) + encoded + payload
    return result, dict(
        tensors=len(mapping),
        clip_tensors=0,
        source_sha256=hashlib.sha256(raw).hexdigest(),
        output_sha256=hashlib.sha256(result).hexdigest(),
        output_size_bytes=len(result),
        tensor_data_sha256=hashlib.sha256(payload).hexdigest(),
        key_map_sha256=hashlib.sha256(
            json.dumps(mapping, sort_keys=True, separators=(',', ':')).encode()
        ).hexdigest(),
    )


def manifest():
    value = json.loads(MANIFEST.read_text(encoding='utf-8'))
    if (
        value.get('id') != 'pixel-art-lora-sdxl-comfy-v1'
        or value.get('filename') != FILENAME
        or value.get('version') != VERSION
        or value.get('source_manifest') != SOURCE['id']
        or value.get('source_sha256') != SOURCE['sha256']
        or not re.fullmatch('[a-f0-9]{64}', value.get('sha256', ''))
        or type(value.get('size_bytes')) is not int
        or not 0 < value['size_bytes'] < 512 * 1024 * 1024
    ):
        raise ValueError('Derived manifest identity differs')
    return value


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        '--check',
        action='store_true',
        help='Read/verify and report deterministic conversion without writes',
    )
    args = parser.parse_args(argv)
    try:
        source = downloader._paths(ROOT, SOURCE['filename'], create=False)[0]
        if not source.is_file() or not downloader._verified(source, SOURCE):
            raise ValueError('Pinned original source size/SHA256 required')
        result, info = convert(source.read_bytes())
        if info['tensors'] != 1120:
            raise ValueError('Pinned source tensor count differs')
        target = source.with_name(FILENAME)
        if target.is_symlink() or target.resolve().parent != source.resolve().parent:
            raise ValueError('Derived output escaped original LoRA directory')
        if not args.check:
            expected = manifest()
            if (info['output_sha256'], info['output_size_bytes']) != (
                expected['sha256'],
                expected['size_bytes'],
            ):
                raise ValueError('Derived bytes differ from reviewed manifest')
            if any(
                info[key] != expected.get('derivation', {}).get(key)
                for key in ('tensors', 'clip_tensors', 'tensor_data_sha256', 'key_map_sha256')
            ):
                raise ValueError('Derived tensor/mapping provenance differs')
            if target.exists():
                if not target.is_file() or not downloader._verified(target, expected):
                    raise ValueError('Existing derived file differs; never overwrite')
            else:
                temporary = None
                try:
                    with tempfile.NamedTemporaryFile(
                        dir=target.parent, prefix='.pixel-conversion-', suffix='.tmp', delete=False
                    ) as stream:
                        temporary = Path(stream.name)
                        stream.write(result)
                        stream.flush()
                        os.fsync(stream.fileno())
                    if not downloader._verified(temporary, expected):
                        raise ValueError('Temporary derived file verification failed')
                    downloader._promote(temporary, target)
                finally:
                    if temporary is not None and temporary.exists():
                        temporary.unlink()
            provenance = target.with_suffix(target.suffix + '.conversion.json')
            if provenance.is_symlink():
                raise ValueError('Conversion provenance may not be a symlink')
            if provenance.exists():
                previous = json.loads(provenance.read_text(encoding='utf-8'))
                if any(previous.get(key) != value for key, value in info.items()):
                    raise ValueError('Existing conversion provenance differs')
            else:
                with provenance.open('x', encoding='utf-8') as stream:
                    json.dump(
                        info
                        | dict(
                            converter_version=1, source=SOURCE['source'], license=SOURCE['license']
                        ),
                        stream,
                        ensure_ascii=False,
                        indent=2,
                    )
        print(json.dumps(info | dict(target=str(target), check_only=args.check)))
        return 0
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(str(exc))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
