"""Register a completed LoRA, publish metadata or prepare native evaluation plans."""

import argparse
import json
import httpx

from backend import training_artifacts as artifacts
from scripts.verify_local_generation import local_url


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    register = commands.add_parser('register')
    register.add_argument('--run-id', required=True)
    for name in ('publish', 'evaluation', 'save-plans'):
        command = commands.add_parser(name)
        command.add_argument('--platform', default='http://127.0.0.1:8000')
        if name != 'save-plans':
            command.add_argument('--run-id', required=True)
        if name != 'publish':
            command.add_argument('--output', required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == 'register':
            result = artifacts.register(args.run_id)
        else:
            with httpx.Client(
                base_url=local_url(args.platform), timeout=30, trust_env=False
            ) as client:
                if args.command == 'publish':
                    result = artifacts.publish(client, args.run_id)
                elif args.command == 'evaluation':
                    result = artifacts.evaluation(client, args.run_id, args.output)
                else:
                    result = artifacts.save_plans(client, args.output)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (OSError, ValueError, KeyError, TypeError, httpx.HTTPError) as exc:
        print(json.dumps(dict(error=str(exc)), ensure_ascii=False))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
