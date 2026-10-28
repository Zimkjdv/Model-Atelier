# 可重跑品質檢查

從根目錄執行完整檢查；任何階段失敗立即停止並回傳非零：

```powershell
.\.venv\Scripts\python.exe scripts/check_quality.py
```

依序執行範圍內格式／靜態檢查、後端 unittest、Vue 型別與正式建置、`npm test` 的前端契約檢查（API／生命週期、實驗、遮罩、控制與欄位預檢）、Playwright Chromium。格式與高風險狀態維護見 [維護規則](maintenance.md)。`--skip-browser` 會明列跳過，不表示完整品質通過。

2026-10-25 起，完整入口依檔名排序，每六份瀏覽器 spec 為一批，各自啟動新的 Playwright／Chromium 與臨時平台，使用不同埠及 `runtime/quality/browser-results/group-N`、`browser-report/group-N`。截至 2026-10-27，共 25 份 spec、五批（6＋6＋6＋6＋1）；實際批數由 `scripts/check_quality.py` 依檔案清單計算，新檔會自動納入一次。任一批失敗立即停止，單 worker／單案限制及零重試保留。此調整針對 Windows CI 的 Chromium `net::ERR_NO_BUFFER_SPACE` 與單次整套八分鐘截止；降低單程序累積負荷，不宣稱已證明某個產品記憶體洩漏。

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

`scripts/browser_fixture.py` 每次建立新的系統臨時 DATA，只接受埠參數，不接受既有資料或引擎位置。真實 FastAPI、SQLite、圖片與下載在該資料運作；上游 HTTP 使用 MockTransport，網址固定為不可解析的 `.invalid` 網域，沒有真實推論。測試端點只存在 fixture。

單次服務預設監聽本機 18765；可用 `ATELIER_TEST_PORT` 指定另一隔離埠，分批入口從此埠依序遞增。`reuseExistingServer: false` 避免誤用既有平台，埠被占用即失敗。不要同時啟動兩套相同輸出目錄的測試；異常強制終止時可能留下系統臨時資料。

瀏覽器案例覆蓋四工作台的 dirty、KeepAlive、重新整理／關頁警示與取消；草稿保存中及完成後狀態；遺失 HTTP 回覆後原 UUID／完整 body／端點恢復且引擎僅收到一次提交；作品 409 保留筆記；實際 workflow 檔案下載及最大 64 位 seed 原文字；Enter 開啟／Escape 關閉預覽與焦點還原；390px 導覽、輸入及預覽。另驗證跨頁比較、模型／收藏／封存組合、較早任務、素材選取保留、Q08 網址／首次使用，以及 Q09 診斷篩選與逐字下載。Node 邏輯檢查另涵蓋六種新舊提交流程。

重試次數為 0；失敗保存 screenshot、video、trace 與 HTML 報告至忽略的 `runtime/quality/`。完整入口在 frontend 以 `npx.cmd playwright show-report ../runtime/quality/browser-report/group-1` 等各批目錄查閱；單獨 `npm run test:browser` 的預設仍為 `browser-report`，trace 可用 `npx.cmd playwright show-trace <trace.zip>`。CI 在 push／PR 執行相同入口，保留證據 14 天。設定依 [Playwright webServer](https://playwright.dev/docs/test-webserver) 與 [CI 官方指南](https://playwright.dev/docs/ci-intro)。

V01 新增 6 項遮罩瀏覽器回歸，當時總計 25 項：1440px／390px 的實際畫布操作與保存 PNG 像素核對、取消選取／素材重讀／KeepAlive、無效 PNG／保存失敗、捕獲／縮放／停用，以及 CDP 主觸點／第二指／取消。兩種寬度另保存全頁與遮罩截圖、像素量測附件至報告。以 `npm.cmd run test:browser -- mask-editor.spec.ts` 單獨執行；實機觸控仍未通過，詳見 [V01 驗收](validation/mask-editor-20261023.md)。

V02 再新增 9 項，當時瀏覽器回歸共 34 項。以 `npm.cmd run test:browser -- inpaint-recovery.spec.ts` 重跑 v1／v2 × 1440px／390px × 遺失回應／異常 JSON 的 8 案例，以及未知版本保護。測試保存原 pending、平台請求／回覆、固定輸入與引擎呼叫雜湊及截圖；fixture 的 `/qa/engine-audit` 最多保留 1,000 筆方法／路徑與輸入雜湊，只存在臨時測試服務。Node 契約對六種生成端點驗證錯誤／缺失成功 id 與錯誤 detail.job_id 不會誤清除 pending。見 [V02 證據](validation/inpaint-recovery-20261023.md)。

V03 新增 5 項，當時瀏覽器回歸共 **39 項**。`npm.cmd run test:browser -- artwork-library.spec.ts` 實際操作 390px 作品整理、兩分頁筆記／評分修訂衝突、未保存及保存中保護、503 不重送、原圖與精確參數比較、橫向鍵盤捲動及四件選取上限。fixture 的 `/qa/artwork-set` 只建立臨時合成作品，不呼叫生成；每案檢查生成數不變，並附原圖／workflow bytes、管理修訂 JSON 與畫面。見 [V03 驗收](validation/artwork-library-20261023.md)。

V04 新增 8 項，當時瀏覽器回歸共 **47 項**。`npm.cmd run test:browser -- comparison-validation.spec.ts` 在 1440px／390px 核對正反 8 步歷史品質條件、指定 LoRA model／CLIP 軸及錯誤、兩模型固定四案例逐組載入，以及任務／作品量測原來源、零與未知值。`scripts/comparison_fixture.py` 僅供臨時 fixture；完成後還原登記及移除本組紀錄，避免影響其他測試。另以本機歷史唯讀副本核對 11 件原 GPU 作品、四案例跨模型並排及設定還原，不以合成圖取代歷史結果。見 [V04 驗收](validation/comparison-measurements-20261023.md)。

V05 新增 12 項，當時瀏覽器回歸共 **59 項**。`npm.cmd run test:browser -- settings-transfer.spec.ts` 在 1440px／390px 實際下載三種一般創作設定及作品來源設定，保存檔案並比對 API bytes／檔名；真正檔案選擇器、剪貼簿貼上、取消及明確另存皆不生成。另核對原 workflow 大整數字串、未核實來源、晚到預覽、保存中停用、無效／跨流程文件，以及過大、無效 UTF-8 與慢速檔案保護。測試作品使用正式 workflow builder，不使用簡略圖冒充可還原設定。見 [V05 驗收](validation/settings-transfer-20261023.md)。

V06 新增 21 項，當時瀏覽器回歸共 **80 項**。`npm.cmd run test:browser -- ui-accessibility.spec.ts` 逐頁檢查九個入口在 1440px／390px 的標題、可讀名稱、Tab／Enter、焦點、展開內容、文字狀態與整頁溢出；另覆蓋硬體卡片、離線／舊資料、四類模型編輯、作品收藏及對話框、素材讀取／空白／錯誤、診斷 JSON、圖生圖與遮罩。精確鎖定 axe Playwright 4.14.0，保存 violations 與 incomplete；漸層文字另核對目前主題的 RGB 端點對比，不把自動結果視為全 WCAG 認證。新增量測與截圖增加執行時間，整套瀏覽器預算由五分鐘改為八分鐘，單案 45 秒、單 worker 與零重試維持。頁面矩陣、截圖／JSON 及限制見 [V06 驗收](validation/ui-accessibility-20261023.md)。

## 依賴與驗收範圍（2026-10-22）

Q06 建立時，全新隔離 venv 依 requirements.lock.txt 安裝、`npm ci` 與 Chromium 安裝通過。後端 550 項，549 通過、1 項 Windows symlink 建立權限跳過；測試列出理由。runner 測試逐個注入四階段失敗，均停止後續步驟並保留非零碼；另以臨時瀏覽器失敗探針確認 exit 1、畫面／錄影／trace／錯誤上下文均保存，探針未納入正式測試。

Starlette 1.6.0 的 TestClient 優先使用 httpx2，現行 lock 的 httpx 0.28.1 fallback 會發出棄用提示；保留提示，以乾淨安裝及全量回歸確認當前相容。引擎 MockTransport／HTTP 仍直接使用 httpx，未混入更換傳輸依賴。故障注入／關閉 SSE 在 Windows 可能印出 ConnectionResetError，不隱藏其他錯誤；斷言與退出碼仍決定結果。

安裝時發現 Vite 7.3.6 與 source-map-js 1.2.1 的既有 npm 警告，更新相容修補版至 7.3.7／1.2.2，當次 `npm audit` 回報 0 項已知問題；這不代表完整安全稽核。真正 GPU、觸控、行動瀏覽器、對比／讀屏及全站視覺仍依 V01–V06 各自驗收，這些案例不代替上述項目；Q04 效能指標及最新回歸見 [分頁說明](list-pagination.md)。

首次遠端 Q06 CI 的 Windows 8.3 TEMP 問題已以實際別名重現並獨立修正，產品路徑防護不變；見 [診斷與回歸](validation/quality-windows-paths-20261022.md)。
