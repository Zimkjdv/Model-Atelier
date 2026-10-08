# 單一 LoRA 強度與 seed 比較（2026-10-08）

固定 Animagine 4.0 Opt 與 IKEA 黑白畫風 LoRA，來源、固定修訂、SHA256 與授權未知限制見 [原驗收](animagine-multi-lora-rtx3060.md)。每次先核對實際權重大小與完整雜湊；沒有新增權重或調整推薦預設。

同一黑白椅子組裝提示詞、負提示詞、1024×1024、28 steps、CFG 5、euler_ancestral／normal、denoise 1、batch 1。只比較模型強度 0.5／1.0 與兩個字串 seed；CLIP 強度固定 1。每組單獨執行，不提供自動批次。

RTX 3060 12 GiB、約 64 GiB RAM、Python 3.12.10、ComfyUI 0.34.0、PyTorch 2.14.0+cu130；模型／CLIP FP16、VAE bfloat16、動態 VRAM／CPU offload。第一張冷載入；後續模型及節點可能快取、patch 重新準備。提交至觀察成功歷史的時間包含佇列／網路／初始化；整卡低頻取樣包含其他程序，不是純推論 benchmark、連續峰值或最低顯存需求。

| Profile | 模型／CLIP 強度 | Seed | 提交至歷史確認 | 整卡取樣最高／有效樣本 |
| --- | --- | --- | --- | --- |
| `style` | 1.0／1 | `9007199254740993` | 45.359 s | 9,921,626,112 bytes／22 |
| `style-half` | 0.5／1 | `9007199254740993` | 31.687 s | 11,805,917,184 bytes／16 |
| `style-seed2` | 1.0／1 | `9007199254740995` | 31.719 s | 11,799,625,728 bytes／16 |
| `style-half-seed2` | 0.5／1 | `9007199254740995` | 31.719 s | 11,364,466,688 bytes／16 |

人工原圖觀察：四組都呈现清楚黑白線條，沒有前次 LCM 多項流程的淡化問題。強度 1 的兩張有完成的椅子與書本／說明書，但沒有完整的組裝步驟；第二個 seed 出現額外數字。強度 0.5 在第一個 seed 有不合理的 U 形輪廓，第二個 seed 的座面與書本融合、額外物件更多。兩個 seed 的構圖與細節皆不同；此小樣本不證明強度 1 普遍更好，也不能量化畫風相似度或保證提示遵循。

四個八節點任務均只提交一次、成功匯入原图；核對完整 workflow、字串 seed、原模型／LoRA 快照與設定還原。關閉 ComfyUI 後四份報告 GET-only 核對再次通過，沒有重送任務。正式資料維持 5 任務／3 作品／0 草稿／0 方案，四個測試任務與作品保留於隔離資料。

重跑範例（平台與 ComfyUI 須啟動，模型／LoRA 已同步並登記）：

```powershell
.\.venv\Scripts\python.exe -m scripts.verify_multi_lora --profile style-half --platform http://127.0.0.1:8001 --report runtime/my-style-half.json
.\.venv\Scripts\python.exe -m scripts.verify_multi_lora --profile style-half --platform http://127.0.0.1:8001 --report runtime/my-style-half.json --verify-report
```

其他 profile 為 `style`、`style-seed2`、`style-half-seed2`。新生成使用不存在的 report 路徑，既有報告只能用原 profile 的 `--verify-report`，只做 GET，不重新生成、同步或匯入。錯誤 profile／改動設定或原快照會在核對前拒絕。

隔離證據保存於 `runtime/quality-live-data-20261008` 及四份 `runtime/style-*-seed*-20261008.json`，不納入 Git。409 項後端測試（408 通過、1 項既有 Windows 權限跳過）。本項沒有 UI 變更；其他畫風、多 LoRA 品質、RTX 4080 與訓練仍待驗證。
