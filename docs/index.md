# 文件索引

現行入口是 [README](../README.md)，待辦與驗收條件以 [ROADMAP](../ROADMAP.MD) 為準；歷史測試數不表示目前所有功能已驗收。

初次操作先讀 [HTML 圖文使用教學](guide/index.html)：用瀏覽器開啟本機檔案，包含六張介面截圖、操作步驟、資料審查與訓練流程、常見問題及備份提醒，可離線閱讀／列印。深入契約與開發細節再依下列索引閱讀。

## 上游參考與開發策略

- [GitHub 借用與開發策略](github-reuse-assessment-20261023.md)：主要決策入口、R01 → R03、ComfyUI 節點、訓練工具及整合邊界
- [全部 47 個 ROADMAP 主項對照](roadmap-upstream-map-20261023.md)：已完成與未完成項目的來源、可沿用流程與仍需驗收部分
- [動漫相關原碼研究](anime-upstream-candidates-20261023.md)：分割、偵測修補、區域提示、LoRA 訓練與標註；尚未安裝或整合

## 安裝與維護

- [安裝、首次生成、埠與備份](setup-and-operations.md)、[架構與資料流](architecture.md)、[UI 規範](ui-guidelines.md)
- [應用程式工廠、配置與測試隔離](application-factory.md)
- [前端 HTTP 契約、取消與原請求恢復](frontend-api.md)
- [工作台未保存內容與離頁保護](unsaved-changes.md)
- [品質檢查、隔離瀏覽器回歸與 CI](quality-checks.md)
- [全站桌面／窄視窗視覺與無障礙補驗](validation/ui-accessibility-20261023.md)
- [清單分頁、相容策略與資料成長基準](list-pagination.md)
- [停機完整備份、唯讀盤點與新目錄還原](data-backup.md)
- [網址導覽、首次使用指引與能力狀態](navigation.md)
- [請求／任務追蹤、狀態分離與診斷預覽匯出](diagnostics.md)
- [格式、靜態檢查與高風險流程維護規則](maintenance.md)
- [裝置回報](execution-device.md)、[環境版本](runtime-versions.md)、[效能條件](execution-context.md)、[量測](job-measurements.md)
- [系統資訊目錄卡片、磁碟容量與開啟資料夾](storage-overview.md)、[狀態驗收](validation/storage-overview-20261024.md)

## 創作與作品

以動漫畫風為目標時，先讀 [動漫畫風驗證與開發計畫](anime-style-development.md)：圖片數量／分組、保留評估集、流程擴充及驗收。R02 已接入單張參考，T03／T04 已提供技術訓練與產物流程，T05／T06 已接上網頁操作；作者圖片仍待逐張審查與品質驗證。歷史指定順序為 **T01 → T02 → R01 → R03**，目前待辦以 ROADMAP 為準。

| 工作 | 說明 |
| --- | --- |
| 一般設定交換 | [精確 JSON](creation-settings-transfer.md) |
| 專用流程格式 | [局部編輯／Canny 草稿、交換與比較的支援及方案](specialized-workflow-formats.md) |
| 畫風／角色參考 | [R02 操作、固定來源與契約](models/ipadapter-reference.md)、[實際圖片用途／未訓練備註](validation/reference-inputs-20261023.md)、[12 組 GPU 與品質觀察](validation/reference-adapter-20261023.md) |
| 圖生圖／素材 | [參考流程與版本](models/reference-workflows.md) |
| 局部編輯 | [遮罩修補](inpainting.md)、[羽化](inpaint-feather.md)、[R03 Fooocus 專用修補實驗選項與品質限制](fooocus-inpainting.md) |
| Canny | [ControlNet 與原邊緣](controlnet.md)、[CPU 預覽](canny-preview.md) |
| Pose／Depth | [R01 SDXL 姿勢／相對深度流程、安裝與 RTX3060 驗收](structure-reference.md) |
| Pony Canny v2 實測 | [五組 LoRA、原邊緣／下載／還原與品質限制](validation/pony-canny-v2-20261023.md)、[可解析證據](validation/pony-canny-v2-20261023.json) |
| 作品整理 | [收藏／筆記／封存](artwork-library.md)、[比較與人工評分](artwork-comparison.md) |
| 實驗 | [固定案例](illustration-suite.md)、[比較方案](experiment-plans.md)、[保存／匯入](experiment-storage.md)、[任務關聯](experiment-runs.md)、[結果報告](comparison-report.md) |

## 訓練與資料

- [T05 訓練圖片與標註審查介面](training/workspace.md)：沿用 T02，原圖預覽、版本保存、來源重驗與明確資料出口，不自動批准作者圖
- [T07 缺項搜尋、篩選與圖片定位](training/workspace.md#t07-缺項導覽)、[桌面／窄版驗收](validation/training-review-navigation-20261025.md)：依已保存檢查完整分頁，保留未保存標註及 final test 不預覽規則
- [T06 本機訓練控制與產物銜接](training/workspace.md#t06-本機訓練與產物)、[停止／續訓與模型回登驗收](validation/training-control-20261025.md)：原 UUID 查回、單次啟動與資源釋放，建比較方案不生成
- [T08 訓練報告預覽與原始 JSON 下載](training/workspace.md#t08-訓練報告)、[唯讀驗收](validation/training-report-20261025.md)：來源／狀態／資源與回執觀察，日誌另選，不代替 payload 驗證或備份

- [T01 訓練需求與驗收範圍 v1](training/requirements.md)、[需求確認證據](validation/training-requirements-20261023.md)：畫風／角色分開、僅 SDXL 候選，沒有啟動訓練

- [T02 資料契約、Schema 與本機 CLI](training/dataset-contract.md)、[固定官方工具介面評估](training/tool-interface-research.md)、[22 檔盤點與出口驗收](validation/training-dataset-20261023.md)：真實資料仍待審查，沒有訓練

- [T03 獨立訓練環境與明確 run](training/runtime.md)、[RTX 3060 技術與資源驗收](validation/training-runtime-20261025.md)：只用自製幾何資料，作者圖未訓練；後續 T06 已提供網頁操作

- [T04 產物回登與固定比較](training/artifacts.md)、[技術載入／保存／離線還原證據](validation/training-artifacts-20261025.md)：原生模型庫與六份比較方案，品質未認列

## 模型與執行環境

- [FLUX／RTX 3060 實作前置判斷](models/flux-rtx3060-planning.md)：官方量化／卸載依據、GGUF 流程差異、4080 提醒規則及未驗收範圍
- [F01 固定 FLUX 安裝與完整驗檔](models/flux-installation.md)：官方 CLI 登入、四元件整體來源／磁碟檢查、續傳及離線 SHA256；[固定四份安裝證據](validation/flux-installation-20261025.md)
- [F02 實際精度／卸載工具](models/flux-runtime-observation.md)、[RTX 3060 實測](validation/flux-runtime-20261025.md)：512 原生配置、CPU／CUDA 張量與有界資源取樣，平台 HTTP／保存／OOM 另見下列 F03
- [F03 平台生成、作品保存與失敗復原](models/flux-generation-acceptance.md)：獨立 HTTP 引擎／DATA、原 UUID、離線 GET 與受控真實 CUDA OOM；[驗收](validation/flux-generation-20261025.md)
- [F04 Schnell LoRA 與原生 VAE 圖生圖](models/flux-extensions.md)：獨立版本／草稿、固定來源、元件與原圖快照、未知組合停用；[RTX 3060 四案例](validation/flux-extensions-20261025.md)
- [F02 元件條款與來源查核](models/flux-component-licenses.md)：BFL 全文與模型卡、CLIP／T5 上游參考；編碼器轉檔鏈仍待追溯

- [部署決策與本機存取](deployment.md)、[D01 HTTP／UI 驗收](validation/local-deployment-20261025.md)：同一台電腦、角色來源與連線邊界
- [選用 Docker 本機部署](docker.md)、[D02 GPU／出圖／資料持久化與還原驗收](validation/docker-deployment-20261025.md)：容器平台接原生 ComfyUI，保留原生操作與訓練限制

- [Animagine 來源與預設](models/animagine-xl-4.0-opt.md)
- [LoRA 庫](models/lora-library.md)、[多 LoRA](models/multi-lora-workflow.md)、[有序證據](models/ordered-lora-evidence.md)
- [FLUX 來源／限制](models/flux1-schnell.md)、[元件庫](models/flux-components.md)、[專用流程](models/flux-workflow.md)
- [Pony manifest](../models/pony-v6-xl.json)、[Animagine manifest](../models/animagine-xl-4.0-opt.json)
- [Pony 固定修訂授權／依賴查核](models/pony-v6-xl-license.md)：標準條文、作者附文及未核實的授權鏈分開記錄

## 實機與歷史證據

實測限於所列模型／hash／硬體／參數與日期；原始 runtime 報告、權重與作品不在 Git，備份依各紀錄。

- [Pony／RTX 3060](validation/pony-v6-xl-rtx3060.md)、[Animagine／RTX 3060](validation/animagine-xl-4-0-opt-rtx3060.md)
- [圖生圖](validation/checkpoint-image2image-rtx3060.md)、[修補](validation/checkpoint-inpaint-rtx3060.md)、[羽化](validation/inpaint-feather-rtx3060.md)
- [Canny](validation/checkpoint-canny-rtx3060.md)、[邊緣](validation/canny-edges-rtx3060.md)、[預覽](validation/canny-preview-rtx3060.md)
- [風格強度](validation/animagine-style-strength-rtx3060.md)、[多 LoRA 品質](validation/animagine-multi-lora-quality-rtx3060.md)、[四案例](validation/general-illustration-suite-rtx3060.md)
- [R05 動漫基準](validation/anime-baseline-20261023.md)：18 件模型／seed／提示標籤／新素材 denoise 比較與逐圖失敗觀察；使用者目標畫風仍待圖片
- [L01 更多畫風／有序 LoRA](validation/style-matrix-20261023.md)：14 組原生比較、四組原格式拒絕證據、獨立[像素畫相容副本](models/pixel-art-lora-sdxl.md)與逐圖品質限制
- [停止](validation/running-stop-rtx3060.md)、[E01](validation/execution-device-20261022.md)、[FLUX 範圍](validation/flux-integration.md)
- [全部驗收目錄](validation)、[CHANGELOG](../CHANGELOG.MD)、[2026-10-03 檢查](review-2026-10-03.md)
- [整理前 README 全文](history/readme-before-q01-20261022.md)：舊限制與命令僅供追溯。

- [E02 RTX 4080 八個基本流程與離線驗收](validation/rtx4080-workflows-20261026.md)、[可解析證據](validation/rtx4080-workflows-20261026.json)
- [E03 同配置 3060／4080 比較與 1536² 獨立負載](validation/hardware-comparison-20261026.md)、[可解析證據](validation/hardware-comparison-20261026.json)
- [E04 推論／訓練資源分開登記、4080 512／1024 真實技術訓練](validation/hardware-resources-20261026.md)、[可解析證據](validation/hardware-resources-20261026.json)

- [M01 作者 V6 聲明補查與本機元件指紋](models/pony-v6-xl-license-followup-20261026.md)、[可解析缺口與證據](validation/pony-license-audit-20261026.json)：完整授權驗收仍需發布者澄清
- [M02 編碼器發布歷史與 CLIP 候選全張量比對](models/flux-encoder-lineage-followup-20261026.md)、[可解析缺口與證據](validation/flux-encoder-audit-20261026.json)：數值吻合已驗證，發布者來源／轉換與條款仍待補足
