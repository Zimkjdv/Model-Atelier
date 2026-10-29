# Model Atelier — Roadmap

個人 AI 圖像創作與實驗工作台。更新日期：2026-10-30。

本檔只追蹤 **11 個未完成主項、12 個待驗收子項**（共 23 個未勾選框）。已完成條目的原驗收敘述、圖片提醒與證據移至 [CHANGELOG 已完成條目](CHANGELOG.md#roadmap-completed-20261025)；原 39 框去向與補回驗收可由 [固定歷史來源](CHANGELOG.md#unchecked-index) 追溯。2026-10-30 已完成 UX01，另記錄已重現但尚未處理的 UX02；計數因此維持 23 框。

原主線與本次確認的 UX02 納入下表；UI 的 N05 全域任務、N06 偏好保存及 N07 分類容量另由 [獨立待辦](docs/ui-redesign/BACKEND-CAPABILITIES-BACKLOG.md) 管理，尚未完成，沒有計入下表。

## 接下來的順序與條件

| 順序／條件 | 目前進度 | 下一個可驗收動作 |
| --- | --- | --- |
| 模型來源 M01／M02 | 2026-10-26 已完成公開資料補查與本機內容指紋；兩項完整驗收仍未完成 | 取得發布者可追溯的條款適用、上游 revision 及轉檔紀錄後，再更新驗證旗標 |
| 作者畫風／角色品質 | T01–T08 已提供需求、資料與訓練工具；作者圖片仍待審查 | 先完成 [T02 缺項](docs/validation/training-dataset-20261023.md)，再明確安排試訓與固定比較；最終品質驗收需獨立保留圖 |
| 窄視窗審查 UX02（另輪） | 390px 固定三欄使主圖實際尺寸為 0×0 | 待確認手機版範圍後處理；本輪桌面 UX01 已完成，沒有停用原 390px 測試 |
| 實機觸控 V01-02 | 桌面／390px 操作及模擬回歸已完成，目前無實體觸控設備 | 有設備後補實際指標互動驗收 |
| 官方 API A01–A07 | 尚未接入，維持最後實作 | A01 查正式接入資料；A02 先確認確切模型與提供者，再依 A03–A07 建立服務能力 |

近期完成：E02 → E03 → E04 已驗證 RTX 4080 八流程、兩機相同配置比較、1536² 較高負載與 512／1024 自製幾何技術訓練。F01–F04 已完成 RTX 3060／約 64 GiB RAM 的固定 512 FLUX 配置；RTX 4080 的 SDXL 驗收不涵蓋 FLUX。T05–T08 的圖片審查、訓練控制、缺項導覽及報告，以及 D01／D02 本機部署與選用 Docker 均已完成，證據保留於 [CHANGELOG.md](CHANGELOG.md)。

各工作項獨立驗證、commit／push 後再接續下一項。已完成項只針對可重現問題改善；其他配置另立實測，不以技術試訓認列作者品質，不自動批准作者圖片。延伸模組參考 [GitHub 借用決策](docs/research/upstream-reuse.md#reuse-assessment)。

技術維持 Vue／FastAPI／SQLite 與獨立 ComfyUI；保留原 UUID／端點、不可變快照、精確 seed、未知結果不重送及未知能力標示。權重／原始圖片／runtime 不進 Git，不以顯卡型號或 VRAM 估算保證可執行。驗收以 [docs/validation](docs/validation) 及各功能說明為準。

| 範圍 | 未完成主項 | 待驗收子項 |
| --- | ---: | ---: |
| P0：硬體、相容性與量測 | 0 | 0 |
| P1／P6：介面顯示與實機觸控 | 2 | 2 |
| P2／P4：模型來源 | 2 | 2 |
| P8：官方 API（最後實作） | 7 | 8 |

## P0：硬體、相容性與量測

<a id="e02"></a>

已完成，原驗收條件與證據移至 [CHANGELOG E02](CHANGELOG.md#e02)。[RTX 4080 實機紀錄](docs/validation/rtx4080-workflows-20261026.md)保存八個固定流程、離線核對與失敗原因；不代表未測變體或訓練通過。

<a id="e03"></a>

已完成，原驗收條件與證據移至 [CHANGELOG E03](CHANGELOG.md#e03)。[兩機對照與獨立較高負載](docs/validation/hardware-comparison-20261026.md)保留 OS／驅動差異、單次觀察與未知峰值，未宣稱普遍加速或最低需求。

<a id="e04"></a>

已完成，原驗收條件與證據移至 [CHANGELOG E04](CHANGELOG.md#e04)。[資源登記](docs/validation/hardware-resources-20261026.md)分開保存九筆推論與 512／1024 自製幾何技術訓練、原模型／環境／取樣定義及 CP950 失敗／UTF-8 修復。未知峰值保留 null，沒有作者圖訓練或長時間容量保證。

## P1／P6：尚未完成的介面驗收

<a id="ux01"></a>

2026-10-30 已完成 [UX01 候選審查計數與 UX01-01 驗收](CHANGELOG.md#ux01)：只統計已保存 train 候選，標註通過、待處理候選、保留／排除及出口狀態分開；未保存、來源、角色、原圖與最終 test 保護保留。1280×800／1440×900／1920×1080 的驗收與原始問題記錄移至 CHANGELOG。

<a id="ux02"></a>

- [ ] **UX02 · 訓練審查窄視窗的主圖被固定三欄壓縮**
  - 2026-10-30 沿用原 `training-review.spec.ts` 的 390px 案例時重現：匯入清單後，審查主圖存在於 DOM，實際尺寸卻為 0×0。獨立隔離檢查量得內容寬 254px、grid 欄寬 `180px 21px 21px`，主圖卡片寬 42px；同資料在 1440px 的主圖為 504×504。
  - 原因：[redesign.css](frontend/src/redesign.css) 的 `.training-review-grid` 固定三欄與卡片內距在此寬度耗盡主圖內容空間。本輪沒有改這套 grid；UX01 的計數及桌面三尺寸正常，不能據此宣稱 390px 審查通過。
  - [ ] 驗收 UX02-01：後續確認手機版範圍與替代排列後，於 390px 驗證主圖為非零尺寸、標註與版本操作可使用、沒有整頁橫向溢出，並保留最終 test 不預覽與未保存保護。
  - 本輪依既定桌面範圍只記錄，不新增手機版規格，也不刪除、跳過或放寬原 390px 測試；該項仍會因主圖不可見而失敗。

<a id="v01"></a>

- [ ] **V01 · 遮罩筆刷與觸控的真實瀏覽器補驗**
  - 已完成部分：[V01-01 筆刷與 PNG 操作](CHANGELOG.md#v01-01)，此處只追蹤 V01-02 實機觸控。
  - [ ] 驗收 V01-02：在桌面與 390px 視窗操作；使用實際觸控能力驗證指標互動，無觸控環境不能標記觸控通過。

  2026-10-23：1440px／390px Chromium 完成操作與保存 PNG 的逐像素雜湊核對；修正素材重讀／切頁清空筆畫、取消選取值未復原及非 PNG 載入問題。主指標、越界捕獲、取消、停用與第二指模擬回歸通過。使用者確認目前沒有實體觸控裝置；V01-02 的實機觸控與 V01 主項保留未完成。見 [V01 驗收紀錄](docs/validation/mask-editor-20261023.md)。

## P2／P4：模型來源與授權追溯

<a id="m01"></a>

- [ ] **M01 · Pony V6 XL 完整授權條款核對**
  - [ ] 驗收 M01-01：核對固定來源修訂的完整條款與依賴，補上可追溯連結；只有模型卡標記時仍註明尚未核對全文。
  - 2026-10-23：已閱讀 Open RAIL-M、Fair AI Public License 1.0-SD、SDXL Open RAIL++-M 全文並查核依賴來源；固定 HF 修訂僅 39 bytes 標記，相同 SHA256 的 Civitai 發布頁另列修改版 Fair AI 與變現推論限制。manifest 保存來源／條文雜湊及差異，`terms_verified` 維持 false；條款適用關係、作者附文與內嵌元件版本仍待可追溯釐清，主項／子項不勾選。見 [M01 查核](docs/models/pony-v6-xl-license.md)。
  - 2026-10-26：已補查[作者官網 V6 聲明](docs/models/pony-v6-xl-license-followup-20261026.md)，並新增[完整權重／四組元件內容指紋](docs/validation/pony-license-audit-20261026.json)與 CPU-only 核對器。HF／作者聲明適用關係及內嵌元件精確 revision 仍需發布者證據，`acceptance_complete=false`、`terms_verified=false`；沒有把補查／工具完成當作本驗收完成。

<a id="m02"></a>

- [ ] **M02 · FLUX 編碼器轉檔來源與授權鏈補驗**
  - [ ] 驗收 M02-01：取得固定 CLIP-L／T5 FP8 scaled 的可追溯原始權重 revision、轉換方式及適用條款；只有整合來源標記及 BFL 推薦上游時，`terms_verified`／`conversion_lineage_verified` 維持 false。
  - F02 已逐一讀取來源與全文，記錄 BFL 主模型／VAE、整合來源與上游參考的差別；本項只保留尚缺的確切轉檔來源證明，見 [條款查核](docs/models/flux-component-licenses.md)。
  - 2026-10-26：已補[兩檔發布提交與公開轉換來源追查](docs/models/flux-encoder-lineage-followup-20261026.md)，新增[完整本機指紋／CLIP 候選全張量比對](docs/validation/flux-encoder-audit-20261026.json)。CLIP 的 196 個 F16 張量與候選 OpenAI 固定修訂 F32 轉型後逐位元一致；T5 確認 389 張量及 168 個 scale。發布者實際輸入 revision／腳本／參數、T5 recipe 與逐元件條款仍缺，`acceptance_complete=false`，兩個原驗證旗標維持 false，主項／子項不勾選。

## P5：FLUX.1 [schnell] 實機接入

使用者要求：實作前先依官方資料對照 RTX 3060 12 GiB、實際 RAM 與磁碟；如需量化／卸載或改用 RTX 4080，先說明限制與依據，再安排下載／GPU 試跑。官方最低值未提供時保持未知，不能把另一份對話的 GGUF Q4／32GB RAM 建議當成已驗收。已核對來源與候選路線見 [3060 前置判斷](docs/models/flux-rtx3060-planning.md)；GGUF 另需節點／來源／流程驗證，尚未安裝。

<a id="f01"></a>

2026-10-25 已完成 [F01 固定四元件安裝與完整 SHA256](CHANGELOG.md#f01)，完整條目已移至 CHANGELOG；此錨點保留既有連結。沒有以其他來源或 GGUF 替換固定版本。

<a id="f02"></a>

F02 的逐元件條款記錄與所列 3060 原生配置觀察已移至 [CHANGELOG](CHANGELOG.md#f02)。主模型 FP8／CUDA BF16 cast、CPU 編碼器與 RAM／VRAM 已有 [實際證據](docs/validation/flux-runtime-20261025.md)，最低需求及未觀察的 kernel 精度仍未知；M02 來源缺口保留。F03 → F04 已分別完成 [平台保存與受控 OOM](CHANGELOG.md#f03)、[固定 LoRA 與 VAE 圖生圖](CHANGELOG.md#f04)；32 GiB RAM、較大尺寸、Redux／身份參考及 RTX 4080 不能直接認列通過。

<a id="f03"></a>

已完成，原驗收敘述移至 [CHANGELOG](CHANGELOG.md#f03)。[實際證據](docs/validation/flux-generation-20261025.md)只涵蓋固定 512 FP8／CPU 配置；OOM 為實際 CUDA allocator 的受控配額故障注入，不代表自然顯存門檻或更大尺寸通過。

<a id="f04"></a>

已完成，完整驗收敘述移至 [CHANGELOG](CHANGELOG.md#f04)。[實際證據](docs/validation/flux-extensions-20261025.md)只涵蓋固定 PVC LoRA、原生 VAE 圖生圖與所列 512 配置；未知 LoRA、Redux／IP-Adapter、身份保證及混合流程保持停用。後續需要指定作者／角色圖片時，提醒依 [圖片備註](docs/models/flux-extensions.md#下一輪圖片提醒)完成審查與保留圖確認。

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
