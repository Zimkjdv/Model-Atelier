"""Owned source + binary luminance mask, one native checkpoint inpaint graph."""
import asyncio
import hashlib
import io
import json
import math
from copy import deepcopy
from uuid import UUID
from PIL import Image, ImageOps, __version__ as pillow_version
from backend import assets, image_workflows, node_preflight, workflows

ID = 'checkpoint-inpaint-v1'
CHECKED_NODES = ('LoadImage','LoadImageMask','VAEEncodeForInpaint','ImageCompositeMasked')


def location(job_id, role='source'):
    return dict(name='reference.png' if role=='source' else 'mask.png',subfolder='model_atelier/'+str(UUID(str(job_id))),type='input')


def build(settings, job_id):
    graph = workflows.build(settings)
    source,mask = location(job_id),location(job_id,'mask')
    graph['12'] = dict(class_type='LoadImage',inputs=dict(image=source['subfolder']+'/'+source['name']))
    graph['13'] = dict(class_type='LoadImageMask',inputs=dict(image=mask['subfolder']+'/'+mask['name'],channel='red'))
    graph['4'] = dict(class_type='VAEEncodeForInpaint',inputs=dict(pixels=['12',0],vae=['1',2],mask=['13',0],grow_mask_by=settings['grow_mask_by']))
    graph['14'] = dict(class_type='ImageCompositeMasked',inputs=dict(destination=['12',0],source=['6',0],x=0,y=0,resize_source=False,mask=['13',0]))
    graph['7']['inputs']['images'] = ['14',0]
    return graph


def prepare(db, folder, settings):
    source_id,mask_id = settings['image_asset_id'],settings['mask_asset_id']
    if not source_id or source_id == mask_id or settings['reference_ids'] != [source_id,mask_id]:
        raise ValueError('局部編輯需不同的原圖及遮罩，素材關聯順序為原圖、遮罩')
    source,encoded_source = image_workflows.prepare(db,folder,dict(settings,reference_ids=[source_id]))
    # Reuse the same verified file reader, with no resize before checking mask geometry.
    try:
        mask = assets.get(db,mask_id)
    except KeyError as exc:
        raise ValueError('遮罩素材不存在') from exc
    if (mask['width'],mask['height']) != (source['width'],source['height']):
        raise ValueError('遮罩必須與原圖的正規化尺寸完全相同，未自動拉伸錯位遮罩')
    _,raw = image_workflows.prepare(db,folder,dict(settings,image_asset_id=mask_id,reference_ids=[mask_id],
        width=mask['width'],height=mask['height'],reference_resize='stretch'))
    # prepare flattened transparency to white; mask semantics explicitly use that RGB.
    with Image.open(io.BytesIO(raw)) as image:
        binary = image.convert('L').point(lambda v:255 if v>=128 else 0)
    size = (settings['width'],settings['height'])
    if settings['reference_resize']=='fit':
        fitted = ImageOps.contain(binary,size,Image.Resampling.NEAREST)
        output = Image.new('L',size,0)
        output.paste(fitted,((size[0]-fitted.width)//2,(size[1]-fitted.height)//2))
    else:
        output = binary.resize(size,Image.Resampling.NEAREST)
    if output.getbbox() is None:
        raise ValueError('遮罩沒有白色編輯區域；未提交任務')
    stream=io.BytesIO();output.convert('RGB').save(stream,format='PNG');encoded_mask=stream.getvalue()
    source['input_role']='source'
    snapshot=deepcopy(mask)|dict(input_role='mask',generation_preprocessing=dict(id='checkpoint-inpaint-mask-input',version=1,
        library='Pillow',library_version=pillow_version,resize=settings['reference_resize'],resampling='NEAREST',
        transparency='white-background',threshold=128,white='edit',black='preserve',background='#000000',
        output_mode='RGB',output_format='PNG',width=size[0],height=size[1],
        sha256=hashlib.sha256(encoded_mask).hexdigest(),size=len(encoded_mask)))
    return [source,snapshot],dict(source=encoded_source,mask=encoded_mask)


def uploads(job_id, encoded):
    return [(location(job_id,role),encoded[role]) for role in ('source','mask')]


def save_input(folder, job_id, encoded):
    inputs=folder/'job_inputs';inputs.mkdir(exist_ok=True)
    if not inputs.resolve().is_relative_to(folder.resolve()):
        raise OSError('輸入目錄超出平台資料範圍')
    created=[]
    try:
        for role in ('source','mask'):
            target=inputs/(str(UUID(str(job_id)))+('.png' if role=='source' else '.mask.png'))
            with target.open('xb') as stream:
                created.append(target);stream.write(encoded[role])
    except OSError:
        for path in created: path.unlink(missing_ok=True)
        raise


async def check_nodes(client, engine, *, settings):
    definitions=(
        ('LoadImage',{'image':None},{},['IMAGE','MASK']),
        ('LoadImageMask',{'image':None,'channel':'red'},{},['MASK']),
        ('VAEEncodeForInpaint',{'pixels':'IMAGE','vae':'VAE','mask':'MASK','grow_mask_by':'INT'},{},['LATENT']),
        ('ImageCompositeMasked',{'destination':'IMAGE','source':'IMAGE','x':'INT','y':'INT','resize_source':'BOOLEAN'},{'mask':'MASK'},['IMAGE']))
    async def inspect(name, required, optional, output):
        response=await client.get(engine+'/object_info/'+name);response.raise_for_status()
        if len(response.content)>1024*1024: raise ValueError('節點定義過大')
        body=response.json()
        if not isinstance(body,dict) or name not in body:
            raise node_preflight.MissingNodes('ComfyUI 缺少局部編輯必要節點：'+name)
        definition=body[name];inputs=definition.get('input',{}) if isinstance(definition,dict) else {}
        required_input=inputs.get('required',{}) if isinstance(inputs,dict) else None
        optional_input=inputs.get('optional',{}) if isinstance(inputs,dict) else None
        if (not isinstance(required_input,dict) or not isinstance(optional_input,dict)
                or set(required_input)!=set(required) or set(optional_input)!=set(optional)
                or not isinstance(definition,dict) or definition.get('output')!=output):
            raise ArithmeticError('局部編輯節點介面不相容：'+name)
        for key,kind in (required|optional).items():
            spec=(required_input|optional_input)[key]
            if not isinstance(spec,list) or not spec: raise ArithmeticError('節點輸入格式無效：'+name)
            if kind in (None,'red'):
                if not isinstance(spec[0],list) or not all(isinstance(v,str) for v in spec[0]) or (kind=='red' and 'red' not in spec[0]):
                    raise ArithmeticError('局部編輯圖片／遮罩選項不相容')
            elif spec[0]!=kind: raise ArithmeticError('局部編輯節點輸入類型不相容：'+name+'.'+key)
            if kind=='INT':
                bound=spec[1] if len(spec)>1 and isinstance(spec[1],dict) else {}
                value=settings['grow_mask_by'] if key=='grow_mask_by' else 0
                low,high=bound.get('min'),bound.get('max')
                if type(low) not in (int,float) or type(high) not in (int,float) or not math.isfinite(low) or not math.isfinite(high) or not low<=value<=high:
                    raise ArithmeticError('局部編輯參數超出節點範圍：'+key)
    results=await asyncio.gather(*(inspect(*d) for d in definitions),return_exceptions=True)
    for result in results:
        if isinstance(result,BaseException): raise result


def extract(item, validate):
    message='局部編輯工作流程或雙輸入快照不完整，未載入部分設定；請下載原流程'
    try:
        settings=validate(deepcopy(item['reference_settings']));refs=item['reference_metadata']
        if (len(refs)!=2 or settings['reference_ids'] != [settings['image_asset_id'],settings['mask_asset_id']]
                or [r['id'] for r in refs]!=settings['reference_ids'] or [r.get('input_role') for r in refs]!=['source','mask']
                or settings['checkpoint']!=item['checkpoint'] or settings['engine_url']!=item['engine_url'] or item['source']['node_id']!='7'):
            raise ValueError(message)
        for ref in refs:
            prep=ref['generation_preprocessing']
            if any(prep[k]!=settings[k] for k in ('width','height')) or prep['resize']!=settings['reference_resize'] or prep['version']!=1:
                raise ValueError(message)
        mask_policy=dict(id='checkpoint-inpaint-mask-input',threshold=128,resampling='NEAREST',transparency='white-background',
            white='edit',black='preserve',background='#000000',output_mode='RGB',output_format='PNG')
        if any(refs[1]['generation_preprocessing'].get(k)!=v for k,v in mask_policy.items()): raise ValueError(message)
        owner=item.get('job_id',item['id'])
        actual={k:{n:v for n,v in node.items() if n!='_meta'} for k,node in item['workflow'].items()}
        if json.dumps(actual,sort_keys=True,allow_nan=False)!=json.dumps(build(settings,owner),sort_keys=True,allow_nan=False):
            raise ValueError(message)
        return settings
    except (KeyError,ValueError,TypeError,AttributeError) as exc:
        raise ValueError(message) from exc
