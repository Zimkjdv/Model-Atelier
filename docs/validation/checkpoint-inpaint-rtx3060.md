# Checkpoint 局部編輯／RTX 3060 驗收

驗收日期：2026-10-09（Asia/Taipei）。此輪完成原圖＋遮罩後端、專用工作台及固定實機驗收，各項完成後依序 commit／push。

## 固定条件與來源

- RTX 3060 12 GiB、平台 RAM 約 64 GiB；nvidia-smi 回報驅動 616.56。只驗證這一台機器，不建立顯卡存取門檻。
- 原引擎 ComfyUI 0.34.0、Python 3.12.10、PyTorch 2.14.0+cu130。原引擎 API 未回報 CUDA runtime／驅動／Git revision，任務快照這些欄位仍為 null，不從版本後綴推定。啟動日志另外觀察模型／CLIP float16、VAE bfloat16、NORMAL_VRAM／動態 offloading；未新增推論精度選項。
- Pony V6 XL 與 Animagine XL 4.0 Opt 使用專案固定 manifest 的檔名、版本、大小與完整 SHA256，本次提交前各自讀取本機權重驗檔。沒有下載新權重。
- 兩次任務使用相同先前自行生成的 1024×1024 山湖插畫，以及另一張不透明二值遮罩。原圖從 `(128,576)` 至 `(512,896)`（右／下界不含）的矩形為白色；其餘黑色。使用 fit 轉為 768×768，原圖 LANCZOS、遮罩 nearest-neighbor，二值門檻 128。
- 20 steps、CFG 5.5、dpmpp_2m／karras、denoise 1、grow_mask_by 6、seed 字串 `9007199254740993`、batch 1、沒有 LoRA。共同提示詞要求湖上單艘紅色木船、松林、日光；完整正／負提示詞及十節點 JSON 保存在報告。未當成各模型最佳預設。
- 使用 8001 的獨立 SQLite 與圖片資料目錄。正式資料維持 5 任務／3 作品／0 素材／0 草稿／0 比較方案；隔離資料新增 2 素材／2 任務／2 作品。

## 實際結果

| 項目 | Pony V6 XL | Animagine XL 4.0 Opt |
| --- | --- | --- |
| 原任務 ID | ec39f4e3-5d40-4b20-84a7-b466bc1fb9f2 | f27f5e89-6160-44fa-85a4-dbb54102d808 |
| 作品 ID | 90be4a6a-30ac-5f66-8def-c2359d58fb57 | f6d8323e-8a94-5321-9823-007e3299c983 |
| 原引擎歷史起訖 | 23.632 秒 | 22.312 秒 |
| 平台提交至首次終態觀察 | 24.990 秒 | 22.713 秒 |
| CLI 提交至成功歷史觀察 | 25.391 秒 | 23.110 秒 |
| 裝置用量離散樣本最大值 | 9.472 GiB（13 次） | 9.933 GiB（12 次） |
| 遮罩外像素 | 520,704 | 520,704 |
| 遮罩外有改變的像素／最大 RGB 差 | 0／0 | 0／0 |
| 遮罩內像素／有改變的像素 | 69,120／69,119 | 69,120／69,120 |

裝置樣本來源是平台 nvidia-smi 聚合用量，包含其他程序，並非此任務的顯存峰值或最低需求。兩次皆包含 checkpoint 載入；Pony 是本輪重啟 ComfyUI 後的第一個生成，Animagine 隨後在同一進程更換模型。OS 檔案快取未清除，不能當作嚴格冷啟動或 GPU 速度對比。

遮罩外差值相對於**處理後的 RGB 原圖**量測，逐像素取三個色彩通道的最大差值；不是原始輸入檔案 bytes 相同的承諾。CLI 容許最多一階量化差，但本次實測為零。

## 原圖觀察與品質限制

開發助手逐張查看完整輸出。Pony 將左側原有小船改為較大且帶棚架的船，色彩偏橘棕，沒有精確滿足紅色；矩形遮罩的左／上邊界仍可見接縫，船身碰到右側邊界。Animagine 生成紅棕色木船，但右側船身在遮罩邊界被截斷，上方新增一條突兀深綠色區域。兩張均保留遮罩外原有其他船，整張圖片並不是單艘船；prompt 只能修改指定區域。

成功驗證的是局部工作流程、保留範圍與追溯能力。沒有把結果標為無縫修補或畫風品質通過，沒有自動設定建議 denoise。後續需評估非矩形遮罩、邊界融合／羽化、專用 inpainting checkpoint、更多區域／模型／seed；目前仍採硬二值合成，避免靜默改動保留區。

## 提交與持久保存驗證

1. 兩次各有一個持久 UUID，兩張任務獨立輸入 PNG 與完整原生流程。確認 CUDA 裝置，原引擎 checkpoint、KSampler 能力與節點介面後只提交一次。
2. 原引擎歷史確認 success，作品匯入成功；核對原圖尺寸與 SHA256、job／artwork workflow、精確整數 seed、兩素材正規化／生成前處理快照、模型版本／雜湊、環境及量測。
3. 停止 8188 後，兩份報告執行 `--verify-report`，僅 GET 任務、處理後原圖／遮罩、作品與原設定，未 sync、refresh、匯入或重新生成。
4. 引擎離線時以相同 request_id／完整原設定恢復，回傳原任務 JSON；改 grow_mask_by 回傳 409。任務數維持兩個。
5. 停止並重啟 8001，再次 GET-only 核對通過，完整任務 JSON hash 與重啟前一致。最後停止 8001，8000／8001／8188／5173 均未監聽。

實機發現遮罩介面初版將素材 API 誤寫為 multipart；已修正為與素材庫相同的原始圖片 body、`filename` query 與 20 MiB 限制，加入前端原請求格式／錯誤回歸檢查，並以隔離 HTTP 成功保存素材。沒有宣稱瀏覽器點擊通過：工具仍因 Windows sandbox `helper_unknown_error` 無法啟動，筆刷實際操作、触控、原生下載与窄視窗仍待驗收。

完整後端 439 項（438 通過、1 項既有 Windows 權限跳過），之後加強報告驗證的 35 項相關回歸再次通過。Vue 型別／建置、`check:inpaint` 及 `check:experiments` 通過。

## 可重讀的本機證據

- `runtime/inpaint-live-data-20261009/`：隔離 SQLite、兩份素材、兩組 job_inputs、原圖及縮圖。
- `runtime/inpaint-inputs-20261009.json`：正規化原图與遮罩 ID／大小／SHA256。
- `runtime/inpaint-pony-20261009.json`、`runtime/inpaint-animagine-20261009.json`：完整条件／workflow／模型與環境／量測／原圖 hash／還原及差值。
- `runtime/inpaint-recovery-20261009.json`：離線原 ID 恢復、409、重啟前後 hash 與正式資料數量。

以上 runtime 為被 Git 忽略的本機證據，不推送圖片、SQLite 或模型權重。操作及可重跑 CLI 見 [局部編輯說明](../inpainting.md)。
