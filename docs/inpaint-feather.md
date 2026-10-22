# 內側羽化局部編輯

`checkpoint-inpaint-feather-v2` 是獨立十一節點流程（啟用的 LoRA 另計），不改寫 `checkpoint-inpaint-v1`。後端已完成；專用工作台與 RTX 3060 驗收依序接續本批第二、三項。

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

新增 12 項後端測試：無引擎／無持久化預覽、預覽與提交 PNG 完全相同、原黑色範圍不擴散、半徑零原 bytes、細遮罩消失、三次上傳與引用、LoRA、必要節點、失敗／unknown 不重送、排他寫入與磁碟失敗清理、UUID 相容、完整離線還原與缺檔不可回填。完整後端 489 項（488 通過、1 項既有 Windows skip）。工作台與真實 GPU 品質／保存範圍接續驗收。

FLUX P5 目前固定 BFL 主模型／VAE 來源於 2026-10-22 只讀 HEAD 回傳 401 GatedRepo，本機未發現已授權 Hugging Face token；未登入、接受條件或下載。磁碟已足夠，但來源存取尚未完成，因此本批先交付現有權重可執行的 P6 修補改善。固定來源見 [BFL 模型卡](https://huggingface.co/black-forest-labs/FLUX.1-schnell/blob/741f7c3ce8b383c54771c7003378a50191e9efe9/README.md)。
