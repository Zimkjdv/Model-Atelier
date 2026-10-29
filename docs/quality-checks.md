# 可重跑品質檢查

從根目錄執行完整檢查；任何階段失敗立即停止並回傳非零：

```powershell
.\.venv\Scripts\python.exe scripts/check_quality.py
```

依序執行範圍內格式／靜態檢查、後端 unittest、Vue 型別與正式建置、`npm test` 的前端契約檢查（API／生命週期、實驗、遮罩、控制與欄位預檢）、Playwright Chromium。格式規則見[格式與靜態檢查](#static-checks)，高風險提交邊界見[架構契約](architecture.md#submission-invariants)。`--skip-browser` 會明列跳過，不表示完整品質通過。

完整入口依檔名排序，每六份瀏覽器 spec 為一批；實際批數依 `frontend/tests/*.spec.ts` 計算，每檔自動納入一次。各批啟動新的 Playwright／Chromium 與臨時平台，使用不同埠及 `runtime/quality/browser-results/group-N`、`browser-report/group-N`。任一批失敗立即停止，單 worker、單案限制與零重試保留。此分批策略用於避免 Windows CI 的 Chromium `net::ERR_NO_BUFFER_SPACE` 與整套截止累積負荷，不代表已證明產品記憶體洩漏。

<a id="static-checks"></a>

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

格式、狀態重構與行為驗收的邊界見[架構維護規則](architecture.md#submission-invariants)。

## 乾淨安裝

Python 3.12、Node.js 24、Git；在新的 checkout 執行：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.lock.txt
Set-Location frontend
npm.cmd ci
npx.cmd playwright install chromium
Set-Location ..
.\.venv\Scripts\python.exe scripts/check_quality.py
```

不需要 ComfyUI、GPU、權重或使用者作品。前端使用 package-lock.json，Playwright 固定 1.64.1；瀏覽器另由該版本安裝。可在 frontend 以 `npm.cmd run test:browser` 單獨重跑，需先完成 `npm.cmd run build`。完整入口將目前 Python 傳給 fixture；單獨執行預設使用根目錄 .venv，也可指定 `ATELIER_TEST_PYTHON`。

請在真實訓練或 F02 量測 worker 結束並釋放租約後執行完整回歸；部分既有 API fixture 沿用專案根目錄，運算佔用會正確拒絕這些本機生成 mock。GPU 技術驗收與 CPU／瀏覽器全套分開執行，不以互斥中的失敗視為功能回歸。

## 隔離與覆蓋

`scripts/browser_fixture.py` 每次建立新的系統臨時 DATA，只接受測試啟動選項（埠、隔離樣本數或空資料），不接受既有資料或引擎位置。真實 FastAPI、SQLite、圖片與下載在該資料運作；上游 HTTP 使用 MockTransport，網址固定為不可解析的 `.invalid` 網域，沒有真實推論。測試端點只存在 fixture。

單次服務預設監聽本機 18765；可用 `ATELIER_TEST_PORT` 指定另一隔離埠，分批入口從此埠依序遞增。`reuseExistingServer: false` 避免誤用既有平台，埠被占用即失敗。不要同時啟動兩套相同輸出目錄的測試；異常強制終止時可能留下系統臨時資料。

瀏覽器案例覆蓋各工作台的 dirty、KeepAlive、重新整理／關頁警示與取消；草稿保存中及完成後狀態；遺失 HTTP 回覆後原 UUID／完整 body／端點恢復且引擎僅收到一次提交；作品 409 保留筆記；實際 workflow 檔案下載及最大 64 位 seed 原文字；Enter 開啟／Escape 關閉預覽與焦點還原；390px 導覽、輸入及預覽。另驗證跨頁比較、模型／收藏／封存組合、較早任務、素材選取保留、Q08 網址／首次使用，以及 Q09 診斷篩選與逐字下載。Node 邏輯檢查另涵蓋六種新舊提交流程。

重試次數為 0；失敗保存 screenshot、video、trace 與 HTML 報告至忽略的 `runtime/quality/`。完整入口在 frontend 以 `npx.cmd playwright show-report ../runtime/quality/browser-report/group-1` 等各批目錄查閱；單獨 `npm run test:browser` 的預設仍為 `browser-report`，trace 可用 `npx.cmd playwright show-trace <trace.zip>`。CI 在 push／PR 執行相同入口，保留證據 14 天。設定依 [Playwright webServer](https://playwright.dev/docs/test-webserver) 與 [CI 官方指南](https://playwright.dev/docs/ci-intro)。

<a id="quality-evidence"></a>

## 專項重跑與歷史證據

以下從 `frontend` 執行，各命令只覆蓋指定領域；目前案例數依測試清單計算，不沿用歷史累積數。

| 指令 | 範圍／原始驗收 |
| --- | --- |
| `npm.cmd run test:browser -- mask-editor.spec.ts` | 畫布筆刷、PNG 像素、素材重讀、捕獲／取消／第二指模擬；[V01](validation/mask-editor-20261023.md)，模擬不等於實機觸控 |
| `npm.cmd run test:browser -- inpaint-recovery.spec.ts` | v1／v2、遺失回應、異常 JSON、未知版本、原 pending／端點／雜湊且不重送；[V02](validation/inpaint-recovery-20261023.md) |
| `npm.cmd run test:browser -- artwork-library.spec.ts` | 修訂衝突、未保存／保存中、503 不重送、原圖／精確參數、鍵盤捲動、跨頁選取；[V03](validation/artwork-library-20261023.md) |
| `npm.cmd run test:browser -- comparison-validation.spec.ts` | 歷史品質條件、有序 LoRA 比較軸、固定案例與量測來源、零／未知；[V04](validation/comparison-measurements-20261023.md) |
| `npm.cmd run test:browser -- settings-transfer.spec.ts` | 真正下載／檔案選擇／貼上與取消、原 bytes／大整數、不跨流程與慢速／過大／無效 UTF-8 保護；[V05](validation/settings-transfer-20261023.md) |
| `npm.cmd run test:browser -- ui-accessibility.spec.ts` | 逐頁標題、可讀名稱、Tab／Enter、焦點、展開／錯誤／空態與整頁溢出；[V06](validation/ui-accessibility-20261023.md) |

V02 fixture 的 `/qa/engine-audit` 最多保留 1,000 筆方法／路徑與輸入雜湊；V03 `/qa/artwork-set` 只建立臨時合成作品。V04 `scripts/comparison_fixture.py` 僅用於隔離平台，完成後還原登記並移除本組紀錄；歷史 GPU 原圖與合成 fixture 的證據分開。以上都不提供正式平台測試端點，不將合成圖當成實機 GPU 品質。

無障礙檢查保存 axe 的 violations 與 incomplete，漸層文字另核對主題 RGB 端點對比；自動結果不是完整 WCAG、讀屏或觸控認證。全站瀏覽器預算八分鐘、單案 45 秒、單 worker 及零重試；以實際設定與各專項驗收為準。

2026-10-22 的乾淨 lock／Chromium 安裝、runner 各階段故障立即停止及臨時失敗探針的 screenshot／video／trace 已驗證；當時的後端／瀏覽器數字與各次新增案例記在 [CHANGELOG](../CHANGELOG.md) 及上述驗收，不視為目前總數。Windows 8.3 TEMP 與 CI 路徑問題的實際別名重現見[獨立診斷](validation/windows-ci.md#windows-temp-alias-20261022)，產品路徑防護未放寬。

歷史相容性觀察：Starlette 1.6.0 TestClient 的 httpx 0.28.1 fallback 曾印出棄用提示；Windows 故障注入／關閉 SSE 可能印出 ConnectionResetError。保留這些提示，仍以斷言與退出碼判定；目前依賴以 lock 為準，不隱藏其他錯誤、不把引擎 HTTP 傳輸任意更換。當時 Vite／source-map-js 修補後的零項 npm audit 只屬當次結果，不是完整安全稽核或目前掃描結論。GPU、實機觸控、行動瀏覽器、對比／讀屏與全站視覺各自驗收；清單成本另見[分頁量測](list-pagination.md)。

## 同組隔離資料連續驗收

模型五分類／兩版型、訓練四階段、五種創作目的／Checkpoint／FLUX 的桌面三尺寸另由 `frontend/tests/desktop-acceptance-matrix.spec.ts` 驗證。此檔沿用一般隔離 fixture，會由既有分批入口自動收集，也可在 `frontend` 執行 `npx.cmd playwright test tests/desktop-acceptance-matrix.spec.ts`。視覺基準直接讀原 `preview.html`，不產生另一份基準檔；支援界線、機器證據與必要差異見 [桌面驗收矩陣](ui-redesign/ACCEPTANCE.md#desktop-matrix)。

從 `frontend` 執行以下獨立設定；每次建立新的 `--empty` 臨時資料，不沿用一般套件的預設樣本。

```powershell
npx.cmd playwright test --config playwright.journey.config.ts
```

此設定只執行 `isolated-journey.spec.ts`，使用正式建置的前端、真實 API／SQLite 與合成引擎，從空庫沿一張來源圖串接生成、作品匯入、詳情、比較、下載、封存還原、離線與未保存保護。此檔位於獨立的 `frontend/journey-tests/`，一般 Playwright 與分批入口只收集 `frontend/tests/`，避免在已有其他測試資料的批次假裝驗證空庫；這個獨立命令需另外執行，不含在既有 `check_quality.py` 成功宣告內。無自動重試，輸出與 HTML 報告分別位於 `runtime/quality/journey-results`、`journey-report`。詳細範圍、證據與未完成能力見 [逐流程驗收](ui-redesign/ACCEPTANCE.md#isolated-journey)。
