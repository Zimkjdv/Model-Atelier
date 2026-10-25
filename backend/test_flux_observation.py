import io
import json
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch
from contextlib import redirect_stdout
import subprocess
from unittest.mock import Mock

from backend.flux_observation import CastObservations, header_observation
from scripts import verify_flux_runtime as runtime


class FluxObservationTests(unittest.TestCase):
    def test_header_records_mixed_storage_without_claiming_execution_or_exporting_thumbnails(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'model.safetensors'
            value = dict(
                __metadata__={
                    'modelspec.license': 'Apache License 2.0',
                    'thumbnail': 'private image',
                },
                a=dict(dtype='F8_E4M3', data_offsets=[0, 4]),
                b=dict(dtype='F32', data_offsets=[4, 8]),
            )
            header = json.dumps(value).encode()
            path.write_bytes(struct.pack('<Q', len(header)) + header + b'12345678')
            before = path.read_bytes()
            result = header_observation(path)
            self.assertEqual(result['tensor_counts_by_dtype'], {'F8_E4M3': 1, 'F32': 1})
            self.assertFalse(result['execution_precision_verified'])
            self.assertNotIn('private image', json.dumps(result))
            self.assertEqual(path.read_bytes(), before)
            value['a']['data_offsets'] = [0, 100000]
            header = json.dumps(value).encode()
            path.write_bytes(struct.pack('<Q', len(header)) + header + b'12345678')
            with self.assertRaises(ValueError):
                header_observation(path)
            path.write_bytes(struct.pack('<Q', 20 * 1024**2))
            with self.assertRaises(ValueError):
                header_observation(path)

    def test_observed_cpu_to_cuda_casts_are_distinct_from_declared_fp8_and_bounded(self):
        observations = CastObservations(limit=2)
        observations.record(
            'diffusion_model',
            ('torch.float8_e4m3fn', 'cpu'),
            ('torch.bfloat16', 'cuda:0'),
            ('torch.bfloat16', 'cuda:0'),
        )
        observations.record(
            'diffusion_model',
            ('torch.float8_e4m3fn', 'cpu'),
            ('torch.bfloat16', 'cuda:0'),
            ('torch.bfloat16', 'cuda:0'),
        )
        observations.record(
            't5xxl',
            ('torch.float8_e4m3fn', 'cpu'),
            ('torch.float32', 'cpu'),
            ('torch.float32', 'cpu'),
        )
        observations.record('vae', None, None, None)
        report = observations.report()
        self.assertEqual(len(report['observations']), 2)
        self.assertEqual(report['observations'][0]['calls'], 2)
        self.assertEqual(report['observations'][0]['source_weight']['device'], 'cpu')
        self.assertEqual(report['observations'][0]['returned_weight']['dtype'], 'torch.bfloat16')
        self.assertEqual(report['overflow_calls'], 1)

    def test_default_cli_does_not_run_gpu_worker_or_acquire_lease(self):
        with (
            patch.object(runtime, 'preparation', return_value={'current_files_verified': False}),
            patch.object(runtime, 'run', side_effect=AssertionError('GPU run')),
            redirect_stdout(io.StringIO()),
        ):
            self.assertEqual(runtime.main([]), 0)

    def test_managed_engine_running_or_unknown_is_never_stopped_automatically(self):
        with patch.object(runtime.httpx.Client, 'get', return_value=object()):
            with self.assertRaisesRegex(RuntimeError, 'stop managed'):
                runtime.ensure_engine_stopped()
        with patch.object(
            runtime.httpx.Client, 'get', side_effect=runtime.httpx.ReadTimeout('private')
        ):
            with self.assertRaisesRegex(RuntimeError, 'Cannot confirm'):
                runtime.ensure_engine_stopped()
        with patch.object(
            runtime.httpx.Client, 'get', side_effect=runtime.httpx.ConnectError('offline')
        ):
            runtime.ensure_engine_stopped()

    def test_timed_out_worker_is_terminated_before_lease_release_and_failure_receipt_is_saved(self):
        with tempfile.TemporaryDirectory() as directory:
            # Windows CI can return an 8.3 TEMP alias. Both sides must use the
            # canonical workspace; this lexical alias exercises the same bug.
            (Path(directory) / 'alias').mkdir()
            root = Path(directory) / 'alias/..'
            python = root / 'runtime/ComfyUI/.venv/Scripts/python.exe'
            python.parent.mkdir(parents=True)
            python.write_bytes(b'fixture')
            (root / 'models').mkdir()
            (root / 'models/flux1-schnell-plan.json').write_text('{}')
            process = Mock()
            process.wait.side_effect = [subprocess.TimeoutExpired('owned worker', 1800), 1]
            process.poll.side_effect = [None, 1, 1]
            lease = Mock()
            lease.__enter__ = Mock(return_value=lease)
            lease.__exit__ = Mock(return_value=False)
            with (
                patch.object(runtime, 'ROOT', root),
                patch.object(runtime, 'ensure_engine_stopped'),
                patch.object(runtime, 'source_snapshot', return_value={}),
                patch.object(
                    runtime,
                    'preparation',
                    return_value={'current_files_verified': True, 'components': []},
                ),
                patch.object(runtime.compute_lease, 'Reservation', return_value=lease),
                patch.object(runtime.subprocess, 'Popen', return_value=process),
                redirect_stdout(io.StringIO()),
            ):
                with self.assertRaises(subprocess.TimeoutExpired):
                    runtime.run()
            process.terminate.assert_called_once()
            process.kill.assert_not_called()
            lease.__exit__.assert_called_once()
            receipt = json.loads(
                next((root / 'runtime/flux-runtime-checks').glob('*/run.json')).read_text()
            )
            self.assertEqual(receipt['status'], 'failed')
            self.assertTrue(receipt['worker_process_exited'])
            self.assertFalse(receipt['observation_available'])


if __name__ == '__main__':
    unittest.main()
