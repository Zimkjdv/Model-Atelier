# Model Atelier

個人 AI 圖像創作與實驗工作台。Vue 3 + TypeScript 前端、FastAPI 後端，透過獨立 ComfyUI 執行生成；SQLite 與圖片保存在本機。

現行待辦與驗收以 [ROADMAP.md](ROADMAP.md) 為準；開發與歷史實測見 [CHANGELOG.md](CHANGELOG.md)。文件整理日期：2026-10-27。

第一次使用可先開啟 [HTML 圖文使用教學](docs/guide/index.html)：依序介紹啟動、生成、單張參考、資料審查、訓練／續訓、LoRA 比較與備份。下載專案後直接用瀏覽器開啟 `docs/guide/index.html`，支援離線閱讀、點圖放大與列印／另存 PDF；圖片與樣式需保留在同一個 guide 目錄。GitHub 檔案頁只顯示 HTML 原碼，不是教學預覽。

桌面介面已依參考重整；新版位置與驗證見 [正式 UI 整合紀錄](docs/ui-redesign/IMPLEMENTATION.md)。教學的部分截圖仍是舊布局。更新後請重新啟動平台並重整瀏覽器，以載入新的後端端點與介面。

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

生成另需獨立 ComfyUI、相容 PyTorch 與 checkpoint；完整步驟見 [安裝與操作](docs/setup-and-operations.md)。已有環境時另開終端執行 `./start-comfyui.ps1`，設定引擎網址並同步模型庫。`start-all.bat` 是兩個啟動腳本的捷徑，平台就緒後會自動以預設瀏覽器開啟 `http://127.0.0.1:8000/`；不代替安裝。

若選用 Docker Desktop／WSL2，可執行 `docker compose up -d --build --wait`，在 `http://127.0.0.1:8001/` 使用獨立資料卷的平台；ComfyUI 仍在 Windows 原生執行。GPU 資訊、資料持久化、備份還原與訓練限制見 [Docker 本機部署](docs/docker.md)。Docker 不是原生使用的必要條件。

## 第一次生成

1. 啟動平台與 ComfyUI；設定頁確認引擎網址，預設 `http://127.0.0.1:8188`。
2. 模型庫同步 checkpoint，選擇模型並登記正確架構／版本；空清單表示還需安裝模型。
3. 工作台選 Checkpoint／SDXL，填入提示詞與參數。模型預設需確認套用，保存草稿不會生成。
4. 明確按生成並查看任務；提交回應遺失時恢復原 UUID，避免重送。完成後到作品庫明確匯入／補齊圖片。
5. 已匯入作品可離線預覽、下載原圖／workflow、載入支援流程的原設定；載入不會自動生成。

首次硬體與模型配置需自行驗證。RTX 3060 的固定案例見 [驗收索引](docs/index.md#實機與歷史證據)；RTX 4080 已完成 [E02 八個基本流程、保存與離線還原](docs/validation/rtx4080-workflows-20261026.md)。[E03](docs/validation/hardware-comparison-20261026.md)另保存兩機相同配置比較與 1536² 高負載；[E04](docs/validation/hardware-resources-20261026.md)分開登記推論與 4080 的 512／1024 幾何技術訓練資源。更多 FLUX 配置及真實畫風／角色訓練品質另行驗收。

Pony 同一權重的 Hugging Face 標記與 Civitai 發布頁條款不同，完整授權適用關係仍未核實；來源、完整參考條文及依賴缺口見 [M01 查核](docs/models/pony-v6-xl-license.md)。

## 功能與限制

| 範圍 | 已提供 | 限制與說明 |
| --- | --- | --- |
| Checkpoint | 文生圖、單張圖生圖、精確字串 seed、草稿、設定交換、最多四個有序 LoRA | batch 固定 1；[參考流程](docs/models/reference-workflows.md)、[LoRA](docs/models/multi-lora-workflow.md) |
| 局部編輯 | 遮罩筆刷／擦除／反相／PNG、v1／v2 羽化修補、Fooocus v3 實驗選項、原設定還原 | [Fooocus 限制與比較](docs/fooocus-inpainting.md)；一般草稿／交換／比較尚未支援；[一般修補](docs/inpainting.md)、[羽化](docs/inpaint-feather.md) |
| 結構參考 | Canny v2／CPU 預覽；SDXL pose／depth v3、實際條件圖保存與完整還原 | [pose／depth 操作與實測限制](docs/structure-reference.md)、[Canny](docs/controlnet.md)；動漫骨架可能缺漏，不保證姿勢一致 |
| 畫風／角色參考 | SDXL Plus ViT-H 單張推論、兩種模式、元件登記、原設定與來源快照 | 沒有訓練；可能帶入服裝／髮色／背景，無身份鎖定；[操作](docs/models/ipadapter-reference.md)、[12 組實測](docs/validation/reference-adapter-20261023.md) |
| FLUX.1 [schnell] | 固定四元件安裝／驗檔、精度／卸載觀察、專用文生圖、PVC LoRA 與 VAE 圖生圖 | [F01 安裝](docs/models/flux-installation.md)、[F02 原生 512 配置](docs/models/flux-runtime-observation.md)、[F03 平台保存／還原與受控 OOM](docs/models/flux-generation-acceptance.md)已實測；另有 [F04 LoRA／構圖重繪](docs/models/flux-extensions.md)。未知組合與身份參考停用，編碼器轉檔鏈保留缺口 |
| 作品與素材 | 原圖／縮圖、搜尋、收藏、筆記、人工評分、封存／還原、素材用途與引用保護 | 封存不釋放檔案，無一般作品永久刪除；[整理](docs/artwork-library.md)、[比較](docs/artwork-comparison.md) |
| 實驗 | 通用／動漫案例、模型／提示詞／取樣參數有限比較、保存／匯入、任務關聯與原始 JSON 報告 | 各組手動生成，無自動重試或品質評分；[方案](docs/experiment-plans.md)、[結果](docs/experiment-runs.md) |
| 執行 | 進度、取消／條件化停止、失敗保存、環境快照、原引擎連續資源取樣、E01 裝置回報 | 觀察最高值不等於任務專用峰值；[量測範圍](docs/job-measurements.md)、[裝置回報](docs/execution-device.md) |

訓練提供 Windows 獨立環境及 SDXL UNet LoRA CLI；[訓練工作區](docs/training/workspace.md)已接上 T05 圖片審查、T06 明確準備／開始／停止／續訓、產物安裝／模型回登與固定比較方案。環境首次安裝仍依 [T03](docs/training/runtime.md)，資料審查與建方案不自動訓練或生成；尚未提供多租戶／付費、自訂節點編輯器或官方付費 API。設定還原不保證跨環境逐像素一致；實測來源條件與品質限制均保留。

## 目前進度與下一步

截至 2026-10-27，ROADMAP 尚有 **10 個未完成主項、11 個待驗收子項**；以下依已提交的驗收紀錄整理，完成代表所列配置通過。

| 範圍 | 已完成進度 | 下一步／限制 |
| --- | --- | --- |
| RTX 4080（E02–E04） | 八個基本流程、兩機固定條件比較、1536² 高負載，以及分開記錄的 512／1024 技術訓練 | 單次結果不代表普遍效能或最低硬體需求；[資源紀錄](docs/validation/hardware-resources-20261026.md) |
| FLUX（F01–F04） | 固定四元件、3060 原生 512 配置、平台保存／離線恢復／受控 OOM、PVC LoRA 與 VAE 圖生圖 | 所列案例約 64 GiB RAM，程序 RSS 曾超過 36 GiB；4080 FLUX、32 GiB RAM、其他尺寸與身份參考尚未驗收 |
| 模型來源（M01／M02） | Pony 作者聲明與元件指紋；FLUX 發布追溯及 CLIP 候選全張量比對 | 完整條款適用關係、確切上游及轉檔鏈仍缺證據；[M01 補查](docs/models/pony-v6-xl-license-followup-20261026.md)、[M02 補查](docs/models/flux-encoder-lineage-followup-20261026.md) |
| 動漫參考與訓練（R01–R05、L01、T01–T08） | 有限品質比較、單張 adapter、pose／depth、修補、資料審查、訓練控制、產物回登及報告 | 作者畫風／角色尚未實際訓練；幾何資料技術驗收不等於作者品質通過 |
| 介面與官方服務 | 桌面／窄視窗已有驗收；官方 API 尚未接入 | V01 待實體觸控設備；A01–A07 最後實作，A02 先確認模型與提供者 |

### 動漫畫風／角色資料準備

既有 R05、L01、R02、T01、T02、R01、R03 的首輪工作已完成，後續以資料審查及固定品質比較推進。R02 使用的 `artist_ref/ハシスタジオ_pixiv` 共 22 檔、20 個不同內容；每次只用一張參考圖，實際選用一張畫風圖、一張角色圖，另留六張評估，沒有把全部圖片送入訓練。詳見 [圖片用途與分組](docs/validation/reference-inputs-20261023.md)。

1. 在 [訓練工作區](docs/training/workspace.md)完成 caption、來源與角色身分審查；兩條資料路徑各有 10 張訓練候選、6 張開發評估、6 張排除，目前真實資料包仍不能匯出。缺項依 [T02 紀錄](docs/validation/training-dataset-20261023.md)核對，T07 可定位待審查圖片。
2. 確認試訓時，依 [T03 環境與資源](docs/training/runtime.md)和 [T06 控制流程](docs/training/workspace.md#t06-本機訓練與產物)明確準備／開始；畫風與角色分開，圖片審查不會自動啟動訓練。
3. 依 [T04 固定比較](docs/training/artifacts.md)評估產物，並用 T08 查看原 run 報告。最終品質驗收前確認獨立保留圖未參與反覆調參；缺圖時先提醒補齊。

新畫風可先從每組七張候選參考、三張保留評估開始；試訓可先規劃 20–50 張訓練圖及 5–10 張評估圖，僅作起始配額。完整分割、提醒時點與品質判準見 [動漫畫風開發計畫](docs/anime-style-development.md)。模組擴充沿用 [GitHub 借用策略](docs/github-reuse-assessment-20261023.md)與現有 Vue／FastAPI／SQLite／ComfyUI 架構。

## 日常操作

另台 Windows／RTX 4080 部署建議 Git clone 程式、搬移已下載權重及停機備份的資料，再重建各自的 Python 環境；不要依賴整包虛擬環境直接搬移。步驟與絕對路徑提醒見 [跨機部署](docs/setup-and-operations.md#部署至另一台-windows主機)。FLUX 有獨立 [固定安裝／驗檔 CLI](docs/models/flux-installation.md)，官方來源存取與 GPU 驗收分開確認。

- 停止：平台與引擎各自在所屬終端按 Ctrl+C；停止平台不會中斷引擎工作。不要結束所有 Python 程序。
- 備份：停平台後保存完整 data，含 SQLite、素材、作品、job_inputs、control_edges、structure_outputs。權重、外部目錄與需要的 runtime 證據另備份，見 [備份還原](docs/setup-and-operations.md#備份與還原)。
- 埠：8000 平台、8188 引擎、5173 Vite 開發預設；8001 等隔離埠不是日常依賴，見 [操作指南](docs/setup-and-operations.md)。

## 專案與文件結構

以下列出主要目錄與入口，省略個別功能模組；完整責任與資料流見 [架構說明](docs/architecture.md)。

```text
model-atelier/
├── README.md                   # 專案介紹、快速開始與閱讀入口
├── ROADMAP.md                  # 現行待辦、優先順序與驗收條件
├── CHANGELOG.md                # 已完成變更與歷史實測紀錄
├── .github/workflows/          # lock 安裝、完整品質檢查與失敗證據 CI
├── Dockerfile                  # 固定基底、前端建置與非 root 平台映像
├── compose.yaml                # 選用本機 Docker 平台與持久資料／鎖卷
├── compose.gpu.yaml            # 選用容器 GPU 資訊觀察，不執行推論
├── backend/                    # FastAPI、SQLite、生成流程與本機檔案管理
│   ├── main.py                 # create_app 工廠與 ASGI 應用程式入口
│   ├── container_main.py       # Linux 容器入口、資料卷及明確 gateway 來源
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
├── schemas/                    # 訓練資料契約 v1 JSON Schema（不是生成 API）
├── training/                   # 獨立 trainer／tokenizer 固定來源與 Windows 依賴鎖
├── scripts/                    # 環境檢查、模型安裝與實機驗證工具
├── docs/                       # 操作、架構、功能契約與驗收文件
│   ├── index.md                # 完整文件索引，按操作目的分類
│   ├── setup-and-operations.md # 安裝、啟停、埠與備份還原
│   ├── deployment.md           # 本機存取邊界與平台／引擎角色
│   ├── docker.md               # 選用 Docker、資料卷、備份與原生差異
│   ├── architecture.md         # 模組責任、資料流與保存約束
│   ├── application-factory.md  # 後端工廠、配置與測試隔離
│   ├── frontend-api.md         # 前端 HTTP 契約、取消與原請求恢復
│   ├── ui-guidelines.md        # 介面與互動規範
│   ├── models/                # 模型來源、LoRA、FLUX 與參考流程說明
│   ├── training/              # 訓練需求、資料契約、獨立環境／run CLI 與工具介面
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
| 本機 Docker | [Docker 部署](docs/docker.md)：Linux 平台接原生 ComfyUI、獨立資料卷與還原；[實測範圍](docs/validation/docker-deployment-20261025.md) |
| 保護與還原資料 | [完整備份工具](docs/data-backup.md)：停機盤點、hash 驗證、新目錄還原與明確切換 |
| 排查故障 | [診斷與匯出](docs/diagnostics.md)：請求／任務 ID、平台／資料／引擎狀態與安全預覽 |
| 尋找功能說明 | [文件索引](docs/index.md)：按創作、作品、實驗與模型流程查閱完整文件 |
| 畫風／角色參考 | [R02 操作與契約](docs/models/ipadapter-reference.md)：單張推論、元件登記、精確還原；[圖片用途](docs/validation/reference-inputs-20261023.md)明確區分參考與訓練 |
| 準備訓練資料 | [T02 契約與 CLI](docs/training/dataset-contract.md)：唯讀盤點、逐張審查、固定分割、不可覆寫出口；[本批缺項](docs/validation/training-dataset-20261023.md)，沒有啟動訓練 |
| 網頁審查圖片 | [T05 訓練工作區](docs/training/workspace.md)：逐張 caption／來源／角色審查、不可變版本與 train-only 出口；不自動訓練 |
| 網頁控制訓練 | [T06 操作與恢復](docs/training/workspace.md#t06-本機訓練與產物)：單次開始、停止／新 run 續訓、資源／日誌／產物及固定比較；[有限驗收](docs/validation/training-control-20261025.md) |
| 本機 SDXL 訓練 | [T03 環境與操作](docs/training/runtime.md)：獨立安裝、凍結 run、停止／續訓與生成互斥；[資源與限制](docs/validation/training-runtime-20261025.md)，技術測試不代表作者品質 |
| 訓練產物與評估 | [T04 回登與固定比較](docs/training/artifacts.md)：來源／版本／hash／條件封存、模型庫登記、12 格計畫與人工審查模板；[技術驗收](docs/validation/training-artifacts-20261025.md)，作者圖仍未訓練 |
| 專用流程保存與交換 | [R07 格式評估](docs/specialized-workflow-formats.md)：局部編輯／Canny 的版本別能力、明確拒絕及完整原流程下載 |
| 理解或修改程式 | [架構與資料流](docs/architecture.md)、[應用程式工廠](docs/application-factory.md)、[前端 API](docs/frontend-api.md)：模組責任、配置隔離、通訊與任務生命週期 |
| 驗證變更與清單效能 | [品質檢查與 CI](docs/quality-checks.md)、[分頁與量測](docs/list-pagination.md)：重跑命令、相容策略與驗收證據 |
| 調整 UI | [UI 規範](docs/ui-guidelines.md)、[導覽與能力狀態](docs/navigation.md)、[逐頁視覺與無障礙驗收](docs/validation/ui-accessibility-20261023.md)：介面原則、可還原網址與桌面／窄視窗證據 |
| 部署與存取 | [本機部署決策](docs/deployment.md)：同一台電腦、來源限制與平台／引擎／儲存角色；[驗收](docs/validation/local-deployment-20261025.md) |
| 安排後續工作 | [ROADMAP](ROADMAP.md)：尚未完成的項目與完成條件；[CHANGELOG](CHANGELOG.md)：已完成變更 |
| 開始動漫畫風驗證 | [開發計畫與圖片準備](docs/anime-style-development.md)：本輪成果與後續順序、參考／評估／訓練資料、adapter 流程及人工驗收 |
| 查核驗收證據 | [驗收目錄](docs/validation)：依硬體、模型、參數與日期記錄結果，不能視為所有環境的保證 |
| 追溯舊文件 | [整理前 README 全文](docs/history/readme-before-q01-20261022.md)：舊限制、命令與歷史測試數，現行操作請以目前文件為準 |
