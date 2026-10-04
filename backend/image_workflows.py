"""Platform-owned single-image input; never accept arbitrary engine filenames."""
import hashlib
import io
import json
import asyncio
from copy import deepcopy
from uuid import UUID

from PIL import Image, ImageOps, __version__ as pillow_version
from backend import assets, node_preflight, workflows
from backend.reference_workflows import IMG2IMG_ID

MAX_ENCODED = 64 * 1024 * 1024


def location(job_id):
    return dict(name='reference.png', subfolder='model_atelier/' + str(UUID(str(job_id))), type='input')


def build(settings, job_id):
    value = workflows.build(settings)
    target = location(job_id)
    value['4'] = dict(class_type='VAEEncode', inputs=dict(pixels=['12', 0], vae=['1', 2]))
    value['12'] = dict(class_type='LoadImage', inputs=dict(image=target['subfolder'] + '/' + target['name']))
    return value


def prepare(db, data_folder, settings):
    asset_id = settings.get('image_asset_id')
    if not asset_id or settings['reference_ids'] != [asset_id]:
        raise ValueError('圖生圖需選擇一張輸入圖片，參考素材必須只包含該圖片')
    if settings['width'] * settings['height'] > assets.MAX_PIXELS:
        raise ValueError('圖生圖前處理的輸出不可超過 1600 萬像素')
    try:
        asset = assets.get(db, asset_id)
    except KeyError as exc:
        raise ValueError('輸入素材不存在，請重新選擇') from exc
    if asset['archived']:
        raise ValueError('輸入素材已封存，請先還原素材')
    path = data_folder / 'assets' / (asset_id + '.png')
    try:
        if path.is_symlink() or not path.resolve().is_relative_to(data_folder.resolve()) or path.stat().st_size > MAX_ENCODED:
            raise ValueError('輸入素材檔案不符合本機來源限制')
        with path.open('rb') as stream:
            raw = stream.read(MAX_ENCODED + 1)
    except OSError as exc:
        raise ValueError('輸入素材檔案遺失或無法讀取') from exc
    if len(raw) != asset['size'] or hashlib.sha256(raw).hexdigest() != asset['sha256']:
        raise ValueError('輸入素材 SHA256 或大小不符，未使用已變更的檔案')
    try:
        with Image.open(io.BytesIO(raw)) as image:
            if image.format != 'PNG' or image.size != (asset['width'], asset['height']) or image.width * image.height > assets.MAX_PIXELS:
                raise ValueError('輸入素材格式或尺寸與紀錄不符')
            image.load()
            rgba = image.convert('RGBA')
            rgb = Image.new('RGB', rgba.size, 'white')
            rgb.paste(rgba, mask=rgba.getchannel('A'))
            size = (settings['width'], settings['height'])
            if settings['reference_resize'] == 'fit':
                fitted = ImageOps.contain(rgb, size, Image.Resampling.LANCZOS)
                output = Image.new('RGB', size, 'white')
                output.paste(fitted, ((size[0] - fitted.width) // 2, (size[1] - fitted.height) // 2))
            else:
                output = rgb.resize(size, Image.Resampling.LANCZOS)
            output.info.clear()
            stream = io.BytesIO()
            output.save(stream, format='PNG')
    except OSError as exc:
        raise ValueError('輸入素材 PNG 損壞，未提交任務') from exc
    encoded = stream.getvalue()
    if len(encoded) > MAX_ENCODED:
        raise ValueError('處理後的輸入圖片過大')
    snapshot = deepcopy(asset)
    snapshot['generation_preprocessing'] = dict(id='checkpoint-image-input', version=1,
        library='Pillow', library_version=pillow_version, resize=settings['reference_resize'],
        resampling='LANCZOS', background='#ffffff', output_mode='RGB', output_format='PNG',
        width=size[0], height=size[1], sha256=hashlib.sha256(encoded).hexdigest(), size=len(encoded))
    return snapshot, encoded


def save_input(data_folder, job_id, encoded):
    folder = data_folder / 'job_inputs'
    folder.mkdir(exist_ok=True)
    if not folder.resolve().is_relative_to(data_folder.resolve()):
        raise OSError('輸入資料目錄超出平台資料範圍')
    path = folder / (str(UUID(str(job_id))) + '.png')
    # A new ledger reservation owns this filename. Never overwrite an older input.
    created = False
    try:
        with path.open('xb') as stream:
            created = True
            stream.write(encoded)
    except OSError:
        if created:
            path.unlink(missing_ok=True)
        raise


async def check_nodes(client, engine_url):
    async def inspect(name, required, output):
        response = await client.get(engine_url + '/object_info/' + name)
        response.raise_for_status()
        if len(response.content) > 1024 * 1024:
            raise ValueError('參考節點回應過大')
        body = response.json()
        if not isinstance(body, dict) or name not in body:
            raise node_preflight.MissingNodes('ComfyUI 缺少圖生圖必要節點：' + name + '；尚未提交任務')
        definition = body[name]
        input_definition = definition.get('input') if isinstance(definition, dict) else None
        inputs = input_definition.get('required', {}) if isinstance(input_definition, dict) else {}
        if not isinstance(inputs, dict) or set(inputs) != set(required) or definition.get('output') != output:
            raise ArithmeticError('圖生圖節點介面不相容：' + name)
        for key, kind in required.items():
            spec = inputs[key]
            if not isinstance(spec, list) or not spec:
                raise ArithmeticError('圖生圖節點輸入無效：' + name + '.' + key)
            if kind is None:
                if not isinstance(spec[0], list) or not all(isinstance(item, str) for item in spec[0]):
                    raise ArithmeticError('LoadImage 圖片選項格式無效')
            elif spec[0] != kind:
                raise ArithmeticError('圖生圖節點輸入類型不相容：' + name + '.' + key)

    results = await asyncio.gather(*(inspect(name, required, output) for name, required, output in (
        ('LoadImage', {'image': None}, ['IMAGE', 'MASK']),
        ('VAEEncode', {'pixels': 'IMAGE', 'vae': 'VAE'}, ['LATENT']),
    )), return_exceptions=True)
    for result in results:
        if isinstance(result, BaseException):
            raise result


def extract(item, validate):
    message = '圖生圖工作流程或來源快照不完整，請下載原工作流程；未載入部分設定'
    try:
        settings = validate(deepcopy(item['reference_settings']))
        refs = item['reference_metadata']
        owner = item.get('job_id', item['id'])
        if (settings['workflow_mode'] != 'image2image' or len(refs) != 1
                or settings['reference_ids'] != [refs[0]['id']] or settings['image_asset_id'] != refs[0]['id']
                or item['source']['node_id'] != '7' or settings['checkpoint'] != item['checkpoint']
                or settings['engine_url'] != item['engine_url']):
            raise ValueError(message)
        prep = refs[0]['generation_preprocessing']
        if any(prep[key] != settings[key] for key in ('width', 'height')) or prep['resize'] != settings['reference_resize'] or prep['version'] != 1:
            raise ValueError(message)
        expected = build(settings, owner)
        actual = {key: {name: value for name, value in node.items() if name != '_meta'} for key, node in item['workflow'].items()}
        if json.dumps(actual, sort_keys=True, allow_nan=False) != json.dumps(expected, sort_keys=True, allow_nan=False):
            raise ValueError(message)
        return settings
    except (KeyError, ValueError, TypeError, AttributeError) as exc:
        raise ValueError(message) from exc


def restoration_warnings(db, data_folder, snapshots):
    messages = []
    for original in snapshots or []:
        try:
            current = assets.get(db, original['id'])
            if current['archived'] or not (data_folder / 'assets' / (original['id'] + '.png')).is_file():
                messages.append('原輸入素材已封存或檔案遺失；已保留原設定，生成前需修復或重新選擇。')
            if current['sha256'] != original['sha256']:
                messages.append('原輸入素材的內容與當時快照不同，生成前會拒絕變更的檔案。')
        except KeyError:
            messages.append('原輸入素材不存在，已保留原 ID；生成前請修復或重新選擇。')
    return messages
