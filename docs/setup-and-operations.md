# 安裝與日常操作

適用於目前 Windows 本機流程，命令從專案根目錄執行。平台與 ComfyUI 使用兩份獨立 Python 環境；硬體與來源條件依對應驗收。

## 平台

依 [README 快速開始](../README.md#快速開始) 建立 `.venv`、安裝 `requirements.lock.txt`，frontend 使用 `npm.cmd ci`、`npm.cmd run build`。`start-local.ps1` 先確認 Python 與前端 dist 存在，再以 localhost:8000 啟動，優雅關閉等待上限 5 秒。PowerShell 不允許腳本時可執行相同命令：

```powershell
.\.venv\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --no-proxy-headers --timeout-graceful-shutdown 5
```

平台停止不會停止引擎的工作；重啟後查詢原 UUID。新安裝不附 checkpoint，無引擎時仍可保存草稿及查看已匯入作品。

使用者已選擇同一台電腦使用；D01 的來源 IP／Host／Origin 保護與主機角色說明見 [部署與存取](deployment.md)。更新後需重啟平台；目前沒有遠端帳號登入，不要將平台埠開放區網。

另可選用 [Docker Desktop／WSL2 本機部署](docker.md)：容器平台預設 8001、原生 ComfyUI 8188、獨立 DATA 與鎖卷；不取代以下原生啟動步驟。容器的 Linux／RAM／磁碟資訊及 Windows 路徑、備份、訓練限制須分開閱讀。

## 獨立 ComfyUI

目錄為 `runtime/ComfyUI`，Python 為其內的 `.venv`。runtime 不在 Git；需自行安裝或沿用既有環境。以下是本專案已驗證來源與 cu130 配置的重建步驟，**不是所有顯卡或驅動的通用安裝建議**：

```powershell
git clone https://github.com/Comfy-Org/ComfyUI.git runtime/ComfyUI
git -C runtime/ComfyUI checkout 15eb748b3ec5f8a0a2d470b7fb280e2d7579f916
python -m venv runtime/ComfyUI/.venv
.\runtime\ComfyUI\.venv\Scripts\python.exe -m pip install --no-cache-dir torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu130
.\runtime\ComfyUI\.venv\Scripts\python.exe -m pip install --no-cache-dir -r runtime/ComfyUI/requirements.txt
.\start-comfyui.ps1
```

ComfyUI 依賴未完整 lock，重建可能解析到不同套件，需重新核對環境。硬體條件見 [Pony 實測](validation/pony-v6-xl-rtx3060.md)。啟動腳本綁定 localhost:8188，停用自動開頁及 API 節點，匯出模型目錄、核對條件化停止能力並安裝 [E01 唯讀裝置回報](execution-device.md)。升級後停止能力不匹配時停用，正常生成仍可用。

模型可放在 `runtime/ComfyUI/models/checkpoints/`，或登記額外目錄。固定來源工具先唯讀預檢，再明確下載：

```powershell
.\.venv\Scripts\python.exe -m scripts.install_model animagine-xl-4.0-opt --check
.\.venv\Scripts\python.exe -m scripts.install_model animagine-xl-4.0-opt
```

`--check` 不連網、不寫入，不等於已安裝或 GPU 驗收；正式安裝驗證大小／SHA256。Pony 固定 Hugging Face 修訂僅附授權標記，相同 SHA256 的 Civitai 發布頁卻列出不同條款及變現推論限制，`terms_verified` 維持 false，見 [M01 查核與限制](models/pony-v6-xl-license.md)。FLUX 預檢不表示取得權重。來源與操作見 [模型文件](index.md#模型與執行環境)。

## 第一次使用與恢復

設定引擎網址 → 模型庫同步 → 工作台選模型／參數 → 明確生成 → 完成後作品庫明確匯入。保存草稿不提交，載入設定不生成，匯入只讀任務原引擎輸出。

離線先確認原網址與服務；遺失提交回應應查詢／恢復原 ID，不能用新 ID 重送。確認失敗後才調整設定建立新任務。引擎裝置未知不推定無 GPU；缺模型／節點或不相容架構仍阻擋提交。變更設定頁不會把舊任務轉到新引擎。

取消佇列與停止執行是不同操作；停止需匹配的原子能力與歷史確認，不使用會影響其他任務的全域 interrupt。狀態見 [架構](architecture.md#任務與原引擎)。

## 額外 checkpoint 目錄

設定頁可登記最多八個既有可讀本機絕對目錄，每行一個。預設 checkpoint 目錄保留；不搬移、上傳或刪除權重。保存後：原 ComfyUI Ctrl+C → 重跑 `start-comfyui.ps1` → 同步模型庫。

匯出 `runtime/comfy-extra-model-paths.json`，用 `--extra-model-paths-config` 追加，不改原 YAML；損壞設定或遺失目錄停止啟動。同相對檔名可能被較早目錄遮蔽，檔名不證明實際權重。此設定只代表受管理本機引擎，不代表遠端引擎；版本與 hash 需正確登記。

GET／PUT `/api/local-model-paths` 使用修訂號保護。data 備份保存路徑登記，外部權重另備份。

## 備份與還原

1. 停止平台，避免 SQLite 與圖片在備份時變動；如需保存引擎輸出，先等待工作結束並停止引擎。
2. 保存完整 data：`atelier.sqlite3`、`assets/`、`artworks/`、`job_inputs/`、`control_edges/` 等現存內容一起保存；設定 JSON／比較報告不能替代備份。
3. 權重、外部模型、ComfyUI input／output，以及需要的隔離 runtime 報告／整份 DATA 另外保存，Git 不包含這些原始檔。
4. 還原前保持平台停止，先保存目前 data 副本，再還原完整備份。重啟後核對作品數、原圖與設定；缺檔從相符備份恢復，不重新生成歷史圖。

停機 check／backup／verify／restore 命令、hash manifest、外置 DB 及新目錄切換見 [完整備份工具](data-backup.md)。目的地必須為新目錄，不自動排程、覆寫、修復或清理。沒有一般作品永久刪除，封存不釋放檔案空間。設定還原不保證跨環境相同像素。

## 部署至另一台 Windows主機

例如從 RTX 3060 搬到 RTX 4080，建議「Git clone 程式＋搬移已下載的權重／資料＋重建執行環境」。大檔不在 Git，毋須重新從網路下載全部權重；但整包複製不等於可直接啟動。[Python 官方 venv 說明](https://docs.python.org/3/library/venv.html#how-venvs-work)指出虛擬環境包含絕對路徑，搬移後應重建。

1. 舊機先完成生成／訓練、停止平台及相關寫入者，依 [完整備份工具](data-backup.md)備份與驗證整份 DATA。需要 ComfyUI input／output、完整訓練 run／bundle 或外部作者圖片時另存；不要只複製 SQLite。
2. 新機安裝 Git、Python 3.12、Node.js 與合適的 NVIDIA 驅動，clone 本專案並確認所需 commit。日後更新程式使用 `git pull`；Git 不會取得舊機的 data、模型或 runtime。
3. 依 README 快速開始重新建立平台 `.venv`、安裝 lock 與 `npm.cmd ci`／build；依本頁固定 ComfyUI 來源重建引擎環境。訓練有需要時再依 [T03](training/runtime.md)重建獨立環境。PyTorch／CUDA 與驅動相容性要在新機實測，舊機安裝成功不能替代。
4. 從可信舊機複製 `runtime/ComfyUI/models/` 權重及需要的 `.provenance.json`，外部權重另搬；依各流程文件重建固定自訂節點與依賴。不要沿用舊機的 `.venv/`、ComfyUI／training 的 `.venv/` 或 `frontend/node_modules/`。FLUX 可用 [離線 verify](models/flux-installation.md)重新核對四份完整檔案；其他模型依個別固定來源工具核對。
5. 新機保持平台停止，驗證備份、restore 到新目錄後用 `scripts/serve_local.py --data <還原的data目錄> --port 8001` 試讀；不要覆寫既有 DATA。預設 `start-all.bat` 仍讀專案 `data/`，自訂還原位置須按備份文件明確切換。核對作品／原圖／素材與數量後才開始新工作。
6. 逐項核對額外 checkpoint 目錄、來源圖片、訓練 run／bundle 與其他絕對路徑。Windows 帳號、磁碟代號或資料夾不同時，不保證舊紀錄能直接續訓；保留舊 run，不批次改寫歷史 manifest。新工作應以新主機驗證過的來源及環境準備。
7. 確認本機引擎網址與節點、同步模型庫，以小型固定案例生成並在裝置回報核對實際 RTX 4080；保存 GPU／VRAM／RAM、驅動／Torch／CUDA／引擎版本及結果，才作為 E02／E03 的新機證據。新機的 FLUX 精度與卸載仍須另測，不能只憑顯卡型號保證原始 BF16 全部常駐顯存。

兩台同時保留時，各用獨立 DATA／SQLite；不要把運作中的資料庫放共用資料夾讓兩台共同寫入。目前兩台可各自本機使用；從 3060 瀏覽器操作 4080 平台則是另外的遠端部署需求，仍須按 [部署與存取](deployment.md)設計連線／認證，單純複製資料夾不會啟用。

## 埠與開發

故障時可先到設定頁「故障診斷」唯讀檢查平台／資料／引擎狀態，再以原任務 UUID 或請求 ID 預覽、下載診斷；操作與隱私／保留限制見 [診斷說明](diagnostics.md)。引擎離線仍可開啟已保存作品；診斷不會重送生成。

| 埠 | 用途 | 啟動／停止 |
| --- | --- | --- |
| 8000 | 平台 API、前端與圖片 | start-local.ps1／該終端 Ctrl+C |
| 8188 | ComfyUI 模型、生成、歷史與輸出 | start-comfyui.ps1／該終端 Ctrl+C |
| 5173（預設） | Vite 開發與代理至 8000 | frontend 內 npm.cmd run dev／該終端 Ctrl+C |
| 8001 等臨時埠 | 隔離驗收 | 不是日常依賴，依驗收紀錄處理 |

`start-all.bat` 只啟動前兩個腳本；SQLite 不占埠。Vite 埠被占用可能選下一個，請看終端網址，需固定可指定 `--port`／`--strictPort`。修改平台埠須同步 vite.config.ts 代理；引擎埠須同步腳本及設定頁，舊任務仍綁定原網址。不要結束所有 Python 程序。

### 雙啟動捷徑與錯誤視窗

雙擊 `start-all.bat` 後，會開啟兩個服務視窗，並由 `scripts/open-platform.ps1` 等待平台健康檢查及首頁正常回應，再用預設瀏覽器開啟 `http://127.0.0.1:8000/`。等待約 60 秒仍未就緒時不自動開頁，保留提示供查看平台視窗；預設瀏覽器無法開啟時會顯示手動網址。自動開頁不必等待 ComfyUI，生成前仍需到引擎視窗確認 `http://127.0.0.1:8188` 已啟動。

批次檔的「Opened service windows」只代表已要求開啟視窗；視窗內的訊息才表示服務是否啟動成功。啟動失敗時 PowerShell 視窗會保留錯誤，依訊息檢查缺少的環境、前端建置、模型目錄或占用中的埠。停止服務後可輸入 `exit` 關閉視窗。

若出現 `'cho'`、`'-NoProfile'` 不是命令，請更新本專案的批次檔。2026-10-24 在真實 `cmd.exe` 重現舊版 UTF-8 中文批次內容被截斷，兩個 PowerShell 腳本單獨執行則能正常啟動。現行批次內容使用 ASCII 訊息，並以 `.gitattributes` 固定 CRLF 換行；維護時請保持此格式。回歸測試透過無視窗探針驗證繁中字碼頁 950、UTF-8 字碼頁 65001、含空白路徑與缺少 PowerShell 的錯誤分支，不會啟動實際生成服務。

本頁為現行操作；歷史服務、磁碟與測試數不代表即時狀態。[整理前全文](history/readme-before-q01-20261022.md) 保留原說明；功能細節見 [索引](index.md)。
