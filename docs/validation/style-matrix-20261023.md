# L01 更多畫風與多 LoRA 品質比較（2026-10-23）

本輪新增一個固定來源像素畫 LoRA、可追溯的原生鍵名相容副本，以及一指令一組的 `scripts.verify_style_matrix`。RTX 3060 完成 14 組原生比較，另保留 4 組原始格式未套用成功的嘗試；兩批的資料、UUID 與載入判斷分開，沒有把成功出圖當成權重成功載入或畫風品質通過。

完整設定、版本、原圖／workflow／報告 hash、轉換 provenance、引擎未載入警告及逐圖觀察見[證據 JSON](style-matrix-20261023.json)。使用者的目標作者／同角色圖片仍未提供；指定目標品質仍待資料，沿用[圖片提醒](../anime-style-development.md#image-input-reminders)。

## 新來源與格式失敗

新增原始來源 `Hadimeeee/pixel-art-lora-sdxl` 的固定修訂與 safetensors，官方大小 185963768 bytes、完整 SHA256 `30ef3c19f6bf6c621a4a90722722df78af915c8f4e9b35f91a66d2ea7a079444`。作者原用途是玩偶照片轉像素角色，另含去背、Canny／ControlNet 及量化；本輪僅用原生 ComfyUI LoRA 文生圖，不執行上游 Python 或借用其完整流程成績。

最初 baseline、model 0.5、model 1、CLIP 0.5 共四次任務正常出圖，後三次卻每次回報 1,120 個權重鍵未載入，合計 3,360 條。結構報告的 `passed` 只說明提交／保存核對完成，該批載入驗收判定為不通過。三張啟用原檔圖片的 RGB hash 相同；與無 LoRA 基準 hash 不同亦不能蓋過引擎的全鍵未載入證據。原始報告、原圖與日誌保留於 `runtime/l01-live-20261023/`，沒有追加至載入 registry。

`scripts.convert_pixel_lora` 對固定來源作**鍵名轉換**，保留 tensor dtype／shape／rank 配對、offset 及完整資料區 bytes。原檔保留，另建 `pixel_art_lora_sdxl_comfy_v1.safetensors`，185969440 bytes、SHA256 `eef9b71806b7715760af4f8ab5a038b29daf41272ab30782f38381aee096f1be`。獨立 manifest／版本及 provenance 保存原來源、資料區及映射 hash；暫存檔 fsync／驗檔後排他發布，已有不符檔案不覆寫。這不是作者另發的模型，也不是任意模型轉換器。來源、安裝及重跑見[模型說明](../models/pixel-art-lora-sdxl.md)。

相容副本 14 組使用全新 UUID 與新資料目錄，原生引擎日誌沒有 `lora key not loaded` 或 `NOT LOADED` 警告。每組完整驗證實際 checkpoint／LoRA 大小與 SHA256、登記及有序設定，保存結果與完整設定還原；沒有自動重送原始四組或改寫其狀態。

原生組提交至成功歷史的觀察時間為 14.125–37.485 秒，引擎歷史為 13.533–35.489 秒。冷／暖載入、LoRA 準備、快取與取樣條件不同，不作順序速度排名。NVIDIA 整卡取樣最高另存每組，包含其他程序；任務專用峰值仍未知，不推算最低 VRAM 或硬體速度承諾。

## 有限矩陣

固定 Animagine XL 4.0 Opt、IKEA、LCM 與像素相容副本。RTX 3060 12 GiB、ComfyUI 0.34.0 git `15eb748b3ec5f8a0a2d470b7fb280e2d7579f916`、Python 3.12.10、PyTorch 2.14.0+cu130、驅動 616.56；模型／CLIP FP16、VAE bfloat16、動態 VRAM 與 CPU offload。各原任務保留自己的環境快照，未知節點版本維持未知。

| cases | 條件 | seed／題材 |
| --- | --- | --- |
| 01–04 | baseline、pixel model 0.5／CLIP 1、pixel 1／1、pixel 1／0.5 | 第一 seed／動漫半身 |
| 05–06 | IKEA → pixel、pixel → IKEA；兩者各 1／1 | 第一 seed／動漫半身 |
| 07–10 | LCM、LCM → pixel、pixel → LCM、LCM → IKEA → pixel | 第一 seed／動漫半身 |
| 11–12 | pixel 1／1、LCM → pixel | 第二 seed／動漫半身 |
| 13–14 | baseline、pixel 1／1 | 第一 seed／坐姿玩偶熊 |

第一／第二 seed 為字串 `9007199254740993`／`18446744073709551615`。IKEA、pixel 均 1／1（特別列出的半強度除外），LCM model／CLIP 為 1／0。有序列表、兩種強度與精確 seed 全部保存，不正規化成另一順序。

共用 1024×1024、denoise 1、batch 1、固定反向提示。非 LCM 使用 28 steps、CFG 5、euler_ancestral／normal；LCM 使用 8 steps、CFG 1、lcm／sgm_uniform。同順序比較及半強度各自保持其餘條件，不把 LCM 組與非 LCM 的差異單獨歸因於順序或一個權重。動漫提示明確加上 pixel art，玩偶提示另立；不是照片轉換或嚴格 16×16／指定色數流程。

## 原圖觀察與限制

開發助手 Codex 檢視實際原圖及聯絡表，四面向逐圖筆記在 JSON，沒有產生數字品質分數或使用者簽核。

- 無 LoRA 的 pixel art 提示本身已形成像素外觀；model 0.5／1 改變臉型、髮型、書本位置及色塊，不能把所有像素感歸因於 LoRA。
- 該檔沒有 CLIP 張量。本次 pixel model 1／CLIP 1 與 model 1／CLIP 0.5 的 decoded RGB 相同（`c907a4bee4e130afa5547c2cded67f886724b46f7481b2222118cd6d9568b4ef`），設定仍如實保存；這不是所有檔案／參數的等效保證。
- IKEA／pixel 的正反順序視覺接近，RGB hash 不同；仍呈彩色像素人物，未見明確黑白說明書風格。此提示不構成家具說明流程的完整品質驗收，也不能推成任意順序等效。
- 本批 LCM 及 LCM／pixel 正反組偏柔化、模糊，未得到清楚像素塊。三項組合看起來較清楚，但仍偏柔和上色；沒有由單例推薦三項更佳。既有 4／8 步低對比結果與品質不足觀察完整保留。
- 多張半身被裁成近距離胸像、成人特徵不明確；換 seed、權重及順序會變動臉型／造型。服裝相同不等於身份一致。
- 玩偶兩組皆有像素外觀；加入 LoRA 後變動棕色陰影、耳臉比例及紅圍巾，沒有保證同玩偶身份、嚴格像素格或上游照片轉換成績。

## 歷史查詢、離線及資料

`models/stack-validation-records.json` 追加 cases 05、06、08、09、10、12 六筆歷史載入條件；原三筆逐項保留。只匹配登記的有序 hash／架構、兩強度及取樣參數，**不匹配 prompt／seed**；後兩者在完整原設定與條件說明內，不把參數匹配當成本次品質證明。新順序、強度、架構、未知 hash 或過期登記仍保持未驗證。單一像素 LoRA 的本輪完整證據在 JSON，未冒充多 LoRA registry。

原生批次保存於 `runtime/l01-native-20261023/`。停掉本次引擎及平台後，以同資料目錄重啟平台；14 份報告只 GET 核對原 UUID、原圖、完整 workflow、精確 seed、模型／有序 LoRA 及原設定，沒有讀權重、同步、匯入或生成，前後維持 14 任務／14 作品／0 草稿。兩批測試的正式 DATA 八個檔案 hash 一致，測試服務已停止。

轉換保留 `terms_verified=false` 的原來源狀態，未將未知授權鏈改成已驗證。更多作者／使用者角色目標、其他強度／題材、圖生圖、RTX 4080 及訓練仍待各自驗收；本輪沒有新的通用品質預設。

## 工程驗證

固定來源安裝器先以 `2107d14` 單獨格式化並納管，Python AST 一致、27 項既有回歸通過（1 跳過）。新增 6 項轉換邊界／原子發布測試與 4 項組合／精確 seed／完整還原／防竄改測試；假引擎涵蓋十 profiles × 兩 seed × 兩題材的一次提交及 GET-only 恢復。

615 項後端（1 既有跳過）、格式／靜態、Vue 型別／建置、四組契約及完整 93 項 Chromium 已通過。1440px／390px 新操作案例驗證歷史順序、兩 seed 條件、品質限制、強度改變後不匹配及零生成；另補拍展開品質觀察的元素截圖並重跑兩案通過，檢視兩尺寸可讀且無水平溢位。
