"""UI integration contracts: read-only connection tests and stable global sorting."""

from contextlib import closing
import json
import sqlite3
import unittest
from unittest.mock import AsyncMock, patch

import httpx
from backend import main, test_api
from scripts.listing_dataset import seed


class RedesignTests(unittest.TestCase):
    setUp = test_api.ApiTests.setUp
    tearDown = test_api.ApiTests.tearDown

    def test_connection_test_never_saves_or_submits(self):
        before = self.client.get('/api/settings').json()
        remote = AsyncMock()
        remote.__aenter__.return_value = remote
        remote.get.return_value = httpx.Response(
            200,
            json={'system': {}, 'devices': []},
            request=httpx.Request('GET', 'http://other-engine:9000/system_stats'),
        )
        with patch.object(main.httpx, 'AsyncClient', return_value=remote):
            result = self.client.post(
                '/api/engine/test', json={'comfy_url': 'http://other-engine:9000/'}
            )
        self.assertEqual(result.status_code, 200)
        self.assertTrue(result.json()['connected'])
        remote.get.assert_awaited_once_with('http://other-engine:9000/system_stats')
        remote.post.assert_not_awaited()
        self.assertEqual(self.client.get('/api/settings').json(), before)
        remote.get.side_effect = httpx.ConnectError('offline')
        with patch.object(main.httpx, 'AsyncClient', return_value=remote):
            failed = self.client.post(
                '/api/engine/test', json={'comfy_url': 'http://other-engine:9000'}
            )
        self.assertFalse(failed.json()['connected'])
        self.assertEqual(self.client.get('/api/settings').json(), before)
        self.assertEqual(
            self.client.post('/api/engine/test', json={'comfy_url': 'file:///secret'}).status_code,
            422,
        )

    def test_sorting_is_global_and_cursor_conditions_are_bound(self):
        seed(self.host, 125)
        page = self.client.get(
            '/api/library/artworks', params={'sort': 'model', 'scope': 'all', 'limit': 13}
        ).json()
        names = []
        while True:
            names.extend(item['checkpoint'] for item in page['items'])
            if not page['next_cursor']:
                break
            cursor = page['next_cursor']
            self.assertEqual(
                self.client.get(
                    '/api/library/artworks',
                    params={'sort': 'latest', 'scope': 'all', 'limit': 13, 'cursor': cursor},
                ).status_code,
                409,
            )
            page = self.client.get(
                '/api/library/artworks',
                params={'sort': 'model', 'scope': 'all', 'limit': 13, 'cursor': cursor},
            ).json()
        self.assertEqual(len(names), 125)
        self.assertEqual(names, sorted(names, key=str.casefold))

    def test_rating_sort_averages_observed_dimensions_and_keeps_unknown_last(self):
        seed(self.host, 3)
        with closing(sqlite3.connect(self.db)) as db, db:
            rows = db.execute(
                "SELECT key,value FROM settings WHERE key GLOB 'artwork:*' ORDER BY key"
            ).fetchall()
            for (key, raw), ratings in zip(
                rows,
                [
                    {'visual_style': 5, 'composition': None},
                    {'visual_style': 3, 'composition': 3},
                    {'visual_style': None},
                ],
            ):
                value = json.loads(raw)
                value['ratings'] = ratings
                db.execute('UPDATE settings SET value=? WHERE key=?', (json.dumps(value), key))
        result = self.client.get(
            '/api/library/artworks', params={'sort': 'rating', 'scope': 'all'}
        ).json()
        self.assertEqual(
            [item['id'] for item in result['items']], [key.split(':', 1)[1] for key, _ in rows]
        )
        self.assertEqual(self.client.get('/api/library/artworks?sort=unsupported').status_code, 422)
