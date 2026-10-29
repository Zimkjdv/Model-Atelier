# 固定測試集與參數比較方案

比較流程依序是[建立方案](#固定測試集與參數比較方案)、[保存與匯入](#storage-and-import)、[明確關聯任務與作品](#runs-and-artworks)、[匯出結果報告](#result-reports)。方案預覽、保存、表單載入與實際生成是不同操作；下方日期段落記錄各功能加入時的驗收，不取代目前的完整流程。

2026-10-23 R05：新增 `anime-illustration-v1.json` 的半身、全身／服裝、車站人物與場景三案例，可在「測試集」選單與通用插畫 v1 間切換；切換清除舊案例選擇及預覽，保留創作設定。新 `prompt`／`negative_prompt` 軸以完整字串陣列比較文字／標籤格式，只改選定提示詞欄位。正向比較不可同時選固定案例，避免提示詞互相覆蓋；反向可用空字串。兩軸沿用 schema 2 的模型登記快照、保存／匯入與生成核對，不自動套用作者格式或改變其他參數。

2026-10-23 R06：新增 Checkpoint 模型、Sampler 取樣器與 Scheduler 排程器軸，涵蓋 checkpoint 文生圖／單張圖生圖，精確名稱用字串陣列。模型比較需原引擎已同步且登記為相同 SD 1.x／SDXL 架構，不自動改動 LoRA。新軸使用 schema 2 保存模型登記快照，生成交易核對版本／架構／大小／hash；未知保持未知。舊六軸維持 schema 1，總數仍最多 8 組且逐組手動生成。欄位、相容規則與驗收見 [R06 紀錄](validation/extended-comparisons-20261023.md)。

局部編輯／羽化／Canny 專用設定不支援一般比較方案，預覽、文件匯入／匯出及保存均明確拒絕；不以捨棄雙輸入或控制參數的方式降成一般流程。專用格式方案與版本別能力見 [R07 評估](specialized-workflow-formats.md)。

創作工作台的「固定測試集與參數比較」提供 checkpoint 文生圖與單張圖生圖的唯讀方案預覽。先選模型並確認完整設定，再選 Steps、CFG、Seed、圖生圖 Denoise 或指定 LoRA 的模型／CLIP 強度一個參數軸，輸入 1–4 個 JSON 值。Seed 必須使用字串，例如 `["9007199254740993", "18446744073709551615"]`；不轉成 JavaScript number。數值超界、型別不符或正規化後重複會拒絕，不自動截斷或調低設定。

固定測試集為自行編寫的 `experiments/general-illustration-v1.json`，版本 1；Git 保持 LF 換行，API 回報完整檔案 bytes 的 SHA256。案例為黑白木椅說明書、山湖構圖，以及同一成年旅人在書店／車站的兩個場景，各有人工評估要點。共同 `character_key` 只是比較分組，不提供角色鎖定。未選案例時沿用目前提示詞；選固定案例會明確替換正提示詞，保留負提示詞、尺寸、原引擎、模型、有序 LoRA 及其餘參數。方案標題另標案例與參數值。

預計任務數為案例數乘以參數值數，最多 8 次，每次 1 張。例如兩個案例與兩個 seed 會列出四份完整設定。超過上限回傳 422，沒有部分方案或隱藏批次。圖生圖要求 image_asset_id 與唯一 reference_ids 相符；保留原素材 ID、fit／stretch、輸出尺寸及未變動參數。Denoise 軸僅圖生圖可用，0 至 1 如實保留。固定案例會替換提示詞，不替換圖片；不提供畫風或角色鎖定。FLUX 及多張／adapter 參考流程仍不支援比較預覽。

按「載入這組設定」會取代目前表單，作為未保存的新草稿；未保存變更有明確提示，原已保存草稿與任務保留。每組需另按原生成按鈕，才能建立任務並走既有即時能力與模型檢查。方案保持原基準快照，載入其他組後仍可繼續選擇；要換基準則重新預覽。顯示「已載入過」只代表表單載入，不代表生成成功。結果匯入後可在[作品比較與評分](artwork-library.md#comparison-and-ratings)人工加入比較。

「匯出比較方案 JSON」先準備完整文件，再提供明確下載連結與 JSON 內容。文件包含基準設定、流程 ID、單一軸（LoRA 軸另存 target_lora）、案例與測試集版本／hash、預計數量及所有設定快照。`plan_sha256` 使用排序鍵的 UTF-8 JSON 計算，排除該 hash 與展示 warnings；新鮮預覽匯出重新建立原方案並核對預覽 hash，測試集或輸入變更回傳 409，需重新預覽。已保存／匯入方案另以凍結文件驗證匯出，不替換成新版案例。匯出後修改表單不會改寫「上次匯出」文件。

| API | 行為 |
| --- | --- |
| `GET /api/experiments/suite` | 預設通用插畫；可用 `suite_id=anime-illustration` 選動漫集；讀取版本及檔案 bytes SHA256；未知 ID 為 422、無效檔案為 503 |
| `POST /api/experiments/preview` | 完整驗證設定，回傳最多八份單張方案；不寫入 SQLite、不連線引擎 |
| `POST /api/experiments/export` | 同一輸入加 `expected_plan_sha256` 核對，可下載 `model-atelier-comparison-plan.json` |

POST 輸入包含 `title`、完整的 `settings`、`axis`、`values`、`case_ids`；可另指定 `suite_id`（預設 `general-illustration`），LoRA 軸另需 `target_lora`，必須是基準中已啟用的精確名稱，其他軸不可指定。不接受 revision、任務 UUID、自訂 workflow 或未知欄位。請求最多 256 KiB，匯出文件最多 1 MiB。完整 `settings` 沿用 checkpoint 草稿欄位但排除 revision；可由創作設定匯出文件取得。不存在的案例、空模型、空目前提示詞及重複案例拒絕。圖生圖原素材遺失或封存時保留設定並提示，預覽不驗圖片 bytes、不重建圖片；生成仍由既有流程重新檢查來源 hash。測試集損壞時仍可比較目前提示詞，不能借用未驗證案例。

已提供方案持久化、重載及 JSON 匯入預覽，見[保存與匯入說明](experiment-plans.md#storage-and-import)。此階段沒有自動批次提交、重試或結果自動關聯，也沒有耗時／VRAM 估算及自動品質評分。匯出的是比較方案，實際提交的完整 workflow 與模型／環境快照仍由原任務系統保存。2026-10-08 已完成 Pony／Animagine 固定四案例的 GPU 比較與原圖觀察，見 [實測結果](validation/general-illustration-suite-rtx3060.md)；已提供指定 LoRA 的強度比較方案；更多模型／seed／參數軸的 GPU 品質及 RTX 4080 仍待後續驗收。

2026-10-05：382 項後端測試（381 通過、1 項既有 Windows 權限跳過）、Vue 型別／建置通過。桌面瀏覽器驗證四份案例／seed 方案、重複值拒絕、最大 seed 精確載入、原有 LoRA 順序、案例提示詞替換、基準快照保留與 JSON bytes／下載檔名；未驗證瀏覽器原生下載落盤及窄視窗。沒有新增 GPU 任務或正式資料；隔離資料仍為 4 任務／4 作品／2 checkpoint 草稿／1 FLUX 草稿，僅前一項人工評分保留。畫面與 JSON 證據保存在 `runtime/experiment-plan-ui-20261005.png`、`runtime/comparison-plan-ui-20261005.json`。


2026-10-08 比較功能優先項目 1：支援 `lora_strength_model`／`lora_strength_clip`。每次只改一個已啟用 LoRA 的一種強度，其餘強度、啟用狀態及順序保持基準值；0 與負強度如實保留。平台格式範圍 -20 至 20，不代表引擎支援或品質建議，生成仍檢查即時範圍。397 項後端測試（396 通過、1 項既有 Windows 權限跳過）及 Vue 型別／建置通過；工具 sandbox 啟動失敗，UI 實機驗收未完成。沒有新增 GPU 任務或正式資料。


2026-10-08 比較功能優先項目 2：單張 checkpoint 圖生圖可比較 denoise、Steps／CFG／精確 Seed／LoRA 強度。來源 ID、唯一素材關聯、縮放方式及未變動設定完整保留。預覽不建任務；明確生成後的工作流程與還原設定已用隔離模擬引擎驗證。401 項後端測試（400 通過、1 項既有 Windows 權限跳過）及 Vue 型別／建置通過；本輪未新增 GPU 品質實測，UI 工具環境故障，實機操作仍待驗收。

2026-10-23 · V04：1440px／390px 補驗指定 LoRA 的 model／CLIP 強度軸，載入及保存零／負強度時，其餘強度、停用項目、順序與最大 64 位字串 seed 保留；缺少／停用目標、重複值、超界及數字字串拒絕且表單不變。Pony／Animagine 各自逐組載入固定四案例，測試集版本／hash 與未變動參數核對；歷史八件 GPU 結果另外唯讀並排及還原設定。未新增生成或品質預設，見 [V04 驗收](validation/comparison-measurements-20261023.md)。

<a id="storage-and-import"></a>

## 比較方案保存、重載與 JSON 匯入

先在創作工作台建立比較預覽，再展開「保存方案與 JSON 匯入」，按「保存目前預覽方案」。方案保存在 SQLite 的 `experiment:` 紀錄，包含原基準、來源素材 ID、流程、案例／版本／hash、單一軸與每組完整設定。保存不建立創作草稿或生成任務；重載只替換比較預覽，創作表單保持原值。逐組按「載入這組設定」後仍需另按生成。

原方案內容凍結，不提供直接覆寫；修改後保存新方案。封存／還原以整數 revision 比較，409 不重試或覆寫，需重新整理清單。封存保留完整快照與素材引用；沒有永久刪除 API。方案引用的素材不可封存，與保存／封存素材在同一 SQLite 寫入交易檢查。來源尚未在此主機存在的文件可保存並提示未知；已封存的本機素材需先還原才可新增方案。

保存使用獨立 request_id。同 ID＋相同 plan hash 回傳原紀錄，不增修訂、解除封存或建立第二份；同 ID＋不同方案回傳 409。介面優先使用已有相同 hash 的紀錄，另在本視窗記憶體及可用 sessionStorage 保存請求 ID；切換方案與同頁重載可沿用。若瀏覽器不允許保存暫存，關閉／重載頁面可能失去未確認請求的 ID，因此先重新整理清單再判斷，平台不自動重送。

讀取 JSON 檔或貼上後按「驗證並預覽比較文件」，檢查完整內容，再按「使用此方案預覽」。匯入驗證不寫資料、不改創作表單、不連線引擎、不生成；使用後要另按保存才持久化。文字修改會使上次匯入預覽失效。最多 1 MiB，使用 UTF-8 JSON；保留字串 seed，拒絕重複欄位、非有限數值、未知欄位、任意 workflow／任務 ID、錯誤 schema／流程及超界設定。

驗證從基準、單一軸、值與文件案例重新建立所有 variant，核對完整內容 hash、每組設定、順序、數量及 batch_size=1；單純重新計算篡改 variant 的 hash 仍會拒絕。文件 warnings 不採信，依本機狀態重新產生。Hash 表示內容一致，不能驗證作者身分、權重、模型／環境相容性或品質。

匯入及重載保留當時案例快照；目前測試集變更或損壞只給提示，不替換歷史提示詞。原模型與素材 ID 未在本機確認時保持原值，生成會重新檢查。圖片、模型權重與原生成 workflow 不包含於比較檔；生成後的任務／作品才有各自不可變來源快照。

| API | 行為 |
| --- | --- |
| `POST /api/experiments/import-preview` | 原比較文件，最多 1 MiB；只讀完整驗證，回傳帶本機提示的方案 |
| `POST /api/experiments/document-export` | 匯入／已保存方案的凍結文件匯出；不以新版案例替換原案例 |
| `GET /api/experiments/plans` | 全部保存方案摘要，包含封存、revision、hash 及原流程；不帶重複完整設定 |
| `GET /api/experiments/plans/{id}` | 讀取並重驗完整原方案；不改寫 SQLite |
| `POST /api/experiments/plans` | `{request_id, plan}`，最多 1 MiB；新增 201，同 ID 重讀 200，不同方案 409 |
| `PUT /api/experiments/plans/{id}` | `{revision, archived}`；僅改封存狀態，原方案不可覆寫 |

現有 `/preview`、`/export` 的輸入維持 256 KiB；新鮮預覽匯出仍核對 expected_plan_sha256，案例改變時 409。已保存／匯入文件使用 document-export 保留歷史內容。所有方案每次最多 8 組，不提供自動批次、重試或品質評分。保存方案的任務／作品關聯後端已接入，見 [關聯說明](experiment-plans.md#runs-and-artworks)。

2026-10-08：408 項後端測試（407 通過、1 項既有 Windows 權限跳過），Vue 型別／建置通過。隔離真實 HTTP 驗證精確 seed、LoRA 強度與圖生圖 denoise 三份保存方案、冪等保存、修訂衝突、來源引用，平台停止／重啟後 GET-only 原樣核對通過。證據 `runtime/experiment-api-acceptance-20261008.json`、`runtime/experiment-live-data-20261008`：3 方案／1 素材／0 任務／0 作品／0 草稿。正式 5 任務／3 作品／0 草稿／0 方案不變，所有測試服務已關閉。UI 工具 sandbox 啟動失敗，本輪畫面及實際瀏覽器下載／窄視窗仍未驗收；沒有新增 GPU 品質測試。

<a id="runs-and-artworks"></a>

## 比較方案的任務與作品關聯

R06 新增軸使用 context 2，另凍結 `expected_model_metadata`；生成預留交易核對原方案身分、當前登記及捕獲快照，不符 409 且不建立任務。離線保存／匯入仍使用原快照，既有 UUID 恢復不重新核對登記或重送。schema 1 及原資料不改寫，見 [R06 驗收](validation/extended-comparisons-20261023.md)。

創作頁展開「固定測試集與參數比較」，先保存方案或重載已保存方案，再按「載入這組設定」。工作台顯示方案與變體關聯；另按「生成圖片」才提交。未保存／剛匯入的方案可作一般設定載入，需先保存、重新載入組別才記錄比較結果；保存本身不追溯已載入或已生成的內容。

變更任何原設定會保留表單並阻擋沿用原關聯；可重新載入原組，或按「解除比較關聯，保留目前設定」作日常生成。保存草稿不保存關聯；重載草稿、作品或一般設定會解除。封存方案先還原並重新載入組別；其他視窗的封存由伺服器最終檢查。未確認提交保存精確原 request_id／設定／關聯，恢復不使用現在表單；處理或待恢復時不能載入新的比較組。

「比較結果」依變體顯示所有原任務與已匯入作品縮圖、原圖、封存標記及錯誤。成功但尚未匯入會顯示任務與「到作品庫匯入」，不誤稱未生成。先在任務區更新狀態、作品庫匯入，再按「重讀已保存結果」；此按鈕只讀本地資料，切換方案清除前份結果，讀取失敗保留上次資料並標示可能過期。任務與作品預覽可展開原比較來源。

目前支援 checkpoint 文生圖與單張圖生圖。先保存完整方案，再以完整變體設定呼叫 `/api/generate`，加上 `experiment`：

```json
{
  "plan_id": "已保存方案的 UUID",
  "plan_sha256": "該方案的完整 SHA256",
  "variant_id": "variant-1"
}
```

此物件放在生成輸入的 `experiment` 欄位，與原 `request_id`、完整創作設定一起提交；不放入草稿或 workflow。原始 `/api/jobs` 任意工作流程不接受關聯。沒有關聯欄位的日常生成仍照原流程。

任務預留的 SQLite `BEGIN IMMEDIATE` 交易內重新檢查方案存在、未封存、完整內容 hash 及變體設定；包括標題、停用 LoRA、精確 seed、原引擎、圖片素材及 fit／stretch。任何不符回傳 409，不預留任務或送往引擎。標題與取樣設定修改後要解除關聯，或重新載入原變體，不能把改過的結果當成原比較組。

新任務的 `experiment_context` 凍結原方案 ID／hash／標題／流程／軸／指定 LoRA／案例／值與完整變體設定；作品沿用深層複製的原快照，任務及作品管理 API 不可修改。歷史紀錄缺少關聯時只讀回傳 null，不依相同 seed／prompt／workflow 推測或回填；相同 hash 保存為不同方案 ID 仍分開。

同一 `request_id` 只接受原 workflow、關聯與完整設定；原請求恢復先讀任務，不重新查方案或引擎、不重送。方案已封存、引擎改位址或離線、輸入素材檔案遺失時也可恢復原任務；失敗及未知結果保留原關聯，重新生成需新 request_id 和明確操作。

`GET /api/experiments/plans/{id}/results` 只讀本地已保存資料，依變體列出所有手動提交的任務、狀態、原版本、量測及已匯入作品；未生成組保留空 runs。包括失敗、未知、封存作品；原圖／縮圖檔案可用性另列。作品需同一 job_id 且關聯快照完整相等，才歸到原任務。成功任務尚未匯入作品時仍列出任務，不把「尚無作品」當作未生成。

此查詢不刷新 ComfyUI、不匯入、不執行、不自動重試或補關聯。狀態是平台最後保存的觀察；取得最新引擎狀態仍使用原任務的 refresh／SSE，作品匯入仍使用原入口。封存方案保留結果可讀，還原後才能建立新的關聯任務。方案內容 hash 不是權重／品質／執行環境證明。

2026-10-08：後端回歸測試涵蓋交易期間封存、篡改 hash、錯誤變體／完整設定、重試不重送、失敗及未知結果、圖生圖原輸入恢復、作品快照、封存與離線唯讀、不同方案 ID 隔離及舊資料不回填。Vue 前端已接入；沒有自動批次。前端關聯保護可跑 `npm --prefix frontend run check:experiments`；涵蓋精確 seed、停用 LoRA／順序、變更設定、封存阻擋、解除關聯及原請求凍結。


2026-10-08 實機驗收：RTX 3060／ComfyUI 0.34.0、固定 Animagine 4.0 Opt＋IKEA LoRA，在隔離平台保存模型強度 0.5／1 兩組方案，只有第一組手動提交一次；28 steps、CFG 5、1024×1024、euler_ancestral／normal、seed `9007199254740993`。任務、作品、完整工作流程、原設定及關聯快照核對通過，第二組 runs 保持空。提交至成功歷史觀察 42.985 秒，包含冷載入／網路／佇列；整卡低頻取樣最高 12,095,324,160 bytes／21 筆，包含其他程序，不是任務專用峰值或最低顯存需求。原圖品質觀察參照同參數的 [強度比較](validation/animagine-style-strength-rtx3060.md)，此驗收驗證追溯而非品質改善。

關閉 ComfyUI 後封存方案，新 request_id 明確 409；切換隔離平台位址後原 ID 恢復同一任務、不重送。停止及重啟平台後只做 GET 核對原方案、完整任務、圖片 hash 與結果組別；包括封存狀態及來源快照。證據 `runtime/experiment-run-20261008.json`、`runtime/experiment-run-recovery-20261008.json`；隔離 1 方案／1 任務／1 作品／0 草稿，正式 5 任務／3 作品／0 草稿／0 方案不變。

420 項後端測試（419 通過、1 項既有 Windows 權限跳過）、前端關聯邏輯檢查及 Vue 建置通過。瀏覽器工具因 Windows sandbox 啟動失敗，畫面點擊、實際瀏覽器下載及窄視窗尚未驗收。驗收服務停止，8000／8001／8188／5173 均未監聽。

<a id="result-reports"></a>

## 比較結果報告

在創作工作台展開「固定測試集與參數比較 → 保存方案與 JSON 匯入」，重載已保存方案，於結果區按「準備比較結果報告」，再下載 JSON。無需引擎連線；不產生任務或匯入作品。

`GET /api/experiments/plans/{UUID}/report?expected_plan_sha256={hash}` 回傳 kind `model-atelier-comparison-results`、schema_version 1。保存方案及所有明確關聯任務／作品在同一 SQLite 讀取交易取得；不根據相同 seed／流程猜測關聯。核對原 plan hash、完整 context 與組設定、完整 workflow（含 seed 整數型別）、作品原任務。來源有損壞或缺少相符關聯回 409，方案不存在回 404；不匯出部分資料。

報告包含生成時間、原方案及修訂／封存狀態、各組所有保存的任務狀態、workflow／SHA256、版本／LoRA／參考／環境／量測快照，以及作品 hash、尺寸、目前人工評分、筆記與收藏／封存狀態。舊 runtime／量測缺失保持 null，不以目前環境回填。最多合計 100 筆任務與作品、8 MiB，超出回 413；不默默截斷。

檔案存在旗標在 DB 交易後另行檢查，屬存在性觀察；current_file_hash_verified=false，未再次讀取校驗原圖。報告不含原圖 bytes、引擎即時歷史或 API 憑證，也不是可匯入的生成方案／資料備份。任務當時資料與目前人工整理值的時間範圍分開說明。

回應為 application/json、Cache-Control:no-store、nosniff、固定 UUID 檔名及 X-Atelier-SHA256。前端限量串流讀取、驗證 kind／版本／原方案 ID／hash 及整份 bytes SHA256；下載保留原 bytes，不重新 JSON.stringify，完整 workflow 的 64 位元 seed 不受 JavaScript 數字精度影響。來源切換、KeepAlive 離開或卸載取消請求並回收 Blob URL；狀態之後改變需重新準備報告。

<a id="result-reports-historical-validation"></a>

### 2026-10-22 驗收

九項新增後端測試涵蓋離線完整快照、不寫 DB、空／封存方案、同內容不同 ID 不推測、錯誤來源與損壞流程／關聯、大小／筆數上限、非匯出作品欄位不消耗預算、舊欄位／缺檔，以及 WAL 並行更新時仍讀取同一原快照。完整後端 530 項（529 通過、1 既有 skip），三組前端邏輯與 Vue 型別／建置通過。

使用 [兩模型 denoise GPU 比較資料](validation/image-comparison-rtx3060.md) 做實際 IAB 驗收：離線重載兩個方案、查看兩個已完成變體與原作品、準備／下載 Animagine 結果報告 22,338 bytes，SHA256 aeebedb45f77b345078c0266fbc47fd37b495c159c789e76bca2e3b756d79fdb。報告包含兩個原任務、各一作品、seed 字串 9007199254740993、denoise 0.3／0.6、新效能條件與來源 hash。此 hash 僅對應該次生成時間的報告；再次準備會產生新的時間與 hash。

原比較方案 JSON 另行下載，plan hash 4ba1b1564ec281b2b06f3498e4127ea27795be44ce1baf7d89c6069c150ed647；貼上後驗證／預覽成功，沒有保存新方案或任務。結果報告貼入方案匯入會被拒絕，原預覽仍可使用；載入 variant-2 後為圖生圖、768²、精確 seed、denoise 0.6、原素材與 Animagine。作品詳細版本區顯示效能條件，實際精度／卸載／冷熱保留未知。

切換 Pony 清除舊報告下載；離開／返回工作台也清除下載。390×844 無橫向溢出（scrollWidth 375），1280×900 結果雙欄（scrollWidth 1265）；截圖與下載證據位於忽略的 runtime/comparison-report-mobile-20261022.jpg、comparison-report-desktop-20261022.jpg、comparison-report-browser-20261022.json。

驗收沒有新增任務、作品、草稿或方案；隔離仍為 1 素材／2 方案／4 任務／4 作品。正式資料指紋不變。測試服務於結束後停止，FLUX 來源存取／其他品質與 RTX 4080 仍待驗證。
