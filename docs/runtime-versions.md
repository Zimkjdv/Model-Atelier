# 任務及作品的執行環境快照

新任務通過必要節點檢查後、提交 GPU prompt 前，以原引擎 `/system_stats` 保存 `runtime_metadata`。查詢最多等待兩秒；HTTP 失敗、逾時、格式無效或超過 256 KiB 的回應保持未知，不因版本未知阻擋已通過驗證的流程。引擎與架構在等待後再次檢查；若原任務被其他程序更新，修訂檢查拒絕覆蓋及提交。

快照包含：

- schema 版本及提交前觀察時間。
- 已完整匹配的標準文生圖、圖生圖或 FLUX 流程規格 ID，以及完整 JSON 的 canonical SHA256、原生節點名稱。不能匹配完整文生圖模板的原始 API 流程使用 `checkpoint-api-workflow-v1`，不假裝為七節點模板。
- 平台 Python，以及 FastAPI、Starlette、Pydantic、HTTPX、Pillow、Uvicorn、WebSockets 的實際安裝版本；只來自平台 Python 程序。
- 原引擎回報的 ComfyUI、Python、PyTorch，以及指定 Comfy 套件的 `installed`／`required` 分開欄位。未知值使用 null；不保存完整環境變數、命令列或任意套件清單。

此端點沒有提供可靠 CUDA、驅動、Git revision 及各節點版本，這些欄位保持未知；不使用平台 GPU 診斷代替遠端引擎，也不從 PyTorch 的 `+cu130` 推定運行時 CUDA。R02 與 R01 的專用模板另允許固定介面的自訂節點，所需修訂與實際版本未知分開記錄，不接受任意節點圖。

SQLite 在原任務 `validating` 且快照尚未保存時，透過一次交易凍結版本。一般更新、取消、進度、歷史刷新不能改寫它。原 UUID 恢復在任何版本查詢前回傳舊任務，不重送；新作品直接複製原任務快照，重複匯入不更新。舊任務、作品與提交前驗證失敗紀錄沒有快照時保持未知，不回填。作品預覽及載入歷史設定可查看快照；原始任務 JSON 也保留它。

快照是提交前觀察，不能證明等待佇列後引擎未更新，也不保證跨版本／硬體逐像素重現。模型、LoRA、FLUX 元件及參考圖版本仍由各自的原始快照追溯。

<a id="execution-context"></a>

## 提交時效能條件

新任務的 runtime_metadata.execution_context（schema_version 1）在既有提交前觀察交易凍結；作品沿用同一份資料，原 UUID 恢復不重新探測或更新。舊紀錄沒有此欄位時保持未知，沒有資料庫遷移或回填。

快照包含推論 workload、流程 ID、尺寸／batch 的來源、取樣節點與設定、字串精確 seed、模型／元件版本與 SHA256、有序 LoRA 原快照。圖生圖／局部編輯／Canny 尺寸取自已凍結參考設定；未知流程不猜測幾何。硬體及耗時沿用同一提交階段既有的來源分離快照，完整 graph 保持原樣。

/system_stats.system.argv 僅保留允許清單中的精度及記憶體旗標；不保存完整命令列、路徑、token、旗標值或未識別選項。衝突旗標完整保留，不選出假定有效值。缺少／無效 argv 記為未回報；空清單代表沒有明示旗標，不能推定預設精度／卸載。

實際 dtype、實際卸載與冷／熱快取目前沒有可靠的逐任務回報，分別為 null／unknown；啟動設定不能代替執行證據。既有固定驗收文件另外保存觀察到的載入精度與冷／熱條件，與一般任務的未知狀態分開。此能力不驗證訓練需求、最低 VRAM、推論品質或新 GPU 相容性。

任務／作品的提交時引擎與依賴版本區塊顯示此快照，可隨原 JSON 下載。裝置是否明確不可用由[即時裝置回報](execution-device.md)判定；任務耗時與背景取樣則由[量測契約](job-measurements.md)管理，不以提交前條件冒充實際執行結果。

<a id="runtime-verification"></a>

## 歷史驗證與限制

2026-10-05 的固定 Animagine／LCM RTX 3060 任務 `6e767729-a4ab-49c8-9853-4e947ad58e6a` 與作品 `1975697f-d9d0-5f71-b552-39d7c37e65ab` 保存 ComfyUI 0.34.0、引擎 Python 3.12.10、PyTorch 2.14.0+cu130 與五個 Comfy 套件；引擎停止、平台重啟後，快照、原圖、完整 JSON、精確 seed 與設定 GET 保持相同。原隔離證據記錄位置為 `runtime/style-live-data-20261005/runtime-snapshot.json` 與 `runtime/runtime-version-ui-20261005.png`；它們是當時本機證據，不是目前環境版本或正式資料新增生成的聲明。

當時另修正 Windows Python 3.12 並行建立目錄偶爾保留 `\\?\` 前綴的等價路徑誤拒絕，仍解析實體位置並核對 runtime 範圍及 symlink／junction；跨程序測試核對只有一份報告可授權生成且失敗回收全部子程序。效能條件測試涵蓋精確 seed、有序 LoRA、素材流程尺寸、未知／衝突／私密 argv 與原 UUID 不重探測。歷史通過數見 [CHANGELOG](../CHANGELOG.md)，不能代替目前重跑或其他硬體的驗收。
