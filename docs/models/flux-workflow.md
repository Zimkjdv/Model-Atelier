# FLUX.1 [schnell] 專用工作流程

2026-10-05：`flux1-schnell-text2image-v1` 使用 9 個原生節點：UNETLoader、DualCLIPLoader（type=flux）、VAELoader、正／空負提示詞 CLIPTextEncode、EmptySD3LatentImage、KSampler、VAEDecode、SaveImage。

採 16 通道 latent；batch 1、CFG 1、Euler／simple、denoise 1，steps 限定 1–4。尺寸 64–8192 且為 16 倍數。負提示詞、LoRA、參考圖及其他變體均不接受，不默默忽略額外欄位。CFG 1 不使用負提示詞；參數依 [ComfyUI 官方範例](https://comfyanonymous.github.io/ComfyUI_examples/flux/) 及 [官方 Schnell workflow](https://github.com/Comfy-Org/workflow_templates/blob/main/templates/flux_schnell.json) 的取樣設定實作，分離載入器介面另核對本機原生源碼與即時節點定義。

主模型 weight_dtype 可選 default、fp8_e4m3fn、fp8_e5m2；編碼器 device 可選 default、cpu。選項必須在原引擎即時定義中，這些精度／裝置組合尚未 GPU 驗證，不承諾效能或記憶體需求。模型檔案名稱與角色由使用者選擇，FLUX 變體不能僅憑名稱判定；主模型登記為已知其他架構時拒絕，未知架構保持未驗證提醒。文字編碼器及 VAE 不依主模型架構標籤推定相容。

## API

| 方法／路徑 | 用途 |
| --- | --- |
| GET `/api/flux/workflow` | 參數與能力描述 |
| POST `/api/flux/workflow` | 只讀產生完整 JSON；不查引擎或新增任務 |
| POST `/api/flux/generate` | 表單加 request_id UUID，安全提交一次 |
| GET／POST `/api/flux/drafts` | 查詢／新增獨立 FLUX 草稿，不啟動生成 |
| PUT `/api/flux/drafts/{id}` | 帶 revision 更新，衝突 409 |
| GET `/api/flux/jobs/{id}/creation-settings` | 終止任務完整設定還原；不提交新任務 |
| GET `/api/flux/artworks/{id}/creation-settings` | 完整作品設定還原至專用表單 |

表單包含 engine_url、diffusion_model、clip_l、t5xxl、vae、prompt、seed（十進位字串）、width、height、steps、weight_dtype、encoder_device、title。兩個 encoder 不能重複；未確認的提交只查原任務，不建立新 UUID 重送。

提交先保留完整工作流程及四元件版本／來源快照，再檢查原引擎全部八種節點的 required／optional 輸入、輸出類型、元件清單及數值範圍；引擎或登記架構驗證期間變更也會阻擋。缺少元件、離線與拒絕均保存失敗原因；送出後連線不明則保留 unknown。重用原 UUID 不重新查模型、不重新提交。四元件快照不可改寫，匯入作品時複製原任務快照；舊紀錄不回填。

佇列、歷史、SSE、指定取消／停止、JSON 下載與作品匯入沿用原任務引擎。標準 checkpoint 創作表單不接受此流程；FLUX 設定需使用專用表單。

## 驗證範圍

11 項新增流程測試涵蓋精確 seed、缺少節點／元件、額外 required 輸入、數值範圍、離線、回應遺失、UUID 恢復、引擎／架構變更、不可變快照、完整還原及草稿修訂。

2026-10-05 本機 ComfyUI 0.34.0 已唯讀取得八種真實節點介面，schema 檢查通過；SaveImage 新版 IMAGE 輸出與舊版空輸出均支援。目前 diffusion_models、text_encoders 皆空；VAE 僅有原生 pixel_space，沒有所需 ae 權重。僅在記憶體中替換元件名稱以檢查介面，未寫入假模型、未送 /prompt、未載入權重。證據保存於忽略目錄 `runtime/flux-live-nodes-20261005.json`。

FLUX 權重安裝、CUDA 生成、真實作品與資源取樣仍待完成。此輪模擬測試不當作 GPU 驗收。

## 創作介面（2026-10-05）

創作工作台上方可切換 Checkpoint／SDXL 與 FLUX.1 [schnell]。兩邊表單由 KeepAlive 分開保留，草稿與待確認提交請求各有獨立儲存；離開頁面前仍需保存草稿，重新載入網頁不承諾保留未保存內容。

四個元件可由引擎建議清單選取，或手動填寫名稱以保存離線草稿。版本／來源在模型庫登記，未知就顯示未知；生成仍查即時清單及節點，不能以離線快照授權提交。原引擎與目前設定不符時提示確認，重新整理不改草稿原位址或參數。

匯出使用後端產生的 `workflow_json` 字串，保留 64 位 seed，不對瀏覽器解析後的數字再次 stringify；頁面提供上次匯出預覽。匯出、保存與載入不增加生成任務。FLUX 作品會自動開啟專用設定表單；載入取代未保存內容前提供確認。

任務狀態／取消／指定停止／SSE 共用既有元件，但依流程分開列表與 localStorage 待確認請求鍵。FLUX 頁不把失敗設定載入 checkpoint 表單，也不在新生成時自動重新傳送舊 UUID。
