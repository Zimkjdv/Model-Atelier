# T04 產物回登與比較流程驗收

2026-10-25，T03 已先以 `db7ab91` commit／push，之後才開發 T04。固定產物來自 `a27f7a75-0791-41ca-958d-bf93bb1f1b89`：512 自製幾何圖、UNet rank 4、全程三步的技術 LoRA。**沒有用作者圖片訓練，也沒有作者畫風／角色品質通過結論。**

## 實際結果

產物大小 21,584,828 bytes，SHA `a60bdfdd75f1f41778edfa64612c7f9d6e1e6a594e463512e4972904bec4bb33`。回登先核對 T03 completed／資源釋放、最終 step 3 完整狀態封存、manifest 與實際權重，複製到受管理 LoRA 目錄並產生來源 sidecar／SHA。平台使用隔離的 `runtime/t04-platform`、1075 埠；正式 DATA 未用於驗收。

透過既有同步與 metadata API 回登成功，模型庫保留完整 run 版本、SDXL、大小／hash、trigger、資料／基底／trainer 識別及 `TECHNICAL TEST ONLY` 備註。沒有變更來源欄位的既有可信度契約。

| 分支 | 原 job | 原作品 | 實際驗收 |
| --- | --- | --- | --- |
| 無 LoRA 基準 | `dc53c8aa-44a2-40cc-831a-52f095d1c788` | `1aa06a1a-a8d4-550a-8165-58a0a002598b` | 七節點、LoRA 空陣列、512／4 steps，保存／hash／完整還原通過 |
| 新訓練候選 | `ef601857-6bac-427b-8740-2b2faac0fd35` | `f25603fb-ff49-5bb9-9269-a460e39960c3` | 八節點、model 1／CLIP 0；ComfyUI 記錄 UNet 722 patches、CLIP 0 patches，保存／hash／完整還原通過 |

兩分支相同提示詞與精確 seed `9007199254740993`。技術產物成功以原生 ComfyUI `LoraLoader` 載入，不需另作 key 轉換。等原引擎佇列空白後暫停，以 `--verify-report` 只 GET 原記錄，兩分支均通過；沒有重送生成，之後恢復原獨立環境及原參數，佇列 HTTP 核對成功。

完整來源、快照、作品 hash、原設定與方案 hash 見 [JSON](training-artifacts-20261025.json)。本輪實際 GPU 任務只有上述兩件；沒有執行 12 件畫風比較。

## 固定比較與限制

建立三題材 × 兩 seed × 兩分支的 12 格計畫，基準為空 LoRA、候選 UNet 1／CLIP 0；六份各含兩個 seed 的方案已透過現有 API 保存至隔離平台，沒有新增生成。後續最後版另外核對原基底／產物登記，封存相同 plan hash 並產生六格人工審查模板；原凍結版本保留、不覆寫。畫風題材沿用動漫 v1，角色題材沿用 R02 去除 adapter 的三組文字；完整來源文件 SHA 固定。

品質狀態保持未審查，最終保留圖仍待確認。現有作者資料尚需 T02 caption／來源用途及角色審查；真正試訓或品質驗收前依 [操作文件](../training/artifacts.md)提醒使用者。T04 完成的是回登與評估流程，512 幾何三步產物及四步技術生成不能證明動漫品質，也不能代表預設 1024／28 steps 的品質比較已執行。

自動測試覆蓋未完成／失敗／仍佔用的 run、權重及 sidecar／完整狀態篡改、禁止覆寫、同名 hash 衝突、遠端引擎拒絕、既有 API 回登、其他 metadata 保留、三題材／兩個大 seed、空基準／UNet 候選、人工模板、原 request_id 保存查回及零生成。全後端及最終定向檢查結果見 CHANGELOG；前端程式未變更，沿用同次 T03 已通過的 108 項 Chromium 回歸。
