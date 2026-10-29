# V06 · 全站視覺規範與無障礙補驗

日期：2026-10-23。對應 [ROADMAP V06](../../CHANGELOG.md#v06)。本次覆蓋六個主頁及四種工作流程的九個網址，逐頁保存 **1440 × 900／390 × 900** 的結果；不是沿用先前工作台與導覽的局部驗收。

## 方法與範圍

Windows、Python 3.12、Node.js 24、Playwright 1.64.1 Chromium。新增 **21 項瀏覽器回歸**：九個入口逐一測兩種寬度，另有六組狀態各測兩種寬度。測試使用新的臨時 DATA、真實平台 API／SQLite，以及固定 MockTransport；硬體狀態、ControlNet／FLUX 元件清單的部分回覆只替換目前測試分頁，並非真實硬體驗收。模型／LoRA 的隔離登記使用既有 fixture，完成後還原。

引入精確鎖定的 `@axe-core/playwright` **4.14.0**，檢查 WCAG 2 A／AA、2.1 AA 相關規則及 best practice。每個狀態保存 violations、**incomplete 待判讀項目**、通過規則、工具版本及 viewport，不把零 violations 解讀為完整 WCAG 認證。

鍵盤驗證包含原生 Tab 順序與自動捲入可見區、跳至主要內容、各頁主要標題與目前導覽、Enter 展開 details、編輯與收藏、ArrowRight 調整遮罩筆刷／捲動表格，以及作品對話框的反向 Tab、Escape 與關閉後焦點還原。檢查 2px 實線焦點框；`main` 接收切頁／跳轉焦點但不顯示控制元件外框。減少動態效果偏好與整頁橫向溢出也納入斷言。

## 逐頁結果矩陣

下列各列均在桌面與窄視窗通過標籤／語意、鍵盤與焦點、文字對比及非顏色提示檢查；截圖逐頁檢視布局、換行、卡片與展開內容。局部橫向比較／表格保留捲動區，不讓整頁橫向溢出。

| 入口 | 1440px／390px 的內容與狀態 | 保留的限制 |
| --- | --- | --- |
| `#/system` 系統資訊 | 首用指引、RAM／磁碟、合成 GPU 卡、引擎與本機裝置、CUDA 不可用、未知／離線、更新失敗保留舊資料及文字警告、儲存與詳細資訊 | 裝置與版本為 fixture 或查詢快照，不推論真實任務裝置／峰值 |
| `#/settings` 設定 | 連線表單與保存失敗、原輸入保留、本機模型目錄及磁碟明細、診斷 JSON 預覽與鍵盤焦點 | 錯誤訊息可讀且以 live region 呈現；沒有更換正式引擎或模型目錄 |
| `#/models` 模型庫 | checkpoint、ControlNet、LoRA、FLUX 四種資料編輯表單、驗證紀錄、空清單、來源與授權、固定 FLUX 計畫及鍵盤橫向捲動 | 清單與版本是登記資料；未下載權重或驗證 GPU 相容性 |
| `#/gallery` 作品庫 | 搜尋／整理、收藏真假 ARIA 狀態與文字、單件加入比較、作品預覽、筆記與評分、展開來源／量測、對話框焦點約束與還原 | 多作品差異、409、評分保存沿用 V03／V04 回歸，沒有新增品質判斷 |
| `#/assets` 參考素材 | 上傳標籤與說明、流程需求、分頁群組、編輯表單、無結果、讀取中與 503 警告 | 未改正式素材或自動套用參考能力 |
| `#/studio/checkpoint` | 草稿、設定交換與無效 JSON、固定比較案例、進階參數、模型工作流程、單張圖生圖輸入與縮放、生成預檢、畫布比例及草稿清單 | 未生成；無效匯入不套用。比較方案結果另有 V04 回歸 |
| `#/studio/flux` | 四角色元件、提示詞、精度／裝置展開欄位、草稿與交換、未齊元件的文字預檢 | FLUX GPU 尚未驗收，不以可編輯表單代表可執行 |
| `#/studio/inpaint` | 原圖／遮罩選擇、已載入畫布、筆刷範圍鍵盤調整與反相、提示詞、參數、未保存及預檢文字 | 自由手繪為路徑輸入；可鍵盤選擇已保存遮罩或載入 PNG。實機觸控仍屬 V01-02 |
| `#/studio/control` | 原素材圖片與替代文字、ControlNet／閾值／縮放標籤、CPU 預覽說明、LoRA、生成缺少條件的文字提示 | 不觸發 CPU 預覽或 GPU 生成；專用預覽的像素證據見既有驗收 |

## 對比、狀態與修正

一般文字依 [W3C 1.4.3](https://www.w3.org/WAI/WCAG22/Understanding/contrast-minimum.html) 的 4.5:1、大字 3:1 檢查。axe 對漸層背景會留下 incomplete；測試另讀取目前主題使用的不透明 RGB 漸層端點，以相對亮度計算最低對比，並保存每個端點的比值。此補查只適用本專案目前的深色 RGB 漸層，不宣稱是任意圖片、透明疊層或多背景的通用判定器。

| 問題 | 修正與驗證 |
| --- | --- |
| 側欄小字對比不足 | WORKSPACE 原約 4.37:1、版本字原約 4.16:1，改用共用 `--text-muted` |
| 漸層上的文字漏查 | 畫布說明原在較亮端點約 4.17:1；畫布說明與 GPU 卡片標記改用共用文字色，漸層另算端點，不只採 axe 自動結論 |
| 收藏宣告無效 | 舊清單摘要可能給數字 0／1，現在兩處收藏 `aria-pressed` 都轉成布林值，驗證 `false → true → false` 與可讀文字；API 與保存格式不變 |
| 工作台標題跳級 | Checkpoint 編輯表單補上二級「創作設定」，模型工作流程與預設保持三級 |
| 窄導覽／分頁語意 | 品牌連結有完整可讀名稱；素材／作品分頁以 `role=group` 配合名稱，不在 generic div 單放 aria-label。作品分頁是檢視 incomplete 後補正，並非只處理 violations |
| 可捲區的焦點 | FLUX 元件表格與診斷 JSON 加入具名 region 與 tabindex；共用 focus-visible 涵蓋 tabindex，診斷 JSON 也得到清楚焦點框。JSON 原先只在 pre 放名稱，現在有對應區域語意 |

連線、清單內外、收藏、停用、缺少必要條件、未保存、讀取與錯誤均有文字／原生控制狀態，不只依賴綠色、黃底或圓點。關於可自由手繪的路徑輸入與鍵盤例外，範圍依 [W3C 2.1.1](https://www.w3.org/WAI/WCAG22/Understanding/keyboard.html)；此處沒有以鍵盤模擬自由筆畫來宣稱觸控通過。

依 [維護規則](../quality-checks.md#static-checks)，CreationStudio 與共用 theme 先以 `6b17b17` 獨立格式提交，核對 TypeScript、編譯模板及 CSS 值／順序相同，再提交功能修正；兩模組與新測試納入品質 scope。格式工具會刪除 Vue 事件的多敘述分號，因此尺寸預設按鈕保留精確原文；另一處明確保留按鈕間空白，避免純格式提交混入模板差異。

## 重跑與證據

```powershell
# 根目錄完整品質入口
.\.venv\Scripts\python.exe scripts/check_quality.py

# 或只跑 V06（先建置）
Set-Location frontend
npm.cmd ci
npm.cmd run build
npm.cmd run test:browser -- ui-accessibility.spec.ts
```

逐頁與狀態測試在 `frontend/tests/ui-accessibility.spec.ts`。單 worker、每案 45 秒、零重試；整套瀏覽器由 59 項增加至 **80 項**，總預算由五分鐘調整為八分鐘，保持有界限且不靠重試掩蓋失敗。單獨 V06 的 21 項約 1.4 分鐘；完整品質結果記錄於 `runtime/v06-quality.log`。

完整入口退出碼 0：格式／靜態、574 項後端回歸（1 項既有 Windows symlink 權限跳過）、Vue 型別／正式建置、四組前端契約及 **80 項瀏覽器**通過，瀏覽器約 4.2 分鐘。其後將 HTML 的稽核 JSON 也明確寫成檔案，檢視 incomplete 時補正作品分頁群組與診斷 pre 區域語意，並將非對比 incomplete 納入失敗條件；再跑格式／靜態、建置／四組契約及 V06 21 項加作品庫 5 項，**26 項全數通過**。使用獨立輸出與 list reporter 保留原完整報告；最後的逐頁稽核、截圖及 log 在 `runtime/v06-final-browser/`、`runtime/v06-final-browser.log`。

最終保存 **50 份狀態稽核 JSON**，violations 為零、沒有未處理的 ARIA／語意 incomplete；剩餘均為對比待判讀。所補算漸層文字端點的最低對比約 **4.88:1**，各狀態的計算值保存在 JSON；橫向裁切與裝飾符號另外以操作及視覺判讀。這些結果仍受下列環境與工具限制約束。

附件位於忽略的 `runtime/quality/browser-results/ui-accessibility-*`，HTML 報告在 `runtime/quality/browser-report/`。九個入口的 `expanded-1440.png`／`expanded-390.png` 與同名 JSON 可逐頁對照；其他附件依狀態命名：`hardware-devices`、`hardware-stale-offline`、`catalog-editors`、`flux-table-keyboard`、`artwork-comparison`、`artwork-dialog`／`artwork-dialog-top`、`asset-editor`／`empty`／`loading`／`error`、`settings-preview`／`error`、`checkpoint-image-input`／`import-error`、`inpaint-mask`、`control-source`。本機另有 `runtime/v06-visual-review/` 的分段截圖及 audit 摘要；CI 保存同一測試的品質附件 14 天，原始圖片不加入 Git。

## 未宣稱的範圍

本次是明列頁面與狀態的 Chromium 視覺／鍵盤／自動語意及對比補驗；沒有實體讀屏軟體的朗讀結果、Firefox／Safari、實體行動瀏覽器、作業系統高對比模式或完整 WCAG 2.2 認證。axe incomplete 中的裝飾導覽符號、漸層與橫向表格裁切需配合端點計算、實際鍵盤捲動與截圖判讀，沒有隱藏、排除整頁或宣稱全部自動通過。新增頁面、控制或主題時需擴充矩陣。

V06 的逐頁補驗與證據歸檔完成不會關閉 V01-02：使用者已確認目前沒有實體觸控裝置，實機觸控仍保留待驗收。未新增 GPU 推論，也未修改正式資料、模型權重或歷史作品。

2026-10-24 系統資訊新增目錄卡片、磁碟使用率與資料夾開啟按鈕後，已補充 [儲存區狀態矩陣](storage-overview-20261024.md)，並重跑本頁於 1440px／390px 的整頁掃描。歷史九入口的驗收範圍與實機觸控限制維持原紀錄。
