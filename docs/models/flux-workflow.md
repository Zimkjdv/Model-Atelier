# FLUX.1 [schnell] 專用工作流程

本文件集中純文生圖流程、[分離元件庫](#components)及[平台生成與失敗復原](#generation-acceptance)。各日期驗收分開保留；目前有實測的固定 512 配置不代表所有精度、尺寸或硬體皆已通過。LoRA／原圖重繪仍見[獨立擴充流程](flux-extensions.md)。

2026-10-25：[F01 固定安裝](flux-installation.md)與 [F02 原生節點 512 配置量測](flux-runtime-observation.md)已有實際證據；F02 使用獨立程序及明確載入順序；[F03](flux-workflow.md#generation-acceptance)另完成相同固定 512 配置的平台 HTTP、作品保存、離線還原與受控 CUDA OOM。[F04 LoRA／原生圖生圖](flux-extensions.md)另立版本與子頁，不混入本檔的純文生圖格式。下方 2026-10-05 的缺權重描述保留為歷史。

2026-10-05：`flux1-schnell-text2image-v1` 使用 9 個原生節點：UNETLoader、DualCLIPLoader（type=flux）、VAELoader、正／空負提示詞 CLIPTextEncode、EmptySD3LatentImage、KSampler、VAEDecode、SaveImage。

採 16 通道 latent；batch 1、CFG 1、Euler／simple、denoise 1，steps 限定 1–4。尺寸 64–8192 且為 16 倍數。本純文生圖格式不接受負提示詞、LoRA、參考圖及其他變體，不默默忽略額外欄位。CFG 1 不使用負提示詞；參數依 [ComfyUI 官方範例](https://comfyanonymous.github.io/ComfyUI_examples/flux/) 及 [官方 Schnell workflow](https://github.com/Comfy-Org/workflow_templates/blob/main/templates/flux_schnell.json) 的取樣設定實作，分離載入器介面另核對本機原生源碼與即時節點定義。

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

使用者已要求先核對 RTX 3060 的官方需求與實測範圍，需要量化／卸載或 4080 時預先說明。來源、官方文件與 GGUF 接入差異見 [實作前置判斷](flux-rtx3060-planning.md)，該文件不代表 GPU 或權重安裝通過。

11 項新增流程測試涵蓋精確 seed、缺少節點／元件、額外 required 輸入、數值範圍、離線、回應遺失、UUID 恢復、引擎／架構變更、不可變快照、完整還原及草稿修訂。

2026-10-05 本機 ComfyUI 0.34.0 已唯讀取得八種真實節點介面，schema 檢查通過；SaveImage 新版 IMAGE 輸出與舊版空輸出均支援。目前 diffusion_models、text_encoders 皆空；VAE 僅有原生 pixel_space，沒有所需 ae 權重。僅在記憶體中替換元件名稱以檢查介面，未寫入假模型、未送 /prompt、未載入權重。證據保存於忽略目錄 `runtime/flux-live-nodes-20261005.json`。

FLUX 權重安裝、CUDA 生成、真實作品與資源取樣仍待完成。此輪模擬測試不當作 GPU 驗收。

## 創作介面（2026-10-05）

創作工作台上方可切換 Checkpoint／SDXL 與 FLUX.1 [schnell]。兩邊表單由 KeepAlive 分開保留，草稿與待確認提交請求各有獨立儲存；離開頁面前仍需保存草稿，重新載入網頁不承諾保留未保存內容。

四個元件可由引擎建議清單選取，或手動填寫名稱以保存離線草稿。版本／來源在模型庫登記，未知就顯示未知；生成仍查即時清單及節點，不能以離線快照授權提交。原引擎與目前設定不符時提示確認，重新整理不改草稿原位址或參數。

匯出使用後端產生的 `workflow_json` 字串，保留 64 位 seed，不對瀏覽器解析後的數字再次 stringify；頁面提供上次匯出預覽。匯出、保存與載入不增加生成任務。FLUX 作品會自動開啟專用設定表單；載入取代未保存內容前提供確認。

任務狀態／取消／指定停止／SSE 共用既有元件，但依流程分開列表與 localStorage 待確認請求鍵。FLUX 頁不把失敗設定載入 checkpoint 表單，也不在新生成時自動重新傳送舊 UUID。

<a id="components"></a>

## FLUX 分離元件庫

2026-10-25：[F04 LoRA／原圖重繪](flux-extensions.md)另立流程與子頁；四元件仍使用本庫，PVC LoRA 從通用 LoRA 模型庫同步／登記。版本登記與即時清單不會替代完整檔案 hash 或目前引擎的實測。

2026-10-05：元件庫由選定 ComfyUI 的 `UNETLoader`、`DualCLIPLoader`、`VAELoader` 列舉 diffusion model、text encoder、VAE。四個生成依賴分別是主模型、CLIP-L、T5、VAE；兩個 encoder 共用同一類模型庫。模型庫已提供搜尋、同步與版本／來源／授權／大小／雜湊登記介面。

- `GET /api/flux/components`：只讀目前引擎快照。
- `POST /api/flux/components/sync`：JSON `{ "engine_url": "http://127.0.0.1:8188" }`，三個載入節點全部成功後才原子發布；失敗保留上次完整清單及同步時間。
- `PUT /api/flux/components/metadata`：傳入 `engine_url`、`category`、`name`，及需要修改的版本、來源、架構、大小、SHA256、授權、備註。category 為 `diffusion_models`、`text_encoders` 或 `vae`。

清單及資料按引擎隔離。同步期間切換引擎回傳 409，不把舊回應發布至新引擎。移除模型保留登記資料並標記未列出，再出現時保留資料。

版本未登記時顯示未知；檔名、清單列出與手動 SHA256 均不代表已驗證檔案、架構、授權或 GPU 執行。固定下載計畫與實際元件庫分開；同步不下載模型，不套用本機磁碟資訊至遠端引擎。

<a id="generation-acceptance"></a>

## 平台生成與失敗復原

F03 使用 [固定四元件](flux-installation.md) 與 [F02 配置](flux-runtime-observation.md)：RTX 3060 12 GiB、約 64 GiB RAM、512×512、batch 1、4 steps、Euler／simple、CFG 1、主模型 `fp8_e4m3fn`、文字編碼器 CPU。精確 seed 為 `9007199254740993`，完整值以字串保存，工作流程 JSON 使用整數。這不是所有精度、尺寸或顯卡的通過保證。

<a id="generation-acceptance-studio"></a>

### 平台操作

1. 啟動服務，在模型庫的 FLUX 元件頁同步四份元件，依安裝報告登記來源 revision 與 SHA256；登記本身不會驗證權重。
2. 在創作工作區選「FLUX.1 [schnell]」，填入四個檔名、提示詞與上述配置。可以先保存草稿或匯出完整 JSON。
3. 按一次生成，等待原 UUID 的工作狀態確認。若提交回覆遺失，查詢原任務；不要再次按生成來猜測結果。
4. 成功後保存作品。在作品庫讀取本機圖片、原始 JSON、元件及環境快照；載入設定只填表，不會生成。
5. 若載入失敗或 CUDA OOM，保留失敗任務。先載入原設定、確認錯誤、修正模型或降低尺寸，再明確按生成建立新 UUID。原 UUID 永遠保留原結果。

沒有支援負面提示詞，也不把 SDXL 的附加元件驗收當成 FLUX 可用證據。LoRA／參考圖由 F04 分開處理。

<a id="generation-acceptance-verification"></a>

### 可重現驗收

從專案目錄執行（需要已安裝的四份固定權重與 managed ComfyUI Python）：

```powershell
# 先結束原引擎工作並關閉 8188 引擎；工具不會代為停止使用者服務。
.\.venv\Scripts\python.exe -m scripts.flux_acceptance_fixture --run
```

工具先完整驗檔並取得本機運算租約，再建立 `runtime/flux-acceptance/<UUID>/`。獨立平台使用新的 DATA／SQLite；獨立 ComfyUI 明確指定 base directory、database URL、模型搜尋目錄及隨機 loopback port，只有測試專用節點可載入。原平台設定、作品及正常引擎自訂節點不參與測試。工具結束只停止自己建立的兩個程序，失敗報告也保留。

案例依序為正常生成、損壞 safetensors 載入失敗、真實 CUDA allocator OOM、使用者明確建立的新任務，以及引擎已接收但平台故意遺失回覆。最後停止測試引擎，從仍開啟的平台讀取先前作品與設定。每個案例的 `/prompt` 計數必須剛好一次；離線驗證不得增加計數。

OOM 案例只在測試程序設定極小的 CUDA 配額，請求 4 MiB tensor 並立即還原配額，讓實際 PyTorch allocator 拋出例外。這是受控故障注入，**不是自然耗盡 12 GiB VRAM，也不代表測得最大可用解析度**。正常權重名稱走原生 loader；損壞檔／OOM 標記檔僅存在該次測試目錄。請勿將 `scripts/flux_failure_node.py` 安裝到正常引擎。

也能對目前平台執行固定單次生成，或在引擎離線時唯讀驗證先前報告：

```powershell
.\.venv\Scripts\python.exe -m scripts.verify_flux_generation --report runtime/my-flux.json
.\.venv\Scripts\python.exe -m scripts.verify_flux_generation --report runtime/my-flux.json --verify-report
```

新報告以 exclusive create 保留，已存在時拒絕覆寫，未送出任務。`--verify-report` 只使用 GET，核對原 job／artwork UUID、完整 graph、四元件與環境快照、PNG SHA256／尺寸及完整設定。它不重新同步、匯入或提交；原報告不改寫。若生成程序中斷或網路失敗，讀取留下的 UUID，先確認原任務。

實際結果與限制見 [F03 驗收紀錄](../validation/flux-generation-20261025.md)。權重、圖片、原始日誌及 DATA 留在 ignored runtime；Git 僅保存去除本機絕對路徑的摘要。
