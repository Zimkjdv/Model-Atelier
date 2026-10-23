# Model Atelier

個人 AI 圖像創作與實驗工作台。Vue 3 + TypeScript 前端、FastAPI 後端，透過獨立 ComfyUI 執行生成；SQLite 與圖片保存在本機。

現行待辦與驗收以 [ROADMAP.MD](ROADMAP.MD) 為準；開發與歷史實測見 [CHANGELOG.MD](CHANGELOG.MD)。文件整理日期：2026-10-22。

## 快速開始

Windows／PowerShell 使用者先準備 Git、Python 3.12 與 Node.js；本專案曾驗證 Python 3.12.10、Node.js 24.19.0。從專案根目錄執行：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.lock.txt
Set-Location frontend
npm.cmd ci
npm.cmd run build
Set-Location ..
.\start-local.ps1
```

開啟 [本機平台](http://127.0.0.1:8000)。前端由 FastAPI 提供，不需另外啟動 Node。尚未開啟引擎時仍可保存草稿、整理素材、瀏覽已匯入作品；新資料庫不附作品或權重。

生成另需獨立 ComfyUI、相容 PyTorch 與 checkpoint；完整步驟見 [安裝與操作](docs/setup-and-operations.md)。已有環境時另開終端執行 `./start-comfyui.ps1`，設定引擎網址並同步模型庫。`start-all.bat` 是兩個啟動腳本的捷徑，不代替安裝。

## 第一次生成

1. 啟動平台與 ComfyUI；設定頁確認引擎網址，預設 `http://127.0.0.1:8188`。
2. 模型庫同步 checkpoint，選擇模型並登記正確架構／版本；空清單表示還需安裝模型。
3. 工作台選 Checkpoint／SDXL，填入提示詞與參數。模型預設需確認套用，保存草稿不會生成。
4. 明確按生成並查看任務；提交回應遺失時恢復原 UUID，避免重送。完成後到作品庫明確匯入／補齊圖片。
5. 已匯入作品可離線預覽、下載原圖／workflow、載入支援流程的原設定；載入不會自動生成。

首次硬體與模型配置需自行驗證。RTX 3060 的 Pony／Animagine 固定案例見 [驗收索引](docs/index.md#實機與歷史證據)；RTX 4080、FLUX GPU 生成與訓練仍有待辦。

Pony 同一權重的 Hugging Face 標記與 Civitai 發布頁條款不同，完整授權適用關係仍未核實；來源、完整參考條文及依賴缺口見 [M01 查核](docs/models/pony-v6-xl-license.md)。

## 功能與限制

| 範圍 | 已提供 | 限制與說明 |
| --- | --- | --- |
| Checkpoint | 文生圖、單張圖生圖、精確字串 seed、草稿、設定交換、最多四個有序 LoRA | batch 固定 1；[參考流程](docs/models/reference-workflows.md)、[LoRA](docs/models/multi-lora-workflow.md) |
| 局部編輯 | 遮罩筆刷／擦除／反相／PNG、v1 修補與 v2 內側羽化、原設定還原 | 一般草稿／交換／比較仍待 R07；[修補](docs/inpainting.md)、[羽化](docs/inpaint-feather.md) |
| Canny | ControlNet 庫、結構引導、CPU 預覽、v2 原邊緣保存與離線查看 | depth／pose／角色 adapter 未接入；[流程](docs/controlnet.md)、[預覽](docs/canny-preview.md) |
| FLUX.1 [schnell] | 元件庫、固定來源預檢、獨立表單／草稿／交換、提交與還原 | 固定來源存取／安裝及 GPU 生成驗收未完成；[FLUX](docs/models/flux-workflow.md) |
| 作品與素材 | 原圖／縮圖、搜尋、收藏、筆記、人工評分、封存／還原、素材用途與引用保護 | 封存不釋放檔案，無一般作品永久刪除；[整理](docs/artwork-library.md)、[比較](docs/artwork-comparison.md) |
| 實驗 | 固定案例、模型／取樣參數有限比較、保存／匯入、任務關聯與原始 JSON 報告 | 各組手動生成，無自動重試或品質評分；[方案](docs/experiment-plans.md)、[結果](docs/experiment-runs.md) |
| 執行 | 進度、取消／條件化停止、失敗保存、環境快照、原引擎連續資源取樣、E01 裝置回報 | 觀察最高值不等於任務專用峰值；[量測範圍](docs/job-measurements.md)、[裝置回報](docs/execution-device.md) |

尚未提供訓練、多租戶／付費、自訂節點編輯器或官方付費 API。設定還原不保證跨環境逐像素一致；實測的來源條件與品質偏差均保留。

## 日常操作

- 停止：平台與引擎各自在所屬終端按 Ctrl+C；停止平台不會中斷引擎工作。不要結束所有 Python 程序。
- 備份：停平台後保存完整 data，含 SQLite、素材、作品、job_inputs、control_edges。權重、外部目錄與需要的 runtime 證據另備份，見 [備份還原](docs/setup-and-operations.md#備份與還原)。
- 埠：8000 平台、8188 引擎、5173 Vite 開發預設；8001 等隔離埠不是日常依賴，見 [操作指南](docs/setup-and-operations.md)。

## 專案與文件結構

以下列出主要目錄與入口，省略個別功能模組；完整責任與資料流見 [架構說明](docs/architecture.md)。

```text
model-atelier/
├── README.md                   # 專案介紹、快速開始與閱讀入口
├── ROADMAP.MD                  # 現行待辦、優先順序與驗收條件
├── CHANGELOG.MD                # 已完成變更與歷史實測紀錄
├── .github/workflows/          # lock 安裝、完整品質檢查與失敗證據 CI
├── backend/                    # FastAPI、SQLite、生成流程與本機檔案管理
│   ├── main.py                 # create_app 工廠與 ASGI 應用程式入口
│   ├── app_context.py          # 每個應用程式的配置、路徑與引擎 HTTP 介面
│   ├── core_api.py             # 核心 API 註冊
│   ├── schemas.py              # API 請求型別
│   └── test_*.py               # 後端單元與整合測試
├── frontend/                   # Vue 3 + TypeScript + Vite
│   ├── src/                    # 工作台、作品庫、設定與共用 API／請求生命週期
│   ├── tests/                  # 隔離 Playwright 瀏覽器回歸
│   ├── check-*.mjs             # 前端 API 契約與流程檢查
│   └── package.json            # 前端依賴與開發／建置／檢查命令
├── comfyui_extensions/         # 專案維護的 ComfyUI 執行裝置回報擴充
├── models/                     # 固定模型來源、版本與驗證資訊的 JSON manifest
├── experiments/                # 固定實驗案例與比較用 JSON 定義
├── scripts/                    # 環境檢查、模型安裝與實機驗證工具
├── docs/                       # 操作、架構、功能契約與驗收文件
│   ├── index.md                # 完整文件索引，按操作目的分類
│   ├── setup-and-operations.md # 安裝、啟停、埠與備份還原
│   ├── architecture.md         # 模組責任、資料流與保存約束
│   ├── application-factory.md  # 後端工廠、配置與測試隔離
│   ├── frontend-api.md         # 前端 HTTP 契約、取消與原請求恢復
│   ├── ui-guidelines.md        # 介面與互動規範
│   ├── models/                # 模型來源、LoRA、FLUX 與參考流程說明
│   ├── validation/            # 限定環境與案例的驗收紀錄
│   └── history/               # 歷史文件快照，僅供追溯
├── requirements.txt           # 後端直接依賴
├── requirements.lock.txt      # 可重現安裝的固定依賴版本
├── requirements-dev.lock.txt  # 品質環境：runtime lock 與 Ruff
├── quality-scope.json         # 分批格式／靜態檢查的明確檔案範圍
├── start-local.ps1             # 啟動平台並提供已建置前端
├── start-comfyui.ps1           # 啟動獨立 ComfyUI 引擎
└── start-all.bat               # Windows 雙啟動捷徑
```

安裝或執行後另有 `.venv/`、`frontend/node_modules/`、`frontend/dist/`、`data/` 與 `runtime/`，均不納入 Git。`data/` 保存 SQLite、素材、作品與任務固定輸入；`runtime/ComfyUI/` 保存獨立引擎及其權重、輸入與輸出。根目錄 `models/` 保存版本資訊，模型權重通常位於 `runtime/ComfyUI/models/`；兩者用途不同。備份範圍見 [資料位置](docs/architecture.md#資料位置與約束)。

## 開發與文件

完整品質檢查：`.venv/Scripts/python.exe scripts/check_quality.py`，依序執行格式／靜態檢查、後端測試、前端型別／建置、四組契約檢查及隔離瀏覽器回歸，失敗立即停止。品質環境需安裝 `requirements-dev.lock.txt` 與測試瀏覽器，見 [乾淨安裝與檢查指南](docs/quality-checks.md)。單獨後端可執行 unittest，前端可執行 `npm.cmd run build`、`npm.cmd test`、`npm.cmd run test:browser`；格式命令與提交／恢復規則見 [維護規則](docs/maintenance.md)。不等同實機 GPU 或完整 UI 驗收。

| 閱讀目的 | 文件與用途 |
| --- | --- |
| 安裝與維護 | [安裝與操作](docs/setup-and-operations.md)：環境準備、首次生成、啟停與備份還原 |
| 保護與還原資料 | [完整備份工具](docs/data-backup.md)：停機盤點、hash 驗證、新目錄還原與明確切換 |
| 排查故障 | [診斷與匯出](docs/diagnostics.md)：請求／任務 ID、平台／資料／引擎狀態與安全預覽 |
| 尋找功能說明 | [文件索引](docs/index.md)：按創作、作品、實驗與模型流程查閱完整文件 |
| 專用流程保存與交換 | [R07 格式評估](docs/specialized-workflow-formats.md)：局部編輯／Canny 的版本別能力、明確拒絕及完整原流程下載 |
| 理解或修改程式 | [架構與資料流](docs/architecture.md)、[應用程式工廠](docs/application-factory.md)、[前端 API](docs/frontend-api.md)：模組責任、配置隔離、通訊與任務生命週期 |
| 驗證變更與清單效能 | [品質檢查與 CI](docs/quality-checks.md)、[分頁與量測](docs/list-pagination.md)：重跑命令、相容策略與驗收證據 |
| 調整 UI | [UI 規範](docs/ui-guidelines.md)、[導覽與能力狀態](docs/navigation.md)、[逐頁視覺與無障礙驗收](docs/validation/ui-accessibility-20261023.md)：介面原則、可還原網址與桌面／窄視窗證據 |
| 安排後續工作 | [ROADMAP](ROADMAP.MD)：尚未完成的項目與完成條件；[CHANGELOG](CHANGELOG.MD)：已完成變更 |
| 查核驗收證據 | [驗收目錄](docs/validation)：依硬體、模型、參數與日期記錄結果，不能視為所有環境的保證 |
| 追溯舊文件 | [整理前 README 全文](docs/history/readme-before-q01-20261022.md)：舊限制、命令與歷史測試數，現行操作請以目前文件為準 |
