"""Synthetic FLUX node schemas for tests, never GPU or installed-weight evidence."""

from backend import flux_plan


def definitions(lora='flux-schnell-pvc-style.safetensors'):
    number = lambda kind, low, high: [kind, dict(min=low, max=high, default=low)]
    encoders = [flux_plan.PINNED[role][1] for role in ('clip_l', 't5xxl')]
    specs = {
        'UNETLoader': (
            {
                'unet_name': [[flux_plan.PINNED['diffusion_model'][1]]],
                'weight_dtype': [['default', 'fp8_e4m3fn']],
            },
            ['MODEL'],
        ),
        'DualCLIPLoader': (
            {
                'clip_name1': [encoders],
                'clip_name2': [encoders],
                'type': [['flux']],
                'device': [['default', 'cpu']],
            },
            ['CLIP'],
        ),
        'VAELoader': ({'vae_name': [[flux_plan.PINNED['vae'][1]]]}, ['VAE']),
        'CLIPTextEncode': ({'clip': ['CLIP'], 'text': ['STRING']}, ['CONDITIONING']),
        'EmptySD3LatentImage': (
            {
                key: number('INT', 1 if key == 'batch_size' else 16, 8192)
                for key in ('width', 'height', 'batch_size')
            },
            ['LATENT'],
        ),
        'KSampler': (
            {
                'model': ['MODEL'],
                'positive': ['CONDITIONING'],
                'negative': ['CONDITIONING'],
                'latent_image': ['LATENT'],
                'seed': number('INT', 0, 2**64 - 1),
                'steps': number('INT', 1, 10000),
                'cfg': number('FLOAT', 0, 100),
                'denoise': number('FLOAT', 0, 1),
                'sampler_name': [['euler']],
                'scheduler': [['simple', 'normal']],
            },
            ['LATENT'],
        ),
        'VAEDecode': ({'samples': ['LATENT'], 'vae': ['VAE']}, ['IMAGE']),
        'SaveImage': ({'images': ['IMAGE'], 'filename_prefix': ['STRING']}, ['IMAGE']),
        'LoraLoaderModelOnly': (
            {
                'model': ['MODEL'],
                'lora_name': [[lora]],
                'strength_model': number('FLOAT', -100, 100),
            },
            ['MODEL'],
        ),
        'LoraLoader': ({'lora_name': [[lora]]}, ['MODEL', 'CLIP']),
        'LoadImage': ({'image': [[]]}, ['IMAGE', 'MASK']),
        'VAEEncode': ({'pixels': ['IMAGE'], 'vae': ['VAE']}, ['LATENT']),
    }
    result = {
        kind: dict(input={'required': inputs}, output=outputs)
        for kind, (inputs, outputs) in specs.items()
    }
    result['SaveImage']['output_node'] = True
    return result


def register(context, engine):
    import json
    from backend import flux_catalog, flux_extensions, loras

    groups = {group: [] for group in flux_catalog.GROUPS}
    for role, (group, filename, _, revision, _, digest) in flux_plan.PINNED.items():
        groups[group].append(filename)
    flux_catalog.merge(context.DB, engine, groups)
    for role, (group, filename, _, revision, _, digest) in flux_plan.PINNED.items():
        flux_catalog.update_metadata(
            context.DB,
            engine,
            group,
            filename,
            dict(
                version='revision ' + revision,
                sha256=digest,
                architecture='flux' if role == 'diffusion_model' else 'unknown',
            ),
        )
    manifest = json.loads(flux_extensions.LORA_MANIFEST.read_text(encoding='utf-8'))
    loras.merge(context.DB, engine, [manifest['filename']])
    loras.update_metadata(
        context.DB,
        engine,
        manifest['filename'],
        {key: manifest[key] for key in ('version', 'sha256', 'architecture')},
    )
