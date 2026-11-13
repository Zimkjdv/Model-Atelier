# Model Atelier — Roadmap

個人 AI 圖像創作與實驗工作台。更新日期：2026-11-14。

<a id="pc02提示詞編輯區整併2026-11-07-完成"></a>
<a id="pc01中文描述轉英文提示詞2026-10-31-完成實作與隔離驗收"></a>

這裡維護目前尚待實作、驗收及外部證據的工作。已完成條目的證據見 [CHANGELOG](../history/changelog.md#roadmap-completed-20261025)，原清單的去向見 [歷史索引](../history/changelog.md#unchecked-index)。規格、操作與各次驗收條件由原主題文件保存。

截至 2026-11-14，主線共有 **15 個未完成主項、17 個待驗收子項**，另有 **8 個優化候選（O01–O08）**。

## 目前進度與接續條件

| 範圍 | 目前進度 | 下一個可驗收動作 |
| --- | --- | --- |
| 作品庫窄版 | 390px 既有案例仍出現整頁橫向溢出 | 修正搜尋／篩選列後，重跑[窄版整理案例](#gallery-narrow-layout)與桌面回歸 |
| 簡易創作真人驗收 | 隔離瀏覽器已驗流程，真人觀察依使用者安排延後 | 有新手參與時觀察[第一次創作](#simple-first-use) |
| 模型來源 M01／M02 | 已完成公開資料補查與本機內容指紋；完整來源鏈仍缺 | 取得發布者可追溯的條款適用、上游 revision 或轉檔紀錄 |
| 作者畫風／角色品質 | 資料工具、技術試訓與產物回登已交付，作者圖仍待審查 | 先完成[候選審查](#author-dataset-review)，再安排試訓與固定比較 |
| 實機觸控 V01-02 | 桌面與 390px 瀏覽器模擬通過 | 有實體觸控設備後操作遮罩筆刷 |
| 官方 API A01–A07 | 尚未接入，依既定順序最後實作 | 先查 NovelAI 正式資料並確認 Mango 2 身分，才評估接入 |

各工作項獨立驗證、commit／push 後再接續下一項。技術維持 Vue／FastAPI／SQLite 與獨立 ComfyUI，保留原 UUID、端點、不可變快照、精確 seed 與未知結果的恢復規則。原始圖片、權重與 runtime 保存在 Git 外。驗收證據依配置與資料範圍記於 [docs/validation](../validation)，採用上游能力的依據見[借用決策](../research/upstream-reuse.md#reuse-assessment)。

| 範圍 | 未完成主項 | 待驗收子項 |
| --- | ---: | ---: |
| P0：硬體、相容性與量測 | 0 | 0 |
| P1／P6：介面、真人與實機觸控驗收 | 3 | 3 |
| P2／P4：模型來源 | 2 | 2 |
| 作者資料、試訓與品質驗收 | 3 | 4 |
| P8：官方 API（最後實作） | 7 | 8 |

<a id="e02"></a>
<a id="e03"></a>
<a id="e04"></a>

硬體 E02–E04 已歸檔至 [CHANGELOG](../history/changelog.md#e02)；此處僅保留舊錨點。

## P1／P6：尚未完成的介面驗收

<a id="ux01"></a>
<a id="ux02"></a>

UX01／UX02 已完成，見 [候選計數](../history/changelog.md#ux01)與[窄視窗審查](../history/changelog.md#ux02)。

<a id="v01"></a>

- [ ] **V01 · 遮罩筆刷與觸控的真實瀏覽器補驗**
  - 已完成部分：[V01-01 筆刷與 PNG 操作](../history/changelog.md#v01-01)，此處只追蹤 V01-02 實機觸控。
  - [ ] 驗收 V01-02：在桌面與 390px 視窗操作；使用實際觸控能力驗證指標互動，無觸控環境不能標記觸控通過。

  2026-10-23：1440px／390px Chromium 完成操作與保存 PNG 的逐像素雜湊核對；修正素材重讀／切頁清空筆畫、取消選取值未復原及非 PNG 載入問題。主指標、越界捕獲、取消、停用與第二指模擬回歸通過。使用者確認目前沒有實體觸控裝置；V01-02 的實機觸控與 V01 主項保留未完成。見 [V01 驗收紀錄](../validation/mask-editor-20261023.md)。

<a id="gallery-narrow-layout"></a>

- [ ] **作品庫 390px 搜尋／篩選列溢出**
  - [ ] 讓搜尋、篩選與版型控制在 390px 可換行，並通過既有作品整理案例的整頁寬度斷言、收藏／筆記／封存／還原流程及桌面回歸。
  - 2026-11-14 用 Edge Chromium 與隔離資料重跑，案例仍在 `document.documentElement.scrollWidth <= innerWidth + 1` 失敗。在 `frontend` 以 `npm.cmd run test:browser -- tests/artwork-library.spec.ts -g "390px organize"` 重跑。見[原驗收限制](../ui-redesign/ACCEPTANCE.md#rerun)及[測試程式](../../frontend/tests/artwork-library.spec.ts)。

<a id="simple-first-use"></a>

- [ ] **簡易創作 11.1 · 真人新手首次操作**（使用者延後）
  - [ ] 觀察已完成安裝的新手能否辨識簡易入口，選卡、生成、保存及修改再生成，盡量不展開技術參數。另記錄他能否理解缺模型／元件的說明，並在處理後回到原選卡及描述。原桌面規格也將 10 秒內辨識入口列為可用性觀察目標。
  - 四步操作及缺項返回已有隔離瀏覽器驗證。真人觀察等使用者安排。見[簡易方案驗收](simple-creation-plan.md#11-驗收清單)及[原介面驗收要求](../ui-redesign/PLAN.md#驗收要求)。

## P2／P4：模型來源與授權追溯

<a id="m01"></a>

- [ ] **M01 · Pony V6 XL 完整授權條款核對**
  - [ ] 驗收 M01-01：核對固定來源修訂的完整條款與依賴，補上可追溯連結；只有模型卡標記時仍註明尚未核對全文。
  - 2026-10-23：已閱讀 Open RAIL-M、Fair AI Public License 1.0-SD、SDXL Open RAIL++-M 全文並查核依賴來源；固定 HF 修訂僅 39 bytes 標記，相同 SHA256 的 Civitai 發布頁另列修改版 Fair AI 與變現推論限制。manifest 保存來源／條文雜湊及差異，`terms_verified` 維持 false；條款適用關係、作者附文與內嵌元件版本仍待可追溯釐清，主項／子項不勾選。見 [M01 查核](../models/pony-v6-xl-license.md)。
  - 2026-10-26：已補查[作者官網 V6 聲明](../models/pony-v6-xl-license-followup-20261026.md)，並新增[完整權重／四組元件內容指紋](../validation/pony-license-audit-20261026.json)與 CPU-only 核對器。HF／作者聲明適用關係及內嵌元件精確 revision 仍需發布者證據，`acceptance_complete=false`、`terms_verified=false`；沒有把補查／工具完成當作本驗收完成。

<a id="m02"></a>

- [ ] **M02 · FLUX 編碼器轉檔來源與授權鏈補驗**
  - [ ] 驗收 M02-01：取得固定 CLIP-L／T5 FP8 scaled 的可追溯原始權重 revision、轉換方式及適用條款；只有整合來源標記及 BFL 推薦上游時，`terms_verified`／`conversion_lineage_verified` 維持 false。
  - F02 已逐一讀取來源與全文，記錄 BFL 主模型／VAE、整合來源與上游參考的差別；本項只保留尚缺的確切轉檔來源證明，見 [條款查核](../models/flux-component-licenses.md)。
  - 2026-10-26：已補[兩檔發布提交與公開轉換來源追查](../models/flux-encoder-lineage-followup-20261026.md)，新增[完整本機指紋／CLIP 候選全張量比對](../validation/flux-encoder-audit-20261026.json)。CLIP 的 196 個 F16 張量與候選 OpenAI 固定修訂 F32 轉型後逐位元一致；T5 確認 389 張量及 168 個 scale。發布者實際輸入 revision／腳本／參數、T5 recipe 與逐元件條款仍缺，`acceptance_complete=false`，兩個原驗證旗標維持 false，主項／子項不勾選。

<a id="f01"></a>
<a id="f02"></a>
<a id="f03"></a>
<a id="f04"></a>

FLUX F01–F04 已歸檔至 [CHANGELOG](../history/changelog.md#f01)。來源缺口仍由 M02 追蹤；硬體／流程擴充見[條件式補驗](#conditional-followups)。

## 作者資料、試訓與品質驗收

T01–T08 的需求、資料契約、技術試訓、產物流程及網頁工作區已交付。[CHANGELOG](../history/changelog.md#t01)以下承接使用者提供的作者圖與角色目標。來源盤點以已記錄的 T02 驗收及工作區匯入紀錄為準。[T02 驗收](../validation/training-dataset-20261023.md)、[工作區匯入紀錄](../validation/training-workspace-20261025.md)

<a id="author-dataset-review"></a>

- [ ] **T02 後續 · 作者圖候選審查與資料包**
  - [ ] 兩份清單各有 10 張 train 候選、6 張開發評估、0 張 final test、6 張排除。逐張補畫風與角色候選的 caption、來源與用途依據，角色另核身分。維持同原作／差分群組分割；有缺少視角、服裝或場景時再補圖。按審查通過的修訂匯出、驗證只含合格 train 圖的資料包。見[資料契約](../training/dataset-contract.md)與[圖片提醒](anime-style-development.md#image-input-reminders)。

<a id="author-training-run"></a>

- [ ] **T03 後續 · 作者畫風與角色 LoRA 試訓**
  - [ ] 資料包就緒後另行安排，以固定 Animagine XL 4.0 Opt／SDXL UNet LoRA 先試畫風，再試角色，分開保留資料版本、run、設定、資源與權重指紋。使用既有技術基線確認停止、恢復與租約釋放。見[訓練規格](../training/requirements.md)、[訓練操作](../training/runtime.md)及[既有技術驗收](../validation/hardware-resources-20261026.md)。

<a id="author-quality"></a>

- [ ] **T04 後續 · 作者畫風與角色品質比較**
  - [ ] 取得未參與選型、調參或訓練的不同原作最終評估圖，保留獨立分組。現有 6 張開發評估維持原用途。
  - [ ] 回登兩件作者試訓產物並核對完整載入；各以三題材 × 兩個精確 seed × 基準／候選做 12 件比較，共 24 件。保存原圖、失敗、設定與來源，逐格人工記錄提示服從、角色一致、畫風與構圖。依既定每路徑六格中至少四格改善的訊號及其品質條件，由使用者檢視。見[固定驗收方案](../training/requirements.md#可追溯與可執行的驗收方案)及[產物操作](../training/artifacts.md)。

## P8：官方 API 服務（最後實作）

<a id="a01"></a>

- [ ] **A01 · NovelAI 官方接入查證**
  - [ ] 驗收 A01-01：核對官方 API、驗證方式、使用條件、費用與能力，以正式資料判定可接範圍。

<a id="a02"></a>

- [ ] **A02 · Mango 2 身分與官方來源查證**
  - [ ] 驗收 A02-01：確認確切模型與提供者，再核對公開權重或官方 API；網站功能不視為 API 能力。
  - [ ] 驗收 A02-02：有符合條件的公開權重時再評估本地階段，否則保留在官方服務階段。

<a id="a03"></a>

- [ ] **A03 · 正式接入門檻與服務介面**
  - [ ] 驗收 A03-01：只有確認正式接入方式才實作，分開描述本地與遠端服務能力，不顯示未支援功能為可用。

<a id="a04"></a>

- [ ] **A04 · 後端憑證保存**
  - [ ] 驗收 A04-01：驗證憑證只保存在後端，不進前端、輸出快照、日誌或版本控制。

<a id="a05"></a>

- [ ] **A05 · 提交前資料傳送及費用資訊**
  - [ ] 驗收 A05-01：明確顯示接收資料的服務及可取得的費用資訊，保留使用者提交時的選擇。

<a id="a06"></a>

- [ ] **A06 · 限流、逾時、扣費狀態與重試**
  - [ ] 驗收 A06-01：驗證未知付費結果的查詢與恢復，不自動重複付費提交，錯誤與請求可追溯。

<a id="a07"></a>

- [ ] **A07 · 遠端結果與請求設定保存**
  - [ ] 驗收 A07-01：依服務可提供範圍保存結果、設定、來源與版本，未知值不補猜，完成離線查閱驗收。

<a id="backend-backlog"></a>
<a id="storage-category-api"></a>

## 已完成能力的歷史入口

N05 生成任務抽屜、N06 同瀏覽器顯示偏好與 N07 分類容量已移至 [CHANGELOG](../history/changelog.md#n07)。原 [N07 計量與 API 規格](../history/changelog.md#storage-category-api)保留當時條件；訓練／安裝任務、跨裝置同步及特殊磁碟實測仍為後續選項。

<a id="audit-20261114"></a>

## 2026-11-14 整體分析與優化候選

本輪檢查前後端入口、任務／資料邊界、主要 Vue 工作台、樣式、功能契約、CI、文件與既有 UI 圖像，並執行下列限定檢查。這是程式與文件的整體抽查，不是逐行安全稽核或全功能實機認證。

### 整體判斷

- **架構**：Vue／FastAPI／SQLite／獨立 ComfyUI 適合目前單人本機產品。AppContext 隔離、不可變快照、UUID 恢復、精確 seed、分頁與運算租約已有明確邊界；沒有足夠證據支持改成微服務、換資料庫或重寫工作流。
- **程式**：主要維護成本集中於大型 Vue 元件、跨檔 CSS 覆蓋，以及少量尚未收斂的依賴與讀取契約。檔案長只是定位線索，不構成刪碼或全面抽象化理由。
- **功能**：本地創作、專用圖片流程、作品整理、比較、訓練工具與系統管理已有實作。主要產品缺口仍是作者資料／品質、真人第一次使用與既定最後接入的官方 API；技術交付不等同模型品質或新手可用性完成。
- **UI**：桌面視覺語言與主要工作區一致。初次稽核重現作品庫窄視窗溢出。 [作品庫待辦](#gallery-narrow-layout)
- **文件**：分類與歷史驗收完整，但 ROADMAP 混有已完成規格、歷史跳轉與目前待辦，容易重複計工。本次已移出完成敘述並保留舊錨點；長期契約仍應由主題文件負責。

### 建議順序與完成條件

先修作品庫窄視窗與 O01，再做 O02 的載入量測及 O03／O04。O05–O08 依維護與使用頻率選擇。官方 API 依既定順序最後實作，真人觀察依使用者安排。

<a id="o01"></a>

- [ ] **O01 · P1／程式可靠性：羽化預覽錯誤回覆有界讀取**（整併原 B4）
  - 依據：羽化預覽在 HTTP 錯誤分支直接呼叫 `response.json()`。成功 PNG 已限制 32 MiB，錯誤 JSON 需要獨立上限。 [inpaintPreview.ts](../../frontend/src/inpaintPreview.ts)
  - 完成條件：限制串流大小並取消超限讀取。驗證分塊、超大及無效 JSON、空回覆、取消和正常 `detail`。保留成功 PNG 的尺寸、SHA256 與過期預覽保護。

<a id="o02"></a>

- [ ] **O02 · P2／載入效能：建立首載預算與按工作區拆包**
  - 依據：[App.vue](../../frontend/src/App.vue) 靜態匯入所有主要工作區；[vite.config.ts](../../frontend/vite.config.ts) 未設定拆包。本輪正式建置主 JS **737.10 kB／gzip 231.71 kB**、CSS **169.83 kB／gzip 27.31 kB**，保留 >500 kB 提示。這是大小證據，尚未量到使用者延遲。
  - 完成條件：固定主機／瀏覽器、冷快取與資料量，記錄首次可操作時間、初始傳輸量、切頁成本；評估非首屏工作區 async import，清楚顯示載入失敗與重試。初始 JS 目標小於 500 kB，實測操作不可退步；保留 KeepAlive、未保存阻擋、跨頁原任務定位及未知提交恢復。不可只提高警告門檻。

<a id="o03"></a>

- [ ] **O03 · P2／架構：按責任拆分大型 Vue 工作台**
  - 依據：[CreationStudio.vue](../../frontend/src/CreationStudio.vue)、[ArtworkLibrary.vue](../../frontend/src/ArtworkLibrary.vue)、[SimpleCreation.vue](../../frontend/src/SimpleCreation.vue) 各混合表單／資料查詢／生命週期與大片模板；最大者超過 1,700 非空行。
  - 完成條件：先選一個實際高變更區，分離純設定轉換、查詢生命週期或展示面板，明列輸入／輸出及狀態擁有者。保留公開 props／事件、儲存 key、精確 seed、dirty／409 衝突與原 UUID 行為，跑受影響 Node／瀏覽器案例；不把不同流程硬合成通用提交器。

<a id="o04"></a>

- [ ] **O04 · P2／UI 維護：收斂 CSS 覆蓋與響應式規則**
  - 依據：[main.ts](../../frontend/src/main.ts) 依序載入 style／theme／redesign，另有元件 scoped style；[redesign.css](../../frontend/src/redesign.css) 超過 4,100 非空行，含高 specificity selector 與多處 media 覆蓋。舊 `.artwork-toolbar` 的換行設定未直接涵蓋新的 `.gallery-browser-tools`。
  - 完成條件：先盤點作品庫工具列、對話框、工作台區域的最終 computed style 與擁有檔案，再逐區整合 spacing／寬度／斷點。以 390／768／1280／1440／1920px、長模型名、空／錯誤狀態驗證可見、鍵盤可達、無整頁橫溢；不移除有動態用途的 selector，不以全域 overflow hidden 代替修正。

<a id="o05"></a>

- [ ] **O05 · P2／文件：現行契約與歷史證據分離、連結自動檢查**
  - 依據：原[架構](../development/architecture.md#storage-capacity)將已交付 N07 的 API 契約連到 ROADMAP；本輪已改到歸檔規格。多份規劃／驗收文件仍交叉引用完成項目，現有品質入口沒有專門的 Markdown／HTML 本地連結驗證階段。
  - 完成條件：現行 storage API 的權威說明歸入 operations／development，歷史驗收保留日期及限制；加入能處理相對路徑、HTML anchor 與標題錨點的文件檢查，明確排除 Git 外原始證據及外部 URL。以刻意失效的連結驗證非零退出，不改歷史 JSON 指紋、不讓待辦與交付重複計數。

<a id="o06"></a>

- [ ] **O06 · P2／功能：大量未完成任務的可達性**
  - 依據：[listing.py 的 job_overview](../../backend/listing.py)只回最近 20 個未完成及 10 個終態；[TaskDrawer.vue](../../frontend/src/TaskDrawer.vue)有截斷提示，但沒有載入較早未完成任務的控制。這是既定摘要範圍的擴充候選，並非已證明任務遺失。
  - 完成條件：用至少 25 個未完成任務（含 unknown 與不同原引擎）驗證分頁／完整任務入口能定位最舊任務；計數與清單一致、連線有界，查閱不觸發提交或取消。只有實際累積需求時擴充，訓練／安裝整合仍另行評估。

<a id="o07"></a>

- [ ] **O07 · P3／測試與依賴：逐步收斂工具重複及 schema 反向依賴**（整併原 B3／B6）
  - 依據：[flux_workflows.py](../../backend/flux_workflows.py) 的 URL validator 仍從 main 匯入 Settings，純型別已在 schemas；[check-inpaint.mjs](../../frontend/check-inpaint.mjs)與[check-control.mjs](../../frontend/check-control.mjs)重複 TS transpile／data URL 載入流程。品質 scope 是明列清單，不能把局部格式通過當全庫覆蓋。
  - 完成條件：各以小變更處理，保留 main 相容匯出與不建立 DATA 的 import 契約；共用載入器保留相依順序與錯誤非零退出，既有斷言不弱化。實質修改時按現行規則納入品質 scope；不為整齊一次格式化全庫。

<a id="o08"></a>

- [ ] **O08 · P3／UI 與素材：範例圖的按需載入**
  - 依據：[SimpleExample.vue](../../frontend/src/SimpleExample.vue) 在 details 中直接放原圖 img，沒有 lazy／展開後掛載策略；本輪輸出有多個約 1–1.9 MB 的 PNG。[simpleExamples.ts](../../frontend/src/simpleExamples.ts)的 eager URL 登記本身不等於全部圖片已下載，須先觀察 network。
  - 完成條件：量測簡易模式初訪／切配方／展開範例的圖片請求與 bytes，再選 lazy loading、展開時掛載或另外產生預覽圖。未展開的非必要圖片不搶首載；原圖、配方下載、來源 hash 與精確 seed 保持可追溯，預覽載入預留比例且有錯誤文字。不得改寫既有實測原圖冒充優化預覽。

### 本輪實際驗證與限制

- `npm.cmd run build -- --configLoader runner`：型別與正式建置通過，保留主 JS 大包警告。
- `npm.cmd test`：API／生命週期、實驗、修補、控制、預檢與配方證據契約通過。
- `.venv/Scripts/python.exe -m unittest backend.test_app_factory backend.test_workflow_support backend.test_storage_categories`：14 項通過；保留 Starlette TestClient 的 httpx 棄用提示，未在本輪更換依賴。
- Edge Chromium 隔離案例：`artwork-library.spec.ts -g "390px organize"` 1 項失敗（整頁橫溢）；`ui-redesign.spec.ts -g "display preferences|task drawer"` 實際只選到 1 項顯示偏好案例並通過，不能據此宣稱抽屜驗收。報告分別在 `runtime/quality/audit-20261114-report`、`audit-delivered-20261114-report`，Git 外保存。
- 文件檢查：三份修改文件共 281 個本地連結的路徑／Markdown 錨點核對通過，無重複顯式錨點；主線 15 項、子項 17 項及候選 8 項與清單一致；`git diff --check` 通過。
- 未跑全套後端／瀏覽器、GPU 生成／訓練、真人或實體觸控；未查詢新的外部模型條款／API 資料。M01／M02、作者品質與官方 API 仍維持原未完成狀態。本輪只修改文件，以上優化未實作。

<a id="conditional-followups"></a>

## 待評估提案與條件式補驗

各列保留已記錄的觸發條件或範圍。排入主線時補上獨立驗收。

| 範圍 | 待評估或補驗 | 依據 |
| --- | --- | --- |
| 行動與人工無障礙 | 有指定裝置／瀏覽器時補實體行動操作、人工讀屏與無障礙檢查。遮罩筆刷實體觸控由 V01-02 追蹤。 | [桌面介面驗收](../ui-redesign/ACCEPTANCE.md#rerun)、[V06 已驗範圍](../validation/ui-accessibility-20261023.md) |
| 顯示偏好與任務範圍 | 視使用需求評估 N05 納入訓練／安裝、N06 全站密度與跨裝置同步。英文介面、淺色／跟隨系統是原提案後續選項。清快取需先定義資料範圍。 | [已交付 UI 範圍](#backend-backlog)、[設定規格](../ui-redesign/PLAN.md#設定) |
| N07 分類容量補驗 | 若需驗收多磁碟與 NTFS 特殊檔案，使用實際多卷、junction、壓縮／稀疏檔核對歸屬、去重和邏輯大小。既有測試以替身覆蓋跨卷與重解析點判定。 | [N07 計量](#storage-category-api)、[掃描測試](../../backend/test_storage_categories.py) |
| 前端建置大小 | 本輪具體量測與完成條件已整併至 O02，不重複計項。 | [O02](#o02) |
| 簡易創作後續選項 | 依需求驗證更多比例、配方或流程組合。現有本機提示詞助手可手動預覽及套用英文，若要擴大適用範圍，另驗更多中文語意、生成品質及與繪圖同時使用的 RAM／耗時。 | [簡易方案第 10 節](simple-creation-plan.md#10-建議實作順序)、[提示詞驗收](../validation/prompt-converter-20261031.md) |
| 擴充模型的授權與依賴 | 固定 PVC LoRA、像素風 LoRA（含轉換版）、IKEA LoRA、Pose／Depth 權重、IP-Adapter／ViT-H 與 Fooocus 權重仍有來源條款或依賴缺口。需要相應使用範圍時，逐個補正式條款及固定修訂證據，按清冊記錄。 | [模型清冊](../../models)、[FLUX PVC LoRA](../models/flux-extensions.md)、[像素風 LoRA](../models/pixel-art-lora-sdxl.md)、[IP-Adapter](../models/ipadapter-reference.md) |
| FLUX 精度、量化與硬體 | 目標配置確認後另驗 RTX 4080、較大尺寸、32 GiB RAM 或不同精度／卸載。GGUF Q4 須先確認固定來源／hash／條款、量化 T5、節點與獨立流程。 | [3060 前置判斷](../models/flux-rtx3060-planning.md)、[F02 實測](../validation/flux-runtime-20261025.md)、[4080 實機範圍](../validation/rtx4080-workflows-20261026.md) |
| FLUX 流程擴充 | Redux／IP-Adapter／身份參考、多 LoRA、LoRA＋圖生圖，以及修補與結構引導目前各有未支援範圍。選定組合後再核對模型／節點，補流程、保存／還原、原請求恢復與實測。 | [FLUX 擴充界線](../models/flux-extensions.md)、[創作目的規格](../ui-redesign/PLAN.md#創作工作台) |
| SDXL 參考、結構與修補品質 | 按指定題材補 R05／L01 更多模型、seed、素材或提示格式。R02 可另驗 Pony、多圖／角色與畫風雙參考、LoRA／Canny 組合。R01 可另驗多人、其他尺寸／模型與 RTX 4080。R03 若選定新版，另驗 Fooocus refine 雙 latent、遮罩邊界品質及新配置。 | [動漫開發計畫](anime-style-development.md)、[參考品質](../validation/reference-adapter-20261023.md)、[結構參考](../features/structure-reference.md)、[Fooocus](../features/fooocus-inpainting.md) |
| 專用設定的圖片套件 | 目前的專用 JSON 使用本機素材 ID 與指紋。若要讓跨主機設定附帶原圖與遮罩，先定義檔案大小、解壓／路徑限制與逐角色 hash 驗證。 | [R07 設計](../development/specialized-workflow-formats.md#r07-專用格式設計草案) |
| 訓練額外配置 | 依實際訓練需求補多圖、長時間、其他 rank／主機等容量與資源驗收。既有 E04 證據是 RTX 4080 的 512／1024 短程幾何技術訓練。 | [T03 實測限制](../validation/training-runtime-20261025.md)、[E04 量測](../validation/hardware-resources-20261026.md) |
| Docker／跨系統搬移 | 有跨 OS 搬移需求時，驗證 Windows 路徑、原圖與資料包重新綁定及還原。容器 cgroup RAM 配額換算、trainer 與跨 OS GPU 租約另行評估。 | [Docker 範圍](../operations/docker.md)、[D02 驗收](../validation/docker-deployment-20261025.md) |
| B3 · FLUX URL 驗證依賴 | 直接引用純 schema，保留主程式相容匯出，驗證 URL 契約及匯入副作用。本輪整併至 [O07](#o07)，未實作。 | [原稽核 B3](../history/codebase-audit-20261027.md#b3讓-flux-url-驗證直接依賴純-schema) |
| B4 · 羽化預覽錯誤大小限制 | 納入 O01。 | [O01](#o01) |
| B5／B6 · 預覽與測試工具整理 | B5 評估 Canny／羽化共用有界串流讀取，B6 評估 Node 契約測試共用純 TS 載入。依各原契約驗證。B5 仍待評估，B6 已整併至 [O07](#o07)；均未實作。 | [原稽核 B5](../history/codebase-audit-20261027.md#b5抽取預覽串流讀取的共用機制)、[原稽核 B6](../history/codebase-audit-20261027.md#b6共用-node-契約測試的純-ts-載入助手) |
