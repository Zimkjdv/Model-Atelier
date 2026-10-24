# T03 RTX 3060 獨立訓練技術驗收

2026-10-25，本機 Windows／Python 3.12.10、RTX 3060 12 GiB。固定 sd-scripts `11d8cedd0c67b93a10f8b2d75f43554f6f12c794`、Torch `2.14.0+cu130` 與 `training/requirements-win-py312.lock.txt`。環境及離線 tokenizer 的修訂／hash 見 `training/environment.json`；`pip check` 及真正的 `sdxl_train_network.py --help` 成功。平台與 ComfyUI 的 Python 沒有安裝訓練依賴。

## 資料及設定

全部圖片由 `scripts/training_fixture.py` 以 Pillow 畫幾何圖形：512×512、train／validation／test 各一張、不同檔案及分組，只有 train 的一張圖及 caption 進入封存包和訓練。沒有使用指定作者圖片，也不宣稱這是動漫畫風或角色品質訓練。

Animagine XL 4.0 Opt 基底 SHA `6327eca98bfb6538dd7a4edce22484a1bbc57a8cff6b11d075d40da1afb847ac`；單 GPU、batch 1、512、UNet LoRA rank／alpha 4、learning rate 0.0001、fp16、AdamW、constant scheduler、SDPA、gradient checkpointing、latent／文字編碼輸出快取、seed 42、全程 3 個更新、每步保存完整狀態。完整 run／資料／環境／產物識別及觀察數字見 [JSON](training-runtime-20261025.json)。

## 結果與失敗保留

| Run | 實際結果 |
| --- | --- |
| `d9e85ee5-7b84-46a1-ba4f-ca8d3902a29a` | 原 ComfyUI 8188 在線，訓練在載入 Torch／基底前拒絕；狀態 blocked，程序及租約釋放 |
| `c243b6a4-821a-4b05-9119-6465a3548e2c` | 完成 step 1 封存後要求停止；停止在下一個步驟起點生效，實際保存至 step 2；程序及租約釋放 |
| `2aca53c7-3b15-455d-b0ee-aed2a31a9bc1` | 載入 optimizer／scheduler／GradScaler／RNG 成功，但上游重設步數，最後 state 僅 step 2；事後核對判定 failed，保留日誌與產物，不認列完成 |
| `a27f7a75-0791-41ca-958d-bf93bb1f1b89` | 從原 step 1 建立新 UUID；明確執行剩餘 2 更新，封存全程 step 2／3；最終 state 確認 step 3、LoRA 產出完整、程序及租約釋放 |

整合層沒有修改上游 checkout，而是載入完整 Accelerator 狀態、顯式設定剩餘更新數與本段 initial_step 0，保存時將步數換回全程值。最終 state 未達原始預算會失敗，不再只信任 trainer 正常返回。恢復不保證資料順序或逐位元結果等同不中斷訓練。

驗收前確認原引擎沒有執行中／排隊工作才暫停。恢復時直接使用 OS 回報的全域 Python 路徑缺少 ComfyUI 依賴，未啟動成功；隨後改用受管理引擎原 `.venv/Scripts/python.exe` 與原參數恢復，HTTP 佇列核對成功。其他遊戲／桌面／模擬器未結束；GPU 整卡數字包含它們。

## 資源及限制

原停止 run 約 69.8 秒，PyTorch allocated 峰值 5,598,029,312 bytes、reserved 5,861,539,840 bytes；程序 Windows peak working set 22,399,766,528 bytes。這些數字包含模型載入與預處理；完整續訓的實際數字另列 JSON，不把缺值寫成零。

PyTorch allocator 是本訓練程序高水位；RAM 是程序 working set，另每秒取樣 RSS；`nvidia-smi memory.used` 是整卡取樣，包含其他軟體且可能錯過短峰值。這不是 GPU 專用程序顯存，也不是可保證的最低需求。此固定 512／rank 4 workload 在 12 GiB 顯卡可執行，但 RAM 峰值約 20.9 GiB；安排容量需包含平台、引擎與系統。未驗證 1024、多圖／長時間訓練、RTX 4080、FLUX 或畫風品質，因此 E04 的其他工作負載仍未關閉。

自動測試涵蓋生成原 UUID 恢復、新提交互斥、驗證後才發生衝突時不送 prompt、FLUX、遠端不佔本機租約、並發提交序列化、寫入失敗／程序突然結束的鎖釋放、資料與完整 checkpoint 篡改、設定／環境／步數一致性、新 UUID 續訓及明確停止。完整品質入口與最終數量另記 CHANGELOG；GPU 工作和後端生成回歸分開執行。

原始資料／權重／日誌在忽略的 `runtime/training/`；Git 僅保存程式、版本、hash 與摘要。作者圖仍有 T02 caption／來源／角色審查缺項；真正作者試訓前提醒完成審查，品質評估前另核對未參與調參的最終保留圖。
