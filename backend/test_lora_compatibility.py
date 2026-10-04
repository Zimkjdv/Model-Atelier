import itertools
import json
import sqlite3
import unittest
from contextlib import closing
from unittest.mock import patch

from backend import catalog, lora_compatibility, loras, main, test_api

ENGINE = 'http://127.0.0.1:8188'
CHECKPOINT = 'arbitrary.safetensors'
LORA = 'pony-flux-sdxl.safetensors'


class LoraCompatibilityTests(unittest.TestCase):
    setUp = test_api.ApiTests.setUp
    tearDown = test_api.ApiTests.tearDown

    def prepare(self, base='sdxl', kind='sdxl'):
        catalog.merge(self.db, ENGINE, [CHECKPOINT])
        catalog.update_metadata(self.db, ENGINE, CHECKPOINT, dict(architecture=base, version='base'))
        loras.merge(self.db, ENGINE, [LORA])
        loras.update_metadata(self.db, ENGINE, LORA, dict(architecture=kind, version='lora'))

    def get(self, engine=ENGINE, name=CHECKPOINT):
        return self.client.get('/api/loras/compatibility', params=dict(engine_url=engine, checkpoint=name))

    def rows(self):
        with closing(sqlite3.connect(self.db)) as db:
            return db.execute('SELECT key,value FROM settings ORDER BY key').fetchall()

    def test_all_architecture_pairs_use_registration_only_and_same_family_stays_untested(self):
        for base, kind in itertools.product(['unknown', 'sd1', 'sdxl', 'sd3', 'flux', 'other'], repeat=2):
            with self.subTest(base=base, kind=kind):
                self.prepare(base, kind)
                result = self.get()
                self.assertEqual(result.status_code, 200, result.text)
                data = result.json()
                item = data['loras'][0]
                expected = ('unverified' if base not in lora_compatibility.KNOWN or kind not in lora_compatibility.KNOWN
                            else 'compatible' if base == kind else 'incompatible')
                self.assertEqual(item['status'], expected)
                self.assertFalse(item['verified'])
                self.assertIn('未讀取權重', item['message'])
                self.assertEqual(data['workflow_supported'], base in ('sd1', 'sdxl', 'unknown'))
                self.assertEqual(data['source'], 'registered_architecture')
                if expected == 'compatible':
                    self.assertIn('未實測', item['label'])
                    self.assertIn('不保證', item['message'])

    def test_get_is_read_only_and_does_not_load_weights_contact_engine_or_inspect_gpu(self):
        self.prepare()
        before = self.rows()
        with (patch('backend.main.httpx.AsyncClient', side_effect=AssertionError('no engine access')),
              patch.object(main, 'gpu_info', side_effect=AssertionError('no GPU access'))):
            data = self.get().json()
        self.assertEqual(data['checkpoint']['metadata_updated_at'], catalog.read(self.db, ENGINE)['models'][0]['metadata_updated_at'])
        self.assertEqual(data['loras'][0]['metadata_updated_at'], loras.read(self.db, ENGINE)['loras'][0]['metadata_updated_at'])
        self.assertEqual(before, self.rows())

    def test_unlisted_or_failed_sync_cannot_display_same_architecture_as_compatible(self):
        self.prepare()
        loras.merge(self.db, ENGINE, [])
        self.assertEqual(self.get().json()['loras'][0]['status'], 'unverified')
        loras.merge(self.db, ENGINE, [LORA])
        catalog.merge(self.db, ENGINE, [])
        self.assertEqual(self.get().json()['loras'][0]['status'], 'unverified')
        catalog.merge(self.db, ENGINE, [CHECKPOINT])
        for collection in [loras, catalog]:
            if collection is loras:
                loras.mutate(self.db, ENGINE, lambda value: value.update(sync_error='offline'))
            else:
                loras.merge(self.db, ENGINE, [LORA])
                catalog.sync_error(self.db, ENGINE, 'offline')
            self.assertEqual(self.get().json()['loras'][0]['status'], 'unverified')
        loras.update_metadata(self.db, ENGINE, LORA, dict(architecture='flux'))
        self.assertEqual(self.get().json()['loras'][0]['status'], 'incompatible')

    def test_engine_scope_unknown_checkpoint_and_empty_lora_collection(self):
        self.prepare()
        self.assertEqual(self.get(name='missing').status_code, 404)
        self.assertEqual(self.get(engine='file:///test').status_code, 422)
        other = 'http://127.0.0.1:9000'
        self.client.put('/api/settings', json=dict(comfy_url=other))
        self.assertEqual(self.get().status_code, 409)
        self.assertEqual(self.get(engine=other).status_code, 404)
        catalog.merge(self.db, other, [CHECKPOINT])
        self.assertEqual(self.get(engine=other).json()['loras'], [])
        self.client.put('/api/settings', json=dict(comfy_url=ENGINE))
        self.assertEqual(self.get().json()['loras'][0]['status'], 'compatible')

    def test_invalid_legacy_architectures_and_other_do_not_guess_from_name_or_hash(self):
        self.prepare()
        for kind in [None, 'SDXL', 'invalid', True, ['sdxl']]:
            loras.update_metadata(self.db, ENGINE, LORA, dict(architecture=kind, sha256='a' * 64))
            item = self.get().json()['loras'][0]
            self.assertEqual(item['architecture'], 'unknown')
            self.assertEqual(item['status'], 'unverified')
        self.prepare('other', 'other')
        self.assertEqual(self.get().json()['loras'][0]['status'], 'unverified')

    def test_metadata_edits_recompute_assessment_without_persisting_a_verified_flag(self):
        self.prepare()
        first = self.get().json()['loras'][0]
        self.client.put('/api/loras/metadata', json=dict(engine_url=ENGINE, name=LORA, architecture='flux'))
        next_item = self.get().json()['loras'][0]
        self.assertEqual(next_item['status'], 'incompatible')
        self.assertNotEqual(next_item['metadata_updated_at'], first['metadata_updated_at'])
        self.client.put('/api/models/metadata', json=dict(engine_url=ENGINE, name=CHECKPOINT, architecture='flux'))
        self.assertEqual(self.get().json()['loras'][0]['status'], 'compatible')
        for key, value in self.rows():
            self.assertNotIn('verified', json.loads(value)['models'][0] if key.startswith('catalog:') else json.loads(value)['loras'][0])

    def test_engine_change_during_assessment_rejects_result(self):
        self.prepare()
        original = lora_compatibility.assess
        def changing(*args):
            result = original(*args)
            self.client.put('/api/settings', json=dict(comfy_url='http://127.0.0.1:9000'))
            return result
        with patch.object(lora_compatibility, 'assess', side_effect=changing):
            self.assertEqual(self.get().status_code, 409)

    def test_malformed_legacy_listing_flag_is_not_treated_as_confirmed_listing(self):
        self.prepare()
        for value in ['false', 'true', 1, None]:
            loras.mutate(self.db, ENGINE, lambda data: data['loras'][0].update(listed=value))
            item = self.get().json()['loras'][0]
            self.assertFalse(item['listed'])
            self.assertEqual(item['status'], 'unverified')


if __name__ == '__main__':
    unittest.main()
