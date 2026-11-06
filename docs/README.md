# 文件總覽

[專案 README](../README.md)提供快速開始與能力摘要；本頁負責分類與導航。未完成工作集中於 [ROADMAP](planning/roadmap.md)，已完成變更與當時條件記於 [CHANGELOG](../CHANGELOG.md)。

第一次操作先讀[離線圖文教學](guide/index.html)；安裝、啟停與搬機以[安裝與日常操作](operations/setup-and-operations.md)為準。

## 文件分類

| 位置 | 收錄內容 |
| --- | --- |
| [operations/](operations/) | 安裝、部署、診斷、備份與還原 |
| [features/](features/) | 創作、圖片流程、作品庫、設定交換與實驗操作 |
| [development/](development/) | 架構、前端契約、執行觀察、品質與驗收工具 |
| [planning/](planning/) | 統一 ROADMAP、簡易創作及動漫畫風方案 |
| [contributing/](contributing/) | 按需閱讀的需求釐清與協作規則維護指南 |
| [models/](models/)／[training/](training/) | 模型來源、專用流程與訓練契約 |
| [guide/](guide/)／[ui-redesign/](ui-redesign/) | 圖文教學與素材、桌面 UI 規格及驗收 |
| [validation/](validation/README.md) | 依功能分類的歷史驗收索引與機器可讀證據 |
| [research/](research/)／[history/](history/) | 上游研究、採用決策與歷次稽核 |

## 安裝與日常操作

| 需求 | 文件 |
| --- | --- |
| Windows 平台／ComfyUI、首次使用、本機存取與搬機 | [安裝與日常操作](operations/setup-and-operations.md) |
| 選用 Docker 的差異與資料卷 | [Docker 部署](operations/docker.md) |
| 停機盤點、備份、驗證與離線還原 | [完整資料備份](operations/data-backup.md) |
| 任務追蹤與可預覽的診斷匯出 | [診斷](operations/diagnostics.md) |

## 創作、作品與比較實驗

| 需求 | 文件 |
| --- | --- |
| 提示詞中文轉英文與手動套用 | [本機轉換器](features/prompt-converter.md) |
| 圖生圖、局部修補與 Fooocus | [參考素材](models/reference-workflows.md)、[修補與羽化](features/inpainting.md)、[Fooocus](features/fooocus-inpainting.md) |
| Canny、Pose／Depth、畫風／角色參考 | [Canny](features/controlnet.md)、[結構參考](features/structure-reference.md)、[IPAdapter](models/ipadapter-reference.md) |
| 創作設定的匯入、預覽與匯出 | [設定交換](features/creation-settings-transfer.md)、[專用格式限制](development/specialized-workflow-formats.md) |
| 作品整理、並排與人工評分 | [作品庫](features/artwork-library.md#comparison-and-ratings) |
| 保存方案、逐組執行與結果報告 | [比較實驗](features/experiment-plans.md) |
| 簡易模式配方與畫風任務 | [交付方案與待驗收清單](planning/simple-creation-plan.md) |

## 模型與 FLUX

| 主題 | 文件 |
| --- | --- |
| Checkpoint 與有序 LoRA | [Animagine 固定來源](models/animagine-xl-4.0-opt.md)、[LoRA 模型庫](models/lora-library.md)、[像素格式轉換](models/pixel-art-lora-sdxl.md) |
| FLUX 硬體前置判斷與固定元件 | [3060 規劃](models/flux-rtx3060-planning.md)、[安裝與完整驗檔](models/flux-installation.md) |
| FLUX 平台工作流程與擴充 | [Schnell 流程](models/flux-workflow.md)、[LoRA／圖生圖](models/flux-extensions.md)、[原生節點觀察](models/flux-runtime-observation.md) |
| Pony 授權與依賴 | [固定來源查核](models/pony-v6-xl-license.md)、[發布者聲明補查](models/pony-v6-xl-license-followup-20261026.md) |
| FLUX 逐元件來源與轉換鏈 | [條款記錄](models/flux-component-licenses.md)、[編碼器來源補查](models/flux-encoder-lineage-followup-20261026.md) |

安裝、完整 hash、發布來源鏈與實機載入各有不同證明範圍；未核實的缺口由上述來源文件與 [ROADMAP](planning/roadmap.md)維護。

## 訓練與資料審查

| 階段 | 文件 |
| --- | --- |
| 目標、品質與獨立保留圖 | [訓練需求](training/requirements.md)、[動漫畫風與圖片分組計畫](planning/anime-style-development.md) |
| 清單、分割、審查與不可變資料包 | [資料契約](training/dataset-contract.md)、[固定上游介面研究](training/tool-interface-research.md) |
| 準備、開始、停止與新 run 續訓 | [獨立 runtime](training/runtime.md) |
| 安裝產物、回登與固定評估 | [產物契約](training/artifacts.md) |
| 網頁四階段、缺項導覽與報告 | [訓練工作區](training/workspace.md) |

## 系統資訊、架構與開發

| 主題 | 文件 |
| --- | --- |
| 模組、應用程式工廠、持久化與提交邊界 | [架構](development/architecture.md) |
| HTTP、導覽、取消與未保存保護 | [前端契約](development/frontend-api.md) |
| 版本快照、即時裝置、耗時與連續取樣 | [執行環境與任務量測](development/runtime-observability.md) |
| 清單成長、分頁與量測預算 | [分頁契約](development/list-pagination.md) |
| 品質入口、格式、靜態與瀏覽器回歸 | [品質檢查](development/quality-checks.md) |
| 單案例實機驗收工具 | [固定插畫與動漫測試集](development/illustration-suite.md) |
| Agent 協作與按需指南 | [AGENTS](../AGENTS.md)、[需求釐清](contributing/requirements-clarification.md)、[規則維護](contributing/agent-maintenance.md) |

## 介面規劃與桌面驗收

[桌面規格](ui-redesign/PLAN.md)與[原始 preview](ui-redesign/preview.html)定義外觀；[功能保留表](ui-redesign/FEATURE-INVENTORY.md)記錄保留邊界，[整合說明](ui-redesign/INTEGRATION-NOTES.md)解釋落點與差異，[桌面矩陣／連續旅程](ui-redesign/ACCEPTANCE.md)保存實際驗收。

N05／N06／N07 的狀態、設計與完成條件集中於 [ROADMAP 的 UI 能力待辦](planning/roadmap.md#backend-backlog)，由同一處維護。

## 實機與歷史證據

依領域查閱[驗收紀錄索引](validation/README.md)：Checkpoint／LoRA／圖片流程、FLUX／硬體、訓練／部署與介面。日期、來源 hash、硬體與參數限定每份證據的適用範圍；歷史通過數不代表目前全量驗收。

## 研究與歷史

[上游研究與採用決策](research/upstream-reuse.md)、[2026-10-27 稽核](history/codebase-audit-20261027.md)及 [CHANGELOG](../CHANGELOG.md)分別保存研究依據、當時稽核與完成紀錄。原始 runtime、權重與使用者圖片依備份流程另存。

## 文件維護

- 根目錄 README 保持快速開始與摘要，詳細操作及契約由各分類主題文件維護；本頁只提供分類與入口。
- 同一能力的目前規則在主題文件維護；待辦與完成條件放 ROADMAP，完成結果放 CHANGELOG，當時的測試條件與限制保存在 validation。
- 新文件依用途放入上表分類。移動或合併時同步更新 Markdown／HTML 連結及章節錨點；保留歷史驗收的日期、數據與限制。
- 模型 manifest、驗收 JSON、教學素材與 preview 有程式或來源指紋引用；調整目錄前先核對消費者。這些實體路徑應與消費者一同維護。
- 啟動器、依賴清單、Docker／Compose 與工具自動讀取的設定留在既有位置；變更它們須連同實際呼叫者驗證。
