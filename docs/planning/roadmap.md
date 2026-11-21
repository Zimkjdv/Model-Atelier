# Model Atelier — Roadmap

個人 AI 圖像創作與實驗工作台。更新日期為 2026-11-21。

**使用範圍：本專案僅供桌面電腦使用，沒有手機使用需求。** 介面驗收以桌面瀏覽器為主。390px 是既有自動化測試用的窄視窗寬度，用於檢查縮窄視窗時的溢出與操作。

這裡維護目前尚待實作、驗收及外部證據的工作。規格、操作與各次驗收條件由原主題文件保存。 [CHANGELOG](../history/changelog.md) · [原清單歷史索引](../history/changelog.md#unchecked-index)

目前共 **17 個未完成主項、19 個待驗收子項**。 [O11–O14 依據與驗收](#audit-20261121) · [已完成變更](../history/changelog.md)

## 目前進度與接續條件

| 範圍 | 目前進度 | 下一個可驗收動作 |
| --- | --- | --- |
| 簡易創作真人驗收 | 依使用者安排延後 | 有新手參與時觀察[第一次創作](#simple-first-use) |
| 模型來源 M01／M02 | 完整來源鏈仍待確認 | 取得發布者可追溯的條款適用、上游 revision 或轉檔紀錄 |
| 作者畫風／角色品質 | 角色試訓及獨立評估圖待補 | 使用已驗證資料包安排[角色 LoRA 試訓](#author-training-run)，備妥保留圖後做[固定品質比較](#author-quality) |
| 實機觸控 V01-02 | 待有桌面觸控設備 | 在實機操作遮罩筆刷並核對保存結果 |
| 官方 API A01–A07 | 尚未接入，依既定順序最後實作 | 先查 NovelAI 正式資料並確認 Mango 2 身分，才評估接入 |

技術維持 Vue／FastAPI／SQLite 與獨立 ComfyUI，保留原 UUID、端點、不可變快照、精確 seed 與未知結果的恢復規則。原始圖片、權重與 runtime 保存在 Git 外。驗收證據依配置與資料範圍記於 [docs/validation](../validation)，採用上游能力的依據見[借用決策](../research/upstream-reuse.md#reuse-assessment)。

| 範圍 | 未完成主項 | 待驗收子項 |
| --- | ---: | ---: |
| O11–O14：本輪改善 | 4 | 4 |
| P1／P6：介面、真人與實機觸控驗收 | 2 | 2 |
| P2／P4：模型來源 | 2 | 2 |
| 作者資料、試訓與品質驗收 | 2 | 3 |
| P8：官方 API（最後實作） | 7 | 8 |

<a id="audit-20261121"></a>

## 2026-11-21 整體檢視與改善順序

Vue 負責互動、FastAPI 協調任務與 SQLite 紀錄、ComfyUI 獨立推論，這個分工仍適合單人桌面工作台。接下來改善功能說明、桌面操作、素材庫載圖及跨頁回歸。官方服務仍排在本地工作之後。

<a id="o11"></a>

- [ ] **O11 · 說清楚 FLUX 圖片輸入的支援範圍（中優先）**。現有工作台可用一張素材做 VAE 圖生圖，但素材庫的流程清單沒有這個項目，參考流程文件又寫「尚未支援參考圖」。讀者難以判斷構圖重繪和角色／畫風參考各自的支援範圍。 [能力清單](../../backend/reference_workflows.py) · [參考流程說明](../models/reference-workflows.md) · [FLUX 已驗收配置](../models/flux-extensions.md)
  - [ ] 從素材庫的流程說明或參考流程文件，都能找到 FLUX VAE 圖生圖入口、單張輸入及固定元件要求，並辨識 Redux／IP-Adapter 的支援狀態。以能力 API 與桌面畫面核對流程 ID 和輸入數，文件連到同一份配置說明。

<a id="o12"></a>

- [ ] **O12 · 區分引擎連線測試與保存中的畫面（中優先）**。設定頁的兩個動作共用 `saving`。按「測試（不保存）」等待回覆時，旁邊的按鈕會顯示「保存中…」，使用者無法從狀態判斷引擎位址是否正在寫入。 [設定頁的表單與請求](../../frontend/src/App.vue)
  - [ ] 延遲測試請求，核對等待、成功、失敗三種狀態均指向受測位址，請求紀錄沒有寫入設定。另驗保存期間的提示、成功後套用的位址，以及兩種操作都能阻擋重複點擊。 [設定頁瀏覽器案例](../../frontend/tests/ui-accessibility.spec.ts)

<a id="o13"></a>

- [ ] **O13 · 降低素材庫卡片載圖量（中優先）**。每頁最多 40 張素材，卡片雖有延遲載入，進入載入範圍時仍取回完整正規化 PNG。作品庫已有獨立縮圖與缺圖提示，可沿用其互動方式。 [素材卡片](../../frontend/src/AssetLibrary.vue) · [素材圖片端點](../../backend/core_api.py) · [作品庫卡片](../../frontend/src/ArtworkLibrary.vue)
  - [ ] 用同一組高解析素材比較桌面首屏的圖片請求及實收位元組。卡片使用縮圖、傳輸量低於基線，舊素材或缺縮圖仍可開啟詳情。核對詳情與創作輸入讀到的正規化 PNG 及 SHA256 與改善前一致。

<a id="o14"></a>

- [ ] **O14 · 讓空庫到作品匯出的完整流程進入 CI（後續）**。這條 Playwright 案例已有獨立空庫設定，一般品質入口只收集 `frontend/tests/`。因此即使各頁測試通過，跨頁的生成、匯入、比較與下載也可能缺少該次提交的驗證。 [品質入口](../../scripts/check_quality.py) · [獨立瀏覽器設定](../../frontend/playwright.journey.config.ts) · [Windows CI](../../.github/workflows/quality.yml)
  - [ ] 在 CI 以獨立的空庫與合成引擎執行現有案例，讓該案例失敗能反映在 CI 結果並保存對應報告。核對一般瀏覽器批次與此案例各執行一次，更新品質指南的實際覆蓋及時間預算。 [現有操作與覆蓋](../development/quality-checks.md#同組隔離資料連續驗收)

## P1／P6：尚未完成的介面驗收

<a id="v01"></a>

- [ ] **V01 · 桌面實機觸控補驗**
  - [ ] 驗收 V01-02：在具觸控功能的桌面設備驗證遮罩筆刷指標互動、畫布及保存 PNG。 [實機驗收方式](../validation/mask-editor-20261023.md#剩餘實機驗收) · [已交付 V01-01](../history/changelog.md#v01-01)

<a id="simple-first-use"></a>

- [ ] **簡易創作 11.1 · 真人新手首次操作**（使用者延後）
  - [ ] 觀察已完成安裝的新手能否辨識簡易入口，選卡、生成、保存及修改再生成，盡量不展開技術參數。另記錄他能否理解缺模型／元件的說明，並在處理後回到原選卡及描述。原桌面規格也將 10 秒內辨識入口列為可用性觀察目標。
  - [簡易方案驗收](simple-creation-plan.md#11-驗收清單) · [原介面驗收要求](../ui-redesign/PLAN.md#驗收要求)

## P2／P4：模型來源與授權追溯

<a id="m01"></a>

- [ ] **M01 · Pony V6 XL 完整授權條款核對**
  - [ ] 驗收 M01-01：核對固定來源修訂的完整條款與依賴，補上可追溯連結；只有模型卡標記時仍註明尚未核對全文。
  - 尚缺固定 Hugging Face 修訂與作者聲明的適用關係、作者附文及內嵌元件的確切修訂。`acceptance_complete` 與 `terms_verified` 維持 `false`。 [M01 歷次查核與證據](../history/changelog.md#m01-source-audit)

<a id="m02"></a>

- [ ] **M02 · FLUX 編碼器轉檔來源與授權鏈補驗**
  - [ ] 驗收 M02-01：取得固定 CLIP-L／T5 FP8 scaled 的可追溯原始權重 revision、轉換方式及適用條款；只有整合來源標記及 BFL 推薦上游時，`terms_verified`／`conversion_lineage_verified` 維持 false。
  - 尚缺發布者實際使用的來源修訂、轉檔腳本／參數、T5 轉換配方及逐元件條款。`acceptance_complete` 維持 `false`。 [M02 歷次查核與證據](../history/changelog.md#m02-source-audit) · [逐元件條款](../models/flux-component-licenses.md)

## 作者資料、試訓與品質驗收

以下為使用者提供的作者圖與角色目標。來源盤點以既有清單與匯入紀錄為準。 [T02 驗收](../validation/training-dataset-20261023.md) · [工作區匯入紀錄](../validation/training-workspace-20261025.md)

<a id="author-training-run"></a>

- [ ] **T03 後續 · 作者角色 LoRA 試訓**
  - [ ] 以固定 Animagine XL 4.0 Opt／SDXL UNet LoRA 完成獨立角色試訓，保存資料版本、run、設定、資源與權重指紋。依試訓目標核對側面、日常服裝與場景涵蓋，按需補圖。使用既有技術基線確認停止、恢復與租約釋放。 [已完成的畫風試訓](../history/changelog.md#t03-style-pilot-20261114) · [T02 已驗證資料包](../history/changelog.md#t02-author-review-20261114) · [訓練規格](../training/requirements.md) · [訓練操作](../training/runtime.md) · [技術驗收](../validation/hardware-resources-20261026.md)

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

<a id="conditional-followups"></a>

## 待評估提案與條件式補驗

各列保留已記錄的觸發條件或範圍。排入主線時補上獨立驗收。

| 範圍 | 待評估或補驗 | 依據 |
| --- | --- | --- |
| 桌面人工無障礙 | 有指定桌面瀏覽器時補人工讀屏與無障礙檢查。桌面觸控設備的遮罩筆刷驗收由 V01-02 追蹤。 | [桌面介面驗收](../ui-redesign/ACCEPTANCE.md#rerun)、[V06 已驗範圍](../validation/ui-accessibility-20261023.md) |
| 顯示偏好與任務範圍 | 視使用需求評估 N05 納入訓練／安裝、N06 全站密度與跨裝置同步。英文介面、淺色／跟隨系統是原提案後續選項。清快取需先定義資料範圍。 | [已交付 UI 範圍](../history/changelog.md#backend-backlog)、[設定規格](../ui-redesign/PLAN.md#設定) |
| N07 分類容量補驗 | 若需驗收多磁碟與 NTFS 特殊檔案，使用實際多卷、junction、壓縮／稀疏檔核對歸屬、去重和邏輯大小。既有測試以替身覆蓋跨卷與重解析點判定。 | [N07 計量](../development/storage-scan-api.md#storage-category-api)、[掃描測試](../../backend/test_storage_categories.py) |
| 簡易創作後續選項 | 依需求驗證更多比例、配方或流程組合。現有本機提示詞助手可手動預覽及套用英文，若要擴大適用範圍，另驗更多中文語意、生成品質及與繪圖同時使用的 RAM／耗時。 | [簡易方案第 10 節](simple-creation-plan.md#10-建議實作順序)、[提示詞驗收](../validation/prompt-converter-20261031.md) |
| 擴充模型的授權與依賴 | 固定 PVC LoRA、像素風 LoRA（含轉換版）、IKEA LoRA、Pose／Depth 權重、IP-Adapter／ViT-H 與 Fooocus 權重仍有來源條款或依賴缺口。需要相應使用範圍時，逐個補正式條款及固定修訂證據，按清冊記錄。 | [模型清冊](../../models)、[FLUX PVC LoRA](../models/flux-extensions.md)、[像素風 LoRA](../models/pixel-art-lora-sdxl.md)、[IP-Adapter](../models/ipadapter-reference.md) |
| FLUX 精度、量化與硬體 | 目標配置確認後另驗 RTX 4080、較大尺寸、32 GiB RAM 或不同精度／卸載。GGUF Q4 須先確認固定來源／hash／條款、量化 T5、節點與獨立流程。 | [3060 前置判斷](../models/flux-rtx3060-planning.md)、[F02 實測](../validation/flux-runtime-20261025.md)、[4080 實機範圍](../validation/rtx4080-workflows-20261026.md) |
| FLUX 流程擴充 | Redux／IP-Adapter／身份參考、多 LoRA、LoRA＋圖生圖，以及修補與結構引導目前各有未支援範圍。選定組合後再核對模型／節點，補流程、保存／還原、原請求恢復與實測。 | [FLUX 擴充界線](../models/flux-extensions.md)、[創作目的規格](../ui-redesign/PLAN.md#創作工作台) |
| SDXL 參考、結構與修補品質 | 按指定題材補 R05／L01 更多模型、seed、素材或提示格式。R02 可另驗 Pony、多圖／角色與畫風雙參考、LoRA／Canny 組合。R01 可另驗多人、其他尺寸／模型與 RTX 4080。R03 若選定新版，另驗 Fooocus refine 雙 latent、遮罩邊界品質及新配置。 | [動漫開發計畫](anime-style-development.md)、[參考品質](../validation/reference-adapter-20261023.md)、[結構參考](../features/structure-reference.md)、[Fooocus](../features/fooocus-inpainting.md) |
| 專用設定的圖片套件 | 目前的專用 JSON 使用本機素材 ID 與指紋。若要讓跨主機設定附帶原圖與遮罩，先定義檔案大小、解壓／路徑限制與逐角色 hash 驗證。 | [R07 設計](../development/specialized-workflow-formats.md#r07-專用格式設計草案) |
| 訓練額外配置 | 依實際訓練需求補多圖、長時間、其他 rank／主機等容量與資源驗收。既有 E04 證據是 RTX 4080 的 512／1024 短程幾何技術訓練。 | [T03 實測限制](../validation/training-runtime-20261025.md)、[E04 量測](../validation/hardware-resources-20261026.md) |
| Docker／跨系統搬移 | 有跨 OS 搬移需求時，驗證 Windows 路徑、原圖與資料包重新綁定及還原。容器 cgroup RAM 配額換算、trainer 與跨 OS GPU 租約另行評估。 | [Docker 範圍](../operations/docker.md)、[D02 驗收](../validation/docker-deployment-20261025.md) |
| B5 · 預覽串流讀取 | 評估 Canny／羽化共用有界串流讀取，依各原契約驗證。 | [原稽核 B5](../history/codebase-audit-20261027.md#b5抽取預覽串流讀取的共用機制) |

## 歷史連結

<a id="o09"></a>
<a id="o10"></a>
<a id="author-dataset-review"></a>
<a id="pc02提示詞編輯區整併2026-11-07-完成"></a>
<a id="pc01中文描述轉英文提示詞2026-10-31-完成實作與隔離驗收"></a>
<a id="e02"></a>
<a id="e03"></a>
<a id="e04"></a>
<a id="ux01"></a>
<a id="ux02"></a>
<a id="f01"></a>
<a id="f02"></a>
<a id="f03"></a>
<a id="f04"></a>
<a id="backend-backlog"></a>
<a id="storage-category-api"></a>
<a id="gallery-narrow-layout"></a>
<a id="audit-20261114"></a>
<a id="o01"></a>
<a id="o02"></a>
<a id="o03"></a>
<a id="o04"></a>
<a id="o05"></a>
<a id="o06"></a>
<a id="o07"></a>
<a id="o08"></a>
<a id="已完成能力的歷史入口"></a>
<a id="2026-11-14-整體分析與優化候選"></a>
<a id="整體判斷"></a>
<a id="建議順序與完成條件"></a>
<a id="初次稽核的驗證與限制"></a>

舊章節的交付紀錄集中於 [CHANGELOG 歷史入口](../history/changelog.md#roadmap-history-index)。近期紀錄見 [O09 素材封存保護](../history/changelog.md#o09)與 [O10 任務抽屜計數](../history/changelog.md#o10)。
