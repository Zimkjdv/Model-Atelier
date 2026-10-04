# Model Atelier

個人 AI 圖像創作與實驗工作台。Vue 3 + TypeScript 前端、Python + FastAPI 後端，優先在 RTX 3060 本機開發，再於 RTX 4080 驗證。

## 目前功能

- 系統資訊：NVIDIA GPU、VRAM、RAM、平台資料磁碟、更新時間與失敗狀態。
- ComfyUI 位址保存至 SQLite，獨立呈現引擎的裝置、記憶體與版本資訊；提供手動本機 Python／PyTorch／CUDA 安裝檢查。
- 平台不因無 GPU 而阻止使用。
- 模型庫：同步 ComfyUI checkpoint 名稱、搜尋與狀態篩選、保存版本、架構、檔案大小、SHA256、來源、授權資訊與備註，選擇偏好模型。
- LoRA 模型庫：獨立同步 `LoraLoader` 清單、搜尋及篩選，登記版本、基礎架構、來源、大小、SHA256、授權及備註。資料依引擎網址隔離，失敗時保留成功快照，詳見 [LoRA 說明](docs/models/lora-library.md)。
- LoRA 相容性比較：選擇 checkpoint 後顯示「架構相容，未實測／未驗證／不相容」，依登記架構及清單狀態判定，資料更新時重算；比較操作不改變創作設定。
- LoRA 創作設定：最多四個不同 LoRA 的選擇、啟用／停用、排序與移除，保存模型與 CLIP 強度（−20～20）到草稿。啟用時按順序串接標準 `LoraLoader`，使用 7～11 節點流程；提交前阻擋已知架構不符，檢查引擎即時名稱、節點介面及強度範圍。固定 Animagine 多 LoRA 已實測載入，但畫風品質需依順序與強度確認，見 [有序串接說明](docs/models/multi-lora-workflow.md)；停用保留設定並使用原七節點流程。
- LoRA 生成追溯：任務提交時凍結登記版本、來源、架構、SHA256、授權及兩種強度；作品匯入沿用原快照。作品與已確認失敗任務可完整還原有序 LoRA 設定，保留精確 seed 並提示目前登記差異；舊紀錄版本未知且不回填。
- 有序 LoRA 實測條件：文生圖按 checkpoint 與所有啟用 LoRA 的有序雜湊／架構比對歷史載入紀錄，強度及取樣參數另外比對；保留原品質觀察，不把對比不足的結果標成品質通過。詳見 [有序組合證據](docs/models/ordered-lora-evidence.md)。
- 執行環境追溯：新任務保存提交前的流程規格／JSON hash、平台 Python／依賴版本及原引擎回報的 ComfyUI／Python／PyTorch／指定套件版本，作品直接沿用；查詢失敗與未提供的 CUDA／驅動／Git revision 保持未知。原 UUID 不重新取版本，舊紀錄不回填，見 [版本快照說明](docs/runtime-versions.md)。
- 創作設定轉移：checkpoint／圖生圖／FLUX 可匯出目前參數、讀取 JSON 檔或貼上，先驗證、比較再套用為未保存的新草稿；保留字串 seed 與有序 LoRA，不自動生成。作品可匯出原來源快照與完整 workflow 字串，匯入文件來源標示未核實；權重及素材圖片不包含於檔案，見 [設定匯出／匯入](docs/creation-settings-transfer.md)。
- LCM LoRA 實機條件：Pony 的 768×768 與 Animagine 的 1024×1024 在 RTX 3060 分別驗收；依各組合的 hash、強度及參數比對紀錄，不沿用其他模型或多 LoRA 的結論。Animagine 專用 CLI 為 `python -m scripts.verify_animagine_lora`，見 [驗收紀錄](docs/validation/animagine-lcm-rtx3060.md)。
- 創作工作台：文生圖／單張圖生圖切換、輸入圖片與縮放預覽、denoise 改動幅度、正／負提示詞、尺寸、完整 seed、模型與取樣設定，以及本機草稿保存與重載。
- 參考素材：圖片上傳、預覽、搜尋、命名、用途篩選、封存／還原與草稿關聯；保存正規化與 Pillow 版本，任務／作品引用保護及跨視窗修訂檢查，見 [參考流程說明](docs/models/reference-workflows.md)。
- 生成任務：標準 checkpoint 文生圖與單張圖生圖、任務查詢、重複請求防護及完整工作流程下載。圖生圖凍結素材與前處理快照、驗證原生節點並使用任務獨立圖片目錄；任務與作品頁可追溯來源並載入原設定。RTX 3060／Pony 一般風景已從 API 與介面實測，見 [圖生圖驗收](docs/validation/checkpoint-image2image-rtx3060.md)。
- 執行中停止：針對原引擎中身分相符的單一任務；需已審查的原子取消能力，歷史確認中斷才顯示停止，未知結果只查詢。RTX 3060 已驗證後續任務正常完成，見 [停止實測](docs/validation/running-stop-rtx3060.md)。更新 ComfyUI 後未匹配來源會停用此操作能力，正常生成不受影響。
- 作品庫：匯入已完成任務圖片、本機原圖與縮圖、大圖預覽、完整 workflow／原圖下載與創作設定還原；支援收藏、10,000 字筆記、模型／收藏／狀態組合篩選、筆記搜尋、封存及還原。跨視窗修訂檢查保留衝突中的未保存筆記，見 [作品庫管理](docs/artwork-library.md)。
- 作品比較：最多四張原圖並排，顯示精確 seed、有序 LoRA 及取樣差異；作品預覽可保存四項 1–5 人工評分或留空，修訂衝突保留未保存內容。見 [比較與評分](docs/artwork-comparison.md)。
- 固定測試集與參數比較：四個一般插畫案例；checkpoint 文生圖可比較 Steps／CFG／字串 Seed，預覽最多八次單張生成、完整設定及版本／hash，匯出方案並逐組手動載入。載入不自動生成，見 [比較方案說明](docs/experiment-plans.md)。
- Pony V6 XL：固定作者來源的本地安裝器、大小與 SHA256 驗證，以及 RTX 3060 生成驗收工具。尚未提供訓練或通用模型下載管理。
- Animagine XL 4.0 Opt：固定作者修訂下載、完整大小／SHA256 核對、版本登記與 RTX 3060 的 1024×1024 文生圖驗收完成；可手動確認套用作者預設，紀錄依 hash／架構匹配。見 [模型紀錄](docs/models/animagine-xl-4.0-opt.md)及 [實機條件](docs/validation/animagine-xl-4-0-opt-rtx3060.md)，其他硬體及負載仍待實測。
- FLUX.1 [schnell]：模型庫提供固定來源、四個元件版本／雜湊與唯讀磁碟預檢；CLI：`.\.venv\Scripts\python.exe -m scripts.flux_preflight`。尚未提供下載及 GPU 生成驗收，來源條件、精度與後續驗收見 [FLUX 接入紀錄](docs/models/flux1-schnell.md)。
  模型庫提供依引擎同步與版本／來源登記；創作頁可切換 FLUX 專用表單，保存獨立草稿、匯出精確 JSON、提交與查詢任務、還原作品設定。見 [元件庫](docs/models/flux-components.md)、[FLUX 流程](docs/models/flux-workflow.md)與 [驗收紀錄](docs/validation/flux-integration.md)；GPU 生成仍未驗證。

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

以下是本專案的服務設定與用途；執行狀態於 2026-10-05 有序組合證據、作品評分與比較方案驗收後查核，之後會隨服務啟停改變。專案啟動腳本均綁定本機 `127.0.0.1`。

| Port | 服務／用途 | 使用時機與啟動方式 | 查核狀態 |
| --- | --- | --- | --- |
| `8000` | Model Atelier 主平台：FastAPI API、建置後的 Vue 頁面、參考素材與作品圖片 | 日常使用；根目錄執行 `./start-local.ps1`，瀏覽 `http://127.0.0.1:8000/` | 2026-10-05 未監聽；本輪使用隔離平台 |
| `8188` | ComfyUI：模型及取樣能力清單、生成任務、佇列／歷史、進度與輸出圖片讀取 | 生成、同步選項／模型或匯入圖片時使用；根目錄執行 `./start-comfyui.ps1` | 2026-10-05 畫風／有序多 LoRA 及版本快照實機驗收後停止 |
| `5173`（預設） | Vite 前端開發伺服器：Vue 熱更新；`/api` 代理到 `8000` | 僅前端開發需要；在 `frontend/` 執行 `npm.cmd run dev` | 本次查核未監聽；實際開發網址以 Vite 終端輸出為準 |
| `8001`（臨時） | 隔離測試平台，使用獨立資料庫與測試圖片，可連接真實或模擬引擎 | 作品設定、任務及瀏覽器驗證使用；模擬引擎可共用此埠的測試路徑，非固定服務、非日常依賴 | 2026-10-05 有序組合證據、作品評分及比較方案驗收後停止；隔離證據保留在 runtime |

日常使用只需啟動 `8000` 與 `8188`。介面、API、作品預覽共用 `8000`；已匯入的作品即使 ComfyUI 關閉仍可瀏覽。SQLite 是本機檔案，不占用網路連接埠；作品庫也不需要額外服務埠。

2026-10-05 最新三項驗收：382 項後端測試（381 通過、1 項既有 Windows 權限跳過）、Vue 型別／建置及桌面瀏覽器通過；8000／8001／8188／5173 均未監聽。本輪使用既有四個真實 GPU 任務／作品，沒有新增生成；兩份 checkpoint 草稿、一份 FLUX 草稿、設定轉移及比較方案證據保留在 `runtime/style-live-data-20261005` 與 `runtime/`。隔離多 LoRA 圖人工視覺風格評分為 1/5，仍保留品質不足的觀察。較早 Animagine 四個任務／作品保留在 `runtime/animagine-live-data-20261005`；Pony 圖生圖證據保留在 `runtime/image-live-data-20261005`。正式資料維持原 5 個任務、3 件作品與 0 個草稿；模型庫已登記驗檔的 Animagine `4.0 Opt` 與公開畫風 LoRA，正式偏好模型仍未選定。固定測試集跨模型 GPU 品質評測與 RTX 4080 仍待驗收。先前的指定任務停止驗收見 [驗收紀錄](docs/validation/running-stop-rtx3060.md)。

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

## 執行環境診斷

系統資訊頁分開顯示三種來源：平台主機的 RAM／資料磁碟與 nvidia-smi 資訊、目前選定 ComfyUI 的 `/system_stats`，以及本專案 ComfyUI Python 的手動檢查。每份回報附來源、範圍與查詢時間；引擎離線或回報無效時不沿用舊裝置，也不從平台主機補值。查詢期間更換引擎會讓該份診斷失效，介面提示重新確認設定並保留輸入。

引擎回報包括 ComfyUI、Python、PyTorch、裝置索引、RAM 與各裝置記憶體的總量／已用／可用量。缺少、非有限數值、負容量或不合理比例顯示未知。ComfyUI 未提供可靠的 CUDA 可用性與驅動欄位時保持未知，不由 PyTorch 的 `+cu` 後綴推定；其可用 VRAM 可能包含可回收快取，與 nvidia-smi 數值不同，不能保證任一模型可執行。裝置清單也不能證明每個任務實際使用哪張 GPU。CPU 裝置使用記憶體標籤，避免將 RAM 當成 GPU 顯存。

按下「檢查本機 ComfyUI 安裝」才會使用 `runtime/ComfyUI/.venv` 的 Python 執行固定診斷腳本，讀取 Python、PyTorch、CUDA 可用性、CUDA 裝置屬性及本機 nvidia-smi 驅動版本。不啟動引擎、不載入模型、不配置張量或生成圖片，20 秒逾時會停止子程序。PyTorch CUDA 建置版本來自 `torch.version.cuda`，與本機 CUDA Toolkit 版本及完整模型相容性驗證不同；CUDA 不可用與資料未知分別呈現。

`GET /api/engine` 保留來源引擎網址及相容版本資訊，並提供結構化 `diagnostics`。`GET /api/local-environment` 只讀取本機檢查快照；`POST /api/local-environment` 明確觸發檢查，不接受自訂執行參數，同時執行的第二個檢查回傳 409。本機快照暫存在平台程序記憶體，平台重啟後需重新檢查；15 秒自動更新不重跑本機檢查。即使設定為遠端引擎，本機檢查仍只代表本專案安裝環境。

2026-10-03：190 項後端測試通過（1 項既有 Windows 權限跳過）、Vue 型別檢查／建置與唯讀審查通過。RTX 3060 真實驗證本機 Python 3.12.10、PyTorch 2.14.0+cu130、CUDA 建置版本 13.0／可用及驅動 616.56；ComfyUI 0.34.0 的診斷仍保留未提供的 CUDA／驅動欄位為未知。隔離 API／瀏覽器驗證多 GPU、異常容量、CPU 標籤、離線清除與切換引擎競態；本輪未新增生成任務，原模型、兩個任務與兩件作品不變。測試服務及隔離資料已清理，RTX 4080 仍待實機驗證。

## 使用既有 checkpoint 目錄

在設定頁的「本機模型目錄」登記最多八個既有的絕對目錄，每行一個，例如 `D:\AI\checkpoints`。目錄必須存在、可讀且位於本機磁碟；平台只保存目錄設定，不上傳、搬移、複製或刪除模型。預設 `runtime/ComfyUI/models/checkpoints` 仍保留，不須重複登記。

此設定只供專案的 `start-comfyui.ps1` 啟動本機受管理 ComfyUI 使用，與設定頁選擇的遠端引擎分開。保存後先在原 ComfyUI 終端按 Ctrl+C，重新執行 `./start-comfyui.ps1`，再到模型庫同步。未重啟前不能當作引擎已讀到新目錄；只登記路徑也不表示檔案是有效模型或已通過生成驗收。

啟動腳本以獨立匯出工具，從 SQLite 產生 `runtime/comfy-extra-model-paths.json`，再透過 ComfyUI 官方 `--extra-model-paths-config` 參數讀取。JSON 採相容 YAML 的格式，追加 checkpoint 搜尋目錄，不覆寫 ComfyUI 原本的 `extra_model_paths.yaml`。設定損壞、目錄遺失或匯出失敗會停止啟動並說明原因，避免繼續使用舊匯出檔。移除登記後須再重啟，不會刪除該目錄或模型檔。

搜尋順序保留 ComfyUI 原目錄，再依登記順序追加。不同目錄內相同相對檔名可能被前面的檔案遮蔽；請避免重名，模型清單中的檔名不能單獨證明實際載入來源。平台不遞迴掃描或雜湊全部外部權重，模型版本及來源仍須正確登記。舊目錄目前不可讀或容量未知時，介面保留登記並提示原因，不以零容量代替未知。

`GET /api/local-model-paths` 讀取本機目錄登記與狀態；`PUT /api/local-model-paths` 使用修訂號保存，衝突回傳 409，不覆寫其他視窗的修改。平台及 ComfyUI 重啟後仍從本機 `data/atelier.sqlite3` 讀取設定；備份 `data/` 會保存登記，外部模型檔案需另行備份。

2026-10-03：170 項後端測試通過（1 項既有 Windows 權限跳過），Vue 型別檢查／建置通過。真實 ComfyUI 驗證含空白的額外目錄、原 Pony 清單保留，以及移除登記後重啟恢復原清單；77 bytes 的測試檔只驗證檔名列舉，未載入權重或新增生成任務。瀏覽器驗證修訂衝突、輸入保留與其他引擎的範圍提示；測試檔已清理，服務已停止。

## 固定來源模型安裝與磁碟預檢

公開 LCM SDXL LoRA 亦可用 `scripts.install_model lcm-lora-sdxl` 安裝至 `runtime/ComfyUI/models/loras/`。Pony＋LCM 單一 LoRA 在 RTX 3060 完成生成及重啟後離線保存驗收；固定來源、參數、版本、耗時與可重跑指令見 [驗收紀錄](docs/validation/pony-lcm-rtx3060.md)。此實測驗證流程，不代表畫師風格或其他 LoRA 效果通過。

公開黑白畫風 LoRA 安裝 ID 為 `ikea-instructions-lora-sdxl`；授權條款未知，版本標示固定 revision。`python -m scripts.verify_multi_lora --profile baseline|style|multi` 可逐次驗證無 LoRA、單一畫風及 LCM→畫風有序組合；RTX 3060 已完成三組生成與離線保存，但 4 步多項結果偏淡，不作為品質預設。來源、命令與限制見 [畫風／多 LoRA 紀錄](docs/validation/animagine-multi-lora-rtx3060.md)。

先用唯讀檢查確認所選 manifest、剩餘下載量、安裝鎖及磁碟容量：

```powershell
.\.venv\Scripts\python.exe -m scripts.install_model animagine-xl-4.0-opt --check
.\.venv\Scripts\python.exe -m scripts.install_model animagine-xl-4.0-opt
```

`--check` 不連網、不建目錄、不改寫檔案；可安裝回傳 0，空間不足或有安裝鎖回傳 2。正式安裝重用 Pony 安裝器的續傳、完整 SHA256、同目錄原子發布與來源紀錄。只接受程式核准的固定作者修訂；不接受任意網址或輸出路徑。已有正式檔仍須在安裝時完整驗證，預檢不是檔案或 GPU 驗收。

Animagine 權重約 6.46 GiB，加上 2 GiB 預留需約 8.46 GiB。2026-10-05 重新預檢約有 18 GiB，已完成下載、雜湊驗證及 RTX 3060 生成驗收；程式沒有刪除其他模型或使用者資料。專用驗收 CLI 為 `python -m scripts.verify_animagine_generation`，新生成須使用新報告路徑，原報告加 `--verify-report` 只讀验证。Pony 亦可透過 `scripts.install_model pony-v6-xl` 安裝，原指令仍保留。

## Pony V6 XL 本地安裝與驗收

本專案提供固定來源的安裝指令，將作者 [AstraliteHeart/pony-diffusion-v6](https://huggingface.co/AstraliteHeart/pony-diffusion-v6) 的權重保存為 `runtime/ComfyUI/models/checkpoints/pony-v6-xl.safetensors`。來源固定在 commit `5ec9c05863255568f1b59753e3838107befaa712`，檔案為 6,938,041,050 bytes，SHA256 為 `67ab2fd8ec439a89b3fedb15cc65f54336af163c7eb5e4f2acc98f090a29b0b3`；詳見 [來源 manifest](models/pony-v6-xl.json)。該修訂模型卡登記 `creativeml-openrail-m`，未附授權全文，本次僅記錄來源標記，完整條款尚未核對。

```powershell
.\.venv\Scripts\python.exe -m scripts.install_pony
```

安裝器使用同目錄 `.part` 暫存檔，支援續傳，不建立第二份下載快取。完整大小與 SHA256 通過後才發布正式 checkpoint，並保存 `.provenance.json`。預設最多嘗試 3 次，需保留至少 2 GiB 可用空間。已存在且符合 hash 的正式檔直接沿用；不同正式檔拒絕覆蓋。`--restart` 只清空此模型的下載暫存檔，不覆蓋正式模型。安裝中止後可重跑續傳；若 `.install.lock` 殘留，先確認沒有安裝程序仍在執行，再移除該模型的鎖檔。

啟動平台與 ComfyUI，至模型庫同步清單、選擇 `pony-v6-xl.safetensors` 後即可生成。權重與本機驗收報告都在 `runtime/`，不提交 Git。

一般風景的可重跑驗收：

```powershell
.\.venv\Scripts\python.exe scripts/verify_local_generation.py --platform http://127.0.0.1:8000 --expected-engine http://127.0.0.1:8188 --checkpoint pony-v6-xl.safetensors --report runtime/pony-v6-xl-acceptance.json
# 重啟平台後，只讀原作品與完整參數；不重新生成。
.\.venv\Scripts\python.exe scripts/verify_local_generation.py --platform http://127.0.0.1:8000 --expected-engine http://127.0.0.1:8188 --checkpoint pony-v6-xl.safetensors --report runtime/pony-v6-xl-acceptance.json --verify-report
```

驗收只提交一個 UUID 任務，確認歷史成功後匯入作品，核對圖片、完整 seed、工作流程及設定還原。逾時或不明結果保留原任務 ID，不自動再次生成。耗時是提交到確認歷史的牆鐘時間，包含載入與查詢；VRAM 是定期取樣的觀察值，不等同精確峰值。768×768、單張、20 steps 只是本次測試設定，不代表所有解析度或硬體均已通過。

2026-10-02 RTX 3060 實機通過生成、作品匯入、瀏覽器節點進度與設定載入，以及重啟後離線讀取；設定與測量範圍見 [驗收紀錄](docs/validation/pony-v6-xl-rtx3060.md)。重跑新的生成需明確指定新的報告檔名；既有報告使用 `--verify-report`，避免意外重複生成。

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

「設為偏好」只保存選擇，不會載入 GPU。「編輯資料」可登記版本、架構、檔案大小（bytes）、完整 SHA256、來源、授權名稱／網址與備註；未填資料顯示「未知」。這些都是使用者登記資訊，平台不會據此宣稱已檢查實際檔案、授權或架構相容性，也不依檔名推測資料。

架構選項為未知、SD 1.x、SDXL、SD 3.x、FLUX、其他。檔案大小需為正的安全整數（上限 `9007199254740991`），空值表示未知；SHA256 需為完整 64 位十六進位字元，保存為小寫。來源與授權網址只接受不含帳密、查詢及片段的 HTTP／HTTPS 位址。Pony 安裝器的 `.provenance.json` 提供已驗證下載的數值，可據此在模型庫登記；模型庫本身仍標示為登記資料。

`PUT /api/models/metadata` 新增 `architecture`、`size_bytes`、`sha256`、`license_name`、`license_url`。未送出的欄位保留既有值，空字串／大小 `null` 可清空；`metadata_updated_at` 由伺服器產生。資料按引擎隔離，同步或同步失敗保留 metadata，SQLite 交易避免同期操作覆寫資料。

新任務在提交前保存 `model_metadata` 快照及捕獲時間，作品從該任務複製；之後修改模型庫、重新匯入或恢復原 request ID 都不更新舊快照。快照來源為 `user_registered`，不代表驗證過實際載入的權重。舊任務／作品未保存快照時保持未知，不用目前模型庫回填。作品預覽的「提交時模型資料」可查看此紀錄，與作品原圖自己的 SHA256 分開。

2026-10-02：129 項後端測試（1 項既有 Windows symlink 權限跳過）與 Vue 型別檢查／建置通過。瀏覽器實際登記 Pony 大小、架構與完整 hash，確認過大整數被拒絕；隔離引擎驗證提交後修改登記版本／hash，再匯入仍顯示原值，原 ID 恢復及重複匯入不改寫快照且上游提交仍只有一次。既有 GPU 作品未保存新快照，確認保持未知。這次快照驗證沒有新增 GPU 推論。

模型庫另外顯示目前連接的 ComfyUI `/system_stats` 回報版本及官方 GitHub 專案連結；離線或無版本資料時顯示「未知」，不以 GitHub 最新版代替正在執行的版本。

模型庫離線、資料合併、主機隔離與驗證錯誤已用模擬 ComfyUI 回應測試。2026-09-06 完成真實 ComfyUI 連線與空 checkpoint 清單同步；2026-10-02 完成 Pony V6 XL 載入、GPU 生成及作品保存驗收。其他模型與 RTX 4080 尚待實測。

本次環境：ComfyUI 0.34.0（commit `15eb748b3ec5f8a0a2d470b7fb280e2d7579f916`）、Python 3.12.10、PyTorch 2.14.0+cu130、NVIDIA 驅動 616.56。CUDA 矩陣運算及 `pip check` 通過，完整套件快照保存於本地 `runtime/comfyui-installed.txt`。

## 資料與測試

設定保存在 `data/atelier.sqlite3`。停止平台後可備份整個 `data/`；`.venv`、`node_modules`、`dist` 與 `data` 不提交版本控制。

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s backend -v
```

目前僅供本機使用，綁定 127.0.0.1，尚無登入功能。Docker 待平台功能穩定後評估，初期不需要安裝 Docker。後續容器化須分別處理資料持久化、GPU 存取與 ComfyUI 連線。


## ComfyUI 任務提交

創作頁的「生成圖片」會提交目前表單，保存草稿仍是獨立操作。標準 checkpoint 文生圖預設 20 steps、Euler / normal、CFG 7、denoise 1、空白負面提示詞；正／負提示詞與取樣參數可編輯、保存並提交，batch 固定為 1。平台 Steps 範圍 1–150、CFG 範圍 0–30、denoise 範圍 0–1；生成使用平台與引擎範圍的交集，取樣器及 scheduler 從 ComfyUI 同步。可選最多四個有序 LoRA；參考圖輸入尚未接入，選有參考素材時明確拒絕生成。FLUX.1 [schnell] 使用獨立表單與提交流程（詳見下方）。尺寸通過驗證不代表顯存一定足夠。

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

## 模型預設與架構檢查

選擇 checkpoint 後，創作頁顯示登記架構與可套用的起始參數。切換模型、載入草稿或作品都保留原值；按「套用模型預設」查看差異，再確認才修改寬度、高度、steps、CFG、sampler、scheduler、denoise。提示詞、負面提示詞、seed、草稿名稱與參考素材不受影響。套用預設不會保存草稿或提交生成。

| 預設 | 匹配方式 | 起始參數 | 驗證範圍 |
| --- | --- | --- | --- |
| Pony V6 XL | 登記為 SDXL，且完整 SHA256 與本專案固定 manifest 相同 | 768×768、20 steps、CFG 5.5、DPM++ 2M / Karras、denoise 1 | 本專案 RTX 3060 單張風景驗收；不代表目前登記的檔案已自動驗證 |
| 一般 SDXL | 登記為 SDXL，其餘 hash | 768×768、20 steps、CFG 7、Euler / normal、denoise 1 | 起始值，尚未逐模型驗證 |
| 一般 SD 1.x | 登記為 SD 1.x | 512×512、20 steps、CFG 7、Euler / normal、denoise 1 | 起始值，尚未實測 |
| 未知／其他未支援架構 | 不提供可套用預設 | 原參數保留 | 未知架構仍可嘗試標準流程；已登記 FLUX、SD 3.x 或其他架構需專用流程，拒絕新的標準提交 |

不根據模型檔名或版本文字猜測 Pony；只有登記架構與完整 hash 符合才提供該預設。預設來源與提示詞參考可收合查看，提示詞不會自動插入。改選模型、重載草稿或更新資料會清除尚未確認的預設，避免把先前選項套到新內容。

`GET /api/models/profile?engine_url=…&name=…` 只讀平台模型資料，回傳架構、相容提示與預設，不讀模型檔、不連接 ComfyUI 或載入 GPU。原引擎不符回傳 409，模型未登記回傳 404。介面查詢中或查詢失敗時保留參數，暫停新的生成。

新 `POST /api/generate` 與直接 `POST /api/jobs` 都會查登記架構；已知不適用的架構回傳 422、保存失敗任務且不發送 `/prompt`。引擎能力查詢後再檢查一次，避免驗證期間改成未支援架構仍被送出。未知、SD 1.x 與 SDXL 都使用目前標準流程，不因補齊登記資訊就自動改參數或封鎖；實際模型載入仍由 ComfyUI 驗證。原 request ID 恢復返回舊紀錄，不重新套預設或更新模型快照。

2026-10-02：140 項後端測試通過（1 項既有 Windows 符號連結權限跳過），Vue 型別檢查／建置通過。瀏覽器驗證取消／確認預設、切換模型清除待確認選項、未知／未支援架構提示、同模型草稿與作品載入保留原值。隔離 API 確認兩個提交入口均保存未支援架構的失敗任務且不送 prompt；自訂 CFG 5.55、denoise 0.45 與完整 seed `18446744073709551615` 原樣送出，不套預設。修改架構後原 ID 仍回舊任務，不重新生成或改寫作品快照。此流程驗收使用模擬引擎；真實 Pony 的 RTX 3060 風景驗收見前述紀錄，RTX 4080 仍待測。驗收服務已停止、隔離資料已清理，8000／8188／5173／8001 均未監聽。

## 即時任務進度

`GET /api/jobs/{id}/events` 以 SSE 傳送 `job` 摘要與 `connection` 連線狀態。平台向任務原 ComfyUI 引擎開啟 WebSocket，使用提交時的 client ID；同一任務的多個頁面共用上游連線，並以 SQLite 監聽租約避免多個平台程序搶用同一 ID。每個任務最多 8 個訂閱、每個程序最多 16 個監聽任務，超過回傳 429。事件只接受原 prompt ID 與工作流程中的節點，忽略預覽二進位資料、全域訊息與其他任務；不傳送完整工作流程或 64 位元 seed。

創作頁顯示目前節點、取樣數與節點百分比。100% 只表示該節點進度，完成或失敗仍以引擎歷史查詢確認。進度每秒最多寫入一次，保留最後樣本及更新時間。斷線後重連原引擎並查詢原任務；重連次數與低頻查詢有上限，失敗後可按「更新任務狀態」或「重新連線進度」。所有恢復操作均不重新提交工作流程。

前端即時監聽最近 4 個未完成任務，其餘或失去連線的任務每 15 秒查詢。切換離開創作頁、隱藏分頁或關閉頁面會清理監聽，返回後重新讀取狀態；最後訂閱離開會關閉上游 WebSocket。舊進度不當作新進度，取消確認中的狀態及已結束任務不被進度事件覆寫。

`start-local.ps1` 設定 5 秒優雅關閉等待上限，避免長時間開著進度頁時 Ctrl+C 無限等待。這只關閉平台連線，生成仍由 ComfyUI 執行。新增 `websockets` 依賴；既有環境更新後請執行 `.\.venv\Scripts\python.exe -m pip install -r requirements.lock.txt`。

2026-10-02：69 項後端測試、前端型別檢查／建置與依賴檢查通過。隔離瀏覽器驗證節點進度、上游斷線恢復、歷史確認完成及切換頁面清理；沒有重新提交任務。這些使用模擬引擎事件，實際 GPU 出圖仍待 checkpoint。

## 任務失敗診斷與設定恢復

任務會保存安全的 `failure_info`，區分引擎離線、未安裝 checkpoint、所選模型遺失、架構不支援、提交驗證失敗、模型載入失敗、CUDA 顯存不足與其他執行錯誤。執行錯誤只依原任務歷史及工作流程中的節點分類；資料不足時顯示一般錯誤，不推測顯存不足。介面顯示處理建議，節點與例外類型可收合查看；完整上游錯誤、歷史與工作流程仍保存在任務 JSON，原始 traceback 與提示詞不直接當作介面錯誤訊息。

只有已確認失敗的任務提供「載入原設定並調整」。`GET /api/jobs/{id}/creation-settings` 從本機標準工作流程完整還原原引擎、checkpoint、提示詞、尺寸、精確 seed 與取樣值，保留當時登記的模型版本及資料。讀取與載入不連接引擎、不生成、不修改舊任務；未保存內容仍須先選擇保留或捨棄。非失敗任務回傳 409，不支援完整還原的流程回傳 422，可下載原 JSON 使用。

顯存不足時可自行降低尺寸等負載，平台不自動修改模型、尺寸、精度或 seed。調整後按「生成圖片」才建立新的請求；提交或取消結果尚未確認時，應先查詢或恢復原請求，不能用新的任務取代結果確認。舊任務沒有診斷欄位時繼續顯示原錯誤，不回填猜測結果。

2026-10-02：153 項後端測試通過（1 項既有 Windows 符號連結權限跳過），Vue 型別檢查／建置通過。隔離 API 與瀏覽器驗證 CUDA OOM、載入節點與一般失敗的安全說明、完整 seed／原取樣值／模型版本保留、未保存內容確認，以及手動改尺寸後只建立一個新請求，舊任務不變。錯誤來自模擬引擎，未刻意耗盡真實 GPU 顯存；測試服務與資料已清理。

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

## 條件化流程驗證紀錄

模型庫及創作頁可查看 `GET /api/models/validation` 的唯讀驗證紀錄。`models/validation-records.json` 保存經審閱的實測證據，以登記 SHA256、架構及流程比對；不是即時檔案驗證。首筆為 Pony V6 XL／RTX 3060 的既有實測，包含環境版本、精度、卸載方式、參數與耗時。冷啟動牆鐘與暖機引擎耗時不可直接比較；設備顯存取樣包含其他程序，並非最低需求。其他模型、參數、RTX 4080 與訓練仍需另行實測。

## 生成資源提示

創作頁的「查看資源與驗證提示」呼叫唯讀 `POST /api/generation-advice`：比對選取模型的實測參數，取得所選 ComfyUI 的裝置／可用顯存。沒有可靠需求估計時返回未知，離線仍提供未驗證提示；不啟動 GPU 任務、不修改草稿、不因 VRAM 或顯卡型號封鎖提交。表單變更即清除舊提示，查詢期間模型或引擎變更會拒絕過期結果。正式提交仍沿用原有的模型／節點／引擎檢查。

## 本機目錄與磁碟容量

系統資訊的「目錄與磁碟容量」透過唯讀 `GET /api/storage` 顯示平台資料、參考素材、作品庫、受管理 ComfyUI 的 checkpoint／output，以及登記的額外 checkpoint 目錄。Windows 以磁碟區 GUID、其他系統以 filesystem device ID 去重，同一磁碟區容量僅查詢與加總一次。容量是整個磁碟區的總量／可用空間，並非資料夾使用量；不掃描權重、不建立目錄、不移動檔案。不存在、不可讀或無法辨識的容量標示未知，總計標示部分資料。

此清單只涵蓋平台及受管理本機路徑，不推定遠端引擎、自訂輸出參數或手動 YAML 的儲存位置。按「更新磁碟容量」取得新快照。

## 送出前必要節點檢查

生成提交除了即時 checkpoint／KSampler 驗證，也會查詢本次流程所使用的其他標準節點定義。缺少節點、查詢失敗或定義格式無效時，保留失敗任務及原因，不呼叫引擎 `/prompt`。相同節點只查詢一次，各節點並行查詢；恢復既有 request ID 不重新檢查、不重送。

此檢查確認節點已登記，不能證明模型一定能載入或裝置一定能執行；未知裝置不以 GPU 型號或空清單推定不可用。

## 創作頁顯示偏好

尺寸、Steps、CFG 直接顯示；Seed、取樣器、排程與 Denoise 放在進階設定。進階區及參考素材的展開狀態保存於本瀏覽器 `atelier-studio-display-v1`，重新載入仍保留。此資料只有顯示偏好，生成參數仍由草稿保存；瀏覽器儲存不可用時提示本次有效，平台草稿功能不受影響。

## 窄視窗與鍵盤操作

創作頁可用「收合創作設定」將空間留給任務與狀態，展開後保留未保存表單；窄視窗保留設定切換按鈕。主要導覽提供文字名稱、滑鼠提示與目前頁面標記；鍵盤可用「跳至主要內容」直接聚焦主區域，各種控制元件提供一致的焦點外框。已驗證 680px／390px 視窗無橫向溢出、Enter 展開／收合及內容保留。

介面共用色彩與狀態規範見 [docs/ui-guidelines.md](docs/ui-guidelines.md)，色彩集中於 frontend/src/theme.css。

模型／作品／素材搜尋結果提供讀屏狀態播報，卡片操作可辨識對應名稱。輸入限制與欄位關聯；作品預覽可用 Enter 開啟、Escape 關閉並返回原操作焦點。這些為本機操作驗證，非完整無障礙認證。

## 流程能力與創作欄位

`GET /api/models/profile` 提供 workflow 描述（流程 ID、欄位、固定單張、參考圖／LoRA 能力）。目前只接受標準 checkpoint 文生圖描述；格式不完整或未知流程不啟用表單。SD 1.x／SDXL 及未知架構可編輯標準欄位，未知架構仍由引擎驗證；已知未支援架構顯示原因並保留原始參數，仍可保存草稿，切回支援模型可繼續編輯。尚未選模型時可先準備草稿。

標準 checkpoint 流程描述包含 LoRA 能力及 `max_loras: 4`；未接入的參考圖流程仍不可提交。FLUX.1 [schnell] 另有 `/api/flux/workflow` 描述，不沿用 checkpoint 表單；FLUX LoRA 仍不可提交。

## 單一 LoRA 組合實測紀錄

模型庫選擇「比較用 checkpoint」後，可在 LoRA 卡片按「查看組合實測」。創作頁啟用 LoRA 後會查詢同一組合，並比對兩種強度與目前解析度、Steps、CFG、sampler、scheduler、denoise 及固定 batch 1；參數變更會清除過期回覆。資源提示使用同一比對，不沿用基礎模型七節點的紀錄。基礎預設仍需確認套用，不自動改成 LCM 參數。

`POST /api/loras/validation` 是唯讀查詢，輸入 `engine_url`、`checkpoint`、`lora`（名稱、啟用及兩種強度）及選填 `settings`（上述取樣參數、`batch_size: 1`）。以兩份登記 SHA256 與架構比對 `models/lora-validation-records.json`，不讀取權重、不連接引擎、不查 GPU 或改資料庫。回傳 `recorded` 只代表有該組合紀錄；`matching_parameter_records` 才表示強度和取樣設定匹配，仍不保證目前檔案、提示詞、硬體或本次生成。清單失效、未知 hash、其他組合及訓練均不視為通過；引擎／登記在查詢期間改變回傳 409。

首筆紀錄為 2026-10-04 Pony＋LCM SDXL／RTX 3060 的單張風景驗收，包含完整環境、兩種冷啟動耗時、整卡顯存取樣及明確未量測的暖機值。詳見 [實機紀錄](docs/validation/pony-lcm-rtx3060.md)。提交時的歷史提示保留原文並標明時間範圍，不用後續紀錄改寫原任務。
