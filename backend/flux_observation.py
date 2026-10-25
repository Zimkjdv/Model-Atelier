"""Bounded file and tensor observations; no Torch import, model loading or network."""

from collections import Counter
import json
from pathlib import Path
import struct

PROFILE = 'flux-schnell-fp8-cpu-512-v1'
SETTINGS = dict(
    workflow_id='flux1-schnell-text2image-v1',
    engine_url='http://127.0.0.1:8188',
    title='F02 runtime observation',
    diffusion_model='flux1-schnell.safetensors',
    clip_l='clip_l.safetensors',
    t5xxl='t5xxl_fp8_e4m3fn_scaled.safetensors',
    vae='ae.safetensors',
    prompt='anime illustration, one adult woman reading a book in a quiet sunlit library, fully clothed, soft colors',
    seed='9007199254740993',
    width=512,
    height=512,
    steps=4,
    weight_dtype='fp8_e4m3fn',
    encoder_device='cpu',
)


def header_observation(path):
    path = Path(path)
    total = path.stat().st_size
    with path.open('rb') as stream:
        prefix = stream.read(8)
        if len(prefix) != 8:
            raise ValueError('Truncated safetensors prefix')
        length = struct.unpack('<Q', prefix)[0]
        if not 2 <= length <= min(16 * 1024**2, total - 8):
            raise ValueError('Invalid safetensors header length')
        value = json.loads(stream.read(length))
    if not isinstance(value, dict):
        raise ValueError('Invalid safetensors header')
    counts, sizes = Counter(), Counter()
    for key, item in value.items():
        if key == '__metadata__':
            continue
        if not isinstance(item, dict) or not isinstance(item.get('dtype'), str):
            raise ValueError('Invalid tensor description')
        offsets = item.get('data_offsets')
        if (
            not isinstance(offsets, list)
            or len(offsets) != 2
            or any(type(n) is not int for n in offsets)
            or not 0 <= offsets[0] <= offsets[1] <= total - 8 - length
        ):
            raise ValueError('Invalid tensor offsets')
        if len(item['dtype']) > 32:
            raise ValueError('Invalid tensor dtype')
        counts[item['dtype']] += 1
        sizes[item['dtype']] += offsets[1] - offsets[0]
    if not counts:
        raise ValueError('No tensors')
    # Do not export arbitrary metadata such as embedded thumbnails or prompts.
    metadata = value.get('__metadata__', {})
    selected = {
        key: metadata[key]
        for key in ('modelspec.license', 'modelspec.architecture')
        if isinstance(metadata, dict)
        and isinstance(metadata.get(key), str)
        and len(metadata[key]) <= 256
    }
    return dict(
        tensor_counts_by_dtype=dict(counts),
        tensor_bytes_by_dtype=dict(sizes),
        selected_metadata=selected,
        execution_precision_verified=False,
    )


class CastObservations:
    """Count actual cast calls without retaining tensors or unbounded layer names."""

    def __init__(self, limit=128):
        self.limit, self.counts, self.overflow_calls = limit, Counter(), 0

    def record(self, component, source, inputs, result):
        key = (component, source, inputs, result)
        if key not in self.counts and len(self.counts) >= self.limit:
            self.overflow_calls += 1
            return
        self.counts[key] += 1

    def report(self):
        def descriptor(value):
            return dict(dtype=value[0], device=value[1]) if value else None

        return dict(
            observations=[
                dict(
                    component=k[0],
                    source_weight=descriptor(k[1]),
                    input_tensor=descriptor(k[2]),
                    returned_weight=descriptor(k[3]),
                    calls=n,
                )
                for k, n in self.counts.items()
            ],
            overflow_calls=self.overflow_calls,
            scope='observed_cast_bias_weight_calls_only_not_every_kernel_or_accumulator',
        )
