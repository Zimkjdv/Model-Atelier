"""Sampling must never affect generation ownership, CAS, or terminal evidence."""

import asyncio
from contextlib import closing
from datetime import datetime, timedelta, timezone
import json
import sqlite3
import unittest
from unittest.mock import patch
from uuid import uuid4

import httpx
from backend import jobs, resource_sampling as sampling, test_api, gallery, test_gallery

STATS = dict(
    system=dict(ram_total=100, ram_free=20),
    devices=[dict(name='GPU', type='cuda', index=0, vram_total=100, vram_free=0)],
)


class ResourceSamplingTests(unittest.TestCase):
    setUp = test_api.ApiTests.setUp
    tearDown = test_api.ApiTests.tearDown

    def start(self):
        job = jobs.reserve(self.db, str(uuid4()), 'http://original.invalid:8188', {}, 'base')[0]
        return jobs.update(self.db, job['id'], status='submitting')

    def tick(self, seconds=0):
        return (datetime.now(timezone.utc) + timedelta(seconds=seconds)).isoformat()

    def test_independent_journal_cas_terminal_freeze_and_late_response(self):
        source = self.start()
        sampling.claim(self.db, 'one', self.tick())
        sampling.record(self.db, 'one', [source['id']], STATS, self.tick())
        live = jobs.get(self.db, source['id'])
        self.assertEqual(live['revision'], source['revision'])
        report = live['measurements']['continuous_resources']
        self.assertEqual(report['devices'][0]['max_used_bytes'], 100)
        self.assertIsNone(report['task_vram_peak_bytes'])
        done, accepted = jobs.compare_update(self.db, source, status='completed')
        self.assertTrue(accepted)
        frozen = done['measurements']
        self.assertEqual(frozen['continuous_resources']['end_reason'], 'job_terminal')
        sampling.record(self.db, 'one', [source['id']], None, self.tick(10), 'request_unavailable')
        self.assertEqual(jobs.get(self.db, source['id'])['measurements'], frozen)
        self.assertEqual(jobs.update(self.db, source['id'], error='later')['measurements'], frozen)
        self.assertEqual(sampling.claim(self.db, 'one', self.tick(10)), [])

    def test_grouping_original_source_lease_errors_and_no_post(self):
        one, two = self.start(), self.start()
        calls = []

        def remote(request):
            calls.append((request.method, str(request.url)))
            return httpx.Response(200, json=STATS)

        context = self.app.state.context
        context.engine_client_factory = lambda **kw: httpx.AsyncClient(
            transport=httpx.MockTransport(remote), **kw
        )
        with closing(sqlite3.connect(self.db)) as db, db:
            db.execute("INSERT INTO settings VALUES ('comfy_url', 'http://changed.invalid:8188')")
        monitor = sampling.Monitor(context)
        asyncio.run(monitor.cycle())
        self.assertEqual(calls, [('GET', 'http://original.invalid:8188/system_stats')])
        self.assertEqual(sampling.claim(self.db, 'other', self.tick(1)), [])
        self.assertEqual(len(sampling.claim(self.db, 'other', self.tick(11))), 2)
        sampling.record(self.db, monitor.owner, [one['id']], STATS, self.tick(12))
        self.assertEqual(
            jobs.get(self.db, one['id'])['measurements']['continuous_resources']['attempts'], 1
        )
        sampling.record(
            self.db, 'other', [one['id'], two['id']], None, self.tick(12), 'request_unavailable'
        )
        report = jobs.get(self.db, one['id'])['measurements']['continuous_resources']
        self.assertEqual(
            (report['attempts'], report['successes'], report['failures'], report['gaps']),
            (2, 1, 1, 1),
        )

    def test_bounded_tail_maxima_invalid_numbers_and_capacity(self):
        source = self.start()
        report = source['measurements']['continuous_resources']
        for n in range(130):
            stats = STATS if n == 0 else dict(system=dict(ram_total=100, ram_free=100), devices=[])
            sampling.observe(report, stats, self.tick(n * 2))
        self.assertEqual(len(report['samples']), 120)
        self.assertEqual(report['ram_max_used_bytes'], 80)
        self.assertEqual(report['samples'][-1]['ram_used_bytes'], 0)
        sampling.observe(
            report,
            dict(system=dict(ram_total=True, ram_free=float('nan')), devices=[]),
            self.tick(270),
        )
        self.assertIsNone(report['samples'][-1]['ram_used_bytes'])
        for _ in range(15):
            self.start()
        rejected = self.start()['measurements']['continuous_resources']
        self.assertEqual(rejected['end_reason'], 'capacity_limit')
        self.assertEqual(rejected['attempts'], 0)

    def test_limits_and_shutdown_preserve_partial_observations(self):
        source = self.start()
        with patch('backend.resource_sampling.MAX_ATTEMPTS', 0):
            self.assertEqual(sampling.claim(self.db, 'one', self.tick()), [])
        report = jobs.get(self.db, source['id'])['measurements']['continuous_resources']
        self.assertEqual(report['end_reason'], 'sampling_limit')
        timed = self.start()
        sampling.claim(self.db, 'one', self.tick(3601))
        self.assertEqual(
            jobs.get(self.db, timed['id'])['measurements']['continuous_resources']['end_reason'],
            'sampling_limit',
        )
        second = self.start()

        async def lifecycle():
            async with sampling.Monitor(self.app.state.context) as monitor:
                sampling.claim(self.db, monitor.owner, self.tick())

        asyncio.run(lifecycle())
        report = jobs.get(self.db, second['id'])['measurements']['continuous_resources']
        self.assertEqual(report['end_reason'], 'platform_shutdown')
        self.assertEqual(sampling.claim(self.db, 'restart', self.tick(60)), [])

    def test_legacy_and_reads_are_unchanged_and_completed_artwork_keeps_report(self):
        source = self.start()
        sampling.claim(self.db, 'one', self.tick())
        sampling.record(self.db, 'one', [source['id']], STATS, self.tick())
        source = jobs.update(self.db, source['id'], status='completed')
        raw = test_gallery.GalleryTests.image(self)
        item = gallery.save(
            self.db,
            self.db.parent / 'artworks',
            source,
            dict(node_id='7', filename='result.png', subfolder='', type='output'),
            raw,
        )[0]
        self.assertEqual(gallery.get(self.db, item['id'])['measurements'], source['measurements'])
        with closing(sqlite3.connect(self.db)) as db, db:
            old = dict(source)
            old['measurements'] = dict(source['measurements'])
            old['measurements'].pop('continuous_resources')
            db.execute(
                'UPDATE settings SET value=? WHERE key=?', (json.dumps(old), 'job:' + source['id'])
            )
        before = self.db.read_bytes()
        self.assertNotIn('continuous_resources', jobs.get(self.db, source['id'])['measurements'])
        self.assertEqual(self.db.read_bytes(), before)
        self.assertNotIn(
            'continuous_resources',
            jobs.update(self.db, source['id'], status='submitting')['measurements'],
        )

    def test_unavailable_and_oversized_sources_do_not_change_job(self):
        context = self.app.state.context
        for response in [
            httpx.Response(503),
            httpx.Response(200, content=b'x' * (sampling.MAX_BYTES + 1)),
        ]:
            source = self.start()
            context.engine_client_factory = lambda **kw: httpx.AsyncClient(
                transport=httpx.MockTransport(lambda _: response), **kw
            )
            asyncio.run(sampling.Monitor(context).cycle())
            source = jobs.get(self.db, source['id'])
            self.assertEqual(source['status'], 'submitting')
            self.assertEqual(
                source['measurements']['continuous_resources']['last_error'], 'request_unavailable'
            )


if __name__ == '__main__':
    unittest.main()
