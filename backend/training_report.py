"""Bounded observations of one frozen run; never load images, weights or trainer."""

import hashlib
import json
import math
import re

from backend import training_runs as runs

MAX_JSON = 4 * 1024 * 1024
MAX_REPORT = 1024 * 1024
MAX_LOG = 64 * 1024
CONFIG = (
    'purpose',
    'gpu_index',
    'resolution',
    'rank',
    'learning_rate',
    'max_steps',
    'save_every_steps',
    'seed',
)


def pick(value, names):
    """Only scalar, bounded fields; no arbitrary nested metadata or machine paths."""
    if not isinstance(value, dict):
        return {}
    result = {}
    for key in names:
        item = value.get(key)
        if item is None or type(item) in (bool, int):
            result[key] = item
        elif type(item) is float:
            result[key] = item if math.isfinite(item) else None
        elif isinstance(item, str) and len(item) <= 256 and not re.search(r'[\\/\x00-\x1f]', item):
            result[key] = item
    return result


class Snapshot:
    def __init__(self, directory):
        self.directory = directory
        self.issues = []
        self.files = {}

    def issue(self, name, code):
        if len(self.issues) < 110:
            self.issues.append(dict(record=name, code=code))

    def path(self, name):
        path = self.directory / name
        for part in (path, *path.parents):
            if part.is_symlink() or (hasattr(part, 'is_junction') and part.is_junction()):
                raise ValueError('linked_record')
            if part == self.directory:
                break
        return path

    def read(self, name, limit=MAX_JSON, optional=False):
        try:
            with self.path(name).open('rb') as stream:
                raw = stream.read(limit + 1)
            if len(raw) > limit:
                raise ValueError('record_too_large')

            def unique(pairs):
                result = {}
                for key, value in pairs:
                    if key in result:
                        raise ValueError('duplicate_key')
                    result[key] = value
                return result

            value = json.loads(raw, object_pairs_hook=unique)
            if not isinstance(value, dict):
                raise ValueError('invalid_object')
            self.files[name] = dict(
                status='read', size_bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest()
            )
            return value
        except FileNotFoundError:
            self.files[name] = dict(status='missing')
            if not optional:
                self.issue(name, 'missing_record')
        except (OSError, ValueError, RecursionError):
            self.files[name] = dict(status='unreadable')
            self.issue(name, 'unreadable_record')
        return None

    def log(self):
        try:
            with self.path('worker.log').open('rb') as stream:
                size = stream.seek(0, 2)
                stream.seek(max(0, size - MAX_LOG))
                raw = stream.read(MAX_LOG)
            return dict(
                text=raw.decode('utf-8', errors='replace'),
                captured_bytes=len(raw),
                truncated=size > MAX_LOG,
            )
        except FileNotFoundError:
            return dict(text=None, captured_bytes=0, truncated=False, status='missing')
        except (OSError, ValueError):
            self.issue('worker.log', 'unreadable_record')
            return dict(text=None, status='unreadable')


def collect(root, uid, *, include_logs=False):
    started = runs.now()
    snap = Snapshot(runs.run_directory(uid, root))
    manifest = snap.read('manifest.json') or {}
    state = snap.read('state.json') or {}
    launch = snap.read('launch.json', optional=True)
    actual_hash = snap.files['manifest.json'].get('sha256')
    recorded_hash = state.get('manifest_sha256')
    match = actual_hash == recorded_hash if actual_hash and recorded_hash else None
    if match is False:
        snap.issue('manifest.json', 'manifest_state_mismatch')
    observation = dict(status='unknown', resources_released=None)
    safe_status = all(
        snap.files[name]['status'] != 'unreadable'
        for name in ('manifest.json', 'state.json', 'launch.json')
    )
    known_manifest = type(manifest.get('schema_version')) is int and manifest['schema_version'] == 1
    known_state = state.get('status') in (
        'prepared',
        'starting',
        'running',
        'stopping',
        'stopped',
        'completed',
        'failed',
        'blocked',
        'interrupted',
        'finishing',
    )
    if match and manifest.get('run_id') == uid and safe_status and known_manifest and known_state:
        try:
            # Inspect hashes only manifest metadata, and observes process/OS lease.
            observation.update(
                pick(
                    runs.inspect(uid, root=root),
                    ('status', 'last_recorded_status', 'resources_released'),
                )
            )
        except (OSError, ValueError, KeyError, TypeError):
            snap.issue('state.json', 'live_observation_unavailable')
    else:
        snap.issue('state.json', 'live_observation_unavailable')
    resources = snap.read('resources.json', optional=True)
    resource_summary = None
    if resources is not None:
        resource_summary = pick(
            resources,
            ('elapsed_seconds', 'torch_peak_allocated_bytes', 'torch_peak_reserved_bytes'),
        )
        samples = resources.get('samples')
        if isinstance(samples, list):
            resource_summary.update(
                sample_count=len(samples),
                samples_retained=min(len(samples), 100),
                samples=[
                    pick(
                        v,
                        (
                            'elapsed_seconds',
                            'rss_bytes',
                            'process_peak_working_set_bytes',
                            'whole_gpu_used_bytes',
                        ),
                    )
                    for v in samples[-100:]
                ],
            )
        resource_summary['measurement_scope'] = (
            'allocator, process RAM and whole-GPU samples are distinct; whole GPU includes other software'
        )
    artifact = snap.read('artifacts.json', optional=True)
    artifact_summary = None
    if artifact is not None:
        artifact_summary = pick(
            artifact, ('schema_version', 'run_id', 'manifest_sha256', 'technical_only')
        )
        files = artifact.get('files')
        artifact_summary['final_weight'] = (
            pick(files.get('model.safetensors'), ('sha256', 'size_bytes'))
            if isinstance(files, dict)
            else None
        )
        artifact_summary['recorded_files'] = len(files) if isinstance(files, dict) else None
        artifact_summary['matches_run'] = (
            bool(actual_hash)
            and artifact.get('run_id') == uid
            and artifact.get('manifest_sha256') == actual_hash
        )
        if not artifact_summary['matches_run']:
            snap.issue('artifacts.json', 'receipt_source_mismatch')
    receipts = []
    checkpoint_count = None
    try:
        directory = snap.path('checkpoints')
        paths = []
        if directory.exists():
            for path in directory.iterdir():
                if re.fullmatch(r'step-[1-9][0-9]{0,7}\.json', path.name):
                    paths.append(path.name)
                    if len(paths) > 10000:
                        raise ValueError('too_many_checkpoints')
        checkpoint_count = len(paths)
        for name in sorted(paths, key=lambda v: int(v[5:-5]))[-100:]:
            receipt = snap.read('checkpoints/' + name, limit=256 * 1024)
            if receipt is not None:
                summary = pick(receipt, ('run_id', 'step', 'manifest_sha256'))
                summary['id'] = name[:-5]
                summary['matches_run'] = (
                    bool(actual_hash)
                    and receipt.get('run_id') == uid
                    and receipt.get('manifest_sha256') == actual_hash
                )
                receipts.append(summary)
                if not summary['matches_run']:
                    snap.issue('checkpoints/' + name, 'receipt_source_mismatch')
    except (OSError, ValueError):
        snap.issue('checkpoints', 'unreadable_record')
    parent = manifest.get('parent_study')
    resume = manifest.get('resume')
    result = dict(
        schema_version=1,
        kind='model-atelier-training-report',
        run_id=uid,
        capture_started_at=started,
        capture_finished_at=runs.now(),
        scope=dict(
            read_only=True,
            atomic_snapshot=False,
            payload_files_verified=False,
            images_included=False,
            weights_included=False,
            captions_included=False,
            local_paths_included=False,
            logs_included=include_logs,
        ),
        observation=observation,
        manifest=dict(
            actual_sha256=actual_hash,
            matches_state=match,
            **pick(state, ('manifest_sha256',)),
            **pick(manifest, ('created_at',)),
        ),
        configuration=pick(manifest.get('configuration'), CONFIG),
        dataset=pick(
            manifest.get('dataset'),
            (
                'id',
                'version',
                'kind',
                'subject_id',
                'trigger',
                'train_count',
                'manifest_sha256',
                'bundle_sha256',
            ),
        ),
        base=pick(manifest.get('base'), ('id', 'version', 'architecture', 'sha256', 'size_bytes')),
        environment=pick(
            manifest.get('environment'),
            ('profile', 'profile_sha256', 'dependencies_sha256', 'trainer_revision', 'ready'),
        ),
        state=pick(
            state,
            (
                'status',
                'steps_completed',
                'last_checkpoint_step',
                'updated_at',
                'finished_at',
                'manifest_sha256',
            ),
        ),
        launch=pick(launch, ('started_at',)),
        parent_study=pick(parent, ('sha256',)) if isinstance(parent, dict) else None,
        resume=pick(resume, ('run_id', 'checkpoint', 'step', 'receipt_sha256'))
        if isinstance(resume, dict)
        else None,
        resources=resource_summary,
        artifact=artifact_summary,
        checkpoints=dict(
            record_count=checkpoint_count, retained=len(receipts), limit=100, receipts=receipts
        ),
        metadata_files=snap.files,
        issues=snap.issues,
    )
    env = manifest.get('environment')
    packages = env.get('packages') if isinstance(env, dict) else None
    result['environment']['packages'] = pick(
        packages,
        ('torch', 'torchvision', 'accelerate', 'diffusers', 'transformers', 'safetensors', 'numpy'),
    )
    if include_logs:
        result['log'] = snap.log()
        result['state_message'] = str(state.get('message', ''))[:4000]
        result['scope']['local_paths_included'] = 'possible_in_log_or_message'
    result['capture_finished_at'] = runs.now()
    return result


def encode(report):
    raw = json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False).encode('utf-8')
    if len(raw) > MAX_REPORT:
        raise ValueError('訓練報告超過 1 MiB，請先檢查本機紀錄；不自動裁掉必要來源。')
    return raw
