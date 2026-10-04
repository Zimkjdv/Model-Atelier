import unittest
from unittest.mock import AsyncMock, patch

import httpx

from backend import flux_catalog, main, test_api

ENGINE = 'http://127.0.0.1:8188'


def definitions():
    return {
        'UNETLoader': dict(input=dict(required=dict(unet_name=[['flux.safetensors']], weight_dtype=[['default', 'fp8_e4m3fn']])), output=['MODEL']),
        'DualCLIPLoader': dict(input=dict(required=dict(clip_name1=[['clip.safetensors', 't5.safetensors']],
            clip_name2=[['clip.safetensors', 't5.safetensors']], type=[['flux']]), optional=dict(device=[['default', 'cpu']])), output=['CLIP']),
        'VAELoader': dict(input=dict(required=dict(vae_name=[['ae.safetensors']])), output=['VAE'])}


def remote_for(defs=None, hook=None):
    definitions_value = definitions() if defs is None else defs
    remote = AsyncMock()
    remote.__aenter__.return_value = remote

    async def get(url):
        if hook:
            hook(url)
        node = url.rsplit('/', 1)[-1]
        return httpx.Response(200, json={node: definitions_value[node]} if node in definitions_value else {}, request=httpx.Request('GET', url))
    remote.get.side_effect = get
    return remote


class FluxCatalogTests(unittest.TestCase):
    setUp = test_api.ApiTests.setUp
    tearDown = test_api.ApiTests.tearDown

    def sync(self, remote):
        with patch('backend.flux_catalog.httpx.AsyncClient', return_value=remote):
            return self.client.post('/api/flux/components/sync', json=dict(engine_url=ENGINE))

    def test_atomic_inventory_and_unknown_versions(self):
        result = self.sync(remote_for()).json()
        self.assertIsNotNone(result['synced_at'])
        self.assertIsNone(result['sync_error'])
        self.assertEqual(set(result['groups']), set(flux_catalog.GROUPS))
        self.assertEqual(len(result['groups']['text_encoders']), 2)
        self.assertEqual(result['groups']['diffusion_models'][0]['version'], '')
        self.assertEqual(result['groups']['diffusion_models'][0]['architecture'], 'unknown')
        self.assertEqual(self.client.get('/api/flux/components').json(), result)

    def test_invalid_one_slot_preserves_entire_previous_inventory(self):
        previous = self.sync(remote_for()).json()
        defs = definitions()
        defs['UNETLoader']['input']['required']['unet_name'] = [['new.safetensors']]
        defs['DualCLIPLoader']['input']['required']['clip_name2'] = [[False]]
        result = self.sync(remote_for(defs)).json()
        self.assertIsNotNone(result['sync_error'])
        self.assertEqual(result['groups'], previous['groups'])
        self.assertEqual(result['synced_at'], previous['synced_at'])

    def test_offline_and_missing_loader_do_not_clear_snapshots(self):
        previous = self.sync(remote_for()).json()
        offline = remote_for()
        offline.get.side_effect = httpx.ConnectError('offline')
        for remote in (remote_for({}), offline):
            result = self.sync(remote).json()
            self.assertEqual(result['groups'], previous['groups'])
            self.assertTrue(result['sync_error'])

    def test_metadata_survives_removal_reappearance_and_snapshot_is_detached(self):
        self.sync(remote_for())
        body = dict(engine_url=ENGINE, category='diffusion_models', name='flux.safetensors',
                    version='revision-a', architecture='flux', sha256='a' * 64)
        self.assertEqual(self.client.put('/api/flux/components/metadata', json=body).status_code, 200)
        snapshot = flux_catalog.capture(self.db, ENGINE, [('diffusion_model', 'diffusion_models', body['name'])])
        defs = definitions()
        defs['UNETLoader']['input']['required']['unet_name'] = [[]]
        result = self.sync(remote_for(defs)).json()['groups']['diffusion_models'][0]
        self.assertFalse(result['listed'])
        self.assertEqual(result['version'], 'revision-a')
        self.client.put('/api/flux/components/metadata', json=body | dict(version='revision-b'))
        self.assertEqual(self.sync(remote_for()).json()['groups']['diffusion_models'][0]['version'], 'revision-b')
        self.assertEqual(snapshot[0]['version'], 'revision-a')

    def test_engine_switch_while_syncing_does_not_publish(self):
        def change(_):
            self.client.put('/api/settings', json=dict(comfy_url='http://127.0.0.1:9000'))
        self.assertEqual(self.sync(remote_for(hook=change)).status_code, 409)
        self.assertIsNone(flux_catalog.read(self.db, ENGINE)['synced_at'])

    def test_scoped_catalog_and_invalid_edits(self):
        self.sync(remote_for())
        self.client.put('/api/settings', json=dict(comfy_url='http://127.0.0.1:9000'))
        self.assertEqual(self.client.get('/api/flux/components').json()['groups']['diffusion_models'], [])
        self.assertEqual(self.sync(remote_for()).status_code, 409)
        body = dict(engine_url='http://127.0.0.1:9000', category='vae', name='missing')
        self.assertEqual(self.client.put('/api/flux/components/metadata', json=body).status_code, 404)
        for fields in (dict(category='checkpoint'), dict(engine_url='http://user:pass@localhost'), dict(sha256='bad'), dict(size_bytes=True)):
            self.assertEqual(self.client.put('/api/flux/components/metadata', json=body | fields).status_code, 422)

    def test_different_encoder_slot_lists_use_intersection(self):
        defs = definitions()
        defs['DualCLIPLoader']['input']['required']['clip_name2'] = [['t5.safetensors']]
        result = self.sync(remote_for(defs)).json()
        self.assertEqual([item['name'] for item in result['groups']['text_encoders']], ['t5.safetensors'])
