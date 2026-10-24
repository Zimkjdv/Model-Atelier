"""Explicit installer/checker for the separate pinned Windows SDXL trainer."""

import argparse
import json

from backend import training_environment as environment


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        '--install', action='store_true', help='Explicitly install the pinned isolated environment.'
    )
    args = parser.parse_args(argv)
    try:
        result = environment.install() if args.install else environment.check()
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result['ready'] else 2
    except (OSError, ValueError) as exc:
        print(json.dumps(dict(ready=False, error=str(exc)), ensure_ascii=False))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
