# 任務及作品環境版本（2026-10-05）

新任務通過必要節點檢查後、提交 GPU prompt 前，以原引擎 `/system_stats` 保存 `runtime_metadata`。查詢最多等待兩秒；HTTP 失敗、逾時、格式無效或超過 256 KiB 的回應保持未知，不因版本未知阻擋已通過驗證的流程。引擎與架構在等待後再次檢查；若原任務被其他程序更新，修訂檢查拒絕覆蓋及提交。

快照包含：

- schema 版本及提交前觀察時間。
- 已完整匹配的標準文生圖、圖生圖或 FLUX 流程規格 ID，以及完整 JSON 的 canonical SHA256、原生節點名稱。不能匹配完整文生圖模板的原始 API 流程使用 `checkpoint-api-workflow-v1`，不假裝為七節點模板。
- 平台 Python，以及 FastAPI、Starlette、Pydantic、HTTPX、Pillow、Uvicorn、WebSockets 的實際安裝版本；只來自平台 Python 程序。
- 原引擎回報的 ComfyUI、Python、PyTorch，以及指定 Comfy 套件的 `installed`／`required` 分開欄位。未知值使用 null；不保存完整環境變數、命令列或任意套件清單。

此端點沒有提供可靠 CUDA、驅動、Git revision 及各節點版本，這些欄位保持未知；不使用平台 GPU 診斷代替遠端引擎，也不從 PyTorch 的 `+cu130` 推定運行時 CUDA。自訂節點目前不能由這些提交流程使用。

SQLite 在原任務 `validating` 且快照尚未保存時，透過一次交易凍結版本。一般更新、取消、進度、歷史刷新不能改寫它。原 UUID 恢復在任何版本查詢前回傳舊任務，不重送；新作品直接複製原任務快照，重複匯入不更新。舊任務、作品與提交前驗證失敗紀錄沒有快照時保持未知，不回填。作品預覽及載入歷史設定可查看快照；原始任務 JSON 也保留它。

快照是提交前觀察，不能證明等待佇列後引擎未更新，也不保證跨版本／硬體逐像素重現。模型、LoRA、FLUX 元件及參考圖版本仍由各自的原始快照追溯。

驗收：固定 Animagine／LCM 在 RTX 3060 真實 GPU 任務 `6e767729-a4ab-49c8-9853-4e947ad58e6a`，作品 `1975697f-d9d0-5f71-b552-39d7c37e65ab` 保存 ComfyUI 0.34.0／引擎 Python 3.12.10／PyTorch 2.14.0+cu130／五個 Comfy 套件。引擎停止、平台重啟後，任務與作品快照完全相同，原圖、完整 JSON、精確 seed 及設定 GET 核對通過；瀏覽器離線預覽顯示上述版本及未知欄位。證據在本機 `runtime/style-live-data-20261005/runtime-snapshot.json` 與 `runtime/runtime-version-ui-20261005.png`；正式資料沒有新增生成紀錄。

修正 Windows Python 3.12 在並行建立目錄時，`Path.resolve` 偶爾保留 `\\?\` 前綴造成報告路徑誤拒絕；先解析實體路徑再正規化等價拼法，仍檢查 runtime 範圍及 symlink／junction。跨程序測試確保只有一個報告能授權生成，失敗也回收全部測試子程序。

365 項後端測試（364 通過、1 項既有 Windows 權限跳過），Vue 型別及正式建置通過，桌面瀏覽器已驗證。
