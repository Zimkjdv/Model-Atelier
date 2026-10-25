"""F03 fixed-profile HTTP acceptance. Offline verification performs GET requests only."""

import argparse
import copy
import hashlib
import io
import json
import sys
import time
from uuid import UUID, uuid4

import httpx
from PIL import Image

from backend import flux_observation, flux_workflows
from scripts.verify_local_generation import (
    local_url,
    report_path,
    reserve_report,
    utc_now,
    write_report,
)


class Acceptance:
    def __init__(self, client, engine, *, emit=lambda value: None, max_wait=900, interval=2):
        self.client, self.engine, self.emit = client, local_url(engine), emit
        self.max_wait, self.interval = max_wait, interval

    def api(self, method, path, **kwargs):
        result = self.client.request(method, '/api/' + path, timeout=30, **kwargs)
        result.raise_for_status()
        return result.json()

    def verify(self, report):
        settings = flux_workflows.Input(**report['settings']).model_dump()
        if settings['engine_url'] != self.engine or report['status'] != 'passed':
            raise ValueError('Report identity or successful original result missing')
        UUID(report['job_id'])
        expected = flux_workflows.build(settings)
        job = self.api('GET', 'jobs/' + report['job_id'])
        if (
            job['id'] != report['job_id']
            or job['engine_url'] != self.engine
            or job['status'] != 'completed'
            or job['workflow'] != expected
            or job['workflow_id'] != flux_workflows.WORKFLOW_ID
            or job['component_metadata'] != report['component_metadata']
            or job['runtime_metadata'] != report['runtime_metadata']
            or job['history']['status']['status_str'] != 'success'
        ):
            raise ValueError('Original job, full graph or immutable snapshots differ')
        if self.api('GET', 'jobs/' + job['id'] + '/workflow') != expected:
            raise ValueError('Exported graph differs')
        if len(report['artworks']) != 1:
            raise ValueError('Expected exactly one original artwork')
        for original in report['artworks']:
            UUID(original['id'])
            prefix = 'artworks/' + original['id']
            item = self.api('GET', prefix)
            response = self.client.get('/api/' + prefix + '/image', timeout=30)
            response.raise_for_status()
            raw = response.content
            with Image.open(io.BytesIO(raw)) as image:
                image.load()
                if image.size != (settings['width'], settings['height']):
                    raise ValueError('Saved image dimensions differ')
            if (
                hashlib.sha256(raw).hexdigest() != original['sha256']
                or item['sha256'] != original['sha256']
                or len(raw) != original['bytes']
                or item['job_id'] != job['id']
                or self.api('GET', prefix + '/workflow') != expected
                or item['component_metadata'] != job['component_metadata']
                or item['runtime_metadata'] != job['runtime_metadata']
            ):
                raise ValueError('Saved artwork content or provenance differs')
            restored = self.api('GET', 'flux/' + prefix + '/creation-settings')
            if any(
                restored['settings'][key] != value
                for key, value in settings.items()
                if key != 'title'
            ):
                raise ValueError('Restored settings differ')
            if type(restored['settings']['seed']) is not str:
                raise ValueError('64-bit seed was not restored as text')
        return dict(status='passed', verified_at=utc_now(), job_id=job['id'], requests='GET only')

    def run(self, *, changes=None, expected_failure=None):
        self.report = None
        try:
            return self._run(changes=changes, expected_failure=expected_failure)
        except BaseException as exc:
            if self.report is not None:
                self.report.update(
                    status='failed',
                    error=str(exc),
                    recovery='Query the original UUID; never automatically replay',
                )
                self.emit(copy.deepcopy(self.report))
            raise

    def _run(self, *, changes=None, expected_failure=None):
        settings = flux_workflows.Input(
            **(flux_observation.SETTINGS | {'engine_url': self.engine} | (changes or {}))
        ).model_dump()
        report = dict(
            schema_version=1,
            status='running',
            settings=settings,
            job_id=str(uuid4()),
            started_at=utc_now(),
            expected_failure=expected_failure,
        )
        self.report = report
        self.emit(copy.deepcopy(report))  # Persist identity before any remote write.
        started = time.monotonic()
        submitted = self.api(
            'POST', 'flux/generate', json=settings | {'request_id': report['job_id']}
        )
        report['initial_status'] = submitted['status']
        if submitted['id'] != report['job_id']:
            raise ValueError('Original request ID changed')
        while True:
            self.api('POST', 'jobs/' + report['job_id'] + '/refresh')
            job = self.api('GET', 'jobs/' + report['job_id'])
            if job['status'] in ('completed', 'failed', 'cancelled', 'stopped'):
                break
            if time.monotonic() - started > self.max_wait:
                raise TimeoutError('Original UUID retained; never automatically resubmit')
            time.sleep(self.interval)
        report.update(
            terminal_job=job,
            component_metadata=job['component_metadata'],
            runtime_metadata=job['runtime_metadata'],
            elapsed_seconds=time.monotonic() - started,
        )
        if expected_failure:
            if job['status'] != 'failed' or job['failure_info']['code'] != expected_failure:
                raise ValueError('Expected confirmed failure was not observed')
            restored = self.api('GET', 'flux/jobs/' + job['id'] + '/creation-settings')
            if any(
                restored['settings'][key] != value
                for key, value in settings.items()
                if key != 'title'
            ):
                raise ValueError('Failed job lost original settings')
            # The same UUID is a read of the ledger, never a retry.
            recovered = self.api('POST', 'flux/generate', json=settings | {'request_id': job['id']})
            if recovered != job:
                raise ValueError('Original failed UUID was changed')
            report.update(status='passed', restored=restored)
        else:
            if job['status'] != 'completed':
                raise ValueError('Generation failed: ' + str(job.get('failure_info')))
            imported = self.api('POST', 'jobs/' + job['id'] + '/artworks')
            if imported['errors']:
                raise ValueError('Artwork import failed')
            report['artworks'] = []
            for item in imported['imported'] + imported['existing']:
                response = self.client.get('/api/artworks/' + item['id'] + '/image', timeout=30)
                response.raise_for_status()
                report['artworks'].append(
                    dict(
                        id=item['id'],
                        bytes=len(response.content),
                        sha256=hashlib.sha256(response.content).hexdigest(),
                    )
                )
            report['status'] = 'passed'
            report['verification'] = self.verify(report)
        self.emit(copy.deepcopy(report))
        return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--platform', default='http://127.0.0.1:8000')
    parser.add_argument('--expected-engine', default='http://127.0.0.1:8188')
    parser.add_argument('--report', default='runtime/flux-generation.json')
    parser.add_argument('--verify-report', action='store_true')
    args = parser.parse_args(argv)
    path = report_path(args.report)
    previous = json.loads(path.read_text(encoding='utf-8')) if args.verify_report else None
    if previous is None:
        reserve_report(path)
    with httpx.Client(base_url=local_url(args.platform), trust_env=False) as client:
        runner = Acceptance(
            client, args.expected_engine, emit=lambda value: write_report(path, value)
        )
        result = runner.verify(previous) if previous is not None else runner.run()
    print(json.dumps({key: result.get(key) for key in ('status', 'job_id', 'requests')}))
    return 0


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    raise SystemExit(main())
