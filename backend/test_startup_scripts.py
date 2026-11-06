"""Exercise the actual Windows batch entry point without starting services."""

import os
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(os.name == 'nt', 'Windows cmd launcher regression')
class StartupScriptTests(unittest.TestCase):
    def test_relocated_platform_launcher_uses_repository_root_from_another_directory(self):
        shell = shutil.which('powershell.exe')
        if not shell:
            self.skipTest('Windows PowerShell is unavailable')
        with tempfile.TemporaryDirectory(prefix='atelier relocated launcher ') as temporary:
            workspace = Path(temporary).resolve()
            scripts = workspace / 'scripts'
            scripts.mkdir()
            shutil.copy2(ROOT / 'scripts/start-local.ps1', scripts)
            binary = workspace / '.venv/Scripts/python.exe'
            binary.parent.mkdir(parents=True)
            shutil.copy2(sys.executable, binary)
            shutil.copy2(Path(sys.executable).parents[1] / 'pyvenv.cfg', workspace / '.venv')
            frontend = workspace / 'frontend/dist'
            frontend.mkdir(parents=True)
            (frontend / 'index.html').write_text('isolated launcher probe', encoding='ascii')
            (workspace / 'uvicorn.py').write_text(
                'import json,sys\nfrom pathlib import Path\n'
                'Path("launch.json").write_text(json.dumps({"cwd":str(Path.cwd()),'
                '"args":sys.argv[1:]}),encoding="utf-8")\n',
                encoding='ascii',
            )
            result = subprocess.run(
                [
                    shell,
                    '-NoProfile',
                    '-ExecutionPolicy',
                    'Bypass',
                    '-File',
                    str(scripts / 'start-local.ps1'),
                ],
                cwd=workspace.parent,
                env=os.environ | {'PYTHONDONTWRITEBYTECODE': '1'},
                capture_output=True,
                timeout=15,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            observed = json.loads((workspace / 'launch.json').read_text(encoding='utf-8'))
            self.assertEqual(Path(observed['cwd']), workspace)
            self.assertEqual(observed['args'][0], 'backend.main:app')
            self.assertIn('--no-proxy-headers', observed['args'])
            self.assertEqual(observed['args'][observed['args'].index('--port') + 1], '8000')

    def test_relocated_prompt_launcher_keeps_models_and_logs_inside_repository(self):
        shell = shutil.which('powershell.exe')
        if not shell:
            self.skipTest('Windows PowerShell is unavailable')
        with tempfile.TemporaryDirectory(prefix='atelier prompt launcher ') as temporary:
            workspace = Path(temporary).resolve()
            scripts = workspace / 'scripts'
            scripts.mkdir()
            shutil.copy2(ROOT / 'scripts/start-prompt-llm.ps1', scripts)
            ollama = workspace / 'runtime/prompt-llm/ollama/ollama.exe'
            ollama.parent.mkdir(parents=True)
            ollama.write_bytes(b'not executed: Start-Process is mocked')
            marker = workspace / 'launch.json'
            wrapper = workspace / 'probe.ps1'
            wrapper.write_text(
                "function Invoke-RestMethod { throw 'isolated offline probe' }\n"
                'function Start-Process { param($FilePath,$ArgumentList,$WindowStyle,'
                '[switch]$PassThru,$RedirectStandardOutput,$RedirectStandardError)\n'
                ' @{ file=$FilePath; models=$env:OLLAMA_MODELS; host=$env:OLLAMA_HOST;'
                ' cloud=$env:OLLAMA_NO_CLOUD; window=$WindowStyle;'
                ' output=$RedirectStandardOutput; error=$RedirectStandardError } |'
                ' ConvertTo-Json | Set-Content -LiteralPath $env:ATELIER_PROMPT_MARKER\n'
                ' return [pscustomobject]@{ Id=0 }\n}\n'
                '& $env:ATELIER_PROMPT_SCRIPT -Background | Out-Null\n',
                encoding='ascii',
            )
            result = subprocess.run(
                [shell, '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', str(wrapper)],
                cwd=workspace.parent,
                env=os.environ
                | {
                    'ATELIER_PROMPT_SCRIPT': str(scripts / 'start-prompt-llm.ps1'),
                    'ATELIER_PROMPT_MARKER': str(marker),
                },
                capture_output=True,
                timeout=15,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            observed = json.loads(marker.read_text(encoding='utf-8-sig'))
            self.assertEqual(Path(observed['file']), ollama)
            self.assertEqual(Path(observed['models']), workspace / 'runtime/prompt-llm/models')
            self.assertEqual(Path(observed['output']), workspace / 'runtime/prompt-llm/serve.log')
            self.assertEqual(
                Path(observed['error']), workspace / 'runtime/prompt-llm/serve-error.log'
            )
            self.assertEqual(
                (observed['host'], observed['cloud'], observed['window']),
                ('127.0.0.1:11434', '1', 'Hidden'),
            )

    def test_batch_launches_both_scripts_under_windows_code_pages(self):
        system = Path(os.environ['SystemRoot'])
        compilers = [
            system / 'Microsoft.NET' / framework / 'v4.0.30319' / 'csc.exe'
            for framework in ('Framework64', 'Framework')
        ]
        compiler = next((path for path in compilers if path.is_file()), None)
        if compiler is None:
            self.skipTest('Windows .NET Framework compiler is unavailable')
        with tempfile.TemporaryDirectory(prefix='atelier launcher space ') as temporary:
            workspace = Path(temporary).resolve()
            binary = workspace / 'bin'
            binary.mkdir()
            source = workspace / 'LauncherProbe.cs'
            source.write_text(
                'using System; using System.IO; '
                'class LauncherProbe { static void Main(string[] args) { '
                'int i = Array.IndexOf(args, "-File"); '
                'if (i < 0 || i + 1 >= args.Length) return; '
                'string marker = Path.Combine('
                'Environment.GetEnvironmentVariable("ATELIER_LAUNCH_PROBE"), '
                'Path.GetFileName(args[i + 1]) + ".args"); '
                'File.WriteAllLines(marker + ".tmp", args); '
                'File.Move(marker + ".tmp", marker); }}',
                encoding='utf-8',
            )
            compiled = subprocess.run(
                [
                    str(compiler),
                    '/nologo',
                    '/target:winexe',
                    '/out:' + str(binary / 'powershell.exe'),
                    str(source),
                ],
                capture_output=True,
                timeout=30,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            self.assertEqual(compiled.returncode, 0, compiled.stdout.decode(errors='replace'))
            batch = workspace / 'start-all.bat'
            batch.write_bytes((ROOT / 'start-all.bat').read_bytes())
            for code_page in (950, 65001):
                with self.subTest(code_page=code_page):
                    observed = workspace / str(code_page)
                    observed.mkdir()
                    result = subprocess.run(
                        f'"{system / "System32" / "cmd.exe"}" /d /c '
                        f'chcp {code_page} >nul & call "{batch}"',
                        cwd=workspace,
                        env=dict(
                            os.environ,
                            PATH=str(binary) + os.pathsep + str(system / 'System32'),
                            ATELIER_LAUNCH_PROBE=str(observed),
                        ),
                        input=b'\r\n',
                        capture_output=True,
                        timeout=10,
                        creationflags=subprocess.CREATE_NO_WINDOW,
                    )
                    output = (result.stdout + result.stderr).decode(
                        'cp950' if code_page == 950 else 'utf-8', errors='replace'
                    )
                    self.assertEqual(result.returncode, 0, output)
                    expected = [
                        ('scripts/start-local.ps1', True),
                        ('scripts/start-comfyui.ps1', True),
                        ('scripts/open-platform.ps1', False),
                    ]
                    markers = [observed / (Path(name).name + '.args') for name, _ in expected]
                    deadline = time.monotonic() + 5
                    while (
                        not all(path.is_file() for path in markers) and time.monotonic() < deadline
                    ):
                        time.sleep(0.05)
                    self.assertTrue(all(path.is_file() for path in markers), output)
                    for marker, (name, keep_open) in zip(markers, expected):
                        arguments = marker.read_text(encoding='utf-8-sig').splitlines()
                        self.assertEqual('-NoExit' in arguments, keep_open)
                        self.assertEqual(
                            arguments[arguments.index('-File') + 1],
                            str(workspace / name),
                        )
            missing = subprocess.run(
                f'"{system / "System32" / "cmd.exe"}" /d /c call "{batch}"',
                cwd=workspace,
                env=dict(os.environ, PATH=str(system / 'System32')),
                input=b'\r\n',
                capture_output=True,
                timeout=10,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            self.assertEqual(missing.returncode, 1)
            self.assertIn(b'Windows PowerShell was not found.', missing.stdout)

    def test_browser_opens_once_after_readiness_and_never_on_timeout(self):
        shell = shutil.which('powershell.exe')
        if not shell:
            self.skipTest('Windows PowerShell is unavailable')
        for mode in ('delayed', 'unavailable', 'no-frontend', 'browser-error'):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as temporary:
                workspace = Path(temporary)
                wrapper = workspace / 'probe.ps1'
                wrapper.write_text(
                    '$script:calls = 0\n'
                    'function Invoke-RestMethod {\n'
                    '  $script:calls++\n'
                    "  if ($env:ATELIER_OPEN_MODE -eq 'unavailable' -or "
                    "($env:ATELIER_OPEN_MODE -eq 'delayed' -and $script:calls -eq 1)) "
                    "{ throw 'Not ready' }\n"
                    "  return @{ status = 'ok' }\n"
                    '}\n'
                    'function Invoke-WebRequest {\n'
                    "  if ($env:ATELIER_OPEN_MODE -eq 'no-frontend') { throw 'No page' }\n"
                    "  return @{ StatusCode = 200; Headers = @{ 'Content-Type' = 'text/html' } }\n"
                    '}\n'
                    'function Start-Process { param($FilePath, $ErrorAction)\n'
                    '  [IO.File]::AppendAllText($env:ATELIER_OPEN_MARKER, $FilePath + "`n")\n'
                    "  if ($env:ATELIER_OPEN_MODE -eq 'browser-error') { throw 'No browser' }\n"
                    '}\n'
                    # Success cases must allow Windows PowerShell cold-start/JIT
                    # overhead on hosted runners; failure cases still exercise
                    # the short real readiness deadline.
                    "$probeTimeout = if ($env:ATELIER_OPEN_MODE -in @('delayed', 'browser-error')) { 5 } else { 1 }\n"
                    '& $env:ATELIER_OPEN_SCRIPT -TimeoutSeconds $probeTimeout\n'
                    'exit $LASTEXITCODE\n',
                    encoding='ascii',
                )
                marker = workspace / 'opened.txt'
                result = subprocess.run(
                    [shell, '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', str(wrapper)],
                    env=dict(
                        os.environ,
                        ATELIER_OPEN_MODE=mode,
                        ATELIER_OPEN_MARKER=str(marker),
                        ATELIER_OPEN_SCRIPT=str(ROOT / 'scripts/open-platform.ps1'),
                    ),
                    capture_output=True,
                    timeout=15,
                    creationflags=subprocess.CREATE_NO_WINDOW,
                )
                self.assertEqual(
                    result.returncode, 0 if mode == 'delayed' else 1, result.stdout + result.stderr
                )
                if mode in ('delayed', 'browser-error'):
                    self.assertEqual(marker.read_text().splitlines(), ['http://127.0.0.1:8000/'])
                else:
                    self.assertFalse(marker.exists())
                if mode == 'browser-error':
                    self.assertIn(b'Open http://127.0.0.1:8000/ manually.', result.stdout)


if __name__ == '__main__':
    unittest.main()
