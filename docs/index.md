# 文件索引

現行入口是 [README](../README.md)，待辦與驗收條件以 [ROADMAP](../ROADMAP.MD) 為準；歷史測試數不表示目前所有功能已驗收。

## 安裝與維護

- [安裝、首次生成、埠與備份](setup-and-operations.md)、[架構與資料流](architecture.md)、[UI 規範](ui-guidelines.md)
- [應用程式工廠、配置與測試隔離](application-factory.md)
- [前端 HTTP 契約、取消與原請求恢復](frontend-api.md)
- [四工作台未保存內容與離頁保護](unsaved-changes.md)
- [品質檢查、隔離瀏覽器回歸與 CI](quality-checks.md)
- [清單分頁、相容策略與資料成長基準](list-pagination.md)
- [停機完整備份、唯讀盤點與新目錄還原](data-backup.md)
- [網址導覽、首次使用指引與能力狀態](navigation.md)
- [請求／任務追蹤、狀態分離與診斷預覽匯出](diagnostics.md)
- [格式、靜態檢查與高風險流程維護規則](maintenance.md)
- [裝置回報](execution-device.md)、[環境版本](runtime-versions.md)、[效能條件](execution-context.md)、[量測](job-measurements.md)

## 創作與作品

| 工作 | 說明 |
| --- | --- |
| 一般設定交換 | [精確 JSON](creation-settings-transfer.md) |
| 圖生圖／素材 | [參考流程與版本](models/reference-workflows.md) |
| 局部編輯 | [遮罩修補](inpainting.md)、[羽化](inpaint-feather.md) |
| Canny | [ControlNet 與原邊緣](controlnet.md)、[CPU 預覽](canny-preview.md) |
| 作品整理 | [收藏／筆記／封存](artwork-library.md)、[比較與人工評分](artwork-comparison.md) |
| 實驗 | [固定案例](illustration-suite.md)、[比較方案](experiment-plans.md)、[保存／匯入](experiment-storage.md)、[任務關聯](experiment-runs.md)、[結果報告](comparison-report.md) |

## 模型與執行環境

- [Animagine 來源與預設](models/animagine-xl-4.0-opt.md)
- [LoRA 庫](models/lora-library.md)、[多 LoRA](models/multi-lora-workflow.md)、[有序證據](models/ordered-lora-evidence.md)
- [FLUX 來源／限制](models/flux1-schnell.md)、[元件庫](models/flux-components.md)、[專用流程](models/flux-workflow.md)
- [Pony manifest](../models/pony-v6-xl.json)、[Animagine manifest](../models/animagine-xl-4.0-opt.json)

## 實機與歷史證據

實測限於所列模型／hash／硬體／參數與日期；原始 runtime 報告、權重與作品不在 Git，備份依各紀錄。

- [Pony／RTX 3060](validation/pony-v6-xl-rtx3060.md)、[Animagine／RTX 3060](validation/animagine-xl-4-0-opt-rtx3060.md)
- [圖生圖](validation/checkpoint-image2image-rtx3060.md)、[修補](validation/checkpoint-inpaint-rtx3060.md)、[羽化](validation/inpaint-feather-rtx3060.md)
- [Canny](validation/checkpoint-canny-rtx3060.md)、[邊緣](validation/canny-edges-rtx3060.md)、[預覽](validation/canny-preview-rtx3060.md)
- [風格強度](validation/animagine-style-strength-rtx3060.md)、[多 LoRA 品質](validation/animagine-multi-lora-quality-rtx3060.md)、[四案例](validation/general-illustration-suite-rtx3060.md)
- [停止](validation/running-stop-rtx3060.md)、[E01](validation/execution-device-20261022.md)、[FLUX 範圍](validation/flux-integration.md)
- [全部驗收目錄](validation)、[CHANGELOG](../CHANGELOG.MD)、[2026-10-03 檢查](review-2026-10-03.md)
- [整理前 README 全文](history/readme-before-q01-20261022.md)：舊限制與命令僅供追溯。
