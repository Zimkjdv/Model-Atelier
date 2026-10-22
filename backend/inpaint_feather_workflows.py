"""Versioned inpaint with separate binary noise and inner feather blend masks."""
import hashlib
import io
import json
import os
import re
from copy import deepcopy
from uuid import UUID
from PIL import Image,ImageChops,ImageFilter,ImageOps,__version__ as pillow_version
from backend import inpaint_workflows as legacy
ID='checkpoint-inpaint-feather-v2'
MAX_BYTES=32*1024*1024
CHECKED_NODES=legacy.CHECKED_NODES
check_nodes=legacy.check_nodes


def location(job_id,role='source'):
    if role=='blend': return dict(name='blend.png',subfolder='model_atelier/'+str(UUID(str(job_id))),type='input')
    return legacy.location(job_id,role)


def build(settings,job_id):
    graph=legacy.build(settings,job_id);target=location(job_id,'blend')
    graph['15']=dict(class_type='LoadImageMask',inputs=dict(image=target['subfolder']+'/'+target['name'],channel='red'))
    graph['14']['inputs']['mask']=['15',0]
    return graph


def feather(binary,radius):
    if type(radius) is not int or not 0<=radius<=64: raise ValueError('羽化半徑需為 0–64 整數輸出像素')
    if binary.mode!='L' or sum(binary.histogram()[1:255]): raise ValueError('去噪遮罩必須是二值灰階')
    if radius==0: return binary.copy()
    padding=4*radius+4
    blurred=ImageOps.expand(binary,border=padding,fill=0).filter(ImageFilter.GaussianBlur(radius)).crop((padding,padding,padding+binary.width,padding+binary.height))
    ramp=blurred.point([max(0,min(255,round((v-128)*255/127))) for v in range(256)])
    result=ImageChops.multiply(binary,ramp)
    if result.getbbox() is None: raise ValueError('羽化後沒有可編輯像素，請減少半徑或擴大已保存遮罩')
    return result


def policy(settings,binary_hash,version=pillow_version):
    return dict(id='checkpoint-inpaint-blend-mask',version=1,method='inner-gaussian-threshold',library='Pillow',library_version=version,
        radius=settings['feather_radius'],radius_unit='output-pixels',blur_cutoff=128,quantization='round((v-128)*255/127), clipped 0..255',
        outside_binary='zero',image_border='black-padding-4r+4',binary_sha256=binary_hash,output_mode='RGB',output_format='PNG',width=settings['width'],height=settings['height'])


def prepare(db,folder,settings):
    refs,encoded=legacy.prepare(db,folder,settings)
    with Image.open(io.BytesIO(encoded['mask'])) as image: blend=feather(image.convert('L'),settings['feather_radius'])
    if settings['feather_radius']==0: raw=encoded['mask']
    else:
        stream=io.BytesIO();blend.convert('RGB').save(stream,format='PNG');raw=stream.getvalue()
    if len(raw)>MAX_BYTES: raise ValueError('合成遮罩超過 32 MiB')
    refs[1]['blend_preprocessing']=policy(settings,refs[1]['generation_preprocessing']['sha256'])|dict(sha256=hashlib.sha256(raw).hexdigest(),size=len(raw))
    return refs,encoded|dict(blend=raw)


def uploads(job_id,encoded): return [(location(job_id,role),encoded[role]) for role in ('source','mask','blend')]


def input_path(folder,job_id,role):
    root=folder.resolve();inputs=folder/'job_inputs'
    if inputs.is_symlink() or (hasattr(inputs,'is_junction') and inputs.is_junction()) or not inputs.resolve().is_relative_to(root): raise OSError('輸入目錄超出平台資料範圍')
    suffix={'source':'.png','mask':'.mask.png','blend':'.blend.png'}[role]
    target=inputs/(str(UUID(str(job_id)))+suffix)
    if target.is_symlink() or not target.resolve().is_relative_to(root): raise OSError('輸入檔案超出平台資料範圍')
    return target


def save_input(folder,job_id,encoded):
    targets={role:input_path(folder,job_id,role) for role in ('source','mask','blend')}
    (folder/'job_inputs').mkdir(exist_ok=True);created=[]
    try:
        for role,target in targets.items():
            with target.open('xb') as stream: created.append(target);stream.write(encoded[role]);stream.flush();os.fsync(stream.fileno())
    except BaseException:
        for target in created: target.unlink(missing_ok=True)
        raise


def extract(item,validate):
    message='羽化局部編輯流程或三份輸入快照不完整；未部分還原設定'
    try:
        settings=validate(deepcopy(item['reference_settings']));refs=item['reference_metadata'];prep=refs[1]['blend_preprocessing']
        if item.get('workflow_id')!=ID or type(settings['feather_radius']) is not int or not 0<=settings['feather_radius']<=64: raise ValueError(message)
        for ref in refs:
            binary=ref['generation_preprocessing']
            if any(type(binary.get(k)) is not int for k in ('version','width','height','size')) or not 0<binary['size']<=64*1024*1024 or not isinstance(binary.get('sha256'),str) or not re.fullmatch('[0-9a-f]{64}',binary['sha256']): raise ValueError(message)
        version=prep['library_version']
        if not isinstance(version,str) or not version or len(version)>100: raise ValueError(message)
        expected=policy(settings,refs[1]['generation_preprocessing']['sha256'],version)
        if set(prep)!=set(expected)|{'sha256','size'} or any(type(prep.get(k)) is not int for k in ('version','radius','width','height','size','blur_cutoff')) or any(prep.get(k)!=v for k,v in expected.items()) or not 0<prep['size']<=MAX_BYTES or not isinstance(prep['sha256'],str) or not re.fullmatch('[0-9a-f]{64}',prep['sha256']): raise ValueError(message)
        owner=item.get('job_id',item['id'])
        actual={k:{n:v for n,v in node.items() if n!='_meta'} for k,node in item['workflow'].items()}
        if json.dumps(actual,sort_keys=True,allow_nan=False)!=json.dumps(build(settings,owner),sort_keys=True,allow_nan=False): raise ValueError(message)
        previous=deepcopy(item);previous['workflow'].pop('15');previous['workflow']['14']['inputs']['mask']=['13',0]
        return legacy.extract(previous,validate)
    except (KeyError,ValueError,TypeError,AttributeError,IndexError) as exc: raise ValueError(message) from exc
