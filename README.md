# Model Atelier

個人 AI 圖像創作與實驗工作台。Vue 3 + TypeScript 前端、Python + FastAPI 後端，優先在 RTX 3060 本機開發，再於 RTX 4080 驗證。

## 目前功能

- 系統資訊：NVIDIA GPU、VRAM、RAM、平台資料磁碟、更新時間與失敗狀態。
- ComfyUI 位址保存至 SQLite，檢查連線並獨立呈現引擎回報的裝置資訊。
- 平台不因無 GPU 而阻止使用。
- 模型庫：同步 ComfyUI checkpoint 名稱、搜尋與狀態篩選、保存來源與備註、選擇偏好模型。
- 創作工作台及作品庫仍為待開發頁面；尚未提供生成、訓練或模型下載。

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

ComfyUI 需另外安裝並啟動，使用自己的 Python 環境，不與平台 `.venv` 混用。預設連接 `http://127.0.0.1:8188`，可在設定頁修改。未安裝或未啟動時，平台仍可使用系統資訊功能。

平台主機的硬體取自 psutil / nvidia-smi，模型執行環境取自 ComfyUI `/system_stats`。引擎沒有提供的遠端磁碟資料顯示無法取得，不以本機磁碟代替。

## 模型庫

在模型庫按「同步模型清單」，平台讀取 ComfyUI `/object_info/CheckpointLoaderSimple` 的 checkpoint 選項。此版本只涵蓋這個載入節點，不代表 ComfyUI 所有模型類型；不複製或下載模型檔。

每個引擎位址各自保存快照、來源網址、備註與偏好模型。離線或回應格式錯誤時保留上次資料；模型從清單移除後保留其備註並標示「最近清單未列出」。清單只代表同步當下引擎登記的名稱，不代表已驗證架構、授權或能成功生成。

「設為偏好」只保存選擇，不會載入 GPU。來源與備註可手動整理；檔案雜湊、大小、自動架構辨識及生成流程尚未實作。

模型庫離線、資料合併、主機隔離與驗證錯誤已用模擬 ComfyUI 回應測試；真實模型同步仍需啟動 ComfyUI 後驗證。

## 資料與測試

設定保存在 `data/atelier.sqlite3`。停止平台後可備份整個 `data/`；`.venv`、`node_modules`、`dist` 與 `data` 不提交版本控制。

```powershell
.\.venv\Scripts\python.exe -m unittest backend.test_api -v
```

目前僅供本機使用，綁定 127.0.0.1，尚無登入功能。Docker 待平台功能穩定後評估，初期不需要安裝 Docker。後續容器化須分別處理資料持久化、GPU 存取與 ComfyUI 連線。
