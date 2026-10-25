# F01：固定 FLUX 四元件安裝驗收

日期：2026-10-25。F01 完成來源存取、動態磁碟檢查、實際下載與四份完整 SHA256；沒有載入模型到 GPU、沒有訓練或生成。操作見 [安裝／驗檔](../models/flux-installation.md)，固定大小／hash 見 [manifest](../../models/flux1-schnell-plan.json)，本次摘要見 [可解析證據](flux-installation-20261025.json)。

使用者自行完成 Hugging Face 官方存取及本機 CLI 登入。登入前 BFL 主模型／VAE HEAD 401，公開編碼器 HEAD 200；工具沒有先下載公開編碼器。登入後固定四份來源均為 HEAD 200，沒有改用鏡像或 GGUF。來源完整修訂、大小及 SHA256 由既有固定登記再次驗證，任意來源或 hash 變更會被拒絕。

## 實際安裝與離線重驗

```powershell
.\.venv\Scripts\python.exe -m scripts.install_flux check
.\.venv\Scripts\python.exe -m scripts.install_flux install
.\.venv\Scripts\python.exe -m scripts.install_flux verify
```

三個命令均退出 0。完整下載、安裝驗檔及另一次離線完整重讀通過四份共 **29,521,303,916 bytes**。離線 verify 不讀憑證、不連網、不使用 provenance 側錄代替 hash，不修改權重、資料庫或來源。

| 角色 | 正式檔案 | 完整大小 bytes | 兩次完整 hash |
| --- | --- | ---: | --- |
| 主模型 | `diffusion_models/flux1-schnell.safetensors` | 23,782,506,688 | 通過 |
| VAE | `vae/ae.safetensors` | 335,304,388 | 通過 |
| CLIP-L | `text_encoders/clip_l.safetensors` | 246,144,152 | 通過 |
| T5 | `text_encoders/t5xxl_fp8_e4m3fn_scaled.safetensors` | 5,157,348,688 | 通過 |

均位於 `runtime/ComfyUI/models/`，沒有覆寫既有正式檔。安裝後各有來源、修訂、bytes／SHA256、驗證時間及授權待核對狀態的 provenance 側錄；未保存 token、帳號、CDN 簽名 URL。原始三份 runtime JSON 的 hash 保存於摘要，原始報告／權重留在本機，不納入 Git。摘要的 `sha256` 是兩次完整驗證均符合的固定值，報告檔 hash 不能替代權重驗證。

下載前同一磁碟區約 394 GiB 可用，完整檔案加 2 GiB 預留約 29.49 GiB，動態容量通過；逐檔傳輸亦重新檢查剩餘容量。既有 partial 僅扣除其已占用部分，不將 partial 當成已驗證權重。完整驗檔時間及下載前精確容量保存在 JSON。

## 程式與 UI 回歸

- 完整後端 761 項通過（1 項既有 Windows 權限跳過）；後續新增網路錯誤遮蔽案例後，最終 48 項安裝／來源預檢回歸通過（1 項相同跳過），其中 FLUX 新增 16 項。
- 格式／靜態檢查、TypeScript、前端 build、四組契約均通過；整站瀏覽器套件本次未重跑。
- 模型庫三項既有 Chromium 回歸通過：頁面無障礙、1440px／390px 編輯與 FLUX 表格鍵盤操作，包含 axe。只調整安裝提示，不新增網頁下載按鈕。
- 合成資料涵蓋來源拒絕前不下載、固定來源驗證、完整 hash、續傳／分角色重下、整體容量、正式檔不覆寫、安裝鎖、token 限固定 BFL HTTPS 路徑、CDN／公開編碼器不帶 token、HTTP 降級拒絕、錯誤不輸出憑證或簽名 URL。

## 驗收邊界

本機硬體查核為 RTX 3060 12 GiB、系統 RAM 約 63.94 GiB；此項只驗證權重來源與本地檔案，不是 GPU 執行資源或最低需求證據。來源 BF16、檔案大小與啟動旗標皆不能證明執行精度／卸載。主模型、VAE、CLIP-L／T5 上游完整條款仍另由 F02 核對，`terms_verified=false` 保留。

F01 的完成條目移至 [CHANGELOG](../../CHANGELOG.MD#f01)。先 commit／push F01 後，才做 F02；RTX 4080、實際 GPU 出圖／保存／OOM、LoRA 與參考圖仍各自依 [ROADMAP](../../ROADMAP.MD) 驗收。
