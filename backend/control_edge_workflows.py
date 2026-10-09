"""Versioned Canny workflow: the exact conditioning tensor also has a PNG output."""
from copy import deepcopy
import json
from uuid import UUID
from backend import control_workflows as legacy
ID='checkpoint-canny-controlnet-edge-v2'
EDGE_NODE='16'
FINAL_NODE='7'
location=legacy.location
save_input=legacy.save_input
uploads=legacy.uploads
prepare=legacy.prepare
check_nodes=legacy.check_nodes
CHECKED_NODES=legacy.CHECKED_NODES


def build(settings,job_id):
    graph=legacy.build(settings,job_id)
    graph[EDGE_NODE]=dict(class_type='SaveImage',inputs=dict(images=['13',0],filename_prefix='model_atelier/'+str(UUID(str(job_id)))+'/canny'))
    return graph


def extract(item,validate):
    message='Canny 邊緣流程不完整，未載入部分設定；請下載原流程'
    try:
        identifier=item.get('job_id',item['id']);graph=deepcopy(item['workflow'])
        expected=build(item['reference_settings'],identifier)[EDGE_NODE]
        actual={k:v for k,v in graph.pop(EDGE_NODE).items() if k!='_meta'}
        if json.dumps(actual,sort_keys=True,allow_nan=False)!=json.dumps(expected,sort_keys=True,allow_nan=False): raise ValueError(message)
        legacy_item=deepcopy(item);legacy_item['workflow']=graph
        return legacy.extract(legacy_item,validate)
    except (KeyError,ValueError,TypeError,AttributeError) as exc: raise ValueError(message) from exc
