"""Published support boundaries; these are platform formats, not engine capability probes."""

from copy import deepcopy
from typing import Literal
from fastapi import HTTPException
from backend import inpaint_workflows, inpaint_feather_workflows
from backend import control_workflows, control_edge_workflows

FLOWS = (
    dict(
        id='checkpoint-structure-controlnet-v3',
        family='control',
        version=3,
        name='SDXL 姿勢／深度 v3',
        input_roles=['image_asset_id'],
        parameters=[
            'control_kind',
            'control_net_name',
            'control_strength',
            'control_start',
            'control_end',
        ],
    ),
    dict(
        id='checkpoint-ipadapter-reference-v1',
        family='reference',
        version=1,
        name='SDXL 畫風／角色外觀參考 v1',
        input_roles=['image_asset_id'],
        parameters=[
            'reference_mode',
            'ipadapter_name',
            'clip_vision_name',
            'reference_weight',
            'reference_start',
            'reference_end',
        ],
    ),
    dict(
        id=inpaint_workflows.ID,
        family='inpaint',
        version=1,
        name='局部編輯 v1',
        input_roles=['image_asset_id', 'mask_asset_id'],
        parameters=['grow_mask_by'],
    ),
    dict(
        id=inpaint_feather_workflows.ID,
        family='inpaint',
        version=2,
        name='羽化局部編輯 v2',
        input_roles=['image_asset_id', 'mask_asset_id'],
        parameters=['grow_mask_by', 'feather_radius'],
    ),
    dict(
        id=control_workflows.ID,
        family='control',
        version=1,
        name='Canny 結構參考 v1',
        input_roles=['image_asset_id'],
        parameters=[
            'control_net_name',
            'control_strength',
            'control_start',
            'control_end',
            'canny_low',
            'canny_high',
        ],
    ),
    dict(
        id=control_edge_workflows.ID,
        family='control',
        version=2,
        name='Canny 邊緣輸出 v2',
        input_roles=['image_asset_id'],
        parameters=[
            'control_net_name',
            'control_strength',
            'control_start',
            'control_end',
            'canny_low',
            'canny_high',
        ],
    ),
)
FLOWS = tuple(sorted(FLOWS, key=lambda flow: flow['version']))
IDS = frozenset(flow['id'] for flow in FLOWS)
SPECIAL_FIELDS = frozenset(field for flow in FLOWS for field in flow['parameters']) | {
    'mask_asset_id',
    '_atelier_inpaint_workflow_id',
    '_atelier_control_workflow_id',
    '_atelier_reference_workflow_id',
}


def problem(settings, operation, workflow_id=None):
    """Detect specialized payloads before a permissive legacy schema could drop fields."""
    fields = set(settings) if isinstance(settings, dict) else set()
    embedded_id = settings.get('workflow_id') if isinstance(settings, dict) else None
    if (
        isinstance(workflow_id, str)
        and workflow_id in IDS
        or isinstance(embedded_id, str)
        and embedded_id in IDS
        or fields & SPECIAL_FIELDS
    ):
        return (
            f'局部編輯／Canny／畫風角色參考專用流程尚不支援{operation}；'
            '未部分保存或轉成一般流程。請保留原圖、遮罩及控制設定，從原任務／作品載入，或下載完整工作流程 JSON。'
        )
    return None


def require_general(settings, operation, workflow_id=None):
    if message := problem(settings, operation, workflow_id):
        raise HTTPException(422, message)


def describe(family):
    return dict(
        schema_version=1,
        scope='platform_formats',
        decision='dedicated_format_required',
        workflows=[
            dict(
                deepcopy(flow),
                capabilities=dict(
                    draft=False,
                    settings_export=False,
                    settings_import=False,
                    comparison_plan=False,
                    restore_saved_settings=True,
                    download_workflow=True,
                ),
            )
            for flow in FLOWS
            if flow['family'] == family
        ],
        note='一般草稿、設定交換與比較方案尚未啟用專用格式；不會捨棄雙輸入、羽化或控制參數。'
        '可載入完整已保存設定（需本機素材可用）及下載原始 workflow；workflow 不包含素材圖片。',
    )


def install(app):
    @app.get('/api/reference-workflows/support')
    def support(family: Literal['inpaint', 'control', 'reference']):
        return describe(family)
