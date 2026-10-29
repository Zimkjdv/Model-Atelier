"""Freeze built-in recipe provenance independently of mutable catalogs and UI labels."""

import hashlib
import json
from copy import deepcopy
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from backend import model_profiles

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = 'models/simple-creation-templates-v1.json'
EXTRA_REGISTRY = 'models/simple-creation-extra-templates-v1.json'
STYLE_REGISTRY = 'models/simple-style-templates-v1.json'


class Selection(BaseModel):
    model_config = ConfigDict(extra='forbid')
    template_id: Literal[
        'animagine',
        'pony',
        'flux',
        'animagine-cafe',
        'animagine-adventurer',
        'animagine-kimono',
        'animagine-library',
        'pony-traveler',
        'pony-station',
        'pony-cat',
        'pony-city',
        'flux-workshop',
        'flux-island',
        'flux-traveler',
        'flux-robot',
        'style-lora',
        'style-reference',
    ]
    template_version: int = Field(strict=True, ge=1, le=1)


def selection(value):
    if value is None:
        return None
    return Selection.model_validate(value).model_dump(mode='json')


def matches(context, selected):
    return (context.get('selection') if context else None) == selection(selected)


def recipe(selected):
    chosen = selection(selected)
    entries = [
        (filename, item)
        for filename in (REGISTRY, EXTRA_REGISTRY, STYLE_REGISTRY)
        for item in json.loads((ROOT / filename).read_text(encoding='utf-8'))['templates']
    ]
    filename, entry = next(
        (filename, item)
        for filename, item in entries
        if item['id'] == chosen['template_id'] and item['version'] == chosen['template_version']
    )
    baseline = dict(prompt=entry['prompt'], seed=entry['seed'])
    if entry['family'] != 'flux':
        manifest = json.loads(
            (ROOT / 'models' / entry['manifest_file']).read_text(encoding='utf-8')
        )
        preset = model_profiles.preset(dict(architecture='sdxl', sha256=manifest['sha256']))
        baseline.update(
            preset['settings'],
            negative_prompt=entry['negative'],
            loras=[],
            workflow_mode='text2image',
            image_asset_id=None,
            reference_ids=[],
        )
        requirements = [dict(role='checkpoint', sha256=manifest['sha256'], architecture='sdxl')]
        workflow = 'checkpoint-text2image-v1'
        if entry.get('task') == 'lora':
            lora = json.loads(
                (ROOT / 'models' / entry['lora_manifest']).read_text(encoding='utf-8')
            )
            baseline['loras'] = [
                dict(name=lora['filename'], enabled=True, strength_model=1.0, strength_clip=1.0)
            ]
            requirements.append(dict(role='lora', sha256=lora['sha256'], architecture='sdxl'))
        elif entry.get('task') == 'reference':
            parts = [
                json.loads((ROOT / 'models' / name).read_text(encoding='utf-8'))
                for name in entry['reference_manifests']
            ]
            baseline.pop('image_asset_id')
            baseline.pop('reference_ids')
            baseline.update(
                reference_mode='style',
                reference_resize='fit',
                reference_weight=0.6,
                reference_start=0.0,
                reference_end=1.0,
                ipadapter_name=parts[0]['filename'],
                clip_vision_name=parts[1]['filename'],
            )
            requirements.extend(
                dict(role=role, sha256=part['sha256'], architecture=kind)
                for part, role, kind in zip(parts, ['ipadapter', 'clip_vision'], ['sdxl', 'other'])
            )
            workflow = 'checkpoint-ipadapter-reference-v1'
    else:
        plan = json.loads((ROOT / 'models/flux1-schnell-plan.json').read_text(encoding='utf-8'))
        requirements = [
            dict(role=part['role'], sha256=part['sha256']) for part in plan['components']
        ]
        baseline.update(
            width=512, height=512, steps=4, weight_dtype='fp8_e4m3fn', encoder_device='cpu'
        )
        workflow = 'flux1-schnell-text2image-v1'
    return dict(
        selection=chosen,
        title=entry['title'],
        model=entry['model'],
        family=entry['family'],
        source=filename,
        reference=entry['reference'],
        quality_note=entry['note'],
        workflow_id=workflow,
        baseline=baseline,
        requirements=requirements,
    )


def freeze(selected, settings, metadata, components, workflow_id, loras=None):
    if selected is None:
        return None
    if settings is None:
        raise ValueError('模板來源需要完整創作設定，不能附加到任意原始流程')
    source = recipe(selected)
    is_flux = 'diffusion_model' in settings
    if (source['family'] == 'flux') != is_flux:
        raise ValueError('模板來源與目前工作流程家族不符')
    if source['family'] == 'reference' and workflow_id != source['workflow_id']:
        raise ValueError('圖片畫風模板需要專用的單張參考流程')
    differences = [key for key, value in source['baseline'].items() if settings.get(key) != value]
    actual_workflow = workflow_id or 'checkpoint-text2image-v1'
    if actual_workflow != source['workflow_id']:
        differences.append('workflow_id')
    actual = {part['role']: part for part in components or []}
    actual['checkpoint'] = metadata or {}
    actual['lora'] = (loras or [{}])[0] if len(loras or []) == 1 else {}
    for part in source['requirements']:
        current = actual.get(part['role'], {})
        if any(current.get(key) != value for key, value in part.items() if key != 'role'):
            differences.append(part['role'])
    digest = hashlib.sha256(
        json.dumps(source, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()
    ).hexdigest()
    return dict(
        schema_version=1,
        origin='builtin_recipe',
        **deepcopy(source),
        recipe_sha256=digest,
        modified=bool(differences),
        changed_fields=sorted(set(differences)),
    )
