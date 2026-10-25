"""Private F02 worker, run only by verify_flux_runtime in the managed ComfyUI Python."""

import argparse
from collections import Counter
import gc
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import time
import traceback
from uuid import UUID

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-id', required=True)
    run_id = parser.parse_args().run_id
    if str(UUID(run_id)) != run_id:
        raise ValueError('Canonical UUID required')
    output = ROOT / 'runtime' / 'flux-runtime-checks' / run_id
    request = json.loads((output / 'request.json').read_text(encoding='utf-8'))
    sys.path.insert(0, str(ROOT))
    from backend.flux_observation import CastObservations, PROFILE, SETTINGS

    if request['profile'] != PROFILE or request['settings'] != SETTINGS:
        raise ValueError('Unrecognized runtime profile')
    comfy = ROOT / 'runtime' / 'ComfyUI'
    if output.is_symlink() or not output.resolve().is_relative_to(ROOT / 'runtime'):
        raise ValueError('Unsafe output path')
    for row in request['weights']:
        target = Path(row['target'])
        stat = target.stat()
        if stat.st_size != row['size_bytes'] or stat.st_mtime_ns != row['mtime_ns']:
            raise ValueError('Verified weight changed before loading')
    os.chdir(comfy)
    sys.path.insert(0, str(comfy))
    # Comfy's parser must see only supported Comfy arguments, never worker arguments.
    sys.argv = ['flux_runtime_worker', '--preview-method', 'none', '--disable-api-nodes']
    import torch
    import psutil
    import numpy as np
    from PIL import Image
    import nodes
    import comfy.model_management as management
    import comfy.ops as ops
    from comfy_extras.nodes_sd3 import EmptySD3LatentImage

    if not torch.cuda.is_available():
        raise RuntimeError('CUDA is required for this explicit GPU observation')
    device = torch.cuda.current_device()
    torch.cuda.reset_peak_memory_stats(device)
    result = dict(
        schema_version=1,
        profile=PROFILE,
        status='running',
        request_sha256=hashlib.sha256((output / 'request.json').read_bytes()).hexdigest(),
        runtime=dict(
            torch=torch.__version__,
            python=sys.version.split()[0],
            cuda=torch.version.cuda,
            gpu=torch.cuda.get_device_name(device),
            vram_bytes=torch.cuda.get_device_properties(device).total_memory,
        ),
        stages=[],
        parameter_snapshots=[],
        resources={},
        casts=None,
        note='Native node calls in an isolated process; encoder first, unload between stages; not platform HTTP acceptance.',
    )
    casts, components, stop = CastObservations(), {}, threading.Event()
    original_cast = ops.cast_bias_weight
    started, samples, process = time.monotonic(), [], psutil.Process()
    peak_rss = peak_host_used = peak_card_used = 0
    sample_total, nvidia_failures = 0, 0

    def descriptor(tensor):
        return (str(tensor.dtype), str(tensor.device)) if isinstance(tensor, torch.Tensor) else None

    def observed_cast(module, *args, **kwargs):
        source = descriptor(getattr(module, 'weight', None))
        inputs = descriptor(kwargs.get('input', args[0] if args else None))
        value = original_cast(module, *args, **kwargs)
        casts.record(components.get(id(module), 'unassigned'), source, inputs, descriptor(value[0]))
        return value

    def inventory(module, label, phase):
        counters = Counter()
        for tensor in list(module.parameters()) + list(module.buffers()):
            counters[(str(tensor.dtype), str(tensor.device))] += (
                tensor.numel() * tensor.element_size()
            )
        result['parameter_snapshots'].append(
            dict(
                component=label,
                phase=phase,
                logical_tensor_bytes=[
                    dict(dtype=k[0], device=k[1], bytes=v) for k, v in counters.items()
                ],
                note='Logical parameter/buffer bytes; not unique storage or allocated VRAM.',
            )
        )

    def register(module, label):
        for child in module.modules():
            components[id(child)] = label

    def sample_resources():
        nonlocal peak_rss, peak_host_used, peak_card_used, sample_total, nvidia_failures
        while not stop.is_set():
            memory = psutil.virtual_memory()
            rss = process.memory_info().rss
            peak_rss, peak_host_used = (
                max(peak_rss, rss),
                max(peak_host_used, memory.total - memory.available),
            )
            sample = dict(
                elapsed_seconds=round(time.monotonic() - started, 3),
                process_rss_bytes=rss,
                host_available_bytes=memory.available,
                card_used_bytes=None,
            )
            try:
                query = subprocess.run(
                    [
                        'nvidia-smi',
                        '--query-gpu=memory.used',
                        '--format=csv,noheader,nounits',
                        '-i',
                        str(device),
                    ],
                    capture_output=True,
                    timeout=3,
                    check=True,
                    creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0),
                )
                # With a visibility mapping we cannot infer the NVML index from a CUDA index.
                if not os.environ.get('CUDA_VISIBLE_DEVICES'):
                    used = int(query.stdout.strip()) * 1024**2
                    sample['card_used_bytes'] = used
                    peak_card_used = max(peak_card_used, used)
            except (OSError, ValueError, subprocess.SubprocessError):
                nvidia_failures += 1
            if len(samples) < 1200:
                samples.append(sample)
            sample_total += 1
            stop.wait(1)

    def stage(name, action):
        print('F02 stage: ' + name, flush=True)
        tick = time.monotonic()
        value = action()
        torch.cuda.synchronize(device)
        result['stages'].append(dict(name=name, elapsed_seconds=round(time.monotonic() - tick, 4)))
        return value

    sampler = threading.Thread(target=sample_resources, daemon=True)
    ops.cast_bias_weight = observed_cast
    sampler.start()
    try:
        with torch.inference_mode():
            clip = stage(
                'load_encoders_cpu',
                lambda: nodes.DualCLIPLoader().load_clip(
                    SETTINGS['clip_l'], SETTINGS['t5xxl'], 'flux', device='cpu'
                )[0],
            )
            for label in ('clip_l', 't5xxl'):
                module = getattr(clip.cond_stage_model, label, None)
                if module is not None:
                    register(module, label)
                    inventory(module, label, 'after_load')
            positive = stage(
                'encode_positive_cpu',
                lambda clip=clip: nodes.CLIPTextEncode().encode(clip, SETTINGS['prompt'])[0],
            )
            negative = stage(
                'encode_empty_cpu', lambda clip=clip: nodes.CLIPTextEncode().encode(clip, '')[0]
            )
            management.unload_all_models()
            del clip
            gc.collect()

            model = stage(
                'load_diffusion_fp8',
                lambda: nodes.UNETLoader().load_unet(
                    SETTINGS['diffusion_model'], SETTINGS['weight_dtype']
                )[0],
            )
            register(model.model, 'diffusion_model')
            inventory(model.model, 'diffusion_model', 'after_load')
            latent = EmptySD3LatentImage().generate(512, 512, 1)[0]
            latent = stage(
                'sample_four_steps',
                lambda model=model: nodes.KSampler().sample(
                    model,
                    int(SETTINGS['seed']),
                    4,
                    1.0,
                    'euler',
                    'simple',
                    positive,
                    negative,
                    latent,
                    denoise=1.0,
                )[0],
            )
            inventory(model.model, 'diffusion_model', 'after_sampling')
            management.unload_all_models()
            del model
            gc.collect()

            vae = stage('load_vae', lambda: nodes.VAELoader().load_vae(SETTINGS['vae'])[0])
            register(vae.first_stage_model, 'vae')
            inventory(vae.first_stage_model, 'vae', 'after_load')
            images = stage('decode', lambda: nodes.VAEDecode().decode(vae, latent)[0])
            inventory(vae.first_stage_model, 'vae', 'after_decode')
            pixels = np.clip(images[0].detach().cpu().numpy() * 255, 0, 255).astype(np.uint8)
            image = output / 'output.png'
            Image.fromarray(pixels).save(image)
            result['output'] = dict(
                filename=image.name,
                sha256=hashlib.sha256(image.read_bytes()).hexdigest(),
                width=pixels.shape[1],
                height=pixels.shape[0],
                pixel_standard_deviation=float(pixels.std()),
                quality_verified=False,
            )
            result['status'] = 'completed'
    except BaseException as exc:
        result.update(status='failed', error_type=type(exc).__name__, error_message=str(exc)[:1000])
        traceback.print_exc()
    finally:
        stop.set()
        sampler.join(timeout=5)
        ops.cast_bias_weight = original_cast
        result['elapsed_seconds'] = round(time.monotonic() - started, 4)
        result['casts'] = casts.report()
        result['resources'] = dict(
            host_total_bytes=psutil.virtual_memory().total,
            process_rss_observed_max_bytes=peak_rss or None,
            host_used_observed_max_bytes=peak_host_used or None,
            card_used_observed_max_bytes=peak_card_used or None,
            torch_max_memory_allocated_bytes=torch.cuda.max_memory_allocated(device),
            torch_max_memory_reserved_bytes=torch.cuda.max_memory_reserved(device),
            sample_count=sample_total,
            retained_samples=len(samples),
            nvidia_failures=nvidia_failures,
            samples=samples,
            note='Process CUDA allocator maxima; RSS/card/host values are periodic shared observations, not continuous or task-exclusive minima.',
        )
        (output / 'observation.json').write_text(
            json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8'
        )
    return 0 if result['status'] == 'completed' else 1


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
    raise SystemExit(main())
