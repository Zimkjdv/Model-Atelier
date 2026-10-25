"""Read-only resource evidence registry; inference and training stay separate."""

import argparse
import copy
import json
import math
from pathlib import Path
import re

from backend import training_files, training_runs
from scripts import verify_local_generation as base

DEFINITIONS = dict(
    inference_engine_time='Original-engine history start to terminal event, including loading/cache/decoding.',
    inference_engine_ram='Shared engine-host total minus free, sampled by the platform; not process RSS.',
    inference_engine_device='Engine total minus free; may include reclaimable allocator cache.',
    nvidia_memory='Sampled whole-card memory.used; includes desktop and other programs; may miss peaks.',
    training_time='Worker monotonic elapsed time including validation, import, preprocessing, training and saving.',
    training_allocator='Dedicated training-process PyTorch allocated/reserved high-water marks after reset.',
    training_ram='Sampled worker RSS and observed Windows peak working-set counter; not whole-host RAM.',
    unknown='Missing/invalid metrics stay null; no zero substitution or minimum-memory inference.',
)


def amount(value):
    return value if type(value) is int and value >= 0 else None


def sampled_max(rows, field):
    values = [value for row in rows if (value := amount(row.get(field))) is not None]
    return max(values) if values else None


def training_record(manifest, inspection, resources, artifacts, hardware):
    identifier = manifest['run_id']
    if (
        inspection.get('run_id') != identifier
        or inspection.get('status') != 'completed'
        or inspection.get('resources_released') is not True
        or inspection.get('state', {}).get('steps_completed')
        != manifest['configuration']['max_steps']
        or artifacts.get('run_id') != identifier
        or artifacts.get('manifest_sha256') != inspection.get('manifest_sha256')
        or 'model.safetensors' not in artifacts.get('files', {})
    ):
        raise ValueError(
            'Completed original training, final artifact and released resources required'
        )
    rows = resources.get('samples') or []
    elapsed = resources.get('elapsed_seconds')
    elapsed = (
        elapsed
        if type(elapsed) in (int, float) and math.isfinite(elapsed) and elapsed >= 0
        else None
    )
    state = inspection['state']
    return dict(
        schema_version=1,
        workload_kind='training',
        run_id=identifier,
        manifest_sha256=inspection['manifest_sha256'],
        configuration=copy.deepcopy(manifest['configuration']),
        dataset=copy.deepcopy(manifest['dataset']),
        base=copy.deepcopy(manifest['base']),
        environment=copy.deepcopy(manifest['environment']),
        hardware=copy.deepcopy(hardware),
        device_observation=state.get('device_observation'),
        torch_version=state.get('torch_version'),
        cuda_runtime=state.get('cuda_runtime'),
        resume=copy.deepcopy(manifest.get('resume')),
        status=inspection['status'],
        resources_released=True,
        elapsed_seconds=elapsed,
        sample_count=len(rows),
        valid_rss_samples=sum(amount(r.get('rss_bytes')) is not None for r in rows),
        valid_nvidia_samples=sum(amount(r.get('whole_gpu_used_bytes')) is not None for r in rows),
        observed_max_rss_bytes=sampled_max(rows, 'rss_bytes'),
        observed_max_process_peak_working_set_bytes=sampled_max(
            rows, 'process_peak_working_set_bytes'
        ),
        observed_max_whole_gpu_used_bytes=sampled_max(rows, 'whole_gpu_used_bytes'),
        torch_peak_allocated_bytes=amount(resources.get('torch_peak_allocated_bytes')),
        torch_peak_reserved_bytes=amount(resources.get('torch_peak_reserved_bytes')),
        task_vram_peak_bytes=None,
        artifacts=copy.deepcopy(artifacts),
        definitions=copy.deepcopy(DEFINITIONS),
    )


def read_training(run_id, hardware, *, root=training_runs.ROOT):
    folder = training_runs.run_directory(run_id, root)
    inspection = training_runs.inspect(run_id, root=root)
    read = training_files.read_json
    manifest, resources, artifacts = [
        read(folder / name) for name in ('manifest.json', 'resources.json', 'artifacts.json')
    ]
    if (
        read(folder / 'output/model-state/train_state.json')['current_step']
        != manifest['configuration']['max_steps']
    ):
        raise ValueError('Final sealed trainer state did not reach the frozen step budget')
    for name, identity in artifacts['files'].items():
        path = folder / 'output' / name
        if (
            path.is_symlink()
            or not path.resolve().is_relative_to((folder / 'output').resolve())
            or path.stat().st_size != identity['size_bytes']
            or training_files.digest(path) != identity['sha256']
        ):
            raise ValueError('Original training artifact checksum differs')
    result = training_record(manifest, inspection, resources, artifacts, hardware)
    result['trainer_arguments'] = read(folder / 'trainer-arguments.json')['arguments']
    result['final_sealed_step'] = read(folder / 'output/model-state/train_state.json')[
        'current_step'
    ]
    result['observed_training_buckets'] = [
        dict(bucket=int(bucket), width=int(width), height=int(height))
        for bucket, width, height in re.findall(
            r'bucket (\d+): resolution \((\d+), (\d+)\)',
            (folder / 'worker.log').read_text(encoding='utf-8'),
        )
    ] or None
    result['evidence_sha256'] = {
        name: training_files.digest(folder / name)
        for name in (
            'manifest.json',
            'resources.json',
            'state.json',
            'artifacts.json',
            'worker.log',
            'trainer-arguments.json',
        )
    }
    result['integration_source_sha256'] = {
        name: training_files.digest(Path(root) / name)
        for name in (
            'scripts/training_worker.py',
            'scripts/training_fixture.py',
            'backend/training_runs.py',
            'backend/training_environment.py',
        )
    }
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-id', required=True)
    parser.add_argument(
        '--hardware', type=Path, required=True, help='Timestamped platform host snapshot JSON'
    )
    parser.add_argument('--report', required=True)
    args = parser.parse_args(argv)
    target = base.report_path(args.report)
    result = read_training(args.run_id, training_files.read_json(args.hardware))
    base.reserve_report(target)
    base.write_report(target, result)
    print(json.dumps(dict(run_id=args.run_id, status=result['status'], report=str(target))))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
