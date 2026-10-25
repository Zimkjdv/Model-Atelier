"""Acceptance admission and provenance checks; no model loading."""

import unittest

import httpx

from scripts import verify_hardware as hardware


class HardwareAcceptanceTests(unittest.TestCase):
    def test_reference_cases_require_explicit_inputs_before_dispatch(self):
        for case in ('image', 'inpaint', 'canny'):
            with self.subTest(case=case), self.assertRaises(ValueError):
                hardware.runner_class(case)
        with self.assertRaises(ValueError):
            hardware.runner_class('inpaint', 'source')

    def test_summary_cannot_promote_failed_report(self):
        with self.assertRaises(ValueError):
            hardware.summarize({'status': 'failed'}, None)

    def test_summary_rejects_other_original_engine(self):
        transport = httpx.MockTransport(
            lambda _: httpx.Response(
                200,
                json={
                    'status': 'completed',
                    'engine_url': 'http://127.0.0.1:9999',
                },
            )
        )
        with httpx.Client(base_url='http://127.0.0.1:8000', transport=transport) as client:
            with self.assertRaises(ValueError):
                hardware.summarize(
                    dict(
                        status='passed', job_id='original', expected_engine='http://127.0.0.1:8188'
                    ),
                    client,
                )


if __name__ == '__main__':
    unittest.main()
