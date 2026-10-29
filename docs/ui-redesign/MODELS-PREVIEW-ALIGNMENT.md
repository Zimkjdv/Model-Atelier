# 模型庫與原預覽對齊

日期：2026-10-29。以原有 `preview.html` 為基準，修改正式平台的五個模型分類。預覽保持不變；清單仍為進入模型庫的預設，卡片為三欄。本輪只驗收桌面，沒有新增手機版範圍。

## 比對與調整

| 範圍 | 原本差異 | 本次調整 |
| --- | --- | --- |
| 分類與版型列 | 分類選中時字重偏粗，「顯示」文字較大，模型內容起點相差 2px | 對齊預覽的 15px 分類文字、38px 按鈕、400 字重、13px 顯示標籤及工具列下方 20px 間距。原 SVG 側欄圖示與大小沿用，不另換圖示。 |
| Checkpoint | 資料展開入口在整列下方，狀態與按鈕只對齊上半列；尺寸說明與預覽不同 | 名稱、架構、尺寸、來源資料集中在左側；狀態及操作整列置中。沿用實際架構與尺寸預設，補回倍數與示例說明；未知架構不提供假預設。 |
| LoRA／結構控制 | 狀態浮在右上方，版本直接占一行，整列與卡片都不符合預覽的內容順序 | 改為左側名稱／架構／展開資料，中間狀態、右側實際編輯操作。版本、授權、hash、來源及驗證仍可展開。 |
| 元件 | 名稱與狀態擠在同一行，編輯按鈕另列在下方；有一行說明先於清單 | 採相同三區排列，補充說明放清單之後；原 adapter／影像編碼器身分及登記編輯器保留。 |
| FLUX 元件 | 主模型、文字編碼器、VAE 分成三組清單，沒有獨立狀態標籤；創作入口先於清單 | 合為一份清單／三欄卡片，保留每筆的實際分類與編輯送出身分；狀態與操作獨立。版本、大小、hash、來源及授權可展開；創作入口移到清單之後。 |
| 清單／卡片 | 各分類內距、標題、狀態及操作位置不一致 | 清單統一 20px 外框、14px 列內距、16px 間隔、15px 標題；卡片為 16px 標題、14px 內容間隔，操作靠下。來源展開文字為 13px。狀態色、按鈕底色及圓角與各自預覽對照。 |
| 無資料／搜尋無結果 | 空訊息下仍留一個空清單外框；FLUX 搜尋會在每組都顯示空訊息 | 移除空清單外框，統一預覽的虛線空狀態樣式。FLUX 改為整體判斷無資料／搜尋無結果，並提供清除搜尋；參考元件分開顯示載入中及無資料。讀取失敗不冒充空庫。 |

## 保留的正式版差異

- 預覽各分類的「套用到創作」多為示意按鈕。正式版 Checkpoint 維持既有模型交接；LoRA、ControlNet、元件的右側操作使用真實的編輯入口，不新增未實作的自動套用。既有獨立「前往 FLUX 創作」保留。
- 「可使用」表示最近清單有列出，並非權重、相容性或生成驗證通過。歷史項目仍標示「最近清單未列出」，Checkpoint 不可套用；引擎離線／同步失敗仍保留歷史說明。沒有把預覽的 Pose／Depth 示意能力視為已接入。
- 五分類的同步 API、引擎身分檢查、編輯期間禁止同步、Checkpoint 偏好與驗證、LoRA 架構比較與組合實測、來源／授權／SHA256／檔案大小均保留。切換版型不重建編輯器、不清除輸入。
- FLUX 文字編碼器清單可能含多種實際檔案，不以檔名猜測 CLIP-L／T5 角色或把未知架構改成 FLUX。送出時仍使用原後端分類。固定下載計畫、修訂、磁碟預算、來源條件與 CLI 安裝限制保留在原「FLUX.1 接入準備」區塊，因此下方內容比預覽多。
- 同步成功／失敗訊息、搜尋／來源管理及額外登記功能保留。同步完成訊息會正常占據空間；幾何比對在重新讀取已同步清單後執行，不隱藏訊息來通過測試。

## 畫面對照

下列均為 1440×900，正式畫面使用隔離測試目錄與模擬引擎的實際清單 API；不是正式使用者資料。檔名、筆數及未知欄位不同於原型，沒有複製示意模型到正式資料庫。

| 分類 | 原預覽清單 | 正式清單 | 原預覽卡片 | 正式卡片 |
| --- | --- | --- | --- | --- |
| Checkpoint | [原清單](models-reference-checkpoint-list.png) | [正式清單](models-platform-checkpoint-list.png) | [原卡片](models-reference-checkpoint-cards.png) | [正式卡片](models-platform-checkpoint-cards.png) |
| LoRA | [原清單](models-reference-lora-list.png) | [正式清單](models-platform-lora-list.png) | [原卡片](models-reference-lora-cards.png) | [正式卡片](models-platform-lora-cards.png) |
| 結構控制 | [原清單](models-reference-control-list.png) | [正式清單](models-platform-control-list.png) | [原卡片](models-reference-control-cards.png) | [正式卡片](models-platform-control-cards.png) |
| 元件 | [原清單](models-reference-reference-list.png) | [正式清單](models-platform-reference-list.png) | [原卡片](models-reference-reference-cards.png) | [正式卡片](models-platform-reference-cards.png) |
| FLUX 元件 | [原清單](models-reference-flux-list.png) | [正式清單](models-platform-flux-list.png) | [原卡片](models-reference-flux-cards.png) | [正式卡片](models-platform-flux-cards.png) |

## 實際驗證

- 正式建置、格式檢查、TypeScript 及 CSS 檢查通過。既有主 JS 超過 500 kB 的建置提醒仍存在。
- 五分類 × 清單／卡片 × 1280×800、1440×900、1920×1080，共 30 格通過。逐格比較內容起點與寬度、標題／展開文字的字級與顏色、狀態及操作的底色／邊框／圓角、卡片欄數；清單狀態及操作置中，沒有水平溢位。
- 同組隔離清單逐類同步並重新讀取，檢查名稱不遺失；各分類開啟原編輯器、輸入未保存版本，在兩種版型間切換仍保留，且同步停用，取消後恢復同步。
- 另三個瀏覽器案例通過：五分類的空資料／兩版型與原預覽空狀態樣式比對、支援搜尋分類的無結果與清除、歷史清單、離線說明、保存失敗保留 FLUX 編輯、切分類保留編輯，以及各分類的無障礙檢查；Checkpoint 交接保留提示詞、不改偏好、不自動提交；參考元件真實保存後重新讀取登記資料。合計六個不同測試案例，不把重跑次數計入。
- 沒有修改後端、正式 DATA、引擎安裝或模型權重，沒有實際生成。測試內的同步與資料保存只發生在臨時 DATA／模擬引擎；空資料及失敗案例使用瀏覽器局部回覆，驗證後實際隔離清單保持不變。20 張對照截圖擷取只執行 GET，未寫入 API 或提交生成。

重跑主要範圍：

```powershell
cd frontend
npm.cmd run build -- --configLoader runner
npx.cmd playwright test tests/desktop-acceptance-matrix.spec.ts tests/preview-alignment.spec.ts tests/ui-redesign.spec.ts --grep "model five-category|model categories retain|model and asset handoff|reference component metadata"
```

本機使用手動管理的 `scripts/browser_fixture.py --port 18772` 與 Git 忽略的 runner 設定執行，同一份前後端與測試程式。原預覽 SHA256 仍為 `f88076148aab2ff1471137f7b60a1be55c72c0d0f1219e52f981c462c9e76433`。三尺寸各分類的幾何、筆數及截圖清單見 [驗收證據](models-preview-evidence.json)。
