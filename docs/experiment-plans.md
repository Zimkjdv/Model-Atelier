# 固定測試集與參數比較方案

創作工作台的「固定測試集與參數比較」提供 checkpoint 文生圖的唯讀方案預覽。先選模型並確認完整設定，再選 Steps、CFG 或 Seed 一個參數軸，輸入 1–4 個 JSON 值。Seed 必須使用字串，例如 `["9007199254740993", "18446744073709551615"]`；不轉成 JavaScript number。數值超界、型別不符或正規化後重複會拒絕，不自動截斷或調低設定。

固定測試集為自行編寫的 `experiments/general-illustration-v1.json`，版本 1；Git 保持 LF 換行，API 回報完整檔案 bytes 的 SHA256。案例為黑白木椅說明書、山湖構圖，以及同一成年旅人在書店／車站的兩個場景，各有人工評估要點。共同 `character_key` 只是比較分組，不提供角色鎖定。未選案例時沿用目前提示詞；選固定案例會明確替換正提示詞，保留負提示詞、尺寸、原引擎、模型、有序 LoRA 及其餘參數。方案標題另標案例與參數值。

預計任務數為案例數乘以參數值數，最多 8 次，每次 1 張。例如兩個案例與兩個 seed 會列出四份完整設定。超過上限回傳 422，沒有部分方案或隱藏批次。圖生圖、FLUX 及任何參考素材關聯目前不支援比較預覽。

按「載入這組設定」會取代目前表單，作為未保存的新草稿；未保存變更有明確提示，原已保存草稿與任務保留。每組需另按原生成按鈕，才能建立任務並走既有即時能力與模型檢查。方案保持原基準快照，載入其他組後仍可繼續選擇；要換基準則重新預覽。顯示「已載入過」只代表表單載入，不代表生成成功。結果匯入後可在[作品比較與評分](artwork-comparison.md)人工加入比較。

「匯出比較方案 JSON」先準備完整文件，再提供明確下載連結與 JSON 內容。文件包含基準設定、流程 ID、單一軸、案例與測試集版本／hash、預計數量及所有設定快照。`plan_sha256` 使用排序鍵的 UTF-8 JSON 計算，排除該 hash 與展示 warnings；匯出重新建立原方案並核對預覽 hash，測試集或輸入變更回傳 409，需重新預覽。匯出後修改表單不會改寫「上次匯出」文件。

| API | 行為 |
| --- | --- |
| `GET /api/experiments/suite` | 讀取已審查的固定案例、版本與檔案 SHA256；無效測試集回傳 503 |
| `POST /api/experiments/preview` | 完整驗證設定，回傳最多八份單張方案；不寫入 SQLite、不連線引擎 |
| `POST /api/experiments/export` | 同一輸入加 `expected_plan_sha256` 核對，可下載 `model-atelier-comparison-plan.json` |

POST 輸入包含 `title`、完整的 `settings`、`axis`、`values`、`case_ids`；不接受 revision、任務 UUID、自訂 workflow 或未知欄位。請求最多 256 KiB，匯出文件最多 1 MiB。完整 `settings` 沿用 checkpoint 草稿欄位但排除 revision；可由創作設定匯出文件取得。不存在的案例、空模型、空目前提示詞及重複案例拒絕。測試集損壞時仍可比較目前提示詞，不能借用未驗證案例。

此階段沒有自動批次提交、重試、方案持久化／匯入或結果自動關聯，也沒有耗時／VRAM 估算及自動品質評分。匯出的是比較方案，實際提交的完整 workflow 與模型／環境快照仍由原任務系統保存。2026-10-08 已完成 Pony／Animagine 固定四案例的 GPU 比較與原圖觀察，見 [實測結果](validation/general-illustration-suite-rtx3060.md)；更多模型／seed／參數軸、LoRA 強度比較與 RTX 4080 仍待後續驗收。

2026-10-05：382 項後端測試（381 通過、1 項既有 Windows 權限跳過）、Vue 型別／建置通過。桌面瀏覽器驗證四份案例／seed 方案、重複值拒絕、最大 seed 精確載入、原有 LoRA 順序、案例提示詞替換、基準快照保留與 JSON bytes／下載檔名；未驗證瀏覽器原生下載落盤及窄視窗。沒有新增 GPU 任務或正式資料；隔離資料仍為 4 任務／4 作品／2 checkpoint 草稿／1 FLUX 草稿，僅前一項人工評分保留。畫面與 JSON 證據保存在 `runtime/experiment-plan-ui-20261005.png`、`runtime/comparison-plan-ui-20261005.json`。
