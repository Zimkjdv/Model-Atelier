"""Protocol regressions for F03 tools; these tests are not GPU evidence."""

import copy
import hashlib
import io
import os
from pathlib import Path
import runpy
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch
from uuid import uuid4

import httpx
from PIL import Image

from backend import failures, flux_observation, flux_workflows
from scripts.verify_flux_generation import Acceptance


class FluxAcceptanceTests(unittest.TestCase):
    def setUp(self):
        self.settings = copy.deepcopy(flux_observation.SETTINGS)
        self.job_id, self.artwork_id = str(uuid4()), str(uuid4())
        buffer = io.BytesIO()
        Image.new('RGB', (512, 512)).save(buffer, format='PNG')
        self.raw = buffer.getvalue()
        self.graph = flux_workflows.build(self.settings)
        self.job = dict(
            id=self.job_id,
            engine_url=self.settings['engine_url'],
            status='completed',
            workflow_id=flux_workflows.WORKFLOW_ID,
            workflow=self.graph,
            component_metadata=[
                {'role': role, 'sha256': str(index) * 64}
                for index, (role, _) in enumerate(flux_workflows.ROLES)
            ],
            runtime_metadata={'original': 'environment'},
            history={'status': {'status_str': 'success'}},
        )
        self.item = self.job | dict(
            id=self.artwork_id, job_id=self.job_id, sha256=hashlib.sha256(self.raw).hexdigest()
        )
        self.report = dict(
            status='passed',
            settings=self.settings,
            job_id=self.job_id,
            component_metadata=self.job['component_metadata'],
            runtime_metadata=self.job['runtime_metadata'],
            artworks=[dict(id=self.artwork_id, sha256=self.item['sha256'], bytes=len(self.raw))],
        )
        self.requests = []

    def remote(self, request):
        self.requests.append(request.method)
        self.assertEqual(request.method, 'GET', 'Offline verification must never mutate or submit')
        path = request.url.path
        if path.endswith('/image'):
            return httpx.Response(200, content=self.raw)
        if path.endswith('/workflow'):
            value = self.graph
        elif path.endswith('/creation-settings'):
            value = {'settings': self.settings}
        elif '/jobs/' in path:
            value = self.job
        else:
            value = self.item
        return httpx.Response(200, json=value)

    def verify(self, report=None):
        with httpx.Client(
            base_url='http://127.0.0.1:8000', transport=httpx.MockTransport(self.remote)
        ) as client:
            return Acceptance(client, self.settings['engine_url']).verify(report or self.report)

    def test_offline_reads_and_exact_uint64_seed(self):
        self.assertEqual(self.verify()['status'], 'passed')
        self.assertEqual(set(self.requests), {'GET'})
        self.assertEqual(self.graph['7']['inputs']['seed'], 9007199254740993)

    def test_changed_snapshots_content_or_parameters_cannot_pass(self):
        for field, changed in (
            ('component_metadata', []),
            ('runtime_metadata', None),
            ('workflow', {}),
            ('status', 'failed'),
        ):
            original = self.job[field]
            self.job[field] = changed
            with self.assertRaises(ValueError):
                self.verify()
            self.job[field] = original
        self.item['sha256'] = 'f' * 64
        with self.assertRaises(ValueError):
            self.verify()

    def test_transport_failure_persists_identity_without_replay(self):
        emitted, requests = [], []

        def remote(request):
            requests.append(request)
            raise httpx.ReadTimeout('lost receipt')

        with httpx.Client(
            base_url='http://127.0.0.1:8000', transport=httpx.MockTransport(remote)
        ) as client:
            runner = Acceptance(client, self.settings['engine_url'], emit=emitted.append)
            with self.assertRaises(httpx.ReadTimeout):
                runner.run()
        self.assertEqual(len(requests), 1)
        self.assertEqual(emitted[-1]['status'], 'failed')
        self.assertEqual(emitted[0]['job_id'], emitted[-1]['job_id'])

    def test_flux_failure_uses_confirmed_own_node_and_keeps_full_graph(self):
        job = self.job | {'prompt_id': self.job_id}
        for node, kind, exception, expected in (
            ('1', 'UNETLoader', 'safetensors_rust.SafetensorError', 'model_load_failed'),
            ('1', 'UNETLoader', 'torch.OutOfMemoryError', 'cuda_oom'),
            ('7', 'KSampler', 'RuntimeError', 'execution_failed'),
        ):
            entry = dict(
                status=dict(
                    status_str='error',
                    messages=[
                        [
                            'execution_error',
                            dict(
                                prompt_id=self.job_id,
                                node_id=node,
                                node_type=kind,
                                exception_type=exception,
                            ),
                        ]
                    ],
                )
            )
            self.assertEqual(failures.from_history(job, entry)['code'], expected)
            entry['status']['messages'][0][1]['prompt_id'] = str(uuid4())
            self.assertEqual(failures.from_history(job, entry)['code'], 'execution_failed')
        self.assertEqual(job['workflow'], self.graph)

    def test_quota_probe_preserves_original_exception_and_restores_known_default(self):
        class Loader:
            def load_unet(self, name, dtype):
                return name, dtype

        oom = RuntimeError('allocator OOM')
        cuda = SimpleNamespace(init=Mock(), set_per_process_memory_fraction=Mock())
        fake_torch = SimpleNamespace(cuda=cuda, empty=Mock(side_effect=oom), float32='float32')
        source = Path(__file__).resolve().parents[1] / 'scripts/flux_failure_node.py'
        with (
            patch.dict(os.environ, ATELIER_F03_FIXTURE='1'),
            patch.dict(sys.modules, nodes=SimpleNamespace(UNETLoader=Loader), torch=fake_torch),
        ):
            runpy.run_path(str(source))
            self.assertEqual(
                Loader().load_unet('ordinary.safetensors', 'default'),
                ('ordinary.safetensors', 'default'),
            )
            with self.assertRaises(RuntimeError) as raised:
                Loader().load_unet('f03-quota-oom.safetensors', 'default')
            self.assertIs(raised.exception, oom)
            self.assertEqual(
                [call.args[0] for call in cuda.set_per_process_memory_fraction.call_args_list],
                [0.000001, 1.0],
            )
        with patch.dict(os.environ, ATELIER_F03_FIXTURE='0'):
            with self.assertRaisesRegex(RuntimeError, 'isolated fixture'):
                runpy.run_path(str(source))
