import copy
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import httpx
from scripts import install_model, install_pony as downloader


class AnimagineInstallTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.workspace = Path(self.temp.name)
        self.value = copy.deepcopy(install_model.manifest('animagine-xl-4.0-opt'))
        self.content = b'checkpoint test fixture'
        self.value.update(size_bytes=len(self.content), sha256=hashlib.sha256(self.content).hexdigest())

    def test_pinned_selection_and_invalid_sources_never_write_or_contact_network(self):
        self.assertEqual(install_model.manifest('pony-v6-xl')['id'], 'pony-v6-xl')
        for change in [dict(id='../bad'), dict(filename='../escape.safetensors'),
                       dict(source=self.value['source'] | dict(revision='a'*40)),
                       dict(source=self.value['source'] | dict(download_url='https://example.org/fake'))]:
            with self.assertRaises(downloader.InstallationError):
                downloader.install(workspace=self.workspace, manifest=self.value | change)
        self.assertEqual(list(self.workspace.iterdir()), [])

    def test_check_is_read_only_and_accounts_for_partial_and_reserve(self):
        with patch.object(downloader.shutil, 'disk_usage', return_value=type('Space', (), {'free': 0})()):
            report = install_model.plan(self.value, workspace=self.workspace)
        self.assertFalse(report['ready'])
        self.assertEqual(list(self.workspace.iterdir()), [])
        directory = self.workspace / 'runtime/ComfyUI/models/checkpoints'
        directory.mkdir(parents=True)
        partial = directory / (self.value['filename'] + '.part')
        partial.write_bytes(self.content[:5])
        free = len(self.content)-5 + downloader.RESERVE_BYTES
        with patch.object(downloader.shutil, 'disk_usage', return_value=type('Space', (), {'free': free})()):
            report = install_model.plan(self.value, workspace=self.workspace)
            restart = install_model.plan(self.value, workspace=self.workspace, restart=True)
        self.assertTrue(report['ready'])
        self.assertTrue(restart['ready'])
        self.assertEqual(report['download_remaining_bytes'], len(self.content)-5)
        self.assertEqual(restart['reclaimable_partial_bytes'], 5)
        self.assertEqual(partial.read_bytes(), self.content[:5])
        self.assertEqual(len(list(directory.iterdir())), 1)

    def test_download_resume_and_provenance_use_selected_checkpoint(self):
        directory = self.workspace / 'runtime/ComfyUI/models/checkpoints'
        directory.mkdir(parents=True)
        partial = directory / (self.value['filename'] + '.part')
        partial.write_bytes(self.content[:5])
        def handle(request):
            self.assertEqual(str(request.url), self.value['source']['download_url'])
            self.assertEqual(request.headers['range'], 'bytes=5-')
            return httpx.Response(206, stream=httpx.ByteStream(self.content[5:]), headers={
                'Content-Range': f'bytes 5-{len(self.content)-1}/{len(self.content)}'})
        with httpx.Client(transport=httpx.MockTransport(handle)) as client:
            result = downloader.install(workspace=self.workspace, manifest=self.value, client=client, output=lambda _: None)
        self.assertTrue(result['verified'])
        self.assertEqual(result['model_id'], 'animagine-xl-4.0-opt')
        self.assertEqual((directory / self.value['filename']).read_bytes(), self.content)
        self.assertFalse(partial.exists())
        self.assertFalse((directory / 'pony-v6-xl.safetensors').exists())

    def test_lock_or_existing_file_has_explicit_read_only_state(self):
        directory = self.workspace / 'runtime/ComfyUI/models/checkpoints'
        directory.mkdir(parents=True)
        target = directory / self.value['filename']
        target.write_bytes(b'not a real model')
        report = install_model.plan(self.value, workspace=self.workspace)
        self.assertTrue(report['existing_requires_hash_verification'])
        self.assertEqual(report['download_remaining_bytes'], 0)
        lock = target.with_name(target.name + '.install.lock')
        lock.write_text('fixture')
        self.assertFalse(install_model.plan(self.value, workspace=self.workspace)['ready'])
        self.assertEqual(target.read_bytes(), b'not a real model')

    def test_cli_check_exits_two_without_installing_when_disk_is_insufficient(self):
        with patch.object(install_model, 'plan', return_value=dict(ready=False, message='insufficient')), \
             patch.object(downloader, 'install', side_effect=AssertionError('check must not install')), \
             patch('sys.stdout', io.StringIO()) as output:
            self.assertEqual(install_model.main(['animagine-xl-4.0-opt', '--check']), 2)
        self.assertFalse(json.loads(output.getvalue())['ready'])
