# Checkpoint 局部編輯

平台提供自有的 `checkpoint-inpaint-v1` 模板：原圖與遮罩各一張，使用已明確登記為 SD 1.x 或 SDXL 的 checkpoint，可依原順序掛載最多四個 LoRA。後端與局部編輯工作台已整合；RTX 3060 實機驗證接續進行。

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

前端驗證：`npm.cmd --prefix frontend run check:inpaint`（尺寸、素材切換、精確 seed、不可變還原、CSS 座標、二值閾值／透明背景／反相）、`check:experiments` 及 Vue 型別／建置。Windows 瀏覽器工具仍因 sandbox helper 啟動失敗，實際畫面點擊、觸控與窄視窗待驗收。
