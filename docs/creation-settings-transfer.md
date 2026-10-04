# 創作設定匯出與匯入（2026-10-05）

Checkpoint／SDXL 與 FLUX 工作台都有「創作設定匯出／匯入」區塊。可以匯出目前完整表單、選取 JSON 檔或貼上 JSON，先按「驗證並預覽設定」，查看目前／文件全部欄位差異、流程與來源提示，再按「套用為新草稿」。取消或格式錯誤不改原表單；驗證後修改任何欄位或文件會使舊預覽失效。套用會明確取代目前欄位，若有未保存變更會先顯示提示，原已保存草稿及待確認任務仍保留。

套用後是未保存的新草稿，沒有原草稿 ID／修訂號；需再按保存或生成。Seed 永遠是十進位字串，保留最大值 `18446744073709551615`。有序 LoRA、停用項目、兩種強度、圖生圖來源 ID／fit 或 stretch／denoise，以及 FLUX 四元件／精度／文字編碼器裝置均保留。跨架構文件需切到對應工作台，不能把 FLUX 設定塞入 checkpoint 欄位。此操作不改目前引擎位址設定或模型庫資料。

作品預覽另有「匯出創作設定（含來源快照）」：保存原模型版本與 metadata、LoRA／元件／參考素材／運行環境快照，以及 `workflow_json` 字串。完整 API 工作流程放在字串內，避免瀏覽器轉換其中的 64 位整數。不能完整還原到已支援表單的流程拒絕匯出設定，仍可下載原完整 workflow。終止任務也可從下列 API 匯出；未終止任務回傳 409，不觸發重送。

文件來源快照可能被編輯，匯入時一律標示未核實；不作為新任務版本或相容性證明，不寫入模型庫、作品或草稿 metadata。新任務依提交時實際登記與原引擎重新取快照。只匯出目前表單時，來源快照為 null。

設定檔沒有權重或參考圖片。另一台主機沒有相同素材 ID／檔案時，保留原 ID 並提示手動重新選取，不能把文字 ID 當成圖片已搬移。原引擎不同、checkpoint 最近清單未確認時會提示；這是本機保存快照檢查，不保證引擎在線。提交前仍執行完整即時驗證。

| API | 用途 | 副作用 |
| --- | --- | --- |
| `POST /api/creation-settings/export` | body 為 `workflow_id` 與完整 `settings`，下載目前設定 | 不保存、不連引擎 |
| `GET /api/artworks/{id}/settings-export` | 作品完整設定及原來源快照 | 本機只讀 |
| `GET /api/jobs/{id}/settings-export` | 終止任務完整設定及原來源快照 | 本機只讀；未終止 409 |
| `POST /api/creation-settings/import` | raw JSON 文件；回傳正規化 bundle 與 warnings，供預覽 | 不保存、不連引擎、不生成 |

格式 `kind: model-atelier-creation`、`schema_version: 1`，支援 `checkpoint-text2image-v1`、`checkpoint-image2image-v1` 與 `flux1-schnell-text2image-v1`。完整表單欄位必須齊全；未知／任務 ID／修訂號／任意 workflow 欄位、數字 seed、非法參數或帳密 URL 拒絕。輸入按 stream 限制 256 KiB，拒絕重複 JSON 欄位、NaN／Infinity、無效 UTF-8；UTF-8 BOM 可讀。原圖輸出與模型庫登記沒有由此 API 開放修改。

驗收：370 項後端測試（369 通過、1 項既有 Windows 權限跳過）、Vue 型別／建置通過。桌面瀏覽器驗證檔案選取、貼上、變更使預覽失效、取消、無效版本、跨流程拒絕、兩個有序 LoRA、精確 seed、套用為新草稿、另存與跨工作台保留；修正 Vue 代理物件不能 structuredClone 的問題，使用設定 JSON 複製並保留字串 seed。圖生圖轉移由 API 測試驗證，未做新 GPU 推論。

IAB 的程式觸發 Blob 下載事件未由驗收工具回報，因此不宣稱瀏覽器下載檔案已落盤；匯出 API bytes、下載連結的 filename 及可展開完整 JSON 內容已核對。其他瀏覽器下載／390px 仍待驗收。畫面證據 `runtime/settings-transfer-ui-20261005.png`，隔離設定檔、兩份 checkpoint 草稿及一份 FLUX 草稿保留，原正式 5 任務／3 作品／0 草稿不變。本項操作沒有新增 GPU 任務。
