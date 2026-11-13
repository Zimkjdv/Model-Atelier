# Model Atelier — Roadmap

個人 AI 圖像創作與實驗工作台。更新日期：2026-11-14。

<a id="pc02提示詞編輯區整併2026-11-07-完成"></a>
<a id="pc01中文描述轉英文提示詞2026-10-31-完成實作與隔離驗收"></a>

這裡維護目前尚待實作、驗收及外部證據的工作。已完成條目的證據見 [CHANGELOG](../history/changelog.md#roadmap-completed-20261025)，原清單的去向見 [歷史索引](../history/changelog.md#unchecked-index)。規格、操作與各次驗收條件由原主題文件保存。

截至 2026-11-14，主線共有 **15 個未完成主項、17 個待驗收子項**。已交付的 [N05／N06／N07](#backend-backlog) 及[待評估提案](#conditional-followups)另有狀態紀錄。

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

2026-11-13 已修正簡易創作的空描述與比例選取，並交付專用流程的提示詞助手、草稿、設定交換與比較。[交付紀錄](../history/changelog.md#2026-11-13--簡易創作與專用工作台)

| 範圍 | 未完成主項 | 待驗收子項 |
| --- | ---: | ---: |
| P0：硬體、相容性與量測 | 0 | 0 |
| P1／P6：介面、真人與實機觸控驗收 | 3 | 3 |
| P2／P4：模型來源 | 2 | 2 |
| 作者資料、試訓與品質驗收 | 3 | 4 |
| P8：官方 API（最後實作） | 7 | 8 |

## P0：硬體、相容性與量測

<a id="e02"></a>

已完成，原驗收條件與證據移至 [CHANGELOG E02](../history/changelog.md#e02)。[RTX 4080 實機紀錄](../validation/rtx4080-workflows-20261026.md)保存八個固定流程、離線核對與失敗原因；不代表未測變體或訓練通過。

<a id="e03"></a>

已完成，原驗收條件與證據移至 [CHANGELOG E03](../history/changelog.md#e03)。[兩機對照與獨立較高負載](../validation/hardware-comparison-20261026.md)保留 OS／驅動差異、單次觀察與未知峰值，未宣稱普遍加速或最低需求。

<a id="e04"></a>

已完成，原驗收條件與證據移至 [CHANGELOG E04](../history/changelog.md#e04)。[資源登記](../validation/hardware-resources-20261026.md)分開保存九筆推論與 512／1024 自製幾何技術訓練、原模型／環境／取樣定義及 CP950 失敗／UTF-8 修復。未知峰值保留 null，沒有作者圖訓練或長時間容量保證。

## P1／P6：尚未完成的介面驗收

<a id="ux01"></a>

2026-10-30 已完成 [UX01 候選審查計數與 UX01-01 驗收](../history/changelog.md#ux01)：只統計已保存 train 候選，標註通過、待處理候選、保留／排除及出口狀態分開；未保存、來源、角色、原圖與最終 test 保護保留。1280×800／1440×900／1920×1080 的驗收與原始問題記錄移至 CHANGELOG。

<a id="ux02"></a>

2026-10-30 已完成 [UX02 窄視窗審查與 UX02-01 驗收](../history/changelog.md#ux02)：1000px 以下依序排列縮圖導覽、原圖及標註表單，390px 主圖由 0×0 恢復為 220×220；原 390px 審查／保存／匯出／衝突案例通過，最終 test 與未保存保護保留。桌面三尺寸的四階段版型及流程回歸通過；不代表全站手機版或實機觸控完成。

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

## P5：FLUX.1 [schnell] 實機接入

使用者要求：實作前先依官方資料對照 RTX 3060 12 GiB、實際 RAM 與磁碟；如需量化／卸載或改用 RTX 4080，先說明限制與依據，再安排下載／GPU 試跑。官方最低值未提供時保持未知，不能把另一份對話的 GGUF Q4／32GB RAM 建議當成已驗收。已核對來源與候選路線見 [3060 前置判斷](../models/flux-rtx3060-planning.md)；GGUF 另需節點／來源／流程驗證，尚未安裝。

<a id="f01"></a>

2026-10-25 已完成 [F01 固定四元件安裝與完整 SHA256](../history/changelog.md#f01)，完整條目已移至 CHANGELOG；此錨點保留既有連結。沒有以其他來源或 GGUF 替換固定版本。

<a id="f02"></a>

F02 的逐元件條款記錄與所列 3060 原生配置觀察已移至 [CHANGELOG](../history/changelog.md#f02)。主模型 FP8／CUDA BF16 cast、CPU 編碼器與 RAM／VRAM 已有 [實際證據](../validation/flux-runtime-20261025.md)，最低需求及未觀察的 kernel 精度仍未知；M02 來源缺口保留。F03 → F04 已分別完成 [平台保存與受控 OOM](../history/changelog.md#f03)、[固定 LoRA 與 VAE 圖生圖](../history/changelog.md#f04)；32 GiB RAM、較大尺寸、Redux／身份參考及 RTX 4080 不能直接認列通過。

<a id="f03"></a>

已完成，原驗收敘述移至 [CHANGELOG](../history/changelog.md#f03)。[實際證據](../validation/flux-generation-20261025.md)只涵蓋固定 512 FP8／CPU 配置；OOM 為實際 CUDA allocator 的受控配額故障注入，不代表自然顯存門檻或更大尺寸通過。

<a id="f04"></a>

已完成，完整驗收敘述移至 [CHANGELOG](../history/changelog.md#f04)。[實際證據](../validation/flux-extensions-20261025.md)只涵蓋固定 PVC LoRA、原生 VAE 圖生圖與所列 512 配置；未知 LoRA、Redux／IP-Adapter、身份保證及混合流程保持停用。後續需要指定作者／角色圖片時，提醒依 [圖片備註](../models/flux-extensions.md#下一輪圖片提醒)完成審查與保留圖確認。

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

## UI 獨立能力：分類容量、全域任務與顯示偏好

<a id="backend-backlog"></a>

N05、N06 與 N07 已交付。後續候選見[待評估提案](#conditional-followups)。

### 狀態與證據

| 編號 | 優先級／狀態 | 交付證據 | 已交付範圍 |
| --- | --- | --- | --- |
| N07 分類容量 | P1／已交付 | [手動背景掃描、去重、快取與取消](../history/changelog.md#n07) | 本機模型與作品的邏輯大小 |
| N05 全域任務抽屜 | 已交付生成任務 | [跨頁追蹤與原任務定位](../history/changelog.md#n05) | 生成任務 |
| N06 顯示偏好保存 | 已交付 | [同瀏覽器還原排版與展開狀態](../history/changelog.md#n06) | 同瀏覽器 |

N07 的唯一含義沿用 [UI 規格](../ui-redesign/PLAN.md#原提案編號與交付範圍) 新增能力表的「模型／作品分類容量」。原 v3 文字曾重用 N07 表示尺寸能力，已移除該處錯誤編號；尺寸驗證仍按 F07 與各流程契約處理。

<a id="storage-category-api"></a>

### N07：模型與作品分類容量

#### 資料範圍與計量

1. 掃描範圍由後端解析既有受管理模型目錄、已登記的額外模型目錄及作品庫輸出。用戶端送出空 JSON 物件即可啟動。掃描採後端確認的範圍。
2. 平台主機本機路徑與遠端／容器內引擎路徑分開。無法從平台讀取的引擎檔案系統標為「此部署無法統計」，不當成空目錄或 0 GB。
3. 每個磁碟區先保留獨立統計，再在口徑相容時加總。根目錄重疊先消除；junction、符號連結避免循環；硬連結以可靠的磁碟區與檔案身分去重，不能只比較檔名。
4. 模型與作品路徑重疊或共享檔案時，兩類均標為不完整。共用檔案從兩類的用量排除。
5. 清楚區分檔案邏輯長度與磁碟實際配置量。壓縮、稀疏檔與硬連結都可能造成差異；不得直接用邏輯檔案長度扣除磁碟已用量來聲稱「其他」容量。
6. 「其他」只有在同一磁碟區、相容計量口徑、掃描範圍完整且沒有歸屬衝突時才能產生剩餘值；跨磁碟、部分失敗、統計不一致或結果為負時維持未知。分段條不能用預覽比例或估計值補齊。
7. 儲存及傳輸以整數 bytes 為準；畫面以 `bytes / 10^9` 顯示 GB。保留精度與四捨五入規則，百分比只在有效分母下計算。

#### 掃描生命週期與 API

| 介面 | 行為 |
| --- | --- |
| `POST /api/storage/scans` | 明確啟動背景工作，回傳 scan ID；相同範圍同時只執行一份，讀取頁面不自動觸發全磁碟掃描 |
| `GET /api/storage/scans/{id}` | 回報 `queued/running/completed/partial/cancelled/failed`、範圍、時間、已檢查項目數與可讀錯誤；不知道剩餘工作時不用假的進度百分比 |
| `POST /api/storage/scans/{id}/cancel` | 合作式取消，立即停止接續遍歷；保留取消狀態，不把部分數字發布為完整分類容量 |
| `GET /api/storage/categories` | 讀取最後可靠快取，包含逐類／逐磁碟區 bytes、計量口徑、完整性、起訖時間、範圍版本及過期原因 |

背景掃描限制併發、記憶體、檔案數與執行時間，避免阻塞生成與主 API。掃描中仍可看上次完整結果，但須標示時間與過期狀態；修改目錄或版本後舊快取不得冒充新範圍。程序中斷後能辨識未完成工作，且不因輪詢或重開頁面重複啟動。

#### 介面接線與完成條件

- 摘要的「尚未統計」連到實際掃描操作與範圍說明；未掃描、取消、部分失敗與真正的空分類是不同狀態。
- 分段條、圖例與明細共同使用同一份分類結果，逐項提供 GB。未知分類不佔據虛構色段，不能將磁碟已用條重新上色冒充分類條。
- 自動測試需覆蓋：空目錄、跨磁碟、重疊根路徑、硬連結、junction 循環、不可讀／消失的檔案、稀疏／壓縮口徑、掃描取消、程序重啟、過期快取與目錄變更。
- 瀏覽器驗收需沿同一份隔離目錄資料完成：首次未掃描 → 啟動 → 掃描中 → 完成 → 更新範圍 → 過期 → 部分失敗／取消。畫面數字必須能由 API 原始 bytes 對照重算。

實際操作與本機／容器範圍見[分類容量](../operations/setup-and-operations.md#storage-categories)。

### N05：生成任務抽屜已交付

[操作與範圍](../history/changelog.md#n05)涵蓋跨頁生成進度及原任務定位。訓練與安裝維持各自的工作台。

### N06：偏好保存已交付

[操作與範圍](../history/changelog.md#n06)包含跨次還原與重設。全站密度及跨裝置同步另依使用需求評估。

### 與連續旅程驗收的關係

[隔離資料逐流程驗收](../ui-redesign/ACCEPTANCE.md#isolated-journey)記錄當時的功能範圍。

<a id="conditional-followups"></a>

## 待評估提案與條件式補驗

各列保留已記錄的觸發條件或範圍。排入主線時補上獨立驗收。

| 範圍 | 待評估或補驗 | 依據 |
| --- | --- | --- |
| 行動與人工無障礙 | 有指定裝置／瀏覽器時補實體行動操作、人工讀屏與無障礙檢查。遮罩筆刷實體觸控由 V01-02 追蹤。 | [桌面介面驗收](../ui-redesign/ACCEPTANCE.md#rerun)、[V06 已驗範圍](../validation/ui-accessibility-20261023.md) |
| 顯示偏好與任務範圍 | 視使用需求評估 N05 納入訓練／安裝、N06 全站密度與跨裝置同步。英文介面、淺色／跟隨系統是原提案後續選項。清快取需先定義資料範圍。 | [已交付 UI 範圍](#backend-backlog)、[設定規格](../ui-redesign/PLAN.md#設定) |
| N07 分類容量補驗 | 若需驗收多磁碟與 NTFS 特殊檔案，使用實際多卷、junction、壓縮／稀疏檔核對歸屬、去重和邏輯大小。既有測試以替身覆蓋跨卷與重解析點判定。 | [N07 計量](#storage-category-api)、[掃描測試](../../backend/test_storage_categories.py) |
| 前端建置大小 | 已有 Vite 主 JS 超過 500 kB 提示；若列為效能工作，先量測首載與路由成本，再決定是否拆分並檢查操作回歸。 | [建置與回歸紀錄](../ui-redesign/ACCEPTANCE.md#rerun) |
| 簡易創作後續選項 | 依需求驗證更多比例、配方或流程組合。現有本機提示詞助手可手動預覽及套用英文，若要擴大適用範圍，另驗更多中文語意、生成品質及與繪圖同時使用的 RAM／耗時。 | [簡易方案第 10 節](simple-creation-plan.md#10-建議實作順序)、[提示詞驗收](../validation/prompt-converter-20261031.md) |
| 擴充模型的授權與依賴 | 固定 PVC LoRA、像素風 LoRA（含轉換版）、IKEA LoRA、Pose／Depth 權重、IP-Adapter／ViT-H 與 Fooocus 權重仍有來源條款或依賴缺口。需要相應使用範圍時，逐個補正式條款及固定修訂證據，按清冊記錄。 | [模型清冊](../../models)、[FLUX PVC LoRA](../models/flux-extensions.md)、[像素風 LoRA](../models/pixel-art-lora-sdxl.md)、[IP-Adapter](../models/ipadapter-reference.md) |
| FLUX 精度、量化與硬體 | 目標配置確認後另驗 RTX 4080、較大尺寸、32 GiB RAM 或不同精度／卸載。GGUF Q4 須先確認固定來源／hash／條款、量化 T5、節點與獨立流程。 | [3060 前置判斷](../models/flux-rtx3060-planning.md)、[F02 實測](../validation/flux-runtime-20261025.md)、[4080 實機範圍](../validation/rtx4080-workflows-20261026.md) |
| FLUX 流程擴充 | Redux／IP-Adapter／身份參考、多 LoRA、LoRA＋圖生圖，以及修補與結構引導目前各有未支援範圍。選定組合後再核對模型／節點，補流程、保存／還原、原請求恢復與實測。 | [FLUX 擴充界線](../models/flux-extensions.md)、[創作目的規格](../ui-redesign/PLAN.md#創作工作台) |
| SDXL 參考、結構與修補品質 | 按指定題材補 R05／L01 更多模型、seed、素材或提示格式。R02 可另驗 Pony、多圖／角色與畫風雙參考、LoRA／Canny 組合。R01 可另驗多人、其他尺寸／模型與 RTX 4080。R03 若選定新版，另驗 Fooocus refine 雙 latent、遮罩邊界品質及新配置。 | [動漫開發計畫](anime-style-development.md)、[參考品質](../validation/reference-adapter-20261023.md)、[結構參考](../features/structure-reference.md)、[Fooocus](../features/fooocus-inpainting.md) |
| 專用設定的圖片套件 | 目前的專用 JSON 使用本機素材 ID 與指紋。若要讓跨主機設定附帶原圖與遮罩，先定義檔案大小、解壓／路徑限制與逐角色 hash 驗證。 | [R07 設計](../development/specialized-workflow-formats.md#r07-專用格式設計草案) |
| 訓練額外配置 | 依實際訓練需求補多圖、長時間、其他 rank／主機等容量與資源驗收。既有 E04 證據是 RTX 4080 的 512／1024 短程幾何技術訓練。 | [T03 實測限制](../validation/training-runtime-20261025.md)、[E04 量測](../validation/hardware-resources-20261026.md) |
| Docker／跨系統搬移 | 有跨 OS 搬移需求時，驗證 Windows 路徑、原圖與資料包重新綁定及還原。容器 cgroup RAM 配額換算、trainer 與跨 OS GPU 租約另行評估。 | [Docker 範圍](../operations/docker.md)、[D02 驗收](../validation/docker-deployment-20261025.md) |
| B3 · FLUX URL 驗證依賴 | 直接引用純 schema，保留主程式相容匯出，驗證 URL 契約及匯入副作用。提案尚未批准。 | [原稽核 B3](../history/codebase-audit-20261027.md#b3讓-flux-url-驗證直接依賴純-schema) |
| B4 · 羽化預覽錯誤大小限制 | 目前錯誤回覆直接讀完整 JSON。若安排功能修正，限制讀取 bytes，保留成功 PNG、錯誤訊息及取消語意。提案尚未批准。 | [原稽核 B4](../history/codebase-audit-20261027.md#b4限制羽化預覽的錯誤回應大小) |
| B5／B6 · 預覽與測試工具整理 | B5 評估 Canny／羽化共用有界串流讀取，B6 評估 Node 契約測試共用純 TS 載入。依各原契約驗證。兩項提案尚未批准。 | [原稽核 B5](../history/codebase-audit-20261027.md#b5抽取預覽串流讀取的共用機制)、[原稽核 B6](../history/codebase-audit-20261027.md#b6共用-node-契約測試的純-ts-載入助手) |
