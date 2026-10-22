"""Submission-time benchmark conditions. Configuration is never execution evidence."""
from copy import deepcopy
import math

PRECISION_FLAGS = frozenset({'--force-fp32','--force-fp16','--fp32-unet','--fp64-unet','--bf16-unet',
    '--fp16-unet','--fp8_e4m3fn-unet','--fp8_e5m2-unet','--fp16-vae','--fp32-vae','--bf16-vae',
    '--fp8_e4m3fn-text-enc','--fp8_e5m2-text-enc','--fp16-text-enc','--fp32-text-enc','--bf16-text-enc'})
MEMORY_FLAGS = frozenset({'--gpu-only','--highvram','--normalvram','--lowvram','--novram','--cpu',
    '--cpu-vae','--disable-smart-memory','--disable-pinned-memory','--async-offload','--disable-async-offload'})
PARAMETERS = {'KSampler': ('steps','cfg','sampler_name','scheduler','denoise','seed'),
    'BasicScheduler': ('steps','scheduler','denoise'), 'KSamplerSelect': ('sampler_name',),
    'RandomNoise': ('noise_seed',), 'CFGGuider': ('cfg',), 'UNETLoader': ('weight_dtype',),
    'DualCLIPLoader': ('device',)}
REFERENCE_WORKFLOWS = {'checkpoint-image2image-v1','checkpoint-inpaint-v1','checkpoint-inpaint-feather-v2',
    'checkpoint-canny-controlnet-v1','checkpoint-canny-controlnet-edge-v2'}


def number(value):
    return type(value) in (int,float) and math.isfinite(value)


def capture(job, stats, workflow_id):
    system = stats.get('system') if isinstance(stats,dict) else None
    argv = system.get('argv') if isinstance(system,dict) else None
    available = isinstance(argv,list) and len(argv)<=256 and all(isinstance(v,str) and len(v)<=4096 for v in argv)
    # Never persist full argv: paths, tokens and unrelated launch options are private.
    flags = set(argv) if available else set()
    geometry = dict(width=None,height=None,batch_size=None,source='unknown')
    parameters=[]
    for identifier,node in job['workflow'].items():
        kind=node.get('class_type');inputs=node.get('inputs',{})
        if kind in ('EmptyLatentImage','EmptySD3LatentImage'):
            dimensions={k:inputs.get(k) for k in ('width','height','batch_size')}
            if all(type(v) is int and v>0 for v in dimensions.values()):
                geometry=dimensions | dict(source='workflow node '+identifier)
        selected={}
        for key in PARAMETERS.get(kind,()):
            value=inputs.get(key)
            if key in ('seed','noise_seed'):
                if type(value) is int and 0<=value<=2**64-1:selected[key]=str(value)
            elif number(value) or isinstance(value,str) and len(value)<=100:selected[key]=value
        if selected:parameters.append(dict(node_id=identifier,class_type=kind,settings=selected))
    settings=job.get('reference_settings')
    if workflow_id in REFERENCE_WORKFLOWS and isinstance(settings,dict):
        if all(type(settings.get(k)) is int and settings[k]>0 for k in ('width','height')):
            geometry=dict(width=settings['width'],height=settings['height'],batch_size=1,source='frozen reference settings')
    def model(item,role):
        return dict(role=role,**{k:deepcopy(item.get(k)) for k in ('name','version','architecture','sha256')})
    models=[]
    if isinstance(job.get('model_metadata'),dict):models.append(model(job['model_metadata'],'checkpoint'))
    elif job.get('checkpoint'):models.append(dict(role='checkpoint',name=job['checkpoint'],version=job.get('model_version'),architecture=None,sha256=None))
    for item in job.get('component_metadata') or []:models.append(model(item,item.get('role','component')))
    loras=deepcopy(job.get('lora_metadata'))
    return dict(schema_version=1,workload='inference',workflow_id=workflow_id,geometry=geometry,
        parameters=parameters,models=models,loras=loras,
        launch_policy=dict(source=job['engine_url']+'/system_stats.system.argv',reported=available,
            precision_flags=sorted(flags & PRECISION_FLAGS),memory_flags=sorted(flags & MEMORY_FLAGS)),
        actual_precision=None,actual_offload=None,cache_state='unknown',
        note='完整流程／設定及提交前版本與資源快照一同保存。啟動旗標僅為設定，不能證明實際精度、卸載或排隊後裝置；無旗標不代表預設模式。冷／熱快取未被可靠回報，保持未知。此紀錄為推論，不代表訓練需求或最低 VRAM。')
