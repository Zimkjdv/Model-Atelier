from contextlib import closing
import errno
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
from backend import backup, control_edges, gallery, jobs, main, test_control_edges, test_inpaint_feather
from backend.data_lease import DataBusyError, DataLease


class BackupTests(unittest.TestCase):
    def setUp(self):
        self.case = test_inpaint_feather.FeatherTests()
        self.case.setUp()
        self.addCleanup(self.case.tearDown)
        self.output = tempfile.TemporaryDirectory()
        self.addCleanup(self.output.cleanup)
        self.folder = Path(self.output.name)
        self.data = self.case.db.parent
        body = self.case.body()
        response = self.case.submit(body)
        self.assertEqual(response.status_code, 200, response.text)
        self.feather = jobs.update(self.case.db, body['request_id'], status='completed', history={
            'status': {'completed': True, 'status_str': 'success'},
            'outputs': {'7': {'images': [{'filename': 'feather.png', 'subfolder': '', 'type': 'output'}]}}})
        self.raw = (self.data / 'assets' / (body['image_asset_id'] + '.png')).read_bytes()
        self.artwork, _ = gallery.save(self.case.db, self.data / 'artworks', self.feather, gallery.outputs(self.feather)[0], self.raw)
        control = test_control_edges.ControlEdgeTests()
        for name in ('db', 'host', 'client'):
            setattr(control, name, getattr(self.case, name))
        _, self.control, source, self.edge = control.complete()
        anchors = control_edges.anchor(self.control, control.validate)
        control_edges.save(self.case.db, self.data, self.control, anchors, source, self.edge)
        self.evidence = self.folder / 'evidence.json'
        self.evidence.write_text('{"fixture":true}', encoding='utf-8')

    def create(self, name='archive', **options):
        return backup.backup(self.data, self.folder / name, database=self.case.db, platform_stopped=True, **options)

    def test_full_roundtrip_offline_preserves_raw_db_seed_sources_masks_edges_and_hashes(self):
        before = backup.tree(self.data, 'data')
        report = backup.inspect(self.data, self.case.db)
        self.assertTrue(report['ok'], report)
        self.create(evidence=[self.evidence])
        archive = self.folder / 'archive'
        manifest = backup.verify(archive)
        self.assertIn('evidence/000/evidence.json', manifest['files'])
        result = backup.restore(archive, self.folder / 'restored')
        self.assertEqual(result['inspection']['counts'], report['counts'])
        restored = Path(result['data'])
        self.assertEqual(backup.tree(restored, 'data'), before)
        self.assertEqual(backup.tree(self.data, 'data'), before)
        def offline(**options):
            raise AssertionError('restored offline reads must not contact engine')
        with TestClient(main.create_app(data_root=restored, database=result['database'], engine_client_factory=offline), base_url='http://127.0.0.1:8000', client=('127.0.0.1', 50000)) as client:
            self.assertEqual(len(client.get('/api/jobs').json()), 2)
            self.assertEqual(client.get('/api/artworks/' + self.artwork['id'] + '/image').content, self.raw)
            self.assertIn(b'18446744073709551615', client.get('/api/jobs/' + self.feather['id'] + '/workflow').content)
            restored_settings = client.get('/api/artworks/' + self.artwork['id'] + '/creation-settings')
            self.assertEqual(restored_settings.status_code, 200, restored_settings.text)
            self.assertEqual(restored_settings.json()['settings']['seed'], '18446744073709551615')
            for suffix in ['reference-image', 'reference-mask', 'reference-blend-mask']:
                self.assertEqual(client.get('/api/jobs/' + self.feather['id'] + '/' + suffix).status_code, 200)
            self.assertEqual(client.get('/api/jobs/' + self.control['id'] + '/control-edge/image').content, self.edge)

    def test_explicit_stop_and_running_platform_are_enforced_across_processes(self):
        with self.assertRaisesRegex(backup.BackupError, 'platform-stopped'):
            backup.backup(self.data, self.folder / 'unsafe', database=self.case.db)
        with TestClient(main.create_app(data_root=self.data, database=self.case.db), base_url='http://127.0.0.1:8000', client=('127.0.0.1', 50000)):
            with self.assertRaises(DataBusyError):
                self.create()
            result = subprocess.run([sys.executable, 'scripts/data_backup.py', 'backup', '--data', str(self.data),
                                     '--database', str(self.case.db), '--destination', str(self.folder / 'child'), '--platform-stopped'],
                                    cwd=Path(__file__).resolve().parents[1], capture_output=True, timeout=20,
                                    env=dict(os.environ, PYTHONIOENCODING='ascii'))
            self.assertEqual(result.returncode, 1)
            self.assertFalse(json.loads(result.stdout)['ok'], result.stderr)
        self.assertFalse((self.folder / 'archive').exists())
        self.assertFalse((self.folder / 'child').exists())
        with DataLease([self.data, self.case.db], maintenance=True):
            with self.assertRaises(DataBusyError):
                with TestClient(main.create_app(data_root=self.data, database=self.case.db), base_url='http://127.0.0.1:8000', client=('127.0.0.1', 50000)):
                    self.fail('platform started during maintenance')

    def test_missing_corrupt_files_and_database_are_reported_without_changes(self):
        image = self.data / 'artworks' / (self.artwork['id'] + '.png')
        image.write_bytes(b'corrupt')
        report = backup.inspect(self.data, self.case.db)
        self.assertFalse(report['ok'])
        self.assertIn('record_hash_or_size_mismatch', [v['code'] for v in report['problems']])
        with self.assertRaises(backup.BackupError):
            self.create()
        image.unlink()
        report = backup.inspect(self.data, self.case.db)
        self.assertIn('missing_file', [v['code'] for v in report['problems']])
        self.assertFalse((self.folder / 'archive').exists())
        self.case.db.write_bytes(b'bad sqlite')
        with self.assertRaises(backup.BackupError):
            backup.inspect(self.data, self.case.db)

    def test_space_failure_and_copy_failure_never_overwrite_existing_paths(self):
        before = backup.tree(self.data, 'data')
        with patch('backend.backup.shutil.disk_usage', return_value=type('Usage', (), {'free': 0})()):
            with self.assertRaisesRegex(backup.BackupError, '空間不足'):
                self.create()
        self.assertFalse((self.folder / 'archive').exists())
        with patch('backend.backup.copy_checked', side_effect=OSError(errno.ENOSPC, 'no space')):
            with self.assertRaisesRegex(backup.BackupError, '空間不足'):
                self.create('partial')
        self.assertTrue((self.folder / 'partial' / backup.INCOMPLETE).exists())
        with self.assertRaises(backup.BackupError):
            backup.restore(self.folder / 'partial', self.folder / 'restore')
        self.assertEqual(backup.tree(self.data, 'data'), before)
        self.create()
        with self.assertRaisesRegex(backup.BackupError, '已存在'):
            self.create()
        with self.assertRaisesRegex(backup.BackupError, '來源內'):
            backup.backup(self.data, self.data / 'nested', database=self.case.db, platform_stopped=True)

    def test_archive_tamper_path_traversal_and_existing_restore_are_rejected(self):
        self.create()
        archive = self.folder / 'archive'
        original = (archive / 'manifest.json').read_bytes()
        manifest = json.loads(original)
        name = next(iter(manifest['files']))
        target = archive / name
        raw = target.read_bytes(); target.write_bytes(b'tamper')
        with self.assertRaises(backup.BackupError):
            backup.restore(archive, self.folder / 'restored')
        self.assertFalse((self.folder / 'restored').exists())
        target.write_bytes(raw)
        for unsafe in ['../escape', '/absolute', 'data/../escape', 'data\\escape', 'data/CON', 'data/foo:bar']:
            changed = dict(manifest, files={unsafe: dict(size=0, sha256=hashlib.sha256(b'').hexdigest())})
            (archive / 'manifest.json').write_text(json.dumps(changed), encoding='utf-8')
            with self.assertRaises(backup.BackupError):
                backup.restore(archive, self.folder / 'restored')
        (archive / 'manifest.json').write_bytes(original)
        existing = self.folder / 'existing'; existing.mkdir(); (existing / 'keep').write_text('original')
        with self.assertRaises(backup.BackupError):
            backup.restore(archive, existing)
        self.assertEqual((existing / 'keep').read_text(), 'original')

    def test_busy_sqlite_leftover_wal_and_changed_source_refuse_snapshot(self):
        with closing(sqlite3.connect(self.case.db)) as db:
            db.execute('BEGIN IMMEDIATE')
            with self.assertRaises(backup.BackupError):
                self.create()
            db.rollback()
        sidecar = Path(str(self.case.db) + '-wal'); sidecar.write_bytes(b'pending')
        with self.assertRaisesRegex(backup.BackupError, 'WAL'):
            self.create()
        sidecar.unlink()
        original = backup.copy_checked
        def changed(source, target, metadata):
            original(source, target, metadata)
            (self.data / 'concurrent-writer.txt').write_text('unexpected')
        with patch('backend.backup.copy_checked', side_effect=changed):
            with self.assertRaisesRegex(backup.BackupError, '變動'):
                self.create()
        self.assertTrue((self.folder / 'archive' / backup.INCOMPLETE).exists())

    def test_external_database_and_empty_directories_are_included(self):
        external = self.folder / 'external.sqlite3'
        external.write_bytes(self.case.db.read_bytes())
        (self.data / 'empty').mkdir()
        result = backup.backup(self.data, self.folder / 'external-backup', database=external, platform_stopped=True)
        restored = backup.restore(result['destination'], self.folder / 'external-restored')
        self.assertEqual(Path(restored['database']).read_bytes(), external.read_bytes())
        self.assertTrue((Path(restored['data']) / 'empty').is_dir())

    def test_exact_file_limit_roundtrip_and_evidence_total_overflow_before_destination(self):
        count = len(backup.tree(self.data, 'data')[0])
        with patch('backend.backup.MAX_FILES', count):
            self.create('exact-limit')
            self.assertEqual(len(backup.verify(self.folder / 'exact-limit')['files']), count)
            self.assertTrue(backup.restore(self.folder / 'exact-limit', self.folder / 'exact-restored')['ok'])
            with self.assertRaisesRegex(backup.BackupError, '總檔案數'):
                self.create('overflow', evidence=[self.evidence])
        self.assertFalse((self.folder / 'overflow').exists())

    def test_malformed_records_are_readonly_reported_and_cli_roundtrip_succeeds(self):
        commands = [
            ['check', '--data', str(self.data), '--database', str(self.case.db)],
            ['backup', '--data', str(self.data), '--database', str(self.case.db), '--destination', str(self.folder / 'cli'), '--platform-stopped'],
            ['verify', '--archive', str(self.folder / 'cli')],
            ['restore', '--archive', str(self.folder / 'cli'), '--destination', str(self.folder / 'cli-restored')],
        ]
        for args in commands:
            result = subprocess.run([sys.executable, 'scripts/data_backup.py', *args], capture_output=True, timeout=20,
                                    cwd=Path(__file__).resolve().parents[1], env=dict(os.environ, PYTHONIOENCODING='ascii'))
            self.assertEqual(result.returncode, 0, result.stdout)
            self.assertTrue(json.loads(result.stdout)['ok'])
        with closing(sqlite3.connect(self.case.db)) as db:
            db.executemany('INSERT INTO settings VALUES (?, ?)', [
                ('draft:broken', '{'), ('draft:orphan', json.dumps({'id': 'orphan', 'reference_ids': ['missing']})),
                ('artwork:bad', json.dumps({'id': 'bad', 'job_id': []})),
                ('experiment:bad', json.dumps({'id': 'bad', 'plan': {'baseline': 'bad'}})),
            ])
            db.commit()
        before = backup.tree(self.data, 'data')
        report = backup.inspect(self.data, self.case.db)
        self.assertFalse(report['ok'])
        self.assertEqual(backup.tree(self.data, 'data'), before)
        self.assertTrue({'invalid_record_json', 'missing_reference_record', 'missing_original_job'} <= {p['code'] for p in report['problems']})
