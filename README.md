# Model Atelier

個人 AI 圖像創作與實驗工作台。Vue 3 + TypeScript 前端、Python + FastAPI 後端，優先在 RTX 3060 本機開發，再於 RTX 4080 驗證。

## 目前功能

- 系統資訊：NVIDIA GPU、VRAM、RAM、平台資料磁碟、更新時間與失敗狀態。
- ComfyUI 位址保存至 SQLite，檢查連線並獨立呈現引擎回報的裝置資訊。
- 平台不因無 GPU 而阻止使用。
- 模型庫：同步 ComfyUI checkpoint 名稱、搜尋與狀態篩選、保存來源與備註、選擇偏好模型。
- 創作工作台：正／負提示詞、尺寸、完整 seed、模型與取樣設定、畫布比例預覽，以及本機草稿保存與重載。
- 參考素材：圖片上傳、預覽、搜尋、命名、封存／還原，以及草稿素材關聯。
- 生成任務：標準 checkpoint 文生圖提交、任務查詢、重複請求防護及完整工作流程下載。
- 作品庫：匯入已完成任務圖片、本機原圖與縮圖、搜尋、大圖預覽、生成參數及下載，並可載入支援流程的創作設定。尚未提供訓練或模型下載。

## 本機安裝（PowerShell）

目前已驗證 Python 3.12.10 與 Node.js 24.19.0。於專案根目錄執行：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.lock.txt
Set-Location frontend
npm.cmd ci
npm.cmd run build
Set-Location ..
.\start-local.ps1
```

瀏覽 <http://127.0.0.1:8000>。Ctrl+C 停止服務。前端建置後由 FastAPI 提供，不需要另外啟動 Node 服務。

Windows 使用者也可以直接雙擊根目錄的 `start-all.bat`，它會開啟兩個獨立視窗並分別執行 `start-local.ps1` 與 `start-comfyui.ps1`。這個 `.bat` 只是啟動捷徑，服務仍由 PowerShell 腳本負責檢查環境與啟動參數。

關閉方式：在平台視窗按 `Ctrl+C` 停止 `8000`，在 ComfyUI 視窗按 `Ctrl+C` 停止 `8188`，看到命令提示字元返回後再關閉視窗。只需要保存草稿或瀏覽已匯入作品時，可以只關閉 ComfyUI；需要完全停止本專案時，兩個視窗都要停止。不要用工作管理員結束所有 `python.exe`，因為其他 Python 專案可能同時運行。

## 連接埠（Port）一覽

以下是本專案的服務設定與用途；執行狀態於 2026-10-02 查核，之後會隨服務啟停改變。專案啟動腳本均綁定本機 `127.0.0.1`。

| Port | 服務／用途 | 使用時機與啟動方式 | 查核狀態 |
| --- | --- | --- | --- |
| `8000` | Model Atelier 主平台：FastAPI API、建置後的 Vue 頁面、參考素材與作品圖片 | 日常使用；根目錄執行 `./start-local.ps1`，瀏覽 `http://127.0.0.1:8000/` | 本日未啟動 |
| `8188` | ComfyUI：模型及取樣能力清單、生成任務、佇列／歷史、進度與輸出圖片讀取 | 生成、同步選項／模型或匯入圖片時使用；根目錄執行 `./start-comfyui.ps1` | 2026-10-02 真實能力同步驗證後已關閉 |
| `5173`（預設） | Vite 前端開發伺服器：Vue 熱更新；`/api` 代理到 `8000` | 僅前端開發需要；在 `frontend/` 執行 `npm.cmd run dev` | 本日未查核占用狀態；實際開發網址以 Vite 終端輸出為準 |
| `8001`（臨時） | 隔離測試平台，使用暫存資料庫、測試圖片與模擬引擎 | 2026-10-02 作品設定、任務取消、進度與取樣選項瀏覽器驗證使用，非固定服務、非日常依賴 | 已停止監聽，隔離資料與臨時啟動腳本已清除 |

日常使用只需啟動 `8000` 與 `8188`。介面、API、作品預覽共用 `8000`；已匯入的作品即使 ComfyUI 關閉仍可瀏覽。SQLite 是本機檔案，不占用網路連接埠；作品庫也不需要額外服務埠。

Vite 設定未啟用 `strictPort`，預設埠被占用時會嘗試下一個可用埠；不要直接把其他專案的 `5173` 當成本平台。需要固定開發埠時可自行指定 Vite 的 `--port` 與 `--strictPort` 參數。

設定來源：平台埠在 `start-local.ps1`；ComfyUI 埠在 `start-comfyui.ps1`；前端開發指令在 `frontend/package.json`，API 代理目標在 `frontend/vite.config.ts`。若更改平台埠，需同步調整 Vite 代理；若更改 ComfyUI 埠，需同步修改啟動參數及平台「設定」頁的引擎網址。既有任務仍保存原引擎網址。

`start-all.bat` 會啟動上述兩個腳本，不會另外建立新的服務或連接埠；按 `Ctrl+C` 的方式相同。

若 PowerShell 不允許執行腳本，可直接在根目錄執行：

```powershell
.\.venv\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

## 前端開發

後端依上述方式啟動，另一個終端執行：

```powershell
Set-Location frontend
npm.cmd run dev
```

開啟 Vite 顯示的本機位址，`/api` 代理至 8000。修改介面可熱更新。

## ComfyUI

本機 ComfyUI 使用 `runtime/ComfyUI` 內的獨立 `.venv`，不與平台 `.venv` 混用。`runtime/` 已排除於 Git。預設連接 `http://127.0.0.1:8188`，可在設定頁修改。未啟動時，平台仍可使用系統資訊功能。

從專案根目錄啟動（另開終端執行平台 `start-local.ps1`）：

```powershell
.\start-comfyui.ps1
```

腳本只監聽本機 8188，停用雲端 API 節點，Ctrl+C 停止。初始安裝不含 checkpoint；模型庫成功同步時顯示 0 個模型是正常結果，不能視為已完成生圖驗證。

其他主機的安裝流程：

```powershell
git clone https://github.com/Comfy-Org/ComfyUI.git runtime/ComfyUI
python -m venv runtime/ComfyUI/.venv
.\runtime\ComfyUI\.venv\Scripts\python.exe -m pip install --no-cache-dir torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu130
.\runtime\ComfyUI\.venv\Scripts\python.exe -m pip install --no-cache-dir -r runtime/ComfyUI/requirements.txt
```

重新安裝時需確認當時官方版本與驅動相容性。模型檔可放在 `runtime/ComfyUI/models/checkpoints/`，或使用 ComfyUI 的額外模型路徑設定。

平台主機的硬體取自 psutil / nvidia-smi，模型執行環境取自 ComfyUI `/system_stats`。引擎沒有提供的遠端磁碟資料顯示無法取得，不以本機磁碟代替。

## 創作草稿

創作工作台可以在未安裝模型時先保存構想。新草稿採用目前模型庫的偏好模型（若仍列在清單），支援另存新草稿、載入及未保存變更提示。切換平台頁面保留編輯內容；重新整理瀏覽器前需保存。

草稿保存當下的模型登記版本、引擎位址、完整 seed、尺寸、正／負提示詞及 steps、CFG、sampler、scheduler、denoise。Seed 以字串保存，支援 64 位元非負整數，避免 JavaScript 數字精度流失。舊草稿缺少新增取樣欄位時採用原流程預設值。更新以修訂號檢查衝突，不默默覆寫另一視窗的更新。草稿未提交給 ComfyUI，比例預覽不是生成結果；目前尺寸範圍為表單驗證，並不保證任何模型或硬體可執行該尺寸。

## 參考素材

在「參考素材」頁上傳單張 PNG、JPEG 或 WebP，最多 20 MiB、1600 萬像素。平台讀取實際圖片格式，拒絕損壞檔案及動畫，校正方向並移除中繼資料後保存 PNG 副本。原始檔仍由使用者保留。

每份草稿可選最多八張素材。素材存在 `data/assets/`，資料與草稿關聯存在 SQLite；備份時需一起備份整個 `data/`。被已保存草稿引用的素材不能封存，先解除引用並保存草稿即可封存。封存不刪除檔案，可在已封存清單還原。

目前只保存參考素材關聯，尚未實作參考用途、權重或 ComfyUI 圖片輸入，不代表圖片已影響生成結果。

## 模型庫操作說明

在模型庫按「同步模型清單」，平台讀取 ComfyUI `/object_info/CheckpointLoaderSimple` 的 checkpoint 選項。此版本只涵蓋這個載入節點，不代表 ComfyUI 所有模型類型；不複製或下載模型檔。

每個引擎位址各自保存快照、來源網址、備註與偏好模型。離線或回應格式錯誤時保留上次資料；模型從清單移除後保留其備註並標示「最近清單未列出」。清單只代表同步當下引擎登記的名稱，不代表已驗證架構、授權或能成功生成。

「設為偏好」只保存選擇，不會載入 GPU。來源、模型版本與備註可手動整理；未填版本或來源顯示「未知」，登記版本不視為自動驗證。檔案雜湊、大小與自動架構辨識尚未實作。

模型庫另外顯示目前連接的 ComfyUI `/system_stats` 回報版本及官方 GitHub 專案連結；離線或無版本資料時顯示「未知」，不以 GitHub 最新版代替正在執行的版本。

模型庫離線、資料合併、主機隔離與驗證錯誤已用模擬 ComfyUI 回應測試。2026-09-06 已在 RTX 3060 上完成真實 ComfyUI 連線與空 checkpoint 清單同步；尚未驗證實際模型載入與生成。

本次環境：ComfyUI 0.34.0（commit `15eb748b3ec5f8a0a2d470b7fb280e2d7579f916`）、Python 3.12.10、PyTorch 2.14.0+cu130、NVIDIA 驅動 616.56。CUDA 矩陣運算及 `pip check` 通過，完整套件快照保存於本地 `runtime/comfyui-installed.txt`。

## 資料與測試

設定保存在 `data/atelier.sqlite3`。停止平台後可備份整個 `data/`；`.venv`、`node_modules`、`dist` 與 `data` 不提交版本控制。

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s backend -v
```

目前僅供本機使用，綁定 127.0.0.1，尚無登入功能。Docker 待平台功能穩定後評估，初期不需要安裝 Docker。後續容器化須分別處理資料持久化、GPU 存取與 ComfyUI 連線。


## ComfyUI 任務提交

創作頁的「生成圖片」會提交目前表單，保存草稿仍是獨立操作。第一版採標準 checkpoint 文生圖，預設 20 steps、Euler / normal、CFG 7、denoise 1、空白負面提示詞；正／負提示詞與取樣參數可編輯、保存並提交，batch 固定為 1。平台 Steps 範圍 1–150、CFG 範圍 0–30、denoise 範圍 0–1；生成使用平台與引擎範圍的交集，取樣器及 scheduler 從 ComfyUI 同步。暫不支援 FLUX 專用流程、LoRA 或參考圖輸入。選有參考素材時明確拒絕生成，避免誤以為已套用圖片。尺寸通過驗證不代表顯存一定足夠。

- `POST /api/generate`：草稿欄位加 UUID `request_id`，後端建立工作流程，seed 由字串轉為精確整數。
- `POST /api/jobs`：`request_id`、`engine_url`、`checkpoint`、完整 ComfyUI API 格式 `workflow`。僅接受目前六種標準節點，SaveImage 前綴固定為 ModelAtelier，不接受任意自訂節點或編輯器格式 JSON。
- `GET /api/jobs`：本平台任務清單及已知佇列狀態。
- `GET /api/jobs/{id}`：任務、完整工作流程及已取得的 ComfyUI 歷史。
- `POST /api/jobs/{id}/refresh`：向任務原引擎查詢 history / queue，更新 queued、running、completed、failed 或 unknown；切換設定不改變舊任務的引擎。
- `GET /api/jobs/{id}/workflow`：直接下載原始完整 JSON，避免瀏覽器重新序列化破壞 64 位元 seed。

提交前重新查詢 checkpoint；無模型或模型消失回傳 409，離線回傳 503，模型清單無效回傳 502，工作流程被引擎拒絕回傳 422 並保存節點錯誤。任務先寫 SQLite，再提交引擎；相同 ID、相同內容回傳既有紀錄，不重複送出；相同 ID、不同內容回傳 409。提交逾時或回應不明標示 unknown，不自動重送。引擎清空歷史或重啟後找不到任務也不推定成功。瀏覽器斷線保留原請求供恢復。

輸出圖片先保存在 ComfyUI output；任務完成後可到作品庫手動匯入。平台保存工作流程及查詢到的歷史 JSON。完整工作流程是 ComfyUI API graph，不含節點編輯器版面配置。

排隊中的任務可按「取消排隊」，確認後只刪除任務原引擎中對應的排隊項目。平台會重新查詢佇列與歷史；任務已開始執行時不停止它，不清空其他任務。取消結果不明時顯示「取消結果待確認」，可以繼續查詢，不自動重送生成。取消後保留原工作流程及模型版本，同一生成請求 ID 不會再次入列。

`POST /api/jobs/{id}/cancel` 取消指定排隊任務或確認先前取消結果。ComfyUI 的排隊刪除介面回應成功不代表實際刪除了項目；平台以後續佇列／歷史確認並保存取消紀錄。「已取消排隊」表示刪除請求已被接受且確認時未找到任務，不保證任務從未執行。執行中任務的停止操作尚未提供。

2026-10-02：取消功能通過 51 項後端測試及前端型別檢查／建置。隔離模擬引擎的瀏覽器驗證確認只移除指定排隊任務，其他排隊與執行項目保留；測試涵蓋逾時、競態、當機後查詢與重複請求。尚未以實際 GPU 排隊生成驗證。

2026-09-06：19 項後端測試及 Vue 型別檢查／建置通過。真實 ComfyUI 空 checkpoint 提交驗證為 409，未監聽端點驗證為 503；測試使用暫存資料庫。尚無 checkpoint，因此成功推論與 GPU 出圖仍待實機驗證。

## 引擎取樣選項與相容檢查

創作頁的進階設定顯示目前引擎 `KSampler` 提供的 Sampler、Scheduler、steps／CFG／denoise 範圍及同步時間。重新整理清單或按「更新引擎選項」會查詢引擎；不再以固定的少數選項代表引擎全部能力。能力快照按引擎位址保存，離線或回應異常時顯示最後快照與原因，沒有快照則顯示尚無資料。

`GET /api/engine/capabilities`、`POST /api/engine/capabilities/sync` 均重新讀取目前引擎 `/object_info/KSampler`。回傳 `engine_url`、`current_engine_url`、`engine_matches`、`available`、`stale`、`sampler_names`、`schedulers`、`bounds`、`engine_bounds`、`synced_at`、`sync_error`。`bounds` 是平台與引擎範圍的交集；`engine_bounds` 保留引擎原始數值範圍／預設值供查閱。HTTP 200 也可能是過期快照，需檢查 `stale` 及 `engine_matches`，不能只以 `available` 判斷。

載入草稿或作品時不改寫原 Sampler、Scheduler 或數值，不支援的選項仍顯示原值。離線、能力未確認、引擎不符或不相容時停用新的生成操作，草稿仍可依平台欄位範圍保存。範圍取交集，不自動截短數值；CFG 等浮點欄位不強制套用引擎介面的按鍵增量，原 CFG 5.55 可保留。

`POST /api/generate` 與直接 `POST /api/jobs` 都會在入列前重新查詢 checkpoint 及 KSampler，驗證每個 KSampler 的取樣器、scheduler、steps、CFG、denoise 及整數 seed，並再次確認目前引擎未變更。不相容回傳 422，能力離線／查詢失敗或異常也明確拒絕，沒有發送 `/prompt`。既有相同請求 ID 直接回傳保存的結果，即使引擎設定已切換也不重新驗證或提交；不同內容仍回傳 409。

標準 EmptyLatentImage 仍以平台尺寸 64–8192、8 的倍數、batch_size 1 驗證，本次沒有動態擴大尺寸或導入 FLUX 專用流程。取樣清單存在不代表模型架構、GPU 顯存或完整工作流程已通過相容驗證。

2026-10-02：84 項後端測試、前端型別檢查／建置與依賴檢查通過。RTX 3060 本機 ComfyUI 0.34.0 實測讀取 45 種 sampler 與 9 種 scheduler。隔離瀏覽器驗證選項變更時提交被拒絕且不入列、原設定可保存、手動調整後精確 seed 與 CFG 5.55 可提交，以及離線快照提示。測試服務與資料已清理；尚無 checkpoint，未驗證實際 GPU 出圖。

## 即時任務進度

`GET /api/jobs/{id}/events` 以 SSE 傳送 `job` 摘要與 `connection` 連線狀態。平台向任務原 ComfyUI 引擎開啟 WebSocket，使用提交時的 client ID；同一任務的多個頁面共用上游連線，並以 SQLite 監聽租約避免多個平台程序搶用同一 ID。每個任務最多 8 個訂閱、每個程序最多 16 個監聽任務，超過回傳 429。事件只接受原 prompt ID 與工作流程中的節點，忽略預覽二進位資料、全域訊息與其他任務；不傳送完整工作流程或 64 位元 seed。

創作頁顯示目前節點、取樣數與節點百分比。100% 只表示該節點進度，完成或失敗仍以引擎歷史查詢確認。進度每秒最多寫入一次，保留最後樣本及更新時間。斷線後重連原引擎並查詢原任務；重連次數與低頻查詢有上限，失敗後可按「更新任務狀態」或「重新連線進度」。所有恢復操作均不重新提交工作流程。

前端即時監聽最近 4 個未完成任務，其餘或失去連線的任務每 15 秒查詢。切換離開創作頁、隱藏分頁或關閉頁面會清理監聽，返回後重新讀取狀態；最後訂閱離開會關閉上游 WebSocket。舊進度不當作新進度，取消確認中的狀態及已結束任務不被進度事件覆寫。

`start-local.ps1` 設定 5 秒優雅關閉等待上限，避免長時間開著進度頁時 Ctrl+C 無限等待。這只關閉平台連線，生成仍由 ComfyUI 執行。新增 `websockets` 依賴；既有環境更新後請執行 `.\.venv\Scripts\python.exe -m pip install -r requirements.lock.txt`。

2026-10-02：69 項後端測試、前端型別檢查／建置與依賴檢查通過。隔離瀏覽器驗證節點進度、上游斷線恢復、歷史確認完成及切換頁面清理；沒有重新提交任務。這些使用模擬引擎事件，實際 GPU 出圖仍待 checkpoint。

## 作品庫

在創作頁更新任務狀態，完成後按「前往作品庫匯入圖片」，或直接在作品庫選擇已完成任務。按「匯入／補齊圖片」會向該任務原 ComfyUI 引擎讀取已記錄的 SaveImage output，保存原始圖片與 512px 以內的 PNG 縮圖；不會重新生成。支援每張 32 MiB、3200 萬像素以內的單張 PNG、JPEG、WebP，每個任務最多 64 張。

作品可搜尋檔名、模型與提示詞，開啟大圖預覽、查看正／負提示詞、精確 seed、取樣參數、來源引擎，並下載原圖與完整工作流程。參數沿該輸出節點的連線解析，無法辨識時顯示未知；模型版本從這次起在提交時保存登記值，舊任務缺少版本時顯示未知，不用匯入當下的版本回填。

同一任務、輸出節點與檔案只保存一筆作品。部分圖片下載失敗會逐張提示，已保存作品保留，再次匯入會略過既有紀錄。引擎離線、來源圖片遺失、無效路徑、格式或尺寸不符、磁碟寫入失敗均有錯誤提示。已匯入的圖片可在引擎離線時瀏覽；本機檔案遺失會提示從備份還原，保留生成設定，也不自動用可能已變更的來源檔覆蓋。

在作品卡片或預覽按「載入創作設定」，會將支援的標準 checkpoint 文生圖流程載入為新的未保存草稿；載入不會提交任務，也不會覆寫原草稿或作品。若工作台有未保存變更，需選擇繼續編輯或捨棄變更再載入。保存草稿與再次生成仍由使用者分別操作。

載入時保留原引擎位址、checkpoint、精確 seed、正／負提示詞及完整取樣設定，尺寸取自原流程的 latent 輸入，而非可能已轉換的作品圖片尺寸。來源模型版本獨立呈現；原引擎不同、模型未列出、模型清單未同步或登記版本不同均有提示。版本只是提交時登記資訊，設定還原不保證跨環境逐像素一致。原圖檔案遺失時仍可載入保存的設定。

目前只還原能完整對應表單的單張標準流程。不支援的節點、額外分支、批次或無法完整對應的參數會回傳 422，保留目前工作台內容，可改為下載完整工作流程。未確認的舊提交請求仍保留原 ID 與參數，恢復時不會使用新載入的設定。

原圖與縮圖存在 `data/artworks/`，作品紀錄與工作流程快照存在 `data/atelier.sqlite3`。停止平台後備份整個 `data/`，還原時也須一起還原。原圖保留原始位元組及中繼資料，縮圖經方向校正並移除中繼資料；平台不刪除 ComfyUI 的來源圖片。目前尚無作品刪除、收藏或備註。

API：

- `POST /api/jobs/{id}/artworks`：匯入已確認成功的任務輸出，回傳 `imported`、`existing`、`errors`；HTTP 200 可能含逐張匯入錯誤，需檢查 `errors`。未知任務為 404，任務狀態或輸出清單不適用為 409。
- `GET /api/artworks`、`GET /api/artworks/{id}`：作品資訊、生成參數與本機檔案存在狀態。
- `GET /api/artworks/{id}/creation-settings`：從作品工作流程取得表單設定、來源模型版本與提示；只讀取本機資料，不連接引擎或提交任務。未知作品回傳 404，不支援完整還原的流程回傳 422。
- `GET /api/artworks/{id}/image`：原圖預覽；`?thumbnail=true` 取得縮圖，`?download=true` 下載原圖；檔案遺失回傳 404。
- `GET /api/artworks/{id}/workflow`：下載作品保存的完整 JSON，不經瀏覽器重新序列化 seed。

2026-09-06：26 項後端測試與前端型別檢查／建置通過，涵蓋並行去重、部分失敗重試、離線瀏覽、無效路徑、圖片／磁碟錯誤與版本快照。隔離資料庫的瀏覽器測試已驗證匯入、重複匯入、大圖預覽、鍵盤關閉及 64 位元 seed 顯示。另以暫存測試 PNG 完成真實 ComfyUI `/view` 匯入並比對原圖位元組；測試資料已清除，這不代表完成模型推論驗證。

2026-10-02：34 項後端測試與 Vue 型別檢查／建置通過。隔離資料庫的瀏覽器驗證涵蓋卡片與預覽載入、精確 seed、latent 尺寸、非預設取樣值、版本提示、未保存內容的取消／確認、保存新草稿及舊草稿預設值；CFG 5.55 與 denoise 0.123 可原值載入、保存，不受固定小數步進限制。再次按生成後確認工作流程保留所有參數，並顯示引擎離線錯誤；載入或保存本身不新增任務。隔離服務與資料已清理。尚無 checkpoint，GPU 模型推論仍未驗證。
