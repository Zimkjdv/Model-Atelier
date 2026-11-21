from contextlib import closing
import json
import sqlite3
from unittest.mock import patch
import unittest
from uuid import uuid4

from backend import gallery, test_api
from backend.listing import Pager, ListingError
from scripts.listing_dataset import seed


class ListingTests(unittest.TestCase):
    setUp = test_api.ApiTests.setUp
    tearDown = test_api.ApiTests.tearDown

    def populate(self, count=125):
        seed(self.client.app.state.context, count)

    def page(self, kind='artworks', **params):
        response = self.client.get('/api/library/' + kind, params=params)
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def test_summary_is_bounded_and_detail_and_legacy_remain_compatible(self):
        self.populate()
        for kind, module in [('artworks', 'gallery'), ('jobs', 'jobs'), ('assets', 'assets')]:
            with patch(f'backend.{module}.list_all', side_effect=AssertionError('no legacy full read')):
                page = self.page(kind, scope='all')
            self.assertEqual(len(page['items']), 40)
            self.assertEqual(page['total'], 125)
            for item in page['items']:
                self.assertNotIn('workflow', item)
                self.assertNotIn('runtime_metadata', item)
                self.assertNotIn('fixture', item.get('preprocessing') or {})
            self.assertLess(len(json.dumps(page)), 65536)
        detail = self.client.get('/api/artworks/' + self.page()['items'][0]['id']).json()
        self.assertEqual(detail['parameters']['seed'], '18446744073709551615')
        self.assertEqual(len(self.client.get('/api/artworks?scope=all').json()), 125)
        self.assertEqual(len(self.client.get('/api/jobs').json()), 125)
        self.assertEqual(len(self.client.get('/api/assets').json()), 125)

    def test_task_overview_reaches_oldest_unfinished_job_across_engines(self):
        self.populate(45)
        rows = self.page('jobs', limit=45)['items']
        with closing(sqlite3.connect(self.db)) as db, db:
            for index, row in enumerate(rows):
                if index < 20:
                    status = ('completed', 'failed', 'cancelled', 'stopped')[index % 4]
                else:
                    status = {43: None, 44: 'unknown'}.get(index, 'running')
                engine = f'http://engine-{index % 2}.invalid:8188'
                db.execute(
                    "UPDATE settings SET value=json_set(value,'$.status',?,'$.engine_url',?) WHERE key=?",
                    (status, engine, 'job:' + row['id']),
                )
            before = db.execute('SELECT * FROM settings ORDER BY key').fetchall()

        endpoint = '/api/library/jobs/overview'
        with patch('backend.jobs.list_all', side_effect=AssertionError('no full read')):
            first = self.client.get(endpoint).json()
            last = self.client.get(endpoint, params={'active_page': 'last'}).json()
        self.assertEqual(
            (first['active_total'], first['active_page'], first['active_limit']), (25, 1, 20)
        )
        self.assertEqual(
            (last['active_total'], last['active_page'], last['active_limit']), (25, 2, 20)
        )
        self.assertEqual(len(first['items']), 30)
        self.assertEqual([row['id'] for row in first['items'][20:]], [row['id'] for row in rows[:10]])
        unfinished = first['items'][:20] + last['items']
        self.assertEqual([row['id'] for row in unfinished], [row['id'] for row in rows[20:]])
        self.assertEqual([row['status'] for row in unfinished[-2:]], ['unknown', 'unknown'])
        self.assertEqual(
            {row['engine_url'] for row in last['items']},
            {'http://engine-0.invalid:8188', 'http://engine-1.invalid:8188'},
        )
        self.assertTrue(all('workflow' not in row for row in first['items'] + last['items']))
        self.assertEqual(self.client.get(endpoint, params={'active_page': 99}).json(), last)
        for invalid in [0, -1, 'abc']:
            self.assertEqual(self.client.get(endpoint, params={'active_page': invalid}).status_code, 422)

        with closing(sqlite3.connect(self.db)) as db, db:
            self.assertEqual(db.execute('SELECT * FROM settings ORDER BY key').fetchall(), before)
            db.executemany(
                "UPDATE settings SET value=json_set(value,'$.status','completed') WHERE key=?",
                [('job:' + row['id'],) for row in unfinished[:5]],
            )
        clamped = self.client.get(endpoint, params={'active_page': 2}).json()
        self.assertEqual((clamped['active_total'], clamped['active_page']), (20, 1))
        self.assertEqual(
            [row['id'] for row in clamped['items'][:20]], [row['id'] for row in unfinished[5:]]
        )

    def test_active_job_count_tracks_new_and_terminal_jobs_without_loading_a_page(self):
        endpoint = '/api/library/jobs/active-count'
        self.populate(4)
        key = 'job:' + str(uuid4())
        with patch.object(Pager, 'job_overview', side_effect=AssertionError('no page read')):
            response = self.client.get(endpoint)
            self.assertEqual(response.status_code, 200, response.text)
            self.assertEqual(response.json(), {'active_total': 0})
            with closing(sqlite3.connect(self.db)) as db:
                with db:
                    db.execute('INSERT INTO settings VALUES (?, ?)', (key, '{}'))
                self.assertEqual(self.client.get(endpoint).json(), {'active_total': 1})
                for status in ('unknown', 'queued', 'running', 'stop_unknown', 'completed'):
                    with db:
                        db.execute(
                            "UPDATE settings SET value=json_set(value,'$.status',?) WHERE key=?",
                            (status, key),
                        )
                    active = int(status != 'completed')
                    self.assertEqual(self.client.get(endpoint).json(), {'active_total': active})

    def test_fixed_membership_has_no_duplicates_or_gaps_after_insert_or_updates(self):
        self.populate()
        first = self.page(scope='all', limit=13)
        expected = [v['id'] for v in sorted(gallery.list_all(self.db), key=lambda v: (v['imported_at'], v['id']), reverse=True)]
        changed = gallery.get(self.db, expected[-1])
        gallery.organize(self.db, changed['id'], changed['revision'], {'favorite': True, 'archived': True, 'notes': 'new note'})
        inserted = dict(changed, id=str(uuid4()), imported_at='2099-01-01T00:00:00+00:00')
        with closing(sqlite3.connect(self.db)) as db, db:
            db.execute('INSERT INTO settings VALUES (?,?)', ('artwork:' + inserted['id'], json.dumps(inserted)))
        seen, page = [], first
        while True:
            seen.extend(item['id'] for item in page['items'])
            if not page['next_cursor']:
                break
            page = self.page(scope='all', limit=13, cursor=page['next_cursor'])
        self.assertEqual(seen, expected)
        self.assertEqual(len(set(seen)), 125)
        self.assertEqual(self.page(scope='all')['total'], 126)
        back = self.page(scope='all', limit=13, cursor=page['previous_cursor'])
        self.assertEqual(back['offset'], 104)

    def test_combined_filters_literal_unicode_search_and_frozen_filter_membership(self):
        self.populate()
        result = self.page(scope='archived', favorites_only=True, model='model-0.safetensors', q='FIXTURE', limit=1)
        self.assertEqual(result['total'], 2)
        item = gallery.get(self.db, result['items'][0]['id'])
        gallery.organize(self.db, item['id'], item['revision'], {'archived': False, 'favorite': False})
        second = self.page(scope='archived', favorites_only=True, model='model-0.safetensors', q='FIXTURE', limit=1, cursor=result['next_cursor'])
        self.assertEqual(second['total'], 2)
        self.assertNotEqual(second['items'][0]['id'], item['id'])
        item = gallery.get(self.db, item['id'])
        gallery.organize(self.db, item['id'], item['revision'], {'notes': 'MÄLÖ %_ 文本' + 'x' * 200})
        self.assertEqual(self.page(scope='all', q='mälö %_')['total'], 1)
        summary = self.page(scope='all', q='mälö %_')['items'][0]
        self.assertEqual(len(summary['notes']), 160)
        self.assertTrue(summary['notes_truncated'])
        self.assertEqual(self.page(scope='all', q="' OR 1=1 --")['total'], 0)

    def test_cursor_validation_expiry_eviction_and_deleted_asset_are_explicit(self):
        self.populate(5)
        for params in [{'limit': 0}, {'limit': 101}, {'q': 'x' * 201}]:
            self.assertEqual(self.client.get('/api/library/artworks', params=params).status_code, 422)
        self.assertEqual(self.client.get('/api/library/jobs?cursor=bad').status_code, 400)
        first = self.page('assets', scope='all', limit=1)
        self.assertEqual(self.client.get('/api/library/assets', params=dict(scope='active', limit=1, cursor=first['next_cursor'])).status_code, 409)
        pager = Pager(self.db, clock=lambda: 0)
        page = pager.page('assets', scope='all', limit=1)
        pager.clock = lambda: 601
        with self.assertRaises(ListingError) as caught:
            pager.page('assets', scope='all', limit=1, cursor=page['next_cursor'])
        self.assertEqual(caught.exception.status, 410)
        for _ in range(9):
            self.page('assets', scope='all', limit=1)
        self.assertEqual(self.client.get('/api/library/assets', params=dict(scope='all', limit=1, cursor=first['next_cursor'])).status_code, 410)
        pager = Pager(self.db)
        first = pager.page('assets', scope='all', limit=1)
        second = pager.page('assets', scope='all', limit=1, cursor=first['next_cursor'])
        deleted = second['items'][0]['id']
        with closing(sqlite3.connect(self.db)) as db, db:
            db.execute('DELETE FROM settings WHERE key=?', ('asset:' + deleted,))
        second = pager.page('assets', scope='all', limit=1, cursor=first['next_cursor'])
        self.assertEqual(second['missing_ids'], [deleted])
        self.assertEqual(second['total'], 5)
        with patch('backend.listing.MAX_KEYS', 3), self.assertRaises(ListingError) as caught:
            Pager(self.db).page('artworks', scope='all')
        self.assertEqual(caught.exception.status, 413)

    def test_reads_do_not_rewrite_json_or_create_schema(self):
        self.populate(3)
        def snapshot():
            with closing(sqlite3.connect(self.db)) as db:
                return db.execute('SELECT * FROM settings ORDER BY key').fetchall(), db.execute('SELECT sql FROM sqlite_master ORDER BY name').fetchall()
        before = snapshot()
        for kind in ['artworks', 'jobs', 'assets']:
            self.page(kind, scope='all')
        self.assertEqual(snapshot(), before)

    def test_equal_timestamps_and_workflow_families_have_stable_order(self):
        self.populate(3)
        with closing(sqlite3.connect(self.db)) as db, db:
            for key, raw in db.execute("SELECT key,value FROM settings WHERE key GLOB 'artwork:*'").fetchall():
                value = json.loads(raw); value['imported_at'] = 'same'
                db.execute('UPDATE settings SET value=? WHERE key=?', (json.dumps(value), key))
            raw = db.execute("SELECT value FROM settings WHERE key GLOB 'job:*' LIMIT 1").fetchone()[0]
            for workflow in ['checkpoint-image2image-v1', 'flux1-schnell-text2image-v1', 'checkpoint-inpaint-v1', 'checkpoint-inpaint-feather-v2', 'checkpoint-canny-controlnet-v1', 'checkpoint-canny-controlnet-edge-v2']:
                value = dict(json.loads(raw), id=str(uuid4()), workflow_id=workflow)
                db.execute('INSERT INTO settings VALUES (?,?)', ('job:' + value['id'], json.dumps(value)))
        first = self.page(scope='all', limit=2)
        second = self.page(scope='all', limit=2, cursor=first['next_cursor'])
        ids = [item['id'] for item in first['items'] + second['items']]
        self.assertEqual(ids, sorted(ids, reverse=True))
        for family, count in [('checkpoint', 4), ('flux', 1), ('inpaint', 2), ('control', 2)]:
            self.assertEqual(self.page('jobs', workflow=family)['total'], count)

    def test_only_current_page_images_are_checked_and_cursors_are_per_app(self):
        from pathlib import Path
        self.populate()
        checked, original = [], Path.is_file
        folder = self.client.app.state.context.DATA / 'artworks'
        def is_file(path):
            if path.parent == folder:
                checked.append(path)
            return original(path)
        with patch.object(Path, 'is_file', is_file):
            self.page(scope='all', limit=7)
        self.assertEqual(len(checked), 14)
        first = Pager(self.db).page('artworks', scope='all')
        with self.assertRaises(ListingError) as caught:
            Pager(self.db).page('artworks', scope='all', cursor=first['next_cursor'])
        self.assertEqual(caught.exception.status, 410)
