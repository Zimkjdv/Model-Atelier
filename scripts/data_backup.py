"""Check, back up, verify, or restore local DATA without overwriting sources."""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend import backup
from backend.data_lease import DataBusyError


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    for name in ('check', 'backup'):
        sub = commands.add_parser(name)
        sub.add_argument('--data', type=Path, default=ROOT / 'data')
        sub.add_argument('--database', type=Path)
        if name == 'backup':
            sub.add_argument('--destination', type=Path, required=True)
            sub.add_argument('--platform-stopped', action='store_true')
            sub.add_argument('--evidence', type=Path, action='append', default=[])
    for name in ('verify', 'restore'):
        sub = commands.add_parser(name)
        sub.add_argument('--archive', type=Path, required=True)
        if name == 'restore':
            sub.add_argument('--destination', type=Path, required=True)
    args = vars(parser.parse_args(argv)); command = args.pop('command')
    try:
        result = getattr(backup, {'check': 'inspect'}.get(command, command))(**args)
        if command == 'verify':
            result = dict(ok=True, files=len(result['files']), inspection=result['inspection'])
        print(json.dumps(result, ensure_ascii=False))
        return 0 if result.get('ok') else 1
    except (backup.BackupError, DataBusyError, OSError, ValueError) as exc:
        print(json.dumps(dict(ok=False, error=str(exc)), ensure_ascii=False))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
