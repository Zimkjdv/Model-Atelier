# E05 · 原引擎連續資源取樣驗收

2026-10-23，在全新 `runtime/e05-live-20261023/data` 和獨立 input／output／user／temp 啟動本機 ComfyUI 與平台，使用現有權重，只提交一個 UUID；未改正式 DATA 或權重。範圍、頻率、程序歸屬與保留界限見 [量測契約](../job-measurements.md#e05-連續觀察的範圍與界限)。

## 真實任務

| 欄位 | 證據 |
| --- | --- |
| GPU／驅動 | RTX 3060 12 GiB，616.56；同主機另有桌面／測試程序，用量不歸屬單一任務 |
| 引擎 | ComfyUI 0.34.0，revision `15eb748b3ec5f8a0a2d470b7fb280e2d7579f916`；Python 3.12.10，PyTorch 2.14.0+cu130；CUDA／驅動不由字串推定 |
| 模型 | Animagine XL 4.0 Opt，SHA256 `6327eca98bfb6538dd7a4edce22484a1bbc57a8cff6b11d075d40da1afb847ac`，提交前完整檔案核對 |
| 設定 | 1024×1024，28 steps，CFG 5，euler_ancestral／normal，denoise 1，seed 字串 `9007199254740993`，無 LoRA／參考圖；安全風景 prompt，沿用固定驗收器 |
| 任務 | `693a40d6-f5d7-441d-8916-4554998f29f9` |
| 取樣來源 | `http://127.0.0.1:2539/system_stats`；開始 05:23:13.788747 UTC、終態 05:24:02.719425 UTC |
| 取樣 | 22 次成功／22 次嘗試，0 失敗、0 個超過 4 秒間隔；最後時間點 05:24:01.833021 UTC |
| RAM 觀察最高值 | 44,508,258,304 bytes，約 41.45 GiB；原引擎整台主機，包含並行品質測試 |
| 裝置觀察最高值 | 9,933,671,648 bytes，約 9.25 GiB；引擎 total−free，CUDA free 含可回收 allocator 快取，與 nvidia-smi 整卡用量不同 |
| 任務專用峰值 | null／UI 未知；原介面不提供可靠的單一 prompt 程序歸屬 |
| 耗時 | 平台提交至確認終態 48.931 秒；引擎歷史 47.641 秒，皆不等於純 GPU 推論 |
| 保存作品 | `275fb551-f2a6-5198-93a9-95773c2fafed`；PNG 1,142,703 bytes，SHA256 `52d12fff1ff5f0415efffc4344b969f19f4f3411d101fe206176b99382bfc43b` |

任務與作品量測完全相同；停止本次引擎後 GET 仍與終態快照相同。1440px／390px Chromium 實際展開此作品量測，核對 22 次、來源、9.25 GiB、凍結與未知任務峰值；檢視兩種寬度截圖，文字換行且沒有水平溢出。原始 JSON、完整 workflow、圖檔、log 與截圖留於忽略的 `runtime/e05-live-20261023/`，不加入 Git。當時保存的 note 是同次實作較早的文字；最終版本另補明 CUDA 可回收快取語意，未改原紀錄。

## 自動回歸與重跑

新增 6 項後端整合測試：取樣不更動 revision／CAS、終態與延遲回應、原引擎分組及設定切換、lease 接續及缺口、錯誤／超大回應、零與無效數字、尾端保留及全期最高值、容量／時間上限、正常停止、歷史唯讀與作品複製。新增 1440px／390px 兩項瀏覽器案例，展開最近時間點、核對凍結與未知值、axe 掃描無違規。診斷既有唯讀斷言排除獨立背景取樣投影，仍完整比對任務 revision、擁有權和提交前量測。

```powershell
.\.venv\Scripts\python.exe -m unittest backend.test_resource_sampling backend.test_job_measurements
.\.venv\Scripts\python.exe scripts/check_quality.py
```

完整品質入口通過 scoped format／static、580 項後端（1 項既有權限條件跳過）、Vue build、四組前端契約及 82 項 Chromium（4.5 分鐘）。最終建置另在引擎離線時重看原 GPU 作品，兩種寬度可讀，資料庫前後 SHA256 相同。完整 log 為 `runtime/e05-quality-final.log`。真實生成可依 [固定 Animagine 驗收](animagine-xl-4-0-opt-rtx3060.md)在另建的隔離 DATA 重跑；完成後另核對 `/api/jobs/{id}` 與 `/api/artworks/{id}` 的 `measurements.continuous_resources`、停引擎後凍結及 UI。不可把測試 fixture 的合成值當 GPU 證據。

E05-01／02 完成。這不是 RTX 4080、其他後端／模型的效能驗收，也不關閉 E02／E04；沒有觸控裝置，V01-02 仍待驗收。
