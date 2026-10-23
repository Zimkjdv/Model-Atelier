# R07 · 局部編輯與 Canny 的草稿、交換及比較格式評估

2026-10-23 決策：**必須使用專用版本格式，目前維持一般草稿／設定交換／比較方案不支援**。R07 的格式評估、能力說明及拒絕邊界完成，不表示這三項功能已上線。原任務／作品仍可完整載入保存的設定及下載完整 workflow；來源不完整時不部分還原。

一般 checkpoint schema 只有單張圖生圖或文生圖欄位，FLUX 另有元件格式。實際重現發現一般草稿端點曾回傳 201，卻忽略 `mask_asset_id`、`grow_mask_by`、`feather_radius`。修正後，建立及更新均回傳 422，原草稿與 revision 不變，其他未知欄位也拒絕。歷史一般草稿的讀取與預設保持相容，不回寫歷史資料。

相容既有客戶端回傳完整草稿或複製生成 body：`id`、`created_at`、`updated_at`、`model_version`、`request_id` 是已知的舊封套欄位，仍排除於草稿設定之外；不能選擇草稿 ID、修改伺服器時間／模型版本或恢復生成 UUID。revision 仍供樂觀鎖核對。此有限清單不含任何遮罩／控制／pending 欄位，其他未知欄位均拒絕。

## 目前能力與版本

`GET /api/reference-workflows/support?family=inpaint|control` 回傳 `schema_version: 1`、`scope: platform_formats` 及各版本的能力。它不查資料庫／引擎，不代表節點、權重、GPU 或品質已通過；未知 family 回傳 422。兩工作台生成區可展開「草稿、設定交換與比較的支援範圍」。

| 流程 ID | 不可遺失的輸入與參數 | 一般草稿／交換／比較方案 | 原設定載入／完整 workflow |
| --- | --- | --- | --- |
| `checkpoint-inpaint-v1` | 原圖、另一張遮罩、有序 reference_ids、grow mask、縮放／尺寸及共同設定 | 未支援／拒絕 | 支援完整已保存來源，需本機素材可用 |
| `checkpoint-inpaint-feather-v2` | v1 全欄位，加整數 feather_radius；二值遮罩與衍生 blend mask 的政策、版本／hash 分開 | 未支援／拒絕 | 支援；不以 v1 或目前 Pillow 重算原 blend |
| `checkpoint-canny-controlnet-v1` | 結構圖、ControlNet 名稱／版本／架構／類型、strength、start／end、Canny low／high、縮放及共同設定 | 未支援／拒絕 | 支援；v1 沒有同次邊緣輸出，不能補造 |
| `checkpoint-canny-controlnet-edge-v2` | v1 全欄位，加同次實際邊緣輸出的版本與來源 | 未支援／拒絕 | 支援完整原流程，包含邊緣 SaveImage 分支 |

共同設定包含原引擎、checkpoint、標題／正負提示詞、十進位字串 seed、width／height、steps／CFG／sampler／scheduler／denoise、有序 LoRA（含停用項及兩種強度）。Canny 固定空 latent、denoise 1；局部編輯固定雙輸入及原遮罩語意。架構或檔名不能替代 hash／來源核對。

新生成沿用既有 v2；載入 v1 保存設定時，畫面明示新提交建立 v2 任務。原 UUID、workflow／版本、素材及待確認請求不因載入而改寫。pending 的 v1／v2 marker 與原端點屬原恢復契約，不是設定檔；未知 marker 不能改成最新版本。

## 專用格式方案（設計草案，尚不可匯入）

| 層次 | 必須保存及驗證的內容 |
| --- | --- |
| 文件識別 | 使用獨立 kind，例如 `model-atelier-specialized-creation`，不借用 `model-atelier-creation`／`model-atelier-comparison-plan`；獨立整數 schema_version 及明確 workflow_id，四個流程版本逐一白名單 |
| 完整設定 | 按指定版本嚴格保存全部欄位；未知欄位／型別／重複 key／非有限數字／未知版本拒絕。v1 不默默補成 v2；升級另作差異預覽及明確選擇 |
| 雙輸入綁定 | 保存角色、原素材 ID、SHA256、bytes 大小、尺寸及有序 reference_ids；原圖／遮罩不同、幾何相符、角色與 settings 一致。未選好的草稿可保存明確 null，但不能宣稱可提交或完整重現 |
| 前處理／衍生物 | 保存縮放幾何、遮罩閾值／透明背景／nearest／grow mask；羽化另存半徑及單位、算法／Pillow 版本、二值與 blend hash／大小；Canny 保存原引擎、前處理 ID／版本／閾值與實際邊緣來源，缺失保持未知 |
| 元件來源 | checkpoint、ControlNet、有序 LoRA 的原版本／hash／架構／類型與快照；匯入聲明未核實，不寫成目前模型庫已驗權重，新提交仍重新驗證原端點與來源 |
| 原工作流程 | 保存原 API graph 的 JSON 文字，避免瀏覽器轉換 64 位 seed；下載保留全部節點及輸出分支。引擎檔名不等於素材圖片隨文件搬移 |
| 草稿保存 | 獨立 store key／修訂與樂觀鎖，完整驗證後交易保存；不覆寫一般草稿，衝突保留未保存內容。區分已保存遮罩、未保存筆畫、草稿及提交 pending |
| 跨主機交換 | 預覽完整差異、來源及缺少素材，再明確套用為新草稿；只有 ID 的 JSON 不宣稱攜帶圖片。若另加圖片套件，需另定大小／解壓／路徑界限與逐角色 hash 驗證，不自動抓 URL 或依檔名替換 |
| 比較方案 | 使用另一專用 kind，凍結完整 baseline、workflow_id、素材綁定及每組全部 settings；軸按流程白名單，一次一個變因。保留版本／hash、載入／任務／作品關聯及人工評分，不自動批次、重試或品質評分 |

啟用任一項前，須完成該版本的保存→下載→匯入預覽→套用／還原→比較或提交，驗證來源遺失／封存／hash 改變、不同主機、未知版本、v1／v2 分離、PUT 衝突、精確 seed、有序 LoRA、雙輸入及全部羽化／控制參數。不能只擴充一個 Literal 就宣稱整條流程已支援。本輪沒有新增可匯入 kind、遷移、專用草稿 store 或比較軸，也沒有更改一般格式版本。

## 明確拒絕與完整保留的驗證

- 一般草稿 POST／PUT 拒絕專用欄位、pending marker、workflow ID 及其他未知欄位；正常草稿保存／更新及 revision 衝突維持。
- 一般交換拒絕四個專用 ID；假稱一般圖生圖／文生圖而帶專用欄位也拒絕。原任務／作品 settings-export 明示拒絕並提示完整 workflow。
- 一般比較的預覽／匯出、文件匯入／匯出及方案保存拒絕專用設定，不建立任務、不連引擎、不寫入或丟棄欄位。
- 四版本的任務／作品 `/creation-settings` 完整還原；`/workflow` 與原 graph 相同，保留 `18446744073709551615` 整數文字。查閱與拒絕前後 SQLite bytes 相同，原版本不變。

新增 5 項後端整合測試、5 項 Chromium 案例。1440px／390px 分別驗證兩工作台版本別能力、拒絕、不增加生成／上傳／草稿／方案／任務、精確 seed 及未提交表單切頁後保留；另測支援讀取失敗與重試。支援區 axe 無違規，畫面不水平溢出；截圖留於 `runtime/quality/browser-results/workflow-format-support-*/`。這是隔離平台／模擬引擎證據，沒有新增 GPU 生成或實體觸控驗收。

```powershell
.\.venv\Scripts\python.exe -m unittest backend.test_workflow_support
.\.venv\Scripts\python.exe scripts/check_quality.py
```

最終完整品質入口通過 scoped format／static、585 項後端（1 項既有 Windows 權限條件跳過）、Vue build、四組前端契約及 87 項 Chromium（4.4 分鐘）。檢視兩工作台的 1440px／390px 四張支援範圍截圖，文字換行可讀。完整 log 為 `runtime/r07-quality-final.log`；初次完整回歸發現舊封套回讀的相容問題，補有限相容及反冒用測試後重跑通過。

R07-01／02 的格式評估及尚未支援時的保護已完成；後續專用功能啟用須另按完整契約實作與驗收。既有說明：[局部編輯](inpainting.md)、[羽化](inpaint-feather.md)、[Canny](controlnet.md)、[一般交換](creation-settings-transfer.md)、[比較方案](experiment-plans.md)。
