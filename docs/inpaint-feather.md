# 內側羽化局部編輯

`checkpoint-inpaint-feather-v2` 是獨立十一節點流程（啟用的 LoRA 另計），不改寫 `checkpoint-inpaint-v1`。後端與專用工作台已完成；RTX 3060 四案例與離線重啟驗收已於第三項完成，見 [完整紀錄](validation/inpaint-feather-rtx3060.md)。

## 遮罩語意

原圖與已保存二值遮罩的條件、fit／stretch、白色編輯／黑色保留沿用 v1。`grow_mask_by` 只影響 VAE 去噪範圍，原二值遮罩仍接到 VAEEncodeForInpaint。新增 `feather_radius` 為 0–64 的整數**輸出像素**，預設 0；沒有通用品質推薦。

最終 ImageCompositeMasked 改用第三份 `blend.png` 灰階遮罩。半徑 0 直接保留二值 PNG 的原 bytes。其他半徑使用 Pillow GaussianBlur，先在影像外補黑 `4r+4` 像素，再裁回原尺寸；模糊值 v 映射為 `clip(round((v-128)*255/127),0,255)`，最後乘回原二值遮罩。此內側淡化讓原黑色範圍的 alpha 保持零；細小白色區域可能縮小或消失，整張遮罩消失時拒絕並提示縮小半徑／擴大遮罩。它不擴張編輯範圍，也不能修正生成物件、色彩或保證接縫消失。

原遮罩保存 `generation_preprocessing`，合成遮罩另存 `blend_preprocessing`，包含方法／版本、Pillow 版本、半徑與單位、量化方式、原二值 SHA256、輸出尺寸／SHA256／bytes。來源圖、二值與合成遮罩分別上傳到同一原 UUID 目錄的 reference.png／mask.png／blend.png，禁止覆寫；三份本機輸入排他建立，失敗只清理本次檔案。上傳任何一份失敗均不送 /prompt；未知提交結果不重送。

## API

- `GET /api/inpaint-feather/workflow`：固定流程與參數描述。
- `POST /api/inpaint-feather/generate`：v1 完整設定加 feather_radius、request_id；嚴格驗證，舊端點拒絕新欄位，相同 UUID 不可跨版本。
- `POST /api/inpaint-feather/preview`：相同設定但不含 request_id；純本機 CPU 前處理，回傳實際合成 PNG，以及 X-Atelier-SHA256／Width／Height／Feather-Radius。Cache-Control no-store，不建立任務、檔案或連線引擎。預覽不凍結目前表單，修改後須重做。
- `GET /api/jobs/{id}/reference-image`、`reference-mask`：本次處理後來源與二值遮罩。
- `GET /api/jobs/{id}/reference-blend-mask`：只讀本機合成 PNG，完整流程／快照及檔案 hash 驗證，可加 download=true；遺失／不符只提示備份，不重新計算。

終止任務與作品的 creation-settings 保留完整 v2 設定與兩份素材／三份處理輸入快照；異常節點、角色、二值來源 hash、羽化方法／版本／半徑拒絕部分載入。原紀錄的 Pillow 版本不由目前環境回填。v1 紀錄不新增 feather_radius 或新遮罩；一般草稿、比較方案、交換 JSON 仍不套用這個流程。

## 驗證與後續

新增 12 項後端測試：無引擎／無持久化預覽、預覽與提交 PNG 完全相同、原黑色範圍不擴散、半徑零原 bytes、細遮罩消失、三次上傳與引用、LoRA、必要節點、失敗／unknown 不重送、排他寫入與磁碟失敗清理、UUID 相容、完整離線還原與缺檔不可回填。完整後端 489 項（488 通過、1 項既有 Windows skip）。工作台及真實 GPU 的保留範圍／邊界觀察已完成；品質偏差保留，見下方驗收連結。

FLUX P5 目前固定 BFL 主模型／VAE 來源於 2026-10-22 只讀 HEAD 回傳 401 GatedRepo，本機未發現已授權 Hugging Face token；未登入、接受條件或下載。磁碟已足夠，但來源存取尚未完成，因此本批先交付現有權重可執行的 P6 修補改善。固定來源見 [BFL 模型卡](https://huggingface.co/black-forest-labs/FLUX.1-schnell/blob/741f7c3ce8b383c54771c7003378a50191e9efe9/README.md)。


## 工作台與歷史

在局部編輯選擇同尺寸的已保存原圖／遮罩，設定「內側羽化半徑（輸出像素）」；預設 0。按「預覽合成遮罩」明確執行純 CPU 計算，圖片只以暫時 Blob URL 保留於本頁，不寫入素材或任務。沒有 checkpoint／引擎連線仍可預覽有效已保存素材；未保存筆刷內容需先保存。灰階預覽是實際將上傳的合成 PNG，不是生成效果示意。

檢查回應的 PNG 類型／32 MiB 上限、IHDR 尺寸／RGB 與 SHA256。來源、遮罩、引用、尺寸、縮放、半徑、未保存遮罩或操作鎖定變更會取消／丟棄過期回覆並撤銷舊 Blob URL；離開工作台清除暫時圖，返回保留表單並需手動重做預覽。修改提示詞不影響這份遮罩。

新生成使用 v2；localStorage 沿用原 pending key，無版本標記的舊 body 仍送 v1，精確 seed／UUID／參數原樣保留；v2 本機版本標記在提交前移除，未知標記拒絕並保留原紀錄。v1 歷史載入新表單時才加入半徑 0，不改原任務。任務／作品顯示原羽化方法、版本／Pillow、半徑、hash，可讀取／下載原合成遮罩；一般草稿／比較格式保持未支援。

V02 已於 2026-10-23 在隔離 Chromium 補驗 v1／v2、1440px／390px 的遺失回應與不完整 JSON。重新載入保留原 pending，空白新表單的半徑 0 不會取代原 v2 半徑 8，無標記 v1 仍走原端點且不新增羽化遮罩。成功回覆必須核對原 UUID；缺失／其他任務 ID 或錯誤回覆中的其他 job_id 不清除 pending。明確手動恢復仍 POST 原端點／完整原 body，由後端查原 UUID 帳本返回既有任務；不重新上傳、不重新向引擎送 /prompt。未知結果以原引擎 history／queue 確認，不能把空佇列當作完成。詳見 [V02 證據、限制與重跑](validation/inpaint-recovery-20261023.md)。

2026-10-22 瀏覽器實際在隔離資料庫完成：引擎關閉、未選 checkpoint 仍成功預覽；1024² PNG 解碼完成、半徑 16→8 清除舊圖、65 阻擋、頁面切換保留 16 並清除暫時圖、390px 無橫向溢出。截圖 runtime/feather-preview-proof-20261022.jpg、feather-preview-narrow-20261022.jpg；隔離 UI 2 素材／0 任務／0 作品，正式 settings 指紋未變。未在本項操作筆刷觸控、生成或歷史下載點擊，GPU／新歷史介面接續驗收。

前端 check:inpaint 新增完整 v1／v2 還原、精確 pending、半徑／LoRA、預覽 bytes／hash／尺寸／有界串流及失效身分檢查；check:control、check:experiments 與 Vue 型別／production build 通過。


## 固定羽化實機 CLI

先保存同尺寸原圖與二值遮罩，登記／同步已安裝固定 Pony 或 Animagine。每次明確執行一個模型／半徑；目前 CLI 固定半徑 0／16，平台表單仍可使用 0–64。新報告須不存在，先排他保存 UUID 再只提交一次；完整權重驗檔後以 CPU 預覽核對實際保存的合成 PNG，並量測原黑色保留與固定內側一像素差值。不是品質評分或通用預設。

```powershell
.\.venv\Scripts\python.exe -m scripts.verify_inpaint_feather --model pony-v6-xl --radius 16 --source-id <原圖UUID> --mask-id <遮罩UUID> --report runtime/feather-pony-16.json
```

可改 --model animagine-xl-4.0-opt 或 --radius 0。既有完整報告加 --verify-report 只 GET 核對，不重新預覽／匯入／生成；不能修復缺少證據的報告。非法來源、半徑／原完整 workflow、羽化政策、灰階／PNG hash、保留範圍／邊界量測均先拒絕且不改原報告。四案例及引擎離線／平台重啟已驗收，見 [RTX 3060 實測與偏差](validation/inpaint-feather-rtx3060.md)。
