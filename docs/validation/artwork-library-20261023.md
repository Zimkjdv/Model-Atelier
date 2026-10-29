# V03 · 作品整理、並排比較與人工評分窄視窗驗收

日期：2026-10-23。對應 [ROADMAP V03](../../CHANGELOG.md#v03)，實際操作作品庫與作品預覽，不以比較報告頁的驗收代替。

## 環境與資料

Windows、Python 3.12、Node.js 24、鎖定的 Playwright 1.64.1 Chromium。五個案例固定 viewport 為 **390 × 844**，並在頁面讀取 `innerWidth` 斷言為 390。第二分頁使用同一 browser context 的相同 viewport；兩頁各自持有作品修訂及未保存表單。

`scripts/browser_fixture.py` 在新的臨時 DATA 建立五件隔離作品，使用實際 jobs／gallery 寫入、FastAPI、SQLite 及 PNG／縮圖讀取。兩個模型名、不同尺寸與參數、相反 LoRA 順序及 model／CLIP 強度均為合成驗收資料；兩張原圖尺寸為 128 × 64、64 × 128，seed 為相鄰的 `18446744073709551615`、`18446744073709551614`。不是 GPU 出圖或相容性證據。

`POST /qa/artwork-set` 只存在測試 wrapper，每次建立獨立組名；正式 API 沒有此路由。上游固定 MockTransport／`.invalid` 位址，每案核對生成呼叫數不變；沒有新推論、正式 DATA 寫入、依賴或資料格式變更。

## 本次修正與失敗證據

1. 清單由後端篩選，沒有符合結果時 `items.length` 必定為零，原 UI 因此誤顯示先生成／匯入作品。改以目前搜尋、模型、收藏及狀態條件決定空清單說明。
2. 比較捲動區補上可聚焦的具名 region、操作說明與焦點框，能使用左右方向鍵。原圖仍使用完整 image API 與 `object-fit: contain`，沒有縮圖替代或裁切。
3. 清單讀取期間 `organize()` 原本直接返回，但預覽的收藏、封存、保存筆記／評分按鈕未同步停用，快速操作會無回應。按鈕改與 busy 條件一致，預覽內顯示等待提示；測試攔住篩選回覆，確認兩種保存皆停用，釋放後再實際保存。

修正前兩項瀏覽器斷言失敗保存在 `runtime/v03-before.log`、`runtime/v03-before-browser/`；雙分頁快速保存未發出 PATCH 的 trace 在 `runtime/v03-read-race-browser/`。測試開發另修正原生 select 的定位及 null 選項標籤，沒有把測試定位問題當成產品缺陷。

依 [維護規則](../quality-checks.md#static-checks)，兩個 Vue 模組先獨立格式提交 `940dab1`，核對 script、編譯模板及 CSS 語意相同，建置與格式檢查通過；功能提交將清空比較的兩個操作移至具名函式，並以實際清空選擇回歸確認。兩個模組與新瀏覽器測試加入明確品質 scope，避免實質修改後漏檢。

## 五項操作案例

| 案例 | 實際操作及斷言 | 附件／截圖 |
| --- | --- | --- |
| 作品整理 | 搜尋、模型與收藏組合；收藏及筆記 PATCH；封存後重新整理、切已封存還原；重載後筆記仍在；整頁沒有水平溢出 | `empty-filter.png`、`organization.png`、`organization.json`、`original.png`、`workflow.json` |
| 未保存保護 | 同時修改筆記／評分；取消關閉、Escape、載入設定、重新整理、關頁及返回，內容保留；確認關閉／返回才放棄，伺服器 revision 仍為 0 | `unsaved.png`、`unsaved.json` |
| 原圖與差異 | 核對兩張原圖 URL、naturalWidth／Height、PNG SHA256；完整精確 seed、Steps／尺寸差異及相同 Sampler；LoRA 順序／強度；Tab 取得焦點、方向鍵及水平滾輪捲動；四件上限、移除、清空與搜尋後保留選擇 | `compared-0.png`、`compared-1.png`、`comparison-parameters.png`、`comparison-scrolled.png`、`comparison.json` |
| 雙分頁衝突／保存 | B 先保存筆記與評分；A 的舊修訂兩者皆 409，保留兩份草稿；取消重讀保留，確認才載入 B 資料；A 保存評分不覆蓋本地筆記，之後以新 revision 保存筆記；保存中不可關閉或重複保存，取消重載保留；比較欄與重載後分數更新 | `rating-conflict.png`、`saved-ratings.png`、`rating-revisions.json` |
| 保存失敗 | 注入 503；筆記／四項分數（含 null）保留；時鐘前進 16 秒仍僅一次請求；取消重載後手動保存評分及筆記成功 | `save-failure.png`、`failed-save.json` |

整理前後的原圖 bytes、SHA256、完整 workflow bytes 與參數相同；評分只更新管理資料。四項人工分數保留 null 的原意，沒有自動填零、平均或影像品質判定。上述流程未觸發生成。

## 重跑與結果

```powershell
# 從專案根目錄執行完整品質入口
.\.venv\Scripts\python.exe scripts/check_quality.py

# 或先建置後單獨執行 V03
Set-Location frontend
npm.cmd run build
npm.cmd run test:browser -- artwork-library.spec.ts
```

五個案例位於 `frontend/tests/artwork-library.spec.ts`，每案最多 45 秒、單 worker、零重試。完整品質入口退出碼 0：明確 scope 格式／靜態、574 項後端回歸（1 項既有 Windows symlink 權限跳過）、Vue 型別／建置、四組 Node 契約與 **39 項瀏覽器案例**通過。全量記錄為 `runtime/v03-quality.log`；成功及失敗證據保存於忽略的 `runtime/quality/browser-results/` 與 HTML 報告。JSON／PNG 附件可在報告開啟，CI 依品質工作流程保存 artifact。

檢視整理、比較、衝突與評分截圖後，調整 `saved-ratings.png` 的捲動位置以完整呈現四項分數；雙分頁案例另以 `--grep "two tabs:" --reporter=list --output=../runtime/v03-final-browser` 通過重驗，記錄為 `runtime/v03-final-browser.log`，保留原全量報告。

驗收範圍限 Chromium 的實際窄 viewport、鍵盤、滑鼠及兩分頁操作。不是實體手機／觸控或完整讀屏驗收；V01 實機觸控及 V06 全站 UI 仍各自待驗收。未改變 2026-10-05 的歷史 GPU 品質結論。
