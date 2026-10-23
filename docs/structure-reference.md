# SDXL 姿勢與深度參考（R01）

`checkpoint-structure-controlnet-v3` 使用一張素材，先在原 ComfyUI 做 DWPose 或 Depth Anything V2 Small，再縮放實際條件圖至輸出尺寸，套用同類型的 SDXL ControlNet。由空 latent 生成；不是圖生圖、角色 adapter 或訓練。Canny v1／v2 維持原端點與格式。

## 安裝與來源

獨立 ComfyUI 的 `custom_nodes/comfyui_controlnet_aux` 固定為 `a587a4c1594524c1d2de5cd1a86cd868ff448e1c`，依其 requirements 安裝在引擎 venv，重新啟動引擎。節點原碼採外部依賴，沒有複製到 FastAPI。[上游原碼／Apache-2.0](https://github.com/Fannovel16/comfyui_controlnet_aux/tree/a587a4c1594524c1d2de5cd1a86cd868ff448e1c)。

控制模型：[OpenPose SDXL](../models/controlnet-openpose-sdxl-1.0.json)、[Depth SDXL FP16](../models/controlnet-depth-sdxl-1.0-fp16.json)；估計器：[固定來源、大小與 SHA256](../models/structure-preprocessors.json)。各權重與基底條款分開登記，不能由節點授權推論權重無限制。

```powershell
.\.venv\Scripts\python.exe -m scripts.install_model controlnet-openpose-sdxl-1.0
.\.venv\Scripts\python.exe -m scripts.install_model controlnet-depth-sdxl-1.0-fp16
.\.venv\Scripts\python.exe -m scripts.install_structure_preprocessors --check
.\.venv\Scripts\python.exe -m scripts.install_structure_preprocessors
```

估計器安裝器只處理三個固定檔案；已有檔案必須符合 hash，不覆寫。中斷留下 partial 時，先確認檔案與空間再人工處理，不會自動重置。上游缺檔會自行下載，因此推論前應完成準備；平台不提供任意節點自動安裝。執行時遠端節點 Git 修訂無法可靠查得，快照區分「所需修訂」與「實際版本未知」。

## 操作與契約

1. 模型庫同步並登記 ControlNet 的 `sdxl`、`pose` 或 `depth`，版本／來源／hash／大小依 manifest；checkpoint 同樣須登記 SDXL。
2. 結構工作台選 Pose 或 Depth、單張原素材與匹配控制模型，設定尺寸、強度及起訖、提示與字串 seed。切換類型清空模型選擇，避免誤用 Canny。此處顯示原圖；Canny CPU 預覽僅在 Canny 模式提供。
3. 明確生成。`POST /api/structure/generate` 嚴格拒絕 Canny 閾值與其他多餘欄位；固定 resolution 512，pose 開啟 body／hand／face 與 xinsir stick scaling，depth 使用 Small。來源先 fit 補白或 stretch，前處理輸出再 bicubic 至生成尺寸。
4. 節點 7 是唯一作品；節點 16 保存節點 13 的同次實際條件圖。完成後展開「查看原任務的姿勢／深度條件圖」，明確從原引擎保存；GET 不抓引擎、不重新生成。
5. 任務與作品可載入完整原設定；保留控制類型、參數、模型快照、原素材／處理圖及精確 seed。一般草稿、設定交換及比較方案仍由專用格式邊界拒絕，不丟棄控制參數。

提交前檢查匹配架構／類型、即時模型清單、前處理選項及節點輸入輸出；交易保留原登記，於上傳及提交前重查。原 UUID 恢復先讀舊任務，不重新探查檔案或提交。未知結果仍只查原請求。

`GET/POST /api/jobs/{id}/structure-output`、`GET /api/jobs/{id}/structure-output/image?download=true`、`GET /api/artworks/{id}/structure-output` 提供條件圖。只接受成功歷史的唯一節點 16、固定 UUID 輸出路徑與同尺寸 RGB PNG；資料存於 `data/structure_outputs` 與 SQLite `structure_output:*`。重複匯入不覆寫，缺檔／hash 變更需備份還原。停機完整備份須包含整個 DATA。

## 驗收及限制

2026-10-23 在 RTX 3060／ComfyUI 0.34.0，以既有 R02 單張動漫參考副本、Animagine 4.0 Opt、768²、20 steps、CFG 5、euler_ancestral／normal、seed `9007199254740993`、strength 0.5、0–1，分別完成 pose／depth 唯一提交、生成、條件圖保存、唯一作品、完整還原。兩次重新建立平台後僅 GET 核對通過。沒有訓練或改動使用者原始圖片。

人工查看：pose 偵測一人，但骨架有明顯斷裂／缺少肢體，生成沒有忠實跟隨原姿勢；depth 保留抬手與傾斜上身的整體佈局，但衣著、髮型與背景有改變，左右有明顯直線分界。這是流程通過與品質限制，不是姿勢或身份一致性保證；多人、其他尺寸／模型及 RTX4080 尚未驗證。

本機完整報告：`runtime/r01-live-20261023/pose.json`、`depth.json`；原圖、條件圖、作品與 SQLite 在同目錄的 DATA，另行備份。[可解析摘要](validation/structure-reference-20261023.json)。新增後端測試驗證雙類型快照／精確還原、缺節點、類型錯配、端點隔離、條件圖唯一保存／損壞拒絕與快照竄改；四項桌面／390px 瀏覽器測試確認遺失回應、重新整理、原 UUID 與完整 body 恢復且引擎僅提交一次。

重跑 CLI 每次只接受一種類型；報告先記錄 UUID 再提交一次，既有報告拒絕新生成。`--verify` 僅 GET，不能補提交、匯入或下載缺失輸出。例：

```powershell
.\.venv\Scripts\python.exe -m scripts.verify_structure_generation --kind pose --source <已確認用途的PNG> --report runtime/new-pose.json
.\.venv\Scripts\python.exe -m scripts.verify_structure_generation --kind pose --report runtime/new-pose.json --verify
```
