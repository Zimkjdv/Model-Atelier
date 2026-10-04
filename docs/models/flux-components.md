# FLUX 分離元件庫

2026-10-05：元件庫由選定 ComfyUI 的 `UNETLoader`、`DualCLIPLoader`、`VAELoader` 列舉 diffusion model、text encoder、VAE。四個生成依賴分別是主模型、CLIP-L、T5、VAE；两個 encoder 共用同一類模型庫。

- `GET /api/flux/components`：只讀目前引擎快照。
- `POST /api/flux/components/sync`：JSON `{ "engine_url": "http://127.0.0.1:8188" }`，三個載入節點全部成功後才原子發布；失敗保留上次完整清單及同步時間。
- `PUT /api/flux/components/metadata`：傳入 `engine_url`、`category`、`name`，及需要修改的版本、來源、架構、大小、SHA256、授權、備註。category 為 `diffusion_models`、`text_encoders` 或 `vae`。

清單及資料按引擎隔離。同步期間切换引擎回傳 409，不把舊回應發布至新引擎。移除模型保留登記資料並標記未列出，再出現時保留資料。

版本未登記時顯示未知；檔名、清單列出與手動 SHA256 均不代表已驗證檔案、架構、授權或 GPU 執行。固定下載計畫與實際元件庫分開；同步不下載模型，不套用本機磁碟資訊至遠端引擎。
