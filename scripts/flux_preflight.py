"""Read-only local FLUX plan. No arbitrary paths, downloads or engine requests."""
import json
from pathlib import Path
from backend import flux_plan


def main():
    try:
        report = flux_plan.report(Path(__file__).resolve().parents[1])
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0 if report['space_status'] == 'sufficient' else 2
    except (OSError, ValueError, TypeError, KeyError):
        print(json.dumps({'error': '固定來源或本機磁碟預檢無法讀取；未下載或修改檔案。'}, ensure_ascii=False))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
