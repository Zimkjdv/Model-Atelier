"""Verified local training artifacts and native comparison plans; no generation."""

import json
from pathlib import Path
import shutil
from uuid import uuid4

from backend import training_bundle, training_runs as runs
from backend.schemas import DraftInput, ModelMetadata
from backend.training_files import digest, read_json, verify_files

SEEDS = ['9007199254740993', '18446744073709551615']


def paths(run_id, root=runs.ROOT):
    run = runs.run_directory(run_id, root)
    name = 'ma-trained-' + run.name + '.safetensors'
    folder = Path(root).resolve() / 'runtime/ComfyUI/models/loras'
    for part in (folder / name, folder / (name + '.training.json'), folder, *folder.parents):
        if part.is_symlink() or (hasattr(part, 'is_junction') and part.is_junction()):
            raise ValueError('Installed training paths cannot be links.')
    return run, folder / name, folder / (name + '.training.json')


def identity(path):
    for part in (path, *path.parents):
        if part.is_symlink() or (hasattr(part, 'is_junction') and part.is_junction()):
            raise ValueError('Trained weights cannot be links.')
    return dict(size_bytes=path.stat().st_size, sha256=digest(path))


def write_new(path, value):
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False).encode('utf-8')
    with path.open('xb') as stream:
        stream.write(raw)


def finished(run_id, root=runs.ROOT):
    status = runs.inspect(run_id, root=root)
    if status['status'] != 'completed' or not status['resources_released']:
        raise ValueError('Only a completed run whose worker released resources can be registered.')
    folder = runs.run_directory(run_id, root)
    manifest, receipt = read_json(folder / 'manifest.json'), read_json(folder / 'artifacts.json')
    if (
        receipt.get('schema_version') != 1
        or receipt.get('run_id') != status['run_id']
        or receipt.get('manifest_sha256') != status['manifest_sha256']
        or receipt.get('technical_only')
        != (manifest['configuration']['purpose'] == 'technical-smoke')
    ):
        raise ValueError('Artifact receipt does not match the frozen run.')
    expected = receipt['files']['model.safetensors']
    source = folder / 'output/model.safetensors'
    actual = identity(source)
    if actual != expected:
        raise ValueError('Final trained weight size/hash differs from its receipt.')
    step = manifest['configuration']['max_steps']
    checkpoint = read_json(folder / f'checkpoints/step-{step}.json')
    if (
        checkpoint.get('run_id') != manifest['run_id']
        or checkpoint.get('step') != step
        or checkpoint.get('manifest_sha256') != status['manifest_sha256']
        or checkpoint.get('directory') != 'model-state'
    ):
        raise ValueError('Final training state is not sealed against this run.')
    verify_files(folder / 'output/model-state', checkpoint['files'])
    if read_json(folder / 'output/model-state/train_state.json')['current_step'] != step:
        raise ValueError('Final saved training step differs from the frozen budget.')
    return manifest, receipt, source


def registration(run_id, root=runs.ROOT):
    run, weight, sidecar = paths(run_id, root)
    # An installed record can be inspected offline without loading any weights.
    value = read_json(sidecar)
    if (
        digest(sidecar)
        != sidecar.with_suffix(sidecar.suffix + '.sha256').read_text(encoding='ascii').strip()
        or value.get('run_id') != run.name
        or value.get('filename') != weight.name
    ):
        raise ValueError('Installed training provenance changed or is incomplete.')
    return value


def verify_installed(run_id, root=runs.ROOT):
    value = registration(run_id, root)
    _, weight, _ = paths(run_id, root)
    if identity(weight) != value['weight']:
        raise ValueError('Installed trained weight changed.')
    return value


def register(run_id, root=runs.ROOT):
    manifest, receipt, source = finished(run_id, root)
    _, weight, sidecar = paths(run_id, root)
    if sidecar.exists():
        value = verify_installed(run_id, root)
        if (
            value['manifest_sha256'] != receipt['manifest_sha256']
            or value['weight'] != receipt['files'][source.name]
        ):
            raise ValueError('Existing registration belongs to different training evidence.')
        return value
    training_bundle.safe_output(weight)
    weight.parent.mkdir(parents=True, exist_ok=True)
    with source.open('rb') as original, weight.open('xb') as output:
        shutil.copyfileobj(original, output, 4 * 1024 * 1024)
    if digest(weight) != receipt['files'][source.name]['sha256']:
        raise ValueError('Copied artifact differs; unsealed output retained for diagnosis.')
    technical = receipt['technical_only']
    value = dict(
        schema_version=1,
        run_id=manifest['run_id'],
        filename=weight.name,
        version='run-' + manifest['run_id'],
        architecture='sdxl',
        weight=receipt['files'][source.name],
        manifest_sha256=receipt['manifest_sha256'],
        dataset=manifest['dataset'],
        configuration=manifest['configuration'],
        environment=manifest['environment'],
        base=manifest['base'],
        resume=manifest['resume'],
        technical_only=technical,
        quality_status='technical-only' if technical else 'not-evaluated',
        quality_limits=[
            'No author-style or character quality acceptance.',
            'Final holdout and human review are required before a quality claim.',
        ],
        license_status='output terms not reviewed; preserve base model and dataset source restrictions',
        registered_at=runs.now(),
    )
    write_new(sidecar, value)
    with sidecar.with_suffix(sidecar.suffix + '.sha256').open('x', encoding='ascii') as stream:
        stream.write(digest(sidecar) + '\n')
    return verify_installed(run_id, root)


def response(client, method, path, **options):
    result = client.request(method, '/api/' + path, **options)
    result.raise_for_status()
    return result.json()


def metadata(value):
    label = (
        'TECHNICAL TEST ONLY; no style/character quality pass'
        if value['technical_only']
        else 'Quality not evaluated'
    )
    notes = (
        f'{label}\nTraining run: {value["run_id"]}\nManifest SHA256: {value["manifest_sha256"]}\n'
        f'Dataset: {value["dataset"]["id"]} / {value["dataset"]["version"]} / {value["dataset"]["manifest_sha256"]}\n'
        f'Base SHA256: {value["base"]["sha256"]}\nTrainer: {value["environment"]["trainer_revision"]}\n'
        f'Trigger: {value["dataset"]["trigger"]}\nProvenance: {value["filename"]}.training.json\n'
        'Output terms unreviewed; preserve base and dataset source restrictions.'
    )
    return ModelMetadata(
        engine_url='http://127.0.0.1:8188',
        name=value['filename'],
        version=value['version'],
        architecture='sdxl',
        sha256=value['weight']['sha256'],
        size_bytes=value['weight']['size_bytes'],
        notes=notes,
        license_name='Unreviewed trained output',
    ).model_dump(mode='json', exclude={'engine_url'})


def require_engine(client):
    engine = response(client, 'GET', 'settings')['comfy_url']
    if engine != 'http://127.0.0.1:8188':
        raise ValueError(
            'Registration supports the managed local engine http://127.0.0.1:8188 only.'
        )
    return engine


def publish(client, run_id, root=runs.ROOT):
    value = verify_installed(run_id, root)
    engine, fields = require_engine(client), metadata(value)
    catalog = response(client, 'POST', 'loras/sync', json=dict(engine_url=engine))
    if catalog.get('engine_url') != engine or catalog.get('sync_error'):
        raise ValueError('A successful original-engine LoRA sync is required.')
    item = next(
        (v for v in catalog['loras'] if v['name'] == value['filename'] and v['listed']), None
    )
    if item is None or item.get('sha256') not in ('', fields['sha256']):
        raise ValueError(
            'Installed artifact is missing or conflicts with existing registered identity.'
        )
    if not all(item.get(key) == field for key, field in fields.items()):
        require_engine(client)
        verify_installed(run_id, root)
        catalog = response(client, 'PUT', 'loras/metadata', json=fields | dict(engine_url=engine))
    saved = next(v for v in catalog['loras'] if v['name'] == value['filename'])
    if not all(saved.get(key) == field for key, field in fields.items()):
        raise ValueError('Catalog did not preserve the trained artifact metadata.')
    return dict(engine_url=engine, artifact=value, catalog_entry=saved)


def cases(kind, root=runs.ROOT):
    source = Path(root) / (
        'experiments/anime-illustration-v1.json'
        if kind == 'style'
        else 'docs/validation/reference-adapter-20261023.json'
    )
    document = read_json(source)
    if kind == 'style':
        rows = document['cases']
    else:
        rows, seen = [], set()
        for item in document['cases']:
            settings = item['settings']
            if settings.get('reference_mode') != 'character' or settings['prompt'] in seen:
                continue
            seen.add(settings['prompt'])
            rows.append(
                dict(
                    id=f'character-{len(rows) + 1}',
                    name=settings['title'].split(' / ')[3],
                    prompt=settings['prompt'],
                    checks=['hair/eyes/ribbon identity', 'clothing/object/background obedience'],
                )
            )
    if len(rows) != 3:
        raise ValueError('The fixed evaluation source must contain exactly three distinct cases.')
    return dict(source=source.relative_to(root).as_posix(), sha256=digest(source), cases=rows)


def evaluation(client, run_id, output, *, root=runs.ROOT):
    value = verify_installed(run_id, root)
    engine = require_engine(client)
    for endpoint, field, name, expected in (
        ('models', 'models', Path(value['base']['path']).name, value['base']),
        (
            'loras',
            'loras',
            value['filename'],
            value['weight'] | dict(version=value['version'], architecture='sdxl'),
        ),
    ):
        catalog = response(client, 'GET', endpoint)
        item = next((v for v in catalog.get(field, []) if v['name'] == name and v['listed']), None)
        if (
            catalog.get('engine_url') != engine
            or catalog.get('sync_error')
            or item is None
            or any(
                item.get(key) != expected[key]
                for key in ('sha256', 'size_bytes', 'version', 'architecture')
            )
        ):
            raise ValueError(
                'Publish and verify the original base/artifact catalog identities before preparing evaluation.'
            )
    target = training_bundle.safe_output(output)
    original = cases(value['dataset']['kind'], root)
    plans = []
    for case in original['cases']:
        for branch in ('baseline', 'candidate'):
            choices = (
                []
                if branch == 'baseline'
                else [
                    dict(
                        name=value['filename'], enabled=True, strength_model=1.0, strength_clip=0.0
                    )
                ]
            )
            settings = DraftInput(
                title=f'T04 {case["id"]} {branch}',
                engine_url=engine,
                checkpoint=Path(value['base']['path']).name,
                prompt=value['dataset']['trigger'] + ', ' + case['prompt'],
                negative_prompt='child, teenager, nudity, text, watermark, multiple people, blurry, bad hands',
                seed=SEEDS[0],
                width=1024,
                height=1024,
                steps=28,
                cfg=5.0,
                sampler_name='euler_ancestral',
                scheduler='normal',
                denoise=1.0,
                loras=choices,
            ).model_dump(mode='json', exclude={'revision'})
            document = response(
                client,
                'POST',
                'experiments/preview',
                json=dict(
                    title=settings['title'],
                    settings=settings,
                    axis='seed',
                    values=SEEDS,
                    case_ids=[],
                ),
            )
            plans.append(
                dict(case_id=case['id'], branch=branch, request_id=str(uuid4()), plan=document)
            )
    result = dict(
        schema_version=1,
        run_id=value['run_id'],
        artifact=value['weight'],
        manifest_sha256=value['manifest_sha256'],
        technical_only=value['technical_only'],
        quality_status='not-reviewed',
        final_holdout_status='requires independent unexposed images and review',
        source=original,
        seeds=SEEDS,
        expected_job_count=12,
        plans=plans,
        review_dimensions=[
            'style proximity',
            'character identity',
            'prompt obedience',
            'absolute image quality',
        ],
        quality_rule='Review all six paired cells; at least four improved is only an initial signal, not a quality guarantee.',
        generation_started=False,
    )
    target.mkdir(parents=True)
    write_new(target / 'evaluation.json', result)
    evaluation_sha = digest(target / 'evaluation.json')
    write_new(
        target / 'review-template.json',
        dict(
            schema_version=1,
            evaluation_sha256=evaluation_sha,
            reviewer='',
            reviewed_at=None,
            final_holdout_review=None,
            quality_accepted=False,
            cells=[
                dict(
                    case_id=case['id'],
                    seed=seed,
                    baseline_artwork_id=None,
                    candidate_artwork_id=None,
                    dimensions={key: None for key in result['review_dimensions']},
                    failure_notes='',
                    reviewed=False,
                )
                for case in original['cases']
                for seed in SEEDS
            ],
        ),
    )
    (target / 'evaluation.sha256').write_text(evaluation_sha + '\n', encoding='ascii')
    return result


def save_plans(client, output):
    target = Path(output)
    if (
        digest(target / 'evaluation.json')
        != (target / 'evaluation.sha256').read_text(encoding='ascii').strip()
    ):
        raise ValueError('Frozen evaluation changed.')
    value = read_json(target / 'evaluation.json')
    saved = []
    for row in value['plans']:
        record = response(
            client,
            'POST',
            'experiments/plans',
            json=dict(request_id=row['request_id'], plan=row['plan']),
        )
        saved.append(
            dict(
                case_id=row['case_id'],
                branch=row['branch'],
                plan_id=record['id'],
                plan_sha256=row['plan']['plan_sha256'],
            )
        )
    return dict(run_id=value['run_id'], plans=saved, generation_started=False)
