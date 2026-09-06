# Model Atelier

個人 AI 圖像創作與實驗工作台。Vue 3 + TypeScript 前端、Python + FastAPI 後端，優先在 RTX 3060 本機開發，再於 RTX 4080 驗證。

## 目前功能

- 系統資訊：NVIDIA GPU、VRAM、RAM、平台資料磁碟、更新時間與失敗狀態。
- ComfyUI 位址保存至 SQLite，檢查連線並獨立呈現引擎回報的裝置資訊。
- 平台不因無 GPU 而阻止使用。
- 模型庫：同步 ComfyUI checkpoint 名稱、搜尋與狀態篩選、保存來源與備註、選擇偏好模型。
- 創作工作台：提示詞、尺寸、seed、模型選擇、畫布比例預覽，以及本機草稿保存與重載。
- 作品庫仍為待開發頁面；尚未提供生成、訓練或模型下載。

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

## 模型庫操作

在模型庫按「同步模型清單」，平台讀取 ComfyUI `/object_info/CheckpointLoaderSimple` 的 checkpoint 選項。此版本只涵蓋這個載入節點，不代表 ComfyUI 所有模型類型；不複製或下載模型檔。

每個引擎位址各自保存快照、來源網址、備註與偏好模型。離線或回應格式錯誤時保留上次資料；模型從清單移除後保留其備註並標示「最近清單未列出」。清單只代表同步當下引擎登記的名稱，不代表已驗證架構、授權或能成功生成。

「設為偏好」只保存選擇，不會載入 GPU。來源、模型版本與備註可手動整理；未填版本或來源顯示「未知」，登記版本不視為自動驗證。檔案雜湊、大小、自動架構辨識及生成流程尚未實作。

模型庫另外顯示目前連接的 ComfyUI `/system_stats` 回報版本及官方 GitHub 專案連結；離線或無版本資料時顯示「未知」，不以 GitHub 最新版代替正在執行的版本。

模型庫離線、資料合併、主機隔離與驗證錯誤已用模擬 ComfyUI 回應測試。2026-09-06 已在 RTX 3060 上完成真實 ComfyUI 連線與空 checkpoint 清單同步；尚未驗證實際模型載入與生成。

本次環境：ComfyUI 0.34.0（commit `15eb748b3ec5f8a0a2d470b7fb280e2d7579f916`）、Python 3.12.10、PyTorch 2.14.0+cu130、NVIDIA 驅動 616.56。CUDA 矩陣運算及 `pip check` 通過，完整套件快照保存於本地 `runtime/comfyui-installed.txt`。

## 資料與測試

設定保存在 `data/atelier.sqlite3`。停止平台後可備份整個 `data/`；`.venv`、`node_modules`、`dist` 與 `data` 不提交版本控制。

```powershell
.\.venv\Scripts\python.exe -m unittest backend.test_api -v
```

目前僅供本機使用，綁定 127.0.0.1，尚無登入功能。Docker 待平台功能穩定後評估，初期不需要安裝 Docker。後續容器化須分別處理資料持久化、GPU 存取與 ComfyUI 連線。
