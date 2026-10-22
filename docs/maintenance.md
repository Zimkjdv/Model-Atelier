# 高風險流程的維護規則

先讀 [任務與原引擎](architecture.md#任務與原引擎)、[前端 API 契約](frontend-api.md) 與本頁。格式、狀態重構及功能差異應分開提交，保留可審閱的原始資料格式與操作邊界。

## 格式與靜態檢查

品質環境使用 `requirements-dev.lock.txt`（包含既有 runtime lock 與 Ruff 0.17.1），frontend 使用 package-lock 精確鎖定 Prettier 3.9.10、CSS-tree 3.2.1。正式使用者安裝仍可只用 runtime lock。

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.lock.txt
.\.venv\Scripts\python.exe scripts/check_style.py
.\.venv\Scripts\python.exe scripts/check_style.py --write
.\.venv\Scripts\python.exe scripts/check_quality.py
```

預設只檢查，不改檔；`--write` 明確格式化後仍須通過靜態檢查，不執行 lint autofix。frontend 可單獨執行 `npm.cmd run format:check`、`npm.cmd run format`、`npm.cmd run lint`。任一步失敗回傳非零，完整 Q06 入口與 CI 先跑 style／static 再跑既有測試；`--skip-browser` 仍不能跳過格式檢查。

| 語言 | 規則與用途 |
| --- | --- |
| Python | Ruff format：100 欄、4 空格、單引號、LF；lint E9／F63／F7／F811／F821–823／F841，檢查語法、錯誤比較／控制流程、重複定義、未定義名稱與未使用的區域賦值 |
| TypeScript／Vue | Prettier：100 欄、2 空格、單引號、不加語句分號、LF，Vue 使用 strict whitespace；vue-tsc 檢查整個前端的型別與模板 |
| CSS | Prettier 保持宣告順序；CSS-tree AST 檢查語法錯誤、同區塊重複宣告／自訂屬性及無效 hex 色碼。不同 selector／media 的覆蓋合法，自訂屬性區分大小寫；不是完整 CSS 相容性或視覺檢查 |

設定見 `ruff.toml`、`.prettierrc.json`、`.gitattributes` 與 `quality-scope.json`；後者是**明確檔案清單**。第一批納管 submissions／jobs／cancellation／stopping、GenerationPanel／generationRequest／jobEvents、全域 style.css，以及對應品質工具。只對列出的檔案執行格式／Ruff／CSS 檢查，不以 `format .` 一次改寫整庫；CSS 檢查目前針對全域 CSS，Vue style 由 Prettier 格式化。

新建或實質修改高風險模組時，將該檔加入 scope 並在同次變更說明理由；歷史模組逐批加入。字寬是 formatter 的換行目標，不是額外的強制 lint 長度。資料 JSON、模型 manifest、歷史 workflow、runtime 與使用者 DATA 不交給格式命令改寫。若要加入新規則，先證明能抓到具體錯誤，避免預設全開或大量忽略。

工具語意依 [Ruff formatter](https://docs.astral.sh/ruff/formatter/)、[Ruff lint 配置](https://docs.astral.sh/ruff/linter/)、[Prettier 選項](https://prettier.io/docs/options) 與 [CSS-tree AST](https://github.com/csstree/csstree/blob/master/docs/ast.md)；未啟用 formatter preview 或任意本機套件版本。

## 提交、恢復與終態

| 狀態／操作 | 維護邊界 |
| --- | --- |
| 未送出表單 | 可編輯不代表已保存；先凍結完整參數、UUID、流程版本及原端點，成功保存 pending 後才可發出 POST |
| 提交結果未知 | 網路／不完整 JSON／無法確認的 5xx 不能清除原 pending；恢復使用原凍結內容，不讀目前表單，不另產生 UUID 或自動重試 |
| 已有任務 | 同 UUID 先核對既有圖／來源／實驗設定再返回；不能用新引擎、新元件或新版本重跑舊 UUID |
| 取消／停止確認中 | cancelling／cancel_unknown 與 stopping／stop_unknown 只確認原操作，不把查詢變成新的取消／停止 POST，不使用全域 interrupt |
| 終態 | completed／failed／cancelled／stopped 依原引擎歷史與擁有權確認；節點進度或佇列消失不能代替終態證據 |
| 修訂與過期觀察 | compare_update 核對取得觀察時的 revision；過期觀察不得覆蓋新狀態。busy 在 finally 清除，過期查詢不得改寫已離開／重新啟用的畫面 |

條件複雜時用具名函式或具名判斷說明上述操作；不要把不同 workflow 的 schema、來源 hash、遮罩／邊緣驗證或專用版本合併成較寬鬆的通用提交器。公開 JSON、精確 seed 字串、localStorage key、來源快照及原始 bytes 下載均屬相容契約。

格式整理先核對 Python AST、TypeScript／Vue 編譯結果及 CSS 值，再跑既有行為回歸；狀態重構另核對原 UUID、原端點、保存失敗、未知結果、revision 與終態。只有產品行為改動才增加新功能驗收，不能把「格式檢查通過」當成 GPU／UI／品質驗收。

本輪分開提交的格式語意比對、冪等檢查、錯誤探針與四流程操作邊界見 [Q10 驗收紀錄](validation/maintenance-20261023.md)。
