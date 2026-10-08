"""Immutable experiment association, checked inside the job reservation transaction."""
import hashlib
import json
from copy import deepcopy
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field


class Selection(BaseModel):
    model_config = ConfigDict(extra='forbid')
    plan_id: UUID
    plan_sha256: str = Field(pattern=r'^[a-f0-9]{64}$')
    variant_id: str = Field(pattern=r'^variant-[1-8]$')


def matches(snapshot, selection, settings):
    if snapshot is None:
        return selection is None
    return (selection is not None and all(snapshot.get(k) == selection.get(k)
            for k in Selection.model_fields) and snapshot.get('settings') == settings)


def freeze(db, selection, settings):
    if selection is None:
        return None
    row = db.execute('SELECT value FROM settings WHERE key=?', ('experiment:' + selection['plan_id'],)).fetchone()
    if not row:
        raise ValueError('比較方案不存在；未提交任務')
    record = json.loads(row[0])
    plan = record['plan']
    raw = json.dumps({k:v for k,v in plan.items() if k not in ('plan_sha256','warnings')},
                     ensure_ascii=False, sort_keys=True, separators=(',',':'), allow_nan=False)
    if plan['plan_sha256'] != selection['plan_sha256'] or hashlib.sha256(raw.encode()).hexdigest() != selection['plan_sha256']:
        raise ValueError('比較方案 hash 不符；未提交任務')
    if record['archived']:
        raise ValueError('比較方案已封存，請先還原；未提交新任務')
    variant = next((v for v in plan['variants'] if v['id'] == selection['variant_id']), None)
    if not variant or variant['settings'] != settings:
        raise ValueError('設定與比較組快照不符；請重新載入該組或解除比較關聯，未提交任務')
    return deepcopy(selection | dict(schema_version=1, plan_title=plan['title'], workflow_id=plan['workflow_id'],
        axis=plan['axis'], target_lora=plan.get('target_lora'), case_id=variant['case_id'],
        value=variant['value'], settings=variant['settings']))
