# Canny 送出前 CPU 預覽

`POST /api/control/preview` 接受已保存的 `image_asset_id`、`reference_resize`（fit／stretch）、`width`、`height`、`canny_low`、`canny_high`，拒絕其他欄位。無需 checkpoint、ControlNet、引擎位址或任務 UUID。

輸入先使用與 Canny 生成相同的 Pillow 縮放／白色背景前處理，校驗素材大小與 SHA256。預覽最多 1,048,576 像素，寬高 64–8192 且為 8 的倍數；低／高閾值為原生浮點值，0.01 ≤ low < high ≤ 0.99。此資源限制僅影響 CPU 預覽，不改變生成的 1600 萬像素上限。

固定使用本專案 `runtime/ComfyUI/.venv` Python 與 `scripts/preview_canny.py`，不接受執行路徑、指令或外部圖片。對照已稽核 `comfy_extras/nodes_canny.py` SHA256（正規化 CRLF）：`5efd352d92d7749b7b9734a1676fee18f4431d44a8e9477822a7a8f38ad26051`。原碼改變或本地環境不存在回 503，生成端點仍獨立可用。

worker 呼叫同一環境的 `kornia.filters.canny`，float32 CPU、相同 BCHW 通道轉換與 RGB 二值輸出。它不匯入 ComfyUI、不載入模型、不連線、不使用 CUDA、不寫入檔案。這是本機近似預覽，**不是原任務輸出，也不保證與任何 GPU／遠端引擎逐像素相同**。原任務節點 16 的邊緣圖仍須透過既有明確匯入操作保存，預覽不會填補歷史。

每次僅允許一個預覽 worker，忙碌回 409；45 秒超時停止並回收子程序。stdin／stdout 有上限，stderr 不對外揭露，輸出需通過版本、輸入與輸出 hash、尺寸與二值 RGB 校驗。HTTP 斷線不提前釋放 worker 鎖；背景工作仍在上限內結束，前端必須忽略過期回覆。

回應為 `image/png`，`Cache-Control: no-store`，含 `X-Atelier-SHA256`、Width／Height 及 base64 JSON `X-Atelier-Canny-Provenance`。來源包含 method `comfy-kornia-canny-cpu-v1`、device、dtype、native SHA256、實際 Torch／Kornia／Pillow 版本、素材與前處理快照、閾值、尺寸、輸入／輸出 hash。預覽沒有資料庫紀錄，重新預覽使用目前安裝版本。
