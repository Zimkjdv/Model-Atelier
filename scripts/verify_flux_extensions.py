"""F04 four-case real HTTP acceptance; explicitly run with --run, never trains."""

import argparse
import hashlib
import io
import json
from pathlib import Path
import time
from uuid import uuid4

from PIL import Image, ImageDraw

from backend import flux_extensions as flow, flux_observation
from scripts import flux_acceptance_fixture as fixture, install_pony
from scripts.verify_flux_generation import Acceptance
from scripts.verify_local_generation import write_report


class ExtensionAcceptance(Acceptance):
    def verify_extension(self, report):
        value = flow.parse(report['settings'])
        expected = flow.build(value, report['job_id'])
        job = self.api('GET', 'jobs/' + report['job_id'])
        if (
            job['status'] != 'completed'
            or job['workflow'] != expected
            or job['reference_settings'] != report['settings']
            or job['history']['status']['status_str'] != 'success'
            or job['history']['status']['completed'] is not True
        ):
            raise ValueError('Saved extension graph, settings or successful history differs')
        for key in (
            'component_metadata',
            'lora_metadata',
            'reference_metadata',
            'runtime_metadata',
        ):
            if job[key] != report['job'][key]:
                raise ValueError('Immutable job snapshot changed: ' + key)
        for original in report['artworks']:
            prefix = 'artworks/' + original['id']
            item = self.api('GET', prefix)
            if item['job_id'] != job['id'] or self.api('GET', prefix + '/workflow') != expected:
                raise ValueError('Saved artwork ownership or full workflow differs')
            for key in (
                'component_metadata',
                'lora_metadata',
                'reference_metadata',
                'runtime_metadata',
                'reference_settings',
            ):
                if item[key] != job[key]:
                    raise ValueError('Immutable artwork snapshot differs: ' + key)
            restored = self.api('GET', 'flux/' + prefix + '/creation-settings')
            if (
                restored['settings'] != report['settings']
                or type(restored['settings']['seed']) is not str
            ):
                raise ValueError('Full extension settings were not restored')
            response = self.client.get('/api/' + prefix + '/image', timeout=30)
            response.raise_for_status()
            if (
                hashlib.sha256(response.content).hexdigest() != original['sha256']
                or item['sha256'] != original['sha256']
            ):
                raise ValueError('Original artwork PNG differs')
        return dict(status='passed', requests='GET only')

    def run_extension(self, value):
        identifier = str(uuid4())
        report = dict(status='running', job_id=identifier, settings=flow.settings(value))
        self.emit(report)
        try:
            started = time.monotonic()
            result = self.api(
                'POST',
                'flux/extensions/generate',
                json=report['settings'] | {'request_id': identifier},
            )
            if result['id'] != identifier:
                raise ValueError('Original UUID changed')
            while time.monotonic() - started < self.max_wait:
                self.api('POST', 'jobs/' + identifier + '/refresh')
                job = self.api('GET', 'jobs/' + identifier)
                if job['status'] in ('completed', 'failed', 'cancelled', 'stopped'):
                    break
                time.sleep(self.interval)
            else:
                raise TimeoutError('Original UUID retained; no automatic replay')
            report.update(job=job, elapsed_seconds=time.monotonic() - started)
            if job['status'] != 'completed':
                raise ValueError('Extension failed: ' + str(job.get('failure_info')))
            imported = self.api('POST', 'jobs/' + identifier + '/artworks')
            entries = imported['imported'] + imported['existing']
            if imported['errors'] or len(entries) != 1:
                raise ValueError('Expected exactly one saved artwork')
            report['artworks'] = []
            for item in entries:
                response = self.client.get('/api/artworks/' + item['id'] + '/image', timeout=30)
                response.raise_for_status()
                with Image.open(io.BytesIO(response.content)) as image:
                    image.load()
                    if image.size != (value.width, value.height):
                        raise ValueError('Output dimensions differ')
                    pixels = image.convert('RGB').tobytes()
                report['artworks'].append(
                    dict(
                        id=item['id'],
                        sha256=hashlib.sha256(response.content).hexdigest(),
                        pixel_sha256=hashlib.sha256(pixels).hexdigest(),
                        bytes=len(response.content),
                    )
                )
            report['status'] = 'passed'
            report['verification'] = self.verify_extension(report)
            return report
        except BaseException as exc:
            report.update(status='failed', error=str(exc))
            raise
        finally:
            self.emit(report)


def cases(directory, original_runner, report, engine):
    report['kind'] = 'F04 independent LoRA and VAE image-input acceptance'
    manifest = install_pony.load_manifest(flow.LORA_MANIFEST)
    target, _, _, lock = install_pony._paths(fixture.ROOT, manifest['filename'], create=False)
    if lock.exists() or not install_pony._verified(target, manifest):
        raise ValueError('Pinned LoRA must pass full hash verification')
    report['lora'] = manifest | {'current_file_verified': True}
    report['extension_sources'] = {
        name: hashlib.sha256((fixture.ROOT / name).read_bytes()).hexdigest()
        for name in (
            'scripts/verify_flux_extensions.py',
            'scripts/flux_lora_observer.py',
            'backend/flux_extensions.py',
        )
    }
    runner = ExtensionAcceptance(original_runner.client, original_runner.engine)
    inventory = runner.api('POST', 'loras/sync', json={'engine_url': runner.engine})
    if inventory['sync_error']:
        raise ValueError(inventory['sync_error'])
    runner.api(
        'PUT',
        'loras/metadata',
        json=dict(
            engine_url=runner.engine,
            name=manifest['filename'],
            architecture='flux',
            version=manifest['version'],
            sha256=manifest['sha256'],
            size_bytes=manifest['size_bytes'],
            source_url=manifest['source']['page_url'],
            license_name=manifest['license']['name'],
            license_url=manifest['license']['url'],
        ),
    )
    common = flux_observation.SETTINGS | dict(
        engine_url=runner.engine,
        title='F04 independent extensions',
        prompt='pvc figure, an adult woman with brown hair and green eyes wearing a long green coat, holding a book, white background, anime figurine',
    )
    values = [
        (
            'lora_zero',
            flow.LoraInput(
                **(
                    common
                    | dict(
                        workflow_id=flow.LORA_ID, lora_name=manifest['filename'], lora_strength=0.0
                    )
                )
            ),
        ),
        (
            'lora_enabled',
            flow.LoraInput(
                **(
                    common
                    | dict(
                        workflow_id=flow.LORA_ID, lora_name=manifest['filename'], lora_strength=0.7
                    )
                )
            ),
        ),
    ]
    for index in range(2):
        image = Image.new('RGB', (512, 512), '#8cc8ff')
        draw = ImageDraw.Draw(image)
        draw.rectangle((0, 320, 512, 512), fill='#55aa55')
        x = 70 if index == 0 else 290
        draw.rectangle((x, 200, x + 140, 365), fill='#ed6655')
        draw.polygon([(x - 20, 200), (x + 70, 100), (x + 160, 200)], fill='#555555')
        raw = io.BytesIO()
        image.save(raw, format='PNG')
        asset = runner.api(
            'POST',
            'assets',
            params={'filename': f'F04 synthetic house {index}.png'},
            content=raw.getvalue(),
        )
        values.append(
            (
                f'image_{index}',
                flow.ImageInput(
                    **(
                        common
                        | dict(
                            workflow_id=flow.IMAGE_ID,
                            image_asset_id=asset['id'],
                            denoise=0.6,
                            reference_resize='fit',
                            prompt='an anime illustration of a red house on a green hill under a blue sky',
                        )
                    )
                ),
            )
        )
    for name, value in values:
        print('F04 case: ' + name, flush=True)
        runner.emit = lambda data, name=name: write_report(directory / (name + '.json'), data)
        report['cases'][name] = runner.run_extension(value)
    for first, second in (('lora_zero', 'lora_enabled'), ('image_0', 'image_1')):
        if (
            report['cases'][first]['artworks'][0]['pixel_sha256']
            == report['cases'][second]['artworks'][0]['pixel_sha256']
        ):
            raise ValueError(
                'Expected a real pixel change, PNG metadata differences alone do not pass'
            )
    observations = [
        json.loads(line) for line in (directory / 'lora-observation.jsonl').read_text().splitlines()
    ]
    report['lora_observations'] = observations
    if not any(
        row['strength'] == 0.7 and row['patched_parameter_count'] > 0 for row in observations
    ):
        raise ValueError('Native model patch application was not observed')
    dispatches = [
        json.loads(line)['id'] for line in (directory / 'dispatch.jsonl').read_text().splitlines()
    ]
    if len(dispatches) != 4 or len(set(dispatches)) != 4:
        raise ValueError('Each extension case must dispatch once')
    report['dispatches'] = dispatches
    fixture.stop(engine)
    report['offline_verification'] = {
        name: runner.verify_extension(result) for name, result in report['cases'].items()
    }
    if len((directory / 'dispatch.jsonl').read_text().splitlines()) != 4:
        raise ValueError('Offline verification dispatched work')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', action='store_true')
    if not parser.parse_args().run:
        parser.error('--run is required to explicitly start GPU acceptance')
    return fixture.run(case_runner=cases)


if __name__ == '__main__':
    raise SystemExit(main())
