# 驗收紀錄索引

實測只適用於文件列出的日期、來源 hash、模型、硬體與參數。以下分開列出 GPU、CPU／HTTP、合成資料與介面證據；完成技術流程不等於品質通過，也不代表其他主機已完成相同驗收。原始 runtime、權重與使用者圖片不在 Git，備份範圍依各文件。

### Checkpoint、LoRA 與影像流程

| 證據範圍 | 獨立紀錄 |
| --- | --- |
| RTX 3060 基礎文生圖 | [Pony V6 XL](pony-v6-xl-rtx3060.md)、[Animagine 4.0 Opt](animagine-xl-4-0-opt-rtx3060.md) |
| 單一 LCM LoRA | [Pony](pony-lcm-rtx3060.md)、[Animagine](animagine-lcm-rtx3060.md) |
| 多 LoRA 與品質條件 | [原 4 步載入](animagine-multi-lora-rtx3060.md)、[8 步順序比較](animagine-multi-lora-quality-rtx3060.md)、[單一 LoRA 強度／seed](animagine-style-strength-rtx3060.md)、[更多畫風矩陣](style-matrix-20261023.md) |
| 固定案例與跨模型觀察 | [通用插畫四案例](general-illustration-suite-rtx3060.md)、[動漫品質基準](anime-baseline-20261023.md) |
| 圖生圖及 denoise 比較 | [Checkpoint 圖生圖](checkpoint-image2image-rtx3060.md)、[兩模型比較與關聯](image-comparison-rtx3060.md) |
| 局部修補 | [一般 v1](checkpoint-inpaint-rtx3060.md)、[內側羽化 v2](inpaint-feather-rtx3060.md)、[Fooocus v3 與品質限制](fooocus-inpainting-20261023.md) |
| Canny 原生條件及 CPU 差異 | [v1](checkpoint-canny-rtx3060.md)、[v2 同次邊緣](canny-edges-rtx3060.md)、[CPU／GPU 預覽比對](canny-preview-rtx3060.md)、[Pony v2 有序 LoRA](pony-canny-v2-20261023.md) |
| 單張畫風／角色參考 | [原圖片用途與分組](reference-inputs-20261023.md)、[12 組 adapter 實測](reference-adapter-20261023.md) |
| Pose／Depth | [流程中的實測與限制](../features/structure-reference.md#驗收及限制)、[可解析證據](structure-reference-20261023.json) |
| 指定執行中任務停止 | [RTX 3060 停止與保存](running-stop-rtx3060.md) |

### FLUX、裝置與資源

| 證據範圍 | 獨立紀錄 |
| --- | --- |
| FLUX 早期介面與缺權重拒絕，非 GPU 出圖 | [2026-10-05 整合](flux-integration.md) |
| FLUX 四元件實際安裝及離線完整驗檔 | [F01](flux-installation-20261025.md) |
| FLUX 原生節點精度／卸載與取樣 | [F02 RTX 3060 固定配置](flux-runtime-20261025.md) |
| FLUX 平台 HTTP、保存、離線與受控 CUDA OOM | [F03](flux-generation-20261025.md) |
| FLUX 固定 LoRA／圖生圖四案例 | [F04](flux-extensions-20261025.md) |
| 執行裝置回報與 CPU 模式 | [E01](execution-device-20261022.md) |
| 原引擎連續取樣，非任務專用峰值 | [E05](resource-sampling-20261023.md) |
| RTX 4080 基本流程 | [E02 八個流程](rtx4080-workflows-20261026.md) |
| 兩機相同配置與獨立較高負載 | [E03](hardware-comparison-20261026.md) |
| 推論與合成訓練資源分開登記 | [E04](hardware-resources-20261026.md) |
| Pony／FLUX 來源查核的機器可讀證據 | [M01](pony-license-audit-20261026.json)、[M02](flux-encoder-audit-20261026.json)；結論見[模型來源文件](../README.md#模型與-flux) |

### 訓練、平台與介面

| 證據範圍 | 獨立紀錄 |
| --- | --- |
| 訓練需求與資料契約，非作者圖訓練 | [T01](training-requirements-20261023.md)、[T02](training-dataset-20261023.md) |
| 自製幾何資料的訓練與產物技術驗收 | [T03](training-runtime-20261025.md)、[T04](training-artifacts-20261025.md) |
| 訓練工作區分階段介面與有限實機 | [T05 審查](training-workspace-20261025.md#t05-review)、[T06 控制](training-workspace-20261025.md#t06-control)、[T07 導覽](training-workspace-20261025.md#t07-navigation)、[T08 報告](training-workspace-20261025.md#t08-report) |
| 原生與容器部署，各自的能力邊界 | [D01 本機存取](local-deployment-20261025.md)、[D02 Docker 與持久化](docker-deployment-20261025.md) |
| 遮罩瀏覽器操作與原請求故障恢復 | [V01 畫布／PNG](mask-editor-20261023.md)、[V02 v1／v2 恢復](inpaint-recovery-20261023.md) |
| 作品、比較及設定交換的介面補驗 | [V03 作品庫](artwork-library-20261023.md)、[V04 比較／量測](comparison-measurements-20261023.md)、[V05 實際設定下載](settings-transfer-20261023.md) |
| 模型／取樣比較軸與版本契約 | [R06](extended-comparisons-20261023.md) |
| 視覺、無障礙與系統目錄操作 | [V06](ui-accessibility-20261023.md)、[目錄／磁碟與開啟資料夾](storage-overview-20261024.md) |
| 格式與高風險維護回歸 | [Q10](maintenance-20261023.md) |
| Windows CI 的不同失敗與修正 | [TEMP 別名及瀏覽器分批歷史](windows-ci.md) |
