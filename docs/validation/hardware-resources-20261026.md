# E04：分開登記推論與訓練資源

E03 已先以 `3cce745` commit／push，才開始本項。2026-10-26（Asia/Taipei），新增 [可解析資源登記](hardware-resources-20261026.json)：九筆 RTX 4080 推論與兩筆真實合成資料訓練各自保存硬體、模型／資料／環境、配置與測量定義；另保留一次編碼失敗。原始權重、run、完整日誌／取樣與圖片保存在本機，不進 Git。

## 測量定義

| 指標 | 來源與範圍 |
| --- | --- |
| 推論引擎耗時 | 原 history start → success，含載入／快取／解碼；不是純取樣時間 |
| 推論 RAM | 原引擎主機 total−free 的背景取樣最高；包含其他程序，不是 ComfyUI RSS |
| 推論引擎裝置觀察 | 原 `/system_stats` total−free；可能包含 allocator 可回收快取，不能當成 nvidia-smi 整卡用量 |
| 整卡 VRAM | nvidia-smi `memory.used` 取樣最高，含桌面與其他軟體；可能漏掉短峰值 |
| 訓練耗時 | worker 的 monotonic elapsed，含驗證、匯入、前處理、訓練及保存；不是單步訓練時間 |
| 訓練 allocator | 獨立 worker 在重設後的 Torch allocated／reserved 高水位；不是整卡或實體任務專用峰值 |
| 訓練 RAM | worker RSS 取樣、以及取樣時讀到的 Windows peak working set 計數；不是整個主機 RAM |

訓練監測執行在環境／基底驗證之後、載入 Torch／trainer 之前；每輪 nvidia-smi 查詢完成後等待一秒，最多 3600 點，實際間隔包含查詢及排程。程序高水位計數也只能保留實際讀到的值。原始取樣及各來源的 byte 值保留於 run／JSON；以下 GiB = bytes ÷ 2³⁰。沒有成功取樣或未提供的欄位保持 null，零值與未知分開。所有紀錄的 `task_vram_peak_bytes` 維持 null，不從上述量測推導最低硬體需求。

## 推論登記

沿用 [E02 八流程](rtx4080-workflows-20261026.md)及 [E03 獨立較高負載](hardware-comparison-20261026.md)，不新增或重跑歷史 UUID。每筆保留設定、模型／有序 LoRA／元件快照、完整 workflow hash、耗時、原引擎連續觀察與整卡樣本數。

| 工作負載 | 整卡 VRAM 觀察最高 GiB | 引擎主機 RAM 觀察最高 GiB |
| --- | ---: | ---: |
| Pony 768² 文生圖 | 8.64 | 34.69 |
| Animagine 1024² 文生圖 | 8.77 | 34.94 |
| 有序雙 LoRA | 8.79 | 35.00 |
| 圖生圖 | 11.19 | 34.56 |
| 一般修補 | 10.05 | 33.14 |
| 羽化修補 | 10.85 | 33.03 |
| 單張 adapter | 13.15 | 36.99 |
| Canny | 11.25 | 37.98 |
| Pony 1536²／30 步 | 9.26 | 32.77 |

這些是不同時刻、不同快取及背景負載的整體觀察，不用表格排序推論各流程必要容量。3060 的 [T03](training-runtime-20261025.md)／[T06](training-control-20261025.md) 舊證據保持原樣，JSON 附來源檔案 hash，不以 4080 觀察回填。

## RTX 4080 訓練

獨立 training `.venv` 同樣有舊電腦 Python 路徑，先以本機 Python 3.12 修復並重新安裝本機 sd-scripts editable 路徑；`pip check`、固定精確依賴、乾淨 trainer commit 與離線 tokenizer hash 全部通過。沿用 sd-scripts `11d8cedd0c67b93a10f8b2d75f43554f6f12c794`、Torch 2.14.0+cu130／CUDA 13.0；實際 worker 回報 RTX 4080 index 0。

依 T01／T03 技術路線使用固定 Animagine XL 4.0 Opt，SHA256 `6327eca98bfb6538dd7a4edce22484a1bbc57a8cff6b11d075d40da1afb847ac`。兩個新資料包均由 Pillow 畫幾何圖形，train／validation／test 各一張、不同內容與分組，只有 train 的一張圖片及 caption 進入 trainer。沒有使用或批准作者圖片。

兩筆配置均為 UNet LoRA rank／alpha 4、batch 1、fp16、AdamW、LR 0.0001、constant scheduler、SDPA、gradient checkpointing、latent／文字編碼快取、seed 42，完整 3 更新、每步保存狀態；尺寸分別 512 與 1024。新增 fixture 選項會實際建立對應尺寸的 PNG；worker 日誌確認 bucket 分別為 `(512, 512)`／`(1024, 1024)`，不是只改 CLI 而實際仍訓練 512。

| 指標 | 512² | 1024² |
| --- | ---: | ---: |
| run | `e9324ef1-7c59-44f5-aa72-e12ef5292ec9` | `8f3d75c1-1e86-4916-92b6-b963f5e90814` |
| worker elapsed 秒 | 53.797 | 52.219 |
| 有效資源點數 | 43 | 42 |
| Torch allocated 峰值 GiB | 5.21 | 5.81 |
| Torch reserved 峰值 GiB | 5.45 | 6.33 |
| worker RSS 觀察最高 GiB | 20.91 | 20.89 |
| Windows peak working set 觀察最高 GiB | 20.95 | 20.93 |
| 整卡 VRAM 觀察最高 GiB | 7.36 | 8.24 |

每筆均確認 final `train_state.current_step=3`、四份 LoRA safetensors 的大小／完整 hash、原 manifest receipt、worker 已退出及運算租約已釋放。完整 trainer arguments、環境／資料包／基底識別、日誌與資源檔案 hash、封存時整合層程式 hash 亦保存於 JSON。兩次載入與檔案快取不同，三步測試不能用總耗時判定 1024 比 512 更快，也不代表長時間、多張資料、其他 rank 或作者訓練品質。

## 保留的失敗與修正

首次 512 run `56011caa-a3b7-4e87-9c6d-1a759ccbfcdf` 在 trainer 列印 `学習開始` 時發生 `UnicodeEncodeError: cp950`，未完成任何更新，原狀態／日誌／資源保留，程序及租約已釋放。

最小重現是隔離 Python `-I` 下列印相同文字；`-I` 忽略控制端的 `PYTHONIOENCODING`，新機 CP950 無法編碼日文。修正只在 worker 起點明確將 stdout／stderr 設成 UTF-8，保留 isolated mode、固定上游與既有提交／停止邊界。`backend/test_training_worker_encoding.py` 強制兩個串流為 CP950，再執行真實 worker bootstrap；修正前同一字元失敗，修正後 UTF-8 日文輸出通過，且沒有載入 GPU 套件。新 512 UUID 完整重跑成功，未覆寫或冒充原失敗 run 成功；1024 仍是第一次明確啟動。

訓練前確認引擎佇列為空，只停止本次擁有的 ComfyUI；完成後以原腳本恢復，平台確認重新連線至 CUDA index 0。平台服務持續運行，沒有停止其他應用程式。

## 重跑與驗證

```powershell
.\.venv\Scripts\python.exe -m scripts.training_fixture --output runtime/new-1024-fixture --resolution 1024
.\.venv\Scripts\python.exe -m scripts.training_run prepare --config runtime/new-1024-fixture/config.json
# 完成現有工作並停止受管理 ComfyUI 後，明確 run prepare 返回的新 UUID。
.\.venv\Scripts\python.exe -m scripts.training_run run --run-id <UUID>
# hardware 是帶時間戳記的 /api/system 主機快照；以下只讀取原 run，不訓練。
.\.venv\Scripts\python.exe -m scripts.hardware_resources --run-id <UUID> --hardware runtime/e04-host-20261026.json --report runtime/new-resource-report.json
```

資源匯出器拒絕未完成／未釋放資源、最終步數不足、產物 receipt／檔案 hash 不符的 run；推論／訓練分開識別，不混算峰值。新增及修改的工具／測試均加入 quality scope。最終空閒狀態下 798 項後端（1 既有跳過）、格式／靜態／型別、建置與契約通過；本項明確使用 `--skip-browser`，沿用 E02 已通過的 122 項 Chromium，沒有前端變更。另一次回歸與真實訓練並行，模擬提交被正確的運算互斥拒絕，產生 70 failures／36 errors；保留 `runtime/e04-quality-20261026.log`，租約釋放後原完整測試在 `runtime/e04-quality-idle-20261026.log` 全部通過，沒有為了測試移除互斥機制。

真正作者圖訓練前仍需完成 [T02 圖片審查](training-dataset-20261023.md)，品質評估另需未參與調參的獨立保留圖。此項關閉固定硬體／工作負載的資源實測，不將有限 smoke 認列為畫風品質或所有配置的容量保證。
