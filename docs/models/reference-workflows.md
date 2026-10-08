# 參考素材與流程

素材庫支援 PNG／JPEG／WebP 單張圖片，最多 20 MiB、1600 萬像素。上傳後校正 EXIF 方向、轉 RGBA、移除中繼資料並保存 PNG；紀錄原始內容 SHA256、格式、尺寸、前處理版本及 Pillow 版本。平台未保存原始檔，請自行保留。舊素材未記錄的版本保持未知，不以目前版本回填。

用途分為「未指定、視覺風格、角色外觀、構圖」，僅供管理與篩選。用途不等於影像條件控制，也不承諾重現畫風或角色。素材編輯帶修訂號防止跨視窗覆寫；既有不帶修訂號的 API 客戶端仍相容。

`GET /api/reference-workflows` 回傳各流程的圖片數量、架構、輸入需求與是否已實作。文生圖不套用圖片；Checkpoint 圖生圖已實作後端，需明確登記 SD 1.x／SDXL 架構與一張未封存的素材。局部編輯、ControlNet 結構參考及 adapter 風格／角色參考尚未整合。FLUX 使用獨立流程，尚未支援參考圖。

`GET /api/assets/{id}/usage` 提供引用素材的草稿、任務、作品及已保存比較方案 ID。素材封存與引用檢查在同一 SQLite 寫入交易執行：草稿引用需先移除並保存；任務／作品／已保存比較方案引用的素材不可封存，以保留來源與重建能力；封存方案仍保留素材引用。方案保存與素材封存共用 SQLite 寫入交易，見[保存方案說明](../experiment-storage.md)。仍可更新名稱與用途。平台沒有素材永久刪除 API。

## Checkpoint 圖生圖 API

`POST /api/generate` 使用原有取樣欄位，加上 `workflow_mode: "image2image"`、`image_asset_id`、僅包含該 ID 的 `reference_ids`，以及 `reference_resize: "fit" | "stretch"`。仍需持久 UUID `request_id`。草稿可保存這些欄位；舊草稿預設文生圖。

- `fit`：先將透明區域合成到白底，以 LANCZOS 等比縮放、置中並補白；`stretch`：白底合成後拉伸至指定寬高，可能改變比例。尺寸為 64～8192、8 的倍數，前處理輸出最多 1600 萬像素。
- 保存原素材 SHA256、名稱、用途、正規化紀錄；另凍結圖生圖前處理版本、Pillow 版本、尺寸、縮放、白底及處理後 PNG 雜湊。處理後 PNG 保存在 `data/job_inputs/{job_id}.png`。
- 以 `LoadImage` → `VAEEncode` 取代空 latent；其餘 checkpoint、最多四個有序 LoRA、提示詞、KSampler、解碼與輸出路徑保持明確連接。`denoise` 越低通常越保留輸入，越高改動越多；不等於 adapter 的獨立風格強度。
- 任務保留完整 JSON，先檢查模型、KSampler、LoRA 與 LoadImage／VAEEncode 介面，再上傳至原引擎 `input/model_atelier/{job_id}/reference.png`。不接受使用者傳入引擎檔名、不覆寫檔案；僅接受完全匹配的上傳回執。上傳回執確認位置，不是遠端內容雜湊驗證；實機驗收另透過 `/view` 核對內容。
- 生成僅提交一次，使用原有歷史、進度、精確取消與停止 API。上傳不確定則記錄失敗、不提交生成；`/prompt` 不確定則保留 unknown、只查詢。重送相同 ID 回傳原紀錄，不重新上傳；相同 ID 改動素材／設定回傳 409。
- 任務與作品都保留不可回填的來源快照，完整模板才能還原。已終止圖生圖任務可使用 `/api/jobs/{id}/creation-settings`，作品使用既有設定 API；還原不自動生成。`/api/jobs/{id}/reference-image` 可預覽保存的處理後輸入。

Pony 圖生圖的 RTX 3060 實機紀錄見 [驗收說明](../validation/checkpoint-image2image-rtx3060.md)。SD 1.x 與其他 checkpoint、參考圖加 LoRA、風格品質及 RTX 4080 仍未實機驗證。

## 在工作台操作

1. 在「參考素材」上傳圖片，可編輯名稱與用途。
2. 在「創作工作台」選擇 Checkpoint／SDXL，將「Checkpoint 工作流程」改為「圖生圖 · 單張輸入」。模型需登記 SD 1.x 或 SDXL。
3. 選擇一張輸入圖片、輸出尺寸與縮放方式，調整提示詞、改動幅度（Denoise）及取樣參數。選擇圖片會把草稿參考關聯替換為該單張素材；縮放示意不等於實際前處理結果。切換流程保留提示詞與取樣參數，不自動套用文生圖預設。
4. 「保存草稿」只寫入本機；「生成圖片」才上傳處理後輸入並提交任務。缺圖片、已封存、未知模型架構、引擎離線或能力快照過期時會顯示阻擋原因。
5. 任務完成後前往作品庫匯入，可在預覽中查看來源素材、前處理版本、SHA256 及保存的處理後輸入。已終止圖生圖任務或作品可載入為新草稿；未保存內容需先選擇保留或捨棄，載入不會自動生成。

文生圖的素材選取仍只供草稿記錄，生成前需取消選取。畫風／角色 adapter、ControlNet 與局部編輯並未因用途標籤或圖生圖介面而啟用。
