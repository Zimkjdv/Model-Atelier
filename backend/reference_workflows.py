"""Explicit reference capabilities; descriptive asset purposes are not conditioning."""
from copy import deepcopy

IMG2IMG_ID = 'checkpoint-image2image-v1'
DESCRIPTIONS = [
    dict(id='checkpoint-text2image-v1', name='Checkpoint 文生圖', implemented=True,
         architectures=['sd1', 'sdxl'], image_count=0, input_requirement='不套用參考圖片；草稿素材關聯僅為記錄。',
         control='提示詞與取樣參數', lora=True),
    dict(id=IMG2IMG_ID, name='Checkpoint 圖生圖', implemented=False,
         architectures=['sd1', 'sdxl'], image_count=1, input_requirement='一張未封存的本機 PNG 素材；縮放至輸出尺寸後編碼為 latent。',
         control='以 denoise 控制改動幅度；不是獨立畫風或角色鎖定。', lora=True),
    dict(id='inpainting', name='局部編輯', implemented=False, architectures=[], image_count=1,
         input_requirement='需原圖、遮罩與相容流程，尚未整合。', control='遮罩區域', lora=False),
    dict(id='structure-reference', name='結構參考', implemented=False, architectures=[], image_count=1,
         input_requirement='需匹配架構的 ControlNet、前處理器與權重，尚未整合。', control='姿勢或結構', lora=False),
    dict(id='style-reference', name='風格／角色參考', implemented=False, architectures=[], image_count=1,
         input_requirement='需匹配架構的影像編碼器與 adapter；用途標籤不會自動啟用此能力。', control='風格或外觀', lora=False),
]


def descriptions():
    return deepcopy(DESCRIPTIONS)
