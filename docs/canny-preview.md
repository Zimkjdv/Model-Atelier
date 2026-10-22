# Canny 送出前 CPU 預覽

`POST /api/control/preview` 接受已保存的 `image_asset_id`、`reference_resize`（fit／stretch）、`width`、`height`、`canny_low`、`canny_high`，拒絕其他欄位。無需 checkpoint、ControlNet、引擎位址或任務 UUID。

輸入先使用與 Canny 生成相同的 Pillow 縮放／白色背景前處理，校驗素材大小與 SHA256。預覽最多 1,048,576 像素，寬高 64–8192 且為 8 的倍數；低／高閾值為原生浮點值，0.01 ≤ low < high ≤ 0.99。此資源限制僅影響 CPU 預覽，不改變生成的 1600 萬像素上限。

固定使用本專案 `runtime/ComfyUI/.venv` Python 與 `scripts/preview_canny.py`，不接受執行路徑、指令或外部圖片。對照已稽核 `comfy_extras/nodes_canny.py` SHA256（正規化 CRLF）：`5efd352d92d7749b7b9734a1676fee18f4431d44a8e9477822a7a8f38ad26051`。原碼改變或本地環境不存在回 503，生成端點仍獨立可用。

worker 呼叫同一環境的 `kornia.filters.canny`，float32 CPU、相同 BCHW 通道轉換與 RGB 二值輸出。它不匯入 ComfyUI、不載入模型、不連線、不使用 CUDA、不寫入檔案。這是本機近似預覽，**不是原任務輸出，也不保證與任何 GPU／遠端引擎逐像素相同**。原任務節點 16 的邊緣圖仍須透過既有明確匯入操作保存，預覽不會填補歷史。

每次僅允許一個預覽 worker，忙碌回 409；45 秒超時停止並回收子程序。stdin／stdout 有上限，stderr 不對外揭露，輸出需通過版本、輸入與輸出 hash、尺寸與二值 RGB 校驗。HTTP 斷線不提前釋放 worker 鎖；背景工作仍在上限內結束，前端必須忽略過期回覆。

回應為 `image/png`，`Cache-Control: no-store`，含 `X-Atelier-SHA256`、Width／Height 及 base64 JSON `X-Atelier-Canny-Provenance`。來源包含 method `comfy-kornia-canny-cpu-v1`、device、dtype、native SHA256、實際 Torch／Kornia／Pillow 版本、素材與前處理快照、閾值、尺寸、輸入／輸出 hash。預覽沒有資料庫紀錄，重新預覽使用目前安裝版本。

## 工作台操作與瀏覽器驗收（2026-10-22）

在「創作工作台 → Canny 結構參考」選擇已保存原圖，設定尺寸、縮放與閾值，再按「預覽 Canny 邊緣」。不依賴生成區的 checkpoint／ControlNet／引擎前置條件；預覽失敗不改變原表單或生成設定。修改圖像相關輸入、素材 SHA256、來源可用狀態時即清除預覽；提示詞、seed、控制強度不影響邊緣圖。

前端只傳六個預覽欄位，檢查 base64 版本來源、原素材 hash／ID、前處理／閾值／尺寸、RGB PNG 與 SHA256；PNG 最多 16 MiB、錯誤內容最多 64 KiB。KeepAlive 離開、卸載或參數變動會取消請求、忽略過期回覆並回收 Blob URL，重新進入保留表單但不保留預覽。

實際 IAB 離線驗收：ComfyUI 未啟動、未選 checkpoint／控制模型，320×192 漸層幾何素材輸出 768×512 fit 與 stretch 預覽；0.4→0.2 閾值與縮放變動清除舊圖，計算途中變更不顯示過期結果。0.9／0.8 非法閾值阻止預覽；切換工作台保留表單並清除預覽。390×844 視窗無橫向溢出（innerWidth 390、scrollWidth 375）。截圖在忽略的 `runtime/canny-preview-mobile-20261022.jpg`。

驗收使用 `runtime/canny-preview-live-data-20261022`：複製四份既有 Canny 任務／作品後增加一張測試素材，共 2 素材／4 任務／4 作品；預覽沒有增加任務或作品。正式資料 settings 指紋保持 `31af66ed1db203c808bee110c1007a8307ae23867df29b259636f0837502a6eb`。
