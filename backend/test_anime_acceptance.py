"""Anime profiles preserve exact seeds, suite provenance and GET-only recovery."""

import copy
from pathlib import Path
import unittest
from unittest.mock import patch
import httpx
from backend import experiment_plans
from backend.test_generation_acceptance import Clock
from backend.test_illustration_suite import SuitePlatform
from backend.workflows import build
from scripts import verify_anime_suite as anime


class AnimeAcceptanceTests(unittest.TestCase):
    def check(self, model, case, seed, prompt_format, previous=None, verified=True):
        platform = SuitePlatform(model, 'chair', lose_submission=True)
        selected = next(
            v for v in experiment_plans.suite('anime-illustration')['cases'] if v['id'] == case
        )
        platform.settings = anime.settings(
            platform.engine, platform.checkpoint, selected, model, seed, prompt_format
        )
        platform.workflow = build(platform.settings)
        cls = type(
            'FixedAnime',
            (anime.AnimeAcceptance,),
            dict(model_id=model, case_id=case, seed=seed, prompt_format=prompt_format),
        )
        clock = Clock()
        with (
            httpx.Client(
                base_url='http://127.0.0.1:8001', transport=httpx.MockTransport(platform.handle)
            ) as client,
            patch.object(Path, 'is_file', return_value=True),
            patch.object(anime.downloader, '_verified', return_value=verified),
        ):
            result = cls(
                client, platform.engine, platform.checkpoint, clock=clock.now, sleep=clock.sleep
            ).run(previous)
        return platform, result

    def test_all_profiles_precise_once_only_then_readonly_recovery(self):
        for model in anime.MODELS:
            for case in anime.CASES:
                for seed in anime.SEEDS:
                    for fmt in ('common', 'quality-tags'):
                        platform, report = self.check(model, case, seed, fmt)
                        self.assertEqual(report['status'], 'passed', report)
                        self.assertEqual(platform.submissions, 1)
                        self.assertEqual(str(report['workflow']['5']['inputs']['seed']), seed)
                        # Recovery reads the very same saved records, never another generation.
                        cls = type(
                            'Fixed',
                            (anime.AnimeAcceptance,),
                            dict(model_id=model, case_id=case, seed=seed, prompt_format=fmt),
                        )
                        platform.seen.clear()
                        with (
                            httpx.Client(
                                base_url='http://127.0.0.1:8001',
                                transport=httpx.MockTransport(platform.handle),
                            ) as client,
                            patch.object(
                                anime.downloader,
                                '_verified',
                                side_effect=AssertionError('no weight reload'),
                            ),
                        ):
                            value = cls(client, platform.engine, platform.checkpoint).run(report)
                        self.assertEqual(value['status'], 'passed', value)
                        self.assertTrue(all(method == 'GET' for method, _ in platform.seen))

    def test_unverified_weights_and_wrong_report_seed_never_submit(self):
        args = ('pony-v6-xl', anime.CASES[0], anime.SEEDS[0], 'common')
        platform, report = self.check(*args, verified=False)
        self.assertEqual(report['status'], 'failed')
        self.assertEqual(platform.submissions, 0)
        _, original = self.check(*args)
        corrupt = copy.deepcopy(original)
        corrupt['test_suite']['seed'] = anime.SEEDS[1]
        platform, report = self.check(*args, previous=corrupt)
        self.assertEqual(report['status'], 'failed')
        self.assertEqual(platform.seen, [])

    def test_quality_tags_change_only_positive_prompt(self):
        case = experiment_plans.suite('anime-illustration')['cases'][0]
        for model in anime.MODELS:
            a = anime.settings(
                'http://127.0.0.1:8188', 'model', case, model, anime.SEEDS[0], 'common'
            )
            b = anime.settings(
                'http://127.0.0.1:8188', 'model', case, model, anime.SEEDS[0], 'quality-tags'
            )
            self.assertNotEqual(a['prompt'], b['prompt'])
            self.assertEqual(
                {k: v for k, v in a.items() if k not in ('title', 'prompt')},
                {k: v for k, v in b.items() if k not in ('title', 'prompt')},
            )
