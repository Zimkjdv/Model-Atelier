# Model Atelier

個人 AI 圖像創作與實驗工作台。Vue 3／TypeScript 前端與 FastAPI 後端透過獨立 ComfyUI 生成圖片，作品、素材、設定與 SQLite 資料保存在本機。

## 快速開始

Windows／PowerShell 先準備 Git、Python 3.12 與 Node.js 24，從專案根目錄執行：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.lock.txt
Set-Location frontend
npm.cmd ci
npm.cmd run build
Set-Location ..
.\start-local.ps1
```

開啟 [本機平台](http://127.0.0.1:8000/)。前端由 FastAPI 提供，不需另啟 Node。生成另需安裝 ComfyUI、相容 PyTorch 與模型權重；既有環境可另開終端執行 `./start-comfyui.ps1`。完成安裝後也可使用 `start-all.bat` 啟動兩者並開啟瀏覽器。

詳細安裝、啟停、埠、跨機搬移與排錯以 [安裝與操作](docs/setup-and-operations.md) 為準；選用 Docker 的獨立資料卷及 8001 埠見 [Docker 部署](docs/docker.md)。新資料庫不附作品或權重，引擎離線時仍可整理已保存資料。

## 第一次生成

1. 啟動平台與 ComfyUI，在設定頁確認引擎網址，預設為 `http://127.0.0.1:8188`。
2. 同步模型庫，選擇 checkpoint 並核對架構、版本與工作流程；空清單表示仍需安裝模型。
3. 在創作工作台填入描述與參數，明確按下「生成圖片」。保存草稿、載入設定、切換分頁都不會自動生成。
4. 任務完成後明確匯入作品庫。提交回應遺失時使用原請求恢復入口，避免重複提交。
5. 已匯入作品可離線預覽、下載原圖與 workflow，並載入支援流程的原設定。

## 主要能力與邊界

| 範圍 | 操作與限制 |
| --- | --- |
| 創作 | 文生圖、單張圖片重繪、精確 Seed、草稿與設定交換；[最多四個有序 LoRA](docs/models/lora-library.md#ordered-lora)。batch 固定 1。 |
| 局部修補 | 遮罩筆刷／擦除／PNG、[v1／v2 修補與羽化](docs/inpainting.md)、[Fooocus 實驗流程](docs/fooocus-inpainting.md)。專用流程的一般草稿／交換／比較仍未開放。 |
| 結構與單張參考 | [Canny 與 CPU 預覽](docs/controlnet.md)、[Pose／Depth](docs/structure-reference.md)、[SDXL 畫風／角色參考](docs/models/ipadapter-reference.md)。不保證身份鎖定或姿勢完全一致。 |
| FLUX | [固定四元件安裝](docs/models/flux-installation.md)、[Schnell 文生圖及保存／復原](docs/models/flux-workflow.md)、[獨立 LoRA／VAE 圖生圖](docs/models/flux-extensions.md)。僅認列已驗收配置，未知組合與身份參考停用。 |
| 作品、素材與實驗 | [搜尋、收藏、筆記、評分、封存及並排比較](docs/artwork-library.md)；[有限比較方案、任務關聯與 JSON 報告](docs/experiment-plans.md)。封存不釋放檔案，各組生成需明確操作。 |
| 訓練 | [資料審查、準備／開始／停止／續訓與產物](docs/training/workspace.md)，使用獨立 Windows 環境及 SDXL UNet LoRA。審查資料不會啟動訓練；幾何技術驗收不代表作者畫風／角色品質通過。 |
| 系統與維運 | [引擎裝置回報](docs/execution-device.md)、[執行量測](docs/job-measurements.md)、[可預覽的診斷匯出](docs/diagnostics.md)、[停機備份還原](docs/data-backup.md)。觀察值不代表任務專用峰值或最低硬體需求。 |

平台預設只供本機使用，沒有多租戶登入或付費服務。使用遠端引擎時，必要的提示詞與輸入圖會送往該引擎；完整存取邊界見 [本機存取與角色](docs/setup-and-operations.md#local-access)。

已有 RTX 3060／4080 的固定案例，更多配置與真正畫風／角色訓練品質仍需各自驗收。[實機與歷史證據](docs/index.md#實機與歷史證據) 保留各次條件與限制。模型安裝或生成成功不代表來源授權已核實，Pony 與 FLUX 的條款／上游缺口見 [模型來源文件](docs/index.md#模型與-flux)。

## 文件入口

| 目的 | 入口 |
| --- | --- |
| 第一次操作 | [HTML 圖文教學](docs/guide/index.html)：下載後用瀏覽器開啟，可離線閱讀、點圖放大與列印；部分截圖為舊布局。 |
| 找功能、API、模型、訓練或驗收文件 | [完整文件索引](docs/index.md)，功能細節由各主題文件維護。 |
| 看目前 UI 與驗收 | [正式交付現況](docs/ui-redesign/INTEGRATION-NOTES.md)、[桌面驗收](docs/ui-redesign/ACCEPTANCE.md)、[原始 preview](docs/ui-redesign/preview.html)。 |
| 看尚未完成的工作 | [產品 ROADMAP](ROADMAP.md) 與 [UI 獨立待辦](docs/ui-redesign/BACKEND-CAPABILITIES-BACKLOG.md)，不以頁面美化代替能力完成。 |
| 查版本變更與舊決策 | [CHANGELOG](CHANGELOG.md)，歷史測試數不代表目前全量驗收結果。 |
| 開發與回歸 | [架構](docs/architecture.md)、[前端通訊與生命週期](docs/frontend-api.md)、[品質檢查](docs/quality-checks.md)。 |

備份或搬機前先停止所有資料寫入者，再依停機備份流程操作；不要直接複製正在寫入的 SQLite，也不要以整包虛擬環境搬移代替重建環境。程式與測試在 Git，模型權重、原始圖片、`data/`、`runtime/` 及虛擬環境不納入 Git。
