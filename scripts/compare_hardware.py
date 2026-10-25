"""Compare frozen inference observations; refuse ratios for unknown/mixed conditions.

This reads evidence only. It never probes hardware, submits work, or backfills jobs.
"""

import argparse
import copy
import hashlib
import json
import math
from pathlib import Path

from backend import job_measurements
from scripts import verify_local_generation as base

CONDITIONS = (
    'model_sha256',
    'model_dtype',
    'clip_dtype',
    'vae_dtype',
    'cache_state',
    'offload_policy',
    'comfy_commit',
    'torch_version',
    'component_sha256',
)


def digest(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()
    ).hexdigest()


def positive(value):
    return type(value) in (int, float) and math.isfinite(value) and value > 0


def observation(report, job, *, conditions, condition_sources):
    if (
        report.get('status') != 'passed'
        or job.get('status') != 'completed'
        or job.get('id') != report.get('job_id')
        or job.get('engine_url') != report.get('expected_engine')
        or digest(job.get('workflow')) != digest(report.get('workflow'))
    ):
        raise ValueError('A successful original job and matching report are required')
    workflow = report['workflow']
    samplers = [n['inputs'] for n in workflow.values() if n['class_type'] == 'KSampler']
    latents = [n['inputs'] for n in workflow.values() if n['class_type'] == 'EmptyLatentImage']
    if len(samplers) != 1 or len(latents) != 1 or latents[0]['batch_size'] != 1:
        raise ValueError('Only explicit single-batch checkpoint text2image observations supported')
    if (
        type(report['settings']['seed']) is not str
        or type(samplers[0]['seed']) is not int
        or samplers[0]['seed'] != int(report['settings']['seed'])
    ):
        raise ValueError('Exact string seed and original sampler must match')
    if set(conditions) != set(CONDITIONS) or set(condition_sources) != set(CONDITIONS):
        raise ValueError('Every comparison condition needs an explicit value and evidence source')
    # Older jobs remain unchanged: derive timing in this separate observation only.
    timing = job_measurements.engine_timing(job)
    metrics = dict(
        engine_execution_seconds=(timing['end'] - timing['start']) / 1000 if timing else None,
        submission_to_history_wall_seconds=report.get('submission_to_history_wall_seconds'),
        nvidia_whole_device_sampled_max_bytes=(report.get('vram_sampling') or {})
        .get('sampled_max_used_bytes_by_gpu', {})
        .get('0'),
        nvidia_samples=(report.get('vram_sampling') or {}).get('samples_with_gpu_values'),
        engine_continuous_resources=copy.deepcopy(
            (job.get('measurements') or {}).get('continuous_resources')
        ),
        task_vram_peak_bytes=None,
    )
    return dict(
        schema_version=1,
        workload_kind='inference',
        job_id=job['id'],
        report_sha256=digest(report),
        job_evidence_sha256=digest(job),
        workflow=copy.deepcopy(workflow),
        settings=copy.deepcopy(report['settings']),
        conditions=copy.deepcopy(conditions),
        condition_sources=copy.deepcopy(condition_sources),
        hardware=copy.deepcopy(report.get('platform_system')),
        engine_stats=copy.deepcopy(report.get('engine_stats')),
        metrics=metrics,
        artwork_hashes=[dict(id=a['id'], sha256=a['sha256']) for a in report['verified_artworks']],
    )


def compare(left, right):
    if any(
        v.get('schema_version') != 1 or v.get('workload_kind') != 'inference' for v in (left, right)
    ):
        raise ValueError('Two schema-1 inference observations required; training is separate')
    issues = []
    for name in CONDITIONS:
        a, b = left.get('conditions', {}).get(name), right.get('conditions', {}).get(name)
        sources = [v.get('condition_sources', {}).get(name) for v in (left, right)]
        # An explicitly verified empty addon list is known, not missing.
        if (
            a is None
            or b is None
            or a in ('', 'unknown')
            or b in ('', 'unknown')
            or not all(isinstance(source, str) and source.strip() for source in sources)
        ):
            issues.append(dict(field=name, reason='unknown'))
        elif digest(a) != digest(b):
            issues.append(dict(field=name, reason='different', left=a, right=b))
    for field in ('settings', 'workflow'):
        a, b = copy.deepcopy(left[field]), copy.deepcopy(right[field])
        if field == 'settings':
            for ignored in ('title', 'engine_url'):
                a.pop(ignored, None)
                b.pop(ignored, None)
        if digest(a) != digest(b):
            issues.append(dict(field=field, reason='different'))
    durations = [v['metrics'].get('engine_execution_seconds') for v in (left, right)]
    return dict(
        schema_version=1,
        matched_conditions=not issues,
        issues=issues,
        left_job_id=left['job_id'],
        right_job_id=right['job_id'],
        engine_time_ratio_left_over_right=(
            round(durations[0] / durations[1], 4)
            if not issues and all(positive(v) for v in durations)
            else None
        ),
        left_metrics=copy.deepcopy(left['metrics']),
        right_metrics=copy.deepcopy(right['metrics']),
        note='Single observations, including model loading and cache. OS/driver/background loads '
        'may differ; this is not an isolated GPU benchmark or minimum-memory guarantee.',
    )


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--left', type=Path, required=True)
    parser.add_argument('--right', type=Path, required=True)
    parser.add_argument('--report', required=True)
    args = parser.parse_args(argv)
    left, right = [json.loads(p.read_text(encoding='utf-8')) for p in (args.left, args.right)]
    result = compare(left, right)
    target = base.report_path(args.report)
    base.reserve_report(target)
    base.write_report(target, result)
    print(
        json.dumps(
            {
                key: result[key]
                for key in ('matched_conditions', 'issues', 'engine_time_ratio_left_over_right')
            },
            ensure_ascii=True,
        )
    )
    return 0 if result['matched_conditions'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
