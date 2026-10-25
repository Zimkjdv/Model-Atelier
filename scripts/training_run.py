"""Prepare, explicitly launch, inspect, stop or resume one frozen SDXL run."""

import argparse
import json

from backend import training_runs as runs


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    prepare = commands.add_parser('prepare')
    prepare.add_argument('--config', required=True)
    prepare.add_argument('--study', help='Original R02 study JSON when required by the bundle.')
    for name in ('run', 'status', 'stop', 'resume'):
        command = commands.add_parser(name)
        command.add_argument('--run-id', required=True)
        if name == 'resume':
            command.add_argument('--checkpoint', required=True, help='Sealed step-N checkpoint ID.')
    args = parser.parse_args(argv)
    try:
        if args.command == 'prepare':
            from backend import training_data

            result = runs.prepare(
                runs.read_json(args.config),
                study=training_data.read_json(args.study) if args.study else None,
            )
        elif args.command == 'resume':
            old = runs.run_directory(args.run_id)
            manifest = runs.read_json(old / 'manifest.json')
            original_study = manifest.get('parent_study')
            result = runs.prepare(
                manifest['configuration'],
                resume=dict(run_id=args.run_id, checkpoint=args.checkpoint),
                study=(original_study['document'], original_study['sha256'])
                if original_study
                else None,
            )
        else:
            method = {'run': runs.launch, 'status': runs.inspect, 'stop': runs.stop}[args.command]
            result = method(args.run_id)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result.get('status') not in ('failed', 'blocked', 'interrupted') else 2
    except (OSError, ValueError) as exc:
        print(json.dumps(dict(error=str(exc)), ensure_ascii=False))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
