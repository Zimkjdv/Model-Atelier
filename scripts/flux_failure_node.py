"""Test-only extension, copied only into a fresh F03 fixture engine base directory.

Never install this into a normal ComfyUI. Normal model names delegate unchanged.
The OOM probe sets a tiny allocator quota, requests 4 MiB, then restores the quota.
"""

import os

if os.environ.get('ATELIER_F03_FIXTURE') != '1':
    raise RuntimeError('F03 fault extension requires the isolated fixture environment')

import nodes
import torch


original_loader = nodes.UNETLoader.load_unet


def load_with_quota(self, unet_name, weight_dtype):
    if unet_name == 'f03-quota-oom.safetensors':
        torch.cuda.init()
        try:
            torch.cuda.set_per_process_memory_fraction(0.000001)
            torch.empty(1024 * 1024, device='cuda', dtype=torch.float32)
        finally:
            # The owned engine starts with the default quota. Some CUDA 13
            # builds report an invalid value from the getter; never mask the
            # allocation exception while restoring this known default.
            torch.cuda.set_per_process_memory_fraction(1.0)
        raise RuntimeError('OOM probe unexpectedly allocated successfully')
    return original_loader(self, unet_name, weight_dtype)


# ComfyUI deliberately ignores custom mappings that replace built-in names.
# Patch the method only in this guarded test process; its normal names delegate.
nodes.UNETLoader.load_unet = load_with_quota
NODE_CLASS_MAPPINGS = {}
