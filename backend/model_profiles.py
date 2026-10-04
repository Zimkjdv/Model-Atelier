"""Registered architecture hints and explicit, opt-in starting parameters."""
import copy
import json
import re
from pathlib import Path

from fastapi import Query

ARCHITECTURES = {'unknown', 'sd1', 'sdxl', 'sd3', 'flux', 'other'}
LABELS = {'sd1': 'SD 1.x', 'sdxl': 'SDXL', 'sd3': 'SD3', 'flux': 'FLUX', 'other': '其他'}
REGISTRATION_NOTE = '架構與 SHA256 來自使用者登記；此查詢未讀取或驗證實際權重檔，也不保證硬體或節點執行成功。'


def pinned_hash(filename):
    try:
        value = json.loads((Path(__file__).resolve().parents[1] / 'models' / filename).read_text(encoding='utf-8'))['sha256']
        return value if isinstance(value, str) and re.fullmatch(r'[0-9a-f]{64}', value) else None
    except (OSError, KeyError, TypeError, ValueError):
        return None


PONY_SHA256 = pinned_hash('pony-v6-xl.json')
ANIMAGINE_SHA256 = pinned_hash('animagine-xl-4.0-opt.json')
PONY_PROMPT_HINT = ('score_9,score_8_up,score_7_up,rating_safe,source_anime,landscape,mountain lake,'
                    'pine forest,blue sky,peaceful daylight,scenery,no humans')


def architecture(value):
    return value if isinstance(value, str) and value in ARCHITECTURES else 'unknown'


def compatibility(value):
    value = architecture(value)
    if value in ('sd1', 'sdxl'):
        return dict(status='supported', allows_submission=True,
                    message=f'已登記為 {LABELS[value]}，適用目前標準 7 節點 checkpoint 文生圖流程。{REGISTRATION_NOTE}')
    if value == 'unknown':
        return dict(status='unknown', allows_submission=True,
                    message=f'模型架構未知；不提供起始預設，仍可提交標準流程交由 ComfyUI 驗證。{REGISTRATION_NOTE}')
    return dict(status='unsupported', allows_submission=False,
                message=f'已登記為 {LABELS[value]}，需要專用工作流程；目前標準 7 節點 checkpoint 文生圖流程尚未支援此架構，無法提交。{REGISTRATION_NOTE}')


def preset(model):
    kind = architecture(model.get('architecture'))
    if kind not in ('sd1', 'sdxl'):
        return None
    settings = dict(width=512 if kind == 'sd1' else 768, height=512 if kind == 'sd1' else 768,
                    steps=20, cfg=7.0, sampler_name='euler', scheduler='normal', denoise=1.0)
    if kind == 'sdxl' and PONY_SHA256 is not None and model.get('sha256') == PONY_SHA256:
        settings.update(cfg=5.5, sampler_name='dpmpp_2m', scheduler='karras')
        return dict(id='pony-v6-xl-rtx3060-landscape', name='Pony V6 XL：RTX 3060 風景起始預設',
                    description='本專案 RTX 3060 單張風景生成已驗；只依登記 SHA256 匹配正式模型 manifest，未驗證目前檔案。',
                    validation='本專案 RTX 3060 12GB：768×768、單張風景生成與重啟後作品保存驗收通過；不代表所有題材或硬體都已驗證。',
                    reference='docs/validation/pony-v6-xl-rtx3060.md', prompt_hint=PONY_PROMPT_HINT, settings=settings)
    if kind == 'sdxl' and ANIMAGINE_SHA256 is not None and model.get('sha256') == ANIMAGINE_SHA256:
        settings.update(width=1024, height=1024, steps=28, cfg=5.0, sampler_name='euler_ancestral')
        return dict(id='animagine-xl-4.0-opt-author', name='Animagine XL 4.0 Opt：作者建議起始預設',
                    description='依固定作者模型卡提供參數；只依登記 SHA256 匹配 manifest，未驗證目前檔案。Scheduler normal 與 denoise 1 為平台標準流程選擇。',
                    validation='尚未在本專案安裝或實測；1024×1024 不代表目前 GPU 可執行，提交仍需通過引擎能力檢查。',
                    reference='docs/models/animagine-xl-4.0-opt.md', prompt_hint='', settings=settings)
    return dict(id=kind + '-starter', name=LABELS[kind] + '：一般起始預設',
                description='依使用者登記架構提供起始參數；僅在使用者選擇套用後修改取樣設定。',
                validation='尚未逐模型實測。' if kind == 'sdxl' else '尚未實測。', reference='', prompt_hint='', settings=settings)


def profile(engine_url, model):
    kind = architecture(model.get('architecture'))
    return dict(engine_url=engine_url, name=model['name'], architecture=kind,
                metadata_updated_at=model.get('metadata_updated_at'), compatibility=compatibility(kind),
                workflow=workflow_description(kind),
                preset=copy.deepcopy(preset(model)))


def workflow_description(kind):
    if not compatibility(kind)['allows_submission']:
        return None
    return dict(id='checkpoint-text2image-v1', name='標準 checkpoint 單張文生圖',
                fields=['prompt', 'negative_prompt', 'seed', 'width', 'height', 'steps', 'cfg',
                        'sampler_name', 'scheduler', 'denoise', 'loras'], batch_size=1,
                reference_images=False, lora=True, max_loras=4,
                verification='registered_architecture' if kind in ('sd1', 'sdxl') else 'engine_validation_required')


def install(app, host):
    @app.get('/api/models/profile')
    def get_profile(engine_url: str = Query(min_length=1, max_length=2048),
                    name: str = Query(min_length=1, max_length=2048)):
        _, model = host.current_catalog(host.ModelTarget(engine_url=engine_url, name=name))
        return profile(engine_url, model)
