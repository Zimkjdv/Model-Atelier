"""Install an explicitly selected, reviewed checkpoint; --check performs no writes."""
import argparse
import json
import sys
from pathlib import Path

from scripts import install_pony as downloader


def manifest(model_id):
    if model_id not in downloader.SOURCES:
        raise downloader.InstallationError('不支援的模型 ID。')
    return downloader.load_manifest(downloader.WORKSPACE / 'models' / (model_id + '.json'))


def plan(value, *, workspace=downloader.WORKSPACE, restart=False):
    value = downloader.validate_manifest(value)
    target, partial, _, lock = downloader._paths(Path(workspace), value['filename'], create=False)
    for path in (target, partial):
        if path.exists() and not path.is_file():
            raise downloader.InstallationError('模型或 partial 不是一般檔案。')
    offset = partial.stat().st_size if partial.exists() else 0
    if offset > value['size_bytes'] and not restart:
        raise downloader.InstallationError('partial 大於預期模型，請先確認後明確使用 --restart。')
    remaining = 0 if target.exists() else value['size_bytes'] - (0 if restart else offset)
    disk_path = target.parent
    while not disk_path.exists():
        disk_path = disk_path.parent
    free = downloader.shutil.disk_usage(disk_path).free
    # Restart can reclaim only this partial, never another model or user data.
    reclaimable = offset if restart and not target.exists() else 0
    required = remaining + downloader.RESERVE_BYTES
    ready = not lock.exists() and (target.exists() or free + reclaimable >= required)
    return dict(model_id=value['id'], filename=value['filename'], target=str(target), size_bytes=value['size_bytes'],
                sha256=value['sha256'], partial_bytes=offset, download_remaining_bytes=remaining,
                free_bytes=free, reclaimable_partial_bytes=reclaimable, reserve_bytes=downloader.RESERVE_BYTES,
                required_bytes=required, ready=ready, installation_locked=lock.exists(),
                existing_requires_hash_verification=target.exists(),
                message='已有安裝鎖，請先確認安裝程序。' if lock.exists()
                else '已有正式檔案；安裝時仍核對完整大小及 SHA256，不保證目前檔案正確。' if target.exists()
                else '可開始下載；尚未安裝或驗證 GPU。' if ready
                else '可用磁碟空間不足，含 2 GiB 預留；未下載、刪除或改寫任何檔案。')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('model_id', choices=sorted(downloader.SOURCES))
    parser.add_argument('--check', action='store_true', help='唯讀檢查來源、partial、安裝鎖及磁碟；不下載或寫入')
    parser.add_argument('--restart', action='store_true', help='明確重置所選模型的 partial，不覆蓋正式檔案')
    parser.add_argument('--attempts', type=int, choices=range(1, 6), default=3)
    args = parser.parse_args(argv)
    try:
        value = manifest(args.model_id)
        if args.check:
            report = plan(value, restart=args.restart)
            print(json.dumps(report, ensure_ascii=False))
            return 0 if report['ready'] else 2
        downloader.install(manifest=value, restart=args.restart, attempts=args.attempts)
        return 0
    except KeyboardInterrupt:
        print('安裝中止；保留 partial，下次可續傳。', file=sys.stderr)
        return 130
    except (downloader.InstallationError, OSError, ValueError) as exc:
        print('安裝失敗：' + str(exc), file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
