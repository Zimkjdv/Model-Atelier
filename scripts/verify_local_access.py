"""Real loopback HTTP ingress verification against isolated DATA; no engine work."""

import argparse
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time

import httpx
from backend import training_bundle

ROOT = Path(__file__).resolve().parents[1]


def verify(output):
    output = training_bundle.safe_output(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='atelier-local-access-') as temporary:
        with socket.socket() as listener:
            listener.bind(('127.0.0.1', 0))
            port = listener.getsockname()[1]
        process = subprocess.Popen(
            [
                sys.executable,
                '-m',
                'scripts.verify_local_access',
                '--serve',
                temporary,
                '--port',
                str(port),
            ],
            cwd=ROOT,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0,
        )
        try:
            base = f'http://127.0.0.1:{port}'
            with httpx.Client(base_url=base, trust_env=False, timeout=5) as client:
                deadline = time.monotonic() + 20
                while True:
                    try:
                        if client.get('/api/health').status_code == 200:
                            break
                    except httpx.HTTPError:
                        pass
                    if process.poll() is not None or time.monotonic() > deadline:
                        raise ValueError('Isolated local platform did not start.')
                    time.sleep(0.1)
                original = client.get('/api/settings').json()
                rows = []
                for headers in (
                    {'Origin': 'https://attacker.invalid'},
                    {'Host': 'attacker.invalid'},
                    {'Origin': 'null'},
                    {'Sec-Fetch-Site': 'cross-site'},
                ):
                    response = client.put(
                        '/api/settings',
                        json={'comfy_url': 'http://127.0.0.1:9999'},
                        headers=headers,
                    )
                    if response.status_code != 403:
                        raise ValueError('Untrusted ingress reached the API.')
                    rows.append(dict(headers=headers, status=response.status_code))
                response = client.put('/api/settings', json=original, headers={'Origin': base})
                response.raise_for_status()
                if client.get('/api/settings').json() != original:
                    raise ValueError('Rejected writes changed settings.')
                forwarded = client.get('/api/health', headers={'X-Forwarded-For': '198.51.100.2'})
                if forwarded.status_code != 200:
                    raise ValueError('Forwarded headers affected local peer identity.')
                report = dict(
                    schema_version=1,
                    status='passed',
                    checks=rows,
                    same_origin_write_status=response.status_code,
                    forwarded_headers_ignored=True,
                    deployment=client.get('/api/deployment').json(),
                    data_isolated=True,
                    generation_submitted=False,
                )
                with output.open('x', encoding='utf-8') as stream:
                    json.dump(report, stream, ensure_ascii=False, indent=2)
                return report
        finally:
            if process.poll() is None:
                process.terminate()
                process.wait(timeout=15)
            process.stderr.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output')
    parser.add_argument('--serve', help=argparse.SUPPRESS)
    parser.add_argument('--port', type=int, default=0, help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.serve:
        import uvicorn
        from backend.main import create_app

        uvicorn.run(
            create_app(data_root=args.serve),
            host='127.0.0.1',
            port=args.port,
            proxy_headers=False,
            log_level='warning',
        )
        return
    if not args.output:
        parser.error('--output is required')
    print(json.dumps(verify(Path(args.output)), ensure_ascii=False))


if __name__ == '__main__':
    main()
