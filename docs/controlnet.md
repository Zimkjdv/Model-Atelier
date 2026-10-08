# Canny 結構參考

固定 `checkpoint-canny-controlnet-v1` 使用一張素材、ComfyUI 原生 Canny 與同架構的 ControlNet。支援明確登記的 SD 1.x／SDXL checkpoint，以及最多四個有序 LoRA。這是結構條件，不是畫風或角色鎖定；本階段完成後端，介面與 GPU 驗收接續實作。

## 模型登記

- `GET /api/controlnets`：目前引擎的控制模型清單與登記資料。
- `POST /api/controlnets/sync`：JSON `{ "engine_url": "http://127.0.0.1:8188" }`，讀取原生 ControlNetLoader。失敗保留歷史清單並標示錯誤；同步不載入權重。
- `PUT /api/controlnets/metadata`：明確的 engine_url、name，以及版本、來源、architecture、kind、SHA256、bytes 大小、授權與備註。架構及類型不依檔名推測，未填版本顯示未知。kind 可登記 unknown／canny／depth／pose／other，目前只有 canny 可提交。

登記依引擎隔離，移除的模型保留版本資料並標示未列出。成功同步、kind=canny，及與 checkpoint 相同的 sd1／sdxl 架構為此流程的必要條件；登記不是實際權重驗檔或載入證明。

## 提交與保存

`POST /api/control/generate` 接收完整 checkpoint 設定與 request_id。固定 workflow_mode=text2image、denoise=1、單張；image_asset_id 與 reference_ids 的唯一 ID 相同。附加欄位：control_net_name、control_strength（大於 0 至 10）、control_start／control_end（0–1 且 start < end）、canny_low／canny_high（0.01–0.99 且 low < high）。

來源先驗檔，再以 fit 等比補白或 stretch 拉伸至輸出尺寸。模型從 EmptyLatentImage 生成，Canny 只提供正／負條件，沒有以來源圖 latent 作圖生圖。控制範圍用原生節點的 start_percent／end_percent，不能解讀成毫秒。Canny 閾值為原生 Kornia 的浮點參數，不能直接當成 OpenCV 的 0–255 閾值。

基礎十一個節點，已啟用 LoRA 各增加一個。凍結完整 workflow JSON、原始素材與處理後 PNG 大小／雜湊、縮放方法、原生 Canny 參數、checkpoint／ControlNet／LoRA 版本及提交環境。Canny 在原引擎執行，個別節點版本無法取得時保持未知；目前只保存縮放後來源 PNG，沒有另存 Canny 邊緣圖。`GET /api/jobs/{id}/reference-image` 提供該來源。

## 保護與還原

交易內確認模型登記及原子保存素材引用；提交前嚴格核對 LoadImage、Canny、ControlNetLoader、ControlNetApplyAdvanced 的介面、浮點範圍與原引擎即時模型清單。上傳前及 /prompt 前再檢查登記快照；變更則停止。輸入使用平台 UUID 子目錄，核對不可覆寫的上傳回條。缺模型、離線、缺節點等錯誤明確保存，不送出無效流程。

相同 UUID 與完整設定先恢復舊任務，不重新探查素材、模型或引擎；不同設定為 409。/prompt 回應遺失保留 unknown，不能自動重送。一般 /api/generate 拒絕控制參數，避免悄悄退回普通流程。

任務／作品的 creation-settings 可離線完整還原控制模型、參數、來源與版本。節點、角色、前處理或控制快照不一致時拒絕部分載入。清單或版本改變只提示，不改寫原設定。普通草稿、設定交換與比較方案尚未接入，不借用舊格式丟棄控制欄位。

依據：[ComfyUI 官方 ControlNet 文件](https://docs.comfy.org/tutorials/controlnet/controlnet)，以及本機固定 ComfyUI 0.34.0 原始碼。新增 12 項後端測試涵蓋登記隔離／競態、精確圖、上傳／離線／未知結果、原 UUID 恢復、有序 LoRA 及完整還原。完整後端 451 項（450 通過、1 項既有權限跳過）。
