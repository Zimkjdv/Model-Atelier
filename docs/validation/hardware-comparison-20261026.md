# E03：兩機相同配置比較與 4080 較高負載

E02 已以 `a74dfbe` commit／push 後，才開始本項。2026-10-26（Asia/Taipei），使用可取得的 RTX 3060 歷史原報告／原任務，與本機 RTX 4080 新實測比較；沒有假裝重新連上舊機。完整設定、workflow、條件來源、原報告 hash、圖片 hash、資源與比較結果見 [JSON](hardware-comparison-20261026.json)。

## 相同配置，分別保留兩機環境

固定 Pony V6 XL，完整 SHA256 `67ab2fd8ec439a89b3fedb15cc65f54336af163c7eb5e4f2acc98f090a29b0b3`；768×768、batch 1、seed 字串 `9007199254740993`、20 步、CFG 5.5、DPM++ 2M／Karras、denoise 1，沒有 LoRA／參考圖／ControlNet。模型／CLIP float16、VAE bfloat16、預設 dynamic VRAM／CPU offload／PyTorch attention。ComfyUI 同 commit `15eb748b3ec5f8a0a2d470b7fb280e2d7579f916`、Torch 2.14.0+cu130。

3060 依 [原冷載入紀錄](pony-v6-xl-rtx3060.md)及保存的原始七節點流程；4080 使用 E02 離線驗收後新啟動的引擎，這是該程序第一個 prompt。兩者 history 的 `execution_cached.nodes` 均為空，4080 啟動／dtype／載入日誌保存在 `runtime/e02-engine-restored.err.log`。條件中的 cold 指引擎程序未載入模型；OS 檔案快取未控制。未觀察到的 kernel 累積精度保持未知。

| 同定義觀察 | RTX 3060 | RTX 4080 |
| --- | ---: | ---: |
| 原任務 | `e24da88f-3de2-4248-9693-abcc1272154e` | `578dcc3b-5fef-4eb4-8879-ff2eb03c0fb7` |
| 引擎 history start → success | 22.551 秒 | 9.380 秒 |
| 原驗收器 submission → observed success | 22.875 秒 | 10.437 秒 |
| nvidia-smi 整卡取樣最高 | 10,451,156,992 bytes | 9,259,974,656 bytes |
| 有效整卡取樣數 | 12 | 6 |
| 原引擎連續 RAM 觀察最高 | 未取得 | 35,204,919,296 bytes |
| 任務專用 VRAM 峰值 | 未知 | 未知 |

此次引擎時間比為 2.4042（3060／4080），各僅一筆冷載入觀察，包含模型載入、解碼及快取，不是純 GPU 取樣或穩定加速保證。3060 是 Windows 10 build 19045／驅動 616.56，4080 是 Windows 11 build 26200／驅動 617.42；背景程式、桌面、磁碟快取與量測長度也不同。

舊文件 22.55／22.880 秒是當時摘要，本表保留原 history 毫秒相減及目前保存原報告的 22.551／22.875。舊任務沒有 E05 連續資源，不能回填；`compare_hardware.observation` 只在獨立報告計算舊 history 耗時，不寫舊 SQLite。

## 獨立較高負載

同一固定 Pony 權重、seed、sampler／scheduler、CFG／denoise，尺寸另改為 **1536×1536、30 步、batch 1**。任務 `d2302547-f65e-482a-b536-c4f17009ca70`，作品 `1ec79fda-73e8-5105-a029-751a92e9b02b`；引擎 15.171 秒、提交至觀察成功 16.047 秒。整卡取樣最高 9,938,403,328 bytes；完整 RAM／原引擎觀察另列 JSON，任務專用峰值仍為 null。

此例接在 baseline 後，Pony 權重與部分文字編碼仍在快取；不能拿耗時與冷載入 baseline 直接算像素擴充效率。單次提交、成功 history、1536² 原圖解碼／SHA256、完整 workflow、精確 seed／30 步／尺寸的保存與還原全部通過。它只證明這筆配置成功，不代表最高可執行尺寸、3060 的必要門檻或所有 NVIDIA 顯卡均相容；沒有刻意耗盡整張卡找極限。

## 可重跑工具與檢查

```powershell
.\.venv\Scripts\python.exe -m scripts.verify_hardware run --case pony -- --report runtime/new-cold.json
.\.venv\Scripts\python.exe -m scripts.verify_hardware run --case pony-high -- --report runtime/new-high.json
.\.venv\Scripts\python.exe -m scripts.compare_hardware --left runtime/e03-rtx3060-observation-20261026.json --right runtime/e03-rtx4080-observation-20261026.json --report runtime/new-comparison.json
```

第一項需自行確認是新程序且沒有其他工作；CLI 不會自動把目前快取標成 cold。`observation` 接收已驗證報告、原任務和各條件的明確來源，保留原文；`compare` 逐項核對模型／元件 hash、dtype、快取／卸載、Torch／ComfyUI 版本、完整精確設定及完整 workflow。未知／缺來源或任何差異都列為不匹配，不提供時間比。較高負載使用獨立原報告，不混進相同配置比較；訓練觀察直接拒絕混用。

新增比較器／測試加入 quality scope，因其決定對照是否成立。格式、靜態、型別檢查及硬體／驗收器／量測相關回歸通過，數量見 CHANGELOG。E02 的完整 784 項後端及 122 項 Chromium 基線已先通過；本項未修改前端、生成協調或取樣產品程式。
