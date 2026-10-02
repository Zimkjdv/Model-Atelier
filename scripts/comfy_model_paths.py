"""Export local checkpoint directories using ComfyUI's standard-library Python."""
import argparse
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend import model_paths


def main(argv=None, *, root=ROOT):
    parser = argparse.ArgumentParser(description='Export registered local checkpoint directories before starting managed ComfyUI.')
    parser.parse_args(argv)
    try:
        target = model_paths.export(Path(root) / 'data' / 'atelier.sqlite3', root)
    except (OSError, ValueError, sqlite3.Error) as exc:
        print('Local checkpoint directory export failed; ComfyUI was not started: ' + str(exc), file=sys.stderr)
        return 1
    print(str(target))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
