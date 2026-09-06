# Model Atelier

個人 AI 圖像創作與實驗工作台。Vue 3 + TypeScript 前端、Python + FastAPI 後端，優先在 RTX 3060 本機開發，再於 RTX 4080 驗證。

## 目前功能

- 系統資訊：NVIDIA GPU、VRAM、RAM、平台資料磁碟、更新時間與失敗狀態。
- ComfyUI 位址保存至 SQLite，檢查連線並獨立呈現引擎回報的裝置資訊。
- 平台不因無 GPU 而阻止使用。
- 模型庫：同步 ComfyUI checkpoint 名稱、搜尋與狀態篩選、保存來源與備註、選擇偏好模型。
- 創作工作台：提示詞、尺寸、seed、模型選擇、畫布比例預覽，以及本機草稿保存與重載。
- 參考素材：圖片上傳、預覽、搜尋、命名、封存／還原，以及草稿素材關聯。
- 生成任務：標準 checkpoint 文生圖提交、任務查詢、重複請求防護及完整工作流程下載。
- 作品庫：匯入已完成任務圖片、本機原圖與縮圖、搜尋、大圖預覽、生成參數及下載。尚未提供訓練或模型下載。

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

## 連接埠（Port）一覽

以下是本專案的服務設定與用途；執行狀態於 2026-09-06 查核，之後會隨服務啟停改變。專案啟動腳本均綁定本機 `127.0.0.1`。

| Port | 服務／用途 | 使用時機與啟動方式 | 查核狀態 |
| --- | --- | --- | --- |
| `8000` | Model Atelier 主平台：FastAPI API、建置後的 Vue 頁面、參考素材與作品圖片 | 日常使用；根目錄執行 `./start-local.ps1`，瀏覽 `http://127.0.0.1:8000/` | 已啟動，`/api/health` 正常 |
| `8188` | ComfyUI：模型清單、生成任務、佇列／歷史及輸出圖片讀取 | 生成、同步模型或匯入圖片時使用；根目錄執行 `./start-comfyui.ps1` | 已啟動，`/system_stats` 正常 |
| `5173`（預設） | Vite 前端開發伺服器：Vue 熱更新；`/api` 代理到 `8000` | 僅前端開發需要；在 `frontend/` 執行 `npm.cmd run dev` | 此埠目前由其他專案占用，不能視為 Model Atelier 的開發服務；實際開發網址以 Vite 終端輸出為準 |
| `8001`（臨時） | 作品庫隔離測試平台，使用暫存資料庫與測試圖片 | 僅本次瀏覽器驗證曾使用，非固定服務、非日常依賴 | 已停止監聽，測試資料與臨時啟動腳本已清除 |

日常使用只需啟動 `8000` 與 `8188`。介面、API、作品預覽共用 `8000`；已匯入的作品即使 ComfyUI 關閉仍可瀏覽。SQLite 是本機檔案，不占用網路連接埠；作品庫也不需要額外服務埠。

Vite 設定未啟用 `strictPort`，預設埠被占用時會嘗試下一個可用埠；不要直接把其他專案的 `5173` 當成本平台。需要固定開發埠時可自行指定 Vite 的 `--port` 與 `--strictPort` 參數。

設定來源：平台埠在 `start-local.ps1`；ComfyUI 埠在 `start-comfyui.ps1`；前端開發指令在 `frontend/package.json`，API 代理目標在 `frontend/vite.config.ts`。若更改平台埠，需同步調整 Vite 代理；若更改 ComfyUI 埠，需同步修改啟動參數及平台「設定」頁的引擎網址。既有任務仍保存原引擎網址。

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

草稿保存當下的模型登記版本、引擎位址、完整 seed、尺寸與提示詞。Seed 以字串保存，支援 64 位元非負整數，避免 JavaScript 數字精度流失。更新以修訂號檢查衝突，不默默覆寫另一視窗的更新。草稿未提交給 ComfyUI，比例預覽不是生成結果；目前尺寸範圍為表單驗證，並不保證任何模型或硬體可執行該尺寸。

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

創作頁的「生成圖片」會提交目前表單，保存草稿仍是獨立操作。第一版採標準 checkpoint 文生圖：20 steps、Euler / normal、CFG 7、batch 1；暫不支援 FLUX 專用流程、LoRA 或參考圖輸入。選有參考素材時明確拒絕生成，避免誤以為已套用圖片。尺寸通過驗證不代表顯存一定足夠。

- `POST /api/generate`：草稿欄位加 UUID `request_id`，後端建立工作流程，seed 由字串轉為精確整數。
- `POST /api/jobs`：`request_id`、`engine_url`、`checkpoint`、完整 ComfyUI API 格式 `workflow`。僅接受目前六種標準節點，SaveImage 前綴固定為 ModelAtelier，不接受任意自訂節點或編輯器格式 JSON。
- `GET /api/jobs`：本平台任務清單及已知佇列狀態。
- `GET /api/jobs/{id}`：任務、完整工作流程及已取得的 ComfyUI 歷史。
- `POST /api/jobs/{id}/refresh`：向任務原引擎查詢 history / queue，更新 queued、running、completed、failed 或 unknown；切換設定不改變舊任務的引擎。
- `GET /api/jobs/{id}/workflow`：直接下載原始完整 JSON，避免瀏覽器重新序列化破壞 64 位元 seed。

提交前重新查詢 checkpoint；無模型或模型消失回傳 409，離線回傳 503，模型清單無效回傳 502，工作流程被引擎拒絕回傳 422 並保存節點錯誤。任務先寫 SQLite，再提交引擎；相同 ID、相同內容回傳既有紀錄，不重複送出；相同 ID、不同內容回傳 409。提交逾時或回應不明標示 unknown，不自動重送。引擎清空歷史或重啟後找不到任務也不推定成功。瀏覽器斷線保留原請求供恢復；進行中的任務每五秒查詢狀態。

輸出圖片先保存在 ComfyUI output；任務完成後可到作品庫手動匯入。平台保存工作流程及查詢到的歷史 JSON。完整工作流程是 ComfyUI API graph，不含節點編輯器版面配置。

2026-09-06：19 項後端測試及 Vue 型別檢查／建置通過。真實 ComfyUI 空 checkpoint 提交驗證為 409，未監聽端點驗證為 503；測試使用暫存資料庫。尚無 checkpoint，因此成功推論與 GPU 出圖仍待實機驗證。

## 作品庫

在創作頁更新任務狀態，完成後按「前往作品庫匯入圖片」，或直接在作品庫選擇已完成任務。按「匯入／補齊圖片」會向該任務原 ComfyUI 引擎讀取已記錄的 SaveImage output，保存原始圖片與 512px 以內的 PNG 縮圖；不會重新生成。支援每張 32 MiB、3200 萬像素以內的單張 PNG、JPEG、WebP，每個任務最多 64 張。

作品可搜尋檔名、模型與提示詞，開啟大圖預覽、查看正／負提示詞、精確 seed、取樣參數、來源引擎，並下載原圖與完整工作流程。參數沿該輸出節點的連線解析，無法辨識時顯示未知；模型版本從這次起在提交時保存登記值，舊任務缺少版本時顯示未知，不用匯入當下的版本回填。

同一任務、輸出節點與檔案只保存一筆作品。部分圖片下載失敗會逐張提示，已保存作品保留，再次匯入會略過既有紀錄。引擎離線、來源圖片遺失、無效路徑、格式或尺寸不符、磁碟寫入失敗均有錯誤提示。已匯入的圖片可在引擎離線時瀏覽；本機檔案遺失會提示從備份還原，保留生成設定，也不自動用可能已變更的來源檔覆蓋。

原圖與縮圖存在 `data/artworks/`，作品紀錄與工作流程快照存在 `data/atelier.sqlite3`。停止平台後備份整個 `data/`，還原時也須一起還原。原圖保留原始位元組及中繼資料，縮圖經方向校正並移除中繼資料；平台不刪除 ComfyUI 的來源圖片。目前尚無作品刪除、收藏、備註或一鍵載入創作設定。

API：

- `POST /api/jobs/{id}/artworks`：匯入已確認成功的任務輸出，回傳 `imported`、`existing`、`errors`；HTTP 200 可能含逐張匯入錯誤，需檢查 `errors`。未知任務為 404，任務狀態或輸出清單不適用為 409。
- `GET /api/artworks`、`GET /api/artworks/{id}`：作品資訊、生成參數與本機檔案存在狀態。
- `GET /api/artworks/{id}/image`：原圖預覽；`?thumbnail=true` 取得縮圖，`?download=true` 下載原圖；檔案遺失回傳 404。
- `GET /api/artworks/{id}/workflow`：下載作品保存的完整 JSON，不經瀏覽器重新序列化 seed。

本次 26 項後端測試與前端型別檢查／建置通過，涵蓋並行去重、部分失敗重試、離線瀏覽、無效路徑、圖片／磁碟錯誤與版本快照。隔離資料庫的瀏覽器測試已驗證匯入、重複匯入、大圖預覽、鍵盤關閉及 64 位元 seed 顯示。另以暫存測試 PNG 完成真實 ComfyUI `/view` 匯入並比對原圖位元組；測試資料已清除，這不代表完成模型推論驗證。
