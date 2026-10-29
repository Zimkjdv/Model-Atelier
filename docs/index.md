# 文件索引

[README](../README.md)提供專案介紹與快速開始，[CHANGELOG](../CHANGELOG.md)記錄有日期的完成歷史，[ROADMAP](../ROADMAP.md)列出未完成工作與驗收條件。本索引依使用情境導向主要文件，詳細契約與證據留在各主題中。

第一次使用可先開啟[離線圖文教學](guide/index.html)，依步驟操作、放大圖片或列印；教學檔案的維護方式見[教學說明](guide/README.md)。

## 安裝與日常操作

| 要做的事 | 文件 |
| --- | --- |
| 安裝、啟動平台與獨立 ComfyUI、首次生成、本機存取 | [安裝與日常操作](setup-and-operations.md) |
| 使用選用的 Docker 本機部署 | [Docker 部署與原生環境差異](docker.md) |
| 停機備份、唯讀盤點及還原 | [完整資料備份](data-backup.md) |
| 認識頁面入口與首次使用指引 | [導覽與能力狀態](frontend-api.md#navigation) |
| 查詢任務、判讀請求狀態與匯出診斷 | [診斷與追蹤](diagnostics.md) |
| 保留尚未保存的編輯 | [未保存內容與離頁保護](frontend-api.md#unsaved-changes) |

## 創作、作品與比較實驗

| 要做的事 | 文件 |
| --- | --- |
| 上傳及管理素材、進行 Checkpoint 單張圖生圖 | [參考素材與圖生圖](models/reference-workflows.md) |
| 遮罩修補、保存筆畫及內側羽化 | [局部編輯](inpainting.md)、[v2 羽化與 CPU 合成預覽](inpainting.md#inner-feather) |
| 試用固定 SDXL 專用修補 | [Fooocus v3 的來源、限制與操作](fooocus-inpainting.md) |
| Canny 引導、保存同次原邊緣、預覽來源 | [Canny 結構參考](controlnet.md)、[近似 CPU 預覽](controlnet.md#cpu-preview) |
| 使用姿勢或深度條件 | [SDXL Pose／Depth v3](structure-reference.md) |
| 使用單張畫風或角色外觀參考 | [IPAdapter SDXL 專用流程](models/ipadapter-reference.md) |
| 匯出、預覽與匯入一般創作設定 | [創作設定交換](creation-settings-transfer.md) |
| 了解專用流程尚未支援的草稿、交換及比較 | [專用格式能力與設計邊界](specialized-workflow-formats.md) |
| 收藏、筆記、封存、並排及人工評分 | [作品庫](artwork-library.md)、[比較與評分](artwork-library.md#comparison-and-ratings) |
| 建立固定案例與參數方案 | [比較方案](experiment-plans.md)、[單案例實機工具](illustration-suite.md) |
| 保存、匯入及手動執行比較組 | [保存與匯入](experiment-plans.md#storage-and-import)、[任務與作品關聯](experiment-plans.md#runs-and-artworks) |
| 下載完整比較結果 | [結果報告](experiment-plans.md#result-reports) |
| 規劃動漫畫風與角色驗證 | [圖片分組、品質判斷與訓練界線](anime-style-development.md) |
| 簡易模式現況、動漫範例與首次成功體驗規劃 | [簡易創作與範例模板改善方案（操作與來源追溯已實作）](simple-creation-plan.md) |

## 模型與 FLUX

| 主題 | 文件 |
| --- | --- |
| Checkpoint 固定來源與選型 | [Animagine XL 4.0 Opt](models/animagine-xl-4.0-opt.md)；[Pony manifest](../models/pony-v6-xl.json)、[Animagine manifest](../models/animagine-xl-4.0-opt.json) |
| LoRA 管理、順序、雙強度與實測匹配 | [LoRA 模型庫](models/lora-library.md)、[有序串接](models/lora-library.md#ordered-lora)、[歷史條件查詢](models/lora-library.md#historical-evidence) |
| 像素畫 LoRA 的格式相容副本 | [固定來源與轉換限制](models/pixel-art-lora-sdxl.md) |
| FLUX 硬體前置判斷 | [RTX 3060、量化／卸載與 GGUF 流程差異](models/flux-rtx3060-planning.md) |
| FLUX 安裝、來源及快速預檢 | [固定四元件安裝與完整驗檔](models/flux-installation.md)、[來源選型歷史](models/flux-installation.md#source-selection) |
| FLUX 元件庫、純文生圖與失敗復原 | [專用工作流程](models/flux-workflow.md)、[元件庫](models/flux-workflow.md#components)、[平台生成與驗收工具](models/flux-workflow.md#generation-acceptance) |
| FLUX 固定精度、卸載與資源觀察 | [獨立原生節點觀察工具](models/flux-runtime-observation.md) |
| FLUX LoRA／原圖重繪 | [獨立擴充流程](models/flux-extensions.md) |
| Pony 授權與依賴 | [固定修訂查核](models/pony-v6-xl-license.md)、[M01 作者聲明與元件指紋補查](models/pony-v6-xl-license-followup-20261026.md) |
| FLUX 逐元件條款與來源鏈 | [F02 查核](models/flux-component-licenses.md)、[M02 編碼器發布與轉換追查](models/flux-encoder-lineage-followup-20261026.md) |

授權標籤、手動登記、檔案完整 hash、發布者來源鏈及實機載入各有不同證明範圍；未核實的缺口以對應文件及 ROADMAP 為準。

## 訓練與資料審查

| 階段 | 文件 |
| --- | --- |
| 決定訓練目標與品質驗收 | [T01 需求與範圍](training/requirements.md) |
| 建立清單、分割、審查與匯出資料包 | [T02 資料契約與 CLI](training/dataset-contract.md) |
| 查閱固定上游 trainer／caption／dataset 介面 | [工具介面研究](training/tool-interface-research.md) |
| 準備獨立環境、啟動、停止與新 run 續訓 | [T03 訓練 runtime](training/runtime.md) |
| 安裝產物、回登來源與建立固定評估 | [T04 產物與品質關卡](training/artifacts.md) |
| 從網頁完成四階段操作 | [訓練工作區](training/workspace.md)、[缺項導覽](training/workspace.md#t07-缺項導覽)、[訓練與產物](training/workspace.md#t06-本機訓練與產物)、[報告](training/workspace.md#t08-訓練報告) |

## 系統資訊、架構與開發

| 主題 | 文件 |
| --- | --- |
| 架構、資料流、應用程式工廠及測試隔離 | [架構](architecture.md) |
| HTTP 邊界、取消、原請求恢復與前端狀態 | [前端 API 契約](frontend-api.md) |
| 平台、引擎裝置與版本來源 | [執行裝置](execution-device.md)、[環境版本與效能條件](runtime-versions.md) |
| 任務耗時、背景取樣及峰值限制 | [任務量測](job-measurements.md) |
| 目錄、磁碟空間與開啟資料夾 | [儲存空間總覽](architecture.md#storage-capacity) |
| 清單成長與分頁相容性 | [分頁契約與基準](list-pagination.md) |
| 檢查命令、隔離瀏覽器、格式與靜態規則 | [品質檢查與維護](quality-checks.md) |
| 專案協作與需求釐清規則 | [AGENTS](../AGENTS.md)、[必要時的需求澄清](../REQUIREMENTS.md) |

## 介面規劃與桌面驗收

| 要查閱的內容 | 文件 |
| --- | --- |
| 視覺規範與元件狀態 | [UI 規範](ui-redesign/PLAN.md#visual-guidelines) |
| 原始參考與重設計目標 | [互動 preview](ui-redesign/preview.html)、[規劃](ui-redesign/PLAN.md) |
| 正式版既有能力及保留範圍 | [功能清單](ui-redesign/FEATURE-INVENTORY.md) |
| 實作落點、已整合行為與必要差異 | [整合說明](ui-redesign/INTEGRATION-NOTES.md) |
| 主要流程、各分類／階段及三種桌面尺寸的驗收 | [統一驗收紀錄](ui-redesign/ACCEPTANCE.md) |
| 需要後端能力、仍未完成的工作 | [後端能力待辦](ui-redesign/BACKEND-CAPABILITIES-BACKLOG.md) |

## 實機與歷史證據

實測只適用於文件列出的日期、來源 hash、模型、硬體與參數。以下分開列出 GPU、CPU／HTTP、合成資料與介面證據；完成技術流程不等於品質通過，也不代表其他主機已完成相同驗收。原始 runtime、權重與使用者圖片不在 Git，備份範圍依各文件。

### Checkpoint、LoRA 與影像流程

| 證據範圍 | 獨立紀錄 |
| --- | --- |
| RTX 3060 基礎文生圖 | [Pony V6 XL](validation/pony-v6-xl-rtx3060.md)、[Animagine 4.0 Opt](validation/animagine-xl-4-0-opt-rtx3060.md) |
| 單一 LCM LoRA | [Pony](validation/pony-lcm-rtx3060.md)、[Animagine](validation/animagine-lcm-rtx3060.md) |
| 多 LoRA 與品質條件 | [原 4 步載入](validation/animagine-multi-lora-rtx3060.md)、[8 步順序比較](validation/animagine-multi-lora-quality-rtx3060.md)、[單一 LoRA 強度／seed](validation/animagine-style-strength-rtx3060.md)、[更多畫風矩陣](validation/style-matrix-20261023.md) |
| 固定案例與跨模型觀察 | [通用插畫四案例](validation/general-illustration-suite-rtx3060.md)、[動漫品質基準](validation/anime-baseline-20261023.md) |
| 圖生圖及 denoise 比較 | [Checkpoint 圖生圖](validation/checkpoint-image2image-rtx3060.md)、[兩模型比較與關聯](validation/image-comparison-rtx3060.md) |
| 局部修補 | [一般 v1](validation/checkpoint-inpaint-rtx3060.md)、[內側羽化 v2](validation/inpaint-feather-rtx3060.md)、[Fooocus v3 與品質限制](validation/fooocus-inpainting-20261023.md) |
| Canny 原生條件及 CPU 差異 | [v1](validation/checkpoint-canny-rtx3060.md)、[v2 同次邊緣](validation/canny-edges-rtx3060.md)、[CPU／GPU 預覽比對](validation/canny-preview-rtx3060.md)、[Pony v2 有序 LoRA](validation/pony-canny-v2-20261023.md) |
| 單張畫風／角色參考 | [原圖片用途與分組](validation/reference-inputs-20261023.md)、[12 組 adapter 實測](validation/reference-adapter-20261023.md) |
| Pose／Depth | [流程中的實測與限制](structure-reference.md#驗收及限制)、[可解析證據](validation/structure-reference-20261023.json) |
| 指定執行中任務停止 | [RTX 3060 停止與保存](validation/running-stop-rtx3060.md) |

### FLUX、裝置與資源

| 證據範圍 | 獨立紀錄 |
| --- | --- |
| FLUX 早期介面與缺權重拒絕，非 GPU 出圖 | [2026-10-05 整合](validation/flux-integration.md) |
| FLUX 四元件實際安裝及離線完整驗檔 | [F01](validation/flux-installation-20261025.md) |
| FLUX 原生節點精度／卸載與取樣 | [F02 RTX 3060 固定配置](validation/flux-runtime-20261025.md) |
| FLUX 平台 HTTP、保存、離線與受控 CUDA OOM | [F03](validation/flux-generation-20261025.md) |
| FLUX 固定 LoRA／圖生圖四案例 | [F04](validation/flux-extensions-20261025.md) |
| 執行裝置回報與 CPU 模式 | [E01](validation/execution-device-20261022.md) |
| 原引擎連續取樣，非任務專用峰值 | [E05](validation/resource-sampling-20261023.md) |
| RTX 4080 基本流程 | [E02 八個流程](validation/rtx4080-workflows-20261026.md) |
| 兩機相同配置與獨立較高負載 | [E03](validation/hardware-comparison-20261026.md) |
| 推論與合成訓練資源分開登記 | [E04](validation/hardware-resources-20261026.md) |
| Pony／FLUX 來源查核的機器可讀證據 | [M01](validation/pony-license-audit-20261026.json)、[M02](validation/flux-encoder-audit-20261026.json)；結論見上方各授權文件 |

### 訓練、平台與介面

| 證據範圍 | 獨立紀錄 |
| --- | --- |
| 訓練需求與資料契約，非作者圖訓練 | [T01](validation/training-requirements-20261023.md)、[T02](validation/training-dataset-20261023.md) |
| 自製幾何資料的訓練與產物技術驗收 | [T03](validation/training-runtime-20261025.md)、[T04](validation/training-artifacts-20261025.md) |
| 訓練工作區分階段介面與有限實機 | [T05 審查](validation/training-workspace-20261025.md#t05-review)、[T06 控制](validation/training-workspace-20261025.md#t06-control)、[T07 導覽](validation/training-workspace-20261025.md#t07-navigation)、[T08 報告](validation/training-workspace-20261025.md#t08-report) |
| 原生與容器部署，各自的能力邊界 | [D01 本機存取](validation/local-deployment-20261025.md)、[D02 Docker 與持久化](validation/docker-deployment-20261025.md) |
| 遮罩瀏覽器操作與原請求故障恢復 | [V01 畫布／PNG](validation/mask-editor-20261023.md)、[V02 v1／v2 恢復](validation/inpaint-recovery-20261023.md) |
| 作品、比較及設定交換的介面補驗 | [V03 作品庫](validation/artwork-library-20261023.md)、[V04 比較／量測](validation/comparison-measurements-20261023.md)、[V05 實際設定下載](validation/settings-transfer-20261023.md) |
| 模型／取樣比較軸與版本契約 | [R06](validation/extended-comparisons-20261023.md) |
| 視覺、無障礙與系統目錄操作 | [V06](validation/ui-accessibility-20261023.md)、[目錄／磁碟與開啟資料夾](validation/storage-overview-20261024.md) |
| 格式與高風險維護回歸 | [Q10](validation/maintenance-20261023.md) |
| Windows CI 的不同失敗與修正 | [TEMP 別名及瀏覽器分批歷史](validation/windows-ci.md) |

## 研究與歷史

| 用途 | 文件 |
| --- | --- |
| 查閱上游原碼、採用決策、整合邊界與未整合候選 | [上游研究與重用評估](research/upstream-reuse.md) |
| 追溯特定日期的程式庫檢查 | [2026-10-27 稽核](history/codebase-audit-20261027.md)、[2026-10-03 檢查](../CHANGELOG.md#review-2026-10-03) |
| 對照整理前的舊入口與完整歷史 | [固定舊版 README](../CHANGELOG.md#readme-before-q01)、[原始 CHANGELOG、狀態快照及驗收對照](../CHANGELOG.md#history) |

歷史文件中的命令、限制及測試數只描述當時狀態；日常操作回到本索引列出的主要文件，完成歷史及剩餘工作分別查 CHANGELOG 與 ROADMAP。
