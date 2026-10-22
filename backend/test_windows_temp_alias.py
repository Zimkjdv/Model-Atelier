"""Exercise path confinement tests under the aliases used by Windows CI."""
import ctypes
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


@unittest.skipUnless(os.name == 'nt', 'Windows 8.3 path aliases')
class WindowsTempAliasTests(unittest.TestCase):
    def test_confined_paths_and_fault_injection_use_canonical_physical_paths(self):
        with tempfile.TemporaryDirectory(prefix='atelier long temporary path ') as folder:
            root = Path(folder).resolve()
            buffer = ctypes.create_unicode_buffer(32768)
            result = ctypes.windll.kernel32.GetShortPathNameW(str(root), buffer, len(buffer))
            if not result or Path(buffer.value) == root:
                self.skipTest('8.3 aliases are not available on this filesystem')
            names = [
                'backend.test_control_acceptance.ControlInstallTests.test_control_target_is_scoped_and_check_is_readonly',
                'backend.test_generation_acceptance.GenerationAcceptanceTests.test_report_path_is_confined_to_runtime_and_urls_are_loopback',
                'backend.test_generation_acceptance.GenerationAcceptanceTests.test_resolve_race_extended_prefix_still_confines_same_physical_runtime',
                'backend.test_model_paths.ModelPathTests.test_export_rejects_symlink_targets_and_resolved_runtime_escape',
            ]
            result = subprocess.run([sys.executable, '-m', 'unittest', *names],
                                    cwd=Path(__file__).resolve().parents[1],
                                    env=dict(os.environ, TEMP=buffer.value, TMP=buffer.value),
                                    capture_output=True, timeout=60)
            self.assertEqual(result.returncode, 0, result.stderr.decode(errors='replace'))
