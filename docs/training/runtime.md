# T03 獨立訓練與運算協調

2026-10-25：獨立環境、明確 run／停止／續訓及生成互斥介面已建立；技術驗收見 [RTX 3060 紀錄](../validation/training-runtime-20261025.md)。T03 已先 commit／push，再完成 [T04 回登與評估流程](artifacts.md)；作者品質仍未認列。

沿用 T02 的 sd-scripts `11d8cedd0c67b93a10f8b2d75f43554f6f12c794`，在 `runtime/training/sd-scripts` 與 `runtime/training/.venv` 安裝，平台與 ComfyUI 的 Python 不安裝 trainer 依賴。Windows x64／Python 3.12／CUDA 13.0 的精確版本位於 `training/requirements-win-py312.lock.txt`；來源及兩份 tokenizer 的固定修訂、大小與 hash 位於 `training/environment.json`。訓練使用離線 tokenizer，不於執行期間下載檔案。

`python -m scripts.training_environment` 唯讀檢查版本、依賴、乾淨 trainer 來源及快取；加 `--install` 才明確建立獨立環境。這只是環境檢查，不代表 GPU 訓練通過。

## 運算使用規則

訓練及本專案對本機引擎的新 prompt dispatch 共用跨程序 OS lease，沿用既有 DataLease 的鎖定實作。本機範圍為 loopback 引擎，遠端引擎不占用本機 lease。原 UUID 恢復先於檢查，已提交任務仍可查詢，禁止因訓練忙碌而重送。

訓練 worker 取得獨占 lease 後，仍須確認受管理的 ComfyUI 8188 已停止，才可載入 GPU 模型。程式不自動結束既有引擎或任務，使用者需先完成工作再停止引擎。其他軟體、直接啟動的引擎及其他 checkout 不受此專案的協定控制；不能宣稱鎖定整張顯卡或隔離其他 GPU 程序。worker 持有 lease 直到程序結束，避免控制端中斷卻過早放行生成。

## Run 契約

- 使用 T02 已封存且資料檢查通過的 bundle；複製 train PNG／caption 到新 run 的工作副本，快取只寫副本，原封存包不變。
- 僅支援已固定 Animagine SDXL 基底與 UNet LoRA；基底大小／hash、資料清單／封存 hash、完整設定、環境與工具版本先凍結。輸出皆為新的 UUID 目錄，不覆寫舊 run。
- 設定範圍先限單 GPU、batch 1、512／1024、rank 4／8／16、fp16、AdamW、SDPA、梯度檢查點、latent／文字編碼快取；步數、seed、learning rate 與保存頻率明確記錄。不接受任意命令或額外 trainer flags。
- 訓練、停止要求、已停止／失敗／完成分開記錄。停止只作用於原 run；worker 在步驟起點讀取停止要求，之後確認程序結束才表示資源已釋放。
- 只有 `Accelerator.save_state` 完整返回後才封存 optimizer／scheduler／RNG／step 狀態，失敗中途的半份目錄不可恢復。恢復使用新的 run UUID，核對原設定及完整 checkpoint hash，不自動重試或改寫原 run。固定上游會重設步數，整合層因此載入完整狀態後，明確執行剩餘更新數並將保存步數換回全程步數，最終 state 必須到達原預算才算完成；資料載入順序不保證與未中斷訓練逐位元一致。
- 資源紀錄區分 PyTorch 訓練程序的 allocator 高水位、整卡觀察值及程序 RAM；未知保持未知，512 合成 smoke 不代表 1024 畫風訓練需求或 RTX 4080 驗收。

## 操作

在根目錄使用平台的 Python 執行控制端；只有獨立 worker 載入 Torch。首次安裝需網路與足夠磁碟，之後訓練離線執行。請先重新啟動平台，讓新生成入口套用資源協調。

```powershell
.\.venv\Scripts\python.exe -m scripts.training_environment --install
.\.venv\Scripts\python.exe -m scripts.training_environment
# 可選：建立自己的新技術測試資料包（不能覆寫）。不是作者畫風資料。
.\.venv\Scripts\python.exe -m scripts.training_fixture --output runtime/training/my-technical-check
.\.venv\Scripts\python.exe -m scripts.training_run prepare --config runtime/training/my-technical-check/config.json
# 使用 prepare 返回的 UUID；先完成現有工作並停止受管理的 ComfyUI。
.\.venv\Scripts\python.exe -m scripts.training_run run --run-id <UUID>
# 另一個終端可查詢／要求停止；停止在下一個訓練步驟起點生效。
.\.venv\Scripts\python.exe -m scripts.training_run status --run-id <UUID>
.\.venv\Scripts\python.exe -m scripts.training_run stop --run-id <UUID>
# status 確認 resources_released 後，選 checkpoints 中已完整封存的 step-N。
.\.venv\Scripts\python.exe -m scripts.training_run resume --run-id <UUID> --checkpoint step-1
# resume 只建立新 UUID，還要明確 run 才開始。結束後自行恢復原引擎。
```

`runtime/training/runs/<UUID>` 保存 manifest／SHA、狀態、完整 CLI、日誌、資源、產物 hash 及 checkpoint receipt。`prepared` 只是凍結設定；`completed` 仍須確認 `resources_released=true`，才代表 worker 與租約皆結束。沒有同名重跑或自動重試。建立中斷留下未封存目錄時，保留診斷並準備新 UUID；不嘗試把半份資料當成功 run。

原始 checkpoint／權重／環境及資料不進 Git；備份時保存整個 run、原 bundle、固定基底及環境 profile，不能只複製 LoRA 而遺失訓練來源。安裝工具拒絕覆寫被修改的 trainer 或 tokenizer，請另行檢查差異。

## 圖片與品質提醒

既有作者圖片仍有 caption／來源用途與逐張角色待審查，不因使用者要求開發 T03／T04 而自動認列為可訓練資料。本輪先用自製合成資料驗證真實技術流程，產物只標示技術測試，不宣稱畫風或角色品質。實際作者圖訓練前提醒使用者完成 T02 缺項；T04 的作者品質比較另需核對獨立評估圖與曝光紀錄。
