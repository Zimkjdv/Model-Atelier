"""One owned source -> native Canny -> matching ControlNet conditioning."""
import asyncio
import json
import math
from copy import deepcopy
from backend import control_catalog,image_workflows,node_preflight,workflows
ID='checkpoint-canny-controlnet-v1'
CHECKED_NODES=('LoadImage','Canny','ControlNetLoader','ControlNetApplyAdvanced')
location=image_workflows.location
save_input=image_workflows.save_input
uploads=image_workflows.uploads


def build(settings,job_id):
    graph=workflows.build(settings);target=location(job_id)
    graph['12']=dict(class_type='LoadImage',inputs=dict(image=target['subfolder']+'/'+target['name']))
    graph['13']=dict(class_type='Canny',inputs=dict(image=['12',0],low_threshold=settings['canny_low'],high_threshold=settings['canny_high']))
    graph['14']=dict(class_type='ControlNetLoader',inputs=dict(control_net_name=settings['control_net_name']))
    graph['15']=dict(class_type='ControlNetApplyAdvanced',inputs=dict(positive=['2',0],negative=['3',0],control_net=['14',0],image=['13',0],vae=['1',2],strength=settings['control_strength'],start_percent=settings['control_start'],end_percent=settings['control_end']))
    graph['5']['inputs'].update(positive=['15',0],negative=['15',1])
    return graph


def prepare(db,folder,settings):
    source,encoded=image_workflows.prepare(db,folder,settings)
    source.update(input_role='structure',control_preprocessing=dict(id='comfy-native-canny',version=1,low_threshold=settings['canny_low'],high_threshold=settings['canny_high'],execution='original-engine',node_version=None))
    return source,encoded


async def check_nodes(client,engine,*,settings):
    specs=(('LoadImage',{'image':None},{},['IMAGE','MASK']),('Canny',{'image':'IMAGE','low_threshold':'FLOAT','high_threshold':'FLOAT'},{},['IMAGE']),
        ('ControlNetLoader',{'control_net_name':None},{},['CONTROL_NET']),
        ('ControlNetApplyAdvanced',{'positive':'CONDITIONING','negative':'CONDITIONING','control_net':'CONTROL_NET','image':'IMAGE','strength':'FLOAT','start_percent':'FLOAT','end_percent':'FLOAT'},{'vae':'VAE'},['CONDITIONING','CONDITIONING']))
    values=dict(low_threshold=settings['canny_low'],high_threshold=settings['canny_high'],strength=settings['control_strength'],start_percent=settings['control_start'],end_percent=settings['control_end'])
    async def inspect(name,required,optional,output):
        response=await client.get(engine+'/object_info/'+name);response.raise_for_status()
        if len(response.content)>1024*1024: raise ValueError('節點定義過大')
        body=response.json()
        if not isinstance(body,dict) or name not in body: raise node_preflight.MissingNodes('ComfyUI 缺少結構參考必要節點：'+name)
        node=body[name];inputs=node.get('input') if isinstance(node,dict) else None
        req=inputs.get('required') if isinstance(inputs,dict) else None;opt=inputs.get('optional',{}) if isinstance(inputs,dict) else None
        if not isinstance(req,dict) or not isinstance(opt,dict) or set(req)!=set(required) or set(opt)!=set(optional) or node.get('output')!=output: raise ArithmeticError('結構參考節點介面不相容：'+name)
        for key,kind in (required|optional).items():
            spec=(req|opt)[key]
            if not isinstance(spec,list) or not spec: raise ArithmeticError('控制節點輸入定義無效')
            if kind is None:
                if not isinstance(spec[0],list) or any(not isinstance(v,str) for v in spec[0]): raise ArithmeticError('控制節點選项無效')
                if key=='control_net_name' and settings['control_net_name'] not in spec[0]: raise LookupError('所選 ControlNet 不在原引擎即時清單，未上傳或提交')
            elif spec[0]!=kind: raise ArithmeticError('控制節點型別不相容：'+key)
            if kind=='FLOAT':
                bounds=spec[1] if len(spec)>1 and isinstance(spec[1],dict) else {};low,high=bounds.get('min'),bounds.get('max')
                if type(low) not in (int,float) or type(high) not in (int,float) or not math.isfinite(low) or not math.isfinite(high) or not low<=values[key]<=high: raise ArithmeticError('控制參數超出原節點範圍：'+key)
    results=await asyncio.gather(*(inspect(*spec) for spec in specs),return_exceptions=True)
    for result in results:
        if isinstance(result,BaseException): raise result


def extract(item,validate):
    message='結構參考工作流程或來源快照不完整，未載入部分設定；請下載原流程'
    try:
        settings=validate(deepcopy(item['reference_settings']));refs=item['reference_metadata'];components=item['component_metadata']
        if (settings['checkpoint']!=item['checkpoint'] or settings['engine_url']!=item['engine_url'] or item['source']['node_id']!='7'
            or len(refs)!=1 or refs[0]['id']!=settings['image_asset_id'] or refs[0].get('input_role')!='structure' or settings['reference_ids']!=[refs[0]['id']]
            or len(components)!=1 or components[0]['role']!='controlnet' or components[0]['name']!=settings['control_net_name'] or components[0]['kind']!='canny' or components[0]['architecture'] not in ('sd1','sdxl') or components[0]['architecture']!=item['model_metadata']['architecture']): raise ValueError(message)
        prep=refs[0]['generation_preprocessing'];control=refs[0]['control_preprocessing']
        if prep['version']!=1 or any(prep[k]!=settings[k] for k in ('width','height')) or prep['resize']!=settings['reference_resize']: raise ValueError(message)
        if control!=dict(id='comfy-native-canny',version=1,low_threshold=settings['canny_low'],high_threshold=settings['canny_high'],execution='original-engine',node_version=None): raise ValueError(message)
        graph={k:{n:v for n,v in node.items() if n!='_meta'} for k,node in item['workflow'].items()}
        if json.dumps(graph,sort_keys=True,allow_nan=False)!=json.dumps(build(settings,item.get('job_id',item['id'])),sort_keys=True,allow_nan=False): raise ValueError(message)
        return settings
    except (ValueError,KeyError,TypeError,AttributeError) as exc: raise ValueError(message) from exc
