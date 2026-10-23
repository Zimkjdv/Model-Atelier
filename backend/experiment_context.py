"""Immutable experiment association, checked inside the job reservation transaction."""

import hashlib
import json
from copy import deepcopy
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field
from backend import experiment_models


class Selection(BaseModel):
    model_config = ConfigDict(extra='forbid')
    plan_id: UUID
    plan_sha256: str = Field(pattern=r'^[a-f0-9]{64}$')
    variant_id: str = Field(pattern=r'^variant-[1-8]$')


def plan_digest(value):
    content = {key: item for key, item in value.items() if key not in ('plan_sha256', 'warnings')}
    if value.get('schema_version') == 2:
        # JavaScript serializes 7.0 as 7. Keep the published v1 hash contract unchanged.
        def numbers(item):
            if isinstance(item, dict):
                return {key: numbers(child) for key, child in item.items()}
            if isinstance(item, list):
                return [numbers(child) for child in item]
            return int(item) if isinstance(item, float) and item.is_integer() else item

        content = numbers(content)
    raw = json.dumps(
        content, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False
    )
    return hashlib.sha256(raw.encode()).hexdigest()


def matches(snapshot, selection, settings):
    if snapshot is None:
        return selection is None
    return (
        selection is not None
        and all(snapshot.get(k) == selection.get(k) for k in Selection.model_fields)
        and snapshot.get('settings') == settings
    )


def snapshot(plan, selection, variant):
    result = deepcopy(
        selection
        | dict(
            schema_version=1,
            plan_title=plan['title'],
            workflow_id=plan['workflow_id'],
            axis=plan['axis'],
            target_lora=plan.get('target_lora'),
            case_id=variant['case_id'],
            value=variant['value'],
            settings=variant['settings'],
        )
    )
    if plan['schema_version'] == 2:
        result.update(
            schema_version=2, expected_model_metadata=experiment_models.expected(plan, variant)
        )
    return result


def freeze(db, selection, settings, model_metadata=None):
    if selection is None:
        return None
    row = db.execute(
        'SELECT value FROM settings WHERE key=?', ('experiment:' + selection['plan_id'],)
    ).fetchone()
    if not row:
        raise ValueError('比較方案不存在；未提交任務')
    record = json.loads(row[0])
    plan = record['plan']
    if (
        plan['plan_sha256'] != selection['plan_sha256']
        or plan_digest(plan) != selection['plan_sha256']
    ):
        raise ValueError('比較方案 hash 不符；未提交任務')
    if record['archived']:
        raise ValueError('比較方案已封存，請先還原；未提交新任務')
    variant = next((v for v in plan['variants'] if v['id'] == selection['variant_id']), None)
    if not variant or variant['settings'] != settings:
        raise ValueError('設定與比較組快照不符；請重新載入該組或解除比較關聯，未提交任務')
    if plan['schema_version'] == 2:
        experiment_models.verify(db, experiment_models.expected(plan, variant), model_metadata)
    return snapshot(plan, selection, variant)
