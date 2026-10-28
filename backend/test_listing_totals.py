import json
import sqlite3
import unittest
from contextlib import closing
from uuid import uuid4

from backend import test_listing


class ListingTotalTests(unittest.TestCase):
    setUp = test_listing.ListingTests.setUp
    tearDown = test_listing.ListingTests.tearDown
    populate = test_listing.ListingTests.populate
    page = test_listing.ListingTests.page

    def test_total_covers_archived_and_filter_is_separate(self):
        self.populate(25)
        result = self.page(scope='archived', limit=4)
        self.assertEqual(result['all_total'], 25)
        self.assertLess(result['total'], result['all_total'])
        empty = self.page(q='not-present-anywhere')
        self.assertEqual(empty['total'], 0)
        self.assertEqual(empty['all_total'], 25)

    def test_snapshot_counts_and_limit_change_are_consistent(self):
        self.populate(25)
        first = self.page(scope='all', limit=4)
        with closing(sqlite3.connect(self.db)) as db, db:
            raw = db.execute(
                "SELECT value FROM settings WHERE key GLOB 'artwork:*' LIMIT 1"
            ).fetchone()[0]
            record = dict(json.loads(raw), id=str(uuid4()))
            db.execute(
                'INSERT INTO settings VALUES (?,?)', ('artwork:' + record['id'], json.dumps(record))
            )
        second = self.page(scope='all', limit=4, cursor=first['next_cursor'])
        self.assertEqual((second['total'], second['all_total'], second['offset']), (25, 25, 4))
        invalid = self.client.get(
            '/api/library/artworks', params=dict(scope='all', limit=12, cursor=first['next_cursor'])
        )
        self.assertEqual(invalid.status_code, 409)
        fresh = self.page(scope='all', limit=12)
        self.assertEqual(
            (fresh['total'], fresh['all_total'], len(fresh['items']), fresh['offset']),
            (26, 26, 12, 0),
        )

    def test_card_ratings_are_fresh_bounded_and_preserve_unrated_dimensions(self):
        self.populate(2)
        first = self.page(scope='all', limit=1)
        item = first['items'][0]
        scores = dict(
            prompt_adherence=3, character_consistency=None, visual_style=5, composition=None
        )
        response = self.client.patch(
            '/api/artworks/' + item['id'] + '/organization',
            json=dict(revision=item['revision'], ratings=scores),
        )
        self.assertEqual(response.status_code, 200, response.text)
        reread = self.page(scope='all', limit=1, cursor=first['next_cursor'].split(':')[0] + ':0')
        self.assertEqual(reread['items'][0]['ratings'], scores)
        self.assertNotIn('workflow', reread['items'][0])
