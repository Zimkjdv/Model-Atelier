"""Exercise the real isolated worker bootstrap with deterministic CP950 streams."""

from pathlib import Path
import subprocess
import sys
import unittest


class WorkerEncodingTests(unittest.TestCase):
    def test_isolated_worker_bootstrap_handles_trainer_unicode_on_legacy_windows(self):
        worker = Path(__file__).resolve().parents[1] / 'scripts/training_worker.py'
        program = (
            'import importlib.util,sys;'
            "sys.stdout.reconfigure(encoding='cp950',errors='strict');"
            "sys.stderr.reconfigure(encoding='cp950',errors='strict');"
            f"spec=importlib.util.spec_from_file_location('worker',{str(worker)!r});"
            'm=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);\n'
            "try: m.main(['--help'])\n"
            'except SystemExit as exc: assert exc.code==0\n'
            "assert not any(n in sys.modules for n in ('torch','transformers','diffusers'))\n"
            "text=''.join(map(chr,(0x5b66,0x7fd2,0x958b,0x59cb)))\n"
            "print('running training / '+text)\n"
            'print(text,file=sys.stderr)\n'
        )
        result = subprocess.run(
            [sys.executable, '-I', '-c', program], capture_output=True, timeout=15
        )
        self.assertEqual(result.returncode, 0, result.stderr.decode('utf-8', errors='replace'))
        self.assertIn('running training / 学習開始', result.stdout.decode('utf-8'))
        self.assertIn('学習開始', result.stderr.decode('utf-8'))


if __name__ == '__main__':
    unittest.main()
