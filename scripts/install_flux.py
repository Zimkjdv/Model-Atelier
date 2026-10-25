"""Pinned FLUX installation: check access, install with resume, or verify local hashes.

Run with the platform Python: python -m scripts.install_flux check|install|verify.
Authentication is read from the official HF login cache or HF_TOKEN, never CLI arguments.
"""

import argparse
import json
import os
from pathlib import Path
import sys
from datetime import datetime, timezone

import httpx

from backend import flux_plan, storage
from scripts import install_pony as downloader


def component_manifests():
    rows = flux_plan.manifest()['components']
    result = []
    for row in rows:
        repository, revision, filename = row['repository'], row['revision'], row['filename']
        value = dict(
            id=f'flux1-schnell-{row["role"]}',
            name=row['name'],
            architecture='flux',
            version='revision ' + revision,
            filename=filename,
            size_bytes=row['size_bytes'],
            sha256=row['sha256'],
            source=dict(
                provider='Hugging Face',
                repository=repository,
                revision=revision,
                filename=filename,
                page_url=f'https://huggingface.co/{repository}/blob/{revision}/README.md',
                download_url=f'https://huggingface.co/{repository}/resolve/{revision}/{filename}',
            ),
            license=dict(
                name=row['license_name'],
                url=f'https://huggingface.co/{repository}/blob/{revision}/README.md',
                terms_verified=False,
                note='F01 固定來源安裝；完整元件授權與執行條件仍由 F02 另行核對。',
            ),
        )
        result.append(downloader.validate_manifest(value))
    return result


def read_token():
    """Follow official HF_TOKEN / HF_TOKEN_PATH / HF_HOME conventions, without logging."""
    token = os.environ.get('HF_TOKEN', '').strip()
    if not token:
        try:
            if os.environ.get('HF_TOKEN_PATH'):
                token_path = Path(os.environ['HF_TOKEN_PATH']).expanduser()
            elif os.environ.get('HF_HOME'):
                token_path = Path(os.environ['HF_HOME']).expanduser() / 'token'
            else:
                cache = (
                    Path(os.environ['XDG_CACHE_HOME']).expanduser()
                    if os.environ.get('XDG_CACHE_HOME')
                    else Path.home() / '.cache'
                )
                token_path = cache / 'huggingface' / 'token'
            with token_path.open('rb') as handle:
                raw = handle.read(4097)
            if len(raw) > 4096:
                raise ValueError()
            token = raw.decode('utf-8').strip()
        except FileNotFoundError:
            return None
        except (OSError, UnicodeError, ValueError, RuntimeError):
            raise downloader.InstallationError(
                'HF 本機登入資料無法讀取；請使用官方 hf auth login。'
            ) from None
    if len(token) > 4096 or any(ord(c) < 33 or ord(c) > 126 for c in token):
        raise downloader.InstallationError('HF 本機登入資料格式無效；請使用官方 hf auth login。')
    return token or None


def source_client(token, *, transport=None):
    # Never forward an account token to CDN redirects, arbitrary Hub paths, or HTTP.
    authenticated_paths = {
        httpx.URL(row['source']['download_url']).path
        for row in component_manifests()
        if row['source']['repository'] == 'black-forest-labs/FLUX.1-schnell'
    }

    def authorize(request):
        request.headers.pop('Authorization', None)
        if request.url.scheme != 'https':
            raise downloader.InstallationError('來源重新導向至非 HTTPS，已停止下載。')
        if (
            token
            and request.url.host == 'huggingface.co'
            and request.url.port in (None, 443)
            and request.url.path in authenticated_paths
        ):
            request.headers['Authorization'] = 'Bearer ' + token

    return httpx.Client(
        transport=transport,
        follow_redirects=True,
        trust_env=False,
        timeout=httpx.Timeout(60.0, connect=20.0),
        event_hooks={'request': [authorize]},
    )


def local_report(workspace, *, verify=False, restart_roles=()):
    rows, volumes = [], {}
    for value in component_manifests():
        role = downloader.FLUX_IDS[value['id']]
        target, partial, _, lock = downloader._paths(
            Path(workspace), value['filename'], create=False
        )
        for path in (target, partial):
            if path.exists() and not path.is_file():
                raise downloader.InstallationError('FLUX 模型或 partial 不是一般檔案。')
        actual = target.stat().st_size if target.exists() else None
        offset = partial.stat().st_size if partial.exists() else 0
        state = 'missing'
        if actual is not None:
            state = 'size_mismatch' if actual != value['size_bytes'] else 'present_unverified'
            if verify and state == 'present_unverified':
                state = 'verified' if downloader._verified(target, value) else 'hash_mismatch'
        restart = role in restart_roles and actual is None
        partial_valid = offset <= value['size_bytes'] or restart or actual is not None
        remaining = 0 if actual is not None else value['size_bytes'] - (0 if restart else offset)
        ancestor = target.parent
        while not ancestor.exists():
            ancestor = ancestor.parent
        volume_id, volume_path = storage.volume_identity(ancestor)
        if volume_id not in volumes:
            free = downloader.shutil.disk_usage(ancestor).free
            if type(free) is not int or free < 0:
                raise downloader.InstallationError('無法確認本機磁碟可用容量。')
            volumes[volume_id] = dict(
                id=volume_id,
                path=volume_path,
                free_bytes=free,
                download_remaining_bytes=0,
                reclaimable_partial_bytes=0,
                reserve_bytes=0,
            )
        disk = volumes[volume_id]
        disk['download_remaining_bytes'] += max(remaining, 0)
        disk['reclaimable_partial_bytes'] += offset if restart else 0
        if actual is None:
            disk['reserve_bytes'] = downloader.RESERVE_BYTES
        rows.append(
            dict(
                role=role,
                target=str(target),
                source=value['source'],
                size_bytes=value['size_bytes'],
                sha256=value['sha256'],
                actual_size_bytes=actual,
                partial_bytes=offset,
                partial_valid=partial_valid,
                state=state,
                sha256_verified=state == 'verified',
                installation_locked=lock.exists(),
                volume_id=volume_id,
            )
        )
    for disk in volumes.values():
        disk['required_bytes'] = disk['download_remaining_bytes'] + disk['reserve_bytes']
        disk['space_status'] = (
            'sufficient'
            if disk['free_bytes'] + disk['reclaimable_partial_bytes'] >= disk['required_bytes']
            else 'insufficient'
        )
    return dict(
        id='flux1-schnell',
        checked_at=datetime.now(timezone.utc).isoformat(),
        scope='managed_local_comfyui_only',
        components=rows,
        volumes=list(volumes.values()),
        total_size_bytes=sum(row['size_bytes'] for row in rows),
        current_files_verified=all(row['sha256_verified'] for row in rows),
        generation_verified=False,
        minimum_vram_bytes=None,
        minimum_ram_bytes=None,
    )


def check_access(client, *, roles=None):
    result = []
    for value in component_manifests():
        role = downloader.FLUX_IDS[value['id']]
        if roles is not None and role not in roles:
            continue
        status, state = None, 'unknown'
        try:
            with client.stream('HEAD', value['source']['download_url']) as response:
                status = response.status_code
                if status == 200:
                    length = response.headers.get('content-length')
                    state = (
                        'accessible'
                        if length is None or int(length) == value['size_bytes']
                        else 'size_mismatch'
                    )
                elif status in (401, 403):
                    state = 'access_denied'
                else:
                    state = 'unavailable'
        except (httpx.HTTPError, httpx.InvalidURL, ValueError):
            # HTTP exceptions/headers/redirect URLs may contain credentials or signed queries.
            state = 'unknown'
        result.append(dict(role=role, http_status=status, state=state))
    return result


def ready(report):
    return (
        all(
            row['state'] not in ('size_mismatch', 'hash_mismatch')
            and row['partial_valid']
            and not row['installation_locked']
            for row in report['components']
        )
        and all(row['space_status'] == 'sufficient' for row in report['volumes'])
        and all(row['state'] == 'accessible' for row in report.get('source_access', []))
    )


def install(*, workspace=downloader.WORKSPACE, client, restart_roles=(), attempts=3, output=print):
    report = local_report(workspace, verify=True, restart_roles=restart_roles)
    if not ready(report):
        raise downloader.InstallationError(
            'FLUX 本機磁碟、檔案或安裝鎖檢查未通過；未開始下載。先執行 check / verify 查看缺項。'
        )
    # Check every required source before creating model directories or downloading any payload.
    missing = {row['role'] for row in report['components'] if row['state'] == 'missing'}
    report['source_access'] = check_access(client, roles=missing)
    if not ready(report):
        raise downloader.InstallationError(
            'FLUX 來源存取、磁碟、檔案或安裝鎖檢查未通過；未開始下載。先執行 check / verify 查看缺項。'
        )
    for value, row in zip(component_manifests(), report['components'], strict=True):
        if row['sha256_verified']:
            output(f'{row["role"]}: 完整 SHA256 已驗證，沿用本機檔案。')
            continue
        result = downloader.install(
            workspace=Path(workspace),
            manifest=value,
            client=client,
            restart=row['role'] in restart_roles,
            attempts=attempts,
            output=output,
        )
        row.update(
            state='verified',
            sha256_verified=result['verified'],
            actual_size_bytes=result['size_bytes'],
            partial_bytes=0,
        )
    report.update(current_files_verified=True, checked_at=datetime.now(timezone.utc).isoformat())
    # Disk/partial values above were the pre-install budget, not post-install measurements.
    report['volumes_before_install'] = report.pop('volumes')
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('check', 'install', 'verify'))
    parser.add_argument(
        '--restart-role', action='append', choices=tuple(flux_plan.PINNED), default=[]
    )
    parser.add_argument('--attempts', type=int, choices=range(1, 6), default=3)
    args = parser.parse_args(argv)
    if args.restart_role and args.command != 'install':
        parser.error('--restart-role 僅用於明確重置 install 所選元件的 partial。')
    try:
        if args.command == 'verify':
            report = local_report(downloader.WORKSPACE, verify=True)
            code = 0 if report['current_files_verified'] else 2
        else:
            token = read_token()
            with source_client(token) as client:
                if args.command == 'check':
                    report = local_report(downloader.WORKSPACE)
                    report['source_access'] = check_access(client)
                    report['ready_for_install'] = ready(report)
                    code = 0 if report['ready_for_install'] else 2
                else:
                    report = install(
                        client=client,
                        restart_roles=args.restart_role,
                        attempts=args.attempts,
                        output=lambda line: print(line, file=sys.stderr, flush=True),
                    )
                    code = 0
            report['credential_available'] = bool(token)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return code
    except KeyboardInterrupt:
        print('安裝中止；保留 partial，下次可續傳。', file=sys.stderr)
        return 130
    except (httpx.HTTPError, httpx.InvalidURL):
        print(
            'FLUX 來源連線或重新導向失敗；未輸出遠端網址，保留已下載的 partial。', file=sys.stderr
        )
        return 1
    except (downloader.InstallationError, OSError, ValueError) as exc:
        print('FLUX 檢查／安裝失敗：' + str(exc), file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
    raise SystemExit(main())
