import copy
import io
import json
import unittest
from uuid import uuid4
from unittest.mock import patch
from PIL import Image
from backend import gallery, jobs, main, settings_transfer as transfer, test_api, flux_workflows, workflows


class SettingsTransferTests(unittest.TestCase):
    setUp = test_api.ApiTests.setUp
    tearDown = test_api.ApiTests.tearDown

    def settings(self):
        return main.DraftInput(title='中文設定', engine_url='http://127.0.0.1:8188',
            checkpoint='test.safetensors', seed='18446744073709551615', prompt='山林',
            loras=[dict(name='one.safetensors', strength_model=0.5, strength_clip=0),
                   dict(name='two.safetensors', enabled=False, strength_model=1.2, strength_clip=0.7)]).model_dump(mode='json', exclude={'revision'})

    def test_checkpoint_full_roundtrip_is_readonly_offline_and_preserves_precise_seed_order(self):
        settings = self.settings()
        before = self.db.read_bytes()
        with patch('backend.submissions.httpx.AsyncClient', side_effect=AssertionError('no engine during transfer')):
            exported = self.client.post('/api/creation-settings/export', json=dict(workflow_id=transfer.STANDARD, settings=settings))
            self.assertEqual(exported.status_code, 200, exported.text)
            self.assertIn('attachment', exported.headers['content-disposition'])
            imported = self.client.post('/api/creation-settings/import', content=exported.content).json()
        self.assertEqual(imported['bundle']['settings'], settings)
        self.assertEqual(imported['bundle']['settings']['seed'], '18446744073709551615')
        self.assertEqual(self.db.read_bytes(), before)
        self.assertEqual(self.client.get('/api/jobs').json(), [])
        self.assertEqual(self.client.get('/api/drafts').json(), [])

    def test_flux_roundtrip_preserves_its_own_fields_and_never_builds_gpu_job(self):
        settings = flux_workflows.Input(engine_url='http://127.0.0.1:9000', diffusion_model='flux.safetensors',
            clip_l='clip', t5xxl='t5', vae='vae', seed='9007199254740993', encoder_device='cpu', weight_dtype='fp8_e4m3fn').model_dump()
        exported = self.client.post('/api/creation-settings/export', json=dict(workflow_id=transfer.FLUX, settings=settings))
        self.assertEqual(exported.status_code, 200, exported.text)
        imported = self.client.post('/api/creation-settings/import', content=exported.content).json()
        self.assertEqual(imported['bundle']['settings'], settings)
        self.assertTrue(any('原引擎' in warning for warning in imported['warnings']))
        self.assertEqual(self.client.get('/api/flux/drafts').json(), [])
        self.assertEqual(self.client.get('/api/jobs').json(), [])

    def test_image_id_missing_on_other_machine_is_preserved_with_warning(self):
        identifier = str(uuid4())
        settings = self.settings() | dict(workflow_mode='image2image', image_asset_id=identifier,
                                          reference_ids=[identifier], reference_resize='stretch', denoise=0.123)
        response = self.client.post('/api/creation-settings/import', json=transfer.document(transfer.IMAGE, settings))
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()['bundle']['settings'], settings)
        self.assertTrue(any(identifier in warning for warning in response.json()['warnings']))
        self.assertEqual(self.client.get('/api/assets').json(), [])

    def test_malformed_unknown_incomplete_or_injected_files_do_not_write(self):
        original = transfer.document(transfer.STANDARD, self.settings())
        cases = [original | dict(schema_version=True), original | dict(schema_version=2),
                 original | dict(kind='arbitrary-workflow'), original | dict(workflow_id='unknown'),
                 original | dict(request_id=str(uuid4())), original | dict(source_snapshot=dict(workflow={})),
                 original | dict(settings=original['settings'] | dict(seed=2**64-1)),
                 original | dict(settings=original['settings'] | dict(seed='18446744073709551616')),
                 original | dict(settings=original['settings'] | dict(engine_url='http://user:password@localhost')),
                 original | dict(settings=original['settings'] | dict(workflow={})),
                 original | dict(settings=original['settings'] | dict(revision=1)),
                 original | dict(settings=original['settings'] | dict(width=True)),
                 original | dict(workflow_id=transfer.IMAGE),
                 original | dict(settings={k:v for k,v in original['settings'].items() if k!='steps'})]
        before = self.db.read_bytes()
        for value in cases:
            result = self.client.post('/api/creation-settings/import', json=value)
            self.assertEqual(result.status_code, 422, result.text)
        for raw in (b'{"kind":"model-atelier-creation","kind":"other"}', b'{"cfg":NaN}', b'[]', b'\xff'):
            self.assertEqual(self.client.post('/api/creation-settings/import', content=raw).status_code, 422)
        self.assertEqual(self.client.post('/api/creation-settings/import', content=b'x'*(transfer.MAX_BYTES+1)).status_code, 413)
        self.assertEqual(self.db.read_bytes(), before)

    def test_original_artwork_and_terminal_job_export_preserve_full_json_and_versions(self):
        settings = self.settings()
        identifier = str(uuid4())
        job, _ = jobs.reserve(self.db, identifier, settings['engine_url'], workflows.build(settings), settings['checkpoint'],
                             'original-v1', dict(name=settings['checkpoint'], version='original-v1'))
        job = jobs.update(self.db, identifier, status='completed')
        buffer = io.BytesIO()
        Image.new('RGB', (8, 8), 'white').save(buffer, 'PNG')
        source = dict(node_id='7', filename='result.png', subfolder='', type='output')
        artwork, _ = gallery.save(self.db, main.DATA/'artworks', job, source, buffer.getvalue())
        for kind, item in [('jobs', job), ('artworks', artwork)]:
            response = self.client.get(f'/api/{kind}/{item["id"]}/settings-export')
            self.assertEqual(response.status_code, 200, response.text)
            document = response.json()
            self.assertEqual(json.loads(document['source_snapshot']['workflow_json']), job['workflow'])
            self.assertEqual(document['source_snapshot']['model_version'], 'original-v1')
            self.assertEqual(document['settings']['loras'], [settings['loras'][0]])
            self.assertEqual(document['settings']['seed'], settings['seed'])
            imported = self.client.post('/api/creation-settings/import', content=response.content)
            self.assertEqual(imported.status_code, 200, imported.text)
            self.assertTrue(any('未核實' in value for value in imported.json()['warnings']))
        another, _ = jobs.reserve(self.db, str(uuid4()), settings['engine_url'], job['workflow'], settings['checkpoint'])
        self.assertEqual(self.client.get('/api/jobs/'+another['id']+'/settings-export').status_code, 409)
        changed = copy.deepcopy(job['workflow']); changed['99'] = dict(class_type='SaveImage', inputs=dict(images=['6',0]))
        other, _ = jobs.reserve(self.db, str(uuid4()), settings['engine_url'], changed, settings['checkpoint'])
        jobs.update(self.db, other['id'], status='failed')
        self.assertEqual(self.client.get('/api/jobs/'+other['id']+'/settings-export').status_code, 422)
