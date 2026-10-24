# V02 v1／v2 原提交恢復驗收（2026-10-23）

V02-01、V02-02 及主項完成。以實際 Chromium、正式 Vue 建置、真實 FastAPI／SQLite／素材與輸入檔案，在全新臨時 DATA 製造故障；引擎 HTTP 為固定 `mock-engine.invalid` 的 MockTransport，不連正式 ComfyUI、不進行 GPU 推論、不改正式 DATA。這項驗收不代替 V01 實機觸控或生成品質驗收。

## 案例與故障

`frontend/tests/inpaint-recovery.spec.ts` 共 9 項，不自動重試：

| 維度 | 固定條件／故障 |
| --- | --- |
| 視窗 | 1440 × 900、390 × 900 |
| 原流程 | v1 舊 pending 無版本標記，POST /api/inpaint/generate；v2 帶本機標記，送出前移除，POST /api/inpaint-feather/generate |
| 引擎結果未知 | 實際上傳後，引擎 /prompt 發生 ReadTimeout，平台保存 unknown；瀏覽器攔截器先讓真實 API 完成，再中斷該回覆，保留原 pending |
| 平台回覆不完整 | 引擎接受一次提交，平台保存 queued；攔截器先取得真實 API 結果，再回傳 HTTP 200 的截斷 JSON，保留原 pending |
| 錯誤確認回覆 | 每個恢復案例先回傳其他 UUID 的合法 HTTP 200 JSON，須保留原 pending；再重新載入，明確手動恢復才取得正確 UUID |
| 未知版本 | 390px 另測未知本機版本標記：重載／點擊恢復不發出生成請求、不清除或改寫原記錄 |

前四個維度構成 2 視窗 × 2 版本 × 2 初始故障的 8 案例。v2 從實際表單點擊「生成圖片」開始；v1 用瀏覽器 fetch 重建舊客戶端的完整原 body 與無標記 pending，再由現行 UI 讀取與恢復。沒有讓現行新生成按鈕偽裝成 v1，也沒有預先塞入假的平台任務替代真實提交。

原設定為 128 × 64、stretch、20 steps、CFG 7、euler／normal、denoise 0.7、grow 4、seed 字串 `18446744073709551615`，無 LoRA；v2 半徑 8。原圖與二值遮罩為 fixture 中不同的 64 × 64 素材，遮罩右半白、左半黑。這是測試條件，不是品質推薦。

## 核對結果

- 每案例首次提交與兩次明確恢復的 API 路徑及原 body bytes 相同，UUID、原引擎、素材順序、seed 與參數沒有替換。v2 本機標記不進 API，v1 不新增 feather_radius，也沒有獨立合成遮罩。
- 重新載入後，新表單為空、羽化半徑為 0；原 pending 原文字仍一致，恢復使用原值。原 v1 仍為 10 節點，合成使用二值遮罩；v2 保持 11 節點、半徑 8，合成使用同次 blend 遮罩。
- 推進瀏覽器時間 16 秒，涵蓋 15 秒狀態輪詢週期，再按「更新任務狀態」：沒有自動發送生成 API，也沒有新增 UUID。狀態確認讀取原 UUID 的 history／queue；空歷史／空佇列保持 unknown，已接受且有成功歷史才 completed。
- 最後兩次手動恢復前將模擬引擎設為 offline：後端仍可查原 UUID 帳本返回既有任務，不重做模型預檢、圖片上傳或 /prompt。此段引擎 HTTP 只有可能的 GET 查詢，沒有 POST。
- 每案例引擎 /prompt 恰為 1 次；v1 上傳恰為 2 份、v2 恰為 3 份，目的地為原 UUID、overwrite=false。實際 multipart 圖片 bytes 的 SHA256 等於任務保存的來源／二值／合成輸入雜湊；恢復後從圖片 API 讀取的 PNG 雜湊仍相同。
- 任務原引擎、workflow、reference_settings、雙素材快照、半徑與上傳位置不變。原始任務 JSON 的數字 seed 另以原文字核對，避免先經 JavaScript Number 捨入再比較。
- 兩種視窗的恢復按鈕可操作，原 UUID 與提示可見且沒有水平溢出；保存全頁及任務區截圖。這不是 V06 全站視覺／讀屏通過。

「不重送」指不再次向引擎上傳或提交生成。手動按恢復仍依既有 API 契約 POST **原生成端點與完整原 body**，後端先查原 UUID 帳本並返回既有紀錄；這與自動或新增引擎生成不同。更新狀態的 /api/jobs/{id}/refresh 雖是 POST，其上游僅查 history／queue。測試分別保存平台與引擎兩層紀錄，沒有以平台 POST 次數代替引擎提交次數。

## 發現與修正

修正前的實際元件收到其他 UUID 的 HTTP 200 JSON，會清除 pending，使恢復按鈕消失；Node 六端點契約亦確認 null／空物件被誤當成成功。現在 `generationRequest.ts` 只有在成功回覆為物件、id 等於凍結 request_id 時才確認；null、陣列、缺少 id 與其他任務 ID 都保留原請求。明確錯誤若含其他 detail.job_id，也不能清除本次 pending；原本可確認的 API 拒絕與屬於原 UUID 的失敗仍沿用既有清除規則。

沒有改動 localStorage key、版本標記、workflow schema、UUID 生成或後端冪等協定。確認平台已有原任務不代表生成完成，unknown 仍須查原歷史。六種新舊生成 descriptor 都加入無效成功 JSON 與錯誤 job_id 回歸；保存失敗不 POST、處理中不重送、凍結參數及已確認拒絕等既有 SFC 測試仍通過。

fixture 新增局部編輯必要節點的確切介面、multipart 上傳回執與 SHA256、原生二值素材，以及最多 1,000 筆 HTTP 方法／路徑與上傳雜湊的唯讀測試紀錄；不增加正式 API。fixture 純格式整理先獨立提交 `98b8964`，Python AST 前後相同、Ruff 通過，再加入功能；fixture 與新瀏覽器測試納入明確品質 scope。

## 重跑與證據

```powershell
Set-Location frontend
npm.cmd run build
npm.cmd run check:api
npm.cmd run test:browser -- inpaint-recovery.spec.ts
Set-Location ..
.\.venv\Scripts\python.exe scripts/check_quality.py
```

完整入口的格式／靜態檢查、574 項後端（1 項既有 Windows symlink 權限跳過）、Vue 型別／建置、四組前端契約與 34 項瀏覽器通過。9 項 V02 專用回歸亦全部通過。依賴與埠隔離見 [品質指南](../quality-checks.md)。

每個完整案例保存 pending.png／pending-panel.png、original-pending.json 與 recovery-evidence.json，包含原始 pending、平台請求 body、原始任務 JSON、恢復後原始 JSON、輸入 SHA256、實際上傳紀錄、狀態查詢及引擎計數。另保存 original-source.png／original-mask.png 原素材，以及 prepared-source.png／prepared-mask.png、v2 的 prepared-blend.png；逐份核對實際 bytes 的 SHA256 後保存，可獨立重新核對雜湊。上述檔案也附於 HTML 報告，位於忽略的 runtime/quality/browser-report 與 browser-results；CI 會保存整個 runtime/quality 14 天。下次執行會重建輸出，若需長期保留應先另存證據。

修正前失敗證據另保留在忽略的 runtime/v02-before-browser（畫面、錄影、trace）、runtime/v02-before.log 與 v02-receipt-before.log；不將正式圖片或 runtime 加入 Git。結案只關閉 [ROADMAP V02](../../CHANGELOG.MD#v02)，V01 實機觸控維持待驗收；剩餘 35 主項／61 子項，共 96 個未勾選框。
