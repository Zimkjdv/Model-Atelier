"""Run fixed public descriptions against a local Ollama, using temporary platform data."""

import argparse
import json
from pathlib import Path
import platform
import sys
import tempfile
from datetime import datetime, timezone

import httpx
import psutil
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend.main import create_app

CASES = [
    dict(id='color-negation', description='一隻黑貓坐在窗邊，不要項圈，水彩風格'),
    dict(
        id='count-relations',
        description='兩位成年女性並排站在花園，左邊穿紅色外套，右邊穿藍色外套，沒有其他人',
    ),
    dict(
        id='hands-action', description='一位成年男子左手拿著合上的書，右手握著白色杯子，坐在木椅上'
    ),
    dict(
        id='landscape-flux',
        description='清晨的山間湖泊，薄霧覆蓋水面，遠處有松樹，畫面中沒有人或建築',
        profile='flux',
    ),
    dict(
        id='pony-tags',
        description='一位成年女性，綠色眼睛，黑色短髮，穿黃色雨衣，站在下雨的街道',
        profile='pony',
        style='tags',
    ),
    dict(
        id='literal-trigger',
        description='一位成年女性在圖書館看書，鉛筆素描風格，不要彩色',
        protected_terms=['atelier_char_v1'],
    ),
]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url', default='http://127.0.0.1:11434')
    parser.add_argument('--model', default='qwen3.5:2b')
    parser.add_argument('--output', default='runtime/prompt-llm/acceptance.json')
    args = parser.parse_args()
    results = []
    with tempfile.TemporaryDirectory(prefix='atelier-prompt-') as directory:
        app = create_app(data_root=directory)
        with TestClient(app, base_url='http://127.0.0.1', client=('127.0.0.1', 1)) as client:
            saved = client.put(
                '/api/prompt-converter/settings', json={'base_url': args.url, 'model': args.model}
            )
            saved.raise_for_status()
            status = client.get('/api/prompt-converter/status')
            status.raise_for_status()
            for item in CASES:
                body = {key: value for key, value in item.items() if key != 'id'}
                response = client.post('/api/prompt-converter/convert', json=body)
                result = dict(case=item, status=response.status_code, result=response.json())
                results.append(result)
                print(json.dumps(result, ensure_ascii=False), flush=True)
    with httpx.Client(trust_env=False, timeout=10) as local:
        version = local.get(args.url + '/api/version').json()
        models = local.get(args.url + '/api/tags').json()
        running = local.get(args.url + '/api/ps').json()
    report = dict(
        measured_at=datetime.now(timezone.utc).isoformat(),
        platform=platform.platform(),
        cpu=platform.processor(),
        ram_bytes=psutil.virtual_memory().total,
        ollama=version,
        installed_models=models,
        running_after=running,
        cases=results,
        limitation='Fixed text conversions only; semantic fidelity requires inspection. No image quality or GPU coexistence acceptance.',
    )
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return 0 if all(item['status'] == 200 for item in results) else 1


if __name__ == '__main__':
    raise SystemExit(main())
