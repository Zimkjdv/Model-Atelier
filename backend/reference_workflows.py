"""Explicit reference capabilities; descriptive asset purposes are not conditioning."""
from copy import deepcopy

IMG2IMG_ID = 'checkpoint-image2image-v1'
DESCRIPTIONS = [
    dict(id='checkpoint-text2image-v1', name='Checkpoint 文生圖', implemented=True,
         architectures=['sd1', 'sdxl'], image_count=0, input_requirement='不套用參考圖片；草稿素材關聯僅為記錄。',
         control='提示詞與取樣參數', lora=True),
    dict(id=IMG2IMG_ID, name='Checkpoint 圖生圖', implemented=True,
         architectures=['sd1', 'sdxl'], image_count=1, input_requirement='一張未封存的本機 PNG 素材；縮放至輸出尺寸後編碼為 latent。',
         control='以 denoise 控制改動幅度；不是獨立畫風或角色鎖定。', lora=True),
    dict(id='checkpoint-inpaint-v1', name='局部編輯', implemented=True, architectures=['sd1','sdxl'], image_count=2,
         input_requirement='相同原始尺寸的原圖及遮罩；白色編輯、黑色保留，需原生節點。', control='二值遮罩與 grow_mask_by；結果合成回原輸入。', lora=True),
    dict(id='checkpoint-canny-controlnet-v1', name='Canny 結構參考', implemented=True, architectures=['sd1','sdxl'], image_count=1,
         input_requirement='一張素材、同架構且登記 canny 的 ControlNet；需原生 Canny 與 ControlNet 節點。', control='邊緣結構與強度／起訖；非姿勢或畫風鎖定。', lora=True),
    dict(id='checkpoint-canny-controlnet-edge-v2', name='Canny 結構與邊緣輸出', implemented=True, architectures=['sd1','sdxl'], image_count=1,
         input_requirement='與 v1 相同的單張來源與控制模型；另存同次執行的原生邊緣 PNG。', control='單次條件圖追溯，不保證畫風或角色鎖定。', lora=True),
    dict(id='style-reference', name='風格／角色參考', implemented=False, architectures=[], image_count=1,
         input_requirement='需匹配架構的影像編碼器與 adapter；用途標籤不會自動啟用此能力。', control='風格或外觀', lora=False),
]


def descriptions():
    return deepcopy(DESCRIPTIONS)
