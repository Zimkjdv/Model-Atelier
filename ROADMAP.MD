# Model Atelier — Roadmap

個人 AI 圖像創作與實驗工作台。更新日期：2026-10-26。

本檔只追蹤 **10 個未完成主項、11 個待驗收子項**（共 21 個未勾選框）。已完成條目的原驗收敘述、圖片提醒與證據移至 [CHANGELOG 已完成條目](CHANGELOG.MD#roadmap-completed-20261025)；原 39 框去向與補回驗收也保留於 [歷史索引](CHANGELOG.MD#unchecked-index)。移動不改變完成狀態，也不新增實測結論。

## 接下來的順序與條件

已依序完成 [T07 缺項導覽](CHANGELOG.MD#t07) → [T08 訓練報告](CHANGELOG.MD#t08)，以及 [F01 固定安裝](CHANGELOG.MD#f01) → [F02 精度／資源](CHANGELOG.MD#f02) → [F03 平台保存／受控 OOM](CHANGELOG.MD#f03) → [F04 固定 LoRA／原生圖生圖](CHANGELOG.MD#f04)，各項先 commit／push 才開始下一項。固定實測限 3060／64 GiB RAM 的所列 512 配置；編碼器轉檔來源缺口仍列 M02，沒有當成全部條款或動漫品質已驗證。

使用者已確認維持同一台電腦使用，上一輪依序完成 [D01](CHANGELOG.MD#d01) → [D02](CHANGELOG.MD#d02)，每項完成後先 commit、push，才做下一項。其餘項目依下列設備、來源及資料審查條件推進；Docker 保持選用，不新增日常前置需求。

先前已依序完成 [T05](CHANGELOG.MD#t05) → [T06](CHANGELOG.MD#t06)，維持各自驗證、commit、push 後才開始下一項。不自動批准作者圖或開始訓練。

- E02 → E03 → E04 已依序完成本機 RTX 4080 八流程、兩機固定配置比較、1536² 較高負載及 512／1024 合成訓練資源實測，每項先 commit／push 才開始下一項。V01-02 需要實體觸控設備，目前不可用。
- E04 分開保存九筆 RTX 4080 推論及兩筆技術訓練；其他配置需新實測，不能當作作者品質或最低容量保證。
- M01 的發布條款差異及依賴來源未釐清；M02 保留 FLUX 編碼器確切上游／轉檔來源的追溯缺口。FLUX F01／F02 已完成所列安裝、條款記錄及原生配置觀察，F03 → F04 已各自完成所列固定配置，完整條目與限制移至 CHANGELOG。
- 作者畫風／角色真實訓練前，仍需完成 [T02 本批圖片審查](docs/validation/training-dataset-20261023.md)；最終品質比較前提醒確認未參與調參的獨立保留圖。T03／T04 技術驗收不代表作者品質通過。
- 官方 API 仍最後實作；A02 先確認確切模型與提供者。已完成項只針對可重現問題局部改善，參考 [GitHub 借用決策](docs/github-reuse-assessment-20261023.md)。

技術維持 Vue／FastAPI／SQLite 與獨立 ComfyUI；保留原 UUID／端點、不可變快照、精確 seed、未知結果不重送及未知能力標示。權重／原始圖片／runtime 不進 Git，不以顯卡型號或 VRAM 估算保證可執行。驗收以 [docs/validation](docs/validation) 及各功能說明為準。

| 範圍 | 未完成主項 | 待驗收子項 |
| --- | ---: | ---: |
| P0：硬體、相容性與量測 | 0 | 0 |
| P1／P6：實機觸控 | 1 | 1 |
| P2／P4：模型來源 | 2 | 2 |
| P8：官方 API（最後實作） | 7 | 8 |

## P0：硬體、相容性與量測

<a id="e02"></a>

已完成，原驗收條件與證據移至 [CHANGELOG E02](CHANGELOG.MD#e02)。[RTX 4080 實機紀錄](docs/validation/rtx4080-workflows-20261026.md)保存八個固定流程、離線核對與失敗原因；不代表未測變體或訓練通過。

<a id="e03"></a>

已完成，原驗收條件與證據移至 [CHANGELOG E03](CHANGELOG.MD#e03)。[兩機對照與獨立較高負載](docs/validation/hardware-comparison-20261026.md)保留 OS／驅動差異、單次觀察與未知峰值，未宣稱普遍加速或最低需求。

<a id="e04"></a>

已完成，原驗收條件與證據移至 [CHANGELOG E04](CHANGELOG.MD#e04)。[資源登記](docs/validation/hardware-resources-20261026.md)分開保存九筆推論與 512／1024 自製幾何技術訓練、原模型／環境／取樣定義及 CP950 失敗／UTF-8 修復。未知峰值保留 null，沒有作者圖訓練或長時間容量保證。

## P1／P6：尚未完成的介面驗收

<a id="v01"></a>

- [ ] **V01 · 遮罩筆刷與觸控的真實瀏覽器補驗**
  - 已完成部分：[V01-01 筆刷與 PNG 操作](CHANGELOG.MD#v01-01)，此處只追蹤 V01-02 實機觸控。
  - [ ] 驗收 V01-02：在桌面與 390px 視窗操作；使用實際觸控能力驗證指標互動，無觸控環境不能標記觸控通過。

  2026-10-23：1440px／390px Chromium 完成操作與保存 PNG 的逐像素雜湊核對；修正素材重讀／切頁清空筆畫、取消選取值未復原及非 PNG 載入問題。主指標、越界捕獲、取消、停用與第二指模擬回歸通過。使用者確認目前沒有實體觸控裝置；V01-02 的實機觸控與 V01 主項保留未完成。見 [V01 驗收紀錄](docs/validation/mask-editor-20261023.md)。

## P2／P4：模型來源與更多 LoRA 品質

<a id="m01"></a>

- [ ] **M01 · Pony V6 XL 完整授權條款核對**
  - [ ] 驗收 M01-01：核對固定來源修訂的完整條款與依賴，補上可追溯連結；只有模型卡標記時仍註明尚未核對全文。
  - 2026-10-23：已閱讀 Open RAIL-M、Fair AI Public License 1.0-SD、SDXL Open RAIL++-M 全文並查核依賴來源；固定 HF 修訂僅 39 bytes 標記，相同 SHA256 的 Civitai 發布頁另列修改版 Fair AI 與變現推論限制。manifest 保存來源／條文雜湊及差異，`terms_verified` 維持 false；條款適用關係、作者附文與內嵌元件版本仍待可追溯釐清，主項／子項不勾選。見 [M01 查核](docs/models/pony-v6-xl-license.md)。

<a id="m02"></a>

- [ ] **M02 · FLUX 編碼器轉檔來源與授權鏈補驗**
  - [ ] 驗收 M02-01：取得固定 CLIP-L／T5 FP8 scaled 的可追溯原始權重 revision、轉換方式及適用條款；只有整合來源標記及 BFL 推薦上游時，`terms_verified`／`conversion_lineage_verified` 維持 false。
  - F02 已逐一讀取來源與全文，記錄 BFL 主模型／VAE、整合來源與上游參考的差別；本項只保留尚缺的確切轉檔來源證明，見 [條款查核](docs/models/flux-component-licenses.md)。

## P5：FLUX.1 [schnell] 實機接入

使用者要求：實作前先依官方資料對照 RTX 3060 12 GiB、實際 RAM 與磁碟；如需量化／卸載或改用 RTX 4080，先說明限制與依據，再安排下載／GPU 試跑。官方最低值未提供時保持未知，不能把另一份對話的 GGUF Q4／32GB RAM 建議當成已驗收。已核對來源與候選路線見 [3060 前置判斷](docs/models/flux-rtx3060-planning.md)；GGUF 另需節點／來源／流程驗證，尚未安裝。

<a id="f01"></a>

2026-10-25 已完成 [F01 固定四元件安裝與完整 SHA256](CHANGELOG.MD#f01)，完整條目已移至 CHANGELOG；此錨點保留既有連結。沒有以其他來源或 GGUF 替換固定版本。

<a id="f02"></a>

F02 的逐元件條款記錄與所列 3060 原生配置觀察已移至 [CHANGELOG](CHANGELOG.MD#f02)。主模型 FP8／CUDA BF16 cast、CPU 編碼器與 RAM／VRAM 已有 [實際證據](docs/validation/flux-runtime-20261025.md)，最低需求及未觀察的 kernel 精度仍未知；M02 來源缺口保留。F03 → F04 已分別完成 [平台保存與受控 OOM](CHANGELOG.MD#f03)、[固定 LoRA 與 VAE 圖生圖](CHANGELOG.MD#f04)；32 GiB RAM、較大尺寸、Redux／身份參考及 RTX 4080 不能直接認列通過。

<a id="f03"></a>

已完成，原驗收敘述移至 [CHANGELOG](CHANGELOG.MD#f03)。[實際證據](docs/validation/flux-generation-20261025.md)只涵蓋固定 512 FP8／CPU 配置；OOM 為實際 CUDA allocator 的受控配額故障注入，不代表自然顯存門檻或更大尺寸通過。

<a id="f04"></a>

已完成，完整驗收敘述移至 [CHANGELOG](CHANGELOG.MD#f04)。[實際證據](docs/validation/flux-extensions-20261025.md)只涵蓋固定 PVC LoRA、原生 VAE 圖生圖與所列 512 配置；未知 LoRA、Redux／IP-Adapter、身份保證及混合流程保持停用。後續需要指定作者／角色圖片時，提醒依 [圖片備註](docs/models/flux-extensions.md#下一輪圖片提醒)完成審查與保留圖確認。

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
