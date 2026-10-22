# Q10 格式與高風險流程維護驗收（2026-10-23）

## 範圍與分開審閱

格式與工具設定為獨立提交 `c465726`；後續狀態重構另行提交。沒有新功能、資料遷移或公開 JSON 變更。第一批只整理四個 Python 任務模組、生成面板／請求／事件與全域 CSS，加上品質工具；未全庫格式化。

`quality-scope.json` 明列 16 個唯一檔案。`scripts/check_style.py` 預設不寫入，明確 `--write` 才格式化；Ruff／Prettier／CSS-tree 固定版本由 dev lock／package-lock 安裝。Q06 入口新增 style／static 為第一階段，CI 改用 dev lock。

## 格式語意與靜態規則

- 格式前後四個 Python 模組 `ast.dump(..., include_attributes=False)` 相同。
- TypeScript transpile 後正規化結果相同；GenerationPanel 的 script、Vue template 編譯結果及 style 相同；全域 CSS 正規化內容相同。只有版面、引號與換行整理。
- 第二次執行 `python scripts/check_style.py --write`，16 檔 SHA256 完全不變；檢查模式、型別與 CSS 規則均通過。
- Ruff stdin 注入未定義名稱，回傳 1 且包含 F821；CSS 探針驗證語法、重複普通／自訂屬性、無效 hex，並確認不同 selector 的覆蓋與自訂屬性大小寫合法。CSS 探針納入 `npm run lint`。
- runner 測試對五個階段逐一注入失敗，保留非零碼且不執行後續步驟。缺 npm 同樣失敗。
- `npm ci`、`pip check` 通過；最終 `npm audit` 為 0 項已知問題。CSS 使用少量 AST 規則，沒有額外 glob 工具鏈或 lint autofix。

## 狀態重構與操作邊界

GenerationPanel 使用 `freezeCurrentSubmission`、`frozenSubmissionDescriptor`、`clearConfirmedSubmission`，清楚隔開本機保存、原版本端點選擇與明確回覆後清除；提交狀態文字改為具名 computed，文字與 disabled 語意保留。後端用 `_matches_recorded_submission` 與 `_submission_guard_active` 命名相同請求與 60 秒活躍提交保護；各專用 workflow 的驗證仍獨立。

四流程實際 SFC setup 回歸驗證：

1. localStorage 保存失敗，不產生 POST，pending 為空，busy 清除。
2. 保存後才 POST，處理中再點不重送。
3. 不完整 JSON 保留原 UUID／pending；目前表單被修改或 blocked 時，恢復仍使用原 body、精確 seed 與原端點。
4. 明確 409 回覆後才清除原 pending；目前表單仍被 blocking 條件阻擋，不自動建立新任務。

既有六種新舊 descriptor／版本、遺失回應、明確錯誤及原 bytes 測試保留；後端活躍提交／過期後查詢擴及 uploading_input，並沿用取消／停止、revision 競爭、終態與診斷回歸。重構後先通過 43 項相關後端與四流程前端契約，再執行完整品質入口。

完整品質入口通過：574 項後端（1 項既有 Windows symlink 權限跳過）、前端型別／正式建置、四組契約與 19 項瀏覽器回歸。README／ROADMAP／索引及本輪文件的 120 個本地連結核對無缺失。

重跑命令見 [品質指南](../quality-checks.md) 與 [維護規則](../maintenance.md)。測試使用臨時 DATA／模擬引擎，不讀寫使用者資料，不提供新的 GPU／全站 V06 驗收結論。
