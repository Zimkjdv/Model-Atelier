# Checkpoint 圖生圖：RTX 3060 驗收

日期：2026-10-05。這是一般風景的流程整合驗收，未評估畫風重現、角色一致性或效能排行。

使用已安裝的 `pony-v6-xl.safetensors`，ComfyUI 0.34.0、PyTorch 2.14.0+cu130、RTX 3060 12 GiB。輸入是平台既有 Pony 一般風景作品的 PNG 副本；平台資料隔離至 `runtime/image-live-data-20261005`，正式資料庫與作品不改動。測試資料保留作為驗收證據，runtime 不納入 Git。

| 項目 | 實測值 |
| --- | --- |
| 流程 | `checkpoint-image2image-v1`，8 節點，無 LoRA |
| 尺寸／處理 | 512×512、等比縮放補白、RGB PNG |
| 取樣 | 20 steps、CFG 5.5、DPM++ 2M／Karras、denoise 0.5 |
| Seed | `18446744073709551615`，完整 uint64 |
| 任務 | `b9d9261b-88cc-4d75-83f6-6d22b9791f98` |
| 作品 | `6ebeffc8-2386-566e-8ad9-2586a2f52fc2` |
| 結果 | 原引擎 successful history、512×512 PNG 匯入成功 |

確認原生 `/upload/image` 的回執、以 `/view?type=input` 讀取內容並核對處理後 SHA256；相同 UUID 重送只取回原任務。作品沿用素材與前處理快照，任務／作品還原均保留完整設定；被任務引用的素材封存回傳 409。

自動測試另外涵蓋離線、缺 checkpoint／必要節點、介面變動、來源檔案變更、上傳目的地不符、上傳逾時、上傳時引擎變更、生成回應遺失、引用／封存交易衝突及有序 LoRA 圖連接。GPU 驗收沒有 LoRA；其他模型、SD 1.x、局部編輯、adapter／ControlNet、畫風品質及 RTX 4080 不在此實測範圍內。
