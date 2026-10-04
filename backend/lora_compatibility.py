"""Read-only architecture assessment; never evidence of successful LoRA loading."""
import sqlite3
from contextlib import closing
from datetime import datetime, timezone

from fastapi import HTTPException, Query

from backend import catalog, loras, model_profiles

KNOWN = {'sd1', 'sdxl', 'sd3', 'flux'}
NOTE = '此為登記資料比較，未讀取權重或執行 LoRA；同架構不保證特定基礎模型、節點或 GPU 可載入。'


def compare(checkpoint, lora, *, stale=False):
    base = model_profiles.architecture(checkpoint.get('architecture'))
    kind = model_profiles.architecture(lora.get('architecture'))
    if base in KNOWN and kind in KNOWN and base != kind:
        status, label = 'incompatible', '不相容：登記架構不同'
        reason = f'Checkpoint 登記為 {model_profiles.LABELS[base]}，LoRA 基礎架構登記為 {model_profiles.LABELS[kind]}。'
    elif stale or checkpoint.get('listed') is not True or lora.get('listed') is not True:
        status, label = 'unverified', '未驗證：清單需確認'
        reason = '最近同步失敗，或其中一個模型未在最近成功清單中列出；先重新同步確認登記狀態。'
    elif base not in KNOWN or kind not in KNOWN:
        status, label = 'unverified', '未驗證：架構資料不足'
        reason = '至少一方的登記架構未知或為「其他」，不能確認是否同一架構。'
    else:
        status, label = 'compatible', '架構相容，未實測'
        reason = f'兩者均登記為 {model_profiles.LABELS[base]}；尚未驗證這個 checkpoint／LoRA 組合。'
    return dict(status=status, label=label, message=reason + NOTE, verified=False)


def record(item):
    return dict(name=item['name'], architecture=model_profiles.architecture(item.get('architecture')),
                metadata_updated_at=item.get('metadata_updated_at'), listed=item.get('listed') is True)


def assess(db_path, url, checkpoint_name):
    # Read both collections in one SQLite snapshot, including concurrent metadata edits.
    with closing(sqlite3.connect(db_path)) as db:
        db.execute('BEGIN')
        checkpoints = catalog._read(db, url)
        collection = loras._read(db, url)
    checkpoint = next((item for item in checkpoints['models'] if item['name'] == checkpoint_name), None)
    if checkpoint is None:
        raise KeyError('Checkpoint 未登記，請先同步模型清單。')
    stale = bool(checkpoints.get('sync_error') or collection.get('sync_error'))
    return dict(engine_url=url, checkpoint=record(checkpoint),
                loras=[record(item) | compare(checkpoint, item, stale=stale) for item in collection['loras']],
                checkpoint_synced_at=checkpoints.get('synced_at'), lora_synced_at=collection.get('synced_at'),
                checkpoint_sync_error=checkpoints.get('sync_error'), lora_sync_error=collection.get('sync_error'),
                source='registered_architecture', workflow_supported=False,
                assessed_at=datetime.now(timezone.utc).isoformat())


def install(app, host):
    @app.get('/api/loras/compatibility')
    def get_assessment(engine_url: str = Query(min_length=1, max_length=2048),
                       checkpoint: str = Query(min_length=1, max_length=2048)):
        try:
            url = host.Settings.validate_url(engine_url)
        except ValueError as exc:
            raise HTTPException(422, str(exc))
        def require_selected():
            if host.engine_url() != url:
                raise HTTPException(409, '執行引擎已變更，請重新載入模型庫。')
        require_selected()
        try:
            result = assess(host.DB, url, checkpoint)
        except KeyError:
            raise HTTPException(404, 'Checkpoint 未登記，請先同步模型清單。')
        require_selected()
        return result
