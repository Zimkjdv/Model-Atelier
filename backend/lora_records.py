"""Registered LoRA provenance at submission; never backfill past identities."""
from backend import catalog, loras


def capture(record, choice):
    return catalog.capture(record, choice['name']) | dict(enabled=True,
        strength_model=choice['strength_model'], strength_clip=choice['strength_clip'])


def restoration(db_path, url, settings, snapshots):
    """Read cached availability without loading weights or changing old records."""
    collection = loras.read(db_path, url)
    warnings, available = [], []
    for choice in settings.get('loras', []):
        name = choice['name']
        current = next((item for item in collection['loras'] if item['name'] == name), None)
        status = ('unknown' if not collection.get('synced_at') or collection.get('sync_error')
                  else 'available' if current and current.get('listed') is True else 'missing')
        available.append(dict(name=name, status=status))
        warnings.append(f'LoRA {name}：' + {
            'unknown': '原引擎 LoRA 清單尚未同步或同步失敗；可用性待確認。',
            'missing': '不在最近同步清單，請先安裝或重新同步；原設定仍保留。',
            'available': '僅在最近同步清單中；生成前會重新查詢，不代表權重可載入。',
        }[status])
        original = next((item for item in (snapshots or []) if item.get('name') == name), None)
        if not original or not original.get('version') or original['version'] == '未知':
            warnings.append(f'LoRA {name} 的原登記版本未知，無法確認與目前版本一致；不以目前模型庫回填。')
        if original and current:
            fields = ('version', 'architecture', 'sha256', 'source_url', 'size_bytes', 'license_name', 'license_url')
            def identity(item, key):
                value = item.get(key, catalog.METADATA_DEFAULTS[key])
                return value or '未知' if key == 'version' else value
            if any(identity(original, key) != identity(current, key) for key in fields):
                warnings.append(f'LoRA {name} 目前登記版本或識別資料與原快照不同；已保留原快照供比較。再次生成使用目前安裝的權重。')
    if settings.get('loras'):
        warnings.append('已完整還原單一 LoRA 的名稱與兩種強度；未載入權重或提交任務，原快照是登記資料而非檔案驗證。')
    return dict(warnings=warnings, loras=available, lora_synced_at=collection.get('synced_at'))
