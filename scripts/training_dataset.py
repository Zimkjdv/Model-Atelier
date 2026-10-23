"""Prepare and verify local versioned SDXL datasets without starting training."""

import argparse
import json
from pathlib import Path
import sys

from backend import training_data as data, training_bundle as bundle

ROOT = Path(__file__).resolve().parents[1]


def expected_base():
    model = data.read_json(ROOT / 'models/animagine-xl-4.0-opt.json')[0]
    return data.BaseAnchor(
        id=model['id'],
        version=model['version'],
        architecture=model['architecture'].lower(),
        sha256=model['sha256'],
        size_bytes=model['size_bytes'],
        source_revision=model['source']['revision'],
    )


def inventory(root):
    root = Path(root).resolve(strict=True)
    if not root.is_dir():
        raise ValueError('來源必須是目錄')
    paths = []
    for path in root.rglob('*'):
        if path.is_symlink() or (hasattr(path, 'is_junction') and path.is_junction()):
            raise ValueError('來源目錄含連結；請提供一般檔案目錄')
        if path.is_file() and path.suffix.lower() in data.IMAGE_EXTENSIONS:
            paths.append(path.relative_to(root).as_posix())
            if len(paths) > 10000:
                raise ValueError('圖片不得超過 10000 張')
    return sorted(paths, key=str.casefold)


def initialize(root, *, dataset_id, version, kind, subject_id, trigger, study=None):
    paths = inventory(root)
    originals = {}
    if study:
        document, sha = study
        if type(document.get('schema_version')) is not int or document['schema_version'] != 1:
            raise ValueError('不支援的 R02 study 版本')
        originals = {r['relative_path']: r for r in document['images']}
        if len(originals) != len(document['images']) or set(paths) != set(originals):
            raise ValueError('來源圖片集合與 R02 凍結清單不同')
        paths = sorted(paths, key=lambda name: originals[name]['index'])
    images, seen, hashes = [], set(), {}
    for index, name in enumerate(paths, 1):
        identity, _ = data.read_source(root, name)
        original = originals.get(name)
        if original:
            if identity != dict(
                sha256=original['sha256'],
                size_bytes=original['size'],
                width=original['width'],
                height=original['height'],
            ):
                raise ValueError('來源圖片身分與 R02 清單不同：' + name)
            group = original['duplicate_group']
            split = {'reference': 'train', 'holdout': 'validation', 'excluded': 'excluded'}[
                original['split']
            ]
            exposure = ['r02_contact_sheet'] + (
                ['inference_reference'] if original['used_as_input'] else []
            )
            row_id = f'img-{original["index"]:03d}'
        else:
            group = hashes.setdefault(identity['sha256'], f'g{index:04d}')
            split, exposure, row_id = 'train', [], f'img-{index:04d}'
        reason = 'R02 已排除；需人工重新審查後另立版本' if split == 'excluded' else ''
        if split == 'train' and group in seen:
            split, reason = 'excluded', '完全重複或同原作差分；保留一張訓練候選'
        if split == 'train':
            seen.add(group)
        images.append(
            dict(
                id=row_id,
                path=name,
                **identity,
                group_id=group,
                split=split,
                exclusion_reason=reason,
                exposure=exposure,
            )
        )
    return data.Dataset(
        dataset_id=dataset_id,
        version=version,
        kind=kind,
        subject_id=subject_id,
        trigger=trigger,
        base_model=expected_base(),
        images=images,
        parent_study=data.StudyAnchor(id=study[0]['study_id'], sha256=study[1]) if study else None,
    )


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    init = commands.add_parser('init', help='建立待審查清單；不複製圖片或推定角色')
    init.add_argument('--dataset-id', required=True)
    init.add_argument('--version', required=True)
    init.add_argument('--kind', choices=('style', 'character'), required=True)
    init.add_argument('--subject-id', required=True)
    init.add_argument('--trigger', required=True)
    init.add_argument('--output', required=True)
    check = commands.add_parser('check', help='完整解碼與檢查原圖及 metadata；未準備好回傳 2')
    check.add_argument('manifest')
    check.add_argument('--report')
    export = commands.add_parser('export', help='只匯出通過檢查的 train 圖與 caption')
    export.add_argument('manifest')
    export.add_argument('--output', required=True)
    verify = commands.add_parser('verify-bundle', help='不讀原圖、不連網地檢查已封存資料包')
    verify.add_argument('bundle')
    for command in (init, check, export):
        command.add_argument('--source-root', required=True)
    for command in (init, check, export, verify):
        command.add_argument('--study', help='有 parent_study 時必須提供原始 R02 清單')
    args = parser.parse_args(argv)
    try:
        study = data.read_json(args.study) if args.study else None
        if args.command == 'init':
            target = bundle.safe_output(args.output, args.source_root)
            dataset = initialize(
                args.source_root,
                dataset_id=args.dataset_id,
                version=args.version,
                kind=args.kind,
                subject_id=args.subject_id,
                trigger=args.trigger,
                study=study,
            )
            bundle.write_new(target, data.manifest_bytes(dataset))
            result = dict(
                manifest=str(target),
                images=len(dataset.images),
                review_required=True,
                training_started=False,
            )
        elif args.command == 'verify-bundle':
            result = bundle.verify(args.bundle, expected_base(), study)
        else:
            dataset = data.load(args.manifest)
            if args.command == 'export':
                result = bundle.export(
                    dataset, args.source_root, args.output, expected_base(), study
                )
            else:
                result = data.audit(dataset, args.source_root, expected_base(), study)
                if args.report:
                    target = bundle.safe_output(args.report, args.source_root)
                    bundle.write_new(
                        target,
                        json.dumps(result, ensure_ascii=False, indent=2).encode('utf-8') + b'\n',
                    )
                print(json.dumps(result, ensure_ascii=True))
                return 0 if result['data_ready'] else 2
        print(json.dumps(result, ensure_ascii=True))
        return 0
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(
            json.dumps(dict(error=str(exc), training_started=False), ensure_ascii=True),
            file=sys.stderr,
        )
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
