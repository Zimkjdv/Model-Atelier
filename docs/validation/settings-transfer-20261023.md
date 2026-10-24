# V05 · 創作設定下載與窄視窗驗收

日期：2026-10-23。對應 [ROADMAP V05](../../CHANGELOG.MD#v05)，使用一般創作設定 `kind: model-atelier-creation`／schema 1；比較方案或比較結果 JSON 不代替本項。

## 環境及範圍

Windows、Python 3.12、Node.js 24、Playwright 1.64.1 Chromium。六種案例各在 1440 × 900 與 **390 × 900** 執行，逐案斷言頁面 `innerWidth`，共十二項。使用 Q06 的新臨時 DATA、真實 API／SQLite、合成 PNG 與固定 MockTransport；每案核對生成呼叫數不變，沒有 GPU 推論或正式作品修改。

三種完整設定分別為 checkpoint 文生圖、單張圖生圖及 FLUX.1 [schnell]。設定含中文、多行及引號、seed `18446744073709551615`；checkpoint 含兩個啟用及一個中間停用 LoRA、零／負強度，圖生圖另保留原素材 ID／stretch／denoise 0.123，FLUX 保留四元件、FP8 選項及 CPU 編碼器設定。這些是交換格式的測試值，不是硬體／品質建議或 FLUX GPU 證據。

## V05-01 · 真正下載與原 bytes

| 入口 | 實際驗證 |
| --- | --- |
| 工作台「匯出目前創作設定」 | 監聽 Chromium 原生 download event，以 `saveAs` 保存到測試輸出；下載成功、完整 bytes 等於該次 POST export API 回應，JSON 全欄位等於原設定，來源快照為 null |
| 「下載上次匯出的設定」 | 修改目前未保存提示詞後，再實際下載原 Blob，bytes／檔名仍等於上次文件，沒有誤用目前表單重建 |
| 作品「匯出創作設定（含來源快照）」 | 直接下載 HTTP attachment，與同一唯讀 export API 的 bytes 相同；來源 id／版本及原 `workflow_json` 字串保留；與完整 workflow API 原文字逐 byte 比對，包含未經 JavaScript number 轉換的最大 64 位整數 |

目前設定下載檔名為 `model-atelier-checkpoint-settings.json` 或 `model-atelier-flux-settings.json`，作品為 `{artwork_id}-settings.json`。保存的下載檔經真正檔案選擇器重新選取，匯入請求 body 等於原檔 bytes，預覽保留精確 seed 及完整欄位。

作品文件匯入時，預覽明示來源由文件提供、未核實、不代表新任務版本或相容性；預覽／取消不改作品。fixture 的示範作品改用正式 `workflows.build` 建立完整七節點圖，取代早期僅供檢視的簡略圖，讓來源設定可完整還原；沒有修改產品 workflow 或使用者紀錄。

## V05-02 · 檔案、貼上、取消與套用保護

- 三種設定皆實際觸發 file chooser、選取剛下載的檔案，再用瀏覽器剪貼簿及 `Control+V` 貼上相同 JSON。兩條路徑的預覽 bundle 相同；預覽表格實際捲到 seed，核對前後兩欄的完整字串。
- 原表單有未保存內容時顯示取代提示；預覽與「取消匯入」均保留表單。只有明確按「套用為新草稿」才載入，仍須另按保存；保存使用新的 POST／新 id，原已保存草稿完整不變，未自動生成。
- 文件或表單改變使舊預覽失效。攔住 import 回覆、修改表單再釋放，晚到的成功不能重新開啟預覽或覆蓋修改；保存中的套用及檔案選取停用。
- 無效 JSON、版本 2、數字 seed 均回傳 422；有效 FLUX 文件在 checkpoint 工作台仍拒絕套用。原引擎不同／素材不存在時保留文件值並提示，不改全域引擎、不假裝已搬移圖片。
- 空選檔保留原預覽；過大或無效 UTF-8 新檔案清除候選文字與預覽，不能繼續驗證舊文件。延遲檔案讀取時停用交換操作；讀取期間表單變更後，晚到檔案也不再成為候選。

## 修正及失敗證據

原 `readFile()` 遇到過大新檔案，只清除預覽，輸入區仍留下舊文件；修正前 390px 測試在「候選應為空」斷言失敗，保留於 `runtime/v05-before.log`、`runtime/v05-before-browser/`。現在開始讀取新檔案即清空舊候選，使用 busy／ticket 保護，失敗後保持空白並清除讀取中提示，需重新選檔或貼上。

原 `File.text()` 會將無效 UTF-8 替換成字元，可能讓原本應拒絕的文件被改寫後接受。改為 `arrayBuffer()` 配合 fatal UTF-8 TextDecoder；測試把非法 byte 放在 JSON 提示詞字串內，確認直接拒絕而不是替換內容。有效檔案仍保留原文字，API schema／256 KiB 上限不變。

依 [維護規則](../maintenance.md)，先以 `36f4e99` 獨立格式提交設定交換元件，script、編譯模板及 CSS 正規化比對相同，格式與正式建置通過；再加入讀取修正與操作回歸。元件與新測試納入明確品質 scope，沒有全庫格式化或新增依賴。

## 重跑及附件

```powershell
# 根目錄完整檢查
.\.venv\Scripts\python.exe scripts/check_quality.py

# 或先建置，再只跑 V05
Set-Location frontend
npm.cmd run build
npm.cmd run test:browser -- settings-transfer.spec.ts
```

十二項案例位於 `frontend/tests/settings-transfer.spec.ts`，單 worker、每案 45 秒、零重試；單獨執行記錄為 `runtime/v05-browser.log`。下載檔與 SHA256／bytes／檔名回執、檔案及剪貼簿預覽、原草稿與另存結果，保存在忽略的 `runtime/quality/browser-results/` 與 HTML 報告。

完整品質入口退出碼 0：範圍內格式／靜態、574 項後端回歸（1 項既有 Windows symlink 權限跳過）、Vue 型別／正式建置、四組 Node 契約與 **59 項瀏覽器案例**通過，記錄為 `runtime/v05-quality.log`。檢視截圖後，另將錯誤提示捲入可見範圍並清除失敗後的讀取中提示，再跑格式／靜態、建置／四組契約及十二項 V05 回歸，結果保存於 `runtime/v05-final-browser.log`、`runtime/v05-final-browser/`；原全量報告保留。

主要附件為各模式 `*-settings.json`、`*-last-export.json`、`*-receipt.json`、`*-preview.png`、`*-transfer.png`，以及 `artwork-settings.json`、`source-receipt.json`、`apply-protection.png`、`too-large.json-error.png`、`invalid-utf8.json-error.png`、`file-read-error.png`。下載以磁碟檔案比對，不以畫面中的 JSON 或 HTTP 200 代替下載完成。

範圍限 Chromium 的桌面／窄 viewport 與已支援三種交換格式；不代表實體行動瀏覽器、觸控、全站無障礙或 inpaint／Canny 已支援一般設定交換。V01 實機觸控與 V06 仍各自待驗收。
