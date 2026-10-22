"""API latency/bytes/Python peak/RSS for deterministic isolated list datasets."""
import argparse
import gc
import json
from pathlib import Path
import platform
import statistics
import sys
import tempfile
import threading
import time
import tracemalloc

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import httpx
import psutil
from fastapi.testclient import TestClient
from backend.main import create_app
from scripts.listing_dataset import seed


def measure(client, url):
    times, peaks, rss_peaks = [], [], []
    size = 0
    for _ in range(3):
        gc.collect()
        process = psutil.Process()
        baseline = process.memory_info().rss
        rss = [baseline]
        stop = threading.Event()
        def sample():
            while not stop.wait(.005):
                rss.append(process.memory_info().rss)
        thread = threading.Thread(target=sample, daemon=True)
        thread.start()
        tracemalloc.start()
        started = time.perf_counter()
        response = client.get(url)
        elapsed = (time.perf_counter() - started) * 1000
        assert response.status_code == 200, response.text[:300]
        size = len(response.content)
        peaks.append(tracemalloc.get_traced_memory()[1])
        tracemalloc.stop()
        stop.set(); thread.join()
        rss.append(process.memory_info().rss)
        rss_peaks.append(max(rss) - baseline)
        times.append(elapsed)
        del response
    return dict(median_ms=round(statistics.median(times), 2), response_bytes=size,
                python_peak_bytes=max(peaks), rss_delta_bytes=max(rss_peaks))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode', choices=['legacy', 'paged'], required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    report = dict(mode=args.mode, python=platform.python_version(), platform=platform.platform(), cpu=platform.processor(),
                  ram_bytes=psutil.virtual_memory().total, repeats=3, datasets=[])
    for count in [100, 1000, 10000]:
        with tempfile.TemporaryDirectory(prefix='atelier-benchmark-') as folder:
            app = create_app(data_root=folder, engine_client_factory=lambda **kw: httpx.AsyncClient(transport=httpx.MockTransport(lambda req: (_ for _ in ()).throw(AssertionError('benchmark is offline'))), **kw))
            with TestClient(app) as client:
                seed(app.state.context, count)
                result = dict(count_per_kind=count)
                for kind in ['artworks', 'jobs', 'assets']:
                    url = f'/api/{kind}' + ('?scope=all' if kind == 'artworks' else '')
                    if args.mode == 'paged':
                        url = f'/api/library/{kind}?limit=40&scope=all'
                    result[kind] = measure(client, url)
                    if args.mode == 'paged':
                        first = client.get(url).json()
                        result[kind]['next_page'] = measure(client, url + '&cursor=' + first['next_cursor'])
                        measured = result[kind]
                        assert measured['median_ms'] <= 1500, measured
                        assert measured['response_bytes'] <= 65536, measured
                        assert measured['python_peak_bytes'] <= 8 * 1024**2, measured
                        assert measured['rss_delta_bytes'] <= 32 * 1024**2, measured
                        assert measured['next_page']['median_ms'] <= 150, measured
                report['datasets'].append(result)
                print(json.dumps(result), flush=True)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()
