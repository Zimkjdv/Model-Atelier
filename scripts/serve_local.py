"""Explicitly start the local platform on a selected, verified DATA directory."""
import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data', type=Path, required=True)
    parser.add_argument('--database', type=Path)
    parser.add_argument('--port', type=int, default=8000)
    args = parser.parse_args()
    data = args.data.resolve()
    if (data / '.incomplete').exists() or (data.parent / '.incomplete').exists():
        parser.error('拒絕使用 incomplete 還原目錄；請先完成 verify／restore')
    if not data.is_dir() or not (args.database or data / 'atelier.sqlite3').is_file():
        parser.error('指定資料目錄或資料庫不存在；不自動建立空白還原資料')
    import uvicorn
    from backend.main import create_app
    uvicorn.run(create_app(data_root=args.data, database=args.database), host='127.0.0.1',
                port=args.port, timeout_graceful_shutdown=5)


if __name__ == '__main__':
    main()
