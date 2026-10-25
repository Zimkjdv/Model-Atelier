"""Frozen SDXL training attempts; explicit launch/stop/resume, no automatic retry."""

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
from typing import Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field
import psutil

from backend import compute_lease, model_paths, training_bundle as bundle, training_data as data
from backend import training_environment as environment
from backend.training_files import file_manifest, read_json, verify_files

ROOT = Path(__file__).resolve().parents[1]
TERMINAL = {'completed', 'stopped', 'failed', 'blocked'}


class Configuration(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    schema_version: Literal[1] = 1
    purpose: Literal['technical-smoke', 'development-training'] = 'development-training'
    label: str = Field(min_length=1, max_length=120)
    bundle: str = Field(min_length=1, max_length=2048)
    checkpoint: str = Field(min_length=1, max_length=2048)
    gpu_index: int = Field(default=0, ge=0, le=15)
    resolution: Literal[512, 1024] = 1024
    rank: Literal[4, 8, 16] = 4
    learning_rate: float = Field(default=0.0001, gt=0, le=0.01, allow_inf_nan=False)
    max_steps: int = Field(ge=1, le=10000)
    save_every_steps: int = Field(default=100, ge=1, le=10000)
    seed: int = Field(default=42, ge=0, le=4294967295)


def now():
    return datetime.now(timezone.utc).isoformat()


def run_directory(run_id, root=ROOT):
    identifier = str(UUID(str(run_id)))
    path = Path(root).resolve() / 'runtime/training/runs' / identifier
    for part in (path, *path.parents):
        if part == Path(root).resolve():
            break
        if part.is_symlink() or (hasattr(part, 'is_junction') and part.is_junction()):
            raise ValueError('Training run paths cannot be links.')
    return path


def base(root=ROOT):
    model = read_json(Path(root) / 'models/animagine-xl-4.0-opt.json')
    return model, data.BaseAnchor(
        id=model['id'],
        version=model['version'],
        architecture=model['architecture'].lower(),
        sha256=model['sha256'],
        size_bytes=model['size_bytes'],
        source_revision=model['source']['revision'],
    )


def prepare(configuration, *, root=ROOT, resume=None, study=None):
    config = Configuration.model_validate(configuration)
    env = environment.check(root)
    if not env['ready']:
        raise ValueError('Training environment is not ready: ' + '; '.join(env['issues']))
    model, anchor = base(root)
    checkpoint = Path(config.checkpoint)
    source = Path(config.bundle)
    if not checkpoint.is_absolute() or not source.is_absolute():
        raise ValueError('Use absolute checkpoint and sealed bundle paths.')
    model_paths.canonical_directory(str(checkpoint.parent))
    source = model_paths.canonical_directory(str(source))
    checkpoint = checkpoint.resolve(strict=True)
    if (
        not checkpoint.is_file()
        or checkpoint.suffix != '.safetensors'
        or checkpoint.stat().st_size != model['size_bytes']
        or environment.digest(checkpoint) != model['sha256']
    ):
        raise ValueError('The base checkpoint differs from the pinned Animagine model.')
    # Web reviews retain the exact R02 study bytes. Older CLI bundles still
    # require the caller to provide that original study when one is anchored.
    verified = bundle.verify(source, anchor, study)
    dataset = data.load(source / 'dataset.json')
    identifier = str(uuid4())
    target = run_directory(identifier, root)
    bundle.safe_output(target, source_root=source)
    target.mkdir(parents=True)
    work = target / 'work'
    work.mkdir()
    shutil.copytree(source / 'train', work / 'train')
    configuration_bytes = bundle.configuration(work).replace(
        b'resolution = [1024, 1024]',
        f'resolution = [{config.resolution}, {config.resolution}]'.encode('ascii'),
    )
    (work / 'dataset.toml').write_bytes(configuration_bytes)
    if study is not None:
        (work / 'parent-study.json').write_bytes(
            data.canonical(dict(document=study[0], sha256=study[1]))
        )
    (target / 'output').mkdir()
    (target / 'checkpoints').mkdir()
    manifest = dict(
        schema_version=1,
        run_id=identifier,
        created_at=now(),
        configuration=config.model_dump(mode='json'),
        environment=env,
        dataset=dict(
            manifest_sha256=verified['manifest_sha256'],
            bundle_sha256=environment.digest(source / 'bundle.json'),
            id=dataset.dataset_id,
            version=dataset.version,
            kind=dataset.kind,
            subject_id=dataset.subject_id,
            trigger=dataset.trigger,
            train_count=verified['train_count'],
        ),
        base=dict(
            id=model['id'],
            version=model['version'],
            architecture=anchor.architecture,
            sha256=model['sha256'],
            size_bytes=model['size_bytes'],
            path=str(checkpoint),
        ),
        frozen_files=file_manifest(work),
        parent_study=dict(document=study[0], sha256=study[1]) if study is not None else None,
        resume=resume,
    )
    if resume is not None:
        if (
            not isinstance(resume, dict)
            or set(resume) != {'run_id', 'checkpoint'}
            or not re.fullmatch(r'step-[1-9][0-9]{0,7}', str(resume['checkpoint']))
        ):
            raise ValueError('Choose a sealed checkpoint ID, not an arbitrary path.')
        old = run_directory(resume['run_id'], root)
        old_status = inspect(resume['run_id'], root=root)
        if not old_status['resources_released']:
            raise ValueError('The source worker must exit before preparing a resumed attempt.')
        state_receipt = read_json(old / 'checkpoints' / (resume['checkpoint'] + '.json'))
        if (
            state_receipt.get('schema_version') != 1
            or state_receipt.get('run_id') != str(UUID(resume['run_id']))
            or state_receipt.get('manifest_sha256') != old_status['manifest_sha256']
        ):
            raise ValueError('The checkpoint is not sealed against the original frozen run.')
        original = read_json(old / 'manifest.json')
        expected = dict(original['configuration'])
        # Resuming preserves optimizer/scheduler settings, data and total step budget.
        if config.model_dump(mode='json') != expected or manifest['dataset'] != original['dataset']:
            raise ValueError('Resume must use the original frozen configuration and dataset.')
        if any(
            env[key] != original['environment'][key]
            for key in ('profile_sha256', 'dependencies_sha256', 'trainer_revision')
        ):
            raise ValueError('Resume must preserve the original training environment.')
        state = old / 'output' / state_receipt['directory']
        if state.parent != old / 'output' or not state.name.startswith('model-'):
            raise ValueError('Invalid saved checkpoint directory.')
        verify_files(state, state_receipt['files'])
        step = state_receipt['step']
        if (
            type(step) is not int
            or step < 1
            or resume['checkpoint'] != f'step-{step}'
            or read_json(state / 'train_state.json').get('current_step') != step
        ):
            raise ValueError('Checkpoint step differs from the sealed training state.')
        if state_receipt['step'] >= config.max_steps:
            raise ValueError('The checkpoint already reached the frozen step budget.')
        shutil.copytree(state, target / 'resume')
        verify_files(target / 'resume', state_receipt['files'])
        manifest['resume'] = dict(
            run_id=resume['run_id'],
            checkpoint=resume['checkpoint'],
            receipt_sha256=environment.digest(
                old / 'checkpoints' / (resume['checkpoint'] + '.json')
            ),
            step=state_receipt['step'],
            files=state_receipt['files'],
        )
    compute_lease.atomic_json(target / 'manifest.json', manifest)
    digest = hashlib.sha256((target / 'manifest.json').read_bytes()).hexdigest()
    (target / 'manifest.sha256').write_text(digest + '\n', encoding='ascii')
    compute_lease.atomic_json(
        target / 'state.json',
        dict(status='prepared', run_id=identifier, updated_at=now(), manifest_sha256=digest),
    )
    return inspect(identifier, root=root)


def inspect(run_id, *, root=ROOT):
    target = run_directory(run_id, root)
    manifest, state = read_json(target / 'manifest.json'), read_json(target / 'state.json')
    if environment.digest(target / 'manifest.json') != state['manifest_sha256']:
        raise ValueError('The frozen run manifest changed.')
    lease = compute_lease.status(root)
    active = (
        lease['active'] and lease['kind'] == 'training' and lease['run_id'] == manifest['run_id']
    )
    launched = (target / 'launch.json').exists()
    process_alive = False
    if launched:
        launch = read_json(target / 'launch.json')
        identity = launch.get('worker') or launch.get('controller')
        if identity:
            try:
                process_alive = (
                    abs(psutil.Process(identity['pid']).create_time() - identity['created_at'])
                    < 0.001
                )
            except (OSError, psutil.Error):
                pass
    status = state['status']
    if process_alive and status == 'prepared':
        status = 'starting'
    elif process_alive and (target / 'stop.request').exists():
        status = 'stopping'
    elif process_alive and status in TERMINAL:
        status = 'finishing'
    elif (
        status in ('starting', 'running', 'stopping') or status == 'prepared' and launched
    ) and not process_alive:
        status = 'interrupted'
    return dict(
        run_id=manifest['run_id'],
        status=status,
        last_recorded_status=state['status'],
        resources_released=not active and not process_alive,
        state=state,
        manifest_sha256=state['manifest_sha256'],
        directory=str(target),
    )


def stop(run_id, *, root=ROOT):
    current = inspect(run_id, root=root)
    if current['last_recorded_status'] in TERMINAL or current['resources_released']:
        raise ValueError('This run has no active worker to stop.')
    path = run_directory(run_id, root) / 'stop.request'
    try:
        with path.open('x', encoding='ascii') as stream:
            stream.write(now())
    except FileExistsError:
        pass
    return dict(
        run_id=str(run_id), stop_requested=True, resources_released=current['resources_released']
    )


def launch(run_id, *, root=ROOT):
    current = inspect(run_id, root=root)
    if current['status'] != 'prepared':
        raise ValueError('A run can be launched once. Prepare a new attempt or explicitly resume.')
    target = run_directory(run_id, root)
    # Exclusive launch marker makes two controllers unable to dispatch the same run.
    with (target / 'launch.json').open('x', encoding='utf-8') as stream:
        json.dump(
            dict(
                started_at=now(),
                controller=dict(pid=os.getpid(), created_at=psutil.Process().create_time()),
            ),
            stream,
        )
    paths = environment.locations(root)
    manifest = read_json(target / 'manifest.json')
    worker_env = dict(
        os.environ,
        CUDA_VISIBLE_DEVICES=str(manifest['configuration']['gpu_index']),
        HF_HUB_OFFLINE='1',
        TRANSFORMERS_OFFLINE='1',
        HF_HUB_DISABLE_TELEMETRY='1',
        TOKENIZERS_PARALLELISM='false',
        PYTHONIOENCODING='utf-8',
        PYTHONDONTWRITEBYTECODE='1',
    )
    with (target / 'worker.log').open('xb') as log:
        try:
            process = subprocess.Popen(
                [
                    str(paths['python']),
                    '-I',
                    str(Path(root).resolve() / 'scripts/training_worker.py'),
                    '--root',
                    str(Path(root).resolve()),
                    '--run-id',
                    str(run_id),
                    '--manifest-sha256',
                    current['manifest_sha256'],
                ],
                cwd=paths['source'],
                env=worker_env,
                stdout=log,
                stderr=subprocess.STDOUT,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0,
            )
        except OSError as exc:
            launch_record = read_json(target / 'launch.json')
            launch_record['controller'] = None
            compute_lease.atomic_json(target / 'launch.json', launch_record)
            state = read_json(target / 'state.json')
            state.update(
                status='failed', message='Worker could not start: ' + str(exc), updated_at=now()
            )
            compute_lease.atomic_json(target / 'state.json', state)
            return inspect(run_id, root=root)
        launch_record = read_json(target / 'launch.json')
        try:
            created_at = psutil.Process(process.pid).create_time()
        except psutil.NoSuchProcess:
            created_at = 0
        launch_record['worker'] = dict(pid=process.pid, created_at=created_at)
        compute_lease.atomic_json(target / 'launch.json', launch_record)
        try:
            process.wait()
        except KeyboardInterrupt:
            (target / 'stop.request').touch(exist_ok=True)
            try:
                process.wait(timeout=120)
            except subprocess.TimeoutExpired:
                process.terminate()  # Only the worker created by this controller.
                process.wait(timeout=30)
    state = read_json(target / 'state.json')
    if (
        state['status'] not in TERMINAL
        or state['status'] == 'completed'
        and process.returncode != 0
    ):
        state.update(
            status='failed',
            message='Worker exited before recording a terminal state.',
            worker_exit_code=process.returncode,
            updated_at=now(),
        )
        compute_lease.atomic_json(target / 'state.json', state)
    return inspect(run_id, root=root)
