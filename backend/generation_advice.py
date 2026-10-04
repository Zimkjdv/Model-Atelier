"""Read-only advice. Never authorizes or blocks job submission."""
from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field
from backend import environment, validation_records, lora_validation
from backend.lora_settings import LoraSetting


class AdviceInput(BaseModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False)
    engine_url: str = Field(min_length=1, max_length=2048)
    checkpoint: str = Field(min_length=1, max_length=2048)
    width: int = Field(ge=64, le=8192, multiple_of=8, strict=True)
    height: int = Field(ge=64, le=8192, multiple_of=8, strict=True)
    steps: int = Field(ge=1, le=150, strict=True)
    cfg: float = Field(ge=0, le=30)
    sampler_name: str = Field(min_length=1, max_length=100)
    scheduler: str = Field(min_length=1, max_length=100)
    denoise: float = Field(ge=0, le=1)
    loras: list[LoraSetting] = Field(default_factory=list, max_length=4)


def advise(value, model, diagnostics, lora=None, *, stale=False):
    evidence = validation_records.evaluate(model)
    settings = value.model_dump(exclude={'engine_url', 'checkpoint', 'loras'})
    active = [item for item in value.loras if item.enabled]
    if len(active) > 1:
        evidence = dict(status='unverified', records=[], matching_parameter_records=[])
    elif active:
        evidence = lora_validation.evaluate(model, lora or {}, active[0], settings | dict(batch_size=1), stale=stale)
    matches = [record for record in evidence['records']
               if all(record['settings'].get(key) == val for key, val in settings.items())
               and (not active or record['id'] in evidence['matching_parameter_records'])]
    warnings = []
    if len(active) > 1:
        warnings.append('多 LoRA 組合尚未實機驗證；順序與每個強度都會影響結果，不沿用單一 LoRA 或基礎模型紀錄。')
    elif active:
        warnings.append('目前啟用 LoRA；僅比對單一 LoRA 八節點組合紀錄，不沿用基礎模型的七節點紀錄。')
    if not evidence['records']:
        warnings.append('此模型沒有匹配的推論實測紀錄。')
    elif not matches:
        warnings.append('目前解析度或取樣設定不在已記錄的實測條件內。')
    else:
        warnings.append('參數符合歷史紀錄，但目前檔案、硬體、精度與卸載方式未重新驗證。')
    if diagnostics.get('status') != 'available':
        warnings.append('引擎離線或診斷不可用，目前裝置與可用顯存未知。')
    warnings.append('沒有可靠的本次 VRAM 需求估計。歷史設備顯存取樣不是最低需求；可用顯存會隨其他程序改變。')
    warnings.append('這些提示不限制提交、不修改參數；生成仍會檢查引擎、模型及流程，實際執行可能因記憶體不足失敗。')
    return dict(engine_url=value.engine_url, checkpoint=value.checkpoint, checked_at=environment.now(),
                settings=settings, advisory_only=True, estimated_vram_bytes=None,
                matching_parameter_records=[record['id'] for record in matches],
                validation_status=evidence['status'], diagnostics=diagnostics, warnings=warnings)


def install(app, host):
    @app.post('/api/generation-advice')
    async def generation_advice(value: AdviceInput):
        target = host.ModelTarget(engine_url=value.engine_url, name=value.checkpoint)
        _, before = host.current_catalog(target)
        choices = [item for item in value.loras if item.enabled]
        active = choices[0] if len(choices) == 1 else None
        pair = lora_validation.read_pair(host.DB, value.engine_url, value.checkpoint, active.name) if active else None
        report = await host.engine()
        _, after = host.current_catalog(target)
        if pair is not None and pair != lora_validation.read_pair(host.DB, value.engine_url, value.checkpoint, active.name):
            raise HTTPException(409, 'LoRA 登記或清單已變更，請重新查詢提示。')
        if before != after or report.get('url') != value.engine_url or report.get('diagnostics', {}).get('matches_selected_engine') is False:
            raise HTTPException(409, '查詢期間模型或引擎已變更，請重新查詢提示。')
        return advise(value, after, report.get('diagnostics') or environment.engine_diagnostics(status='invalid'),
                      pair[1] if pair else None, stale=pair[2] if pair else False)
