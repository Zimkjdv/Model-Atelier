"""Pinned FLUX dependency inventory. No network, hashing, writes or GPU work."""
import json
import shutil
from pathlib import Path

from fastapi import HTTPException
from backend import environment, storage

MANIFEST = Path(__file__).resolve().parents[1] / 'models' / 'flux1-schnell-plan.json'
RESERVE_BYTES = 2 * 1024**3
BFL = '741f7c3ce8b383c54771c7003378a50191e9efe9'
ENCODERS = '6af2a98e3f615bdfa612fbd85da93d1ed5f69ef5'
PINNED = {
    'diffusion_model': ('diffusion_models', 'flux1-schnell.safetensors', 'black-forest-labs/FLUX.1-schnell', BFL, 23782506688,
                        '9403429e0052277ac2a87ad800adece5481eecefd9ed334e1f348723621d2a0a'),
    'vae': ('vae', 'ae.safetensors', 'black-forest-labs/FLUX.1-schnell', BFL, 335304388,
            'afc8e28272cd15db3919bacdb6918ce9c1ed22e96cb12c4d5ed0fba823529e38'),
    'clip_l': ('text_encoders', 'clip_l.safetensors', 'comfyanonymous/flux_text_encoders', ENCODERS, 246144152,
               '660c6f5b1abae9dc498ac2d21e1347d2abdb0cf6c0c0c8576cd796491d9a6cdd'),
    't5xxl': ('text_encoders', 't5xxl_fp8_e4m3fn_scaled.safetensors', 'comfyanonymous/flux_text_encoders', ENCODERS, 5157348688,
             'a498f0485dc9536735258018417c3fd7758dc3bccc0a645feaa472b34955557a'),
}


def manifest():
    if MANIFEST.stat().st_size > 64 * 1024:
        raise ValueError('Oversized manifest')
    value = json.loads(MANIFEST.read_text(encoding='utf-8'))
    if not isinstance(value, dict) or value.get('id') != 'flux1-schnell' or value.get('architecture') != 'flux':
        raise ValueError('Invalid plan')
    rows = value.get('components')
    if (not isinstance(rows, list) or len(rows) != 4 or not all(isinstance(row, dict) for row in rows)
            or {row.get('role') for row in rows} != set(PINNED)):
        raise ValueError('Invalid components')
    keys = ('category', 'filename', 'repository', 'revision', 'size_bytes', 'sha256')
    for row in rows:
        if tuple(row.get(key) for key in keys) != PINNED[row['role']] or type(row['size_bytes']) is not int:
            raise ValueError('Component identity is not pinned')
    return value


def report(root):
    value = manifest()
    root = Path(root).resolve(strict=True)
    runtime = root / 'runtime'
    components, volumes = [], {}
    for row in value['components']:
        row = dict(row)
        target = runtime / 'ComfyUI' / 'models' / row['category'] / row['filename']
        row.update(version='revision ' + row['revision'][:12], target=str(target), state='unknown',
                   actual_size_bytes=None, sha256_verified=False, error=None, volume_id=None,
                   source_url=f"https://huggingface.co/{row['repository']}/blob/{row['revision']}/{row['filename']}")
        components.append(row)
        try:
            resolved = target.resolve()
            if target.is_symlink() or not resolved.is_relative_to(runtime):
                raise ValueError('Unsafe managed path')
            if target.exists():
                if not target.is_file():
                    raise ValueError('Not a regular file')
                row['actual_size_bytes'] = target.stat().st_size
                row['state'] = 'present_unverified' if row['actual_size_bytes'] == row['size_bytes'] else 'size_mismatch'
            else:
                row['state'] = 'missing'
            ancestor = target.parent
            while not ancestor.exists():
                ancestor = ancestor.parent
            identity, label = storage.volume_identity(ancestor)
            row['volume_id'] = identity
            if identity not in volumes:
                free = shutil.disk_usage(ancestor).free
                if type(free) is not int or free < 0:
                    raise ValueError('Invalid disk capacity')
                volumes[identity] = dict(id=identity, path=label, free_bytes=free, required_bytes=RESERVE_BYTES)
            # Even same-sized files are unverified; reserve a full replacement
            # budget rather than claiming that unknown local files are installed.
            volumes[identity]['required_bytes'] += row['size_bytes']
        except (OSError, ValueError, RuntimeError):
            row.update(state='unknown', error='本機路徑不可讀或不在受管理 runtime；未寫入或改動檔案。', volume_id=None)
    disks = list(volumes.values())
    for disk in disks:
        disk['space_status'] = 'sufficient' if disk['free_bytes'] >= disk['required_bytes'] else 'insufficient'
    unknown = any(row['volume_id'] is None for row in components)
    status = 'unknown' if unknown else 'insufficient' if any(d['space_status'] == 'insufficient' for d in disks) else 'sufficient'
    return dict(id=value['id'], name=value['name'], architecture=value['architecture'], verified_at=value['verified_at'],
                source_url=value['source_url'], reference_url=value['reference_url'], license=value['license'],
                checked_at=environment.now(), scope='managed_local_comfyui_only', components=components, volumes=disks,
                total_size_bytes=sum(row['size_bytes'] for row in components), reserve_bytes_per_volume=RESERVE_BYTES,
                space_status=status, current_files_verified=False, generation_supported=False, download_supported=False,
                minimum_vram_bytes=None, minimum_ram_bytes=None,
                required_loaders=['UNETLoader', 'DualCLIPLoader', 'VAELoader'],
                warnings=['這是固定來源與本機磁碟預檢，不代表已安裝、可以生成或目前引擎已讀到這些檔案。',
                          '已有檔案仍需完整 SHA256 驗證；空間估算保守計入全部元件及每個磁碟區 2 GiB 預留，不回收既有檔案或 partial。',
                          'BFL 權重來源目前有 Hugging Face 帳號／條件確認門檻；平台不自動登入、接受條件或下載。',
                          '此選型不使用 SDXL 表單；FLUX 專用生成、LoRA、參考圖及 RTX 3060／4080 資源仍未驗證。',
                          '編碼器採 ComfyUI 範例引用的整合來源，與 BFL 主模型分開記錄；不將整合來源標記當作所有上游授權已核對。'])


def install(app, host):
    @app.get('/api/model-plans/flux1-schnell')
    def get_plan():
        try:
            return report(host.ROOT)
        except (OSError, ValueError, TypeError, KeyError):
            raise HTTPException(503, 'FLUX 固定來源或本機磁碟預檢無法讀取；未下載或修改檔案。')
