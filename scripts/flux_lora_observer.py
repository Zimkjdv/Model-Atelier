"""Owned F04 engine only: observe native LoRA patch count without changing tensors."""

import json
import os
from pathlib import Path

if os.environ.get('ATELIER_F03_FIXTURE') != '1' or not os.environ.get('ATELIER_F04_OBSERVATIONS'):
    raise RuntimeError('F04 observer requires the isolated fixture')

import nodes

original = nodes.LoraLoaderModelOnly.load_lora_model_only


def observe(self, model, lora_name, strength_model):
    result = original(self, model, lora_name, strength_model)
    keys = sorted(result[0].patches)
    record = dict(
        name=lora_name,
        strength=strength_model,
        patched_parameter_count=len(keys),
        patched_parameter_sample=keys[:8],
        tensor_keys=len(self.loaded_lora[1]) if self.loaded_lora else 0,
    )
    with Path(os.environ['ATELIER_F04_OBSERVATIONS']).open('a', encoding='utf-8') as file:
        file.write(json.dumps(record) + '\n')
    return result


nodes.LoraLoaderModelOnly.load_lora_model_only = observe
NODE_CLASS_MAPPINGS = {}
