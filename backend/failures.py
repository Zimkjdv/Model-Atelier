"""Conservative failure summaries; raw engine diagnostics stay in the ledger."""
import re
from itertools import islice

KNOWN_NODES = {'CheckpointLoaderSimple', 'CLIPTextEncode', 'EmptyLatentImage', 'KSampler', 'VAEDecode', 'SaveImage'}
OOM_TYPES = {'torch.OutOfMemoryError', 'torch.cuda.OutOfMemoryError', 'torch._C.OutOfMemoryError',
             'cuda.OutOfMemoryError', 'CUDAOutOfMemoryError'}
CUDA_OOM = re.compile(r'\bcuda(?:\s+error\s*:)?\s+out\s+of\s+memory\b', re.IGNORECASE)
IDENTIFIER = re.compile(r'[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*')

TEXT = {
    'missing_nodes': ('缺少必要節點', '原 ComfyUI 引擎未登記此流程需要的節點，任務尚未提交。',
                      ['查看任務錯誤中的節點名稱並確認引擎安裝完整。', '修復或重啟原引擎後，載入設定再建立新任務。']),
    'engine_offline': ('ComfyUI 無法連線', '原 ComfyUI 引擎離線或連線逾時，任務尚未提交。',
                       ['確認原引擎已啟動且位址正確。', '連線恢復後先查詢原任務；確認失敗原因並調整設定後才建立新任務。']),
    'no_checkpoints': ('尚未安裝 checkpoint', 'ComfyUI 目前沒有可用的 checkpoint，任務尚未提交。',
                       ['在原 ComfyUI 引擎安裝 checkpoint。', '同步模型庫並重新選擇模型，再確認設定後建立新任務。']),
    'checkpoint_missing': ('所選 checkpoint 不存在', '所選 checkpoint 已不在原 ComfyUI 引擎的即時模型清單中，任務尚未提交。',
                          ['確認模型檔案是否已移動、改名或刪除。', '同步模型庫並選擇可用模型，再確認設定後建立新任務。']),
    'unsupported_architecture': ('模型需要專用工作流程', '登記的模型架構尚不適用目前標準 checkpoint 文生圖流程，任務尚未提交。',
                                 ['確認模型庫登記的架構是否正確。', '選擇適用的 SD 1.x／SDXL checkpoint；其他架構需要專用流程。']),
    'preflight_invalid': ('生成前驗證未通過', '模型清單、引擎能力或工作流程參數未通過生成前驗證，任務尚未提交。',
                          ['重新同步模型庫與即時取樣能力。', '載入原設定，檢查節點、參數與模型是否符合引擎能力，再建立新任務。']),
    'engine_changed': ('引擎設定已變更', '驗證期間引擎設定已變更，任務尚未提交至任一引擎。',
                       ['確認原引擎與目前引擎設定。', '重新載入模型庫與取樣能力，確認設定後再建立新任務。']),
    'workflow_rejected': ('ComfyUI 拒絕工作流程', 'ComfyUI 已明確拒絕工作流程；此結果未確認為顯存不足。',
                          ['載入原設定並檢查節點、checkpoint 與取樣參數。', '需要完整診斷時查看原任務 JSON，再確認設定後建立新任務。']),
    'cuda_oom': ('CUDA 顯存不足', '原引擎的已確認執行錯誤明確指出 CUDA 顯存不足。',
                 ['載入原設定並降低圖片寬度或高度，再建立新任務。', '關閉其他占用顯存的程式；必要時使用符合該模型的省顯存流程。']),
    'model_load_failed': ('模型載入節點失敗', '原工作流程的 checkpoint 載入節點執行失敗；目前沒有足夠資訊判定為顯存不足。',
                          ['確認原 checkpoint 檔案存在、完整且架構與流程相符。', '查看原任務 JSON 與引擎日誌，再選擇可用模型或修復檔案後建立新任務。']),
    'execution_failed': ('ComfyUI 執行失敗', '原引擎歷史已確認任務失敗，尚無足夠資訊判定為顯存不足或模型載入失敗。',
                         ['載入原設定並檢查工作流程與參數。', '需要完整診斷時查看原任務 JSON 與引擎日誌；確認原因後才建立新任務。']),
}


def info(code, context=None):
    code = code if code in TEXT else 'execution_failed'
    title, message, suggestions = TEXT[code]
    return dict(code=code, title=title[:80], message=message[:400], suggestions=[value[:240] for value in suggestions[:3]],
                node_id=context.get('node_id') if context else None,
                node_type=context.get('node_type') if context else None,
                exception_type=context.get('exception_type') if context else None)


def trusted_node(job, node_id, node_type, exception_type=None):
    if not isinstance(node_id, str) or not re.fullmatch(r'[A-Za-z0-9_.-]{1,128}', node_id):
        return None
    node = job.get('workflow', {}).get(node_id)
    if not isinstance(node, dict):
        return None
    kind = node.get('class_type')
    if not isinstance(kind, str) or kind not in KNOWN_NODES or kind != node_type:
        return None
    exception = (exception_type if isinstance(exception_type, str) and len(exception_type) <= 120
                 and IDENTIFIER.fullmatch(exception_type) else None)
    return dict(node_id=node_id, node_type=node['class_type'], exception_type=exception)


def history_matches(job, entry):
    """Reject explicit history ownership contradictions without guessing IDs."""
    if 'prompt' not in entry:
        return True
    prompt = entry['prompt']
    if (not isinstance(prompt, (list, tuple)) or len(prompt) < 4 or prompt[1] != job['prompt_id']
            or prompt[2] != job['workflow'] or not isinstance(prompt[3], dict)):
        return False
    owner = prompt[3].get('model_atelier_job_id')
    return owner is None or owner == job['id']


def from_history(job, entry):
    state = entry.get('status') if isinstance(entry, dict) else None
    if not isinstance(state, dict) or state.get('status_str') != 'error':
        return None
    if not history_matches(job, entry):
        return info('execution_failed')
    messages = state.get('messages')
    if not isinstance(messages, list):
        return info('execution_failed')
    for event in reversed(messages[-64:]):
        if not isinstance(event, (list, tuple)) or len(event) != 2 or event[0] != 'execution_error':
            continue
        data = event[1]
        if not isinstance(data, dict) or data.get('prompt_id') != job['prompt_id']:
            continue
        context = trusted_node(job, data.get('node_id'), data.get('node_type'), data.get('exception_type'))
        if context is None:
            continue
        message = data.get('exception_message')
        explicit_cuda = isinstance(message, str) and len(message) <= 8192 and CUDA_OOM.search(message) is not None
        if context['exception_type'] in OOM_TYPES or explicit_cuda:
            return info('cuda_oom', context)
        if context['node_type'] == 'CheckpointLoaderSimple':
            return info('model_load_failed', context)
        return info('execution_failed', context)
    return info('execution_failed')


def from_rejection(job, payload):
    node_errors = payload.get('node_errors') if isinstance(payload, dict) else None
    if isinstance(node_errors, dict):
        for node_id, error in islice(node_errors.items(), 64):
            if not isinstance(error, dict) or not isinstance(error.get('errors'), list) or not error['errors']:
                continue
            context = trusted_node(job, node_id, error.get('class_type'))
            if context is not None:
                return info('workflow_rejected', context)
    return info('workflow_rejected')
