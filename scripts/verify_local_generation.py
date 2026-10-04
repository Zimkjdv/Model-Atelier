"""Run one local generation acceptance, or verify its durable outputs with GETs.

This is an acceptance check, not a pure GPU benchmark. A lost submission response
is reconciled using the original UUID; it is never submitted a second time.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import io
import json
import os
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit
from uuid import UUID, uuid4

import httpx
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from backend.workflows import build

SEED = '9007199254740993'
PROMPT = ('score_9,score_8_up,score_7_up,rating_safe,source_anime,landscape,'
          'mountain lake,pine forest,blue sky,peaceful daylight,scenery,no humans')
NEGATIVE = 'people,person,character,animal,text,watermark'
INTERVAL = 2.0
MAX_WAIT = 900.0


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def local_url(value):
    parsed = urlsplit(value)
    if (parsed.scheme != 'http' or parsed.hostname not in ('127.0.0.1', 'localhost', '::1')
            or parsed.username or parsed.password or parsed.query or parsed.fragment
            or parsed.path not in ('', '/') or parsed.port is None):
        raise ValueError('Acceptance URLs must be HTTP loopback URLs with an explicit port')
    return value.rstrip('/')


def report_path(value):
    root = ROOT.resolve()
    runtime = root / 'runtime'
    candidate = root / value if not Path(value).is_absolute() else Path(value)
    for part in (candidate, *candidate.parents):
        if part == root:
            break
        if part.is_symlink() or (hasattr(part, 'is_junction') and part.is_junction()):
            raise ValueError('Report paths may not contain symlinks or junctions')
    target = candidate.resolve()
    if not runtime.is_relative_to(root) or not target.is_relative_to(runtime) or target.suffix.lower() != '.json':
        raise ValueError('Reports must be .json files inside this project runtime directory')
    return target


def write_report(path, value):
    path = report_path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path = report_path(path)
    # An exclusively created random sibling never follows a predictable .tmp
    # symlink. Recheck confinement before replacing the report itself.
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=path.parent,
                                         prefix=path.name + '.', suffix='.tmp', delete=False) as stream:
            temporary = Path(stream.name)
            json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
            stream.flush()
            os.fsync(stream.fileno())
        if temporary.is_symlink() or not temporary.resolve().is_relative_to((ROOT.resolve() / 'runtime')):
            raise ValueError('Temporary report path escaped runtime')
        os.replace(temporary, report_path(path))
    finally:
        if (temporary is not None and temporary.exists()
                and temporary.resolve().is_relative_to(ROOT.resolve() / 'runtime')):
            temporary.unlink()


def reserve_report(path):
    """Atomically admit one invocation before it can contact the generation API."""
    path = report_path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path = report_path(path)
    with path.open('x', encoding='utf-8') as stream:
        json.dump(dict(schema_version=1, status='reserved', stage='arguments', job_id=None,
                       request_id=None, reserved_at=utc_now()), stream)
        stream.flush()
        os.fsync(stream.fileno())


def settings(engine, checkpoint):
    return dict(title='Pony V6 XL local GPU acceptance', engine_url=engine, checkpoint=checkpoint,
                prompt=PROMPT, negative_prompt=NEGATIVE, seed=SEED, width=768, height=768,
                steps=20, cfg=5.5, sampler_name='dpmpp_2m', scheduler='karras', denoise=1.0,
                reference_ids=[])


class Acceptance:
    def __init__(self, client, engine, checkpoint, *, emit=None, clock=time.monotonic,
                 sleep=time.sleep, max_wait=MAX_WAIT, interval=INTERVAL):
        self.client = client
        self.engine = local_url(engine)
        self.checkpoint = checkpoint
        self.emit = emit or (lambda value: None)
        self.clock, self.sleep = clock, sleep
        if not 0 < max_wait <= MAX_WAIT or interval < INTERVAL:
            raise ValueError('Wait may not exceed 15 minutes; polling interval must be at least 2 seconds')
        self.max_wait, self.interval = max_wait, interval
        self.report = {}
        self.original_artworks = None

    def expected_settings(self):
        return settings(self.engine, self.checkpoint)

    def preflight(self):
        """Additional fixed-profile checks, before admitting a generation UUID."""

    def validate_report(self, value):
        """Validate all integrity anchors before emitting or contacting a server."""
        def identity(text):
            return isinstance(text, str) and str(UUID(text)) == text
        if (not isinstance(value, dict) or type(value.get('schema_version')) is not int
                or value['schema_version'] != 1 or value.get('expected_engine') != self.engine
                or value.get('settings') != self.expected_settings()
                or value.get('mode') not in ('generate', 'verify_report')
                or value.get('status') not in ('passed', 'failed')):
            raise ValueError('Report schema or fixed acceptance settings do not match this invocation')
        local_url(value['platform'])
        original_settings = value['settings']
        if (any(type(original_settings[name]) is not int for name in ('width', 'height', 'steps'))
                or any(type(original_settings[name]) not in (int, float) for name in ('cfg', 'denoise'))
                or type(original_settings['seed']) is not str):
            raise ValueError('Report original parameter types are invalid')
        if not identity(value.get('job_id')) or value.get('request_id') != value['job_id']:
            raise ValueError('Report job/request identity is invalid')
        ids = value.get('artwork_ids')
        if not isinstance(ids, list) or len(ids) != 1 or not all(identity(item) for item in ids):
            raise ValueError('Report must identify exactly one saved artwork')
        version = value.get('model_version')
        if not isinstance(version, str) or not version or len(version) > 100:
            raise ValueError('Report original model version is invalid')
        expected = build(value['settings'])
        if value.get('workflow') != expected or type(value['workflow']['5']['inputs']['seed']) is not int:
            raise ValueError('Report full workflow or exact seed is invalid')
        entries = value.get('verified_artworks')
        if not isinstance(entries, list) or len(entries) != 1 or entries[0].get('id') != ids[0]:
            raise ValueError('Report artwork integrity entries do not match saved IDs')
        entry = entries[0]
        digest = entry.get('sha256')
        restored = entry.get('restore_settings')
        if not isinstance(restored, dict):
            raise ValueError('Report original restored settings are missing')
        # Schema 1 reports created before this hardening stored the version in
        # restore_settings. Keep that original report fully compatible.
        entry_version = entry.get('model_version', restored.get('model_version'))
        if (not isinstance(digest, str) or len(digest) != 64 or any(c not in '0123456789abcdef' for c in digest)
                or type(entry.get('bytes')) is not int or not 0 < entry['bytes'] <= 32 * 1024 * 1024
                or entry.get('width') != 768 or entry.get('height') != 768 or entry_version != version):
            raise ValueError('Report artwork checksum, size, dimensions or model version is invalid')
        if not isinstance(restored.get('settings'), dict) or any(
                restored['settings'].get(name) != expected_value
                for name, expected_value in value['settings'].items() if name != 'title'):
            raise ValueError('Report original restored parameters are invalid')

    def record(self, stage, **changes):
        self.report.update(stage=stage, updated_at=utc_now(), **changes)
        self.emit(self.report)

    def request(self, method, path, *, deadline=None, **kwargs):
        timeout = 30.0 if deadline is None else min(30.0, deadline - self.clock())
        if timeout <= 0:
            raise TimeoutError('15-minute generation observation deadline exceeded; do not replay the request')
        response = self.client.request(method, '/api/' + path, timeout=timeout, **kwargs)
        response.raise_for_status()
        return response

    def json(self, method, path, **kwargs):
        value = self.request(method, path, **kwargs).json()
        if not isinstance(value, (dict, list)):
            raise ValueError(path + ': invalid JSON response')
        return value

    def warning(self, message):
        samples = self.report.setdefault('warnings', [])
        if message not in samples and len(samples) < 10:
            samples.append(message)

    def sample(self, deadline=None):
        """Observe aggregate device memory; this is not process-exclusive VRAM."""
        metric = self.report['vram_sampling']
        metric['attempts'] += 1
        sample = dict(at=utc_now(), elapsed_seconds=round(self.clock() - self.started, 3), gpus=[])
        try:
            value = self.json('GET', 'system', deadline=deadline)
            if 'platform_system' not in self.report:
                self.report['platform_system'] = value
            for gpu in value.get('gpus', []):
                used = gpu.get('used')
                if type(used) is int and used >= 0:
                    key = str(gpu.get('index', 'unknown'))
                    sample['gpus'].append(dict(index=key, name=gpu.get('name'), used_bytes=used))
                    metric['sampled_max_used_bytes_by_gpu'][key] = max(used, metric['sampled_max_used_bytes_by_gpu'].get(key, 0))
            if not sample['gpus']:
                self.warning('NVIDIA aggregate used-memory sample unavailable; an absent peak is not zero VRAM')
        except (httpx.HTTPError, ValueError, TypeError, AttributeError) as exc:
            self.warning('VRAM sampling unavailable: ' + str(exc))
        metric['samples'].append(sample)
        metric['samples_with_gpu_values'] += bool(sample['gpus'])

    def assert_job(self, value, expected):
        if value.get('id') != self.report['job_id'] or value.get('engine_url') != self.engine or value.get('checkpoint') != self.checkpoint:
            raise ValueError('Job identity, original engine or checkpoint changed')
        workflow = value.get('workflow')
        if workflow != expected or type(workflow['5']['inputs']['seed']) is not int or workflow['5']['inputs']['seed'] != int(SEED):
            raise ValueError('The full saved workflow or exact 64-bit seed differs from the submitted settings')

    def verify_artworks(self, expected):
        verified = []
        for artwork_id in self.report['artwork_ids']:
            UUID(artwork_id)
            prefix = 'artworks/' + artwork_id
            item = self.json('GET', prefix)
            if (item.get('id') != artwork_id or item.get('job_id') != self.report['job_id']
                    or item.get('engine_url') != self.engine or item.get('checkpoint') != self.checkpoint
                    or item.get('model_version') != self.report['model_version']
                    or item.get('width') != 768 or item.get('height') != 768 or item.get('image_available') is not True):
                raise ValueError('Artwork identity, dimensions or locally saved image availability mismatch')
            workflow = self.json('GET', prefix + '/workflow')
            if workflow != expected or type(workflow['5']['inputs']['seed']) is not int:
                raise ValueError('Artwork workflow or seed precision mismatch')
            raw = self.request('GET', prefix + '/image').content
            with Image.open(io.BytesIO(raw)) as image:
                image.verify()
            with Image.open(io.BytesIO(raw)) as image:
                if image.size != (768, 768) or getattr(image, 'n_frames', 1) != 1:
                    raise ValueError('Generated image is not a valid single 768 x 768 image')
                image.load()
                image_format = image.format
            digest = hashlib.sha256(raw).hexdigest()
            if item.get('sha256') != digest:
                raise ValueError('Artwork image checksum differs from its stored metadata')
            if self.original_artworks is not None:
                original = self.original_artworks.get(artwork_id)
                if original is None or original['sha256'] != digest or original['bytes'] != len(raw):
                    raise ValueError('Artwork ID, checksum or byte length differs from the original verified report')
            restored = self.json('GET', prefix + '/creation-settings')
            for name, value in self.report['settings'].items():
                if name != 'title' and restored.get('settings', {}).get(name) != value:
                    raise ValueError('Restored creation parameter differs: ' + name)
            if type(restored['settings'].get('seed')) is not str or restored.get('model_version') != self.report['model_version']:
                raise ValueError('Restored seed type or original model version mismatch')
            verified.append(dict(id=artwork_id, sha256=digest, bytes=len(raw), format=image_format,
                                 width=768, height=768, model_version=self.report['model_version'], restore_settings=restored))
        if not verified:
            raise ValueError('No saved artwork available to verify')
        self.report['verified_artworks'] = verified

    def run(self, previous=None):
        verify = previous is not None
        if verify:
            try:
                self.validate_report(previous)
            except (KeyError, ValueError, TypeError, AttributeError) as exc:
                # Return a diagnostic without emitting: invalid input JSON must
                # never be replaced with a failed verification report.
                self.report = dict(status='failed', stage='validate_report', mode='verify_report', error=str(exc),
                                   job_id=previous.get('job_id') if isinstance(previous, dict) else None)
                return self.report
        self.report = copy.deepcopy(previous) if verify else dict(schema_version=1, status='running', mode='generate',
                                                       platform=str(self.client.base_url).rstrip('/'), expected_engine=self.engine,
                                                       settings=self.expected_settings(), started_at=utc_now(),
                                                       job_id=None, request_id=None, artwork_ids=[])
        if verify:
            self.report['mode'] = 'verify_report'
            self.original_artworks = {item['id']: copy.deepcopy(item) for item in previous['verified_artworks']}
        try:
            if verify:
                self.record('verify_report', status='running', error=None)
            else:
                self.record('preflight')
                if self.json('GET', 'health').get('status') != 'ok':
                    raise ValueError('Platform health check failed')
                if self.json('GET', 'settings').get('comfy_url') != self.engine:
                    raise ValueError('Platform settings do not point to the expected original engine')
                engine = self.json('GET', 'engine')
                if engine.get('connected') is not True or engine.get('url') != self.engine:
                    raise ValueError('Expected ComfyUI engine is not connected')
                self.report['engine_stats'] = engine['stats']
                if not any(device.get('type') == 'cuda' for device in engine['stats'].get('devices', [])):
                    raise ValueError('This NVIDIA GPU acceptance requires an original-engine CUDA device; CPU fallback is not a GPU pass')
                catalog = self.json('POST', 'models/sync')
                if (catalog.get('engine_url') != self.engine or catalog.get('sync_error')
                        or not any(item.get('name') == self.checkpoint and item.get('listed') is True for item in catalog.get('models', []))):
                    raise ValueError('Checkpoint is not present in a successful fresh original-engine model sync')
                caps = self.json('POST', 'engine/capabilities/sync')
                if (caps.get('engine_url') != self.engine or caps.get('available') is not True
                        or caps.get('stale') is not False or caps.get('engine_matches') is not True
                        or self.report['settings']['sampler_name'] not in caps.get('sampler_names', [])
                        or self.report['settings']['scheduler'] not in caps.get('schedulers', [])):
                    raise ValueError('Fresh original-engine KSampler capability check failed')
                for name in ('steps', 'cfg', 'denoise'):
                    bound = caps.get('bounds', {}).get(name, {})
                    if not bound.get('min', float('inf')) <= self.report['settings'][name] <= bound.get('max', -float('inf')):
                        raise ValueError('Fixed acceptance parameter is outside fresh capability bounds: ' + name)
                self.report['capabilities'] = caps
                self.preflight()
                self.report['workflow'] = build(self.report['settings'])
                self.report['job_id'] = self.report['request_id'] = str(uuid4())
                self.report['vram_sampling'] = dict(requested_interval_seconds=self.interval,
                    source='platform /api/system NVIDIA aggregate device used memory; sampled peak, not continuous or process-exclusive',
                    attempts=0, samples_with_gpu_values=0, samples=[], sampled_max_used_bytes_by_gpu={})
                self.started = self.clock()
                self.sample()
                self.record('submit_once')  # Persist the UUID before any ambiguous remote write.
                submitted_at = self.clock()
                deadline = submitted_at + self.max_wait
                try:
                    response = self.json('POST', 'generate', deadline=deadline,
                                         json=self.report['settings'] | {'request_id': self.report['request_id']})
                    if response.get('id') != self.report['job_id']:
                        raise ValueError('Submission response returned another job ID')
                except httpx.RequestError as exc:
                    self.report['submission_transport_error'] = str(exc)
                    self.warning('Submission response lost; only the original UUID will be queried, never resubmitted')
                self.record('poll_history')
                while True:
                    self.sample(deadline)
                    try:
                        self.json('POST', 'jobs/' + self.report['job_id'] + '/refresh', deadline=deadline)
                    except httpx.HTTPError as exc:
                        self.warning('Refresh temporarily unavailable: ' + str(exc))
                    try:
                        job = self.json('GET', 'jobs/' + self.report['job_id'], deadline=deadline)
                    except httpx.HTTPError as exc:
                        if not isinstance(exc, httpx.HTTPStatusError) or exc.response.status_code != 404:
                            self.warning('Original job query temporarily unavailable: ' + str(exc))
                        job = None
                    if job:
                        self.assert_job(job, build(self.report['settings']))
                        self.report['last_job_status'] = job.get('status')
                        if job.get('status') == 'completed':
                            history = job.get('history') or {}
                            if history.get('status', {}).get('completed') is not True or history.get('status', {}).get('status_str') != 'success':
                                raise ValueError('Completed job lacks confirmed successful history')
                            self.report['submission_to_history_wall_seconds'] = round(self.clock() - submitted_at, 3)
                            self.report['timing_scope'] = 'From one submission HTTP request to observed successful history; includes queue, network, sampling and reconciliation, not pure GPU inference'
                            self.report['model_version'] = job.get('model_version') or '未知'
                            break
                        if job.get('status') in ('failed', 'cancelled'):
                            raise ValueError('Generation ended without success: ' + str(job.get('error') or job['status']))
                    self.record('poll_history')
                    remaining = deadline - self.clock()
                    if remaining <= 0:
                        raise TimeoutError('15-minute generation observation deadline exceeded; original UUID retained, never replay')
                    self.sleep(min(self.interval, remaining))
                self.record('import_artworks')
                imported = self.json('POST', 'jobs/' + self.report['job_id'] + '/artworks')
                self.report['import_response'] = imported
                if not isinstance(imported.get('errors'), list) or imported['errors']:
                    raise ValueError('Artwork import reported errors: ' + json.dumps(imported.get('errors'), ensure_ascii=False))
                values = imported.get('imported', []) + imported.get('existing', [])
                if len(values) != 1:
                    raise ValueError('Expected exactly one imported or already saved artwork')
                self.report['artwork_ids'] = [value['id'] for value in values]
            self.record('verify_saved_outputs')
            expected = build(self.report['settings'])
            job = self.json('GET', 'jobs/' + self.report['job_id'])
            self.assert_job(job, expected)
            history = job.get('history') or {}
            if (job.get('status') != 'completed' or not isinstance(history.get('status'), dict)
                    or history['status'].get('completed') is not True or history['status'].get('status_str') != 'success'
                    or job.get('model_version') != self.report['model_version']):
                raise ValueError('Saved job history success or original model version no longer matches the report')
            if self.json('GET', 'jobs/' + self.report['job_id'] + '/workflow') != expected:
                raise ValueError('Downloaded job workflow differs from the original complete JSON')
            self.report['workflow'] = expected
            self.verify_artworks(expected)
            self.record('complete', status='passed', error=None, verified_at=utc_now())
        except (Exception, KeyboardInterrupt) as exc:
            if isinstance(exc, httpx.HTTPStatusError):
                try:
                    self.report['api_error'] = exc.response.json()
                except ValueError:
                    self.report['api_error'] = {'status_code': exc.response.status_code}
            self.record(self.report.get('stage', 'initialization'), status='failed',
                        error=str(exc) or 'Acceptance interrupted; the original job may still be running',
                        manual_recovery='Inspect this original job ID in the platform; do not automatically replay /api/generate')
        return self.report


def main(argv=None, *, runner_type=Acceptance, default_report='runtime/pony-v6-xl-acceptance.json'):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--platform', default='http://127.0.0.1:8000')
    parser.add_argument('--expected-engine', default='http://127.0.0.1:8188')
    parser.add_argument('--checkpoint', default='pony-v6-xl.safetensors')
    parser.add_argument('--report', default=default_report)
    parser.add_argument('--verify-report', action='store_true', help='Only GET existing job/artwork records; no generation, sync or import')
    args = parser.parse_args(argv)
    runner = None
    path = None
    reserved = False
    try:
        path = report_path(args.report)
        previous = json.loads(path.read_text(encoding='utf-8')) if args.verify_report else None
        if not args.verify_report:
            try:
                reserve_report(path)
            except FileExistsError as exc:
                raise ValueError('Report already exists: use --verify-report or explicitly choose a new report filename; no generation was submitted') from exc
            reserved = True
        with httpx.Client(base_url=local_url(args.platform), trust_env=False, follow_redirects=False) as client:
            runner = runner_type(client, args.expected_engine, args.checkpoint, emit=lambda value: write_report(path, value))
            value = runner.run(previous)
        print(json.dumps({key: value.get(key) for key in ('status', 'stage', 'job_id', 'artwork_ids', 'error')}, ensure_ascii=False))
        return 0 if value['status'] == 'passed' else 1
    except (Exception, KeyboardInterrupt) as exc:
        # A full disk may prevent reporting; the original UUID is also printed.
        failure = dict(status='failed', stage=runner.report.get('stage') if runner else 'arguments',
                       job_id=runner.report.get('job_id') if runner else None, error=str(exc))
        if path is not None and runner is None and reserved:
            try:
                write_report(path, failure | {'schema_version': 1})
            except OSError:
                pass
        print(json.dumps(failure, ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
