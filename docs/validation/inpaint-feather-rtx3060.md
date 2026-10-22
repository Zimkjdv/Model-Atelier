# 內側羽化／RTX 3060 四案例驗收（2026-10-22）

Pony V6 XL、Animagine XL 4.0 Opt 各比較羽化半徑 0／16，四個真實 CUDA 任務成功生成、匯入及核對三份處理輸入。每項新 UUID 只提交一次；引擎關閉與平台重啟後四份 GET-only 報告通過。這是局部合成與保留範圍的整合驗收，品質偏差保留。

## 固定條件

兩模型來源、修訂、大小及 SHA256 沿用 models/pony-v6-xl.json、models/animagine-xl-4.0-opt.json；每次新生成前完整本機驗檔。沒有下載新模型或改變來源。RTX 3060 12 GiB、RAM 68,654,481,408 bytes、driver 616.56，ComfyUI 0.34.0／Python 3.12.10／Torch 2.14.0+cu130，NORMAL_VRAM／DynamicVRAM、CPU async offload。模型及 CLIP FP16、VAE bfloat16；平台 Pillow 12.3.0 的前處理版本另存快照。

768²、20 steps、CFG 5.5、dpmpp_2m／karras、denoise 1、grow 6、batch 1、無 LoRA、seed 字串 9007199254740993。來源沿用先前一般山湖插畫與矩形二值遮罩，原始素材 1024²，fit 至 768²。提示詞為 landscape, mountain lake, single red wooden boat floating on the lake, pine forest, daylight, no humans；兩模型使用相同提示，沒有額外品質前綴。一般 checkpoint，不是專用 inpainting 權重。

原圖素材 ID 896cb37f-29d2-47a8-8fc5-bf7fb7b803dc、SHA256 b266ebb6b8bce14e49d588c7cca55b1b4a0c9104ec0a275cb69550ee79d6ce9b；遮罩素材 ID a7c62685-7085-4f0d-88e1-6ef8f03bfe55、SHA256 cbbf7fa0d3e3f08b11568fd95b4b7e7b54bd3937609e5a139f104d03bc87114c。四張圖的處理後原圖均為 ce475070442cc0ea4fdbd26a0f4ad66c18c39757f229b76ec116f6f055027a76，二值遮罩均為 f7cdb3d15d8c4730e1ccd6ac461229a97b58700d20955b113c9d0ad875a71056。羽化 0 的 PNG 與二值遮罩 bytes 相同；羽化 16 的 PNG SHA256 為 3ad7ade45b55233a2533da26f4841637de2eb0f75f52ba7c43606dfd2c52b9ed，5041 bytes。四次 CPU 預覽 hash 均等於原任務實際合成輸入。

## 時間、取樣記憶體與固定邊界量測

| 模型 | 半徑 | 提交至成功歷史觀察秒 | 原引擎起訖秒 | 整卡取樣最大 used GiB | 固定內側邊界平均差值 |
| --- | --- | --- | --- | --- | --- |
| Pony V6 XL | 0 | 28.39 | 27.769 | 10.805 | 36.471483 |
| Pony V6 XL | 16 | 12.078 | 10.76 | 9.488 | 0.70057 |
| Animagine 4.0 Opt | 0 | 28.343 | 26.36 | 9.537 | 34.053232 |
| Animagine 4.0 Opt | 16 | 12.281 | 10.734 | 9.505 | 0.564639 |

每模型半徑 0 是本輪載入／切換模型的第一張；16 使用同引擎暖快取，不能用此表推論羽化加速。平台時間含佇列、網路、取樣與查詢，引擎起訖含載入／快取；整卡用量包含其他程序及快取，不是任務專用連續峰值、最低需求或純 GPU benchmark。完整測試在首次提交前與四張完成後執行，瀏覽器只讀驗收可能影響 CPU／I/O。

固定內側邊界為原二值遮罩一像素、8 鄰接的 1,052 個像素，以處理後原圖為基準計算每像素最大 RGB 通道差再取平均；這不是跨接縫的自然度分數、畫質評分或自動推薦。較小差值代表該區回到原圖的程度較高，不能直接推論生成物件更完整。

四張圖在遮罩外 520,704 像素均完全保留：outside_changed_pixels=0、outside_max_delta=0。二值白色範圍 69,120 像素；半徑 16 有 35,588 個灰階混合像素、32,548 個完全不透明像素，另有 984 個原白色角落像素變成 alpha 0。兩模型分別比較半徑 0／16，在這 32,548 個完全不透明核心像素，changed_pixels=0、max_delta=0；本次差異來自最後合成，沒有替換去噪遮罩。這些是本輪量測，沒有保證跨硬體逐像素一致。

## 品質觀察

Pony 的 0 半徑矩形區域在湖面與船尾有明顯色塊邊界；16 淡化外緣色差，但船尾與倒影也淡出，橙棕色船仍未完整符合單一紅船要求。Animagine 的 0 半徑有硬矩形水面／樹影與截斷船尾；16 混合較平順，船尾仍有不自然淡出。來源遮罩外本來就有其他船，依保留語意沒有消除。沒有把邊界差值降低標成無縫修補或品質通過；專用修補模型、更合適遮罩、其他半徑／seed／prompt 與 RTX 4080 留待評估。

## 原任務與作品

| 模型／半徑 | 任務 UUID | 作品 UUID | 作品 PNG SHA256 |
| --- | --- | --- | --- |
| Pony V6 XL／0 | bac9fd7f-d184-4376-9f17-36c1ab0a2347 | 4c4ef7dd-26bd-5517-9705-2446fd4bf1a7 | 6665ee207293d21b2669d694d4abb23809cc3d9c009ba324442c4ceb677a55ad |
| Pony V6 XL／16 | 6ed6c612-7580-4337-a951-a98d0be02425 | 07a6a58c-3d6c-5283-8925-0afcf19c39ee | 01dd56256f5601ffc525e9a4474e436430a9537c5e6df12b4937abe80a93bb2e |
| Animagine 4.0 Opt／0 | 8b043f78-7723-4c0e-aa36-865b5def6cb0 | 82d3dc86-5ef1-5562-9406-9b85fee7a2b2 | 7ff0e995cc7fba89962e71b97ae23c38860d1c6851be1a473c1c2e6ed9a7788f |
| Animagine 4.0 Opt／16 | 906fc4ef-b02c-4368-aa1c-0e8898a694a2 | fb81408d-f948-553a-aed2-6fcea18c0bc7 | c2f9f6e03f35cb18b3d86515df5f8a5eb90138dcc9012e1b34ddc868994ade29 |

首張生成及匯入已成功，驗收工具原先假設作品摘要含 workflow，檢查階段失敗；依實際 API 契約改讀 /artworks/{id}/workflow，保留初次失敗報告後以原 UUID 的 GET 證據完成，沒有再次生成。測試替身同步改為不含 workflow 的作品摘要，避免掩蓋此契約。原提交／時間與失敗報告保留。

關閉 ComfyUI 後四個原 body／UUID 恢復 200、同 UUID 改半徑 8 回 409；原合成遮罩下載 hash 相符。CLI --verify-report 只 GET 已保存的任務／作品／三份輸入，不能預覽、同步、匯入或重送；平台停止／重啟後重做通過，完整任務 JSON 不變：
- bac9fd7f-d184-4376-9f17-36c1ab0a2347：9bbe0e7a804175f18c0f06bc0e090d495f58a04eaf026e4a3fe2b730edcd7cec
- 6ed6c612-7580-4337-a951-a98d0be02425：8d3b38ac519f968a7c4e0548af4e6c8e20e8f0f7685463c8a88f790cd87c1c21
- 8b043f78-7723-4c0e-aa36-865b5def6cb0：97432c8561d89d4e278af4cdf2c8caacf1323b19aeea4ab3b86f6e438012fdfe
- 906fc4ef-b02c-4368-aa1c-0e8898a694a2：967f6c77737bfef826abe449dd316726e0e49d57f5915df97392814babf858ee

## 瀏覽器與資料隔離

本輪實際驗收：引擎關閉、未選 checkpoint 時可 CPU 預覽；改半徑清除舊圖、65 阻擋、切頁保留表單並撤銷暫時圖，390px 無橫向溢出。新 v2 作品顯示原半徑／方法／Pillow／PNG hash；實際點擊下載 5041 bytes，SHA256 與 16 半徑原快照一致。載入作品回局部編輯，半徑 16、字串 seed 9007199254740993 完整保留。設定交換格式仍不支援局部編輯／Canny，已隱藏其錯誤匯出入口，保留完整 workflow 下載；實際確認新作品該入口 0 個、workflow 下載 1 個。截圖 runtime/feather-preview-proof-20261022.jpg、feather-history-proof-20261022.jpg。

UI 隔離 runtime/feather-ui-live-data-20261022 為 2 素材／0 任務／0 作品；GPU 隔離 runtime/feather-gpu-live-data-20261022 為 2 素材／4 任務／4 作品，保留全部 job_inputs。原始報告 runtime/feather-<pony|animagine>-r<0|16>-20261022.json，離線與核心比較在 feather-recovery-20261022.json；初次失敗在 feather-pony-r0-first-check-failed-20261022.json。runtime 不納入 Git，備份須保存整份 DATA 及報告，不能只備份作品 PNG。

正式 13 個 settings key、5 任務／3 作品／0 素材／0 草稿／0 方案，前後指紋均為 31af66ed1db203c808bee110c1007a8307ae23867df29b259636f0837502a6eb。8000／8001／8188／5173 全部停止。

## 驗證與限制

本批新增 12 項後端流程與 5 項 CLI 測試，完整後端 494 項（493 通過、1 項既有 Windows skip）；前端遮罩／Canny／比較檢查及 Vue 型別／production build 通過。包含兩半徑精確設定、回應遺失不重送、CPU 預覽／保存 hash、三份輸入／完整圖形／原版本、非法報告不發請求／不覆寫、GET-only、灰階洩漏與固定邊界量測。

筆刷觸控未重驗；v1／v2 pending 遷移採邏輯測試，未在真實瀏覽器注入未知／遺失回應的 pending。其他圖片格式、專用模型、FLUX 權重與訓練仍未驗證。
