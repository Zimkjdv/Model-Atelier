# Checkpoint 局部編輯

一般局部編輯 v1 與[v2 內側羽化](#inner-feather)在本文件分別說明。版本間的遮罩、端點、原請求恢復與歷史不互相改寫；Fooocus v3 的固定基底、專用權重及品質限制仍見[專用修補](fooocus-inpainting.md)。

2026-10-23 R03：另有 [Fooocus SDXL 專用修補 v3](fooocus-inpainting.md)，仍使用獨立內側合成遮罩。固定基底、denoise 1、無 LoRA；有限比較未優於一般修補，保留實驗選項；一般格式邊界不因此開放。

一般草稿、設定交換及比較尚未支援專用格式；建立／更新一般草稿時的遮罩等欄位會明確拒絕，避免部分保存。工作台可展開版本別支援範圍，原任務／作品完整設定及 workflow 仍可載入／下載，見 [R07 格式評估](specialized-workflow-formats.md)。

平台提供自有的 `checkpoint-inpaint-v1` 模板：原圖與遮罩各一張，使用已明確登記為 SD 1.x 或 SDXL 的 checkpoint，可依原順序掛載最多四個 LoRA。後端與局部編輯工作台已整合；Pony／Animagine 的 RTX 3060 固定實機驗證已完成，修補接縫及色彩偏差如實保留。見 [驗收紀錄](validation/checkpoint-inpaint-rtx3060.md)。

## 輸入與遮罩

`POST /api/inpaint/generate` 接收一般 checkpoint 設定、`request_id`、`workflow_mode: image2image`、`image_asset_id`、`mask_asset_id`、`grow_mask_by`（整數 0–64）。`reference_ids` 必須依序為不同的原圖及遮罩 ID。使用素材庫的已正規化檔案，兩張素材尺寸必須一致；不自動拉伸錯位遮罩。素材不能封存，檔案 SHA256、尺寸與 bytes 大小必須仍符合登記。

原圖以 fit 等比補白或 stretch 拉伸至目標尺寸。遮罩先將透明背景合成為白色，再取灰階，128 以上為白色、其餘黑色，以 nearest-neighbor 使用相同縮放幾何；fit 的遮罩留白區填黑。**白色編輯、黑色保留**。若要保留區域，請使用不透明的黑色，不要使用透明黑色。沒有白色區域、超過 1600 萬輸出像素或尺寸不符會在提交前拒絕。

## 工作流程與保存

平台只建立十節點的固定模板（每個已啟用 LoRA 再增加一個節點）：CheckpointLoaderSimple、兩個 CLIPTextEncode、VAEEncodeForInpaint、KSampler、VAEDecode、SaveImage、LoadImage、LoadImageMask 及 ImageCompositeMasked。遮罩用 red channel 載入已處理的黑白 RGB PNG。`grow_mask_by` 擴大供模型去噪的範圍；最後合成仍使用原二值遮罩，黑色區域取處理後原圖。

保存完整工作流程 JSON、兩份素材快照、處理方法／版本／雜湊、完整參數、模型／LoRA／提交環境快照。任務原圖及遮罩分別由 `/api/jobs/{id}/reference-image`、`/api/jobs/{id}/reference-mask` 提供。作品及已終止任務的 `/creation-settings` 可離線完整還原；若流程、輸入角色或遮罩語意被修改，拒絕部分載入。

## 提交保護

先驗證本機素材，再原子保存兩份引用；素材封存與引用保存具有交易一致性。驗證原引擎 checkpoint、取樣能力及四個圖片／遮罩節點的確切介面。依序上傳至平台持有的 UUID 子目錄，禁止覆寫且核對每次回傳位置；第二張失敗時不送 `/prompt`。每次上傳及最終提交前重新確認引擎，模型／LoRA 來源變更會拒絕。

相同 request_id 與相同完整設定先讀取原紀錄，不重新讀素材或連線引擎。設定不同回傳 409。`/prompt` 回應遺失保留 unknown，只查原任務，不能自動重送。一般 `/api/generate` 拒絕遮罩欄位，避免把局部編輯默默當成圖生圖。

## 限制與依據

單張輸出、固定模板。比較方案、一般草稿及設定交換 JSON 尚未支援這個新流程，不將遮罩欄位丟棄後套用舊格式。黑色區域的保留是相對於縮放後的 RGB 原圖；不能承諾原始檔案 bytes 相同。Pillow 與浮點影像合成／重新編碼也可能產生微小量化差異，實機驗證將量測差值。

一般 checkpoint 可以執行 VAEEncodeForInpaint，修補效果仍依模型、prompt、遮罩及 denoise 而異；專用 inpainting 模型通常更適合此用途，沒有自動套用品質預設。節點結構依目前已安裝的官方 ComfyUI 0.34.0 原始碼驗證；參考 [ComfyUI 官方局部編輯文件](https://docs.comfy.org/tutorials/basic/inpaint)。

驗證：新增 14 項後端測試覆蓋遮罩前處理、兩素材引用、確切流程及 LoRA、不可覆寫輸入、失敗／未知結果不重送與離線完整還原。

## 工作台操作

1. 在創作工作台切換「局部編輯」，選 checkpoint 與素材庫原圖；可到「參考素材」上傳原圖。
2. 選一張與原圖同尺寸的已保存遮罩，或在畫布上用筆刷標白、擦除回黑。支援大小 1–256 原圖像素、清空、反相及載入 PNG；CSS 縮放座標會換算回原圖像素。
3. 按「保存遮罩」，將不透明二值 PNG 保存為新素材並明確關聯。沒有白色區域不能保存。更換原圖清除舊遮罩關聯；尚未保存的繪製阻擋生成。選檔不自動上傳或生成。
4. 確認提示詞、尺寸、fit／stretch、精確 seed、取樣、denoise、擴張與有序 LoRA，按「生成圖片」。原請求以獨立 localStorage key 保留，恢復使用當時完整參數，與目前畫布／表單分開。
5. 任務頁可查看兩份原素材／前處理快照與處理後圖片。完成後匯入作品库；作品或已終止任務載入設定會回到局部編輯工作台，完整保留兩素材 ID、擴張與字串 seed。未保存變更需明確選擇是否替換，不自動生成。

這個專用表單在頁面切換時保留，重新整理會清除未提交的內容；沒有普通草稿保存功能。已保存遮罩是持久素材，提交後的原設定是不可變任務紀錄。引擎資料更新失敗時阻擋新的生成，不取用舊資料悄悄替換模型或取樣器。

前端驗證：`npm.cmd --prefix frontend run check:inpaint`（尺寸、素材切換、精確 seed、不可變還原、CSS 座標、二值閾值／透明背景／反相）、`check:experiments` 及 Vue 型別／建置。2026-10-23 已以 Playwright Chromium 補驗 1440px／390px 的筆刷、擦除、反相、PNG 選檔／保存、縮放與未保存保護，保存後重新讀取 PNG 的 RGBA 雜湊與畫布相同。見 [V01 證據與重跑方式](validation/mask-editor-20261023.md)。實體觸控仍待驗收，CDP 模擬不能代替觸控螢幕或觸控筆。

素材清單更新與站內切頁返回保留未保存筆畫；取消更換原圖或已保存遮罩時，選單與畫布一併保留。載入 PNG 先核對檔頭與尺寸，錯誤檔案不取代畫布。保存、清空、反相、載入或停用編輯會先結束目前筆畫；僅主指標可開始繪製，取消／失去捕獲後不延續舊筆畫。保存失敗仍可編輯或再次手動保存；已保存遮罩不代表完整表單已保存。

## 實機驗收 CLI

先在素材庫明確保存不同的原圖及同尺寸二值遮罩，再執行單一固定模型的驗收。只接受 loopback 平台／引擎與已安裝固定來源的 Pony／Animagine 權重；不下載、不自動建立素材或批次跑圖。

```powershell
.\.venv\Scripts\python.exe -m scripts.verify_inpaint_generation --model pony-v6-xl --source-id <原圖UUID> --mask-id <遮罩UUID> --report runtime/inpaint-pony.json
```

使用 `--model animagine-xl-4.0-opt` 執行另一模型；完整固定條件為 768²、20 steps、CFG 5.5、dpmpp_2m／karras、denoise 1、grow 6、seed 9007199254740993，無 LoRA。這是驗收條件，不是品質推薦。報告必須不存在，先排他保存原 UUID 再送唯一一次生成；最多觀察 15 分鐘。回應遺失只查原任務，不再送生成。

既有完整報告只讀核對，加同一素材 ID、模型、平台與 `--verify-report`。此模式只 GET 已保存紀錄及圖片，不能修復未完成／缺少完整證據的報告，也不補提交或匯入。非法 workflow／seed／素材 hash／遮罩政策／量測先拒絕，不改原報告；資料源差異保留失敗診斷。報告與圖片保存在本機 runtime，正式資料使用者可自行備份。

<a id="inner-feather"></a>

## v2 內側羽化局部編輯

`checkpoint-inpaint-feather-v2` 是獨立十一節點流程（啟用的 LoRA 另計），不改寫 `checkpoint-inpaint-v1`。後端與專用工作台已完成；RTX 3060 四案例與離線重啟驗收已於第三項完成，見 [完整紀錄](validation/inpaint-feather-rtx3060.md)。

<a id="inner-feather-mask-semantics"></a>

### 遮罩語意

原圖與已保存二值遮罩的條件、fit／stretch、白色編輯／黑色保留沿用 v1。`grow_mask_by` 只影響 VAE 去噪範圍，原二值遮罩仍接到 VAEEncodeForInpaint。新增 `feather_radius` 為 0–64 的整數**輸出像素**，預設 0；沒有通用品質推薦。

最終 ImageCompositeMasked 改用第三份 `blend.png` 灰階遮罩。半徑 0 直接保留二值 PNG 的原 bytes。其他半徑使用 Pillow GaussianBlur，先在影像外補黑 `4r+4` 像素，再裁回原尺寸；模糊值 v 映射為 `clip(round((v-128)*255/127),0,255)`，最後乘回原二值遮罩。此內側淡化讓原黑色範圍的 alpha 保持零；細小白色區域可能縮小或消失，整張遮罩消失時拒絕並提示縮小半徑／擴大遮罩。它不擴張編輯範圍，也不能修正生成物件、色彩或保證接縫消失。

原遮罩保存 `generation_preprocessing`，合成遮罩另存 `blend_preprocessing`，包含方法／版本、Pillow 版本、半徑與單位、量化方式、原二值 SHA256、輸出尺寸／SHA256／bytes。來源圖、二值與合成遮罩分別上傳到同一原 UUID 目錄的 reference.png／mask.png／blend.png，禁止覆寫；三份本機輸入排他建立，失敗只清理本次檔案。上傳任何一份失敗均不送 /prompt；未知提交結果不重送。

<a id="inner-feather-api"></a>

### API

- `GET /api/inpaint-feather/workflow`：固定流程與參數描述。
- `POST /api/inpaint-feather/generate`：v1 完整設定加 feather_radius、request_id；嚴格驗證，舊端點拒絕新欄位，相同 UUID 不可跨版本。
- `POST /api/inpaint-feather/preview`：相同設定但不含 request_id；純本機 CPU 前處理，回傳實際合成 PNG，以及 X-Atelier-SHA256／Width／Height／Feather-Radius。Cache-Control no-store，不建立任務、檔案或連線引擎。預覽不凍結目前表單，修改後須重做。
- `GET /api/jobs/{id}/reference-image`、`reference-mask`：本次處理後來源與二值遮罩。
- `GET /api/jobs/{id}/reference-blend-mask`：只讀本機合成 PNG，完整流程／快照及檔案 hash 驗證，可加 download=true；遺失／不符只提示備份，不重新計算。

終止任務與作品的 creation-settings 保留完整 v2 設定與兩份素材／三份處理輸入快照；異常節點、角色、二值來源 hash、羽化方法／版本／半徑拒絕部分載入。原紀錄的 Pillow 版本不由目前環境回填。v1 紀錄不新增 feather_radius 或新遮罩；一般草稿、比較方案、交換 JSON 仍不套用這個流程。

<a id="inner-feather-validation-history"></a>

### 驗證與後續

新增 12 項後端測試：無引擎／無持久化預覽、預覽與提交 PNG 完全相同、原黑色範圍不擴散、半徑零原 bytes、細遮罩消失、三次上傳與引用、LoRA、必要節點、失敗／unknown 不重送、排他寫入與磁碟失敗清理、UUID 相容、完整離線還原與缺檔不可回填。完整後端 489 項（488 通過、1 項既有 Windows skip）。工作台及真實 GPU 的保留範圍／邊界觀察已完成；品質偏差保留，見下方驗收連結。

FLUX P5 目前固定 BFL 主模型／VAE 來源於 2026-10-22 只讀 HEAD 回傳 401 GatedRepo，本機未發現已授權 Hugging Face token；未登入、接受條件或下載。磁碟已足夠，但來源存取尚未完成，因此本批先交付現有權重可執行的 P6 修補改善。固定來源見 [BFL 模型卡](https://huggingface.co/black-forest-labs/FLUX.1-schnell/blob/741f7c3ce8b383c54771c7003378a50191e9efe9/README.md)。


<a id="inner-feather-studio-and-history"></a>

### 工作台與歷史

在局部編輯選擇同尺寸的已保存原圖／遮罩，設定「內側羽化半徑（輸出像素）」；預設 0。按「預覽合成遮罩」明確執行純 CPU 計算，圖片只以暫時 Blob URL 保留於本頁，不寫入素材或任務。沒有 checkpoint／引擎連線仍可預覽有效已保存素材；未保存筆刷內容需先保存。灰階預覽是實際將上傳的合成 PNG，不是生成效果示意。

檢查回應的 PNG 類型／32 MiB 上限、IHDR 尺寸／RGB 與 SHA256。來源、遮罩、引用、尺寸、縮放、半徑、未保存遮罩或操作鎖定變更會取消／丟棄過期回覆並撤銷舊 Blob URL；離開工作台清除暫時圖，返回保留表單並需手動重做預覽。修改提示詞不影響這份遮罩。

新生成使用 v2；localStorage 沿用原 pending key，無版本標記的舊 body 仍送 v1，精確 seed／UUID／參數原樣保留；v2 本機版本標記在提交前移除，未知標記拒絕並保留原紀錄。v1 歷史載入新表單時才加入半徑 0，不改原任務。任務／作品顯示原羽化方法、版本／Pillow、半徑、hash，可讀取／下載原合成遮罩；一般草稿／比較格式保持未支援。

V02 已於 2026-10-23 在隔離 Chromium 補驗 v1／v2、1440px／390px 的遺失回應與不完整 JSON。重新載入保留原 pending，空白新表單的半徑 0 不會取代原 v2 半徑 8，無標記 v1 仍走原端點且不新增羽化遮罩。成功回覆必須核對原 UUID；缺失／其他任務 ID 或錯誤回覆中的其他 job_id 不清除 pending。明確手動恢復仍 POST 原端點／完整原 body，由後端查原 UUID 帳本返回既有任務；不重新上傳、不重新向引擎送 /prompt。未知結果以原引擎 history／queue 確認，不能把空佇列當作完成。詳見 [V02 證據、限制與重跑](validation/inpaint-recovery-20261023.md)。

2026-10-22 瀏覽器實際在隔離資料庫完成：引擎關閉、未選 checkpoint 仍成功預覽；1024² PNG 解碼完成、半徑 16→8 清除舊圖、65 阻擋、頁面切換保留 16 並清除暫時圖、390px 無橫向溢出。截圖 runtime/feather-preview-proof-20261022.jpg、feather-preview-narrow-20261022.jpg；隔離 UI 2 素材／0 任務／0 作品，正式 settings 指紋未變。未在本項操作筆刷觸控、生成或歷史下載點擊，GPU／新歷史介面接續驗收。

前端 check:inpaint 新增完整 v1／v2 還原、精確 pending、半徑／LoRA、預覽 bytes／hash／尺寸／有界串流及失效身分檢查；check:control、check:experiments 與 Vue 型別／production build 通過。


<a id="inner-feather-gpu-cli"></a>

### 固定羽化實機 CLI

先保存同尺寸原圖與二值遮罩，登記／同步已安裝固定 Pony 或 Animagine。每次明確執行一個模型／半徑；目前 CLI 固定半徑 0／16，平台表單仍可使用 0–64。新報告須不存在，先排他保存 UUID 再只提交一次；完整權重驗檔後以 CPU 預覽核對實際保存的合成 PNG，並量測原黑色保留與固定內側一像素差值。不是品質評分或通用預設。

```powershell
.\.venv\Scripts\python.exe -m scripts.verify_inpaint_feather --model pony-v6-xl --radius 16 --source-id <原圖UUID> --mask-id <遮罩UUID> --report runtime/feather-pony-16.json
```

可改 --model animagine-xl-4.0-opt 或 --radius 0。既有完整報告加 --verify-report 只 GET 核對，不重新預覽／匯入／生成；不能修復缺少證據的報告。非法來源、半徑／原完整 workflow、羽化政策、灰階／PNG hash、保留範圍／邊界量測均先拒絕且不改原報告。四案例及引擎離線／平台重啟已驗收，見 [RTX 3060 實測與偏差](validation/inpaint-feather-rtx3060.md)。
