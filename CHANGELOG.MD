# Model Atelier — Changelog

## 2026-10-26 · E04 推論／訓練資源分開登記與 CP950 修復

E03 已先以 `3cce745` commit／push。新增唯讀訓練資源匯出器，核對原 manifest、最終完整步數、產物 receipt／hash 及程序／租約釋放，保留環境／資料／基底／完整 trainer arguments、實際 bucket、程式／日誌 hash；allocator、程序 RSS／Windows peak working set 與整卡取樣分開，未知保持 null。九筆 RTX 4080 推論獨立登記，不拿推論結果替代訓練。

修復搬移後獨立 trainer Python／editable 路徑並核對 lock、乾淨 sd-scripts 及離線 tokenizer。只用自製幾何 train／validation／test，各一張且只有 train 進 trainer；新增真正 1024 PNG fixture。RTX 4080 的 512／1024、UNet LoRA rank 4／batch 1／fp16 各完成 3 更新、最終完整狀態與 LoRA hash；worker elapsed 53.797／52.219 秒，Torch allocated 峰值約 5.21／5.81 GiB。兩次不同快取、僅三步，不能認列尺寸效能排行、最低容量或作者品質。

首次 512 run 因隔離 `-I` 忽略 `PYTHONIOENCODING`、CP950 無法列印 trainer 日文而失敗，保留原紀錄並確認釋放資源。最小回歸先重現同一字元失敗，再於 worker 起點明確將 stdout／stderr 設為 UTF-8；回歸及新 UUID 真實訓練成功。沒有修改固定上游、覆寫歷史 run 或批准作者圖；結束後恢復本機 ComfyUI，平台確認 CUDA 連線。

最終空閒狀態下 798 項後端（1 既有跳過）、格式／靜態／型別、前端建置與契約全部通過；本項明確使用 --skip-browser，E02 的 122 項 Chromium 基線沿用，本項沒有前端變更。先前與真實訓練並行的回歸因運算互斥拒絕模擬提交而失敗，保留該輸出並於租約釋放後重新完整驗證，未移除互斥機制。見 [資源與失敗紀錄](docs/validation/hardware-resources-20261026.md)、[JSON](docs/validation/hardware-resources-20261026.json)。ROADMAP 保留 10 主項／11 子項（21 框），E02 → E03 → E04 各自 commit／push。

<a id="e04"></a>

- [x] **E04 · 補齊推論與訓練各自的資源實測**
  - [x] 驗收 E04-01：保留硬體、環境、流程、模型與測量定義；新增工作負載及 RTX 4080 結果各自登記。
  - [x] 驗收 E04-02：訓練實測依 T01／T03 決策另建紀錄，不以推論量測替代；不可得欄位保持未知。

## 2026-10-26 · E03 相同條件比較與獨立較高負載

E02 已先以 `a74dfbe` commit／push。讀取 RTX 3060 原始 Pony 報告／成功 history，與 RTX 4080 新引擎程序第一次相同配置生成比較；固定權重完整 SHA256、模型／CLIP／VAE dtype、768²／20 步／精確 seed／batch 1／無附加元件及完整七節點圖均匹配。原 history 耗時 22.551／9.380 秒，單次比例 2.4042，保留 OS／驅動及背景負載差異；未回填舊任務量測、未把整卡取樣視為任務峰值。

RTX 4080 另完成 1536²／30 步／batch 1，原圖、完整 workflow／設定與版本還原通過；15.171 秒引擎耗時使用 baseline 後的模型快取，獨立保存，不混入冷載入對照。新增唯讀比較器，精度／快取／來源／hash 未知、設定或 workflow 不同時不提供時間比，訓練不混用。見 [紀錄](docs/validation/hardware-comparison-20261026.md)、[JSON](docs/validation/hardware-comparison-20261026.json)。

格式／靜態／Vue 型別與 38 項相關回歸通過；E02 完整 784 項後端及 122 項 Chromium 基線沿用。本項沒有修改前端或生成協調／背景取樣。ROADMAP 保留 11 主項／13 子項，E04 待本項 commit／push 後開始。

<a id="e03"></a>

- [x] **E03 · 兩台主機相同設定比較及 RTX 4080 較高負載驗收**
  - [x] 驗收 E03-01：先以相同模型、精度、尺寸、seed、步數、batch、附加元件及載入條件比較耗時與資源。
  - [x] 驗收 E03-02：另存 RTX 4080 較高負載結果，不把它當成 RTX 3060 門檻或宣稱所有 NVIDIA 顯卡皆相容。

## 2026-10-26 · E02 RTX 4080 搬移與基本流程驗收

修復搬移後平台／ComfyUI Python 3.12 環境的舊使用者路徑，前端重新安裝及建置。實機記錄 Windows 11、RTX 4080／16 GiB、約 64 GiB RAM、磁碟、617.42 驅動、Torch 2.14.0+cu130／CUDA 13.0 與固定 ComfyUI commit；新增可重跑的硬體快照及既有驗收器入口。

八個固定案例通過：Pony／Animagine 文生圖、有序雙 LoRA、圖生圖、一般／羽化修補、Canny、單張 adapter。每例確認原 UUID／成功 history、原圖 hash／完整 workflow／版本與精確 seed 還原；引擎離線後八份原報告全部 GET-only 核對通過。Chromium 1440px／390px 核對系統 GPU、原圖預覽及載入表單，沒有生成請求。Canny 因搬移後元件登記缺漏的預檢失敗保留，補登固定身分後新報告通過。

完整品質入口：784 項後端（1 既有跳過）、格式／靜態／型別／建置／契約及 122 項 Chromium 通過。幾何參考圖不代表作者品質，整卡觀察值不代表任務峰值；未測變體、較高負載及訓練另行登記。見 [實機紀錄](docs/validation/rtx4080-workflows-20261026.md)、[可解析證據](docs/validation/rtx4080-workflows-20261026.json)。ROADMAP 保留 12 主項／15 子項，E03 待本項 commit／push 後開始。

<a id="e02"></a>

- [x] **E02 · RTX 4080 主機基本功能與工作流程實測**
  - [x] 驗收 E02-01：在該機器記錄實際 GPU／VRAM／RAM／磁碟、驅動、PyTorch／CUDA／ComfyUI 版本。
  - [x] 驗收 E02-02：重跑 RTX 3060 已驗收的基本操作與相同工作流程，保存模型版本、設定、結果及失敗原因。

## 2026-10-25 · F04 獨立 Schnell LoRA 與原生圖生圖

F03 已先以 `6ac8bae` commit／push，才接續本項；其 [GitHub Actions](https://github.com/Zimkjdv/Model-Atelier/actions/runs/40166211208)亦已確認通過。新增兩個明確版本的 FLUX 流程、獨立草稿格式／revision、UUID 端點復原、元件與 LoRA 快照、原圖正規化／一次上傳／本機保存、完整作品還原及唯讀匯出；Vue 介面提供 LoRA／圖生圖子頁，保留舊純文生圖與未保存內容。

固定 PVC LoRA 全檔 SHA256 通過，RTX 3060／約 64 GiB RAM、512×512／4 步／主模型 FP8／CPU 編碼器完成四個 HTTP 實機案例：強度 0／0.7，及兩張自製幾何原圖。原生 LoRA 觀察到 304 個參數 patch，RGB 像素差異、四份作品／來源快照與引擎離線後 GET 核對通過，各只提交一次。未知／SDXL／Dev LoRA、Redux／IP-Adapter、LoRA＋原圖混用及未驗收配置不啟用；幾何圖重繪不認列動漫畫風或角色品質。作者圖片後續需先審查及確認獨立保留圖。

沿用原生節點與既有下載器，新增約 164 MiB 權重，未導入額外推論框架或開始訓練。模型卡宣告 Apache-2.0，但沒有獨立完整條款及全部資料權利鏈證明，manifest `terms_verified` 保持 false；M02 也保留。操作見 [F04](docs/models/flux-extensions.md)，[實機／介面證據](docs/validation/flux-extensions-20261025.md)。

本機完整 780 項後端測試（1 既有跳過）通過，另新增清理後資料庫保護回歸，含此項的 38 項相關測試（1 既有跳過）通過；格式／型別／建置／契約及 122 項 Chromium 通過，1,062 個 Markdown 本機連結有效。完成項移至本檔，ROADMAP 保留 13 主項／17 子項未完成。

<a id="f04"></a>

- [x] **F04 · FLUX LoRA 與參考圖能力逐項接入**
  - [x] 驗收 F04-01：以此架構可用的 LoRA 獨立驗證相容性、版本與工作流程。
  - [x] 驗收 F04-02：參考圖能力另立流程與實測；未知或未驗證能力保持停用，不沿用 SDXL 驗收。

## 2026-10-25 · F03 平台 FLUX 生成、保存、離線與失敗復原

固定四份權重完整 SHA256 通過後，使用獨立 loopback HTTP 引擎與全新 DATA／SQLite，RTX 3060／約 64 GiB RAM 完成 512×512／4 步／主模型 FP8 e4m3fn／CPU 編碼器的單次提交、作品保存、完整設定還原與停止引擎後的唯讀驗證。另實測損壞模型載入失敗、極小程序配額下實際 CUDA OOM、明確新 UUID 的快取重試，以及故意遺失回覆後查回原 UUID；五個案例各僅一次 `/prompt`。保留完整錯誤、工作流程、四元件及環境快照，未認列自然顯存門檻、其他配置或動漫品質。

新增驗收 CLI、只限獨立程序的故障測試及回歸；明確指定 ComfyUI database URL，避免其舊資料庫自動遷移，最終測試前後原資料庫 hash 相同。也依 F02 CI 的實際 traceback 修正 Windows 8.3／非正規 TEMP 路徑比較，保留逸出檢查。操作見 [F03](docs/models/flux-generation-acceptance.md)，[實測與限制](docs/validation/flux-generation-20261025.md)。

完整本機檢查：775 項後端（1 既有跳過）、格式／型別／建置／契約及 120 項 Chromium 通過；1,033 個 Markdown 本機連結無誤。ROADMAP 僅保留 14 主項／19 子項未完成，F04 接續獨立實作。

<a id="f03"></a>

- [x] **F03 · FLUX 載入、生成、結果保存及 OOM 實機驗收**
  - [x] 驗收 F03-01：固定模型／元件與完整參數，驗證載入、單次提交、作品保存、設定還原及離線讀取。
  - [x] 驗收 F03-02：驗證載入失敗與記憶體不足的原設定／錯誤保存及明確重試，未知回應不重送。

## 2026-10-25 · F02 實際精度／卸載、資源與元件條款

F01 已先以 `5076208` commit／push。新增固定原生節點量測工具、檔案標頭的混合 dtype 盤點、實際 cast／參數裝置觀察、有界 RSS／整卡取樣及程序 CUDA allocator 最高值。先核對完整權重 hash、引擎停止及運算租約，獨立 worker 明確使用 CPU 編碼器、FP8 主模型與 512×512／batch 1／4 步，失敗／逾時保留回執，只停止自己擁有的程序。

RTX 3060／約 64 GiB RAM 完成兩次原生案例，約 59／56 秒，輸出 PNG hash 相同；觀察到 FP8 權重由 CPU／CUDA 轉成 CUDA BF16，以及 CPU 常駐權重。程序 RSS 取樣最高約 36–37 GiB，整卡取樣最高約 11.4–11.6 GiB，不能承諾 32 GiB RAM、其他尺寸或最低硬體需求。條款清冊讀取 BFL／OpenAI／Google 一手全文與模型卡，CLIP／T5 的確切轉檔來源仍未證明，新增 M02 保留 false，不回填 F01 歷史側錄。見 [操作](docs/models/flux-runtime-observation.md)、[實測](docs/validation/flux-runtime-20261025.md)、[條款](docs/models/flux-component-licenses.md)。

770 項後端（1 既有跳過）、型別／建置／契約及全部 120 項 Chromium 分四批通過。另依實際 Windows CI 的 `net::ERR_NO_BUFFER_SPACE` 及 480 秒總截止，將完整入口改為每六份 spec 使用新程序／埠與獨立證據目錄，保留單案限制及零重試；[診斷與驗證](docs/validation/browser-batching-20261025.md)。平台 HTTP／作品保存／離線還原／OOM 仍留 F03，沒有作者圖訓練或品質認列。

<a id="f02"></a>

- [x] **F02 · 實際精度、卸載、資源與元件授權核對**
  - [x] 驗收 F02-01：逐一記錄主模型、VAE、CLIP-L、T5 的來源、條款及使用條件。
  - [x] 驗收 F02-02：實測實際精度、卸載與 GPU／RAM 需求；引擎旗標不是實際執行證據，不可得值保持未知。

## 2026-10-25 · F01 固定 FLUX 四元件來源與安裝

使用者完成官方 Hugging Face 存取及本機 CLI 登入後，固定 BFL 主模型／VAE、ComfyUI 範例編碼器四個來源 HEAD 均為 200。新增 `scripts.install_flux` 的整體來源／容量 check、有限續傳 install 與離線完整 verify；沿用共用下載器，固定 revision／bytes／SHA256、每磁碟區 2 GiB 預留、安裝鎖及不覆寫正式檔。憑證只從官方本機位置讀取，不寫進報告，CDN 與公開編碼器不收到 token。

本機實際下載四份共 29,521,303,916 bytes，各自完整 SHA256 通過並保存來源側錄。761 項後端（1 既有跳過）、格式／型別／建置／契約、三項模型庫桌面／窄版含 axe 檢查通過；最終 48 項安裝／預檢回歸（1 既有跳過）亦通過。本項沒有載入 GPU，不認列 F02／F03；授權待核對欄位保留。操作見 [F01](docs/models/flux-installation.md)、[實際證據](docs/validation/flux-installation-20261025.md)。另補上 [另一台 Windows 主機部署](docs/setup-and-operations.md#部署至另一台-windows主機)的資料搬移與環境重建步驟。

<a id="f01"></a>

- [x] **F01 · 固定 FLUX 權重的來源存取與本地安裝**
  - [x] 驗收 F01-01：先取得固定 BFL 主模型／VAE 的合法來源存取，再重新檢查動態磁碟容量及完整元件。
  - [x] 驗收 F01-02：依固定來源／修訂驗證大小與 SHA256；來源選型、預檢與專用表單完成不等於權重已安裝。

## 2026-10-25 · T08 訓練紀錄與診斷報告

T07 已先以 `e09fa3b` commit／push，才新增已登記原 run 的唯讀報告：固定參數／來源 hash、狀態／資源、resume 與產物回執，最多 1 MiB；預設排除圖片、caption、路徑、GPU UUID 與日誌，另選才附日誌尾段。下載保存預覽的原始 bytes，改選 run／資料範圍清除舊預覽，未知／損壞紀錄保留，不重送或重跑。

746 項完整後端（1 既有跳過）、格式／型別／建置／契約通過；本項採 8 項訓練相關 Chromium 回歸（含 axe 與 390px），不宣稱重跑整站瀏覽器。最後未知狀態保護另經 15 項相關後端及靜態檢查。原生平台只讀既有幾何圖 run，兩種寬度各 17,140 bytes 的下載與預覽 SHA 一致，零 API 寫入、原紀錄不變、沒有新訓練／生成。見 [操作](docs/training/workspace.md#t08-訓練報告)、[有限驗收](docs/validation/training-report-20261025.md)。

HTML 教學新增報告截圖與步驟。依使用者補充，另記錄 [FLUX／3060 官方資料與前置判斷](docs/models/flux-rtx3060-planning.md)：下一輪建議 F01 → F04，需量化／卸載或 4080 時先說明，GGUF 尚未整合／安裝，不認列固定權重或 GPU 驗收。

<a id="t08"></a>

- [x] **T08 · 訓練紀錄與診斷報告匯出**
  - [x] 驗收 T08-01：提供已登記原 run 的唯讀、有界報告與可下載 JSON，保存來源／設定／狀態／資源及產物關係，區分觀察與完整性驗證。
  - [x] 驗收 T08-02：明確預覽資料範圍與選擇性日誌，不讀原圖／權重、不啟動 worker／引擎、不自動重送；未知／損壞紀錄與容器邊界保留。

## 2026-10-25 · T07 訓練資料缺項搜尋與定位

T05 資料審查加入圖片 ID／檔名／群組搜尋、用途／已保存缺項篩選、跨頁定位與下一張阻擋缺項；完整問題分頁取代前 200 項截斷。資料集層級提醒獨立顯示，篩選與定位保留未保存標註，final test 仍不預覽。教學文字與截圖同步更新。

739 項後端（1 既有跳過）、格式／型別／建置與契約通過；完整 Chromium 117 項通過、1 項既有模型庫案例在最後唯讀 `/qa/state` 遇到 ECONNRESET，獨立重驗同案例通過。新增桌面／390px 操作及 axe 均通過，125 張自製圖核對 244 個缺項可完整定位，沒有作者圖審查／訓練或生成。見 [操作](docs/training/workspace.md#t07-缺項導覽)與[驗收](docs/validation/training-review-navigation-20261025.md)。

<a id="t07"></a>

- [x] **T07 · 訓練資料缺項篩選與圖片定位**
  - [x] 驗收 T07-01：依後端已保存檢查提供 ID／檔名／群組搜尋、用途／缺項篩選及完整分頁，保留資料集層級問題與未保存標註。
  - [x] 驗收 T07-02：跨頁定位／下一缺項不改標註或批准資料；桌面／390px、鍵盤及 final test 不預覽邊界通過。


## 2026-10-25 · 離線 HTML 圖文使用教學

新增 [圖文教學](docs/guide/index.html)，依操作目的說明啟動、生成、單張參考、T05 資料審查、T06 訓練／停止／續訓、產物比較與備份，包含五張真實介面截圖、流程圖、參數解釋與疑難排解。支援桌面／窄視窗、圖片放大、鍵盤操作與列印／另存 PDF，不依賴外部資源；圖片明確區分隔離示範與幾何圖技術驗收，未使用作者圖。README／文件索引新增入口，深入規格仍連回既有 Markdown。

## 2026-10-25 · T06 原生訓練控制與產物操作網頁

T05 已先以 `29715e7` commit／push，再接上 T03 的凍結準備、明確單次開始、停止、新 UUID 續訓與狀態／資源／日誌，以及 T04 校驗安裝、模型庫來源回登及固定比較。背景請求先落帳，未知結果只查原 UUID；啟動標記避免重送，容器／非 Windows／任意旗標不進 trainer。R02 study 隨來源封存，worker 無法建立時正確 failed 並釋放控制端身分。

RTX 3060 原生網頁實測自製幾何圖：原 run 保存至第 2 步後停止，從 step-1 建新 run，明確開始剩餘 5 更新並確認全程 step 6、程序／租約釋放、產物 hash／安裝、來源回登及六份方案保存；沒有生成比較圖或訓練作者圖。只啟停自己的驗收平台／引擎，原本離線的引擎狀態已恢復。另補 T05 候選圖不可在審查後轉為未曝光 final test，按既有主題統一操作按鈕。

739 項完整後端（1 既有跳過）、型別／建置／契約／靜態及 116 項 Chromium 通過；最後審查保護及 UI 整理另完成 44 項相關後端、4 項含 axe 的桌面／390px 回歸。Windows CI fixture 時間修正為 `7ed76e9`，本項包含其格式同步。見 [操作與中斷恢復](docs/training/workspace.md)、[有限實機驗收](docs/validation/training-control-20261025.md)。

<a id="t06"></a>

- [x] **T06 · 本機訓練執行介面**
  - [x] 驗收 T06-01：沿用 T03 的凍結設定、獨立環境與單次啟動，提供明確建立／開始／停止／新 UUID 續訓及原 run 查回。
  - [x] 驗收 T06-02：顯示狀態、資源釋放、環境／資料／產物來源及失敗；確認原生 GPU 協調與容器限制，以自製技術資料驗證，不自動訓練作者圖。

## 2026-10-25 · Windows CI 啟動測試時間修正

T05 的 Windows CI 在既有 delayed readiness 案例失敗；該案例僅有 1 秒重試預算，受 hosted runner 的 PowerShell 冷啟動／JIT 開銷影響。成功／瀏覽器錯誤案例改給 5 秒，持續不可用與無前端案例仍驗證 1 秒截止；仍核對只開啟一次及未就緒不開啟。失敗斷言納入 stdout，保留後續診斷資訊；正式啟動器及其 60 秒預設不變。本機兩項 Windows 啟動回歸通過。

## 2026-10-25 · T05 訓練圖片與標註審查網頁

使用者確認新增 T05 → T06。訓練工作區沿用 T02 清單與出口，提供逐張原圖預覽、caption／來源／角色審查、不可變修訂與下載、409 保留編輯、來源重驗及 train-only 封存。保留圖不能轉 train、曝光不可降級；最終評估圖不提供預覽，避免提前曝光。匯入／出口以原 UUID 查回，失敗不覆寫或自動重做；Q07 增加審查 hash 與已完成出口檔案關聯檢查。

隔離本機平台匯入兩份既有作者清單，22 個原檔 hash 不變，20／30 個缺項保持待審查；只有自製色塊完成審查與出口，沒有訓練或作者品質認列。730 項完整後端（1 既有跳過）、18 項最終審查／備份回歸、建置／契約／靜態檢查通過；完整 Chromium 113 項通過，另一項受並行輸出目錄清理影響，改用獨立目錄後與兩個新增含 axe 的案例共三項重跑通過。操作與證據見 [訓練工作區](docs/training/workspace.md)、[T05 驗收](docs/validation/training-review-20261025.md)。

<a id="t05"></a>

- [x] **T05 · 訓練圖片與標註審查介面**
  - [x] 驗收 T05-01：沿用 T02 清單、圖片身分與 R02 分割，提供原圖預覽、標註／來源／角色審查、不可變版本及修訂衝突保護。
  - [x] 驗收 T05-02：重驗來源、呈現缺項與補圖提醒；只匯出已審查 train 圖並保留原 UUID／失敗，不自動批准或開始訓練。

## 2026-10-25 · D02 選用 Docker 本機平台與持久化驗收

D01 已先以 `bd82a59` commit／push，再加入固定基底的多階段映像、非 root／唯讀平台、loopback Compose 與獨立 DATA／協調鎖卷。容器入口只適配明確 bridge peer，保留 Host／Origin 與原生入口的存取邊界；系統頁分開容器可見資訊與 Windows 引擎，原生安裝檢查明確標示需在 Windows 執行。

Windows Docker Desktop／WSL2 與 RTX 3060 完成實際 CUDA sample、選用 GPU observer、連原生 ComfyUI 生成一件固定案例，保存精確 seed／workflow／模型資訊。容器重建、使用中備份拒絕、停機備份／verify、新卷還原及引擎離線原作品查閱皆通過；正式 DATA／作者圖未使用。722 項後端（1 既有跳過）、型別／建置／契約與 112 項 Chromium 通過，最後 UI 提示另定向重跑兩項及建置／靜態檢查。見 [操作與原生差異](docs/docker.md)、[限定驗收](docs/validation/docker-deployment-20261025.md)。

<a id="d02"></a>

- [x] **D02 · Docker 部署評估**
  - [x] 驗收 D02-01：本機功能穩定後，驗證資料持久化、GPU 存取、主機硬體資訊來源及 ComfyUI 連線。
  - [x] 驗收 D02-02：記錄容器與宿主機差異及備份／恢復方式；Docker 不作本機使用前置需求。

  - 已驗收同機 Desktop／WSL2 平台容器；GPU 推論仍在原生引擎。沒有容器訓練、Windows DATA 跨 OS 遷移、遠端部署或跨 OS GPU 租約認列；原生 T03 訓練前須先停止容器平台。

## 2026-10-25 · D01 本機部署決策與存取保護

使用者確認維持同一台電腦使用。平台新增全域來源 IP／Host／完整 Origin 檢查，拒絕非 loopback、重複標頭、DNS rebinding 型 Host 與跨站 API 寫入；原啟動腳本停用 forwarded-header 信任。系統頁顯示本機模式，分開平台／引擎／儲存來源，失敗保留上次資料。沒有新增遠端帳號認證，本機使用者與程式仍視為可信。

718 項後端（1 既有跳過）、前端建置／契約及 108 項既有 Chromium 通過。新增兩項桌面／390px 案例最初誤把 mock-engine.invalid 預期為本機引擎，修正測試後兩項定向重跑通過；七項邊界測試及真正 loopback HTTP 隔離驗收通過。正式 DATA／GPU 工作未變更。操作與限制見 [部署說明](docs/deployment.md)、[驗收](docs/validation/local-deployment-20261025.md)。

<a id="d01"></a>

- [x] **D01 · 遠端 GPU／區網存取決策與連線保護**
  - [x] 驗收 D01-01：確認是否需要獨立 GPU 主機或區網存取；目前本機執行決策與此後續需求分開記錄。
  - [x] 驗收 D01-02：若開放存取，先驗證身分／連線保護及主機角色、硬體與儲存資訊來源。

  - D01-01：本輪使用者已明確選擇本機；D01-02 的遠端身分驗證條件未啟用，不宣稱通過遠端驗證。本機邊界及角色來源已實測，未來區網需求須另開規劃。

## 2026-10-25 · ROADMAP 已完成項目移入變更紀錄

ROADMAP 只保留 18 個未完成主項與 28 個待驗收子項；完整已完成敘述、驗收連結與圖片提醒移至 [歸檔](#roadmap-completed-20261025)。保留 V01 實機觸控待辦，僅移出已完成的 V01-01；修正原摘要表仍把 T03／T04 計為待辦的舊數字。項目狀態及既有品質限制不變，相關內部連結改指歸檔。

## 2026-10-25 · T04 訓練產物回登與固定評估

T03 已先以 `db7ab91` commit／push，再接入完整產物及最終狀態核對、不可覆寫安裝、來源 sidecar／SHA 與現有 LoRA 模型庫 API 回登。保留基底、資料／trigger、完整訓練設定、環境／trainer／續訓來源與權重識別，技術產物明確標示，不自動認列品質或產物條款。

建立三題材、兩個精確 seed、空 LoRA 基準／UNet 候選的 12 格比較，沿用六份原生方案與既有作品比較；封存來源 prompt／hash、先核對模型登記並提供人工審查模板。建立與保存方案不生成，保留原 request_id 查回；作者 caption／來源／角色審查與獨立最終保留圖提醒仍在文件。

T03 幾何技術 LoRA 在 RTX 3060 原生載入成功，候選有 UNet 722 patches、CLIP 0 patches；只生成兩件 512／4 steps 基準／候選，保存、精確 seed、完整設定與權重快照還原通過。暫停閒置引擎後，兩組原紀錄 GET 查回也通過且沒有重送，原引擎已恢復。使用隔離平台 DATA，作者圖未訓練、12 件畫風品質比較未執行。

最終 711 項後端（1 項既有跳過）、18 項產物／run 定向重跑與靜態檢查通過；前端程式未變更，沿用 T03 同次已通過的建置／契約及 108 Chromium。ROADMAP T04 流程完成，剩餘 18 主項／28 子項。見 [回登與比較操作](docs/training/artifacts.md)、[技術驗收與限制](docs/validation/training-artifacts-20261025.md)。

## 2026-10-25 · T03 獨立 SDXL 訓練環境與資源協調

固定 sd-scripts、Windows／Python 3.12／CUDA 13 的獨立訓練環境與離線 tokenizer，提供本機 CLI 的設定／資料／模型封存、明確啟動、停止及新 UUID 完整狀態續訓。訓練與本機生成共享跨程序 OS 租約；既有 UUID 查回先行，新 prompt 衝突拒絕且不自動重送，遠端引擎分開處理。

只用自製 512 幾何圖片進行 RTX 3060 技術驗收：在線引擎拒絕、保存後停止、資源釋放、從 step 1 完整恢復至 step 3。發現並保留上游續訓重設步數的失敗結果，整合層明確計算剩餘更新並核對最終 state；不修改固定上游 checkout。PyTorch 配置峰值約 5.2 GiB、程序 RAM 峰值約 20.9 GiB，不推論為 1024／RTX 4080／畫風品質需求。驗收後原 ComfyUI 恢復；作者圖片未訓練，仍需 T02 審查及最終保留集。

701 項後端（1 項既有跳過）、前端建置／契約與 108 項 Chromium 回歸通過；最終 19 項訓練／互斥測試另重跑。ROADMAP T03 完成，剩餘 19 主項／29 子項；T04 待 T03 commit、push 後才實作。操作及實測見 [訓練 runtime](docs/training/runtime.md)、[驗收與量測](docs/validation/training-runtime-20261025.md)。

## 2026-10-24 · 系統資訊目錄卡片與開啟資料夾

目錄與磁碟容量改為摘要、使用率與精簡目錄列，支援長路徑及窄視窗；每列新增資料夾圖示，可從 Windows 本機平台頁面開啟對應檔案總管目錄。未建立目錄停用按鈕，更新失敗保留舊快照；後端只開啟清單中的既有本機目錄，驗證來源與實際位置，不接受任意開啟路徑或自動建立目錄。操作及契約見 [目錄與磁碟容量](docs/storage-overview.md)。

31 項相關後端與 6 項瀏覽器／系統頁無障礙回歸、建置及靜態檢查通過；另在隔離平台由瀏覽器實際點擊，Windows 接受開啟要求。舊平台程序會提示重新啟動，測試版面與實機範圍見 [驗收紀錄](docs/validation/storage-overview-20261024.md)。

## 2026-10-24 · Windows 雙啟動批次修正與自動開頁

修正 `start-all.bat` 的 UTF-8 中文內容在真實 cmd.exe 被截斷，導致兩個啟動指令未執行的問題。批次訊息改為 ASCII、Git 固定 CRLF；PowerShell 加入 `-NoExit`，保留啟動錯誤供查看。真實批次入口在繁中／UTF-8 字碼頁、含空白路徑及缺少 PowerShell 分支通過回歸；平台與 ComfyUI 腳本也分別啟動並以 HTTP 驗證成功。操作與排錯見 [雙啟動捷徑](docs/setup-and-operations.md#雙啟動捷徑與錯誤視窗)。

雙啟動後等待平台健康檢查及首頁成功回應，再以預設瀏覽器開啟 `http://127.0.0.1:8000/`；約 60 秒未就緒或開頁失敗保留英文提示。新增延遲就緒、平台失敗、前端未就緒及開頁失敗的回歸，不等待 ComfyUI 載入。

## 2026-10-23 · GitHub Actions 暫存路徑別名回歸

修正 R02／T02 新增測試以未解析的 Windows TEMP 路徑比較既有長路徑輸出的問題；近期 CI 兩個失敗已在本機真實 8.3 別名環境重現。兩個預期值使用完整實體路徑，並加入既有短路徑子程序回歸；產品目錄與越界防護不變。15 項相關測試與格式／靜態檢查通過，詳見 [失敗來源與重跑方式](docs/validation/ci-path-alias-20261023.md)。

## 2026-10-23 · R03 Fooocus 專用修補與有限品質比較

R01 已先以 `855714d` commit／push，再接入獨立 Fooocus SDXL v3 模板與修補模型選項。固定 head／v2.6 patch、Acly 節點及 Animagine 4.0 Opt，限制 denoise 1、無 LoRA；保存專用模型來源與三份輸入、精確 seed、原 UUID 恢復及完整設定還原。一般 v1／v2 保留，專用參數不進一般草稿／交換／比較格式。

兩張動漫生成素材各比較 A0／A16／B16 與一般 v2 A16，共八件 RTX3060 結果。遮罩外像素差皆 0，引擎停止後八組僅 GET／hash 核對及 DATA 健全性通過。Fooocus 有矩形色塊、色偏、花紋／物件提示不符，未優於一般 v2，因此標示實驗選項並保持一般修補預設。第一次新版 COMBO 介面檢查失敗保留原紀錄，修正後使用新 UUID；沒有自動重送。

新增六項後端及兩項桌面／390px 瀏覽器回歸；675 後端（1 既有跳過）、建置／契約與 103 Chromium 通過；最終兩項預覽／原設定還原另重跑通過。見 [操作與限制](docs/fooocus-inpainting.md)、[逐圖證據](docs/validation/fooocus-inpainting-20261023.md)。ROADMAP 剩餘 20 主項／31 子項，T03／T04 仍另排，沒有啟動訓練。

## 2026-10-23 · R01 SDXL 姿勢／相對深度

依上游選型接入固定 controlnet_aux、DWPose／Depth Anything V2 Small 與兩種匹配 SDXL ControlNet，新增專用 v3 提交、結構類型選項、完整快照／精確還原、同次條件圖明確匯入與離線下載。保留 Canny v1／v2 及原 UUID 恢復，條件圖不匯入作品；完整備份／健全性核對涵蓋新目錄。

兩種 Animagine／RTX3060 固定案例均完成唯一生成、條件圖、唯一作品與重建平台後 GET 核對。人工保留骨架缺漏、姿勢偏離、衣著／背景變化與深度構圖分界，沒有訓練或角色一致性保證。669 後端測試（1 既有跳過）、前端建置／契約與 101 Chromium 通過；另有四項桌面／390px 遺失回應恢復測試，以及15項新流程／備份回歸。操作、固定來源與完整證據見 [R01](docs/structure-reference.md)。ROADMAP 剩餘 21 主項／33 子項，下一項 R03。

## 2026-10-23 · T02 資料契約與訓練工具介面

新增 v1 訓練清單／JSON Schema 與 CPU CLI：來源唯讀盤點、原作分組／固定分割／曝光、逐張 caption／來源用途／角色審查、版本 hash、只匯出 train 的不可覆寫資料包與獨立核對。固定 sd-scripts 候選資料 TOML，明確保留 tokenizer、獨立環境、VRAM、實際訓練及新 LoRA 載入待 T03／T04 實測；沒有安裝 trainer、啟動訓練或生成。

既有 22 檔／20 不同內容／19 群組各建畫風與角色清單，10 張候選、6 張開發評估、6 張排除。caption／來源用途及角色身分仍待審查，真實資料出口正確拒絕；三張合成圖片的 train-only 出口與核對通過。新增 33 測試，完整格式／靜態、663 後端（1 跳過）、Vue 建置／契約與 97 Chromium 通過；原圖與正式 DATA 八檔 hash 不變。

README／索引／圖片備註與 ROADMAP 同步，T02 及其子項完成，剩餘 22 主項／35 子項。需要圖片時的審查／補齊提醒已記錄；後續依指定順序 R01 → R03，T03／T04 另排。見 [契約與 CLI](docs/training/dataset-contract.md)、[官方工具介面](docs/training/tool-interface-research.md)、[T02 驗收](docs/validation/training-dataset-20261023.md)。

## 2026-10-23 · T01 訓練需求與驗收範圍

依使用者的作者畫風／棕髮綠眼角色目標與 R02 偏差，記錄分開的 SDXL UNet LoRA 候選，固定 Animagine 基底身分、用途／排除範圍、兩路徑各 12 件未來比較與四面向人工判準。明確區分推論調整、單張參考、資料整理及實際訓練，保留現有分組／曝光紀錄與必要補圖時點；沒有啟動訓練或新增 GPU 工作。

README／索引／開發計畫與 ROADMAP 同步；文件連結、23 主項／36 子項計數、基底 manifest 與題材／seed 一致性核對通過。T01 及其子項完成，下一項 T02 在本項推送後開始，之後維持 R01 → R03；T03／T04 另排。見 [需求 v1](docs/training/requirements.md)、[T01 驗收](docs/validation/training-requirements-20261023.md)。

## 2026-10-23 · R02 單張畫風／角色參考

新增固定 SDXL Plus ViT-H adapter／編碼器及逐檔核對的節點安裝，專用工作台提供畫風／角色模式、元件登記、224 方圖前處理、嚴格預檢、原 UUID pending 與完整原設定還原。一般草稿、交換與比較方案明確拒絕專用欄位，不丟棄來源、模式或元件；格式整理以 `7eb5918`／`11f6277` 獨立提交。

使用者提供 22 檔、20 個不同內容並確認棕髮綠眼角色；本輪沒有訓練，只選一張畫風圖及一張角色圖分別作單張推論，另留 6 張評估。12 組 RTX 3060 比較保存原圖、完整來源與四面向觀察；粉髮、服裝帶入、張傘、雙人與背景弱化保留，不宣稱作者畫風或身份完全重現。

停引擎、改登記與重啟平台後 12 報告只 GET，1440px／390px 下載／精確還原與完整 630 後端（1 跳過）、Vue 建置／契約及 97 Chromium 通過；正式 DATA 八檔 hash 與 22 張原圖均不變。R02 與兩子項關閉的是接入及有限品質比較，剩餘 24 主項／37 子項。後續依使用者指定 **T01 → T02 → R01 → R03**，不自動開始 T03 訓練。見 [R02 驗收](docs/validation/reference-adapter-20261023.md)、[圖片用途與未訓練備註](docs/validation/reference-inputs-20261023.md)。

## 2026-10-23 · L01 更多畫風、順序、強度與 seed

新增固定像素畫 LoRA 來源，查出原檔在 ComfyUI 0.34.0 的 1120 個鍵未載入，四組出圖保留為格式失敗證據。新增只改 header 鍵名的固定來源轉換，原 tensor payload／原檔保留，另建有獨立版本／hash／provenance 的排他相容副本。原生工具在 Animagine 完成 14 組單／雙／三 LoRA、正反順序、兩種強度／seed 及兩題材，保存原圖和四面向觀察；沒有新增通用品質預設。

六筆多 LoRA 條件追加至歷史 registry，原三筆低對比紀錄完整保留；LCM 模糊、造型偏移、裁切及無 CLIP 張量等限制分開記錄。14 份報告停引擎／平台重啟後僅 GET 核對，正式 DATA 八檔 hash 不變；格式／靜態、615 後端（1 跳過）、Vue 建置／契約及 93 Chromium 通過。安裝器先以 `2107d14` 獨立格式整理，AST 一致且 27 項既有回歸通過（1 跳過）。L01 及兩子項完成，剩餘 25 主項／39 子項；指定作者／使用者角色品質與 M01 保留。見 [L01 驗收](docs/validation/style-matrix-20261023.md)。

## 2026-10-23 · R05 動漫基準與提示詞比較

新增獨立動漫 v1 三案例、UI／API 測試集選取、正／反向完整提示詞比較與單組驗收 CLI；保留通用 v1 bytes／hash、舊方案及精確 seed，新文字軸沿 schema 2 保存模型登記快照。兩模型／三題材／兩 seed 與品質標籤完成 14 件文字生成，兩種自產素材各比較 denoise 0.3／0.6 共 4 件，保存原圖、完整設定／版本／hash 及四面向觀察。

雙人、開書、裁切、跨場景身份變動及高 denoise 臉／手扭曲均保留，不建立全面品質推薦；指定作者／使用者角色品質仍待圖片。18 份報告停引擎及平台重啟後僅 GET 核對，正式 DATA 八檔 hash 不變。格式／靜態、605 項後端（1 既有跳過）、Vue 建置／契約與 91 項 Chromium 通過。R05 關閉範圍為本輪有限比較與限制紀錄，剩餘 26 主項／41 子項；見 [R05 驗收](docs/validation/anime-baseline-20261023.md)。

## 2026-10-23 · R04 Pony Canny v2 與其他 LoRA 實機驗收

RTX 3060 完成無 LoRA、IKEA、LCM、LCM → IKEA 與反向五個獨立 UUID，固定原素材、控制權重、seed 及各組取樣條件；全檔驗證權重，保存同次原邊緣、唯一作品、完整 workflow 與有序版本／強度。新增單次驗收 CLI、可重跑來源 PNG 及精簡證據 JSON，已有報告拒絕重跑，離線驗證僅 GET。

五組整合／保存還原通過，材質與畫風仍有中空、平面線框等偏差，不建立品質預設。1440px／390px 實際下載與還原、引擎離線／改登記／平台重啟核對通過，生成總數仍為五；正式 DATA 八檔 hash 不變。本機完整品質入口通過格式／靜態、599 項後端（1 項既有權限跳過）、Vue 建置／四組契約及 89 項瀏覽器。R04 與兩子項完成，剩餘 27 主項／43 子項；M01 與 V01-02 保留。來源、量測、人工觀察與重跑見 [R04 驗收](docs/validation/pony-canny-v2-20261023.md)。


## 2026-10-23 · R06 模型與取樣參數比較軸

新增 checkpoint、sampler_name、scheduler 三軸，涵蓋文生圖及單張圖生圖；單一變因最多 8 組、逐組手動載入與生成。schema 2 保存模型登記來源／版本／hash 與完整基準，交易內核對模型身分，變更登記須建立新方案；原 UUID 恢復不重送。原 schema 1、精確 seed、有序 LoRA 及圖片輸入保留，未知不補成已驗證。

9 項新增後端整合及 1440px／390px 瀏覽器驗收涵蓋保存、實際下載／檔案匯入、載入、一次明確生成及任務／作品／報告追溯；另修正 schema 2 跨 Python／瀏覽器整數浮點表示的 hash 一致性。相關模組先以 `ab41b8a` 獨立格式提交。R06 與兩子項完成，剩餘 28 主項／45 子項；能力邊界與證據見 [R06 驗收](docs/validation/extended-comparisons-20261023.md)。


## 2026-10-23 · R07 專用格式評估與資料遺失保護

完成局部編輯／羽化／Canny v1、v2 的專用草稿、設定交換與比較方案評估，新增唯讀版本別能力 API 及工作台支援說明。決策維持三項操作未支援，須完整保存雙輸入、羽化／控制參數、來源及版本後才能啟用；完整原設定載入與 workflow 下載保留，未借用一般 schema 丟棄資訊。

修正一般草稿曾回傳 201 卻默默捨棄遮罩參數的問題：POST／PUT、一般交換與比較明確拒絕專用設定，不部分寫入；保留既有回讀／複製生成 body 的有限封套相容，封套不選擇草稿或任務 UUID。新增 5 項後端整合及 5 項瀏覽器案例，四版本原設定、完整 workflow 與精確 seed 保留。core_api／settings_transfer／experiment_plans 先以 `80abccc` 獨立格式提交，Python AST 與 23 項既有回歸一致。R07 與兩子項完成，剩餘 29 主項／47 子項；M01 授權適用仍待釐清，V01-02 實機觸控保留。方案、拒絕與驗收範圍見 [R07 文件](docs/specialized-workflow-formats.md)。

完整品質入口通過格式／靜態、585 項後端（1 項既有權限跳過）、Vue 建置／四組契約及 87 項瀏覽器；檢視兩工作台 1440px／390px 截圖可讀。未新增 GPU 生成或實體觸控驗收。

## 2026-10-23 · M01 固定權重的授權來源查核

補齊 Pony manifest 的固定模型卡、39 bytes／SHA256、發布檔案清單、標準完整條文與參考 hash、現有 workflow 依賴及未提供的上游元件版本。查出相同權重 SHA256 的 Civitai 發布頁列出修改版 Fair AI Public License 1.0-SD 與變現推論限制，與固定 Hugging Face 的 OpenRAIL-M 標記不同；`terms_verified=false`，不替發布者解決適用條款，也不改舊 provenance／作品快照。

69 項既有安裝、模型登記／預設與生成驗收回歸通過（1 項既有權限跳過）；未下載／重寫權重或生成。查核結果、完整官方參考與限制見 [M01 文件](docs/models/pony-v6-xl-license.md)。來源差異及依賴授權鏈未核實，M01 與 M01-01 保持未完成，未完成數維持 30 主項／49 子項。

## 2026-10-23 · E05 連續資源取樣與峰值歸屬評估

新任務開始提交後，由平台背景查詢凍結的原引擎 `/system_stats`，每輪至少 2 秒、最多 16 項／每項 1 小時或 1800 次，保留最近 120 個時間點及全期觀察最高值。journal 不改 job revision，終態交易凍結、延遲回應丟棄，作品與離線閱讀沿用；舊資料不回填。裝置 total−free 含引擎可回收快取語意，與 nvidia-smi 整卡用量不同，任務專用峰值固定未知。

RTX 3060／Animagine 實際一個 UUID 取得 22 次成功觀察；保存作品、停引擎後凍結及 1440px／390px UI 核對通過。新增 6 項後端及 2 項瀏覽器回歸，另調整診斷唯讀斷言，區分獨立取樣投影；多筆取樣使用 group 避免重複地標。完整品質入口通過格式／靜態、580 項後端（1 項既有權限跳過）、Vue 建置／四組契約及 82 項瀏覽器。量測模組先以 `55e2cb2` 獨立格式提交，AST／Vue／TypeScript 語意一致。E05 及兩子項完成，剩餘 30 主項／49 子項；實際數值、重跑與限制見 [E05 驗收](docs/validation/resource-sampling-20261023.md)。

## 2026-10-23 · V06 全站視覺與無障礙補驗

新增 21 項瀏覽器回歸，逐頁覆蓋六主頁／四流程的九個入口在 1440px／390px 的標籤、鍵盤、焦點、對比、非顏色狀態與展開內容；另驗證硬體／離線／舊資料、四類模型編輯、作品收藏與對話框、素材空白／讀取／錯誤、診斷 JSON 及圖生圖／遮罩。鎖定 axe Playwright 4.14.0，保存 violations 與 incomplete、逐頁截圖與漸層端點對比；不以零自動錯誤宣稱完整 WCAG 認證或實體讀屏通過。

修正側欄／GPU 標記／畫布說明文字對比、收藏 0／1 的 ARIA 值、Checkpoint 標題層級、窄版品牌名稱、素材分頁語意及 FLUX 表格／診斷預覽焦點。CreationStudio／theme 先以 `6b17b17` 獨立格式提交並核對編譯語意，再加入修正與明確品質 scope。完整品質入口通過格式／靜態、574 項後端（1 項既有權限跳過）、Vue 建置／四組契約及 80 項瀏覽器。瀏覽器總預算調為八分鐘，單案 45 秒與零重試維持；V06 與兩子項完成，剩餘 31 主項／51 子項。V01-02 實機觸控保留，未生成圖片或修改正式資料；逐頁矩陣、證據與限制見 [V06 驗收](docs/validation/ui-accessibility-20261023.md)。

## 2026-10-23 · V05 創作設定下載、匯入與窄視窗補驗

新增十二項 1440px／390px 瀏覽器回歸，實際下載 checkpoint、圖生圖、FLUX 與作品來源設定，保存檔案並比對 API 原 bytes／檔名、精確 seed 及 workflow 大整數字串；檔案選擇器與真正剪貼簿貼上皆先預覽、可取消，明確套用及保存才建立新草稿，原草稿不變。另覆蓋過期驗證、保存中停用、跨流程／非法文件及原引擎／素材提示。

修正過大新檔失敗後仍留下舊候選、File.text 非嚴格 UTF-8 解碼，以及讀取中的操作／過期回覆保護。元件先以 `36f4e99` 獨立格式提交並核對 script／模板／CSS 語意，再加入修正及明確品質 scope；示範作品 fixture 改用完整正式 workflow builder。格式／靜態、574 項後端（1 項既有權限跳過）、Vue 建置／四組契約與 59 項瀏覽器通過，沒有新 GPU 推論或正式資料變更。V05 與兩子項完成，剩餘 32 主項／53 子項；證據與限制見 [V05 驗收](docs/validation/settings-transfer-20261023.md)。

## 2026-10-23 · V04 比較與量測介面補驗

新增八項 1440px／390px 瀏覽器回歸，核對正反 8 步多 LoRA 歷史條件與品質限制、指定 LoRA model／CLIP 強度軸及錯誤、兩個 checkpoint 的固定四案例逐組載入，以及任務／作品的原量測來源、零與未知值。隔離 fixture 使用固定 manifest 登記與合成圖片，驗收後還原登記及移除本組紀錄，避免影響其他回歸。

另從既有 GPU 報告建立唯讀離線副本，核對 11 件原作品、兩種寬度共八次四案例跨模型並排與 22 次原設定還原；原資料庫／原圖／workflow 不變，真實量測 UI 顯示平台 27.311／引擎 26.029 秒，舊紀錄保持未知。未新增生成、品質預設或產品 API，未回填舊方案關聯。完整品質入口通過格式／靜態、574 項後端（1 項既有權限跳過）、Vue 建置／四組契約與 47 項瀏覽器。V04 及四子項完成，剩餘 33 主項／55 子項；證據及限制見 [V04 驗收](docs/validation/comparison-measurements-20261023.md)。

## 2026-10-23 · V03 作品整理、並排與人工評分窄視窗補驗

新增五項 390 × 844 瀏覽器回歸，實際操作作品庫的搜尋／收藏／筆記／封存還原、未保存保護、雙分頁筆記與評分 409、明確重新讀取、保存中與 503 不重送。原圖並排核對完整 PNG／workflow bytes、相鄰最大 64 位 seed、參數差異及有序 LoRA／強度，涵蓋四件選取上限、跨篩選保留及清空。

修正無結果篩選誤提示先生成、預覽保存按鈕在清單讀取期間可點卻無回應，以及比較區缺少鍵盤焦點；兩個 Vue 模組先以 `940dab1` 獨立格式提交，再加入修正與明確品質 scope。完整品質入口通過格式／靜態、574 項後端（1 項既有權限跳過）、Vue 建置／四組契約及 39 項瀏覽器。臨時合成作品不提供 GPU／觸控或影像品質結論；V03 及兩子項完成，剩餘 34 主項／59 子項，V01 實機觸控仍保留。重跑及證據見 [V03 驗收](docs/validation/artwork-library-20261023.md)。

## 2026-10-23 · V02 v1／v2 原提交恢復瀏覽器補驗

加入 v1／v2 × 1440px／390px × 引擎回覆遺失／平台異常 JSON 的 8 項真實瀏覽器案例，以及未知版本保護；核對重新載入後原 pending、UUID／端點／body bytes、精確 seed、雙素材與原羽化輸入。原 v1 不被新表單升為 v2，v2 保留原半徑；手動恢復只返回原 UUID 帳本，引擎仍僅一次提交且不重傳圖片。

修正成功 JSON 或明確錯誤含其他任務 ID 時誤清除 pending；六種生成端點均加入缺失／其他 id、異常 JSON 與錯誤 job_id 契約。fixture 先以 `98b8964` 獨立格式提交並比對 AST，再加入精確節點、multipart 回執及有界呼叫紀錄。574 項後端（1 項既有權限跳過）、建置／四組前端契約與 34 項瀏覽器通過；原請求、任務 JSON、呼叫／輸入雜湊與畫面見 [V02 驗收](docs/validation/inpaint-recovery-20261023.md)。V02 完成，剩餘 35 主項／61 子項，V01 實機觸控仍待驗收。

## 2026-10-23 · V01 遮罩瀏覽器補驗與筆畫保留

修正同素材清單重讀／切頁返回清空未保存畫布、取消更換原圖／遮罩後選單值未復原，以及非 PNG 冒充遮罩被載入。指標停用、取消與工具操作會結束筆畫，限制主指標；狀態區分未選原圖、載入與保存。格式整理先獨立提交 `875496e`，再加入操作修正與 6 項瀏覽器回歸。

1440px／390px 完成筆刷、擦除、反相、PNG 選檔／保存與未保存保護；保存後從素材 API 解碼及重新整理後重選的 RGBA 雜湊一致。574 項後端（1 項既有權限跳過）、建置／四組前端契約與 25 項瀏覽器回歸通過。使用者確認目前沒有實體觸控裝置；模擬第二指／取消不能視為實機通過，僅關閉 V01-01，V01-02 與主項保留。證據見 [V01 驗收](docs/validation/mask-editor-20261023.md)，剩餘 36 主項／63 子項。

## 2026-10-23 · Q10 高風險流程格式、靜態檢查與維護規則

Ruff／Prettier／CSS-tree 精確鎖版，16 檔明確 scope 的格式／少量靜態檢查接入 Q06 與 CI；runtime 安裝與品質 dev lock 分開。格式整理獨立提交 `c465726`，Python AST、TypeScript／Vue 編譯結果及 CSS 內容相同，第二次格式零差異；未全庫格式化。靜態錯誤探針與五階段 fail-fast 通過，npm ci／pip check 通過，npm audit 為 0。

後續重構以具名函式區分凍結保存、原版本端點、確認清除、既有請求核對與活躍提交保護。四流程實際元件驗證保存失敗不 POST、處理中不重送、未知回覆保留原 UUID／精確 seed、已修改／blocked 表單不影響恢復、明確 409 才清除；各 workflow 驗證與公開資料格式不變。完整品質入口 574 項後端（1 項既有權限跳過）、建置／四組契約與 19 項瀏覽器通過。規則、操作邊界與證據見 [維護指南](docs/maintenance.md)、[Q10 驗收](docs/validation/maintenance-20261023.md)。Q01–Q10 完成，剩餘 36 主項／64 子項。

## 2026-10-23 · Q07 備份檔案上限邊界

收尾檢視修正 manifest 額外占用驗證檔案數的邊界，並在建立目的地前檢查 DATA／外置 DB／證據的總檔案數。以縮小上限的隔離測試驗證剛好達上限仍能備份→驗證→還原，加入證據超量則拒絕且不建立目的地；9 項備份回歸通過。

## 2026-10-23 · Q09 請求／任務追蹤與可預覽診斷

加入每 app 的限量記憶體診斷，串聯平台 request ID、原 job UUID、流程、API／引擎階段、耗時與固定錯誤分類。恢復原提交與新增提交分開，過期觀察記錄被拒絕的狀態及保留終態；作品讀取／筆記衝突亦關聯原任務。狀態分開呈現平台、資料與引擎，沿用原 health 契約。

設定頁提供 UUID 篩選、唯讀狀態檢查、預覽後下載相同 JSON。最多 500 筆／256 KiB／24 小時，重啟清空，預設排除提示詞、圖片、完整 workflow、憑證、模型名及個人路徑。573 項後端（1 項既有權限跳過）、前端建置／四組契約與 19 項瀏覽器通過，後續 28 項針對追蹤／作品關聯的回歸亦通過。離線、遺失回應、409、提交後磁碟錯誤、過期觀察、隱私／保留與 1440px／390px 下載驗證見 [診斷說明](docs/diagnostics.md)。剩餘 37 主項／66 子項。

## 2026-10-23 · Q08 網址導覽、首次使用與能力層級

頁面、四種流程及作品匯入任務使用可還原 hash URL；返回／前進、錯誤網址、焦點、目前導覽與作品筆記取消離頁一致。保留 KeepAlive 與 Q05 保護，開啟網址不自動提交。新增連線→選模型→創作指引，生成區區分處理中、缺條件、表單預檢可提交及原提交待確認，實機／未知能力另行明示。

566 項後端（1 項既有權限跳過）、前端建置／四組契約與 17 項隔離瀏覽器回歸通過；1440px／390px 完成模擬生成、原任務匯入與引擎離線預覽。檢視兩種寬度截圖，未拆包或宣稱 V06 全站驗收，大小比較與操作見 [導覽說明](docs/navigation.md)。剩餘 38 主項／68 子項。

## 2026-10-23 · Q07 Windows CLI 編碼相容

遠端 Windows CI 的非 Unicode 終端無法輸出中文錯誤，改以標準 JSON Unicode escape 輸出；JSON 解碼後內容不變。子程序回歸強制 ASCII stdout，驗證忙碌拒絕及完整 check→backup→verify→restore 都能輸出有效 JSON。修正不改備份格式或資料內容。

## 2026-10-23 · Q07 完整停機備份與離線還原

加入唯讀 check、backup、verify、restore 與明確指定 DATA 啟動入口。全 DATA、外置 DB 與選定證據使用逐檔 SHA256 manifest；程序鎖、SQLite 排他交易與複製前後盤點拒絕不一致快照。只寫入新目錄，失敗保留 incomplete，既有資料不覆寫、不修復、不重新生成；權重與引擎資料另備份。

隔離 CLI 與離線 API 還原核對任務／作品、精確 seed、來源／遮罩／羽化遮罩與 Canny 邊緣，並覆蓋忙碌、損壞／缺檔、壞紀錄、路徑穿越、空間不足與中途來源變動。完整品質入口：566 項後端（1 項既有權限跳過）、前端建置／四組契約、9 項瀏覽器通過。操作、切換及限制見 [完整備份工具](docs/data-backup.md)。剩餘 39 主項／70 子項。

## 2026-10-22 · Q04 摘要分頁、跨頁比較與資料成長基準

作品、任務及素材提供預設 40／上限 100 的 library API，固定本次查詢成員、穩定排序、後端搜尋與組合篩選，詳情及比較快照按需讀取。介面支援上下頁、較早任務、跨頁比較與素材選取保留；原陣列 API 相容保留。沒有 schema／歷史 JSON 遷移，快取有限且過期明示。

同機 100／1,000／10,000 合成資料的 API／回應 bytes／Python 峰值／RSS／UI 指標通過預算；10,000 作品首批約 565 ms、19.3 KB、Python 峰值 1.6 MB，後續約 21 ms，UI 可搜尋約 1.8 秒；舊 UI 首卡等待逾時如實保留。完整品質入口、558 項後端（1 項既有權限跳過）、9 項瀏覽器及新增的分頁／舊 JSON 不變回歸通過，量測限制與回退見 [說明](docs/list-pagination.md)。剩餘 40 主項／72 子項。

## 2026-10-22 · Q06 Windows CI 長／短路徑相容

遠端 runner 的 8.3 TEMP 別名使三個路徑斷言與一個故障注入比較未命中。以子程序短路徑重現四項失敗，正規化測試預期／注入目標後，42 項相關測試通過；新增別名回歸，不放寬產品目錄邊界。此修正獨立於 Q04，見 [診斷與證據](docs/validation/quality-windows-paths-20261022.md)。

## 2026-10-22 · Q06 可重跑品質入口與瀏覽器 CI

加入 fail-fast 品質入口，串接後端、前端建置／四組契約及 8 項 Playwright 瀏覽器回歸。fixture 使用全新臨時資料與 MockTransport，涵蓋原請求恢復、409、真實 workflow 下載、鍵盤焦點與 390px 操作；CI 以 lock 安裝並保存失敗畫面／錄影／trace。全新隔離 venv 與 npm ci 的完整驗證通過（後端 550 項，1 項既有權限跳過）；失敗注入確認非零退出及證據。相容修補 Vite／source-map-js 後 npm audit 為 0；TestClient 棄用與故障注入警告明示保留，不宣稱 GPU／全站 UI 驗收完成。詳見 [品質指南](docs/quality-checks.md)。剩餘 41 主項／74 子項。

## 2026-10-22 · Q05 四工作台未保存內容保護

共用離頁監聽與保存狀態提示，涵蓋 KeepAlive 隱藏表單、草稿保存中與筆刷／遮罩保存；FLUX 載入原設定保持未保存狀態。未提供新的專用草稿格式，生成不會清除 dirty，離開也不提交任務。前端建置、四組檢查及隔離 Chrome 四流程驗證通過，模擬引擎生成呼叫為 0；行動瀏覽器限制與操作證據見 [說明](docs/unsaved-changes.md)。剩餘 42 主項／76 子項。

## 2026-10-22 · Q03 前端 HTTP 契約與可取消載入

App、四工作台、作品庫與 GenerationPanel 採用共用 HTTP／ApiError，解析字串、結構化與欄位陣列錯誤；HTML／異常 JSON、連線與取消分開處理。共用 request scope 統一取代／離頁／卸載失效；設定與方案交換使用原文字路徑，原始 workflow／圖片／報告 bytes 驗證保留。

submitOnce 僅執行一次凍結請求；只有可確認回覆才清除 pending，傳輸失敗／異常回覆保留原 UUID／body／端點。check:api 直接執行實際 Vue SFC setup／KeepAlive、四流程 GenerationPanel、作品 409 筆記保留，以及六種新舊端點／seed／LoRA／不重試檢查。型別／建置、check:api 與既有三組檢查通過；隔離真實瀏覽器的 422、四流程切換與未知生成狀態通過，模擬引擎提交一次，服務已停止。未重新進行 GPU 出圖或全站無障礙驗收。Q03 及兩子項完成，剩餘 43 主項／78 子項；詳見 [契約與驗證](docs/frontend-api.md)。

## 2026-10-22 · Q02 明確配置與應用程式工廠

新增 create_app 與每 app 的 AppContext，將目錄／SQLite 初始化移至 lifespan；主入口保留 backend.main:app。純請求型別移至 schemas，核心端點移至 core_api，其餘功能逐個以 context 組裝，不再傳入整個 main 模組。引擎 HTTP 可注入，現有 timeout／來源綁定與重送保護保留。

既有 API 測試改用工廠與自身臨時資料／context，不再 patch main 全域路徑。新增雙 app 同時運作、匯入不建立資料、重開舊資料不改寫測試；548 項後端回歸（547 通過、1 項既有 symlink 權限跳過）、編譯與文件連結檢查通過。無 schema／資料遷移，配置及回退見 [說明](docs/application-factory.md)。Q02 及兩子項完成，剩餘 44 主項／80 子項。

## 2026-10-22 · Q01 文件入口與現況一致性

README 收斂為安裝、首次生成、現有功能／限制與日常操作入口；新增操作指南、文件索引、架構／任務狀態／資料流說明。整理前 README 全文保存於 [歷史快照](docs/history/readme-before-q01-20261022.md)，僅調整相對連結並明示舊限制不是現況，歷史測試與硬體證據沒有刪除。

依當前腳本／端點核對啟動、固定來源、離線、備份與恢復說明；5 份入口／歷史文件共 130 個本地連結及錨點有效，固定 Animagine 唯讀預檢通過。沒有重新安裝全部依賴或產生 GPU 任務；ComfyUI 非完整 lock 與硬體條件明確記錄。Q01 及兩子項完成，剩餘 45 主項／82 子項。

## 2026-10-22 · 歸檔後新增：E01 執行裝置回報與提交保護

在 ComfyUI 程序內加入專案維護的唯讀裝置回報，以目前設定的裝置選取與明確的後端可用性結果為依據；nonce、版本、來源與格式不符時保持未知。標準／直接 workflow、圖生圖、局部編輯 v1／v2、Canny v1／v2 與 FLUX 在新任務取得明確不可用證據時，於上傳／提交前保存失敗，原 UUID 不重探測或重送。CPU 模式、草稿保存、離線作品與 CPU 預覽保留可用；系統資訊及任務／作品快照顯示回報來源。

545 項後端測試（544 通過、1 項既有 symlink 權限跳過）、前端型別／建置與三組邏輯檢查通過。隔離真實 ComfyUI CPU 模式、實際 aiohttp 路由故障注入、API 整合及瀏覽器三態顯示驗證完成；沒有停用或破壞真實 GPU／驅動。E01 主項及兩個驗收子項已關閉；剩餘 46 主項／84 子項。詳見 [操作說明](docs/execution-device.md)與 [驗收紀錄](docs/validation/execution-device-20261022.md)。以下歷史歸檔維持原始時點的敘述與數量。

---

本檔歸檔開發清單的全部可取得 Git 歷史，包含功能項、未勾選提醒、驗收、測試數、限制、決策及更名紀錄；目前未完成工作與驗收集中在 [ROADMAP.MD](ROADMAP.MD)。

歸檔建立日期：2026-10-22。來源範圍為 `origin/main` 從首次提交至 [17440f4](https://github.com/Zimkjdv/Model-Atelier/commit/17440f47e2a3f263fa4e3d28399cbb4312c7f571)；已與遠端同步核對。

| 稽核範圍 | 結果 |
| --- | --- |
| Git commits | 83，包含 2 個未改動開發清單的提交 |
| 不同清單內容版本 | 81；逐 commit 檢查舊名 `平台開發清單.md` 與現名 `ROADMAP.MD` |
| 時間範圍 | 2026-09-06 17:12:03 → 2026-10-22 20:29:42（Asia/Taipei，UTC+08:00） |
| 最新來源核取框 | 422：383 已勾選、39 未勾選（主清單 26、歷史提醒 13） |
| 歷史未勾選原文 | 151 種不同文字；逐項列出後續完成證據或現行待辦去向 |
| 從已勾選／敘述補回的待驗收 | 13 條來源敘述，對應現行明確驗收子項 |
| 整理後現行待辦 | 37 個主項、66 個驗收子項；去重與拆分後重新計數 |

日期以 **Git committer time 換算台北時間，從舊到新排列**；來源段落中的日期、字詞及當時判斷原樣保留。若原段落自填日期與提交日不同，以提交日決定歸檔位置，不改寫原文。

歷史 `[ ]` 不會因歸檔被一律改成 `[x]`。同一項後來完成、拆分或改寫，由索引說明；尚缺的部分留在 ROADMAP。已勾選行內的「待驗收」也會保留。歷史測試數、磁碟／服務狀態及工具故障只代表當次紀錄，不代表目前狀態。

每個提交節點附固定 commit／blob 來源、核取框統計及完整文字變更。第一版保留全文，後續保留可逐行還原的 unified diff（零行上下文，包含刪除、勾選變更、驗收及非核取框文字）；最新一版另附完整閱讀快照。沒有改清單的提交也列入，避免只追蹤清單變更而漏掉修正提交。

本次只整理文件，未執行生成、模型下載、GPU 驗收或程式修改；以下測試結果均為來源提交當時的歷史結果。

- [按日期排列的完整版本與驗收歷史](#history)
- [最後來源完整閱讀版（含完成項與驗收）](#latest-snapshot)
- [歷史未勾選項去向](#unchecked-index)
- [原 39 個未勾選框對照](#current-open-map)
- [已勾選文字中的待驗收回收](#acceptance-recovery)

後續完成工作時，將主項 ID、完成日期、來源 commit 及驗收證據追加至本檔，同步更新去向索引，再從 ROADMAP 移除已完成項並重新統計；部分完成時保留仍缺的驗收框。

<a id="unchecked-index"></a>

## 歷史未勾選項去向

H001–H151 依首次出現順序編號，文字相同者合併索引；所有重複出現與標記變動仍保留於下方逐版歷史。「已交付」只指該原文所述範圍；有現行待辦連結的行仍有未完成或延伸驗收。

| 編號／首次日期 | 歷史未勾選原文 | 後續證據與目前去向 |
| --- | --- | --- |
| <a id="h001"></a>H001<br>2026-09-06 [cd1d1af](https://github.com/Zimkjdv/Model-Atelier/commit/cd1d1af3aa94ad5b8cd6990a61735acab4b87dff) | 真實 ComfyUI 連線、工作流程提交與生成結果保存尚待實作／驗證；目前導覽中的創作、模型與作品頁為待開發頁面。 | 已交付，見 [7541feb](https://github.com/Zimkjdv/Model-Atelier/commit/7541feb57d69550c6e35c05bdab6efe1cab8ee1e)、[c651cfa](https://github.com/Zimkjdv/Model-Atelier/commit/c651cfa543d490ba61ef0c25234877c011471c96)、[631834d](https://github.com/Zimkjdv/Model-Atelier/commit/631834d9a45f546ddc9655e681d3cf707640a7f1)、[6578394](https://github.com/Zimkjdv/Model-Atelier/commit/6578394b9c0ff91c9f4403d0cae876b148aa0216)。 本地引擎、checkpoint、提交與作品匯入已分階段完成並實機驗證。 |
| <a id="h002"></a>H002<br>2026-09-06 [cd1d1af](https://github.com/Zimkjdv/Model-Atelier/commit/cd1d1af3aa94ad5b8cd6990a61735acab4b87dff) | 後續 Docker 評估涵蓋資料持久化、GPU 存取、主機硬體資訊來源及 ComfyUI 連線；不預設容器內資訊等於宿主機全部資訊。 | 2026-10-25 已完成 [D02](#d02) 的同機 Docker Desktop／WSL2 評估；其他部署環境未驗收。 |
| <a id="h003"></a>H003<br>2026-09-06 [cd1d1af](https://github.com/Zimkjdv/Model-Atelier/commit/cd1d1af3aa94ad5b8cd6990a61735acab4b87dff) | 規劃由平台自動偵測 GPU 型號、VRAM、RAM 與可用磁碟空間，於 P1 實作系統資訊頁。 | 已交付，見 [4bc2d5c](https://github.com/Zimkjdv/Model-Atelier/commit/4bc2d5ca4a89c8302e5b248d0756c647ea8ec4d4)、[2960e56](https://github.com/Zimkjdv/Model-Atelier/commit/2960e561ca5de85487b42c170805472e6c697a1f)。 硬體來源、主機角色及未知／過期狀態已實作；未提供的引擎裝置資訊保持未知。 |
| <a id="h004"></a>H004<br>2026-09-06 [cd1d1af](https://github.com/Zimkjdv/Model-Atelier/commit/cd1d1af3aa94ad5b8cd6990a61735acab4b87dff) | 確認 GPU 執行於本機或獨立主機；Web 平台與推論引擎分離。 | 已交付部分見 [cd1d1af](https://github.com/Zimkjdv/Model-Atelier/commit/cd1d1af3aa94ad5b8cd6990a61735acab4b87dff)；2026-10-25 已完成 [D01](#d01)：使用者確認維持同機使用，補上本機邊界；未來遠端／區網需求另立規劃。 |
| <a id="h005"></a>H005<br>2026-09-06 [cd1d1af](https://github.com/Zimkjdv/Model-Atelier/commit/cd1d1af3aa94ad5b8cd6990a61735acab4b87dff) | 確認 Windows 原生或 WSL 的推論環境。 | 已交付，見 [cd1d1af](https://github.com/Zimkjdv/Model-Atelier/commit/cd1d1af3aa94ad5b8cd6990a61735acab4b87dff)。 初期環境、資料目錄、骨架、導覽與設定已交付；後續頁面在個別增量接入。 |
| <a id="h006"></a>H006<br>2026-09-06 [cd1d1af](https://github.com/Zimkjdv/Model-Atelier/commit/cd1d1af3aa94ad5b8cd6990a61735acab4b87dff) | 確認資料方案：初期 SQLite + 本地檔案目錄。 | 已交付，見 [cd1d1af](https://github.com/Zimkjdv/Model-Atelier/commit/cd1d1af3aa94ad5b8cd6990a61735acab4b87dff)。 初期環境、資料目錄、骨架、導覽與設定已交付；後續頁面在個別增量接入。 |
| <a id="h007"></a>H007<br>2026-09-06 [cd1d1af](https://github.com/Zimkjdv/Model-Atelier/commit/cd1d1af3aa94ad5b8cd6990a61735acab4b87dff) | 定義模型、輸入素材、輸出、縮圖及資料庫的儲存位置。 | 已交付，見 [cd1d1af](https://github.com/Zimkjdv/Model-Atelier/commit/cd1d1af3aa94ad5b8cd6990a61735acab4b87dff)。 初期環境、資料目錄、骨架、導覽與設定已交付；後續頁面在個別增量接入。 |
| <a id="h008"></a>H008<br>2026-09-06 [cd1d1af](https://github.com/Zimkjdv/Model-Atelier/commit/cd1d1af3aa94ad5b8cd6990a61735acab4b87dff) | 定義本機存取設定；若開放區網或遠端，再加入驗證與連線保護。 | 已交付部分見 [cd1d1af](https://github.com/Zimkjdv/Model-Atelier/commit/cd1d1af3aa94ad5b8cd6990a61735acab4b87dff)；2026-10-25 已完成 [D01](#d01)：使用者確認維持同機使用，補上本機邊界；未來遠端／區網需求另立規劃。 |
| <a id="h009"></a>H009<br>2026-09-06 [cd1d1af](https://github.com/Zimkjdv/Model-Atelier/commit/cd1d1af3aa94ad5b8cd6990a61735acab4b87dff) | 檢查模型執行環境的 GPU、驅動、PyTorch 與 CUDA 可用狀態；資料不可得時標示未知。 | 已交付，見 [4bc2d5c](https://github.com/Zimkjdv/Model-Atelier/commit/4bc2d5ca4a89c8302e5b248d0756c647ea8ec4d4)。 診斷與未知值處理已交付。 |
| <a id="h010"></a>H010<br>2026-09-06 [cd1d1af](https://github.com/Zimkjdv/Model-Atelier/commit/cd1d1af3aa94ad5b8cd6990a61735acab4b87dff) | 建立模型與工作流程的相容性紀錄，區分已驗證、未驗證及已知不相容。 | 已交付，見 [6cb5e1c](https://github.com/Zimkjdv/Model-Atelier/commit/6cb5e1ce5d4be67f3529c4d412a38312d888a2dd)。 條件化相容性紀錄已交付。 |
| <a id="h011"></a>H011<br>2026-09-06 [cd1d1af](https://github.com/Zimkjdv/Model-Atelier/commit/cd1d1af3aa94ad5b8cd6990a61735acab4b87dff) | 記錄生圖與訓練各自的實測資源需求，保留硬體、環境及測試設定，不提供未經驗證的效能保證。 | 已交付部分見 [6578394](https://github.com/Zimkjdv/Model-Atelier/commit/6578394b9c0ff91c9f4403d0cae876b148aa0216)、[df8b141](https://github.com/Zimkjdv/Model-Atelier/commit/df8b14155b8e03fa42889d84ce6e8b28e7595b40)；未完成保留 [E04](ROADMAP.MD#e04)、[E02](ROADMAP.MD#e02)、[T01](CHANGELOG.MD#t01)、[T03](CHANGELOG.MD#t03)。 已有 RTX 3060 推論量測；訓練與 RTX 4080 不能借用該結果。 |
| <a id="h012"></a>H012<br>2026-09-06 [cd1d1af](https://github.com/Zimkjdv/Model-Atelier/commit/cd1d1af3aa94ad5b8cd6990a61735acab4b87dff) | 資源預估不足或尚未實測時提供提示，允許使用者嘗試；不因顯卡型號或估算 VRAM 單獨封鎖提交。 | 已交付，見 [0a9b72a](https://github.com/Zimkjdv/Model-Atelier/commit/0a9b72aa75ce2c7bb7ef89f136dbe742a10e506f)。 唯讀資源提示，不因 VRAM 估算封鎖。 |
| <a id="h013"></a>H013<br>2026-09-06 [cd1d1af](https://github.com/Zimkjdv/Model-Atelier/commit/cd1d1af3aa94ad5b8cd6990a61735acab4b87dff) | 已確認無可用執行裝置、缺少必要元件或工作流程不相容時，只阻擋受影響任務並說明原因，不限制其他平台功能。 | 已交付部分見 [87647e9](https://github.com/Zimkjdv/Model-Atelier/commit/87647e9f58ebe5b71dabc4f32f1ea2e217b9ecb7)；未完成保留 [E01](CHANGELOG.MD#e01)。 缺必要節點等檢查已完成；無裝置判斷仍需可靠引擎證據。 |
| <a id="h014"></a>H014<br>2026-09-06 [cd1d1af](https://github.com/Zimkjdv/Model-Atelier/commit/cd1d1af3aa94ad5b8cd6990a61735acab4b87dff) | 執行記憶體不足時保留原設定並提供調整與重試入口；不默默改動解析度、精度或模型。 | 已交付，見 [bfbae93](https://github.com/Zimkjdv/Model-Atelier/commit/bfbae935974c587ed00f7ed6d58ce79898cf5803)。 保存失敗原設定與診斷，調整後才明確建立新任務。 |
| <a id="h015"></a>H015<br>2026-09-06 [cd1d1af](https://github.com/Zimkjdv/Model-Atelier/commit/cd1d1af3aa94ad5b8cd6990a61735acab4b87dff) | 以現有 RTX 3060 主機完成首輪開發與驗證，保存實際硬體、環境版本及工作流程設定。 | 已交付，見 [6578394](https://github.com/Zimkjdv/Model-Atelier/commit/6578394b9c0ff91c9f4403d0cae876b148aa0216)。 Pony／RTX 3060 首輪、環境及固定負載量測已完成，不外推其他硬體。 |
| <a id="h016"></a>H016<br>2026-09-06 [cd1d1af](https://github.com/Zimkjdv/Model-Atelier/commit/cd1d1af3aa94ad5b8cd6990a61735acab4b87dff) | 首輪通過後，在現有 RTX 4080 主機重跑相同的基本功能與工作流程，記錄相容性、資源用量及耗時差異。 | 未完成保留 [E02](ROADMAP.MD#e02)。 |
| <a id="h017"></a>H017<br>2026-09-06 [cd1d1af](https://github.com/Zimkjdv/Model-Atelier/commit/cd1d1af3aa94ad5b8cd6990a61735acab4b87dff) | 先在兩台主機比較相同設定，再另行測試 RTX 4080 可承受的較高負載；後者不作為 RTX 3060 的基本驗收門檻。 | 未完成保留 [E03](ROADMAP.MD#e03)。 |
| <a id="h018"></a>H018<br>2026-09-06 [cd1d1af](https://github.com/Zimkjdv/Model-Atelier/commit/cd1d1af3aa94ad5b8cd6990a61735acab4b87dff) | 效能紀錄包含模型版本、精度、解析度、步數、批次大小、附加元件、卸載方式與冷／熱啟動條件，避免無條件的秒數承諾。 | 已交付，見 [0fd7fd3](https://github.com/Zimkjdv/Model-Atelier/commit/0fd7fd39846558e808d9308e2ac073518a41fcb6)。 提交時條件快照已交付；實際精度／卸載及冷熱未知時如實保存未知，不當成實測。 |
| <a id="h019"></a>H019<br>2026-09-06 [cd1d1af](https://github.com/Zimkjdv/Model-Atelier/commit/cd1d1af3aa94ad5b8cd6990a61735acab4b87dff) | 建立前後端專案與環境設定範例。 | 已交付，見 [cd1d1af](https://github.com/Zimkjdv/Model-Atelier/commit/cd1d1af3aa94ad5b8cd6990a61735acab4b87dff)。 初期環境、資料目錄、骨架、導覽與設定已交付；後續頁面在個別增量接入。 |
| <a id="h020"></a>H020<br>2026-09-06 [cd1d1af](https://github.com/Zimkjdv/Model-Atelier/commit/cd1d1af3aa94ad5b8cd6990a61735acab4b87dff) | 建立創作工作台、模型庫、作品庫、系統資訊、設定頁的基本導覽。 | 已交付，見 [cd1d1af](https://github.com/Zimkjdv/Model-Atelier/commit/cd1d1af3aa94ad5b8cd6990a61735acab4b87dff)。 初期環境、資料目錄、骨架、導覽與設定已交付；後續頁面在個別增量接入。 |
| <a id="h021"></a>H021<br>2026-09-06 [cd1d1af](https://github.com/Zimkjdv/Model-Atelier/commit/cd1d1af3aa94ad5b8cd6990a61735acab4b87dff) | 支援設定 ComfyUI 位址與連線健康檢查。 | 已交付，見 [cd1d1af](https://github.com/Zimkjdv/Model-Atelier/commit/cd1d1af3aa94ad5b8cd6990a61735acab4b87dff)。 初期環境、資料目錄、骨架、導覽與設定已交付；後續頁面在個別增量接入。 |
| <a id="h022"></a>H022<br>2026-09-06 [cd1d1af](https://github.com/Zimkjdv/Model-Atelier/commit/cd1d1af3aa94ad5b8cd6990a61735acab4b87dff) | 建立執行引擎介面，避免前端直接依賴 ComfyUI API。 | 已交付，見 [c651cfa](https://github.com/Zimkjdv/Model-Atelier/commit/c651cfa543d490ba61ef0c25234877c011471c96)、[1b13d47](https://github.com/Zimkjdv/Model-Atelier/commit/1b13d47b78aec0d1e52c42eaaea925d8031988de)、[87647e9](https://github.com/Zimkjdv/Model-Atelier/commit/87647e9f58ebe5b71dabc4f32f1ea2e217b9ecb7)。 提交、表單欄位與前置檢查分階段完成。 |
| <a id="h023"></a>H023<br>2026-09-06 [cd1d1af](https://github.com/Zimkjdv/Model-Atelier/commit/cd1d1af3aa94ad5b8cd6990a61735acab4b87dff) | 匯入一套已驗證的工作流程，定義可由表單修改的欄位。 | 已交付，見 [c651cfa](https://github.com/Zimkjdv/Model-Atelier/commit/c651cfa543d490ba61ef0c25234877c011471c96)、[1b13d47](https://github.com/Zimkjdv/Model-Atelier/commit/1b13d47b78aec0d1e52c42eaaea925d8031988de)、[87647e9](https://github.com/Zimkjdv/Model-Atelier/commit/87647e9f58ebe5b71dabc4f32f1ea2e217b9ecb7)。 提交、表單欄位與前置檢查分階段完成。 |
| <a id="h024"></a>H024<br>2026-09-06 [cd1d1af](https://github.com/Zimkjdv/Model-Atelier/commit/cd1d1af3aa94ad5b8cd6990a61735acab4b87dff) | 提交前驗證必填值、參數範圍及所需模型是否存在。 | 已交付，見 [c651cfa](https://github.com/Zimkjdv/Model-Atelier/commit/c651cfa543d490ba61ef0c25234877c011471c96)、[1b13d47](https://github.com/Zimkjdv/Model-Atelier/commit/1b13d47b78aec0d1e52c42eaaea925d8031988de)、[87647e9](https://github.com/Zimkjdv/Model-Atelier/commit/87647e9f58ebe5b71dabc4f32f1ea2e217b9ecb7)。 提交、表單欄位與前置檢查分階段完成。 |
| <a id="h025"></a>H025<br>2026-09-06 [cd1d1af](https://github.com/Zimkjdv/Model-Atelier/commit/cd1d1af3aa94ad5b8cd6990a61735acab4b87dff) | 提交任務並保存平台任務 ID 與引擎任務 ID 的對應。 | 已交付，見 [c651cfa](https://github.com/Zimkjdv/Model-Atelier/commit/c651cfa543d490ba61ef0c25234877c011471c96)、[1b13d47](https://github.com/Zimkjdv/Model-Atelier/commit/1b13d47b78aec0d1e52c42eaaea925d8031988de)、[87647e9](https://github.com/Zimkjdv/Model-Atelier/commit/87647e9f58ebe5b71dabc4f32f1ea2e217b9ecb7)。 提交、表單欄位與前置檢查分階段完成。 |
| <a id="h026"></a>H026<br>2026-09-06 [cd1d1af](https://github.com/Zimkjdv/Model-Atelier/commit/cd1d1af3aa94ad5b8cd6990a61735acab4b87dff) | 顯示排隊、執行、完成、失敗及取消狀態。 | 已交付，見 [8fcc946](https://github.com/Zimkjdv/Model-Atelier/commit/8fcc9460fe03f158577cea09deba2f91e43a81d9)、[97ecabe](https://github.com/Zimkjdv/Model-Atelier/commit/97ecabea4bffe86b445af6b8682df83867227180)、[2d64ec1](https://github.com/Zimkjdv/Model-Atelier/commit/2d64ec13836c3ecf5b830d74865357056271fbb0)。 任務狀態、原請求恢復、進度與適用取消已完成。 |
| <a id="h027"></a>H027<br>2026-09-06 [cd1d1af](https://github.com/Zimkjdv/Model-Atelier/commit/cd1d1af3aa94ad5b8cd6990a61735acab4b87dff) | 接收進度事件；斷線重連後查詢任務，避免重複提交。 | 已交付，見 [8fcc946](https://github.com/Zimkjdv/Model-Atelier/commit/8fcc9460fe03f158577cea09deba2f91e43a81d9)、[97ecabe](https://github.com/Zimkjdv/Model-Atelier/commit/97ecabea4bffe86b445af6b8682df83867227180)、[2d64ec1](https://github.com/Zimkjdv/Model-Atelier/commit/2d64ec13836c3ecf5b830d74865357056271fbb0)。 任務狀態、原請求恢復、進度與適用取消已完成。 |
| <a id="h028"></a>H028<br>2026-09-06 [cd1d1af](https://github.com/Zimkjdv/Model-Atelier/commit/cd1d1af3aa94ad5b8cd6990a61735acab4b87dff) | 支援取消排隊任務；執行中停止需確認引擎語意，避免中斷其他任務。 | 已交付，見 [8fcc946](https://github.com/Zimkjdv/Model-Atelier/commit/8fcc9460fe03f158577cea09deba2f91e43a81d9)、[2d64ec1](https://github.com/Zimkjdv/Model-Atelier/commit/2d64ec13836c3ecf5b830d74865357056271fbb0)。 排隊取消及指定執行中任務停止已交付，後者具 RTX 3060 驗收。 |
| <a id="h029"></a>H029<br>2026-09-06 [cd1d1af](https://github.com/Zimkjdv/Model-Atelier/commit/cd1d1af3aa94ad5b8cd6990a61735acab4b87dff) | 保存生成結果、縮圖、執行設定與錯誤資訊。 | 已交付，見 [631834d](https://github.com/Zimkjdv/Model-Atelier/commit/631834d9a45f546ddc9655e681d3cf707640a7f1)、[bfbae93](https://github.com/Zimkjdv/Model-Atelier/commit/bfbae935974c587ed00f7ed6d58ce79898cf5803)。 作品匯入、預覽、完整流程與失敗紀錄已交付；備份方法見 README。 |
| <a id="h030"></a>H030<br>2026-09-06 [cd1d1af](https://github.com/Zimkjdv/Model-Atelier/commit/cd1d1af3aa94ad5b8cd6990a61735acab4b87dff) | 支援從作品載入原設定，再次提交。 | 已交付，見 [f167b9a](https://github.com/Zimkjdv/Model-Atelier/commit/f167b9ad4d04874098a4118d02d13042741eaca2)。 作品原設定還原與再次明確提交已完成。 |
| <a id="h031"></a>H031<br>2026-09-06 [cd1d1af](https://github.com/Zimkjdv/Model-Atelier/commit/cd1d1af3aa94ad5b8cd6990a61735acab4b87dff) | 提供啟動、停止與故障排查說明。 | 已交付，見 [58c5c1e](https://github.com/Zimkjdv/Model-Atelier/commit/58c5c1e55098032ea7e811aa64338a4fe65eb86d)。 PowerShell／BAT 啟停及故障排查說明已交付。 |
| <a id="h032"></a>H032<br>2026-09-06 [cd1d1af](https://github.com/Zimkjdv/Model-Atelier/commit/cd1d1af3aa94ad5b8cd6990a61735acab4b87dff) | 將常用參數直接呈現，進階參數收合，保留使用者設定狀態。 | 已交付，見 [1247600](https://github.com/Zimkjdv/Model-Atelier/commit/1247600aaeae5fd208509a669f2a705b48551702)。 |
| <a id="h033"></a>H033<br>2026-09-06 [cd1d1af](https://github.com/Zimkjdv/Model-Atelier/commit/cd1d1af3aa94ad5b8cd6990a61735acab4b87dff) | 依選定模型與工作流程顯示適用選項，不相容設定需清楚說明原因。 | 已交付，見 [65175c4](https://github.com/Zimkjdv/Model-Atelier/commit/65175c465a241fe06761c6d460e07c0016bcac17)、[88fb32f](https://github.com/Zimkjdv/Model-Atelier/commit/88fb32faba6a2542347aa4d90c502e7f3cdddbd9)。 能力描述、模型預設、原參數保存及不相容保護已交付；FLUX 專用表單另見後續。 |
| <a id="h034"></a>H034<br>2026-09-06 [cd1d1af](https://github.com/Zimkjdv/Model-Atelier/commit/cd1d1af3aa94ad5b8cd6990a61735acab4b87dff) | 清楚呈現排隊、執行、完成及失敗狀態，提供適用的取消與重新執行操作。 | 已交付，見 [8fcc946](https://github.com/Zimkjdv/Model-Atelier/commit/8fcc9460fe03f158577cea09deba2f91e43a81d9)、[97ecabe](https://github.com/Zimkjdv/Model-Atelier/commit/97ecabea4bffe86b445af6b8682df83867227180)、[2d64ec1](https://github.com/Zimkjdv/Model-Atelier/commit/2d64ec13836c3ecf5b830d74865357056271fbb0)。 任務狀態、原請求恢復、進度與適用取消已完成。 |
| <a id="h035"></a>H035<br>2026-09-06 [cd1d1af](https://github.com/Zimkjdv/Model-Atelier/commit/cd1d1af3aa94ad5b8cd6990a61735acab4b87dff) | 作品可一鍵載入原設定，作為繼續創作的起點；圖片並排比較於 P6 實作。 | 已交付部分見 [f167b9a](https://github.com/Zimkjdv/Model-Atelier/commit/f167b9ad4d04874098a4118d02d13042741eaca2)、[a21b41e](https://github.com/Zimkjdv/Model-Atelier/commit/a21b41e578a235a2876b36787315a8615a94b9f6)；未完成保留 [V03](CHANGELOG.MD#v03)。 原設定載入、桌面原圖並排與人工評分已完成；窄視窗仍需補驗。 |
| <a id="h036"></a>H036<br>2026-09-06 [cd1d1af](https://github.com/Zimkjdv/Model-Atelier/commit/cd1d1af3aa94ad5b8cd6990a61735acab4b87dff) | 統一字體、間距、配色、按鈕、表單及載入、空白、錯誤狀態的視覺規範。 | 已交付部分見 [63794de](https://github.com/Zimkjdv/Model-Atelier/commit/63794decb1ad9ed49c430d81730d67fb23dfb618)、[6cbb4a9](https://github.com/Zimkjdv/Model-Atelier/commit/6cbb4a904602daa27ac172b766512ac66d480930)；未完成保留 [V06](CHANGELOG.MD#v06)。 視覺規範及工作台／導覽已驗證，不能概括所有頁面。 |
| <a id="h037"></a>H037<br>2026-09-06 [cd1d1af](https://github.com/Zimkjdv/Model-Atelier/commit/cd1d1af3aa94ad5b8cd6990a61735acab4b87dff) | 建立適合桌面操作的工作台布局，較窄視窗可收合設定區，避免主要操作被擠出畫面。 | 已交付，見 [0c1f60b](https://github.com/Zimkjdv/Model-Atelier/commit/0c1f60bd98765289d02e66b8e9f15193d45772f2)。 |
| <a id="h038"></a>H038<br>2026-09-06 [cd1d1af](https://github.com/Zimkjdv/Model-Atelier/commit/cd1d1af3aa94ad5b8cd6990a61735acab4b87dff) | 表單提供清楚標籤、鍵盤焦點及可讀對比；狀態不只用顏色區分。 | 已交付部分見 [63794de](https://github.com/Zimkjdv/Model-Atelier/commit/63794decb1ad9ed49c430d81730d67fb23dfb618)、[6cbb4a9](https://github.com/Zimkjdv/Model-Atelier/commit/6cbb4a904602daa27ac172b766512ac66d480930)；未完成保留 [V06](CHANGELOG.MD#v06)。 視覺規範及工作台／導覽已驗證，不能概括所有頁面。 |
| <a id="h039"></a>H039<br>2026-09-06 [cd1d1af](https://github.com/Zimkjdv/Model-Atelier/commit/cd1d1af3aa94ad5b8cd6990a61735acab4b87dff) | 由後端或模型執行主機上的資訊採集介面讀取硬體資料，不以瀏覽器所在電腦代表模型執行環境。 | 已交付，見 [4bc2d5c](https://github.com/Zimkjdv/Model-Atelier/commit/4bc2d5ca4a89c8302e5b248d0756c647ea8ec4d4)、[2960e56](https://github.com/Zimkjdv/Model-Atelier/commit/2960e561ca5de85487b42c170805472e6c697a1f)。 硬體來源、主機角色及未知／過期狀態已實作；未提供的引擎裝置資訊保持未知。 |
| <a id="h040"></a>H040<br>2026-09-06 [cd1d1af](https://github.com/Zimkjdv/Model-Atelier/commit/cd1d1af3aa94ad5b8cd6990a61735acab4b87dff) | 顯示 GPU 型號；多 GPU 時逐張列出，並標示引擎使用的裝置，無法確認時顯示未知。 | 已交付，見 [4bc2d5c](https://github.com/Zimkjdv/Model-Atelier/commit/4bc2d5ca4a89c8302e5b248d0756c647ea8ec4d4)、[2960e56](https://github.com/Zimkjdv/Model-Atelier/commit/2960e561ca5de85487b42c170805472e6c697a1f)。 硬體來源、主機角色及未知／過期狀態已實作；未提供的引擎裝置資訊保持未知。 |
| <a id="h041"></a>H041<br>2026-09-06 [cd1d1af](https://github.com/Zimkjdv/Model-Atelier/commit/cd1d1af3aa94ad5b8cd6990a61735acab4b87dff) | 顯示各 GPU 的 VRAM 總量、已用量與可用量，統一容量單位。 | 已交付，見 [4bc2d5c](https://github.com/Zimkjdv/Model-Atelier/commit/4bc2d5ca4a89c8302e5b248d0756c647ea8ec4d4)、[2960e56](https://github.com/Zimkjdv/Model-Atelier/commit/2960e561ca5de85487b42c170805472e6c697a1f)。 硬體來源、主機角色及未知／過期狀態已實作；未提供的引擎裝置資訊保持未知。 |
| <a id="h042"></a>H042<br>2026-09-06 [cd1d1af](https://github.com/Zimkjdv/Model-Atelier/commit/cd1d1af3aa94ad5b8cd6990a61735acab4b87dff) | 顯示模型執行主機的 RAM 總量、已用量與可用量。 | 已交付，見 [4bc2d5c](https://github.com/Zimkjdv/Model-Atelier/commit/4bc2d5ca4a89c8302e5b248d0756c647ea8ec4d4)、[2960e56](https://github.com/Zimkjdv/Model-Atelier/commit/2960e561ca5de85487b42c170805472e6c697a1f)。 硬體來源、主機角色及未知／過期狀態已實作；未提供的引擎裝置資訊保持未知。 |
| <a id="h043"></a>H043<br>2026-09-06 [cd1d1af](https://github.com/Zimkjdv/Model-Atelier/commit/cd1d1af3aa94ad5b8cd6990a61735acab4b87dff) | 顯示模型、素材及輸出目錄所在磁碟的總容量與可用空間；同一磁碟不重複加總。 | 已交付，見 [2960e56](https://github.com/Zimkjdv/Model-Atelier/commit/2960e561ca5de85487b42c170805472e6c697a1f)。 |
| <a id="h044"></a>H044<br>2026-09-06 [cd1d1af](https://github.com/Zimkjdv/Model-Atelier/commit/cd1d1af3aa94ad5b8cd6990a61735acab4b87dff) | 平台與推論引擎分開部署時，分別標示主機角色與資料來源；素材及輸出磁碟資訊依其實際儲存主機顯示。 | 已交付，見 [4bc2d5c](https://github.com/Zimkjdv/Model-Atelier/commit/4bc2d5ca4a89c8302e5b248d0756c647ea8ec4d4)、[2960e56](https://github.com/Zimkjdv/Model-Atelier/commit/2960e561ca5de85487b42c170805472e6c697a1f)。 硬體來源、主機角色及未知／過期狀態已實作；未提供的引擎裝置資訊保持未知。 |
| <a id="h045"></a>H045<br>2026-09-06 [cd1d1af](https://github.com/Zimkjdv/Model-Atelier/commit/cd1d1af3aa94ad5b8cd6990a61735acab4b87dff) | 進入系統資訊頁時自動取得資料，提供手動重新整理、定期更新及最後更新時間。 | 已交付，見 [4bc2d5c](https://github.com/Zimkjdv/Model-Atelier/commit/4bc2d5ca4a89c8302e5b248d0756c647ea8ec4d4)、[2960e56](https://github.com/Zimkjdv/Model-Atelier/commit/2960e561ca5de85487b42c170805472e6c697a1f)。 硬體來源、主機角色及未知／過期狀態已實作；未提供的引擎裝置資訊保持未知。 |
| <a id="h046"></a>H046<br>2026-09-06 [cd1d1af](https://github.com/Zimkjdv/Model-Atelier/commit/cd1d1af3aa94ad5b8cd6990a61735acab4b87dff) | 若遠端介面不提供某項資訊，顯示「無法取得」及原因，不以平台主機資料代替，也不顯示為零。 | 已交付，見 [4bc2d5c](https://github.com/Zimkjdv/Model-Atelier/commit/4bc2d5ca4a89c8302e5b248d0756c647ea8ec4d4)、[2960e56](https://github.com/Zimkjdv/Model-Atelier/commit/2960e561ca5de85487b42c170805472e6c697a1f)。 硬體來源、主機角色及未知／過期狀態已實作；未提供的引擎裝置資訊保持未知。 |
| <a id="h047"></a>H047<br>2026-09-06 [cd1d1af](https://github.com/Zimkjdv/Model-Atelier/commit/cd1d1af3aa94ad5b8cd6990a61735acab4b87dff) | 處理無 GPU、驅動或權限不足、主機離線等狀態；保留的舊資料需明確標示已過期。 | 已交付，見 [4bc2d5c](https://github.com/Zimkjdv/Model-Atelier/commit/4bc2d5ca4a89c8302e5b248d0756c647ea8ec4d4)、[2960e56](https://github.com/Zimkjdv/Model-Atelier/commit/2960e561ca5de85487b42c170805472e6c697a1f)。 硬體來源、主機角色及未知／過期狀態已實作；未提供的引擎裝置資訊保持未知。 |
| <a id="h048"></a>H048<br>2026-09-06 [cd1d1af](https://github.com/Zimkjdv/Model-Atelier/commit/cd1d1af3aa94ad5b8cd6990a61735acab4b87dff) | 第一版以資訊顯示為主；單靠剩餘 VRAM 不保證模型可執行。 | 已交付，見 [0a9b72a](https://github.com/Zimkjdv/Model-Atelier/commit/0a9b72aa75ce2c7bb7ef89f136dbe742a10e506f)。 唯讀資源提示，不因 VRAM 估算封鎖。 |
| <a id="h049"></a>H049<br>2026-09-06 [cd1d1af](https://github.com/Zimkjdv/Model-Atelier/commit/cd1d1af3aa94ad5b8cd6990a61735acab4b87dff) | 核對 Pony V6 XL 的正式來源、版本、授權及依賴。 | 已交付部分見 [6578394](https://github.com/Zimkjdv/Model-Atelier/commit/6578394b9c0ff91c9f4403d0cae876b148aa0216)；未完成保留 [M01](ROADMAP.MD#m01)。 來源、修訂、hash 與模型卡標記已保存；完整授權條款未核對。 |
| <a id="h050"></a>H050<br>2026-09-06 [cd1d1af](https://github.com/Zimkjdv/Model-Atelier/commit/cd1d1af3aa94ad5b8cd6990a61735acab4b87dff) | 核對並選定 Animagine XL 版本、來源、授權及依賴。 | 已交付，見 [2602811](https://github.com/Zimkjdv/Model-Atelier/commit/2602811267f7be836aa1f0e4410bfa6bd25e5804)、[cbc0ee1](https://github.com/Zimkjdv/Model-Atelier/commit/cbc0ee10748e9c763477b87f451e32587a752efc)、[1602004](https://github.com/Zimkjdv/Model-Atelier/commit/16020048e31c7c1b0dda189dec80ed38d4a906c0)。 Animagine 4.0 Opt 選型、安裝及 RTX 3060 切換已完成。 |
| <a id="h051"></a>H051<br>2026-09-06 [cd1d1af](https://github.com/Zimkjdv/Model-Atelier/commit/cd1d1af3aa94ad5b8cd6990a61735acab4b87dff) | 支援登記既有本地模型路徑，第一版不強制複製大型檔案。 | 已交付，見 [7541feb](https://github.com/Zimkjdv/Model-Atelier/commit/7541feb57d69550c6e35c05bdab6efe1cab8ee1e)、[d6364f5](https://github.com/Zimkjdv/Model-Atelier/commit/d6364f5415ea13d20613a81dbdd0be924927ab06)。 本地 ComfyUI 安裝與既有模型路徑登記已完成。 |
| <a id="h052"></a>H052<br>2026-09-06 [cd1d1af](https://github.com/Zimkjdv/Model-Atelier/commit/cd1d1af3aa94ad5b8cd6990a61735acab4b87dff) | 記錄模型名稱、架構、版本、檔案大小、雜湊、來源與授權連結。 | 已交付，見 [d4391de](https://github.com/Zimkjdv/Model-Atelier/commit/d4391de9650b567ff2c7577a63a6e4e23c8c78a9)。 |
| <a id="h053"></a>H053<br>2026-09-06 [cd1d1af](https://github.com/Zimkjdv/Model-Atelier/commit/cd1d1af3aa94ad5b8cd6990a61735acab4b87dff) | 建立每個模型獨立的工作流程與參數預設。 | 已交付，見 [65175c4](https://github.com/Zimkjdv/Model-Atelier/commit/65175c465a241fe06761c6d460e07c0016bcac17)、[2602811](https://github.com/Zimkjdv/Model-Atelier/commit/2602811267f7be836aa1f0e4410bfa6bd25e5804)。 各模型起始預設與工作流程描述已交付；不是所有模型的品質保證。 |
| <a id="h054"></a>H054<br>2026-09-06 [cd1d1af](https://github.com/Zimkjdv/Model-Atelier/commit/cd1d1af3aa94ad5b8cd6990a61735acab4b87dff) | 依流程能力顯示提示詞、seed、尺寸、步數等設定。 | 已交付，見 [65175c4](https://github.com/Zimkjdv/Model-Atelier/commit/65175c465a241fe06761c6d460e07c0016bcac17)、[88fb32f](https://github.com/Zimkjdv/Model-Atelier/commit/88fb32faba6a2542347aa4d90c502e7f3cdddbd9)。 能力描述、模型預設、原參數保存及不相容保護已交付；FLUX 專用表單另見後續。 |
| <a id="h055"></a>H055<br>2026-09-06 [cd1d1af](https://github.com/Zimkjdv/Model-Atelier/commit/cd1d1af3aa94ad5b8cd6990a61735acab4b87dff) | 只顯示流程實際支援的進階欄位，保存原始參數。 | 已交付，見 [65175c4](https://github.com/Zimkjdv/Model-Atelier/commit/65175c465a241fe06761c6d460e07c0016bcac17)、[88fb32f](https://github.com/Zimkjdv/Model-Atelier/commit/88fb32faba6a2542347aa4d90c502e7f3cdddbd9)。 能力描述、模型預設、原參數保存及不相容保護已交付；FLUX 專用表單另見後續。 |
| <a id="h056"></a>H056<br>2026-09-06 [cd1d1af](https://github.com/Zimkjdv/Model-Atelier/commit/cd1d1af3aa94ad5b8cd6990a61735acab4b87dff) | 切換模型時重新檢查相容性，不沿用不適用的參數或元件。 | 已交付，見 [65175c4](https://github.com/Zimkjdv/Model-Atelier/commit/65175c465a241fe06761c6d460e07c0016bcac17)、[88fb32f](https://github.com/Zimkjdv/Model-Atelier/commit/88fb32faba6a2542347aa4d90c502e7f3cdddbd9)。 能力描述、模型預設、原參數保存及不相容保護已交付；FLUX 專用表單另見後續。 |
| <a id="h057"></a>H057<br>2026-09-06 [cd1d1af](https://github.com/Zimkjdv/Model-Atelier/commit/cd1d1af3aa94ad5b8cd6990a61735acab4b87dff) | 測量生成耗時與記憶體需求，記錄測量環境。 | 已交付，見 [6578394](https://github.com/Zimkjdv/Model-Atelier/commit/6578394b9c0ff91c9f4403d0cae876b148aa0216)、[df8b141](https://github.com/Zimkjdv/Model-Atelier/commit/df8b14155b8e03fa42889d84ce6e8b28e7595b40)、[0fd7fd3](https://github.com/Zimkjdv/Model-Atelier/commit/0fd7fd39846558e808d9308e2ac073518a41fcb6)。 固定工作負載耗時、可得記憶體與環境條件已保存；連續峰值延伸另列 E05。 |
| <a id="h058"></a>H058<br>2026-09-06 [cd1d1af](https://github.com/Zimkjdv/Model-Atelier/commit/cd1d1af3aa94ad5b8cd6990a61735acab4b87dff) | 處理模型遺失、載入失敗及 GPU 記憶體不足。 | 已交付，見 [bfbae93](https://github.com/Zimkjdv/Model-Atelier/commit/bfbae935974c587ed00f7ed6d58ce79898cf5803)。 保存失敗原設定與診斷，調整後才明確建立新任務。 |
| <a id="h059"></a>H059<br>2026-09-06 [cd1d1af](https://github.com/Zimkjdv/Model-Atelier/commit/cd1d1af3aa94ad5b8cd6990a61735acab4b87dff) | 建立 LoRA 登記、來源、版本與基礎架構欄位。 | 已交付，見 [ddb871f](https://github.com/Zimkjdv/Model-Atelier/commit/ddb871f47ead3448c5df91e4f7df7167db2f8fb7)。 |
| <a id="h060"></a>H060<br>2026-09-06 [cd1d1af](https://github.com/Zimkjdv/Model-Atelier/commit/cd1d1af3aa94ad5b8cd6990a61735acab4b87dff) | 支援選擇、啟用及移除 LoRA，保存工作流程支援的設定。 | 已交付，見 [ca019b3](https://github.com/Zimkjdv/Model-Atelier/commit/ca019b3019063146a7058c8ff718d1816aeb81b6)、[367ae73](https://github.com/Zimkjdv/Model-Atelier/commit/367ae73d8dcfd2926900818410b1bdeba26d6e5a)。 |
| <a id="h061"></a>H061<br>2026-09-06 [cd1d1af](https://github.com/Zimkjdv/Model-Atelier/commit/cd1d1af3aa94ad5b8cd6990a61735acab4b87dff) | 顯示相容、未驗證或不相容狀態；不以檔名推斷相容性。 | 已交付，見 [d73c6da](https://github.com/Zimkjdv/Model-Atelier/commit/d73c6da540c03929a6324581ba238a2b0ff9bc0d)。 |
| <a id="h062"></a>H062<br>2026-09-06 [cd1d1af](https://github.com/Zimkjdv/Model-Atelier/commit/cd1d1af3aa94ad5b8cd6990a61735acab4b87dff) | 提交前阻擋已知不相容組合。 | 已交付，見 [34145fe](https://github.com/Zimkjdv/Model-Atelier/commit/34145fe915312ae42d0a580b97fc813eb2cdb263)。 |
| <a id="h063"></a>H063<br>2026-09-06 [cd1d1af](https://github.com/Zimkjdv/Model-Atelier/commit/cd1d1af3aa94ad5b8cd6990a61735acab4b87dff) | 先驗證單一 LoRA，再評估多個 LoRA 的組合支援。 | 已交付部分見 [7595335](https://github.com/Zimkjdv/Model-Atelier/commit/7595335697dc15cef43617b2ef82414f914dc2a6)、[367ae73](https://github.com/Zimkjdv/Model-Atelier/commit/367ae73d8dcfd2926900818410b1bdeba26d6e5a)、[4287634](https://github.com/Zimkjdv/Model-Atelier/commit/428763421fe3a2d3b3b5de269a9e7e02a3adfe5f)；未完成保留 [L01](CHANGELOG.MD#l01)。 單一與有序多 LoRA 載入／還原已完成；其他組合及畫風品質仍待評估。 |
| <a id="h064"></a>H064<br>2026-09-06 [cd1d1af](https://github.com/Zimkjdv/Model-Atelier/commit/cd1d1af3aa94ad5b8cd6990a61735acab4b87dff) | 將 LoRA 版本及設定保存至生成紀錄。 | 已交付，見 [c80068e](https://github.com/Zimkjdv/Model-Atelier/commit/c80068e8c109b73632e4f86aed60787b4d11f6c7)。 |
| <a id="h065"></a>H065<br>2026-09-06 [cd1d1af](https://github.com/Zimkjdv/Model-Atelier/commit/cd1d1af3aa94ad5b8cd6990a61735acab4b87dff) | 選定可本地執行的公開權重變體，記錄授權及使用條件。 | 已交付，見 [5bf331f](https://github.com/Zimkjdv/Model-Atelier/commit/5bf331f543250fd5a0f88a71424f8eda7368eb96)。 已固定 FLUX.1 [schnell] 變體；安裝與實機驗收另列 F01–F04。 |
| <a id="h066"></a>H066<br>2026-09-06 [cd1d1af](https://github.com/Zimkjdv/Model-Atelier/commit/cd1d1af3aa94ad5b8cd6990a61735acab4b87dff) | 確認所需編碼器、解碼器、推論精度及硬體需求。 | 已交付部分見 [5bf331f](https://github.com/Zimkjdv/Model-Atelier/commit/5bf331f543250fd5a0f88a71424f8eda7368eb96)、[c7008c6](https://github.com/Zimkjdv/Model-Atelier/commit/c7008c6a4c503bca40658b99780ccf756f533513)；未完成保留 [F01](ROADMAP.MD#f01)、[F02](ROADMAP.MD#f02)。 固定元件與預檢已交付，尚不能視為已安裝或已驗證實際精度／資源。 |
| <a id="h067"></a>H067<br>2026-09-06 [cd1d1af](https://github.com/Zimkjdv/Model-Atelier/commit/cd1d1af3aa94ad5b8cd6990a61735acab4b87dff) | 建立獨立工作流程與參數描述，不直接套用 SDXL 表單。 | 已交付，見 [2f8f23e](https://github.com/Zimkjdv/Model-Atelier/commit/2f8f23e28d092ecdda05bd6c78b2381c14a8fe1e)、[3aaf6ed](https://github.com/Zimkjdv/Model-Atelier/commit/3aaf6ed4665c79385ad2387cbd37a6d2834e2c9b)。 獨立後端與表單已交付；未宣稱 GPU 出圖完成。 |
| <a id="h068"></a>H068<br>2026-09-06 [cd1d1af](https://github.com/Zimkjdv/Model-Atelier/commit/cd1d1af3aa94ad5b8cd6990a61735acab4b87dff) | 驗證載入、生成、結果保存及記憶體不足時的處理。 | 未完成保留 [F03](ROADMAP.MD#f03)。 |
| <a id="h069"></a>H069<br>2026-09-06 [cd1d1af](https://github.com/Zimkjdv/Model-Atelier/commit/cd1d1af3aa94ad5b8cd6990a61735acab4b87dff) | 對此架構的 LoRA 與參考圖功能逐項驗證，未驗證能力保持停用。 | 未完成保留 [F04](ROADMAP.MD#f04)。 |
| <a id="h070"></a>H070<br>2026-09-06 [cd1d1af](https://github.com/Zimkjdv/Model-Atelier/commit/cd1d1af3aa94ad5b8cd6990a61735acab4b87dff) | 上傳、預覽及管理參考圖片，檢查格式和尺寸。 | 已交付，見 [47a7c59](https://github.com/Zimkjdv/Model-Atelier/commit/47a7c5961f1345fcfd4a7c38ccea0f924bcc8125)。 |
| <a id="h071"></a>H071<br>2026-09-06 [cd1d1af](https://github.com/Zimkjdv/Model-Atelier/commit/cd1d1af3aa94ad5b8cd6990a61735acab4b87dff) | 標示參考用途：視覺風格、角色外觀、構圖等。 | 已交付，見 [5dfa86a](https://github.com/Zimkjdv/Model-Atelier/commit/5dfa86a0f16f941de793069cdf34ef39b691cf57)。 |
| <a id="h072"></a>H072<br>2026-09-06 [cd1d1af](https://github.com/Zimkjdv/Model-Atelier/commit/cd1d1af3aa94ad5b8cd6990a61735acab4b87dff) | 建立每套工作流程的輸入需求與支援能力說明。 | 已交付，見 [5dfa86a](https://github.com/Zimkjdv/Model-Atelier/commit/5dfa86a0f16f941de793069cdf34ef39b691cf57)、[88fb32f](https://github.com/Zimkjdv/Model-Atelier/commit/88fb32faba6a2542347aa4d90c502e7f3cdddbd9)。 |
| <a id="h073"></a>H073<br>2026-09-06 [cd1d1af](https://github.com/Zimkjdv/Model-Atelier/commit/cd1d1af3aa94ad5b8cd6990a61735acab4b87dff) | 逐項評估圖片生成圖片、局部編輯及結構參考流程。 | 已交付部分見 [7302384](https://github.com/Zimkjdv/Model-Atelier/commit/7302384d92bd38d9de3dd43a350b20398cdbad15)、[7e5680f](https://github.com/Zimkjdv/Model-Atelier/commit/7e5680faf49ab76980493afd9c778f3610c392a9)、[87d277d](https://github.com/Zimkjdv/Model-Atelier/commit/87d277d5716c0c1f3a4307e1b3049d588abe2f95)、[3dc10b8](https://github.com/Zimkjdv/Model-Atelier/commit/3dc10b8c2d71883b1514c85db9f353c48476e108)；未完成保留 [R01](CHANGELOG.MD#r01)、[R02](CHANGELOG.MD#r02)、[R03](CHANGELOG.MD#r03)。 單張圖生圖、checkpoint 局部編輯及 Canny 已接入；其他結構、adapter 與修補品質仍待評估。 |
| <a id="h074"></a>H074<br>2026-09-06 [cd1d1af](https://github.com/Zimkjdv/Model-Atelier/commit/cd1d1af3aa94ad5b8cd6990a61735acab4b87dff) | 保存參考圖與輸出的關聯；保存前處理設定及版本。 | 已交付，見 [7302384](https://github.com/Zimkjdv/Model-Atelier/commit/7302384d92bd38d9de3dd43a350b20398cdbad15)、[b699024](https://github.com/Zimkjdv/Model-Atelier/commit/b699024f6885fa0635cc5724be5f5e6259216bdb)。 |
| <a id="h075"></a>H075<br>2026-09-06 [cd1d1af](https://github.com/Zimkjdv/Model-Atelier/commit/cd1d1af3aa94ad5b8cd6990a61735acab4b87dff) | 檢查素材是否被任務引用，避免刪除後無法重建流程。 | 已交付，見 [5dfa86a](https://github.com/Zimkjdv/Model-Atelier/commit/5dfa86a0f16f941de793069cdf34ef39b691cf57)。 |
| <a id="h076"></a>H076<br>2026-09-06 [cd1d1af](https://github.com/Zimkjdv/Model-Atelier/commit/cd1d1af3aa94ad5b8cd6990a61735acab4b87dff) | 支援作品篩選、收藏、備註與下載。 | 已交付部分見 [9ca7c22](https://github.com/Zimkjdv/Model-Atelier/commit/9ca7c221012f33c0dc96ba604816b77b0393c860)、[f167b9a](https://github.com/Zimkjdv/Model-Atelier/commit/f167b9ad4d04874098a4118d02d13042741eaca2)；未完成保留 [V03](CHANGELOG.MD#v03)。 作品整理與原設定載入已交付，桌面已驗證；窄視窗整理驗收未完成。 |
| <a id="h077"></a>H077<br>2026-09-06 [cd1d1af](https://github.com/Zimkjdv/Model-Atelier/commit/cd1d1af3aa94ad5b8cd6990a61735acab4b87dff) | 支援設定匯出、匯入及從歷史紀錄重新執行。 | 已交付部分見 [5c44382](https://github.com/Zimkjdv/Model-Atelier/commit/5c4438218ee3338aede710e5c3f597a8e79a936b)；未完成保留 [V05](CHANGELOG.MD#v05)。 創作設定交換後端與桌面介面已交付；原生下載落盤及 390px 尚缺。 |
| <a id="h078"></a>H078<br>2026-09-06 [cd1d1af](https://github.com/Zimkjdv/Model-Atelier/commit/cd1d1af3aa94ad5b8cd6990a61735acab4b87dff) | 保存模型、LoRA、工作流程、引擎及依賴版本。 | 已交付，見 [d4391de](https://github.com/Zimkjdv/Model-Atelier/commit/d4391de9650b567ff2c7577a63a6e4e23c8c78a9)、[c80068e](https://github.com/Zimkjdv/Model-Atelier/commit/c80068e8c109b73632e4f86aed60787b4d11f6c7)、[7f32d47](https://github.com/Zimkjdv/Model-Atelier/commit/7f32d47b0f21e6e97de1f0d6a4502ed39c7ab72e)。 |
| <a id="h079"></a>H079<br>2026-09-06 [cd1d1af](https://github.com/Zimkjdv/Model-Atelier/commit/cd1d1af3aa94ad5b8cd6990a61735acab4b87dff) | 提供圖片並排比較與人工評分。 | 已交付部分見 [f167b9a](https://github.com/Zimkjdv/Model-Atelier/commit/f167b9ad4d04874098a4118d02d13042741eaca2)、[a21b41e](https://github.com/Zimkjdv/Model-Atelier/commit/a21b41e578a235a2876b36787315a8615a94b9f6)；未完成保留 [V03](CHANGELOG.MD#v03)。 原設定載入、桌面原圖並排與人工評分已完成；窄視窗仍需補驗。 |
| <a id="h080"></a>H080<br>2026-09-06 [cd1d1af](https://github.com/Zimkjdv/Model-Atelier/commit/cd1d1af3aa94ad5b8cd6990a61735acab4b87dff) | 使用固定的一般插畫測試集，比較提示服從、角色一致、視覺風格及構圖。 | 已交付部分見 [e3ef1d2](https://github.com/Zimkjdv/Model-Atelier/commit/e3ef1d2261e0c47947b39930cea61312d7d2890b)；未完成保留 [R05](CHANGELOG.MD#r05)、[R02](CHANGELOG.MD#r02)、[V04](CHANGELOG.MD#v04)。 固定兩模型四案例 GPU 完成；更多 seed、作者提示及角色／畫風品質不被涵蓋，新的 UI 仍需補驗。 |
| <a id="h081"></a>H081<br>2026-09-06 [cd1d1af](https://github.com/Zimkjdv/Model-Atelier/commit/cd1d1af3aa94ad5b8cd6990a61735acab4b87dff) | 支援有限範圍的參數比較，提交前顯示預計任務數。 | 已交付部分見 [0ed66ce](https://github.com/Zimkjdv/Model-Atelier/commit/0ed66ce82acafbc0e8337663b2a0bae17a927043)、[8d9aa15](https://github.com/Zimkjdv/Model-Atelier/commit/8d9aa15a2dc10a34b3a817c03716bbc61b190bd3)、[ea31058](https://github.com/Zimkjdv/Model-Atelier/commit/ea310584c69d5a3416d45a0d6feb5498c6aa5d36)、[2a64a9a](https://github.com/Zimkjdv/Model-Atelier/commit/2a64a9a41a7b4c5a1a6f0fdb6e748cf63bd96930)；未完成保留 [R06](CHANGELOG.MD#r06)、[R07](CHANGELOG.MD#r07)。 有界預覽、既有參數軸與關聯已交付；擴充工作流程／參數另評估。自動批次與自動品質評分是排除範圍。 |
| <a id="h082"></a>H082<br>2026-09-06 [cd1d1af](https://github.com/Zimkjdv/Model-Atelier/commit/cd1d1af3aa94ad5b8cd6990a61735acab4b87dff) | 記錄耗時及可取得的資源用量，無法測得的數值不推估填入。 | 已交付部分見 [df8b141](https://github.com/Zimkjdv/Model-Atelier/commit/df8b14155b8e03fa42889d84ce6e8b28e7595b40)；未完成保留 [E05](CHANGELOG.MD#e05)。 既有耗時與提交前快照已交付；連續／任務專用峰值尚缺。 |
| <a id="h083"></a>H083<br>2026-09-06 [cd1d1af](https://github.com/Zimkjdv/Model-Atelier/commit/cd1d1af3aa94ad5b8cd6990a61735acab4b87dff) | 確認是否有超出推論參數調整的實際訓練需求。 | 未完成保留 [T01](CHANGELOG.MD#t01)。 |
| <a id="h084"></a>H084<br>2026-09-06 [cd1d1af](https://github.com/Zimkjdv/Model-Atelier/commit/cd1d1af3aa94ad5b8cd6990a61735acab4b87dff) | 評估資料集管理、標註、版本及訓練工具介面。 | 未完成保留 [T02](CHANGELOG.MD#t02)。 |
| <a id="h085"></a>H085<br>2026-09-06 [cd1d1af](https://github.com/Zimkjdv/Model-Atelier/commit/cd1d1af3aa94ad5b8cd6990a61735acab4b87dff) | 規劃獨立環境與 GPU 資源協調，避免與生成任務互相干擾。 | 未完成保留 [T03](CHANGELOG.MD#t03)。 |
| <a id="h086"></a>H086<br>2026-09-06 [cd1d1af](https://github.com/Zimkjdv/Model-Atelier/commit/cd1d1af3aa94ad5b8cd6990a61735acab4b87dff) | 規劃訓練產物回登模型庫及評估流程。 | 未完成保留 [T04](CHANGELOG.MD#t04)。 |
| <a id="h087"></a>H087<br>2026-09-06 [cd1d1af](https://github.com/Zimkjdv/Model-Atelier/commit/cd1d1af3aa94ad5b8cd6990a61735acab4b87dff) | NovelAI：確認官方 API、驗證方式、使用條件、費用及可接入功能。 | 未完成保留 [A01](ROADMAP.MD#a01)。 |
| <a id="h088"></a>H088<br>2026-09-06 [cd1d1af](https://github.com/Zimkjdv/Model-Atelier/commit/cd1d1af3aa94ad5b8cd6990a61735acab4b87dff) | Mango 2：先確認確切模型與提供者，再核對公開權重或官方 API。 | 未完成保留 [A02](ROADMAP.MD#a02)。 |
| <a id="h089"></a>H089<br>2026-09-06 [cd1d1af](https://github.com/Zimkjdv/Model-Atelier/commit/cd1d1af3aa94ad5b8cd6990a61735acab4b87dff) | 只有已確認正式接入方式的服務才列入實作，不假設網站功能等於 API 功能。 | 未完成保留 [A03](ROADMAP.MD#a03)。 |
| <a id="h090"></a>H090<br>2026-09-06 [cd1d1af](https://github.com/Zimkjdv/Model-Atelier/commit/cd1d1af3aa94ad5b8cd6990a61735acab4b87dff) | 建立服務介面，分離本地模型與遠端服務的能力描述。 | 未完成保留 [A03](ROADMAP.MD#a03)。 |
| <a id="h091"></a>H091<br>2026-09-06 [cd1d1af](https://github.com/Zimkjdv/Model-Atelier/commit/cd1d1af3aa94ad5b8cd6990a61735acab4b87dff) | 憑證只保存在後端，不寫入前端或版本控制。 | 未完成保留 [A04](ROADMAP.MD#a04)。 |
| <a id="h092"></a>H092<br>2026-09-06 [cd1d1af](https://github.com/Zimkjdv/Model-Atelier/commit/cd1d1af3aa94ad5b8cd6990a61735acab4b87dff) | 提交前顯示資料將送往的服務及已知費用資訊。 | 未完成保留 [A05](ROADMAP.MD#a05)。 |
| <a id="h093"></a>H093<br>2026-09-06 [cd1d1af](https://github.com/Zimkjdv/Model-Atelier/commit/cd1d1af3aa94ad5b8cd6990a61735acab4b87dff) | 處理限流、逾時、扣費狀態及重試，避免重複付費提交。 | 未完成保留 [A06](ROADMAP.MD#a06)。 |
| <a id="h094"></a>H094<br>2026-09-06 [cd1d1af](https://github.com/Zimkjdv/Model-Atelier/commit/cd1d1af3aa94ad5b8cd6990a61735acab4b87dff) | 依服務支援範圍保存結果及請求設定。 | 未完成保留 [A07](ROADMAP.MD#a07)。 |
| <a id="h095"></a>H095<br>2026-09-06 [cd1d1af](https://github.com/Zimkjdv/Model-Atelier/commit/cd1d1af3aa94ad5b8cd6990a61735acab4b87dff) | 推論跑本機或遠端 GPU；是否需要區網存取。 | 已交付部分見 [cd1d1af](https://github.com/Zimkjdv/Model-Atelier/commit/cd1d1af3aa94ad5b8cd6990a61735acab4b87dff)；2026-10-25 已完成 [D01](#d01)：使用者確認維持同機使用，補上本機邊界；未來遠端／區網需求另立規劃。 |
| <a id="h096"></a>H096<br>2026-09-06 [cd1d1af](https://github.com/Zimkjdv/Model-Atelier/commit/cd1d1af3aa94ad5b8cd6990a61735acab4b87dff) | 現有 ComfyUI 是否已安裝，是否有可沿用的模型目錄。 | 已交付，見 [7541feb](https://github.com/Zimkjdv/Model-Atelier/commit/7541feb57d69550c6e35c05bdab6efe1cab8ee1e)、[d6364f5](https://github.com/Zimkjdv/Model-Atelier/commit/d6364f5415ea13d20613a81dbdd0be924927ab06)。 本地 ComfyUI 安裝與既有模型路徑登記已完成。 |
| <a id="h097"></a>H097<br>2026-09-06 [cd1d1af](https://github.com/Zimkjdv/Model-Atelier/commit/cd1d1af3aa94ad5b8cd6990a61735acab4b87dff) | 確認第一個模型採 Pony V6 XL，或依硬體與實測調整。 | 已交付，見 [6578394](https://github.com/Zimkjdv/Model-Atelier/commit/6578394b9c0ff91c9f4403d0cae876b148aa0216)。 Pony／RTX 3060 首輪、環境及固定負載量測已完成，不外推其他硬體。 |
| <a id="h098"></a>H098<br>2026-09-06 [cd1d1af](https://github.com/Zimkjdv/Model-Atelier/commit/cd1d1af3aa94ad5b8cd6990a61735acab4b87dff) | Animagine XL 與 FLUX.1 的確切版本。 | 已交付，見 [2602811](https://github.com/Zimkjdv/Model-Atelier/commit/2602811267f7be836aa1f0e4410bfa6bd25e5804)、[5bf331f](https://github.com/Zimkjdv/Model-Atelier/commit/5bf331f543250fd5a0f88a71424f8eda7368eb96)。 Animagine 4.0 Opt 與 FLUX.1 [schnell] 版本已選定。 |
| <a id="h099"></a>H099<br>2026-09-06 [cd1d1af](https://github.com/Zimkjdv/Model-Atelier/commit/cd1d1af3aa94ad5b8cd6990a61735acab4b87dff) | Mango 2 的官方來源。 | 未完成保留 [A02](ROADMAP.MD#a02)。 |
| <a id="h100"></a>H100<br>2026-09-06 [7699c4f](https://github.com/Zimkjdv/Model-Atelier/commit/7699c4f86109fb88bda39c9d38509754dd97839d) | 真實 ComfyUI 連線與模型同步仍待驗證；工作流程提交與生成結果保存尚未實作，創作與作品頁仍為待開發頁面。 | 已交付，見 [7541feb](https://github.com/Zimkjdv/Model-Atelier/commit/7541feb57d69550c6e35c05bdab6efe1cab8ee1e)、[c651cfa](https://github.com/Zimkjdv/Model-Atelier/commit/c651cfa543d490ba61ef0c25234877c011471c96)、[631834d](https://github.com/Zimkjdv/Model-Atelier/commit/631834d9a45f546ddc9655e681d3cf707640a7f1)、[6578394](https://github.com/Zimkjdv/Model-Atelier/commit/6578394b9c0ff91c9f4403d0cae876b148aa0216)。 本地引擎、checkpoint、提交與作品匯入已分階段完成並實機驗證。 |
| <a id="h101"></a>H101<br>2026-09-06 [7699c4f](https://github.com/Zimkjdv/Model-Atelier/commit/7699c4f86109fb88bda39c9d38509754dd97839d) | 模型庫後續補齊檔案雜湊、大小、版本與架構等資料；目前來源與備註為使用者登記資訊，不能視為已驗證。 | 已交付，見 [d4391de](https://github.com/Zimkjdv/Model-Atelier/commit/d4391de9650b567ff2c7577a63a6e4e23c8c78a9)。 |
| <a id="h102"></a>H102<br>2026-09-06 [7541feb](https://github.com/Zimkjdv/Model-Atelier/commit/7541feb57d69550c6e35c05bdab6efe1cab8ee1e) | 尚未安裝 checkpoint，非空模型清單、實際模型載入與生成仍待驗證；工作流程提交與生成結果保存尚未實作。 | 已交付，見 [7541feb](https://github.com/Zimkjdv/Model-Atelier/commit/7541feb57d69550c6e35c05bdab6efe1cab8ee1e)、[c651cfa](https://github.com/Zimkjdv/Model-Atelier/commit/c651cfa543d490ba61ef0c25234877c011471c96)、[631834d](https://github.com/Zimkjdv/Model-Atelier/commit/631834d9a45f546ddc9655e681d3cf707640a7f1)、[6578394](https://github.com/Zimkjdv/Model-Atelier/commit/6578394b9c0ff91c9f4403d0cae876b148aa0216)。 本地引擎、checkpoint、提交與作品匯入已分階段完成並實機驗證。 |
| <a id="h103"></a>H103<br>2026-09-06 [47a7c59](https://github.com/Zimkjdv/Model-Atelier/commit/47a7c5961f1345fcfd4a7c38ccea0f924bcc8125) | 參考素材目前僅管理與記錄，尚未串接 ComfyUI 圖片輸入、用途或參考權重。 | 已交付部分見 [5dfa86a](https://github.com/Zimkjdv/Model-Atelier/commit/5dfa86a0f16f941de793069cdf34ef39b691cf57)、[7302384](https://github.com/Zimkjdv/Model-Atelier/commit/7302384d92bd38d9de3dd43a350b20398cdbad15)、[b699024](https://github.com/Zimkjdv/Model-Atelier/commit/b699024f6885fa0635cc5724be5f5e6259216bdb)；未完成保留 [R02](CHANGELOG.MD#r02)。 素材用途與單張圖生圖已完成；風格／角色 adapter 尚未接入。 |
| <a id="h104"></a>H104<br>2026-09-06 [c651cfa](https://github.com/Zimkjdv/Model-Atelier/commit/c651cfa543d490ba61ef0c25234877c011471c96) | 尚未安裝 checkpoint，非空模型清單、實際模型載入與生成仍待驗證；工作流程提交已實作，生成圖片匯入作品庫尚未實作。 | 已交付，見 [7541feb](https://github.com/Zimkjdv/Model-Atelier/commit/7541feb57d69550c6e35c05bdab6efe1cab8ee1e)、[c651cfa](https://github.com/Zimkjdv/Model-Atelier/commit/c651cfa543d490ba61ef0c25234877c011471c96)、[631834d](https://github.com/Zimkjdv/Model-Atelier/commit/631834d9a45f546ddc9655e681d3cf707640a7f1)、[6578394](https://github.com/Zimkjdv/Model-Atelier/commit/6578394b9c0ff91c9f4403d0cae876b148aa0216)。 本地引擎、checkpoint、提交與作品匯入已分階段完成並實機驗證。 |
| <a id="h105"></a>H105<br>2026-09-06 [c651cfa](https://github.com/Zimkjdv/Model-Atelier/commit/c651cfa543d490ba61ef0c25234877c011471c96) | 安裝 checkpoint 後驗證完整成功生成及實際 VRAM／耗時。 | 已交付，見 [6578394](https://github.com/Zimkjdv/Model-Atelier/commit/6578394b9c0ff91c9f4403d0cae876b148aa0216)。 Pony／RTX 3060 首輪、環境及固定負載量測已完成，不外推其他硬體。 |
| <a id="h106"></a>H106<br>2026-09-06 [c651cfa](https://github.com/Zimkjdv/Model-Atelier/commit/c651cfa543d490ba61ef0c25234877c011471c96) | 輸出圖片匯入平台作品庫、預覽與備份。 | 已交付，見 [631834d](https://github.com/Zimkjdv/Model-Atelier/commit/631834d9a45f546ddc9655e681d3cf707640a7f1)、[bfbae93](https://github.com/Zimkjdv/Model-Atelier/commit/bfbae935974c587ed00f7ed6d58ce79898cf5803)。 作品匯入、預覽、完整流程與失敗紀錄已交付；備份方法見 README。 |
| <a id="h107"></a>H107<br>2026-09-06 [c651cfa](https://github.com/Zimkjdv/Model-Atelier/commit/c651cfa543d490ba61ef0c25234877c011471c96) | 參考圖、LoRA、FLUX 各自的相容工作流程。 | 已交付部分見 [7302384](https://github.com/Zimkjdv/Model-Atelier/commit/7302384d92bd38d9de3dd43a350b20398cdbad15)、[367ae73](https://github.com/Zimkjdv/Model-Atelier/commit/367ae73d8dcfd2926900818410b1bdeba26d6e5a)、[2f8f23e](https://github.com/Zimkjdv/Model-Atelier/commit/2f8f23e28d092ecdda05bd6c78b2381c14a8fe1e)、[7e5680f](https://github.com/Zimkjdv/Model-Atelier/commit/7e5680faf49ab76980493afd9c778f3610c392a9)、[87d277d](https://github.com/Zimkjdv/Model-Atelier/commit/87d277d5716c0c1f3a4307e1b3049d588abe2f95)；未完成保留 [F03](ROADMAP.MD#f03)、[F04](ROADMAP.MD#f04)、[R01](CHANGELOG.MD#r01)、[R02](CHANGELOG.MD#r02)、[R07](CHANGELOG.MD#r07)。 參考圖、LoRA 與 FLUX 各有專用流程；FLUX GPU／擴充能力及其他參考流程仍待實測。 |
| <a id="h108"></a>H108<br>2026-09-06 [631834d](https://github.com/Zimkjdv/Model-Atelier/commit/631834d9a45f546ddc9655e681d3cf707640a7f1) | 尚未安裝 checkpoint，非空模型清單、實際模型載入與生成仍待驗證；工作流程提交及作品庫匯入已實作，已用測試圖片驗證讀取流程。 | 已交付，見 [7541feb](https://github.com/Zimkjdv/Model-Atelier/commit/7541feb57d69550c6e35c05bdab6efe1cab8ee1e)、[c651cfa](https://github.com/Zimkjdv/Model-Atelier/commit/c651cfa543d490ba61ef0c25234877c011471c96)、[631834d](https://github.com/Zimkjdv/Model-Atelier/commit/631834d9a45f546ddc9655e681d3cf707640a7f1)、[6578394](https://github.com/Zimkjdv/Model-Atelier/commit/6578394b9c0ff91c9f4403d0cae876b148aa0216)。 本地引擎、checkpoint、提交與作品匯入已分階段完成並實機驗證。 |
| <a id="h109"></a>H109<br>2026-09-06 [631834d](https://github.com/Zimkjdv/Model-Atelier/commit/631834d9a45f546ddc9655e681d3cf707640a7f1) | 安裝 checkpoint 後驗證「生成 → 完成 → 匯入作品」完整實機流程。 | 已交付，見 [7541feb](https://github.com/Zimkjdv/Model-Atelier/commit/7541feb57d69550c6e35c05bdab6efe1cab8ee1e)、[c651cfa](https://github.com/Zimkjdv/Model-Atelier/commit/c651cfa543d490ba61ef0c25234877c011471c96)、[631834d](https://github.com/Zimkjdv/Model-Atelier/commit/631834d9a45f546ddc9655e681d3cf707640a7f1)、[6578394](https://github.com/Zimkjdv/Model-Atelier/commit/6578394b9c0ff91c9f4403d0cae876b148aa0216)。 本地引擎、checkpoint、提交與作品匯入已分階段完成並實機驗證。 |
| <a id="h110"></a>H110<br>2026-09-06 [631834d](https://github.com/Zimkjdv/Model-Atelier/commit/631834d9a45f546ddc9655e681d3cf707640a7f1) | 作品收藏、備註、封存與一鍵載入創作設定。 | 已交付部分見 [9ca7c22](https://github.com/Zimkjdv/Model-Atelier/commit/9ca7c221012f33c0dc96ba604816b77b0393c860)、[f167b9a](https://github.com/Zimkjdv/Model-Atelier/commit/f167b9ad4d04874098a4118d02d13042741eaca2)；未完成保留 [V03](CHANGELOG.MD#v03)。 作品整理與原設定載入已交付，桌面已驗證；窄視窗整理驗收未完成。 |
| <a id="h111"></a>H111<br>2026-10-02 [f167b9a](https://github.com/Zimkjdv/Model-Atelier/commit/f167b9ad4d04874098a4118d02d13042741eaca2) | 作品收藏、備註與封存。 | 已交付部分見 [9ca7c22](https://github.com/Zimkjdv/Model-Atelier/commit/9ca7c221012f33c0dc96ba604816b77b0393c860)、[f167b9a](https://github.com/Zimkjdv/Model-Atelier/commit/f167b9ad4d04874098a4118d02d13042741eaca2)；未完成保留 [V03](CHANGELOG.MD#v03)。 作品整理與原設定載入已交付，桌面已驗證；窄視窗整理驗收未完成。 |
| <a id="h112"></a>H112<br>2026-10-02 [f167b9a](https://github.com/Zimkjdv/Model-Atelier/commit/f167b9ad4d04874098a4118d02d13042741eaca2) | 尚無 checkpoint；實際 GPU 出圖、P1 完整實機驗收與 P2 模型整合仍待驗證。 | 已交付，見 [7541feb](https://github.com/Zimkjdv/Model-Atelier/commit/7541feb57d69550c6e35c05bdab6efe1cab8ee1e)、[c651cfa](https://github.com/Zimkjdv/Model-Atelier/commit/c651cfa543d490ba61ef0c25234877c011471c96)、[631834d](https://github.com/Zimkjdv/Model-Atelier/commit/631834d9a45f546ddc9655e681d3cf707640a7f1)、[6578394](https://github.com/Zimkjdv/Model-Atelier/commit/6578394b9c0ff91c9f4403d0cae876b148aa0216)。 本地引擎、checkpoint、提交與作品匯入已分階段完成並實機驗證。 |
| <a id="h113"></a>H113<br>2026-10-02 [8fcc946](https://github.com/Zimkjdv/Model-Atelier/commit/8fcc9460fe03f158577cea09deba2f91e43a81d9) | 執行中停止仍需另行驗證引擎語意，避免中斷其他任務。 | 已交付，見 [8fcc946](https://github.com/Zimkjdv/Model-Atelier/commit/8fcc9460fe03f158577cea09deba2f91e43a81d9)、[2d64ec1](https://github.com/Zimkjdv/Model-Atelier/commit/2d64ec13836c3ecf5b830d74865357056271fbb0)。 排隊取消及指定執行中任務停止已交付，後者具 RTX 3060 驗收。 |
| <a id="h114"></a>H114<br>2026-10-03 [6cb5e1c](https://github.com/Zimkjdv/Model-Atelier/commit/6cb5e1ce5d4be67f3529c4d412a38312d888a2dd) | 訓練及 RTX 4080 的實測資源紀錄仍待驗證。 | 已交付部分見 [6578394](https://github.com/Zimkjdv/Model-Atelier/commit/6578394b9c0ff91c9f4403d0cae876b148aa0216)、[df8b141](https://github.com/Zimkjdv/Model-Atelier/commit/df8b14155b8e03fa42889d84ce6e8b28e7595b40)；未完成保留 [E04](ROADMAP.MD#e04)、[E02](ROADMAP.MD#e02)、[T01](CHANGELOG.MD#t01)、[T03](CHANGELOG.MD#t03)。 已有 RTX 3060 推論量測；訓練與 RTX 4080 不能借用該結果。 |
| <a id="h115"></a>H115<br>2026-10-03 [87647e9](https://github.com/Zimkjdv/Model-Atelier/commit/87647e9f58ebe5b71dabc4f32f1ea2e217b9ecb7) | 無可用裝置需引擎提供可靠證據，不能只憑空裝置清單推定；P0 此部分保持待驗證。 | 已交付部分見 [87647e9](https://github.com/Zimkjdv/Model-Atelier/commit/87647e9f58ebe5b71dabc4f32f1ea2e217b9ecb7)；未完成保留 [E01](CHANGELOG.MD#e01)。 缺必要節點等檢查已完成；無裝置判斷仍需可靠引擎證據。 |
| <a id="h116"></a>H116<br>2026-10-04 [cbc0ee1](https://github.com/Zimkjdv/Model-Atelier/commit/cbc0ee10748e9c763477b87f451e32587a752efc) | FLUX.1 的確切公開權重變體。 | 已交付，見 [5bf331f](https://github.com/Zimkjdv/Model-Atelier/commit/5bf331f543250fd5a0f88a71424f8eda7368eb96)。 已固定 FLUX.1 [schnell] 變體；安裝與實機驗收另列 F01–F04。 |
| <a id="h117"></a>H117<br>2026-10-04 [7595335](https://github.com/Zimkjdv/Model-Atelier/commit/7595335697dc15cef43617b2ef82414f914dc2a6) | 評估多個 LoRA 的組合支援及其他畫風 LoRA 的品質。 | 已交付部分見 [7595335](https://github.com/Zimkjdv/Model-Atelier/commit/7595335697dc15cef43617b2ef82414f914dc2a6)、[367ae73](https://github.com/Zimkjdv/Model-Atelier/commit/367ae73d8dcfd2926900818410b1bdeba26d6e5a)、[4287634](https://github.com/Zimkjdv/Model-Atelier/commit/428763421fe3a2d3b3b5de269a9e7e02a3adfe5f)；未完成保留 [L01](CHANGELOG.MD#l01)。 單一與有序多 LoRA 載入／還原已完成；其他組合及畫風品質仍待評估。 |
| <a id="h118"></a>H118<br>2026-10-05 [5bf331f](https://github.com/Zimkjdv/Model-Atelier/commit/5bf331f543250fd5a0f88a71424f8eda7368eb96) | 驗證實際推論精度、卸載、GPU／RAM 需求與各元件上游授權；來源選型不代表權重已安裝或可生成。 | 已交付部分見 [5bf331f](https://github.com/Zimkjdv/Model-Atelier/commit/5bf331f543250fd5a0f88a71424f8eda7368eb96)、[c7008c6](https://github.com/Zimkjdv/Model-Atelier/commit/c7008c6a4c503bca40658b99780ccf756f533513)；未完成保留 [F01](ROADMAP.MD#f01)、[F02](ROADMAP.MD#f02)。 固定元件與預檢已交付，尚不能視為已安裝或已驗證實際精度／資源。 |
| <a id="h119"></a>H119<br>2026-10-05 [7302384](https://github.com/Zimkjdv/Model-Atelier/commit/7302384d92bd38d9de3dd43a350b20398cdbad15) | 逐項評估圖片生成圖片、局部編輯及結構參考流程；單張 checkpoint 圖生圖後端與 Pony／RTX 3060 已驗證，其他流程仍待整合。 | 已交付部分見 [7302384](https://github.com/Zimkjdv/Model-Atelier/commit/7302384d92bd38d9de3dd43a350b20398cdbad15)、[7e5680f](https://github.com/Zimkjdv/Model-Atelier/commit/7e5680faf49ab76980493afd9c778f3610c392a9)、[87d277d](https://github.com/Zimkjdv/Model-Atelier/commit/87d277d5716c0c1f3a4307e1b3049d588abe2f95)、[3dc10b8](https://github.com/Zimkjdv/Model-Atelier/commit/3dc10b8c2d71883b1514c85db9f353c48476e108)；未完成保留 [R01](CHANGELOG.MD#r01)、[R02](CHANGELOG.MD#r02)、[R03](CHANGELOG.MD#r03)。 單張圖生圖、checkpoint 局部編輯及 Canny 已接入；其他結構、adapter 與修補品質仍待評估。 |
| <a id="h120"></a>H120<br>2026-10-05 [b699024](https://github.com/Zimkjdv/Model-Atelier/commit/b699024f6885fa0635cc5724be5f5e6259216bdb) | 逐項評估圖片生成圖片、局部編輯及結構參考流程；單張 checkpoint 圖生圖後端／介面與 Pony／RTX 3060 已驗證，其他流程仍待整合。 | 已交付部分見 [7302384](https://github.com/Zimkjdv/Model-Atelier/commit/7302384d92bd38d9de3dd43a350b20398cdbad15)、[7e5680f](https://github.com/Zimkjdv/Model-Atelier/commit/7e5680faf49ab76980493afd9c778f3610c392a9)、[87d277d](https://github.com/Zimkjdv/Model-Atelier/commit/87d277d5716c0c1f3a4307e1b3049d588abe2f95)、[3dc10b8](https://github.com/Zimkjdv/Model-Atelier/commit/3dc10b8c2d71883b1514c85db9f353c48476e108)；未完成保留 [R01](CHANGELOG.MD#r01)、[R02](CHANGELOG.MD#r02)、[R03](CHANGELOG.MD#r03)。 單張圖生圖、checkpoint 局部編輯及 Canny 已接入；其他結構、adapter 與修補品質仍待評估。 |
| <a id="h121"></a>H121<br>2026-10-08 [e3ef1d2](https://github.com/Zimkjdv/Model-Atelier/commit/e3ef1d2261e0c47947b39930cea61312d7d2890b) | 更多 seed、模型及作者提示格式的品質比較；其他畫風、參考引導／角色鎖定仍待驗證。 | 已交付部分見 [e3ef1d2](https://github.com/Zimkjdv/Model-Atelier/commit/e3ef1d2261e0c47947b39930cea61312d7d2890b)；未完成保留 [R05](CHANGELOG.MD#r05)、[R02](CHANGELOG.MD#r02)、[V04](CHANGELOG.MD#v04)。 固定兩模型四案例 GPU 完成；更多 seed、作者提示及角色／畫風品質不被涵蓋，新的 UI 仍需補驗。 |
| <a id="h122"></a>H122<br>2026-10-08 [8d9aa15](https://github.com/Zimkjdv/Model-Atelier/commit/8d9aa15a2dc10a34b3a817c03716bbc61b190bd3) | 更多強度／seed 的實際畫風品質仍待評估，不能把參數比較支援當成品質驗證。 | 已交付部分見 [79ea409](https://github.com/Zimkjdv/Model-Atelier/commit/79ea409438830a57c8b86f9672a952ec6cee0bfa)；未完成保留 [L01](CHANGELOG.MD#l01)、[R05](CHANGELOG.MD#r05)。 已有固定強度／兩 seed 比較，不能替代廣泛畫風品質。 |
| <a id="h123"></a>H123<br>2026-10-08 [ea31058](https://github.com/Zimkjdv/Model-Atelier/commit/ea310584c69d5a3416d45a0d6feb5498c6aa5d36) | 不同 denoise／模型的 GPU 品質與新 UI 實機驗收待進行；本輪沒有新增 GPU 任務或正式資料。局部編輯、結構／畫風 adapter 仍待整合。 | 已交付部分見 [4df715a](https://github.com/Zimkjdv/Model-Atelier/commit/4df715a4f6fe8461d5d53a982dc630089778ed54)、[17440f4](https://github.com/Zimkjdv/Model-Atelier/commit/17440f47e2a3f263fa4e3d28399cbb4312c7f571)、[7e5680f](https://github.com/Zimkjdv/Model-Atelier/commit/7e5680faf49ab76980493afd9c778f3610c392a9)；未完成保留 [R05](CHANGELOG.MD#r05)、[R01](CHANGELOG.MD#r01)、[R02](CHANGELOG.MD#r02)、[R03](CHANGELOG.MD#r03)。 兩模型 0.3／0.6 denoise、結果介面與報告下載已補驗；更多素材／模型／adapter／修補品質待辦保留。 |
| <a id="h124"></a>H124<br>2026-10-08 [eab5e76](https://github.com/Zimkjdv/Model-Atelier/commit/eab5e76a5babe9d7c10e1289d3c1234e4fb8afb6) | 比較結果與方案自動關聯、更多模型／流程／參數軸待規劃，不提供自動批次與品質評分。 | 已交付部分見 [0ed66ce](https://github.com/Zimkjdv/Model-Atelier/commit/0ed66ce82acafbc0e8337663b2a0bae17a927043)、[8d9aa15](https://github.com/Zimkjdv/Model-Atelier/commit/8d9aa15a2dc10a34b3a817c03716bbc61b190bd3)、[ea31058](https://github.com/Zimkjdv/Model-Atelier/commit/ea310584c69d5a3416d45a0d6feb5498c6aa5d36)、[2a64a9a](https://github.com/Zimkjdv/Model-Atelier/commit/2a64a9a41a7b4c5a1a6f0fdb6e748cf63bd96930)；未完成保留 [R06](CHANGELOG.MD#r06)、[R07](CHANGELOG.MD#r07)。 有界預覽、既有參數軸與關聯已交付；擴充工作流程／參數另評估。自動批次與自動品質評分是排除範圍。 |
| <a id="h125"></a>H125<br>2026-10-08 [eab5e76](https://github.com/Zimkjdv/Model-Atelier/commit/eab5e76a5babe9d7c10e1289d3c1234e4fb8afb6) | UI 工具 sandbox 啟動失敗，本輪瀏覽器／原生下載／窄視窗驗收未完成。更多 GPU 品質、局部編輯／adapter、FLUX 安裝與 RTX 4080 仍待完成。 | 已交付部分見 [17440f4](https://github.com/Zimkjdv/Model-Atelier/commit/17440f47e2a3f263fa4e3d28399cbb4312c7f571)；未完成保留 [R05](CHANGELOG.MD#r05)、[R02](CHANGELOG.MD#r02)、[R03](CHANGELOG.MD#r03)、[F01](ROADMAP.MD#f01)、[F03](ROADMAP.MD#f03)、[E02](ROADMAP.MD#e02)。 比較方案實際下載、匯入、精確載入與 390px 已補驗；其他範圍仍未完成。 |
| <a id="h126"></a>H126<br>2026-10-08 [79ea409](https://github.com/Zimkjdv/Model-Atelier/commit/79ea409438830a57c8b86f9672a952ec6cee0bfa) | 其他畫風、更廣泛品質、RTX 4080 與訓練資源仍待驗證。 | 已交付部分見 [79ea409](https://github.com/Zimkjdv/Model-Atelier/commit/79ea409438830a57c8b86f9672a952ec6cee0bfa)；未完成保留 [L01](CHANGELOG.MD#l01)、[R05](CHANGELOG.MD#r05)、[E02](ROADMAP.MD#e02)、[E04](ROADMAP.MD#e04)、[T01](CHANGELOG.MD#t01)、[T03](CHANGELOG.MD#t03)。 固定強度品質比較已完成，未外推其他畫風、硬體或訓練。 |
| <a id="h127"></a>H127<br>2026-10-08 [2a64a9a](https://github.com/Zimkjdv/Model-Atelier/commit/2a64a9a41a7b4c5a1a6f0fdb6e748cf63bd96930) | 前端關聯操作與結果查看接續第三項；不提供自動批次、品質評分或反向補關聯。 | 已交付，見 [9abddcf](https://github.com/Zimkjdv/Model-Atelier/commit/9abddcf5dec70d4ac0661fdd45e53dddbf5b1c2d)、[17440f4](https://github.com/Zimkjdv/Model-Atelier/commit/17440f47e2a3f263fa4e3d28399cbb4312c7f571)。 前端明確關聯及結果查看／報告介面已補驗；自動批次、品質評分及反向補關聯不在範圍。 |
| <a id="h128"></a>H128<br>2026-10-08 [9abddcf](https://github.com/Zimkjdv/Model-Atelier/commit/9abddcf5dec70d4ac0661fdd45e53dddbf5b1c2d) | 更多模型／流程／參數軸待規劃，不提供自動批次與品質評分。 | 已交付部分見 [0ed66ce](https://github.com/Zimkjdv/Model-Atelier/commit/0ed66ce82acafbc0e8337663b2a0bae17a927043)、[8d9aa15](https://github.com/Zimkjdv/Model-Atelier/commit/8d9aa15a2dc10a34b3a817c03716bbc61b190bd3)、[ea31058](https://github.com/Zimkjdv/Model-Atelier/commit/ea310584c69d5a3416d45a0d6feb5498c6aa5d36)、[2a64a9a](https://github.com/Zimkjdv/Model-Atelier/commit/2a64a9a41a7b4c5a1a6f0fdb6e748cf63bd96930)；未完成保留 [R06](CHANGELOG.MD#r06)、[R07](CHANGELOG.MD#r07)。 有界預覽、既有參數軸與關聯已交付；擴充工作流程／參數另評估。自動批次與自動品質評分是排除範圍。 |
| <a id="h129"></a>H129<br>2026-10-08 [9abddcf](https://github.com/Zimkjdv/Model-Atelier/commit/9abddcf5dec70d4ac0661fdd45e53dddbf5b1c2d) | 瀏覽器工具仍因 Windows sandbox `helper_unknown_error` 無法啟動，畫面點擊、實際下載及窄視窗未驗收；其他畫風、更廣泛品質、局部編輯／adapter、FLUX 安裝及 RTX 4080 仍待完成。 | 已交付部分見 [17440f4](https://github.com/Zimkjdv/Model-Atelier/commit/17440f47e2a3f263fa4e3d28399cbb4312c7f571)；未完成保留 [L01](CHANGELOG.MD#l01)、[R05](CHANGELOG.MD#r05)、[R02](CHANGELOG.MD#r02)、[R03](CHANGELOG.MD#r03)、[F01](ROADMAP.MD#f01)、[F03](ROADMAP.MD#f03)、[E02](ROADMAP.MD#e02)。 比較結果、原圖縮圖、報告下載與窄視窗已補驗；其他畫風／模型／硬體不能借用。 |
| <a id="h130"></a>H130<br>2026-10-09 [7e5680f](https://github.com/Zimkjdv/Model-Atelier/commit/7e5680faf49ab76980493afd9c778f3610c392a9) | 遮罩操作介面及 RTX 3060 實機驗收接續開發；比較／一般草稿／交換 JSON 不借用舊格式丟棄遮罩。 | 已交付部分見 [ddac4d6](https://github.com/Zimkjdv/Model-Atelier/commit/ddac4d6c27c1cfe3010fcd49b967dbe6d9e6c893)、[3e06576](https://github.com/Zimkjdv/Model-Atelier/commit/3e06576576d153c2b4cd1b4105fdbe95b2394d3f)、[962216b](https://github.com/Zimkjdv/Model-Atelier/commit/962216ba12f73b800bd500904d91526bbe499a52)；未完成保留 [R07](CHANGELOG.MD#r07)、[V01](ROADMAP.MD#v01)、[V02](CHANGELOG.MD#v02)。 遮罩工作台與固定 GPU 驗收已完成；真實筆刷／觸控及 pending 補驗仍缺，舊草稿／交換／比較格式維持拒絕。 |
| <a id="h131"></a>H131<br>2026-10-09 [ddac4d6](https://github.com/Zimkjdv/Model-Atelier/commit/ddac4d6c27c1cfe3010fcd49b967dbe6d9e6c893) | 瀏覽器工具仍因 sandbox helper 啟動失敗，實際畫面操作／下載／窄視窗未驗收；RTX 3060 接續第三項。 | 已交付部分見 [3e06576](https://github.com/Zimkjdv/Model-Atelier/commit/3e06576576d153c2b4cd1b4105fdbe95b2394d3f)、[962216b](https://github.com/Zimkjdv/Model-Atelier/commit/962216ba12f73b800bd500904d91526bbe499a52)；未完成保留 [V01](ROADMAP.MD#v01)。 RTX 3060、預覽、歷史下載及 390px 已後續補驗；筆刷／觸控不能視為已驗證。 |
| <a id="h132"></a>H132<br>2026-10-09 [3e06576](https://github.com/Zimkjdv/Model-Atelier/commit/3e06576576d153c2b4cd1b4105fdbe95b2394d3f) | 逐項評估圖片生成圖片、局部編輯及結構參考流程；單張圖生圖與 checkpoint 局部編輯已完成後端／介面及固定 RTX 3060 驗證，結構參考與修補品質改善仍待完成。 | 已交付部分見 [7302384](https://github.com/Zimkjdv/Model-Atelier/commit/7302384d92bd38d9de3dd43a350b20398cdbad15)、[7e5680f](https://github.com/Zimkjdv/Model-Atelier/commit/7e5680faf49ab76980493afd9c778f3610c392a9)、[87d277d](https://github.com/Zimkjdv/Model-Atelier/commit/87d277d5716c0c1f3a4307e1b3049d588abe2f95)、[3dc10b8](https://github.com/Zimkjdv/Model-Atelier/commit/3dc10b8c2d71883b1514c85db9f353c48476e108)；未完成保留 [R01](CHANGELOG.MD#r01)、[R02](CHANGELOG.MD#r02)、[R03](CHANGELOG.MD#r03)。 單張圖生圖、checkpoint 局部編輯及 Canny 已接入；其他結構、adapter 與修補品質仍待評估。 |
| <a id="h133"></a>H133<br>2026-10-09 [3e06576](https://github.com/Zimkjdv/Model-Atelier/commit/3e06576576d153c2b4cd1b4105fdbe95b2394d3f) | 瀏覽器工具仍無法啟動，實際筆刷／觸控／下載／窄視窗待驗收；羽化／邊界融合、專用 inpainting checkpoint、更多 seed、ControlNet／adapter、FLUX 權重与 RTX 4080 保留後續工作。 | 已交付部分見 [962216b](https://github.com/Zimkjdv/Model-Atelier/commit/962216ba12f73b800bd500904d91526bbe499a52)、[7b03393](https://github.com/Zimkjdv/Model-Atelier/commit/7b033934fa75bba06990af37c59c06017feda2e8)；未完成保留 [V01](ROADMAP.MD#v01)、[V02](CHANGELOG.MD#v02)、[R03](CHANGELOG.MD#r03)、[R05](CHANGELOG.MD#r05)、[R01](CHANGELOG.MD#r01)、[R02](CHANGELOG.MD#r02)、[F01](ROADMAP.MD#f01)、[F03](ROADMAP.MD#f03)、[E02](ROADMAP.MD#e02)。 羽化、Canny 及固定 GPU／歷史介面已交付；實際筆刷觸控與其他範圍仍待補驗。 |
| <a id="h134"></a>H134<br>2026-10-09 [87d277d](https://github.com/Zimkjdv/Model-Atelier/commit/87d277d5716c0c1f3a4307e1b3049d588abe2f95) | 專用工作台與固定 SDXL Canny／RTX 3060 接續第二／三項；未宣稱畫風／角色鎖定或實機品質。 | 已交付，見 [8c61d4d](https://github.com/Zimkjdv/Model-Atelier/commit/8c61d4df91774feaba35cc4b1d7f1f2b26de3422)、[7b03393](https://github.com/Zimkjdv/Model-Atelier/commit/7b033934fa75bba06990af37c59c06017feda2e8)、[ab17b82](https://github.com/Zimkjdv/Model-Atelier/commit/ab17b82dd9092f9abb35a7cc6ea635877c3f61bd)。 專用工作台、固定 SDXL／RTX 3060 與後續瀏覽器／窄視窗已驗證。 |
| <a id="h135"></a>H135<br>2026-10-09 [8c61d4d](https://github.com/Zimkjdv/Model-Atelier/commit/8c61d4df91774feaba35cc4b1d7f1f2b26de3422) | 瀏覽器工具本輪仍因 Node kernel 啟動失敗，畫面操作與窄視窗待驗收；固定控制權重／RTX 3060 接續第三項。 | 已交付，見 [8c61d4d](https://github.com/Zimkjdv/Model-Atelier/commit/8c61d4df91774feaba35cc4b1d7f1f2b26de3422)、[7b03393](https://github.com/Zimkjdv/Model-Atelier/commit/7b033934fa75bba06990af37c59c06017feda2e8)、[ab17b82](https://github.com/Zimkjdv/Model-Atelier/commit/ab17b82dd9092f9abb35a7cc6ea635877c3f61bd)。 專用工作台、固定 SDXL／RTX 3060 與後續瀏覽器／窄視窗已驗證。 |
| <a id="h136"></a>H136<br>2026-10-09 [7b03393](https://github.com/Zimkjdv/Model-Atelier/commit/7b033934fa75bba06990af37c59c06017feda2e8) | 瀏覽器工具仍無法啟動，畫面／下載／窄視窗未驗收；下一批評估邊緣預覽／保存、更多 seed／強度、depth／pose／adapter、專用局部編輯／羽化、FLUX 安裝容量及 RTX 4080。 | 已交付部分見 [ab17b82](https://github.com/Zimkjdv/Model-Atelier/commit/ab17b82dd9092f9abb35a7cc6ea635877c3f61bd)、[e992b00](https://github.com/Zimkjdv/Model-Atelier/commit/e992b00a990fb531516ba65a093e6a4aa5ac43bc)、[962216b](https://github.com/Zimkjdv/Model-Atelier/commit/962216ba12f73b800bd500904d91526bbe499a52)；未完成保留 [R05](CHANGELOG.MD#r05)、[R01](CHANGELOG.MD#r01)、[R02](CHANGELOG.MD#r02)、[R03](CHANGELOG.MD#r03)、[F01](ROADMAP.MD#f01)、[F03](ROADMAP.MD#f03)、[E02](ROADMAP.MD#e02)。 Canny 邊緣保存／預覽／下載／窄視窗、兩 seed／強度與羽化已後續完成。 |
| <a id="h137"></a>H137<br>2026-10-09 [3dc10b8](https://github.com/Zimkjdv/Model-Atelier/commit/3dc10b8c2d71883b1514c85db9f353c48476e108) | 逐項評估圖片生成圖片、局部編輯及結構參考流程；單張圖生圖與 checkpoint 局部編輯已完成後端／介面及固定 RTX 3060 驗證，Canny 結構已完成固定整合，其他結構流程與修補品質改善仍待完成。 | 已交付部分見 [7302384](https://github.com/Zimkjdv/Model-Atelier/commit/7302384d92bd38d9de3dd43a350b20398cdbad15)、[7e5680f](https://github.com/Zimkjdv/Model-Atelier/commit/7e5680faf49ab76980493afd9c778f3610c392a9)、[87d277d](https://github.com/Zimkjdv/Model-Atelier/commit/87d277d5716c0c1f3a4307e1b3049d588abe2f95)、[3dc10b8](https://github.com/Zimkjdv/Model-Atelier/commit/3dc10b8c2d71883b1514c85db9f353c48476e108)；未完成保留 [R01](CHANGELOG.MD#r01)、[R02](CHANGELOG.MD#r02)、[R03](CHANGELOG.MD#r03)。 單張圖生圖、checkpoint 局部編輯及 Canny 已接入；其他結構、adapter 與修補品質仍待評估。 |
| <a id="h138"></a>H138<br>2026-10-09 [3dc10b8](https://github.com/Zimkjdv/Model-Atelier/commit/3dc10b8c2d71883b1514c85db9f353c48476e108) | 介面与两 seed／两強度 RTX 3060 比較接續第二／三項。 | 已交付，見 [c8b1cf5](https://github.com/Zimkjdv/Model-Atelier/commit/c8b1cf578d5a61faa33ef5bafd1d66d1b6d85ccf)、[e992b00](https://github.com/Zimkjdv/Model-Atelier/commit/e992b00a990fb531516ba65a093e6a4aa5ac43bc)、[ab17b82](https://github.com/Zimkjdv/Model-Atelier/commit/ab17b82dd9092f9abb35a7cc6ea635877c3f61bd)。 介面、兩 seed／兩強度 GPU 與後續瀏覽器驗收已完成。 |
| <a id="h139"></a>H139<br>2026-10-09 [c8b1cf5](https://github.com/Zimkjdv/Model-Atelier/commit/c8b1cf578d5a61faa33ef5bafd1d66d1b6d85ccf) | 介面已於第二項完成；兩 seed／兩強度 RTX 3060 比較接續第三項。 | 已交付，見 [c8b1cf5](https://github.com/Zimkjdv/Model-Atelier/commit/c8b1cf578d5a61faa33ef5bafd1d66d1b6d85ccf)、[e992b00](https://github.com/Zimkjdv/Model-Atelier/commit/e992b00a990fb531516ba65a093e6a4aa5ac43bc)、[ab17b82](https://github.com/Zimkjdv/Model-Atelier/commit/ab17b82dd9092f9abb35a7cc6ea635877c3f61bd)。 介面、兩 seed／兩強度 GPU 與後續瀏覽器驗收已完成。 |
| <a id="h140"></a>H140<br>2026-10-09 [c8b1cf5](https://github.com/Zimkjdv/Model-Atelier/commit/c8b1cf578d5a61faa33ef5bafd1d66d1b6d85ccf) | 瀏覽器工具 Node kernel 無法啟動，畫面操作／窄視窗仍待驗收；兩 seed／兩強度 RTX 3060 接續第三項。 | 已交付，見 [c8b1cf5](https://github.com/Zimkjdv/Model-Atelier/commit/c8b1cf578d5a61faa33ef5bafd1d66d1b6d85ccf)、[e992b00](https://github.com/Zimkjdv/Model-Atelier/commit/e992b00a990fb531516ba65a093e6a4aa5ac43bc)、[ab17b82](https://github.com/Zimkjdv/Model-Atelier/commit/ab17b82dd9092f9abb35a7cc6ea635877c3f61bd)。 介面、兩 seed／兩強度 GPU 與後續瀏覽器驗收已完成。 |
| <a id="h141"></a>H141<br>2026-10-09 [e992b00](https://github.com/Zimkjdv/Model-Atelier/commit/e992b00a990fb531516ba65a093e6a4aa5ac43bc) | 瀏覽器畫面／窄視窗操作、未提交設定即時邊緣預覽、Pony v2／其他 LoRA、depth／pose／adapter、局部編輯品質改善、FLUX 安裝容量與 RTX 4080 接續評估。 | 已交付部分見 [ab17b82](https://github.com/Zimkjdv/Model-Atelier/commit/ab17b82dd9092f9abb35a7cc6ea635877c3f61bd)；未完成保留 [R04](CHANGELOG.MD#r04)、[R01](CHANGELOG.MD#r01)、[R02](CHANGELOG.MD#r02)、[R03](CHANGELOG.MD#r03)、[F01](ROADMAP.MD#f01)、[F03](ROADMAP.MD#f03)、[E02](ROADMAP.MD#e02)。 Canny v2 邊緣介面、送出前 CPU 預覽及窄視窗已補驗；Pony v2 組合等其餘內容仍待實測。 |
| <a id="h142"></a>H142<br>2026-10-22 [b9bd7d7](https://github.com/Zimkjdv/Model-Atelier/commit/b9bd7d74c256c2f416d19d1cc3f4967f9f4a8676) | 工作台預覽／新參數／pending 相容與 RTX 3060 比較依序接續第二／三項。詳見 docs/inpaint-feather.md。 | 已交付部分見 [2c43e47](https://github.com/Zimkjdv/Model-Atelier/commit/2c43e470723d05725e6f78c0b2d131696bd0bae1)、[962216b](https://github.com/Zimkjdv/Model-Atelier/commit/962216ba12f73b800bd500904d91526bbe499a52)；未完成保留 [V02](CHANGELOG.MD#v02)。 新工作台、預覽與 GPU 已完成；pending 邏輯測試已通過，真實遺失回應仍未注入驗收。 |
| <a id="h143"></a>H143<br>2026-10-22 [2c43e47](https://github.com/Zimkjdv/Model-Atelier/commit/2c43e470723d05725e6f78c0b2d131696bd0bae1) | 真實 RTX 3060 羽化比較及新歷史介面核對接續第三項；筆刷觸控尚未重驗。 | 已交付部分見 [962216b](https://github.com/Zimkjdv/Model-Atelier/commit/962216ba12f73b800bd500904d91526bbe499a52)；未完成保留 [V01](ROADMAP.MD#v01)。 羽化 GPU 與新歷史介面已核對；筆刷觸控未重驗。 |
| <a id="h144"></a>H144<br>2026-10-22 [962216b](https://github.com/Zimkjdv/Model-Atelier/commit/962216ba12f73b800bd500904d91526bbe499a52) | P5 固定 BFL 權重需先取得來源存取；P6 專用 inpainting 模型／其他半徑與 seed、depth／pose／adapter、Canny 未提交即時預覽及 RTX 4080 接續評估。 | 已交付部分見 [ab17b82](https://github.com/Zimkjdv/Model-Atelier/commit/ab17b82dd9092f9abb35a7cc6ea635877c3f61bd)；未完成保留 [F01](ROADMAP.MD#f01)、[F03](ROADMAP.MD#f03)、[R03](CHANGELOG.MD#r03)、[R05](CHANGELOG.MD#r05)、[R01](CHANGELOG.MD#r01)、[R02](CHANGELOG.MD#r02)、[E02](ROADMAP.MD#e02)。 Canny 送出前 CPU 預覽已完成；FLUX 存取、修補品質、其他參考與硬體仍待驗證。 |
| <a id="h145"></a>H145<br>2026-10-22 [ab17b82](https://github.com/Zimkjdv/Model-Atelier/commit/ab17b82dd9092f9abb35a7cc6ea635877c3f61bd) | 更多模型／seed／強度、depth／pose／adapter、專用局部編輯品質、FLUX 來源存取及 RTX 4080 待評估；邊緣預覽／保存、羽化與瀏覽器畫面／下載／窄視窗已於後續完成。 | 已交付部分見 [ab17b82](https://github.com/Zimkjdv/Model-Atelier/commit/ab17b82dd9092f9abb35a7cc6ea635877c3f61bd)；未完成保留 [R05](CHANGELOG.MD#r05)、[R01](CHANGELOG.MD#r01)、[R02](CHANGELOG.MD#r02)、[R03](CHANGELOG.MD#r03)、[F01](ROADMAP.MD#f01)、[F03](ROADMAP.MD#f03)、[E02](ROADMAP.MD#e02)。 邊緣保存／預覽、羽化、歷史下載及窄視窗已完成，其餘保留。 |
| <a id="h146"></a>H146<br>2026-10-22 [ab17b82](https://github.com/Zimkjdv/Model-Atelier/commit/ab17b82dd9092f9abb35a7cc6ea635877c3f61bd) | Pony v2／其他 LoRA、depth／pose／adapter、局部編輯品質改善、FLUX 安裝容量與 RTX 4080 接續評估。 | 未完成保留 [R04](CHANGELOG.MD#r04)、[R01](CHANGELOG.MD#r01)、[R02](CHANGELOG.MD#r02)、[R03](CHANGELOG.MD#r03)、[F01](ROADMAP.MD#f01)、[F03](ROADMAP.MD#f03)、[E02](ROADMAP.MD#e02)。 |
| <a id="h147"></a>H147<br>2026-10-22 [ab17b82](https://github.com/Zimkjdv/Model-Atelier/commit/ab17b82dd9092f9abb35a7cc6ea635877c3f61bd) | P5 固定 BFL 權重需先取得來源存取；P6 專用 inpainting 模型／其他半徑與 seed、depth／pose／adapter及 RTX 4080 接續評估；Canny 送出前 CPU 預覽已於後續完成。 | 已交付部分見 [ab17b82](https://github.com/Zimkjdv/Model-Atelier/commit/ab17b82dd9092f9abb35a7cc6ea635877c3f61bd)；未完成保留 [F01](ROADMAP.MD#f01)、[F03](ROADMAP.MD#f03)、[R03](CHANGELOG.MD#r03)、[R05](CHANGELOG.MD#r05)、[R01](CHANGELOG.MD#r01)、[R02](CHANGELOG.MD#r02)、[E02](ROADMAP.MD#e02)。 Canny 送出前 CPU 預覽已完成；FLUX 存取、修補品質、其他參考與硬體仍待驗證。 |
| <a id="h148"></a>H148<br>2026-10-22 [4df715a](https://github.com/Zimkjdv/Model-Atelier/commit/4df715a4f6fe8461d5d53a982dc630089778ed54) | 更廣泛 denoise／素材／模型品質、結構／畫風 adapter 待評估；2026-10-22 已完成 Pony／Animagine 各 0.3／0.6 圖生圖及比較關聯 GPU 驗收，瀏覽器結果介面接續報告匯出項目。 | 已交付部分見 [4df715a](https://github.com/Zimkjdv/Model-Atelier/commit/4df715a4f6fe8461d5d53a982dc630089778ed54)、[17440f4](https://github.com/Zimkjdv/Model-Atelier/commit/17440f47e2a3f263fa4e3d28399cbb4312c7f571)、[7e5680f](https://github.com/Zimkjdv/Model-Atelier/commit/7e5680faf49ab76980493afd9c778f3610c392a9)；未完成保留 [R05](CHANGELOG.MD#r05)、[R01](CHANGELOG.MD#r01)、[R02](CHANGELOG.MD#r02)、[R03](CHANGELOG.MD#r03)。 兩模型 0.3／0.6 denoise、結果介面與報告下載已補驗；更多素材／模型／adapter／修補品質待辦保留。 |
| <a id="h149"></a>H149<br>2026-10-22 [17440f4](https://github.com/Zimkjdv/Model-Atelier/commit/17440f47e2a3f263fa4e3d28399cbb4312c7f571) | 更廣泛 denoise／素材／模型品質、結構／畫風 adapter 待評估；2026-10-22 已完成 Pony／Animagine 各 0.3／0.6 圖生圖及比較關聯 GPU 驗收，瀏覽器結果介面與報告匯出亦已於第三項驗收。 | 已交付部分見 [4df715a](https://github.com/Zimkjdv/Model-Atelier/commit/4df715a4f6fe8461d5d53a982dc630089778ed54)、[17440f4](https://github.com/Zimkjdv/Model-Atelier/commit/17440f47e2a3f263fa4e3d28399cbb4312c7f571)、[7e5680f](https://github.com/Zimkjdv/Model-Atelier/commit/7e5680faf49ab76980493afd9c778f3610c392a9)；未完成保留 [R05](CHANGELOG.MD#r05)、[R01](CHANGELOG.MD#r01)、[R02](CHANGELOG.MD#r02)、[R03](CHANGELOG.MD#r03)。 兩模型 0.3／0.6 denoise、結果介面與報告下載已補驗；更多素材／模型／adapter／修補品質待辦保留。 |
| <a id="h150"></a>H150<br>2026-10-22 [17440f4](https://github.com/Zimkjdv/Model-Atelier/commit/17440f47e2a3f263fa4e3d28399cbb4312c7f571) | 更多素材／seed 品質、專用局部編輯／adapter、FLUX 來源存取與 RTX 4080 待完成；2026-10-22 已補驗比較方案下載／匯入、精確設定載入及 390px。 | 已交付部分見 [17440f4](https://github.com/Zimkjdv/Model-Atelier/commit/17440f47e2a3f263fa4e3d28399cbb4312c7f571)；未完成保留 [R05](CHANGELOG.MD#r05)、[R02](CHANGELOG.MD#r02)、[R03](CHANGELOG.MD#r03)、[F01](ROADMAP.MD#f01)、[F03](ROADMAP.MD#f03)、[E02](ROADMAP.MD#e02)。 比較方案實際下載、匯入、精確載入與 390px 已補驗；其他範圍仍未完成。 |
| <a id="h151"></a>H151<br>2026-10-22 [17440f4](https://github.com/Zimkjdv/Model-Atelier/commit/17440f47e2a3f263fa4e3d28399cbb4312c7f571) | 其他畫風、更廣泛品質、專用局部編輯／adapter、FLUX 來源存取及 RTX 4080 待完成；2026-10-22 已補驗比較關聯結果、原圖縮圖、報告實際下載與窄視窗。 | 已交付部分見 [17440f4](https://github.com/Zimkjdv/Model-Atelier/commit/17440f47e2a3f263fa4e3d28399cbb4312c7f571)；未完成保留 [L01](CHANGELOG.MD#l01)、[R05](CHANGELOG.MD#r05)、[R02](CHANGELOG.MD#r02)、[R03](CHANGELOG.MD#r03)、[F01](ROADMAP.MD#f01)、[F03](ROADMAP.MD#f03)、[E02](ROADMAP.MD#e02)。 比較結果、原圖縮圖、報告下載與窄視窗已補驗；其他畫風／模型／硬體不能借用。 |

<a id="current-open-map"></a>

## 歸檔前 39 個未勾選框對照

以下行號固定指來源 [17440f4](https://github.com/Zimkjdv/Model-Atelier/commit/17440f47e2a3f263fa4e3d28399cbb4312c7f571) 的 `ROADMAP.MD`。以 H 編號回查原文；同一待辦在主清單與歷史增量重複者只保留一份現行工作。

| 舊行號 | 歷史索引 | 現行未完成去向 |
| ---: | --- | --- |
| 52 | [H002](#h002) | [D02](#d02) |
| 116 | [H011](#h011) | [E04](ROADMAP.MD#e04)、[E02](ROADMAP.MD#e02)、[T01](CHANGELOG.MD#t01)、[T03](CHANGELOG.MD#t03) |
| 118 | [H013](#h013) | [E01](CHANGELOG.MD#e01) |
| 121 | [H016](#h016) | [E02](ROADMAP.MD#e02) |
| 122 | [H017](#h017) | [E03](ROADMAP.MD#e03) |
| 198 | [H117](#h117) | [L01](CHANGELOG.MD#l01) |
| 212 | [H118](#h118) | [F01](ROADMAP.MD#f01)、[F02](ROADMAP.MD#f02) |
| 215 | [H068](#h068) | [F03](ROADMAP.MD#f03) |
| 216 | [H069](#h069) | [F04](ROADMAP.MD#f04) |
| 227 | [H137](#h137) | [R01](CHANGELOG.MD#r01)、[R02](CHANGELOG.MD#r02)、[R03](CHANGELOG.MD#r03) |
| 238 | [H121](#h121) | [R05](CHANGELOG.MD#r05)、[R02](CHANGELOG.MD#r02)、[V04](CHANGELOG.MD#v04) |
| 244 | [H128](#h128) | [R06](CHANGELOG.MD#r06)、[R07](CHANGELOG.MD#r07) |
| 251 | [H083](#h083) | [T01](CHANGELOG.MD#t01) |
| 252 | [H084](#h084) | [T02](CHANGELOG.MD#t02) |
| 253 | [H085](#h085) | [T03](CHANGELOG.MD#t03) |
| 254 | [H086](#h086) | [T04](CHANGELOG.MD#t04) |
| 260 | [H087](#h087) | [A01](ROADMAP.MD#a01) |
| 261 | [H088](#h088) | [A02](ROADMAP.MD#a02) |
| 262 | [H089](#h089) | [A03](ROADMAP.MD#a03) |
| 263 | [H090](#h090) | [A03](ROADMAP.MD#a03) |
| 264 | [H091](#h091) | [A04](ROADMAP.MD#a04) |
| 265 | [H092](#h092) | [A05](ROADMAP.MD#a05) |
| 266 | [H093](#h093) | [A06](ROADMAP.MD#a06) |
| 267 | [H094](#h094) | [A07](ROADMAP.MD#a07) |
| 287 | [H095](#h095) | [D01](CHANGELOG.MD#d01) |
| 292 | [H099](#h099) | [A02](ROADMAP.MD#a02) |
| 316 | [H107](#h107) | [F03](ROADMAP.MD#f03)、[F04](ROADMAP.MD#f04)、[R01](CHANGELOG.MD#r01)、[R02](CHANGELOG.MD#r02)、[R07](CHANGELOG.MD#r07) |
| 422 | [H114](#h114) | [E04](ROADMAP.MD#e04)、[E02](ROADMAP.MD#e02)、[T01](CHANGELOG.MD#t01)、[T03](CHANGELOG.MD#t03) |
| 440 | [H115](#h115) | [E01](CHANGELOG.MD#e01) |
| 579 | [H122](#h122) | [L01](CHANGELOG.MD#l01)、[R05](CHANGELOG.MD#r05) |
| 587 | [H149](#h149) | [R05](CHANGELOG.MD#r05)、[R01](CHANGELOG.MD#r01)、[R02](CHANGELOG.MD#r02)、[R03](CHANGELOG.MD#r03) |
| 597 | [H150](#h150) | [R05](CHANGELOG.MD#r05)、[R02](CHANGELOG.MD#r02)、[R03](CHANGELOG.MD#r03)、[F01](ROADMAP.MD#f01)、[F03](ROADMAP.MD#f03)、[E02](ROADMAP.MD#e02) |
| 606 | [H126](#h126) | [L01](CHANGELOG.MD#l01)、[R05](CHANGELOG.MD#r05)、[E02](ROADMAP.MD#e02)、[E04](ROADMAP.MD#e04)、[T01](CHANGELOG.MD#t01)、[T03](CHANGELOG.MD#t03) |
| 626 | [H151](#h151) | [L01](CHANGELOG.MD#l01)、[R05](CHANGELOG.MD#r05)、[R02](CHANGELOG.MD#r02)、[R03](CHANGELOG.MD#r03)、[F01](ROADMAP.MD#f01)、[F03](ROADMAP.MD#f03)、[E02](ROADMAP.MD#e02) |
| 643 | [H131](#h131) | [V01](ROADMAP.MD#v01) |
| 654 | [H133](#h133) | [V01](ROADMAP.MD#v01)、[V02](CHANGELOG.MD#v02)、[R03](CHANGELOG.MD#r03)、[R05](CHANGELOG.MD#r05)、[R01](CHANGELOG.MD#r01)、[R02](CHANGELOG.MD#r02)、[F01](ROADMAP.MD#f01)、[F03](ROADMAP.MD#f03)、[E02](ROADMAP.MD#e02) |
| 685 | [H145](#h145) | [R05](CHANGELOG.MD#r05)、[R01](CHANGELOG.MD#r01)、[R02](CHANGELOG.MD#r02)、[R03](CHANGELOG.MD#r03)、[F01](ROADMAP.MD#f01)、[F03](ROADMAP.MD#f03)、[E02](ROADMAP.MD#e02) |
| 715 | [H146](#h146) | [R04](CHANGELOG.MD#r04)、[R01](CHANGELOG.MD#r01)、[R02](CHANGELOG.MD#r02)、[R03](CHANGELOG.MD#r03)、[F01](ROADMAP.MD#f01)、[F03](ROADMAP.MD#f03)、[E02](ROADMAP.MD#e02) |
| 746 | [H147](#h147) | [F01](ROADMAP.MD#f01)、[F03](ROADMAP.MD#f03)、[R03](CHANGELOG.MD#r03)、[R05](CHANGELOG.MD#r05)、[R01](CHANGELOG.MD#r01)、[R02](CHANGELOG.MD#r02)、[E02](ROADMAP.MD#e02) |

<a id="acceptance-recovery"></a>

## 已勾選行與敘述中的待驗收回收

這些原行未另設待辦框，不能因 `[x]` 或段落歸檔而遺漏。原行完整保留，現行 ROADMAP 已補成明確的 `[ ]` 主項與驗收子項；較早已補驗的範圍不重開，例如 Canny 預覽／下載／390px、比較方案 JSON 及兩模型 denoise 結果頁。

| 編號／來源 | 原行 | 仍需完成的驗收去向 |
| --- | --- | --- |
| U01 · [17440f4](https://github.com/Zimkjdv/Model-Atelier/commit/17440f47e2a3f263fa4e3d28399cbb4312c7f571) L175 | - [x] 固定 Pony V6 XL 作者來源／修訂與 SHA256，記錄模型卡授權標記及依賴；完整授權條款仍待核對。 | [M01](ROADMAP.MD#m01)。只有模型卡標記，全文核對未完成。 |
| U02 · [17440f4](https://github.com/Zimkjdv/Model-Atelier/commit/17440f47e2a3f263fa4e3d28399cbb4312c7f571) L151 | - [x] 圖片並排比較與人工評分已於 P6 實作；窄視窗實際操作仍待驗收。 | [V03](CHANGELOG.MD#v03)。並排與評分的窄視窗尚缺，不借用結果報告驗收。 |
| U03 · [17440f4](https://github.com/Zimkjdv/Model-Atelier/commit/17440f47e2a3f263fa4e3d28399cbb4312c7f571) L510 | - [x] 354 項後端測試（353 通過、1 項既有 Windows 權限跳過）、Vue 型別／建置、兩個視窗衝突及桌面瀏覽器驗收通過；viewport override 實際未生效，390px 本轮保持未驗收。 | [V03](CHANGELOG.MD#v03)。作品整理桌面已過，viewport override 未生效。 |
| U04 · [17440f4](https://github.com/Zimkjdv/Model-Atelier/commit/17440f47e2a3f263fa4e3d28399cbb4312c7f571) L531 | - [x] 370 項後端測試（369 通過、1 項既有權限跳過）、Vue 型別／建置及桌面 UI 驗收通過；IAB Blob 下載事件未回報，僅確認 API bytes、下載連結及完整 JSON，其他瀏覽器下載與 390px 待驗收。 | [V05](CHANGELOG.MD#v05)。一般創作設定交換不是比較方案 JSON。 |
| U05 · [17440f4](https://github.com/Zimkjdv/Model-Atelier/commit/17440f47e2a3f263fa4e3d28399cbb4312c7f571) L557 | - [x] 384 項後端測試（383 通過、1 項既有 Windows 權限跳過）、Vue 型別／建置、API 及原圖觀察；瀏覽器工具無法啟動，UI 實機驗收未完成。見 `docs/validation/animagine-multi-lora-quality-rtx3060.md`。 | [V04](CHANGELOG.MD#v04)。較早有序匹配桌面已過，但新 8 步品質紀錄未補驗。 |
| U06 · [17440f4](https://github.com/Zimkjdv/Model-Atelier/commit/17440f47e2a3f263fa4e3d28399cbb4312c7f571) L563 | - [x] 390 項後端測試（389 通過、1 項既有 Windows 權限跳過）、Vue 型別／建置與 RTX 3060 真實量測、作品及離線核對；瀏覽器 UI 實機驗收未完成。見 `docs/job-measurements.md`。 | [V04](CHANGELOG.MD#v04)。任務量測 UI 尚未補驗。 |
| U07 · [17440f4](https://github.com/Zimkjdv/Model-Atelier/commit/17440f47e2a3f263fa4e3d28399cbb4312c7f571) L570 | - [x] 394 項後端測試（393 通過、1 項既有 Windows 權限跳過）、Vue 型別／建置通過；本輪瀏覽器工具環境故障，UI 實機驗收未完成。 | [V04](CHANGELOG.MD#v04)。固定四案例 GPU 已過，新的 UI 實際驗收未完成。 |
| U08 · [17440f4](https://github.com/Zimkjdv/Model-Atelier/commit/17440f47e2a3f263fa4e3d28399cbb4312c7f571) L578 | - [x] 397 項後端測試（396 通過、1 項既有 Windows 權限跳過）及 Vue 型別／建置通過；工具 sandbox 啟動失敗，UI 實機驗收未完成。沒有新增 GPU 任務或正式資料。 | [V04](CHANGELOG.MD#v04)。LoRA 強度軸 UI 未完成，不能以 denoise 操作替代。 |
| U09 · [17440f4](https://github.com/Zimkjdv/Model-Atelier/commit/17440f47e2a3f263fa4e3d28399cbb4312c7f571) L245 | - [x] 新任務保存平台觀察耗時、原引擎歷史起訖及提交前資源快照；作品沿用，未知值不推估或回填。連續／任務專用峰值仍待實作。 | [E05](CHANGELOG.MD#e05)。單次快照不能作連續或任務專用峰值。 |
| U10 · [17440f4](https://github.com/Zimkjdv/Model-Atelier/commit/17440f47e2a3f263fa4e3d28399cbb4312c7f571) L452 | - 全站視覺規範及所有頁面的無障礙驗收仍可繼續完善，本項驗證以創作工作台與主要導覽為範圍。 | [V06](CHANGELOG.MD#v06)。原驗收只涵蓋工作台及主要導覽。 |
| U11 · [17440f4](https://github.com/Zimkjdv/Model-Atelier/commit/17440f47e2a3f263fa4e3d28399cbb4312c7f571) L733 | - [x] 真實 RTX 3060 羽化比較及新歷史介面已於第三項核對；筆刷觸控尚未重驗。 | [V01](ROADMAP.MD#v01)。筆刷觸控仍未重驗。 |
| U12 · [17440f4](https://github.com/Zimkjdv/Model-Atelier/commit/17440f47e2a3f263fa4e3d28399cbb4312c7f571) L742 | - [x] 真實瀏覽器預覽／390px、歷史羽化來源／下載 hash／精確 seed 與半徑還原通過；筆刷觸控與真實遺失回應的 pending 未重驗。 | [V01](ROADMAP.MD#v01)、[V02](CHANGELOG.MD#v02)。預覽、下載、390px 已過，觸控及未知回應注入仍缺。 |
| U13 · [87d277d](https://github.com/Zimkjdv/Model-Atelier/commit/87d277d5716c0c1f3a4307e1b3049d588abe2f95) L10 | 本輪接續 P6 ControlNet：第一項 Canny 結構參考後端已完成，451 項後端測試（450 通過、1 項既有 Windows 權限跳過）。專用工作台及固定 SDXL 控制模型／RTX 3060 驗收接續實作；一般草稿／比較方案、adapter 畫風／角色、FLUX 安裝與 RTX 4080 仍待完成。 | [R07](CHANGELOG.MD#r07)。保留歷史中一般草稿／比較方案的後續評估；不擅自宣稱已支援。 |

<a id="history"></a>

## 按日期排列的完整版本與驗收歷史

## 2026-09-06

<a id="commit-cd1d1af3aa94ad5b8cd6990a61735acab4b87dff"></a>

### 17:12:03 · [cd1d1af](https://github.com/Zimkjdv/Model-Atelier/commit/cd1d1af3aa94ad5b8cd6990a61735acab4b87dff) · feat: bootstrap local Vue and FastAPI studio with hardware monitoring

來源：[完整清單原檔](https://github.com/Zimkjdv/Model-Atelier/blob/cd1d1af3aa94ad5b8cd6990a61735acab4b87dff/%E5%B9%B3%E5%8F%B0%E9%96%8B%E7%99%BC%E6%B8%85%E5%96%AE.md)；檔名 `平台開發清單.md`；Git blob `33edaa7a5a647a9e7c4eb3db0edcfce5b2d3cd34`。

當時核取框：111，已勾選 12、未勾選 99。作者時間 `2026-09-06T17:12:03+08:00`；提交時間 `2026-09-06T17:12:03+08:00`。

<details>
<summary>首次完整清單（含全部階段驗收與規劃原文）</summary>

````markdown
# Model Atelier — 平台開發清單

> 個人 AI 圖像創作與實驗工作台
>
> A self-hosted web studio for anime illustration, reference-guided image creation, and reproducible multi-model experiments.

更新日期：2026-09-06
狀態：開發中；已交付範圍見下方開發進度，各階段其餘項目仍待實作與驗收。

### 開發進度（2026-09-06）

- [x] 建立本地 Python `.venv`、Vue 3 + TypeScript 前端及 FastAPI 後端。
- [x] 完成系統資訊頁：平台主機 GPU、VRAM、RAM、資料磁碟、更新時間及錯誤狀態。
- [x] 完成 ComfyUI 位址保存、連線檢查及引擎回報資訊的獨立呈現。
- [x] 完成前端型別檢查與正式建置；後端設定保存、無 GPU 降級及未知顯存值測試通過。
- [x] 本地瀏覽器驗證硬體資訊與設定保存：RTX 3060 12GiB、約 64GiB RAM；ComfyUI 預設位址目前未連線，尚未完成真實引擎整合驗證。
- [ ] 真實 ComfyUI 連線、工作流程提交與生成結果保存尚待實作／驗證；目前導覽中的創作、模型與作品頁為待開發頁面。
- 第一階段僅在 LOCAL 端執行，平台 `.venv` 與 ComfyUI 環境分離。功能穩定後再評估 Docker 部署，不把 Docker 列為本機使用前置需求。
- [ ] 後續 Docker 評估涵蓋資料持久化、GPU 存取、主機硬體資訊來源及 ComfyUI 連線；不預設容器內資訊等於宿主機全部資訊。

## 1. 產品方向與實作原則

- 個人使用、自行部署的 Web 平台，整合一般二次元插畫創作與模型實驗。
- 優先整合可取得權重且符合使用條件的本地模型。
- 沒有公開權重、必須使用官方 API 的服務，統一放在最後階段。
- 公開權重不等於無使用限制；模型登記需保留來源及授權資訊。
- ComfyUI 是執行引擎；Pony、Animagine、FLUX 是模型候選；LoRA 是附加模型能力；各層分開管理。
- 依架構、功能及相容性分類模型，不使用內容尺度作為產品分類。
- 參考圖片用於引導創作，不承諾單張圖片能完全重現畫風或角色。
- 所有模型版本、支援能力及硬體需求，以正式接入時的官方資料與實測為準。

## 2. 實作順序

| 階段 | 範圍 | 備註 |
| --- | --- | --- |
| P0 | 確認環境與架構 | 先確認 GPU、儲存空間及部署位置 |
| P1 | 平台骨架與本地 ComfyUI | 打通提交、進度、結果保存 |
| P2 | Pony V6 XL | 第一個本地 SDXL 模型候選，接入前確認來源與授權 |
| P3 | Animagine XL | 驗證同架構多模型切換，確切版本待選 |
| P4 | 通用 LoRA 支援 | 先完成已接入架構的相容性管理 |
| P5 | FLUX.1 公開權重變體 | 跨架構整合；確切變體待確認，LoRA 支援另行驗證 |
| P6 | 參考圖工作流程與實驗管理 | 每套流程分別驗證模型與元件相容性 |
| P7 | 訓練與微調模組評估 | 與推論參數調整分開規劃 |
| P8 | 官方 API 服務 | NovelAI、Mango 2 等候選，先驗證正式接入方式 |

Mango 2 的確切提供者、權重可用性及 API 狀態尚未確認，暫留 P8 待查證，不視為已確定可接入。若確認有可用公開權重，再重新排入本地模型階段。

## 3. P0：環境與技術決策

- [x] 確認現有硬體：使用者有 RTX 3060 與 RTX 4080 兩台機器。
- [x] 確認開發順序：目前在 RTX 3060 主機開發並進行首輪驗證，之後在 RTX 4080 主機驗證。
- 實際 VRAM、RAM、磁碟與軟體環境由平台偵測，不根據顯卡名稱預先填入容量。
- [ ] 規劃由平台自動偵測 GPU 型號、VRAM、RAM 與可用磁碟空間，於 P1 實作系統資訊頁。
- [ ] 確認 GPU 執行於本機或獨立主機；Web 平台與推論引擎分離。
- [ ] 確認 Windows 原生或 WSL 的推論環境。
- [x] 確認前端方案：Vue 3 + TypeScript；此項為選型定案，尚未實作。
- [x] 確認後端方案：Python + FastAPI；ComfyUI 負責模型執行，此項為選型定案，尚未實作。
- [x] 確認第一版優先支援 NVIDIA / CUDA 執行環境；具體相容範圍待驗證。
- [ ] 確認資料方案：初期 SQLite + 本地檔案目錄。
- [ ] 定義模型、輸入素材、輸出、縮圖及資料庫的儲存位置。
- [ ] 定義本機存取設定；若開放區網或遠端，再加入驗證與連線保護。

驗收：部署方式、資料目錄和硬體限制已記錄，可據此選擇第一個執行流程。

### 技術選型理由

- 採用 Vue 3 + TypeScript 建立參數表單、模型切換、任務進度及作品管理介面；目前沒有必須使用 React 的需求。
- Vue 與 React 本身不決定美觀或易用程度，介面品質由版面、字體、配色、元件一致性及互動設計決定。
- Python + FastAPI 負責平台 API、資料管理與執行引擎串接；模型推論保留在 ComfyUI 的獨立環境。

### NVIDIA 支援範圍與資源限制

- 平台不以顯卡等級、型號白名單或固定 VRAM 門檻限制使用。瀏覽器端不要求 NVIDIA 顯卡，執行需求取決於連接的模型主機。
- 即使本機無可用 GPU，仍可開啟平台、管理素材與作品、編輯設定及設定遠端引擎；本機推論是否可用另行判斷。
- 第一版針對 NVIDIA / CUDA 開發，不承諾所有 NVIDIA 顯卡都能執行所有模型。
- GPU 世代、驅動、PyTorch、CUDA 及模型運算需求都會影響相容性；正式支援組合需記錄版本並實測。
- VRAM 影響工作負載能否容納，容量不足可能直接執行失敗，不能只解讀為速度較慢。
- 生成速度同時受 GPU 算力、記憶體頻寬、模型、解析度及生成設定影響，不能單靠 VRAM 大小推估。
- 生成與訓練分別評估；能生成圖片不代表能訓練或微調同一模型。
- CPU 卸載等降低顯存需求的方式，僅在工作流程支援且通過驗證時提供，並說明 RAM 與速度上的代價。
- [ ] 檢查模型執行環境的 GPU、驅動、PyTorch 與 CUDA 可用狀態；資料不可得時標示未知。
- [ ] 建立模型與工作流程的相容性紀錄，區分已驗證、未驗證及已知不相容。
- [ ] 記錄生圖與訓練各自的實測資源需求，保留硬體、環境及測試設定，不提供未經驗證的效能保證。
- [ ] 資源預估不足或尚未實測時提供提示，允許使用者嘗試；不因顯卡型號或估算 VRAM 單獨封鎖提交。
- [ ] 已確認無可用執行裝置、缺少必要元件或工作流程不相容時，只阻擋受影響任務並說明原因，不限制其他平台功能。
- [ ] 執行記憶體不足時保留原設定並提供調整與重試入口；不默默改動解析度、精度或模型。
- [ ] 以現有 RTX 3060 主機完成首輪開發與驗證，保存實際硬體、環境版本及工作流程設定。
- [ ] 首輪通過後，在現有 RTX 4080 主機重跑相同的基本功能與工作流程，記錄相容性、資源用量及耗時差異。
- [ ] 先在兩台主機比較相同設定，再另行測試 RTX 4080 可承受的較高負載；後者不作為 RTX 3060 的基本驗收門檻。
- RTX 4090 不屬於目前持有硬體及必要驗收範圍；未實測的硬體不標示為已驗證。測試配置不作為顯卡白名單。
- [ ] 效能紀錄包含模型版本、精度、解析度、步數、批次大小、附加元件、卸載方式與冷／熱啟動條件，避免無條件的秒數承諾。

研究資料採用原則：不將「4080 固定 3–5 秒一張」「4090 所有模型最高畫質隨便跑」「掛載固定數量 LoRA 就不會 OOM」列為規格。FLUX 等模型的記憶體需求受完整流程與精度影響，24GB 也不代表所有元件可同時常駐 GPU。量化與 CPU 卸載是可評估的記憶體優化方式，GGUF 並非唯一方式；實際支援需逐流程驗證。

## 4. P1：平台骨架與 ComfyUI

- [ ] 建立前後端專案與環境設定範例。
- [ ] 建立創作工作台、模型庫、作品庫、系統資訊、設定頁的基本導覽。
- [ ] 支援設定 ComfyUI 位址與連線健康檢查。
- [ ] 建立執行引擎介面，避免前端直接依賴 ComfyUI API。
- [ ] 匯入一套已驗證的工作流程，定義可由表單修改的欄位。
- [ ] 提交前驗證必填值、參數範圍及所需模型是否存在。
- [ ] 提交任務並保存平台任務 ID 與引擎任務 ID 的對應。
- [ ] 顯示排隊、執行、完成、失敗及取消狀態。
- [ ] 接收進度事件；斷線重連後查詢任務，避免重複提交。
- [ ] 支援取消排隊任務；執行中停止需確認引擎語意，避免中斷其他任務。
- [ ] 保存生成結果、縮圖、執行設定與錯誤資訊。
- [ ] 支援從作品載入原設定，再次提交。
- [ ] 提供啟動、停止與故障排查說明。

### 介面美觀與操作體驗

- [ ] 將常用參數直接呈現，進階參數收合，保留使用者設定狀態。
- [ ] 依選定模型與工作流程顯示適用選項，不相容設定需清楚說明原因。
- [ ] 清楚呈現排隊、執行、完成及失敗狀態，提供適用的取消與重新執行操作。
- [ ] 作品可一鍵載入原設定，作為繼續創作的起點；圖片並排比較於 P6 實作。
- [ ] 統一字體、間距、配色、按鈕、表單及載入、空白、錯誤狀態的視覺規範。
- [ ] 建立適合桌面操作的工作台布局，較窄視窗可收合設定區，避免主要操作被擠出畫面。
- [ ] 表單提供清楚標籤、鍵盤焦點及可讀對比；狀態不只用顏色區分。

介面驗收：使用者能完成選模型、輸入提示詞、調整常用設定、提交、查看狀態及載入作品設定；進階欄位不妨礙基本操作，錯誤與不相容原因能在介面直接理解。

### 系統資訊與硬體自動偵測

- [ ] 由後端或模型執行主機上的資訊採集介面讀取硬體資料，不以瀏覽器所在電腦代表模型執行環境。
- [ ] 顯示 GPU 型號；多 GPU 時逐張列出，並標示引擎使用的裝置，無法確認時顯示未知。
- [ ] 顯示各 GPU 的 VRAM 總量、已用量與可用量，統一容量單位。
- [ ] 顯示模型執行主機的 RAM 總量、已用量與可用量。
- [ ] 顯示模型、素材及輸出目錄所在磁碟的總容量與可用空間；同一磁碟不重複加總。
- [ ] 平台與推論引擎分開部署時，分別標示主機角色與資料來源；素材及輸出磁碟資訊依其實際儲存主機顯示。
- [ ] 進入系統資訊頁時自動取得資料，提供手動重新整理、定期更新及最後更新時間。
- [ ] 若遠端介面不提供某項資訊，顯示「無法取得」及原因，不以平台主機資料代替，也不顯示為零。
- [ ] 處理無 GPU、驅動或權限不足、主機離線等狀態；保留的舊資料需明確標示已過期。
- [ ] 第一版以資訊顯示為主；單靠剩餘 VRAM 不保證模型可執行。

驗收：使用瀏覽器完成一次生成，結果與設定在平台重啟後仍可讀取；失敗任務有可理解的原因。系統資訊頁可自動顯示執行主機的硬體與儲存資訊，重新整理後更新數值；無法取得的欄位有明確狀態，遠端部署不會誤顯示為平台主機的硬體。

## 5. P2–P3：本地 SDXL 模型整合

- [ ] 核對 Pony V6 XL 的正式來源、版本、授權及依賴。
- [ ] 核對並選定 Animagine XL 版本、來源、授權及依賴。
- [ ] 支援登記既有本地模型路徑，第一版不強制複製大型檔案。
- [ ] 記錄模型名稱、架構、版本、檔案大小、雜湊、來源與授權連結。
- [ ] 建立每個模型獨立的工作流程與參數預設。
- [ ] 依流程能力顯示提示詞、seed、尺寸、步數等設定。
- [ ] 只顯示流程實際支援的進階欄位，保存原始參數。
- [ ] 切換模型時重新檢查相容性，不沿用不適用的參數或元件。
- [ ] 測量生成耗時與記憶體需求，記錄測量環境。
- [ ] 處理模型遺失、載入失敗及 GPU 記憶體不足。

驗收：兩個模型都能完成生成；切換時能正確載入對應預設，作品可追溯到確切模型版本。

## 6. P4：LoRA 通用支援

- [ ] 建立 LoRA 登記、來源、版本與基礎架構欄位。
- [ ] 支援選擇、啟用及移除 LoRA，保存工作流程支援的設定。
- [ ] 顯示相容、未驗證或不相容狀態；不以檔名推斷相容性。
- [ ] 提交前阻擋已知不相容組合。
- [ ] 先驗證單一 LoRA，再評估多個 LoRA 的組合支援。
- [ ] 將 LoRA 版本及設定保存至生成紀錄。

驗收：支援的 LoRA 組合可載入與追溯；不相容組合不會直接送往 GPU 執行。

## 7. P5：FLUX.1 跨架構整合

- [ ] 選定可本地執行的公開權重變體，記錄授權及使用條件。
- [ ] 確認所需編碼器、解碼器、推論精度及硬體需求。
- [ ] 建立獨立工作流程與參數描述，不直接套用 SDXL 表單。
- [ ] 驗證載入、生成、結果保存及記憶體不足時的處理。
- [ ] 對此架構的 LoRA 與參考圖功能逐項驗證，未驗證能力保持停用。

驗收：平台可在 SDXL 與選定的 FLUX 變體之間切換，各自具有正確的設定介面及依賴檢查。

## 8. P6：參考圖創作、作品庫與實驗比較

### 參考素材與流程

- [ ] 上傳、預覽及管理參考圖片，檢查格式和尺寸。
- [ ] 標示參考用途：視覺風格、角色外觀、構圖等。
- [ ] 建立每套工作流程的輸入需求與支援能力說明。
- [ ] 逐項評估圖片生成圖片、局部編輯及結構參考流程。
- [ ] 保存參考圖與輸出的關聯；保存前處理設定及版本。
- [ ] 檢查素材是否被任務引用，避免刪除後無法重建流程。

### 作品與實驗

- [ ] 支援作品篩選、收藏、備註與下載。
- [ ] 支援設定匯出、匯入及從歷史紀錄重新執行。
- [ ] 保存模型、LoRA、工作流程、引擎及依賴版本。
- [ ] 提供圖片並排比較與人工評分。
- [ ] 使用固定的一般插畫測試集，比較提示服從、角色一致、視覺風格及構圖。
- [ ] 支援有限範圍的參數比較，提交前顯示預計任務數。
- [ ] 記錄耗時及可取得的資源用量，無法測得的數值不推估填入。

驗收：任一結果都能追溯輸入、參數、模型和流程；比較任務可追溯各自差異。重現表示設定可恢復，不保證跨硬體或環境逐像素一致。

## 9. P7：訓練與微調模組評估

- [ ] 確認是否有超出推論參數調整的實際訓練需求。
- [ ] 評估資料集管理、標註、版本及訓練工具介面。
- [ ] 規劃獨立環境與 GPU 資源協調，避免與生成任務互相干擾。
- [ ] 規劃訓練產物回登模型庫及評估流程。

此階段不屬於第一版，也不預先承諾支援所有模型的訓練。

## 10. P8：官方 API 服務，最後實作

- [ ] NovelAI：確認官方 API、驗證方式、使用條件、費用及可接入功能。
- [ ] Mango 2：先確認確切模型與提供者，再核對公開權重或官方 API。
- [ ] 只有已確認正式接入方式的服務才列入實作，不假設網站功能等於 API 功能。
- [ ] 建立服務介面，分離本地模型與遠端服務的能力描述。
- [ ] 憑證只保存在後端，不寫入前端或版本控制。
- [ ] 提交前顯示資料將送往的服務及已知費用資訊。
- [ ] 處理限流、逾時、扣費狀態及重試，避免重複付費提交。
- [ ] 依服務支援範圍保存結果及請求設定。

驗收：服務來源與接入條件明確；不支援的功能不顯示為可用；錯誤或重試不會造成不可追蹤的重複請求。

## 11. 第一版邊界

第一版交付 P0、P1 與 P2：ComfyUI + 一個本地模型 + 生成介面 + 任務狀態 + 作品與參數保存 + 系統資訊與硬體自動偵測。

暫不包含：

- 公開社群、分享廣場、多租戶及付費系統。
- 自製節點編輯器。
- 官方 API 服務。
- 模型訓練、一鍵安裝全部模型、自動安裝任意第三方節點。
- 對畫風完全一致、角色完全一致或所有模型互通的保證。

## 12. 待確認事項

- [x] 現有主機與驗證順序已確認：RTX 3060 先開發與驗證，RTX 4080 後續驗證；兩台實際環境資訊待自動偵測。
- [x] 確認硬體資訊由平台自動偵測並顯示，功能實作列於 P1；不要求使用者手動填寫。
- [ ] 推論跑本機或遠端 GPU；是否需要區網存取。
- [ ] 現有 ComfyUI 是否已安裝，是否有可沿用的模型目錄。
- [ ] 確認第一個模型採 Pony V6 XL，或依硬體與實測調整。
- [ ] Animagine XL 與 FLUX.1 的確切版本。
- [ ] Mango 2 的官方來源。

## 13. 官方查核入口

- [ComfyUI 系統需求](https://docs.comfy.org/installation/system_requirements)
- [Diffusers 記憶體優化](https://huggingface.co/docs/diffusers/optimization/memory)
- [Diffusers FLUX 流程與記憶體需求](https://github.com/huggingface/diffusers/blob/main/docs/source/en/api/pipelines/flux.md)
- [ComfyUI 伺服器 API](https://docs.comfy.org/development/comfyui-server/comms_routes)
- [Animagine XL 4.0 模型卡](https://huggingface.co/cagliostrolab/animagine-xl-4.0)（版本候選，不代表已選定）
- [FLUX.1 Kontext Dev 模型卡](https://huggingface.co/black-forest-labs/FLUX.1-Kontext-dev)（用於釐清公開權重與 API 版本差異，不代表已選定）

其他候選模型與服務的官方來源於接入前補齊。
````

</details>

<a id="commit-7699c4f86109fb88bda39c9d38509754dd97839d"></a>

### 17:25:53 · [7699c4f](https://github.com/Zimkjdv/Model-Atelier/commit/7699c4f86109fb88bda39c9d38509754dd97839d) · feat: add engine-scoped checkpoint library with metadata and offline snapshots

來源：[完整清單原檔](https://github.com/Zimkjdv/Model-Atelier/blob/7699c4f86109fb88bda39c9d38509754dd97839d/%E5%B9%B3%E5%8F%B0%E9%96%8B%E7%99%BC%E6%B8%85%E5%96%AE.md)；檔名 `平台開發清單.md`；Git blob `e3b3a5b9e945952006e2ae9c7ba2766e1cdcd420`。

當時核取框：115，已勾選 15、未勾選 100。作者時間 `2026-09-06T17:25:53+08:00`；提交時間 `2026-09-06T17:25:53+08:00`。

<details>
<summary>完整清單差異（含項目、勾選與驗收變動）</summary>

````diff
--- 平台開發清單.md
+++ 平台開發清單.md
@@ -17 +17,5 @@
-- [ ] 真實 ComfyUI 連線、工作流程提交與生成結果保存尚待實作／驗證；目前導覽中的創作、模型與作品頁為待開發頁面。
+- [x] 完成模型庫第一階段：checkpoint 清單同步、搜尋與篩選、來源與備註保存、偏好模型選擇。
+- [x] 模型紀錄依引擎位址分開保存；同步失敗保留快照，模型移除保留備註並標示未列出。
+- [x] 七項後端測試與前端建置通過；瀏覽器驗證離線提示，另以隔離測試資料驗證搜尋、備註及偏好選擇。
+- [ ] 真實 ComfyUI 連線與模型同步仍待驗證；工作流程提交與生成結果保存尚未實作，創作與作品頁仍為待開發頁面。
+- [ ] 模型庫後續補齊檔案雜湊、大小、版本與架構等資料；目前來源與備註為使用者登記資訊，不能視為已驗證。
````

</details>

<a id="commit-7541feb57d69550c6e35c05bdab6efe1cab8ee1e"></a>

### 17:38:31 · [7541feb](https://github.com/Zimkjdv/Model-Atelier/commit/7541feb57d69550c6e35c05bdab6efe1cab8ee1e) · feat: add local ComfyUI launcher and engine and model version details

來源：[完整清單原檔](https://github.com/Zimkjdv/Model-Atelier/blob/7541feb57d69550c6e35c05bdab6efe1cab8ee1e/%E5%B9%B3%E5%8F%B0%E9%96%8B%E7%99%BC%E6%B8%85%E5%96%AE.md)；檔名 `平台開發清單.md`；Git blob `f130388d19ac4832ee3a3a79612c42d1dc8fd1e9`。

當時核取框：118，已勾選 19、未勾選 99。作者時間 `2026-09-06T17:38:31+08:00`；提交時間 `2026-09-06T17:38:31+08:00`。

<details>
<summary>完整清單差異（含項目、勾選與驗收變動）</summary>

````diff
--- 平台開發清單.md
+++ 平台開發清單.md
@@ -20 +20,4 @@
-- [ ] 真實 ComfyUI 連線與模型同步仍待驗證；工作流程提交與生成結果保存尚未實作，創作與作品頁仍為待開發頁面。
+- [x] 在 `runtime/ComfyUI` 安裝官方 ComfyUI 0.34.0 與獨立 `.venv`，提供 `start-comfyui.ps1`；runtime 不納入 Git。
+- [x] RTX 3060 通過 PyTorch CUDA 運算與依賴檢查；真實 ComfyUI `/system_stats`、平台連線及空 checkpoint 清單同步成功。
+- [x] 模型庫顯示 ComfyUI 服務回報版本與官方 GitHub 來源；checkpoint 另有版本登記欄位，未取得或未填版本顯示「未知」，不依檔名或 GitHub 最新版本推測。
+- [ ] 尚未安裝 checkpoint，非空模型清單、實際模型載入與生成仍待驗證；工作流程提交與生成結果保存尚未實作。
@@ -240 +243 @@
-- [ ] 現有 ComfyUI 是否已安裝，是否有可沿用的模型目錄。
+- [x] ComfyUI 已安裝於 `runtime/ComfyUI`；目前 checkpoint 目錄為空，未下載模型。
````

</details>

<a id="commit-e5f3fcb96f179b69327b539c68390cffb80e1297"></a>

### 17:58:36 · [e5f3fcb](https://github.com/Zimkjdv/Model-Atelier/commit/e5f3fcb96f179b69327b539c68390cffb80e1297) · feat: add creation studio with versioned local drafts

來源：[完整清單原檔](https://github.com/Zimkjdv/Model-Atelier/blob/e5f3fcb96f179b69327b539c68390cffb80e1297/%E5%B9%B3%E5%8F%B0%E9%96%8B%E7%99%BC%E6%B8%85%E5%96%AE.md)；檔名 `平台開發清單.md`；Git blob `806f6819d39ddfa99d96c03cdb5e82771afe78b3`。

當時核取框：121，已勾選 22、未勾選 99。作者時間 `2026-09-06T17:58:36+08:00`；提交時間 `2026-09-06T17:58:36+08:00`。

<details>
<summary>完整清單差異（含項目、勾選與驗收變動）</summary>

````diff
--- 平台開發清單.md
+++ 平台開發清單.md
@@ -22,0 +23,3 @@
+- [x] 完成創作工作台草稿：提示詞、模型選擇、尺寸、seed、比例預覽、保存與重載、另存新草稿及未保存變更保護。
+- [x] 草稿保存模型版本與引擎位址，seed 以字串保存避免精度損失；修訂號防止跨視窗覆寫，十項後端測試通過。
+- [x] 瀏覽器驗證無模型時保存草稿、切換尺寸、未保存提示與重載；臨時測試草稿已清理。
````

</details>

<a id="commit-47a7c5961f1345fcfd4a7c38ccea0f924bcc8125"></a>

### 18:08:19 · [47a7c59](https://github.com/Zimkjdv/Model-Atelier/commit/47a7c5961f1345fcfd4a7c38ccea0f924bcc8125) · feat: add local reference asset library and draft links

來源：[完整清單原檔](https://github.com/Zimkjdv/Model-Atelier/blob/47a7c5961f1345fcfd4a7c38ccea0f924bcc8125/%E5%B9%B3%E5%8F%B0%E9%96%8B%E7%99%BC%E6%B8%85%E5%96%AE.md)；檔名 `平台開發清單.md`；Git blob `c63f5aa83fc14b65d158de3e8245850dec566d5e`。

當時核取框：125，已勾選 25、未勾選 100。作者時間 `2026-09-06T18:08:19+08:00`；提交時間 `2026-09-06T18:08:19+08:00`。

<details>
<summary>完整清單差異（含項目、勾選與驗收變動）</summary>

````diff
--- 平台開發清單.md
+++ 平台開發清單.md
@@ -25,0 +26,4 @@
+- [x] 完成參考素材上傳、預覽、搜尋、命名及可還原封存；驗證真實圖片格式、檔案大小與像素數。
+- [x] 草稿可保存最多八張參考素材關聯；被草稿引用的素材禁止封存，資料操作在同一 SQLite 交易檢查。
+- [x] 十三項後端測試與前端建置通過；驗證實際上傳 API、瀏覽器預覽、封存還原及素材選取，臨時圖片已清理。
+- [ ] 參考素材目前僅管理與記錄，尚未串接 ComfyUI 圖片輸入、用途或參考權重。
````

</details>

<a id="commit-c651cfa543d490ba61ef0c25234877c011471c96"></a>

### 18:29:45 · [c651cfa](https://github.com/Zimkjdv/Model-Atelier/commit/c651cfa543d490ba61ef0c25234877c011471c96) · feat: add ComfyUI workflow submission layer

來源：[完整清單原檔](https://github.com/Zimkjdv/Model-Atelier/blob/c651cfa543d490ba61ef0c25234877c011471c96/%E5%B9%B3%E5%8F%B0%E9%96%8B%E7%99%BC%E6%B8%85%E5%96%AE.md)；檔名 `平台開發清單.md`；Git blob `4059378413ed0a90da1ffda527d5513537737ff7`。

當時核取框：134，已勾選 31、未勾選 103。作者時間 `2026-09-06T18:29:45+08:00`；提交時間 `2026-09-06T18:29:45+08:00`。

<details>
<summary>完整清單差異（含項目、勾選與驗收變動）</summary>

````diff
--- 平台開發清單.md
+++ 平台開發清單.md
@@ -30 +30 @@
-- [ ] 尚未安裝 checkpoint，非空模型清單、實際模型載入與生成仍待驗證；工作流程提交與生成結果保存尚未實作。
+- [ ] 尚未安裝 checkpoint，非空模型清單、實際模型載入與生成仍待驗證；工作流程提交已實作，生成圖片匯入作品庫尚未實作。
@@ -264,0 +265,13 @@
+
+
+## 本次增量：工作流程提交層
+
+- [x] 標準 checkpoint 文生圖提交 API 與創作頁生成按鈕。
+- [x] SQLite 任務紀錄、完整 API 工作流程 JSON 保存及下載。
+- [x] 請求 UUID 去重，提交結果不明不自動重送。
+- [x] 原引擎佇列／歷史查詢，保存成功／失敗歷史及節點錯誤。
+- [x] 缺少 checkpoint、引擎離線、模型清單異常的明確錯誤。
+- [x] 19 項後端測試、前端建置、真實引擎空模型及離線驗證。
+- [ ] 安裝 checkpoint 後驗證完整成功生成及實際 VRAM／耗時。
+- [ ] 輸出圖片匯入平台作品庫、預覽與備份。
+- [ ] 參考圖、LoRA、FLUX 各自的相容工作流程。
````

</details>

<a id="commit-631834d9a45f546ddc9655e681d3cf707640a7f1"></a>

### 18:48:28 · [631834d](https://github.com/Zimkjdv/Model-Atelier/commit/631834d9a45f546ddc9655e681d3cf707640a7f1) · feat: add local artwork library and document service ports

來源：[完整清單原檔](https://github.com/Zimkjdv/Model-Atelier/blob/631834d9a45f546ddc9655e681d3cf707640a7f1/%E5%B9%B3%E5%8F%B0%E9%96%8B%E7%99%BC%E6%B8%85%E5%96%AE.md)；檔名 `平台開發清單.md`；Git blob `761e8ad509474621759102d8d8d01ececa49617a`。

當時核取框：142，已勾選 39、未勾選 103。作者時間 `2026-09-06T18:48:28+08:00`；提交時間 `2026-09-06T18:48:28+08:00`。

<details>
<summary>完整清單差異（含項目、勾選與驗收變動）</summary>

````diff
--- 平台開發清單.md
+++ 平台開發清單.md
@@ -30 +30 @@
-- [ ] 尚未安裝 checkpoint，非空模型清單、實際模型載入與生成仍待驗證；工作流程提交已實作，生成圖片匯入作品庫尚未實作。
+- [ ] 尚未安裝 checkpoint，非空模型清單、實際模型載入與生成仍待驗證；工作流程提交及作品庫匯入已實作，已用測試圖片驗證讀取流程。
@@ -121 +121 @@
-- [ ] 保存生成結果、縮圖、執行設定與錯誤資訊。
+- [x] 保存生成結果、縮圖、執行設定與錯誤資訊（已完成任務手動匯入作品庫）。
@@ -276 +276 @@
-- [ ] 輸出圖片匯入平台作品庫、預覽與備份。
+- [x] 輸出圖片匯入平台作品庫、預覽與完整資料目錄備份說明。
@@ -277,0 +278,11 @@
+
+## 本次增量：作品庫
+
+- [x] 成功任務 SaveImage 輸出匯入、原圖與縮圖本機保存。
+- [x] 依任務與輸出識別去重；部分下載失敗可再次匯入補齊。
+- [x] 作品搜尋、大圖預覽、原圖與完整工作流程下載。
+- [x] 正／負提示詞、精確 seed、取樣參數與模型版本快照；無版本紀錄顯示未知。
+- [x] 原引擎離線、來源或本機檔案遺失、無效圖片與磁碟寫入錯誤提示。
+- [x] 26 項後端測試、前端建置、隔離瀏覽器匯入測試及真實 ComfyUI 圖片讀取測試。
+- [ ] 安裝 checkpoint 後驗證「生成 → 完成 → 匯入作品」完整實機流程。
+- [ ] 作品收藏、備註、封存與一鍵載入創作設定。
````

</details>

<a id="commit-58c5c1e55098032ea7e811aa64338a4fe65eb86d"></a>

### 19:59:51 · [58c5c1e](https://github.com/Zimkjdv/Model-Atelier/commit/58c5c1e55098032ea7e811aa64338a4fe65eb86d) · docs: add Windows launcher and shutdown guide

來源：[完整清單原檔](https://github.com/Zimkjdv/Model-Atelier/blob/58c5c1e55098032ea7e811aa64338a4fe65eb86d/%E5%B9%B3%E5%8F%B0%E9%96%8B%E7%99%BC%E6%B8%85%E5%96%AE.md)；檔名 `平台開發清單.md`；Git blob `2fcd6dd7baf97b0916bafe7d0fa2e13f68a66194`。

當時核取框：142，已勾選 40、未勾選 102。作者時間 `2026-09-06T19:59:51+08:00`；提交時間 `2026-09-06T19:59:51+08:00`。

<details>
<summary>完整清單差異（含項目、勾選與驗收變動）</summary>

````diff
--- 平台開發清單.md
+++ 平台開發清單.md
@@ -123 +123 @@
-- [ ] 提供啟動、停止與故障排查說明。
+- [x] 提供 PowerShell 與 `start-all.bat` 啟動方式、Ctrl+C 停止方式與基本故障排查說明。
````

</details>

## 2026-10-02

<a id="commit-f167b9ad4d04874098a4118d02d13042741eaca2"></a>

### 19:35:40 · [f167b9a](https://github.com/Zimkjdv/Model-Atelier/commit/f167b9ad4d04874098a4118d02d13042741eaca2) · Add artwork settings restoration and editable sampling controls

來源：[完整清單原檔](https://github.com/Zimkjdv/Model-Atelier/blob/f167b9ad4d04874098a4118d02d13042741eaca2/%E5%B9%B3%E5%8F%B0%E9%96%8B%E7%99%BC%E6%B8%85%E5%96%AE.md)；檔名 `平台開發清單.md`；Git blob `791745d1742d48419893557e18804219e7da733c`。

當時核取框：156，已勾選 55、未勾選 101。作者時間 `2026-10-02T19:35:40+08:00`；提交時間 `2026-10-02T19:35:40+08:00`。

<details>
<summary>完整清單差異（含項目、勾選與驗收變動）</summary>

````diff
--- 平台開發清單.md
+++ 平台開發清單.md
@@ -7 +7 @@
-更新日期：2026-09-06
+更新日期：2026-10-02
@@ -10 +10 @@
-### 開發進度（2026-09-06）
+### 開發進度（更新至 2026-10-02）
@@ -28,0 +29,5 @@
+- [x] 完成作品「載入創作設定」API 與按鈕：保留原引擎、64 位元 seed、latent 輸入尺寸、正／負提示詞與取樣設定，載入為新草稿且不自動提交。
+- [x] 作品載入保護工作台未保存變更；原引擎、模型清單與版本不符時顯示提示，不默默替換模型或版本。
+- [x] 創作草稿支援負面提示詞、steps、CFG、sampler、scheduler、denoise 編輯、保存及提交；舊草稿新增欄位採相容預設值。
+- [x] 不支援完整對應表單的工作流程回傳 422，不載入部分參數或覆寫目前內容；完整工作流程仍可下載。
+- [x] 34 項後端測試、Vue 型別檢查／建置及作品載入的隔離瀏覽器驗證通過；確認原參數、未保存保護、保存新草稿、舊草稿預設值及再次提交的離線錯誤。
@@ -122 +127 @@
-- [ ] 支援從作品載入原設定，再次提交。
+- [x] 支援從標準單張文生圖作品載入原設定為新草稿，由使用者調整、保存或再次提交；實際 GPU 生成另待 checkpoint 驗證。
@@ -130 +135,2 @@
-- [ ] 作品可一鍵載入原設定，作為繼續創作的起點；圖片並排比較於 P6 實作。
+- [x] 作品可一鍵載入支援流程的原設定，作為繼續創作的起點；保留未保存變更確認及來源版本提示。
+- 圖片並排比較仍於 P6 實作。
@@ -288 +294,13 @@
-- [ ] 作品收藏、備註、封存與一鍵載入創作設定。
+- [ ] 作品收藏、備註與封存。
+
+## 本次增量：作品載入創作設定（2026-10-02）
+
+- [x] 作品卡片及預覽提供「載入創作設定」，只讀本機快照，不啟動生成任務。
+- [x] 從完整標準工作流程解析原引擎、checkpoint、正／負提示詞、精確 seed、latent 尺寸與取樣設定。
+- [x] 載入為新草稿；保護目前未保存內容，保留舊草稿、作品與未確認提交請求。
+- [x] 原模型版本、引擎不符及模型清單狀態提示；未知版本仍顯示未知。
+- [x] 負面提示詞、steps、CFG、sampler、scheduler、denoise 可編輯、保存與提交，舊草稿使用相容預設值。
+- [x] 無法完整還原的自訂流程、額外分支或批次回傳 422，可下載原始 JSON；不默默遺漏設定。
+- [x] Vue 型別檢查及正式建置通過。
+- [x] 34 項後端測試及隔離瀏覽器驗證通過；載入／保存不新增生成任務，再次提交保留完整參數並明確顯示離線失敗。隔離服務與資料已清理。
+- [ ] 尚無 checkpoint；實際 GPU 出圖、P1 完整實機驗收與 P2 模型整合仍待驗證。
````

</details>

<a id="commit-8fcc9460fe03f158577cea09deba2f91e43a81d9"></a>

### 19:56:50 · [8fcc946](https://github.com/Zimkjdv/Model-Atelier/commit/8fcc9460fe03f158577cea09deba2f91e43a81d9) · Add safe cancellation for queued ComfyUI jobs

來源：[完整清單原檔](https://github.com/Zimkjdv/Model-Atelier/blob/8fcc9460fe03f158577cea09deba2f91e43a81d9/%E5%B9%B3%E5%8F%B0%E9%96%8B%E7%99%BC%E6%B8%85%E5%96%AE.md)；檔名 `平台開發清單.md`；Git blob `10ba27fa50f7c0d696508397fc6da327a11ed07b`。

當時核取框：162，已勾選 62、未勾選 100。作者時間 `2026-10-02T19:56:50+08:00`；提交時間 `2026-10-02T19:56:50+08:00`。

<details>
<summary>完整清單差異（含項目、勾選與驗收變動）</summary>

````diff
--- 平台開發清單.md
+++ 平台開發清單.md
@@ -123 +123 @@
-- [ ] 顯示排隊、執行、完成、失敗及取消狀態。
+- [x] 顯示排隊、執行、完成、失敗、取消確認中與取消結果待確認等狀態。
@@ -125 +125,2 @@
-- [ ] 支援取消排隊任務；執行中停止需確認引擎語意，避免中斷其他任務。
+- [x] 支援取消指定排隊任務；保留取消紀錄與結果確認，不清空佇列或停止執行中任務。
+- [ ] 執行中停止仍需另行驗證引擎語意，避免中斷其他任務。
@@ -306,0 +308,8 @@
+
+## 優先項目 1：安全取消排隊任務（2026-10-02）
+
+- [x] 提供任務取消 API 與操作入口，只移除原引擎中身分相符的排隊項目。
+- [x] 以佇列與歷史確認結果，保留工作流程、模型版本與取消紀錄；結果不明時不自動重新提交。
+- [x] 任務已開始執行時拒絕排隊刪除；其他排隊與執行中的任務不受影響。
+- [x] 修訂號與取消租約防止並行回應覆蓋新狀態，原 prompt ID 不因其他任務的中繼資料被改寫。
+- [x] 51 項後端測試、Vue 型別檢查／建置通過；隔離瀏覽器驗證確認取消指定任務、保留其他排隊／執行項目與完整工作流程。測試服務與資料已清理。
````

</details>

<a id="commit-97ecabea4bffe86b445af6b8682df83867227180"></a>

### 20:12:53 · [97ecabe](https://github.com/Zimkjdv/Model-Atelier/commit/97ecabea4bffe86b445af6b8682df83867227180) · Stream ComfyUI job progress and recover original tasks

來源：[完整清單原檔](https://github.com/Zimkjdv/Model-Atelier/blob/97ecabea4bffe86b445af6b8682df83867227180/%E5%B9%B3%E5%8F%B0%E9%96%8B%E7%99%BC%E6%B8%85%E5%96%AE.md)；檔名 `平台開發清單.md`；Git blob `d068356d400c97cf405deade7909bfc7682ed656`。

當時核取框：168，已勾選 69、未勾選 99。作者時間 `2026-10-02T20:12:53+08:00`；提交時間 `2026-10-02T20:12:53+08:00`。

<details>
<summary>完整清單差異（含項目、勾選與驗收變動）</summary>

````diff
--- 平台開發清單.md
+++ 平台開發清單.md
@@ -124 +124 @@
-- [ ] 接收進度事件；斷線重連後查詢任務，避免重複提交。
+- [x] 接收原任務節點進度事件；斷線重連後查詢佇列／歷史，避免重複提交；實際 GPU 事件另待驗證。
@@ -315,0 +316,9 @@
+
+## 優先項目 2：即時進度與斷線恢復（2026-10-02）
+
+- [x] 原引擎 WebSocket → 平台 SSE → 創作頁節點進度，精確核對 prompt ID 與工作流程節點。
+- [x] 同任務共用上游連線，跨程序監聽租約、訂閱上限、訊息及寫入頻率限制。
+- [x] 有限重連及低頻查詢；完成／失敗需歷史確認，保留最後進度與更新時間，不自動重新提交。
+- [x] 取消確認與終止狀態不被進度覆寫；離開創作頁、隱藏分頁及 HTTP 中斷清理連線。
+- [x] 啟動腳本加入優雅關閉等待上限；更新 requirements 與鎖定版本。
+- [x] 69 項後端測試、Vue 型別檢查／建置與依賴檢查通過；隔離瀏覽器驗證進度、重連、完成及監聽清理。
````

</details>

<a id="commit-1b13d47b78aec0d1e52c42eaaea925d8031988de"></a>

### 20:25:41 · [1b13d47](https://github.com/Zimkjdv/Model-Atelier/commit/1b13d47b78aec0d1e52c42eaaea925d8031988de) · Discover ComfyUI sampling capabilities before submission

來源：[完整清單原檔](https://github.com/Zimkjdv/Model-Atelier/blob/1b13d47b78aec0d1e52c42eaaea925d8031988de/%E5%B9%B3%E5%8F%B0%E9%96%8B%E7%99%BC%E6%B8%85%E5%96%AE.md)；檔名 `平台開發清單.md`；Git blob `94333ef960dd4e1a9a06b6e324c43db9bd3667e8`。

當時核取框：174，已勾選 76、未勾選 98。作者時間 `2026-10-02T20:25:41+08:00`；提交時間 `2026-10-02T20:25:41+08:00`。

<details>
<summary>完整清單差異（含項目、勾選與驗收變動）</summary>

````diff
--- 平台開發清單.md
+++ 平台開發清單.md
@@ -121 +121 @@
-- [ ] 提交前驗證必填值、參數範圍及所需模型是否存在。
+- [x] 標準 checkpoint 文生圖提交前驗證必填值、平台／引擎取樣範圍及模型是否存在；其他模型架構另行驗證。
@@ -324,0 +325,9 @@
+
+## 優先項目 3：動態取樣選項與提交前相容驗證（2026-10-02）
+
+- [x] 從目前 ComfyUI KSampler 同步 sampler／scheduler 及 steps、CFG、denoise 範圍，按引擎保存快照與同步時間。
+- [x] 創作頁提供實際選項、範圍交集及離線／未知／不相容提示；保留草稿及作品原值，不默默重設選項或截短數值。
+- [x] 新生成及直接工作流程提交重新讀取能力，所有 KSampler 參數及原引擎確認後才送出；不以過期快照授權生成。
+- [x] 精確 request ID 恢復仍回原任務，不重新查能力或重送；直接工作流程也限制精確 seed、平台 latent 尺寸及 batch 1。
+- [x] RTX 3060 上真實 ComfyUI 0.34.0 同步成功：45 種 sampler、9 種 scheduler；checkpoint 清單仍為空，未進行 GPU 推論。
+- [x] 84 項後端測試、Vue 型別檢查／建置與依賴檢查通過；隔離瀏覽器驗證選項更新、提交前拒絕、原值保存、精確參數及離線快照。測試服務與資料已清理。
````

</details>

<a id="commit-6578394b9c0ff91c9f4403d0cae876b148aa0216"></a>

### 22:26:46 · [6578394](https://github.com/Zimkjdv/Model-Atelier/commit/6578394b9c0ff91c9f4403d0cae876b148aa0216) · Install Pony V6 XL and verify local GPU generation

來源：[完整清單原檔](https://github.com/Zimkjdv/Model-Atelier/blob/6578394b9c0ff91c9f4403d0cae876b148aa0216/%E5%B9%B3%E5%8F%B0%E9%96%8B%E7%99%BC%E6%B8%85%E5%96%AE.md)；檔名 `平台開發清單.md`；Git blob `a5b7d0efe263d9fc4e197f03a57050e585cbfb84`。

當時核取框：179，已勾選 100、未勾選 79。作者時間 `2026-10-02T22:26:46+08:00`；提交時間 `2026-10-02T22:26:46+08:00`。

<details>
<summary>完整清單差異（含項目、勾選與驗收變動）</summary>

````diff
--- 平台開發清單.md
+++ 平台開發清單.md
@@ -16 +16 @@
-- [x] 本地瀏覽器驗證硬體資訊與設定保存：RTX 3060 12GiB、約 64GiB RAM；ComfyUI 預設位址目前未連線，尚未完成真實引擎整合驗證。
+- [x] 本地瀏覽器驗證硬體資訊與設定保存：RTX 3060 12GiB、約 64GiB RAM；初期 ComfyUI 尚未連線，後續已完成下方引擎與 Pony 實機驗收。
@@ -35 +35 @@
-- [ ] 尚未安裝 checkpoint，非空模型清單、實際模型載入與生成仍待驗證；工作流程提交及作品庫匯入已實作，已用測試圖片驗證讀取流程。
+- [x] 安裝作者固定修訂的 Pony V6 XL，完整大小與 SHA256 驗證；RTX 3060 真實模型同步、GPU 生成、作品匯入、即時節點進度、設定載入與重啟後離線讀取通過，詳見 `docs/validation/pony-v6-xl-rtx3060.md`。
@@ -72,5 +72,5 @@
-- [ ] 規劃由平台自動偵測 GPU 型號、VRAM、RAM 與可用磁碟空間，於 P1 實作系統資訊頁。
-- [ ] 確認 GPU 執行於本機或獨立主機；Web 平台與推論引擎分離。
-- [ ] 確認 Windows 原生或 WSL 的推論環境。
-- [x] 確認前端方案：Vue 3 + TypeScript；此項為選型定案，尚未實作。
-- [x] 確認後端方案：Python + FastAPI；ComfyUI 負責模型執行，此項為選型定案，尚未實作。
+- [x] 平台偵測 GPU 型號、VRAM、RAM 與可用磁碟空間，已提供系統資訊頁。
+- [x] 首輪 GPU 在本機執行；Web 平台與 ComfyUI 以不同環境及程序運行。
+- [x] 首輪使用 Windows 原生推論環境。
+- [x] 前端採 Vue 3 + TypeScript，已實作。
+- [x] 後端採 Python + FastAPI；ComfyUI 負責模型執行，已實作。
@@ -78,3 +78,3 @@
-- [ ] 確認資料方案：初期 SQLite + 本地檔案目錄。
-- [ ] 定義模型、輸入素材、輸出、縮圖及資料庫的儲存位置。
-- [ ] 定義本機存取設定；若開放區網或遠端，再加入驗證與連線保護。
+- [x] 初期資料採 SQLite + 本地檔案目錄。
+- [x] 模型在 `runtime/ComfyUI`，素材／作品／縮圖與 SQLite 在 `data/`，README 說明備份。
+- [x] 啟動腳本綁定 `127.0.0.1`；若開放區網或遠端，再加入驗證與連線保護。
@@ -106 +106 @@
-- [ ] 以現有 RTX 3060 主機完成首輪開發與驗證，保存實際硬體、環境版本及工作流程設定。
+- [x] RTX 3060 完成 Pony V6 XL 單張風景生成驗收，保存硬體、環境版本及完整工作流程設定；其他負載另測。
@@ -116,5 +116,5 @@
-- [ ] 建立前後端專案與環境設定範例。
-- [ ] 建立創作工作台、模型庫、作品庫、系統資訊、設定頁的基本導覽。
-- [ ] 支援設定 ComfyUI 位址與連線健康檢查。
-- [ ] 建立執行引擎介面，避免前端直接依賴 ComfyUI API。
-- [ ] 匯入一套已驗證的工作流程，定義可由表單修改的欄位。
+- [x] 建立前後端專案與環境設定範例。
+- [x] 建立創作工作台、模型庫、作品庫、系統資訊、設定頁的基本導覽。
+- [x] 支援設定 ComfyUI 位址與連線健康檢查。
+- [x] 平台後端封裝引擎連線，前端使用平台 API。
+- [x] 標準 checkpoint 單張文生圖流程已在 Pony V6 XL 驗證，表單可編輯提示詞及取樣欄位。
@@ -122 +122 @@
-- [ ] 提交任務並保存平台任務 ID 與引擎任務 ID 的對應。
+- [x] 提交任務並保存平台任務 ID 與引擎任務 ID 的對應。
@@ -124 +124 @@
-- [x] 接收原任務節點進度事件；斷線重連後查詢佇列／歷史，避免重複提交；實際 GPU 事件另待驗證。
+- [x] 接收原任務節點進度事件；斷線重連後查詢佇列／歷史，避免重複提交；RTX 3060 GPU 取樣進度已在瀏覽器確認。
@@ -128 +128 @@
-- [x] 支援從標準單張文生圖作品載入原設定為新草稿，由使用者調整、保存或再次提交；實際 GPU 生成另待 checkpoint 驗證。
+- [x] 標準單張文生圖作品可載入原設定為新草稿；已用 Pony GPU 作品驗證精確 seed、取樣設定及再次生成。
@@ -161 +161 @@
-- [ ] 核對 Pony V6 XL 的正式來源、版本、授權及依賴。
+- [x] 固定 Pony V6 XL 作者來源／修訂與 SHA256，記錄模型卡授權標記及依賴；完整授權條款仍待核對。
@@ -169 +169 @@
-- [ ] 測量生成耗時與記憶體需求，記錄測量環境。
+- [x] 記錄 Pony V6 XL 單張 RTX 3060 生成耗時與設備顯存取樣；其他模型／負載未測量。
@@ -282 +282 @@
-- [ ] 安裝 checkpoint 後驗證完整成功生成及實際 VRAM／耗時。
+- [x] Pony V6 XL 已完成成功生成及 VRAM／耗時取樣，見實機驗收紀錄。
@@ -294 +294 @@
-- [ ] 安裝 checkpoint 後驗證「生成 → 完成 → 匯入作品」完整實機流程。
+- [x] Pony V6 XL 已完成「生成 → 完成 → 匯入作品」完整實機流程。
@@ -307 +307 @@
-- [ ] 尚無 checkpoint；實際 GPU 出圖、P1 完整實機驗收與 P2 模型整合仍待驗證。
+- [x] 已完成 Pony V6 XL GPU 出圖與重啟後作品／設定保存驗收；Animagine、FLUX 與其他硬體未驗證。
@@ -333,0 +334,8 @@
+
+## 本輪優先項目 1：Pony 安裝與 P1 實機驗收（2026-10-02）
+
+- [x] 作者固定修訂 manifest、完整檔案大小與 SHA256、續傳／原子發布／安裝互斥；runtime 權重不納入 Git。
+- [x] 只提交一次的 NVIDIA GPU 驗收 CLI；保存原 UUID、完整 workflow、精確 seed、耗時範圍與顯存取樣，查詢錯誤不自動重送。
+- [x] RTX 3060 真實生成、作品保存、介面節點進度與載入設定通過。
+- [x] 停止引擎與平台後，只重啟平台，原圖、模型版本、精確參數與流程可離線讀取並與原報告比對。
+- [x] 116 項後端測試、Vue 型別檢查／建置及依賴檢查通過（1 項 Windows symlink 權限跳過），保存實機驗收紀錄 `docs/validation/pony-v6-xl-rtx3060.md`。
````

</details>

<a id="commit-d4391de9650b567ff2c7577a63a6e4e23c8c78a9"></a>

### 22:38:18 · [d4391de](https://github.com/Zimkjdv/Model-Atelier/commit/d4391de9650b567ff2c7577a63a6e4e23c8c78a9) · Record model metadata and preserve submission snapshots

來源：[完整清單原檔](https://github.com/Zimkjdv/Model-Atelier/blob/d4391de9650b567ff2c7577a63a6e4e23c8c78a9/%E5%B9%B3%E5%8F%B0%E9%96%8B%E7%99%BC%E6%B8%85%E5%96%AE.md)；檔名 `平台開發清單.md`；Git blob `9f0847bdb5eccb9f8678aad5f161bf58f4db66c7`。

當時核取框：184，已勾選 107、未勾選 77。作者時間 `2026-10-02T22:38:18+08:00`；提交時間 `2026-10-02T22:38:18+08:00`。

<details>
<summary>完整清單差異（含項目、勾選與驗收變動）</summary>

````diff
--- 平台開發清單.md
+++ 平台開發清單.md
@@ -36 +36 @@
-- [ ] 模型庫後續補齊檔案雜湊、大小、版本與架構等資料；目前來源與備註為使用者登記資訊，不能視為已驗證。
+- [x] 模型庫可登記檔案雜湊、大小、架構及授權資訊，新任務／作品保存當時快照；登記值不視為驗檔、授權或相容性證明，舊紀錄缺少快照保持未知。
@@ -164 +164 @@
-- [ ] 記錄模型名稱、架構、版本、檔案大小、雜湊、來源與授權連結。
+- [x] 模型庫登記名稱、架構、版本、檔案大小、SHA256、來源與授權連結，並保存提交時快照。
@@ -341,0 +342,8 @@
+
+## 本輪優先項目 2：模型資料與歷史快照（2026-10-02）
+
+- [x] 模型庫新增架構、大小、完整 SHA256、授權名稱／網址及更新時間，使用者登記與已驗證資訊明確區分。
+- [x] 提交保存模型資料快照，作品從原任務複製；修改模型庫、重新匯入及原 ID 恢復不改寫既有快照。
+- [x] 舊紀錄缺少資料時顯示未知，不從目前模型庫回填；作品圖片 hash 與模型檔案 hash 分開。
+- [x] 同步及離線保留資料，metadata／清單／偏好以 SQLite 原子操作避免覆寫。
+- [x] 129 項後端測試（1 項既有 Windows 權限跳過）、Vue 型別檢查／建置通過；真實 Pony 登記與隔離瀏覽器快照、原 ID 恢復、重複匯入及舊作品未知驗收通過。
````

</details>

<a id="commit-65175c465a241fe06761c6d460e07c0016bcac17"></a>

### 22:58:07 · [65175c4](https://github.com/Zimkjdv/Model-Atelier/commit/65175c465a241fe06761c6d460e07c0016bcac17) · Add explicit model presets and architecture compatibility checks

來源：[完整清單原檔](https://github.com/Zimkjdv/Model-Atelier/blob/65175c465a241fe06761c6d460e07c0016bcac17/%E5%B9%B3%E5%8F%B0%E9%96%8B%E7%99%BC%E6%B8%85%E5%96%AE.md)；檔名 `平台開發清單.md`；Git blob `fdc3df85b9343678b5262026a65f065cbb996104`。

當時核取框：190，已勾選 116、未勾選 74。作者時間 `2026-10-02T22:58:07+08:00`；提交時間 `2026-10-02T22:58:07+08:00`。

<details>
<summary>完整清單差異（含項目、勾選與驗收變動）</summary>

````diff
--- 平台開發清單.md
+++ 平台開發清單.md
@@ -134 +134 @@
-- [ ] 依選定模型與工作流程顯示適用選項，不相容設定需清楚說明原因。
+- [x] 依登記架構顯示標準流程與模型起始預設，已知未支援架構說明原因並拒絕新提交；跨架構專用流程仍待實作。
@@ -165 +165 @@
-- [ ] 建立每個模型獨立的工作流程與參數預設。
+- [x] 已提供 Pony V6 XL、SDXL 與 SD 1.x 的明確套用預設；SD 系列共用標準流程，跨架構工作流程另於 P5 實作。
@@ -168 +168 @@
-- [ ] 切換模型時重新檢查相容性，不沿用不適用的參數或元件。
+- [x] 切換模型重新檢查登記架構與引擎能力，保留原值並明確提示；預設需確認套用，已知不適用架構拒絕新的標準提交。
@@ -349,0 +350,9 @@
+
+## 本輪優先項目 3：模型預設與架構相容檢查（2026-10-02）
+
+- [x] 只讀模型 profile API：Pony 依登記 SDXL＋完整固定 hash 匹配，SDXL／SD 1.x 起始預設明註未逐模型驗證，未知不推測。
+- [x] 創作頁顯示預設差異與明確確認，只修改七項取樣／尺寸參數；切換模型、載入草稿與作品保留原內容。
+- [x] 新表單生成與直接工作流程提交均阻擋已登記 FLUX／SD 3.x／其他不支援架構，保存失敗任務且不發送 prompt。
+- [x] 驗證期間重新檢查架構；仍適用標準流程的變更不改原參數或快照，原 ID 恢復不重新查模型或提交。
+- [x] 140 項後端測試通過（1 項既有 Windows 權限跳過）、Vue 型別檢查／建置通過；瀏覽器驗證預設確認／取消、切換、同模型草稿與作品還原，隔離 API 驗證兩個入口阻擋且不送 prompt、自訂參數與完整 seed 保留。RTX 4080 仍待實機驗證。
+- [x] 驗收服務停止、隔離資料清理，8000／8188／5173／8001 均未監聽；真實模型與作品保留。
````

</details>

<a id="commit-bfbae935974c587ed00f7ed6d58ce79898cf5803"></a>

### 23:46:47 · [bfbae93](https://github.com/Zimkjdv/Model-Atelier/commit/bfbae935974c587ed00f7ed6d58ce79898cf5803) · Diagnose generation failures and restore failed job settings

來源：[完整清單原檔](https://github.com/Zimkjdv/Model-Atelier/blob/bfbae935974c587ed00f7ed6d58ce79898cf5803/%E5%B9%B3%E5%8F%B0%E9%96%8B%E7%99%BC%E6%B8%85%E5%96%AE.md)；檔名 `平台開發清單.md`；Git blob `a0019304400629fa1d79d60704c9198719e69e9e`。

當時核取框：195，已勾選 125、未勾選 70。作者時間 `2026-10-02T23:46:47+08:00`；提交時間 `2026-10-02T23:46:47+08:00`。

<details>
<summary>完整清單差異（含項目、勾選與驗收變動）</summary>

````diff
--- 平台開發清單.md
+++ 平台開發清單.md
@@ -105 +105 @@
-- [ ] 執行記憶體不足時保留原設定並提供調整與重試入口；不默默改動解析度、精度或模型。
+- [x] 已確認 CUDA OOM 時保存安全診斷及原設定，失敗任務可載入設定手動調整後建立新請求；不自動改動解析度、精度或模型，未知結果仍恢復原 ID。
@@ -135 +135 @@
-- [ ] 清楚呈現排隊、執行、完成及失敗狀態，提供適用的取消與重新執行操作。
+- [x] 清楚呈現任務狀態、排隊取消與失敗診斷；已確認失敗任務可載入原設定手動調整後提交新任務，未知結果不自動重送。
@@ -170 +170 @@
-- [ ] 處理模型遺失、載入失敗及 GPU 記憶體不足。
+- [x] 保存模型遺失、載入失敗與 CUDA OOM 的安全診斷及處理建議，失敗任務可完整載入原設定；保留原流程與錯誤 JSON。
@@ -257,2 +257,2 @@
-- [x] ComfyUI 已安裝於 `runtime/ComfyUI`；目前 checkpoint 目錄為空，未下載模型。
-- [ ] 確認第一個模型採 Pony V6 XL，或依硬體與實測調整。
+- [x] ComfyUI 已安裝於 `runtime/ComfyUI`；Pony V6 XL 已下載且通過完整 SHA256 與 RTX 3060 生成驗收。
+- [x] 第一個模型採 Pony V6 XL，固定來源、修訂與實測紀錄見本輪優先項目 1。
@@ -358,0 +359,8 @@
+
+## 後續優先項目 1：失敗診斷與原設定恢復（2026-10-02）
+
+- [x] 區分模型遺失、載入失敗、CUDA 顯存不足及其他提交／執行錯誤，依原歷史與節點身分分類，不把未知錯誤猜成 OOM。
+- [x] 任務 API 與即時摘要提供安全說明及建議，完整上游歷史／錯誤保存於 JSON，介面不展開原始 traceback。
+- [x] 僅已確認失敗任務可完整還原標準流程為新草稿，保留精確 seed、原版本、模型快照與取樣值，並保護未保存內容。
+- [x] 載入不提交、原 ID 恢復不重送；手動調整後明確生成才建立新請求，舊任務保持不變。
+- [x] 153 項後端測試（1 項既有 Windows 權限跳過）與 Vue 建置通過；隔離瀏覽器驗證診斷、精確 seed、原版本、未保存保護及一次明確新提交。錯誤使用模擬引擎，未刻意造成真實 OOM；服務與隔離資料已清理。
````

</details>

## 2026-10-03

<a id="commit-d6364f5415ea13d20613a81dbdd0be924927ab06"></a>

### 00:04:05 · [d6364f5](https://github.com/Zimkjdv/Model-Atelier/commit/d6364f5415ea13d20613a81dbdd0be924927ab06) · Register existing local checkpoint directories for ComfyUI

來源：[完整清單原檔](https://github.com/Zimkjdv/Model-Atelier/blob/d6364f5415ea13d20613a81dbdd0be924927ab06/%E5%B9%B3%E5%8F%B0%E9%96%8B%E7%99%BC%E6%B8%85%E5%96%AE.md)；檔名 `平台開發清單.md`；Git blob `70c02e518d1d25ddef6daa2a5ef48b9e1b7dfb84`。

當時核取框：200，已勾選 131、未勾選 69。作者時間 `2026-10-03T00:04:05+08:00`；提交時間 `2026-10-03T00:04:05+08:00`。

<details>
<summary>完整清單差異（含項目、勾選與驗收變動）</summary>

````diff
--- 平台開發清單.md
+++ 平台開發清單.md
@@ -163 +163 @@
-- [ ] 支援登記既有本地模型路徑，第一版不強制複製大型檔案。
+- [x] 支援登記既有本地 checkpoint 目錄，不複製大型檔案；受管理 ComfyUI 需重啟後再同步，其他引擎不套用此設定。
@@ -366,0 +367,8 @@
+
+## 後續優先項目 2：既有本地模型目錄（2026-10-03）
+
+- [x] 設定頁登記最多八個本機絕對 checkpoint 目錄，保存順序、修訂衝突及可讀／容量未知提示，不搬移或刪除模型。
+- [x] 純標準庫匯出工具產生固定 runtime 設定，原子寫入並限制路徑；啟動腳本檢查匯出結果，失敗時停止，不沿用舊設定。
+- [x] ComfyUI 原搜尋範圍保留，額外路徑只套用受管理本機啟動；遠端引擎不宣稱已套用，保存後提示重啟與同步。
+- [x] 170 項後端測試（1 項既有 Windows 權限跳過）及 Vue 建置通過，含實際 PowerShell 空白路徑參數與匯出失敗保護測試。
+- [x] 真實 ComfyUI 驗證登記／移除後重啟、原 Pony 保留；瀏覽器驗證衝突與重新讀取。測試檔僅用於列舉，未做新推論；測試檔清理、服務停止。
````

</details>

<a id="commit-4bc2d5ca4a89c8302e5b248d0756c647ea8ec4d4"></a>

### 00:29:50 · [4bc2d5c](https://github.com/Zimkjdv/Model-Atelier/commit/4bc2d5ca4a89c8302e5b248d0756c647ea8ec4d4) · Add engine environment diagnostics and manual local checks

來源：[完整清單原檔](https://github.com/Zimkjdv/Model-Atelier/blob/4bc2d5ca4a89c8302e5b248d0756c647ea8ec4d4/%E5%B9%B3%E5%8F%B0%E9%96%8B%E7%99%BC%E6%B8%85%E5%96%AE.md)；檔名 `平台開發清單.md`；Git blob `b7839e8014537c8d132c9aaf1556a9fde607ad80`。

當時核取框：206，已勾選 147、未勾選 59。作者時間 `2026-10-03T00:29:50+08:00`；提交時間 `2026-10-03T00:29:50+08:00`。

<details>
<summary>完整清單差異（含項目、勾選與驗收變動）</summary>

````diff
--- 平台開發清單.md
+++ 平台開發清單.md
@@ -100 +100 @@
-- [ ] 檢查模型執行環境的 GPU、驅動、PyTorch 與 CUDA 可用狀態；資料不可得時標示未知。
+- [x] 檢查選定引擎的裝置與 PyTorch 版本，另提供固定本機 ComfyUI Python 的手動 CUDA／驅動檢查；不同來源分開，資料不可得時標示未知。
@@ -146,4 +146,4 @@
-- [ ] 由後端或模型執行主機上的資訊採集介面讀取硬體資料，不以瀏覽器所在電腦代表模型執行環境。
-- [ ] 顯示 GPU 型號；多 GPU 時逐張列出，並標示引擎使用的裝置，無法確認時顯示未知。
-- [ ] 顯示各 GPU 的 VRAM 總量、已用量與可用量，統一容量單位。
-- [ ] 顯示模型執行主機的 RAM 總量、已用量與可用量。
+- [x] 由平台後端與選定 ComfyUI `/system_stats` 讀取各自硬體資料，不以瀏覽器電腦代表模型執行環境。
+- [x] 逐裝置顯示引擎回報名稱、類型及索引；每個任務實際使用的 GPU 無法由此確認，保持未知。
+- [x] 顯示引擎回報的 VRAM 總量、已用量與可用量，統一 GiB；CPU 裝置區分記憶體標籤。
+- [x] 顯示模型執行主機回報 RAM 總量、已用量與可用量；無效數值保持未知。
@@ -151,5 +151,5 @@
-- [ ] 平台與推論引擎分開部署時，分別標示主機角色與資料來源；素材及輸出磁碟資訊依其實際儲存主機顯示。
-- [ ] 進入系統資訊頁時自動取得資料，提供手動重新整理、定期更新及最後更新時間。
-- [ ] 若遠端介面不提供某項資訊，顯示「無法取得」及原因，不以平台主機資料代替，也不顯示為零。
-- [ ] 處理無 GPU、驅動或權限不足、主機離線等狀態；保留的舊資料需明確標示已過期。
-- [ ] 第一版以資訊顯示為主；單靠剩餘 VRAM 不保證模型可執行。
+- [x] 分別顯示平台／引擎角色與來源；平台資料磁碟取自實際資料目錄，遠端磁碟未提供時顯示未知。
+- [x] 系統資訊自動取得、每 15 秒與手動更新並附時間；本機 Python 檢查僅明確按鈕觸發。
+- [x] 遠端介面未提供的 CUDA、驅動及磁碟資訊保持未知並說明原因，不以平台資訊代替或填零。
+- [x] 無 GPU／CUDA 不可用／缺環境／逾時／離線分開顯示；平台舊資料與本機快照提示可能已過期，引擎失效時清除舊診斷。
+- [x] 第一版以資訊顯示為主；單靠剩餘 VRAM 不保證模型可執行。
@@ -374,0 +375,9 @@
+
+## 後續優先項目 3：來源明確的環境診斷（2026-10-03）
+
+- [x] 選定引擎診斷 API、版本與裝置／RAM／VRAM 數值正規化，附來源及時間；不從 PyTorch 後綴推測 CUDA 或以平台硬體補遠端資訊。
+- [x] 固定本機 ComfyUI Python 的明確手動檢查，包含 PyTorch、CUDA 建置版本／可用性、裝置屬性與本機 nvidia-smi 驅動；無模型載入或生成。
+- [x] GET 只讀程序內快照，POST 拒絕自訂命令／參數；並行檢查 409、20 秒逾時停止／回收子程序，HTTP 中止不提前解除執行鎖。
+- [x] 引擎設定切換後舊回應不覆蓋新來源，另一視窗切換使診斷失效、裝置清空，介面保留輸入並提示確認。
+- [x] 190 項後端測試通過（1 項既有 Windows 權限跳過）、Vue 型別檢查／建置及唯讀審查通過。
+- [x] RTX 3060 真實環境檢查及 ComfyUI 0.34.0 回報通過；隔離 API／瀏覽器驗證同名多 GPU、無效容量、CPU 標籤、離線與引擎切換。不新增生成任務，正式資料不變；服務停止、隔離資料清理，RTX 4080 仍待實機驗證。
````

</details>

<a id="commit-6cb5e1ce5d4be67f3529c4d412a38312d888a2dd"></a>

### 01:34:42 · [6cb5e1c](https://github.com/Zimkjdv/Model-Atelier/commit/6cb5e1ce5d4be67f3529c4d412a38312d888a2dd) · feat: expose condition-scoped model validation records

來源：[完整清單原檔](https://github.com/Zimkjdv/Model-Atelier/blob/6cb5e1ce5d4be67f3529c4d412a38312d888a2dd/%E5%B9%B3%E5%8F%B0%E9%96%8B%E7%99%BC%E6%B8%85%E5%96%AE.md)；檔名 `平台開發清單.md`；Git blob `37b2eed159b4238020db5f74c666d3f8c4677926`。

當時核取框：210，已勾選 151、未勾選 59。作者時間 `2026-10-03T01:34:42+08:00`；提交時間 `2026-10-03T01:34:42+08:00`。

<details>
<summary>完整清單差異（含項目、勾選與驗收變動）</summary>

````diff
--- 平台開發清單.md
+++ 平台開發清單.md
@@ -101 +101 @@
-- [ ] 建立模型與工作流程的相容性紀錄，區分已驗證、未驗證及已知不相容。
+- [x] 建立模型與工作流程的相容性紀錄，區分已驗證、未驗證及已知不相容。
@@ -383,0 +384,7 @@
+
+## 本輪優先項目 1：條件化流程驗證紀錄（2026-10-03）
+
+- [x] 模型庫與創作頁顯示 SHA256／架構匹配的實測條件、來源、環境、精度、卸載、耗時與設備顯存取樣。
+- [x] 無匹配證據顯示尚未驗證；不以名稱推定相容，也不把登記紀錄當成目前檔案驗證。
+- [x] 194 項後端測試通過（1 項既有 Windows symlink 權限跳過），Vue 型別檢查與建置通過，實際模型庫顯示確認。修正 PowerShell 測試輸出遇系統編碼時的解碼例外。
+- [ ] 訓練及 RTX 4080 的實測資源紀錄仍待驗證。
````

</details>

<a id="commit-0a9b72aa75ce2c7bb7ef89f136dbe742a10e506f"></a>

### 01:39:12 · [0a9b72a](https://github.com/Zimkjdv/Model-Atelier/commit/0a9b72aa75ce2c7bb7ef89f136dbe742a10e506f) · feat: add non-blocking generation resource advice

來源：[完整清單原檔](https://github.com/Zimkjdv/Model-Atelier/blob/0a9b72aa75ce2c7bb7ef89f136dbe742a10e506f/%E5%B9%B3%E5%8F%B0%E9%96%8B%E7%99%BC%E6%B8%85%E5%96%AE.md)；檔名 `平台開發清單.md`；Git blob `2cef4a4dd71a32043a31ec92af8f0b2001640251`。

當時核取框：213，已勾選 155、未勾選 58。作者時間 `2026-10-03T01:39:12+08:00`；提交時間 `2026-10-03T01:39:12+08:00`。

<details>
<summary>完整清單差異（含項目、勾選與驗收變動）</summary>

````diff
--- 平台開發清單.md
+++ 平台開發清單.md
@@ -103 +103 @@
-- [ ] 資源預估不足或尚未實測時提供提示，允許使用者嘗試；不因顯卡型號或估算 VRAM 單獨封鎖提交。
+- [x] 資源預估不足或尚未實測時提供提示，允許使用者嘗試；不因顯卡型號或估算 VRAM 單獨封鎖提交。
@@ -390,0 +391,6 @@
+
+## 本輪優先項目 2：創作資源與未驗證條件提示（2026-10-03）
+
+- [x] 提供唯讀資源提示 API 與創作頁入口，保留未知顯存需求，不以歷史取樣當作最低需求。
+- [x] 參數差異、沒有實測紀錄、離線與過期回應均有明確處理；不修改生成參數或增加 GPU／VRAM 提交限制。
+- [x] 199 項後端測試通過（1 項既有權限跳過），含零可用顯存、離線、未知模型、來源變更及無資料寫入；Vue 型別及建置通過。
````

</details>

<a id="commit-2960e561ca5de85487b42c170805472e6c697a1f"></a>

### 01:45:35 · [2960e56](https://github.com/Zimkjdv/Model-Atelier/commit/2960e561ca5de85487b42c170805472e6c697a1f) · feat: report storage capacity by deduplicated local volume

來源：[完整清單原檔](https://github.com/Zimkjdv/Model-Atelier/blob/2960e561ca5de85487b42c170805472e6c697a1f/%E5%B9%B3%E5%8F%B0%E9%96%8B%E7%99%BC%E6%B8%85%E5%96%AE.md)；檔名 `平台開發清單.md`；Git blob `415411553d3602c78461b9df50b8b2657951f4fc`。

當時核取框：216，已勾選 159、未勾選 57。作者時間 `2026-10-03T01:45:35+08:00`；提交時間 `2026-10-03T01:45:35+08:00`。

<details>
<summary>完整清單差異（含項目、勾選與驗收變動）</summary>

````diff
--- 平台開發清單.md
+++ 平台開發清單.md
@@ -150 +150 @@
-- [ ] 顯示模型、素材及輸出目錄所在磁碟的總容量與可用空間；同一磁碟不重複加總。
+- [x] 顯示模型、素材及輸出目錄所在磁碟的總容量與可用空間；同一磁碟不重複加總。
@@ -396,0 +397,6 @@
+
+## 本輪優先項目 3：本機目錄與磁碟容量（2026-10-03）
+
+- [x] 系統頁列出模型、素材、作品及受管理 ComfyUI 輸出目錄，按實際磁碟區去重統計；不存在／不可讀／未知容量保留明確狀態。
+- [x] 額外目錄設定損壞不影響固定目錄查詢，部分總計不假裝完整；遠端引擎不套用本機磁碟資訊。
+- [x] 206 項後端測試通過（1 項既有 Windows 權限跳過），Vue 型別與建置通過；實機五個目錄均落於 C 磁碟區，畫面僅加總一次。完成新提示面板的深色主題一致性調整。
````

</details>

<a id="commit-3318fcdee6ccd233831300d6ec5b11b28d4ff7e8"></a>

### 01:49:55 · [3318fcd](https://github.com/Zimkjdv/Model-Atelier/commit/3318fcdee6ccd233831300d6ec5b11b28d4ff7e8) · fix: harden validation and durable submission boundaries

來源：[完整清單原檔](https://github.com/Zimkjdv/Model-Atelier/blob/3318fcdee6ccd233831300d6ec5b11b28d4ff7e8/%E5%B9%B3%E5%8F%B0%E9%96%8B%E7%99%BC%E6%B8%85%E5%96%AE.md)；檔名 `平台開發清單.md`；Git blob `415411553d3602c78461b9df50b8b2657951f4fc`。

當時核取框：216，已勾選 159、未勾選 57。作者時間 `2026-10-03T01:49:55+08:00`；提交時間 `2026-10-03T01:49:55+08:00`。

本提交未改動開發清單，原檔與前一提交相同；修正內容見上方 commit。

<a id="commit-87647e9f58ebe5b71dabc4f32f1ea2e217b9ecb7"></a>

### 01:52:43 · [87647e9](https://github.com/Zimkjdv/Model-Atelier/commit/87647e9f58ebe5b71dabc4f32f1ea2e217b9ecb7) · feat: validate required ComfyUI nodes before dispatch

來源：[完整清單原檔](https://github.com/Zimkjdv/Model-Atelier/blob/87647e9f58ebe5b71dabc4f32f1ea2e217b9ecb7/%E5%B9%B3%E5%8F%B0%E9%96%8B%E7%99%BC%E6%B8%85%E5%96%AE.md)；檔名 `平台開發清單.md`；Git blob `724ee68b13bcecca4b3c1d4e879bb5d2eb5c3496`。

當時核取框：219，已勾選 161、未勾選 58。作者時間 `2026-10-03T01:52:43+08:00`；提交時間 `2026-10-03T01:52:43+08:00`。

<details>
<summary>完整清單差異（含項目、勾選與驗收變動）</summary>

````diff
--- 平台開發清單.md
+++ 平台開發清單.md
@@ -7 +7 @@
-更新日期：2026-10-02
+更新日期：2026-10-03
@@ -10 +10 @@
-### 開發進度（更新至 2026-10-02）
+### 開發進度（更新至 2026-10-03）
@@ -402,0 +403,6 @@
+
+## 檢查修正後優先項目 1：必要節點提交前檢查（2026-10-03）
+
+- [x] 針對本次流程的標準節點查詢即時定義；缺少／格式無效／服務失敗均不送出 GPU 任務，保留明確錯誤及失敗紀錄。
+- [x] 節點去重並行查詢，舊請求恢復不重送；209 項後端測試通過（1 項既有權限跳過）。
+- [ ] 無可用裝置需引擎提供可靠證據，不能只憑空裝置清單推定；P0 此部分保持待驗證。
````

</details>

<a id="commit-1247600aaeae5fd208509a669f2a705b48551702"></a>

### 01:55:05 · [1247600](https://github.com/Zimkjdv/Model-Atelier/commit/1247600aaeae5fd208509a669f2a705b48551702) · feat: persist studio disclosure preferences and expose common controls

來源：[完整清單原檔](https://github.com/Zimkjdv/Model-Atelier/blob/1247600aaeae5fd208509a669f2a705b48551702/%E5%B9%B3%E5%8F%B0%E9%96%8B%E7%99%BC%E6%B8%85%E5%96%AE.md)；檔名 `平台開發清單.md`；Git blob `70df1199a8c7b8cbbdfb681303032c57da3ebfff`。

當時核取框：221，已勾選 164、未勾選 57。作者時間 `2026-10-03T01:55:05+08:00`；提交時間 `2026-10-03T01:55:05+08:00`。

<details>
<summary>完整清單差異（含項目、勾選與驗收變動）</summary>

````diff
--- 平台開發清單.md
+++ 平台開發清單.md
@@ -133 +133 @@
-- [ ] 將常用參數直接呈現，進階參數收合，保留使用者設定狀態。
+- [x] 將常用參數直接呈現，進階參數收合，保留使用者設定狀態。
@@ -408,0 +409,5 @@
+
+## 檢查修正後優先項目 2：常用參數與介面偏好（2026-10-03）
+
+- [x] Steps／CFG 與尺寸直接顯示，其餘進階參數收合；保存進階區與素材區展開偏好，與草稿參數分離。
+- [x] Vue 型別／正式建置通過，瀏覽器驗證展開進階區後重新載入仍保留，Seed 等原參數不變；未新增草稿或生成。
````

</details>

<a id="commit-0c1f60bd98765289d02e66b8e9f15193d45772f2"></a>

### 01:57:55 · [0c1f60b](https://github.com/Zimkjdv/Model-Atelier/commit/0c1f60bd98765289d02e66b8e9f15193d45772f2) · feat: add collapsible studio layout and keyboard navigation

來源：[完整清單原檔](https://github.com/Zimkjdv/Model-Atelier/blob/0c1f60bd98765289d02e66b8e9f15193d45772f2/%E5%B9%B3%E5%8F%B0%E9%96%8B%E7%99%BC%E6%B8%85%E5%96%AE.md)；檔名 `平台開發清單.md`；Git blob `d25e687b6971cdd7ccec1bf8b5a2f9d42eb56e6e`。

當時核取框：224，已勾選 168、未勾選 56。作者時間 `2026-10-03T01:57:55+08:00`；提交時間 `2026-10-03T01:57:55+08:00`。

<details>
<summary>完整清單差異（含項目、勾選與驗收變動）</summary>

````diff
--- 平台開發清單.md
+++ 平台開發清單.md
@@ -139 +139 @@
-- [ ] 建立適合桌面操作的工作台布局，較窄視窗可收合設定區，避免主要操作被擠出畫面。
+- [x] 建立適合桌面操作的工作台布局，較窄視窗可收合設定區，避免主要操作被擠出畫面。
@@ -413,0 +414,7 @@
+
+## 檢查修正後優先項目 3：窄視窗工作台與鍵盤操作（2026-10-03）
+
+- [x] 創作設定可收合，任務區擴展；保留原表單與未保存變更，窄視窗顯示當前參數摘要。
+- [x] 導覽補上文字名稱／提示／目前頁面語意、主內容跳轉及一致 focus-visible 樣式。
+- [x] 前端型別與正式建置通過；680px／390px 無橫向溢出，鍵盤 Enter 收合與再展開保留內容，跳轉主內容後焦點正確。未建立測試草稿或生成任務。
+- 全站視覺規範及所有頁面的無障礙驗收仍可繼續完善，本項驗證以創作工作台與主要導覽為範圍。
````

</details>

<a id="commit-63794decb1ad9ed49c430d81730d67fb23dfb618"></a>

### 02:04:08 · [63794de](https://github.com/Zimkjdv/Model-Atelier/commit/63794decb1ad9ed49c430d81730d67fb23dfb618) · feat: centralize studio visual tokens and control states

來源：[完整清單原檔](https://github.com/Zimkjdv/Model-Atelier/blob/63794decb1ad9ed49c430d81730d67fb23dfb618/%E5%B9%B3%E5%8F%B0%E9%96%8B%E7%99%BC%E6%B8%85%E5%96%AE.md)；檔名 `平台開發清單.md`；Git blob `11140ff44535a77c6e4a0f098f098d62031fd63a`。

當時核取框：226，已勾選 171、未勾選 55。作者時間 `2026-10-03T02:04:08+08:00`；提交時間 `2026-10-03T02:04:08+08:00`。

<details>
<summary>完整清單差異（含項目、勾選與驗收變動）</summary>

````diff
--- 平台開發清單.md
+++ 平台開發清單.md
@@ -138 +138 @@
-- [ ] 統一字體、間距、配色、按鈕、表單及載入、空白、錯誤狀態的視覺規範。
+- [x] 統一字體、間距、配色、按鈕、表單及載入、空白、錯誤狀態的視覺規範；見 docs/ui-guidelines.md。
@@ -420,0 +421,5 @@
+
+## 本輪優先項目 1：共用視覺規範（2026-10-03）
+
+- [x] 建立 theme.css 共用色彩／表單／焦點／提示狀態，主要資料頁引用相同輸入色彩，區分一般通知與警告。
+- [x] 記錄 docs/ui-guidelines.md；Vue 型別與建置、設定頁畫面檢查通過。
````

</details>

<a id="commit-6cbb4a904602daa27ac172b766512ac66d480930"></a>

### 02:06:44 · [6cbb4a9](https://github.com/Zimkjdv/Model-Atelier/commit/6cbb4a904602daa27ac172b766512ac66d480930) · feat: improve form descriptions and library operation announcements

來源：[完整清單原檔](https://github.com/Zimkjdv/Model-Atelier/blob/6cbb4a904602daa27ac172b766512ac66d480930/%E5%B9%B3%E5%8F%B0%E9%96%8B%E7%99%BC%E6%B8%85%E5%96%AE.md)；檔名 `平台開發清單.md`；Git blob `2af41b60b78b98329b7dabc095c7d59673dff965`。

當時核取框：229，已勾選 175、未勾選 54。作者時間 `2026-10-03T02:06:44+08:00`；提交時間 `2026-10-03T02:06:44+08:00`。

<details>
<summary>完整清單差異（含項目、勾選與驗收變動）</summary>

````diff
--- 平台開發清單.md
+++ 平台開發清單.md
@@ -140 +140 @@
-- [ ] 表單提供清楚標籤、鍵盤焦點及可讀對比；狀態不只用顏色區分。
+- [x] 表單提供清楚標籤、鍵盤焦點及可讀對比；狀態不只用顏色區分。
@@ -425,0 +426,6 @@
+
+## 本輪優先項目 2：表單可讀性與操作回饋（2026-10-03）
+
+- [x] 素材、作品讀取狀態及模型／作品／素材搜尋結果以 status 呈現；重複卡片操作包含對應名稱。
+- [x] 素材上傳限制、模型 SHA256 格式及目錄限制與輸入欄位建立 describedby 關聯；沿用原生 label 與共用焦點／對比樣式。
+- [x] 型別與建置通過，實際鍵盤 Enter 開啟作品、Escape 關閉並返回原按鈕通過；不改寫作品或模型資料。
````

</details>

<a id="commit-88fb32faba6a2542347aa4d90c502e7f3cdddbd9"></a>

### 02:11:20 · [88fb32f](https://github.com/Zimkjdv/Model-Atelier/commit/88fb32faba6a2542347aa4d90c502e7f3cdddbd9) · feat: describe supported workflow fields and retain unsupported settings

來源：[完整清單原檔](https://github.com/Zimkjdv/Model-Atelier/blob/88fb32faba6a2542347aa4d90c502e7f3cdddbd9/%E5%B9%B3%E5%8F%B0%E9%96%8B%E7%99%BC%E6%B8%85%E5%96%AE.md)；檔名 `平台開發清單.md`；Git blob `c476e4b2751f4ed8bc5d9f72738e89641c41d4ff`。

當時核取框：232，已勾選 180、未勾選 52。作者時間 `2026-10-03T02:11:20+08:00`；提交時間 `2026-10-03T02:11:20+08:00`。

<details>
<summary>完整清單差異（含項目、勾選與驗收變動）</summary>

````diff
--- 平台開發清單.md
+++ 平台開發清單.md
@@ -166,2 +166,2 @@
-- [ ] 依流程能力顯示提示詞、seed、尺寸、步數等設定。
-- [ ] 只顯示流程實際支援的進階欄位，保存原始參數。
+- [x] 依流程能力顯示提示詞、seed、尺寸、步數等設定（目前標準 checkpoint 流程）。
+- [x] 只顯示流程實際支援的進階欄位，保存原始參數；未接入架構保留唯讀原值。
@@ -431,0 +432,6 @@
+
+## 本輪優先項目 3：依流程能力呈現欄位（2026-10-03）
+
+- [x] 模型 profile 提供版本化 workflow 描述與明確欄位；前端驗證描述，僅啟用已接入的標準流程表單。
+- [x] 不支援架構保留可查看／保存的原參數，切回 SDXL 恢復原值，不自動套用預設。
+- [x] 212 項後端測試（211 通過、1 項既有權限跳過）、前端型別及建置通過。8001 隔離資料實際驗證 FLUX 保留 31 steps、保存草稿及切回 SDXL 恢復欄位；正式資料未修改。
````

</details>

## 2026-10-04

<a id="commit-2602811267f7be836aa1f0e4410bfa6bd25e5804"></a>

### 19:09:00 · [2602811](https://github.com/Zimkjdv/Model-Atelier/commit/2602811267f7be836aa1f0e4410bfa6bd25e5804) · feat: pin Animagine XL 4.0 Opt provenance and author preset

來源：[完整清單原檔](https://github.com/Zimkjdv/Model-Atelier/blob/2602811267f7be836aa1f0e4410bfa6bd25e5804/%E5%B9%B3%E5%8F%B0%E9%96%8B%E7%99%BC%E6%B8%85%E5%96%AE.md)；檔名 `平台開發清單.md`；Git blob `719360ce0c997f0ad1f2f1a5b6927c0b04bfe0cc`。

當時核取框：232，已勾選 181、未勾選 51。作者時間 `2026-10-04T19:09:00+08:00`；提交時間 `2026-10-04T19:09:00+08:00`。

<details>
<summary>完整清單差異（含項目、勾選與驗收變動）</summary>

````diff
--- 平台開發清單.md
+++ 平台開發清單.md
@@ -162 +162 @@
-- [ ] 核對並選定 Animagine XL 版本、來源、授權及依賴。
+- [x] 選定 Animagine XL 4.0 Opt，固定作者修訂、大小及 SHA256，核對授權及標準流程依賴；權重安裝與 GPU 驗收尚未完成，詳見 `docs/models/animagine-xl-4.0-opt.md`。
````

</details>

<a id="commit-ddb871f47ead3448c5df91e4f7df7167db2f8fb7"></a>

### 19:19:48 · [ddb871f](https://github.com/Zimkjdv/Model-Atelier/commit/ddb871f47ead3448c5df91e4f7df7167db2f8fb7) · feat: add engine-scoped LoRA catalog and metadata editor

來源：[完整清單原檔](https://github.com/Zimkjdv/Model-Atelier/blob/ddb871f47ead3448c5df91e4f7df7167db2f8fb7/%E5%B9%B3%E5%8F%B0%E9%96%8B%E7%99%BC%E6%B8%85%E5%96%AE.md)；檔名 `平台開發清單.md`；Git blob `b60d23312c7e73091688e6cdd64d8cad6370abe4`。

當時核取框：232，已勾選 182、未勾選 50。作者時間 `2026-10-04T19:19:48+08:00`；提交時間 `2026-10-04T19:19:48+08:00`。

<details>
<summary>完整清單差異（含項目、勾選與驗收變動）</summary>

````diff
--- 平台開發清單.md
+++ 平台開發清單.md
@@ -176 +176 @@
-- [ ] 建立 LoRA 登記、來源、版本與基礎架構欄位。
+- [x] 建立依引擎隔離的 LoRA 清單同步、搜尋與登記，包含來源、版本、基礎架構、大小、SHA256、授權及備註；離線保留成功快照，尚未載入生成流程。
````

</details>

<a id="commit-d73c6da540c03929a6324581ba238a2b0ff9bc0d"></a>

### 19:33:34 · [d73c6da](https://github.com/Zimkjdv/Model-Atelier/commit/d73c6da540c03929a6324581ba238a2b0ff9bc0d) · feat: assess registered LoRA and checkpoint architecture compatibility

來源：[完整清單原檔](https://github.com/Zimkjdv/Model-Atelier/blob/d73c6da540c03929a6324581ba238a2b0ff9bc0d/%E5%B9%B3%E5%8F%B0%E9%96%8B%E7%99%BC%E6%B8%85%E5%96%AE.md)；檔名 `平台開發清單.md`；Git blob `e1f47188a9976ddd7489d365dbcd51666cfcb24e`。

當時核取框：232，已勾選 183、未勾選 49。作者時間 `2026-10-04T19:33:34+08:00`；提交時間 `2026-10-04T19:33:34+08:00`。

<details>
<summary>完整清單差異（含項目、勾選與驗收變動）</summary>

````diff
--- 平台開發清單.md
+++ 平台開發清單.md
@@ -7 +7 @@
-更新日期：2026-10-03
+更新日期：2026-10-04
@@ -10 +10 @@
-### 開發進度（更新至 2026-10-03）
+### 開發進度（更新至 2026-10-04）
@@ -178 +178 @@
-- [ ] 顯示相容、未驗證或不相容狀態；不以檔名推斷相容性。
+- [x] 比較 checkpoint／LoRA 登記架構，顯示架構相容（未實測）、未驗證或已知不相容；不以檔名、版本推斷，清單失效時保守顯示，尚未載入生成流程。
````

</details>

<a id="commit-ca019b3019063146a7058c8ff718d1816aeb81b6"></a>

### 19:47:27 · [ca019b3](https://github.com/Zimkjdv/Model-Atelier/commit/ca019b3019063146a7058c8ff718d1816aeb81b6) · feat: save single LoRA controls in creation drafts

來源：[完整清單原檔](https://github.com/Zimkjdv/Model-Atelier/blob/ca019b3019063146a7058c8ff718d1816aeb81b6/%E5%B9%B3%E5%8F%B0%E9%96%8B%E7%99%BC%E6%B8%85%E5%96%AE.md)；檔名 `平台開發清單.md`；Git blob `ef0a20173317ab5d9d1d62536559d468bf1a7afc`。

當時核取框：232，已勾選 184、未勾選 48。作者時間 `2026-10-04T19:47:27+08:00`；提交時間 `2026-10-04T19:47:27+08:00`。

<details>
<summary>完整清單差異（含項目、勾選與驗收變動）</summary>

````diff
--- 平台開發清單.md
+++ 平台開發清單.md
@@ -177 +177 @@
-- [ ] 支援選擇、啟用及移除 LoRA，保存工作流程支援的設定。
+- [x] 支援選擇、啟用及移除單一 LoRA，保存模型／CLIP 強度與啟用狀態至草稿；目前啟用時明確阻止生成，待下一階段接入工作流程。
````

</details>

<a id="commit-34145fe915312ae42d0a580b97fc813eb2cdb263"></a>

### 19:57:13 · [34145fe](https://github.com/Zimkjdv/Model-Atelier/commit/34145fe915312ae42d0a580b97fc813eb2cdb263) · feat: submit single LoRA workflows with live preflight checks

來源：[完整清單原檔](https://github.com/Zimkjdv/Model-Atelier/blob/34145fe915312ae42d0a580b97fc813eb2cdb263/%E5%B9%B3%E5%8F%B0%E9%96%8B%E7%99%BC%E6%B8%85%E5%96%AE.md)；檔名 `平台開發清單.md`；Git blob `29d24c25eb63056d9e0f47986320bbf33cef724f`。

當時核取框：232，已勾選 185、未勾選 47。作者時間 `2026-10-04T19:57:13+08:00`；提交時間 `2026-10-04T19:57:13+08:00`。

<details>
<summary>完整清單差異（含項目、勾選與驗收變動）</summary>

````diff
--- 平台開發清單.md
+++ 平台開發清單.md
@@ -176,4 +176,4 @@
-- [x] 建立依引擎隔離的 LoRA 清單同步、搜尋與登記，包含來源、版本、基礎架構、大小、SHA256、授權及備註；離線保留成功快照，尚未載入生成流程。
-- [x] 支援選擇、啟用及移除單一 LoRA，保存模型／CLIP 強度與啟用狀態至草稿；目前啟用時明確阻止生成，待下一階段接入工作流程。
-- [x] 比較 checkpoint／LoRA 登記架構，顯示架構相容（未實測）、未驗證或已知不相容；不以檔名、版本推斷，清單失效時保守顯示，尚未載入生成流程。
-- [ ] 提交前阻擋已知不相容組合。
+- [x] 建立依引擎隔離的 LoRA 清單同步、搜尋與登記，包含來源、版本、基礎架構、大小、SHA256、授權及備註；離線保留成功快照。
+- [x] 支援選擇、啟用及移除單一 LoRA，保存模型／CLIP 強度與啟用狀態至草稿。
+- [x] 比較 checkpoint／LoRA 登記架構，顯示架構相容（未實測）、未驗證或已知不相容；不以檔名、版本推斷，清單失效時保守顯示。
+- [x] 提交前阻擋已知不相容組合；單一 LoRA 八節點模板接入即時名稱、介面及強度交集檢查，提交前再次確認引擎與架構登記。
````

</details>

<a id="commit-c80068e8c109b73632e4f86aed60787b4d11f6c7"></a>

### 20:11:36 · [c80068e](https://github.com/Zimkjdv/Model-Atelier/commit/c80068e8c109b73632e4f86aed60787b4d11f6c7) · feat: preserve LoRA provenance and restore creation settings

來源：[完整清單原檔](https://github.com/Zimkjdv/Model-Atelier/blob/c80068e8c109b73632e4f86aed60787b4d11f6c7/%E5%B9%B3%E5%8F%B0%E9%96%8B%E7%99%BC%E6%B8%85%E5%96%AE.md)；檔名 `平台開發清單.md`；Git blob `55120a957a5204ca8bafdc57f834198765cf510c`。

當時核取框：232，已勾選 186、未勾選 46。作者時間 `2026-10-04T20:11:36+08:00`；提交時間 `2026-10-04T20:11:36+08:00`。

<details>
<summary>完整清單差異（含項目、勾選與驗收變動）</summary>

````diff
--- 平台開發清單.md
+++ 平台開發清單.md
@@ -181 +181 @@
-- [ ] 將 LoRA 版本及設定保存至生成紀錄。
+- [x] 將 LoRA 版本及設定保存至生成紀錄：提交時凍結登記來源、版本、架構、SHA256、授權與兩種強度，作品沿用原快照；支援完整單一 LoRA 流程還原及版本差異提示，舊紀錄不回填。
````

</details>

<a id="commit-cbc0ee10748e9c763477b87f451e32587a752efc"></a>

### 21:48:04 · [cbc0ee1](https://github.com/Zimkjdv/Model-Atelier/commit/cbc0ee10748e9c763477b87f451e32587a752efc) · feat: add pinned Animagine installer and read-only disk preflight

來源：[完整清單原檔](https://github.com/Zimkjdv/Model-Atelier/blob/cbc0ee10748e9c763477b87f451e32587a752efc/%E5%B9%B3%E5%8F%B0%E9%96%8B%E7%99%BC%E6%B8%85%E5%96%AE.md)；檔名 `平台開發清單.md`；Git blob `296116b797e3e955910b4e5af5498cb82220f1fe`。

當時核取框：234，已勾選 188、未勾選 46。作者時間 `2026-10-04T21:48:04+08:00`；提交時間 `2026-10-04T21:48:04+08:00`。

<details>
<summary>完整清單差異（含項目、勾選與驗收變動）</summary>

````diff
--- 平台開發清單.md
+++ 平台開發清單.md
@@ -58 +58 @@
-| P3 | Animagine XL | 驗證同架構多模型切換，確切版本待選 |
+| P3 | Animagine XL 4.0 Opt | 固定來源與安裝器已完成；同架構多模型 GPU 切換待驗證 |
@@ -162,0 +163 @@
+- [x] 提供 Animagine 固定來源安裝器與唯讀磁碟預檢；沿用安全續傳、完整雜湊、安裝鎖與原子發布。本機空間不足，完整權重下載仍待執行。
@@ -259 +260,2 @@
-- [ ] Animagine XL 與 FLUX.1 的確切版本。
+- [x] Animagine XL 選定 4.0 Opt，固定來源見選型紀錄。
+- [ ] FLUX.1 的確切公開權重變體。
````

</details>

<a id="commit-7595335697dc15cef43617b2ef82414f914dc2a6"></a>

### 21:56:47 · [7595335](https://github.com/Zimkjdv/Model-Atelier/commit/7595335697dc15cef43617b2ef82414f914dc2a6) · feat: verify pinned single LoRA generation on RTX 3060

來源：[完整清單原檔](https://github.com/Zimkjdv/Model-Atelier/blob/7595335697dc15cef43617b2ef82414f914dc2a6/%E5%B9%B3%E5%8F%B0%E9%96%8B%E7%99%BC%E6%B8%85%E5%96%AE.md)；檔名 `平台開發清單.md`；Git blob `c3169ce1b051278eb4c49787a24e2c5658480a9f`。

當時核取框：235，已勾選 189、未勾選 46。作者時間 `2026-10-04T21:56:47+08:00`；提交時間 `2026-10-04T21:56:47+08:00`。

<details>
<summary>完整清單差異（含項目、勾選與驗收變動）</summary>

````diff
--- 平台開發清單.md
+++ 平台開發清單.md
@@ -181 +181,2 @@
-- [ ] 先驗證單一 LoRA，再評估多個 LoRA 的組合支援。
+- [x] 單一 LoRA 實機驗證：Pony＋作者公開 LCM SDXL 在 RTX 3060 通過八節點生成、快照與重啟後離線保存；驗收工具及條件見 `docs/validation/pony-lcm-rtx3060.md`，不代表畫師效果或全部 LoRA 已驗證。
+- [ ] 評估多個 LoRA 的組合支援及其他畫風 LoRA 的品質。
````

</details>

<a id="commit-0c84e4118525185e451799eeb734125b215025bf"></a>

### 22:13:45 · [0c84e41](https://github.com/Zimkjdv/Model-Atelier/commit/0c84e4118525185e451799eeb734125b215025bf) · feat: surface condition-scoped single LoRA validation evidence

來源：[完整清單原檔](https://github.com/Zimkjdv/Model-Atelier/blob/0c84e4118525185e451799eeb734125b215025bf/%E5%B9%B3%E5%8F%B0%E9%96%8B%E7%99%BC%E6%B8%85%E5%96%AE.md)；檔名 `平台開發清單.md`；Git blob `afda6000875f3dd6fa57a756facec298ed5570b3`。

當時核取框：236，已勾選 190、未勾選 46。作者時間 `2026-10-04T22:13:45+08:00`；提交時間 `2026-10-04T22:13:45+08:00`。

<details>
<summary>完整清單差異（含項目、勾選與驗收變動）</summary>

````diff
--- 平台開發清單.md
+++ 平台開發清單.md
@@ -181,0 +182 @@
+- [x] 將 LoRA 實測條件接到模型庫、創作頁及資源提示；依兩份登記 hash／架構比對組合，強度與取樣參數另外比對，清單失效及未知條件保持未驗證，不限制 GPU 型號或改設定。
````

</details>

<a id="commit-2d64ec13836c3ecf5b830d74865357056271fbb0"></a>

### 23:34:19 · [2d64ec1](https://github.com/Zimkjdv/Model-Atelier/commit/2d64ec13836c3ecf5b830d74865357056271fbb0) · feat: safely stop an owned running ComfyUI job

來源：[完整清單原檔](https://github.com/Zimkjdv/Model-Atelier/blob/2d64ec13836c3ecf5b830d74865357056271fbb0/%E5%B9%B3%E5%8F%B0%E9%96%8B%E7%99%BC%E6%B8%85%E5%96%AE.md)；檔名 `平台開發清單.md`；Git blob `65c1cf917e6b151918d5a41aaaf1da1445671d4f`。

當時核取框：236，已勾選 191、未勾選 45。作者時間 `2026-10-04T23:34:19+08:00`；提交時間 `2026-10-04T23:34:19+08:00`。

<details>
<summary>完整清單差異（含項目、勾選與驗收變動）</summary>

````diff
--- 平台開發清單.md
+++ 平台開發清單.md
@@ -126 +126 @@
-- [ ] 執行中停止仍需另行驗證引擎語意，避免中斷其他任務。
+- [x] 執行中指定停止：受管理 ComfyUI 來源核對、原子取消能力與完整身分驗證，歷史確認中斷；RTX 3060 已驗證後續任務正常完成，其他版本及硬體另測。
````

</details>

<a id="commit-367ae73d8dcfd2926900818410b1bdeba26d6e5a"></a>

### 23:45:13 · [367ae73](https://github.com/Zimkjdv/Model-Atelier/commit/367ae73d8dcfd2926900818410b1bdeba26d6e5a) · feat: support ordered multi-LoRA checkpoint workflows

來源：[完整清單原檔](https://github.com/Zimkjdv/Model-Atelier/blob/367ae73d8dcfd2926900818410b1bdeba26d6e5a/%E5%B9%B3%E5%8F%B0%E9%96%8B%E7%99%BC%E6%B8%85%E5%96%AE.md)；檔名 `平台開發清單.md`；Git blob `9aec63e21a86209d46b2227e9346ce41e2311da1`。

當時核取框：237，已勾選 192、未勾選 45。作者時間 `2026-10-04T23:45:13+08:00`；提交時間 `2026-10-04T23:45:13+08:00`。

<details>
<summary>完整清單差異（含項目、勾選與驗收變動）</summary>

````diff
--- 平台開發清單.md
+++ 平台開發清單.md
@@ -183,0 +184 @@
+- [x] 最多四個不同 LoRA 有序串接、各別啟用／強度／排序、即時名稱與架構檢查、快照與完整還原；多 LoRA 不沿用單一實測證據，實際 GPU 與畫風品質仍待驗收。
````

</details>

## 2026-10-05

<a id="commit-5bf331f543250fd5a0f88a71424f8eda7368eb96"></a>

### 00:02:37 · [5bf331f](https://github.com/Zimkjdv/Model-Atelier/commit/5bf331f543250fd5a0f88a71424f8eda7368eb96) · feat: add pinned FLUX schnell dependency and disk preflight

來源：[完整清單原檔](https://github.com/Zimkjdv/Model-Atelier/blob/5bf331f543250fd5a0f88a71424f8eda7368eb96/%E5%B9%B3%E5%8F%B0%E9%96%8B%E7%99%BC%E6%B8%85%E5%96%AE.md)；檔名 `平台開發清單.md`；Git blob `72e854092a165ee0448f95083fa1c3800a9ff6ff`。

當時核取框：238，已勾選 195、未勾選 43。作者時間 `2026-10-05T00:02:37+08:00`；提交時間 `2026-10-05T00:02:37+08:00`。

<details>
<summary>完整清單差異（含項目、勾選與驗收變動）</summary>

````diff
--- 平台開發清單.md
+++ 平台開發清單.md
@@ -7 +7 @@
-更新日期：2026-10-04
+更新日期：2026-10-05
@@ -8,0 +9,2 @@
+
+本輪新增：執行中指定停止（RTX 3060 驗收）、最多四個 LoRA 有序流程，以及 FLUX.1 [schnell] 固定元件／版本／磁碟預檢。300 項後端測試（299 通過、1 項既有權限跳過）、Vue build 與瀏覽器驗收通過；多 LoRA 的 GPU／畫風品質、FLUX 安裝與專用生成、Animagine 完整下載及 RTX 4080 仍待實測。
@@ -60 +62 @@
-| P5 | FLUX.1 公開權重變體 | 跨架構整合；確切變體待確認，LoRA 支援另行驗證 |
+| P5 | FLUX.1 [schnell] 公開權重 | 固定原始 BF16 主模型及分離元件；預檢已完成，專用生成與 LoRA 待驗證 |
@@ -191,2 +193,3 @@
-- [ ] 選定可本地執行的公開權重變體，記錄授權及使用條件。
-- [ ] 確認所需編碼器、解碼器、推論精度及硬體需求。
+- [x] 選定 FLUX.1 [schnell] 原始 BF16 公開權重，固定作者修訂、大小、SHA256 與模型卡授權；來源有 Hugging Face 帳號／條件確認，平台不代為接受。
+- [x] 記錄分離 VAE、CLIP-L、T5 FP8 scaled 的固定來源與版本，模型庫及 CLI 提供唯讀本機磁碟預檢；已有檔案仍需驗檔，不使用 SDXL 表單。
+- [ ] 驗證實際推論精度、卸載、GPU／RAM 需求與各元件上游授權；來源選型不代表權重已安裝或可生成。
@@ -264 +267 @@
-- [ ] FLUX.1 的確切公開權重變體。
+- [x] FLUX.1 首輪選定 [schnell] 原始 BF16 主模型，分離 VAE／CLIP-L／T5 FP8 scaled；安裝與專用 GPU 流程仍待執行。
````

</details>

<a id="commit-c7008c6a4c503bca40658b99780ccf756f533513"></a>

### 01:33:14 · [c7008c6](https://github.com/Zimkjdv/Model-Atelier/commit/c7008c6a4c503bca40658b99780ccf756f533513) · feat: add engine-scoped FLUX component inventories

來源：[完整清單原檔](https://github.com/Zimkjdv/Model-Atelier/blob/c7008c6a4c503bca40658b99780ccf756f533513/%E5%B9%B3%E5%8F%B0%E9%96%8B%E7%99%BC%E6%B8%85%E5%96%AE.md)；檔名 `平台開發清單.md`；Git blob `d57d6140d64bb68541711a46ef4a052380def4ef`。

當時核取框：239，已勾選 196、未勾選 43。作者時間 `2026-10-05T01:33:14+08:00`；提交時間 `2026-10-05T01:33:14+08:00`。

<details>
<summary>完整清單差異（含項目、勾選與驗收變動）</summary>

````diff
--- 平台開發清單.md
+++ 平台開發清單.md
@@ -192,0 +193,2 @@
+- [x] 分離元件庫：依引擎原子同步主模型／兩個文字編碼器／VAE，保留未知版本及來源登記，離線不清除上次完整快照（2026-10-05）。
+
````

</details>

<a id="commit-2f8f23e28d092ecdda05bd6c78b2381c14a8fe1e"></a>

### 01:44:31 · [2f8f23e](https://github.com/Zimkjdv/Model-Atelier/commit/2f8f23e28d092ecdda05bd6c78b2381c14a8fe1e) · feat: add safe dedicated FLUX schnell workflow submission

來源：[完整清單原檔](https://github.com/Zimkjdv/Model-Atelier/blob/2f8f23e28d092ecdda05bd6c78b2381c14a8fe1e/%E5%B9%B3%E5%8F%B0%E9%96%8B%E7%99%BC%E6%B8%85%E5%96%AE.md)；檔名 `平台開發清單.md`；Git blob `045c67be6fbcfce222d951b2ec7ff12134aeeba9`。

當時核取框：239，已勾選 197、未勾選 42。作者時間 `2026-10-05T01:44:31+08:00`；提交時間 `2026-10-05T01:44:31+08:00`。

<details>
<summary>完整清單差異（含項目、勾選與驗收變動）</summary>

````diff
--- 平台開發清單.md
+++ 平台開發清單.md
@@ -198 +198 @@
-- [ ] 建立獨立工作流程與參數描述，不直接套用 SDXL 表單。
+- [x] 建立 FLUX.1 [schnell] 獨立 9 節點流程、參數描述及安全提交 API；四元件不可變快照、獨立草稿及終止任務完整還原（2026-10-05）。專用創作介面接續實作；GPU 未驗證。
````

</details>

<a id="commit-3aaf6ed4665c79385ad2387cbd37a6d2834e2c9b"></a>

### 02:07:38 · [3aaf6ed](https://github.com/Zimkjdv/Model-Atelier/commit/3aaf6ed4665c79385ad2387cbd37a6d2834e2c9b) · feat: add dedicated FLUX studio and lossless workflow export

來源：[完整清單原檔](https://github.com/Zimkjdv/Model-Atelier/blob/3aaf6ed4665c79385ad2387cbd37a6d2834e2c9b/%E5%B9%B3%E5%8F%B0%E9%96%8B%E7%99%BC%E6%B8%85%E5%96%AE.md)；檔名 `平台開發清單.md`；Git blob `b2958c2840813f031ab6e72e1a41b54ed55f987f`。

當時核取框：240，已勾選 198、未勾選 42。作者時間 `2026-10-05T02:07:38+08:00`；提交時間 `2026-10-05T02:07:38+08:00`。

<details>
<summary>完整清單差異（含項目、勾選與驗收變動）</summary>

````diff
--- 平台開發清單.md
+++ 平台開發清單.md
@@ -10,3 +10,3 @@
-本輪新增：執行中指定停止（RTX 3060 驗收）、最多四個 LoRA 有序流程，以及 FLUX.1 [schnell] 固定元件／版本／磁碟預檢。300 項後端測試（299 通過、1 項既有權限跳過）、Vue build 與瀏覽器驗收通過；多 LoRA 的 GPU／畫風品質、FLUX 安裝與專用生成、Animagine 完整下載及 RTX 4080 仍待實測。
-
-### 開發進度（更新至 2026-10-04）
+本輪新增：FLUX 分離元件庫、獨立 9 節點安全提交與專用創作頁，包含版本來源快照、獨立草稿、完整 JSON 匯出及作品設定還原。319 項後端測試（318 通過、1 項既有權限跳過）、Vue build 與隔離瀏覽器驗收通過；真實 ComfyUI 節點／缺模型拒絕已驗證。磁碟不足，FLUX 權重安裝與 GPU 出圖、多 LoRA 品質、Animagine 完整下載及 RTX 4080 仍待實測。
+
+### 開發進度（更新至 2026-10-05）
@@ -62 +62 @@
-| P5 | FLUX.1 [schnell] 公開權重 | 固定原始 BF16 主模型及分離元件；預檢已完成，專用生成與 LoRA 待驗證 |
+| P5 | FLUX.1 [schnell] 公開權重 | 預檢、分離元件庫、安全提交與專用表單已完成；權重安裝、GPU 生成與 LoRA 待驗證 |
@@ -198 +198,2 @@
-- [x] 建立 FLUX.1 [schnell] 獨立 9 節點流程、參數描述及安全提交 API；四元件不可變快照、獨立草稿及終止任務完整還原（2026-10-05）。專用創作介面接續實作；GPU 未驗證。
+- [x] 建立 FLUX.1 [schnell] 獨立 9 節點流程、參數描述及安全提交 API；四元件不可變快照、獨立草稿及終止任務完整還原（2026-10-05）。
+- [x] 接入專用創作頁、跨流程表單保留、元件版本與來源介面、精確 JSON 匯出及作品還原；GPU 未驗證（2026-10-05）。
````

</details>

<a id="commit-5dfa86a0f16f941de793069cdf34ef39b691cf57"></a>

### 02:20:23 · [5dfa86a](https://github.com/Zimkjdv/Model-Atelier/commit/5dfa86a0f16f941de793069cdf34ef39b691cf57) · feat: add reference purposes provenance and asset usage protection

來源：[完整清單原檔](https://github.com/Zimkjdv/Model-Atelier/blob/5dfa86a0f16f941de793069cdf34ef39b691cf57/%E5%B9%B3%E5%8F%B0%E9%96%8B%E7%99%BC%E6%B8%85%E5%96%AE.md)；檔名 `平台開發清單.md`；Git blob `df2fa79847aaa6c07c3d10c8b59fec747a3d69b3`。

當時核取框：240，已勾選 202、未勾選 38。作者時間 `2026-10-05T02:20:23+08:00`；提交時間 `2026-10-05T02:20:23+08:00`。

<details>
<summary>完整清單差異（含項目、勾選與驗收變動）</summary>

````diff
--- 平台開發清單.md
+++ 平台開發清單.md
@@ -209,3 +209,3 @@
-- [ ] 上傳、預覽及管理參考圖片，檢查格式和尺寸。
-- [ ] 標示參考用途：視覺風格、角色外觀、構圖等。
-- [ ] 建立每套工作流程的輸入需求與支援能力說明。
+- [x] 上傳、預覽及管理參考圖片，檢查格式和尺寸。
+- [x] 標示參考用途：視覺風格、角色外觀、構圖等；用途僅為整理標籤，不自動產生影像條件。
+- [x] 建立每套工作流程的輸入需求與支援能力說明，未整合的參考能力明確停用。
@@ -214 +214 @@
-- [ ] 檢查素材是否被任務引用，避免刪除後無法重建流程。
+- [x] 檢查素材是否被草稿、任務或作品引用；封存於同一資料交易檢查，平台不提供永久刪除 API。
@@ -448,0 +449,7 @@
+
+## 本輪優先項目 1：參考素材用途與引用保護（2026-10-05）
+
+- 用途保存／篩選、修訂衝突、正規化來源與版本紀錄；舊素材未知值不回填。
+- 參考流程能力 API 區分圖生圖、局部編輯、結構及風格參考；任務與作品引用素材禁止封存。
+- 324 項後端測試（323 通過、1 項既有跳過）、Vue 建置與隔離瀏覽器用途保存／篩選驗收通過。
+
````

</details>

<a id="commit-7302384d92bd38d9de3dd43a350b20398cdbad15"></a>

### 02:36:28 · [7302384](https://github.com/Zimkjdv/Model-Atelier/commit/7302384d92bd38d9de3dd43a350b20398cdbad15) · feat: add safe reference-guided checkpoint image-to-image jobs

來源：[完整清單原檔](https://github.com/Zimkjdv/Model-Atelier/blob/7302384d92bd38d9de3dd43a350b20398cdbad15/%E5%B9%B3%E5%8F%B0%E9%96%8B%E7%99%BC%E6%B8%85%E5%96%AE.md)；檔名 `平台開發清單.md`；Git blob `fe629817cf7e0caada6210fc924fe1fbeda354ad`。

當時核取框：240，已勾選 204、未勾選 36。作者時間 `2026-10-05T02:36:28+08:00`；提交時間 `2026-10-05T02:36:28+08:00`。

<details>
<summary>完整清單差異（含項目、勾選與驗收變動）</summary>

````diff
--- 平台開發清單.md
+++ 平台開發清單.md
@@ -36 +36 @@
-- [ ] 參考素材目前僅管理與記錄，尚未串接 ComfyUI 圖片輸入、用途或參考權重。
+- [x] 參考素材用途與單張 checkpoint 圖生圖後端：來源／前處理快照、原生 LoadImage 與 VAEEncode、獨立任務上傳及 Pony／RTX 3060 實機驗證。創作介面待接入；adapter 畫風與角色、ControlNet 結構、局部編輯仍待整合。
@@ -212,2 +212,2 @@
-- [ ] 逐項評估圖片生成圖片、局部編輯及結構參考流程。
-- [ ] 保存參考圖與輸出的關聯；保存前處理設定及版本。
+- [ ] 逐項評估圖片生成圖片、局部編輯及結構參考流程；單張 checkpoint 圖生圖後端與 Pony／RTX 3060 已驗證，其他流程仍待整合。
+- [x] 圖生圖保存參考圖、任務與作品的關聯，凍結前處理設定及版本；未支援流程不套用素材。
@@ -455,0 +456,8 @@
+
+## 本輪優先項目 2：安全的 checkpoint 圖生圖後端（2026-10-05）
+
+- 一張平台素材、等比補白／拉伸、LoadImage → VAEEncode、精確 seed、有序 LoRA 路徑；完整 JSON 與不可回填的来源快照。
+- 驗證後才上傳原引擎獨立目錄；UUID 恢復不重新上傳／提交，未知生成結果只查詢。
+- 339 項後端測試（338 通過、1 項既有跳過）；真實 Pony／RTX 3060 成功生成 512×512、輸入 SHA256、作品匯入、離線設定還原與引用保護通過。
+- UI 下一項接入；其他模型、參考圖加 LoRA 及品質仍待實機測試。
+
````

</details>

<a id="commit-b699024f6885fa0635cc5724be5f5e6259216bdb"></a>

### 02:59:54 · [b699024](https://github.com/Zimkjdv/Model-Atelier/commit/b699024f6885fa0635cc5724be5f5e6259216bdb) · feat: add image-to-image studio controls and reference tracing

來源：[完整清單原檔](https://github.com/Zimkjdv/Model-Atelier/blob/b699024f6885fa0635cc5724be5f5e6259216bdb/%E5%B9%B3%E5%8F%B0%E9%96%8B%E7%99%BC%E6%B8%85%E5%96%AE.md)；檔名 `平台開發清單.md`；Git blob `6d6af3479a7afc1aa802746b0bd847593a26d063`。

當時核取框：240，已勾選 204、未勾選 36。作者時間 `2026-10-05T02:59:54+08:00`；提交時間 `2026-10-05T02:59:54+08:00`。

<details>
<summary>完整清單差異（含項目、勾選與驗收變動）</summary>

````diff
--- 平台開發清單.md
+++ 平台開發清單.md
@@ -10 +10 @@
-本輪新增：FLUX 分離元件庫、獨立 9 節點安全提交與專用創作頁，包含版本來源快照、獨立草稿、完整 JSON 匯出及作品設定還原。319 項後端測試（318 通過、1 項既有權限跳過）、Vue build 與隔離瀏覽器驗收通過；真實 ComfyUI 節點／缺模型拒絕已驗證。磁碟不足，FLUX 權重安裝與 GPU 出圖、多 LoRA 品質、Animagine 完整下載及 RTX 4080 仍待實測。
+本輪新增：參考素材用途與引用保護、Checkpoint 圖生圖後端及創作介面，包含素材／前處理版本快照、完整 JSON、單張圖片縮放與改動幅度、任務／作品設定還原。339 項後端測試（338 通過、1 項既有權限跳過）、Vue build、瀏覽器與 Pony／RTX 3060 兩個真實圖生圖任務通過。FLUX 權重、多 LoRA 畫風品質、Animagine 完整下載與 RTX 4080 仍待後續實測；安裝前需重新查詢動態磁碟容量。
@@ -36 +36 @@
-- [x] 參考素材用途與單張 checkpoint 圖生圖後端：來源／前處理快照、原生 LoadImage 與 VAEEncode、獨立任務上傳及 Pony／RTX 3060 實機驗證。創作介面待接入；adapter 畫風與角色、ControlNet 結構、局部編輯仍待整合。
+- [x] 參考素材用途與單張 checkpoint 圖生圖後端／介面：來源／前處理快照、原生 LoadImage 與 VAEEncode、獨立任務上傳、草稿及作品設定還原，以及 Pony／RTX 3060 實機驗證。adapter 畫風與角色、ControlNet 結構、局部編輯仍待整合。
@@ -212 +212 @@
-- [ ] 逐項評估圖片生成圖片、局部編輯及結構參考流程；單張 checkpoint 圖生圖後端與 Pony／RTX 3060 已驗證，其他流程仍待整合。
+- [ ] 逐項評估圖片生成圖片、局部編輯及結構參考流程；單張 checkpoint 圖生圖後端／介面與 Pony／RTX 3060 已驗證，其他流程仍待整合。
@@ -459 +459 @@
-- 一張平台素材、等比補白／拉伸、LoadImage → VAEEncode、精確 seed、有序 LoRA 路徑；完整 JSON 與不可回填的来源快照。
+- 一張平台素材、等比補白／拉伸、LoadImage → VAEEncode、精確 seed、有序 LoRA 路徑；完整 JSON 與不可回填的來源快照。
@@ -463,0 +464,8 @@
+
+## 本輪優先項目 3：圖生圖創作介面與來源追溯（2026-10-05）
+
+- Checkpoint 文生圖／圖生圖切換、單張來源選擇、等比補白／拉伸預覽、改動幅度及精確 seed；草稿重載、未保存保護、任務／作品還原不自動生成。
+- 任務及作品顯示素材與前處理快照；圖生圖不沿用文生圖預設與品質驗證結論。
+- Vue 型別／正式建置通過；瀏覽器驗證 0.123 denoise 保存、390px 無溢出、真實 GPU 生成與匯入；關閉引擎後離線警示正確且原參數保留。
+- 每項測試後分別 commit、push；本輪正式資料維持原 5 個任務與 3 件作品，隔離驗收資料保留。
+
````

</details>

<a id="commit-16020048e31c7c1b0dda189dec80ed38d4a906c0"></a>

### 03:17:34 · [1602004](https://github.com/Zimkjdv/Model-Atelier/commit/16020048e31c7c1b0dda189dec80ed38d4a906c0) · feat: validate pinned Animagine on local RTX 3060

來源：[完整清單原檔](https://github.com/Zimkjdv/Model-Atelier/blob/16020048e31c7c1b0dda189dec80ed38d4a906c0/%E5%B9%B3%E5%8F%B0%E9%96%8B%E7%99%BC%E6%B8%85%E5%96%AE.md)；檔名 `平台開發清單.md`；Git blob `cc629072d91452509124db9bc66351d7478913d2`。

當時核取框：243，已勾選 207、未勾選 36。作者時間 `2026-10-05T03:17:34+08:00`；提交時間 `2026-10-05T03:17:34+08:00`。

<details>
<summary>完整清單差異（含項目、勾選與驗收變動）</summary>

````diff
--- 平台開發清單.md
+++ 平台開發清單.md
@@ -10 +10 @@
-本輪新增：參考素材用途與引用保護、Checkpoint 圖生圖後端及創作介面，包含素材／前處理版本快照、完整 JSON、單張圖片縮放與改動幅度、任務／作品設定還原。339 項後端測試（338 通過、1 項既有權限跳過）、Vue build、瀏覽器與 Pony／RTX 3060 兩個真實圖生圖任務通過。FLUX 權重、多 LoRA 畫風品質、Animagine 完整下載與 RTX 4080 仍待後續實測；安裝前需重新查詢動態磁碟容量。
+本輪進行：Animagine 安裝與 RTX 3060 驗收、Animagine／LCM LoRA 組合、作品庫管理。第一項已完成固定權重驗證、兩次 1024×1024 生成、切回 Pony 及平台重啟後離線讀取。FLUX 權重、多 LoRA 畫風品質與 RTX 4080 仍待後續實測；安裝前需重新查詢動態磁碟容量。
@@ -60 +60 @@
-| P3 | Animagine XL 4.0 Opt | 固定來源與安裝器已完成；同架構多模型 GPU 切換待驗證 |
+| P3 | Animagine XL 4.0 Opt | 固定來源安裝、RTX 3060 文生圖及切回 Pony 已驗證；其他硬體／負載另測 |
@@ -164,2 +164,2 @@
-- [x] 選定 Animagine XL 4.0 Opt，固定作者修訂、大小及 SHA256，核對授權及標準流程依賴；權重安裝與 GPU 驗收尚未完成，詳見 `docs/models/animagine-xl-4.0-opt.md`。
-- [x] 提供 Animagine 固定來源安裝器與唯讀磁碟預檢；沿用安全續傳、完整雜湊、安裝鎖與原子發布。本機空間不足，完整權重下載仍待執行。
+- [x] Animagine XL 4.0 Opt 固定作者修訂、大小及 SHA256，核對授權及標準流程依賴；完整安裝、RTX 3060 1024×1024 文生圖與離線作品驗收完成，詳見 `docs/validation/animagine-xl-4-0-opt-rtx3060.md`。
+- [x] Animagine 固定來源安裝器與唯讀磁碟預檢，安全續傳、完整雜湊、安裝鎖與原子發布；2026-10-05 預檢磁碟已足夠，完成下載，沒有刪除其他模型。
@@ -318 +318 @@
-- [x] 已完成 Pony V6 XL GPU 出圖與重啟後作品／設定保存驗收；Animagine、FLUX 與其他硬體未驗證。
+- [x] 已完成 Pony V6 XL 與 Animagine XL 4.0 Opt 的 RTX 3060 GPU 出圖與離線作品／設定保存驗收；FLUX 與其他硬體未驗證。
@@ -471,0 +472,6 @@
+## 本輪優先項目 1：Animagine 固定權重與真實 GPU 整合（2026-10-05）
+
+- [x] 6.46 GiB checkpoint 完整大小／SHA256 核對、版本 `4.0 Opt` 登記，不改偏好 Pony；專用驗收 CLI 使用原 UUID 與精確 seed，無重送。
+- [x] RTX 3060 兩次 1024×1024 風景、同引擎切回 Pony、作品快照與重啟平台後離線 GET 驗證通過；條件登記接入模型庫／資源提示，其他環境保持未驗證。
+- [x] 344 項後端測試（343 通過、1 項既有權限跳過）、Vue 型別／正式建置通過。一次既有跨程序報告鎖測試偶發失敗後，單項及完整重跑通過。
+
````

</details>

<a id="commit-babb5205889e9a0381ede347edafc8598758ac89"></a>

### 03:24:00 · [babb520](https://github.com/Zimkjdv/Model-Atelier/commit/babb5205889e9a0381ede347edafc8598758ac89) · feat: verify Animagine with LCM LoRA and scoped evidence

來源：[完整清單原檔](https://github.com/Zimkjdv/Model-Atelier/blob/babb5205889e9a0381ede347edafc8598758ac89/%E5%B9%B3%E5%8F%B0%E9%96%8B%E7%99%BC%E6%B8%85%E5%96%AE.md)；檔名 `平台開發清單.md`；Git blob `973e34c20efd4cafd6020255f28bc8c399b6d3fd`。

當時核取框：248，已勾選 212、未勾選 36。作者時間 `2026-10-05T03:24:00+08:00`；提交時間 `2026-10-05T03:24:00+08:00`。

<details>
<summary>完整清單差異（含項目、勾選與驗收變動）</summary>

````diff
--- 平台開發清單.md
+++ 平台開發清單.md
@@ -183,0 +184 @@
+- [x] 第二個已接入模型組合：Animagine XL 4.0 Opt＋既有 LCM SDXL 在 RTX 3060 完成 1024×1024 八節點生成、完整快照與離線讀取，見 `docs/validation/animagine-lcm-rtx3060.md`；依兩份 hash 與設定匹配，沒有借用 Pony 實測。
@@ -477,0 +479,7 @@
+## 本輪優先項目 2：Animagine／LCM LoRA 組合（2026-10-05）
+
+- [x] 專用固定參數驗收 CLI，共用一次提交與離線完整快照檢查；Pony CLI 維持原設定。
+- [x] RTX 3060 成功生成 1024×1024 一般風景，model strength 1、CLIP strength 0、4 steps、CFG 1、lcm／sgm_uniform；八節點、精確 seed、原圖 hash、模型／LoRA 快照與重啟後離線還原通過。
+- [x] 組合證據接入既有模型庫、創作頁與資源提示；解析度／強度／取樣設定改變時不匹配，未推定多 LoRA 或畫風品質。
+- [x] 347 項後端測試（346 通過、1 項既有權限跳過），Vue 型別／正式建置通過。
+
````

</details>

<a id="commit-9ca7c221012f33c0dc96ba604816b77b0393c860"></a>

### 03:43:24 · [9ca7c22](https://github.com/Zimkjdv/Model-Atelier/commit/9ca7c221012f33c0dc96ba604816b77b0393c860) · feat: organize artwork favorites notes and archives safely

來源：[完整清單原檔](https://github.com/Zimkjdv/Model-Atelier/blob/9ca7c221012f33c0dc96ba604816b77b0393c860/%E5%B9%B3%E5%8F%B0%E9%96%8B%E7%99%BC%E6%B8%85%E5%96%AE.md)；檔名 `平台開發清單.md`；Git blob `11429d834c7026688f856ef05d3e65c20ccf085c`。

當時核取框：252，已勾選 218、未勾選 34。作者時間 `2026-10-05T03:43:24+08:00`；提交時間 `2026-10-05T03:43:24+08:00`。

<details>
<summary>完整清單差異（含項目、勾選與驗收變動）</summary>

````diff
--- 平台開發清單.md
+++ 平台開發清單.md
@@ -10 +10 @@
-本輪進行：Animagine 安裝與 RTX 3060 驗收、Animagine／LCM LoRA 組合、作品庫管理。第一項已完成固定權重驗證、兩次 1024×1024 生成、切回 Pony 及平台重啟後離線讀取。FLUX 權重、多 LoRA 畫風品質與 RTX 4080 仍待後續實測；安裝前需重新查詢動態磁碟容量。
+本輪完成：Animagine 固定權重安裝與 RTX 3060 驗收、Animagine／LCM LoRA 組合、作品庫收藏／筆記／封存與還原。四個隔離 GPU 任務、作品及原設定驗證通過；354 項後端測試（353 通過、1 項既有權限跳過）、Vue build 與桌面瀏覽器驗收通過。FLUX 權重、多 LoRA 畫風品質與 RTX 4080 仍待後續實測；安裝前需重新查詢動態磁碟容量。
@@ -219 +219 @@
-- [ ] 支援作品篩選、收藏、備註與下載。
+- [x] 作品模型／收藏／狀態組合篩選、筆記搜尋、收藏、最多 10,000 字筆記及原圖／完整流程下載；修訂衝突保留未保存內容，見 `docs/artwork-library.md`。
@@ -307 +307 @@
-- [ ] 作品收藏、備註與封存。
+- [x] 作品收藏、筆記與封存／還原，保留原圖、參數及版本快照；沒有永久刪除。
@@ -475 +475 @@
-- [x] 6.46 GiB checkpoint 完整大小／SHA256 核對、版本 `4.0 Opt` 登記，不改偏好 Pony；專用驗收 CLI 使用原 UUID 與精確 seed，無重送。
+- [x] 6.46 GiB checkpoint 完整大小／SHA256 核對、版本 `4.0 Opt` 登記，不改正式偏好（仍未選定）；隔離測試資料選用 Animagine，專用驗收 CLI 使用原 UUID 與精確 seed，無重送。
@@ -485,0 +486,7 @@
+## 本輪優先項目 3：作品庫管理（2026-10-05）
+
+- [x] 收藏、筆記、封存／還原、模型／狀態／收藏組合篩選及筆記搜尋；交易修訂檢查，409 保留表單，不自動覆蓋或重送。
+- [x] 舊作品唯讀預設、原圖／workflow／模型快照不變、封存作品仍保護素材引用，重複匯入不重設管理資料。
+- [x] 354 項後端測試（353 通過、1 項既有 Windows 權限跳過）、Vue 型別／建置、兩個視窗衝突及桌面瀏覽器驗收通過；viewport override 實際未生效，390px 本轮保持未驗收。
+- [x] 正式 5 任務／3 作品／0 草稿不變，隔離四件作品及管理資料保留；服務停止後分項 commit、push。
+
````

</details>

<a id="commit-428763421fe3a2d3b3b5de269a9e7e02a3adfe5f"></a>

### 03:59:23 · [4287634](https://github.com/Zimkjdv/Model-Atelier/commit/428763421fe3a2d3b3b5de269a9e7e02a3adfe5f) · feat: validate pinned style and ordered multi LoRA workflows

來源：[完整清單原檔](https://github.com/Zimkjdv/Model-Atelier/blob/428763421fe3a2d3b3b5de269a9e7e02a3adfe5f/%E5%B9%B3%E5%8F%B0%E9%96%8B%E7%99%BC%E6%B8%85%E5%96%AE.md)；檔名 `平台開發清單.md`；Git blob `59b17bf41fbe162d0e637a5c20c60181d461e539`。

當時核取框：256，已勾選 222、未勾選 34。作者時間 `2026-10-05T03:59:23+08:00`；提交時間 `2026-10-05T03:59:23+08:00`。

<details>
<summary>完整清單差異（含項目、勾選與驗收變動）</summary>

````diff
--- 平台開發清單.md
+++ 平台開發清單.md
@@ -10 +10 @@
-本輪完成：Animagine 固定權重安裝與 RTX 3060 驗收、Animagine／LCM LoRA 組合、作品庫收藏／筆記／封存與還原。四個隔離 GPU 任務、作品及原設定驗證通過；354 項後端測試（353 通過、1 項既有權限跳過）、Vue build 與桌面瀏覽器驗收通過。FLUX 權重、多 LoRA 畫風品質與 RTX 4080 仍待後續實測；安裝前需重新查詢動態磁碟容量。
+本輪進行：公開畫風 LoRA／有序多 LoRA RTX 3060 驗證、引擎及依賴版本快照、設定匯出／匯入。第一項三組生成與離線核對通過，357 項後端測試（356 通過、1 項既有權限跳過）及 Vue build 通過；4 步多 LoRA 對比不足，品質仍待調整。FLUX 約需 29.5 GiB，當前約 14.9 GiB，先處理 P6 的追溯與設定重用；RTX 4080 未實測。
@@ -186,0 +187 @@
+- [x] Animagine＋公開黑白畫風與 LCM→畫風有序九節點，RTX 3060 一次提交、出圖、完整快照及離線還原；固定來源／未知授權如實保存，4 步品質偏淡，不能視為所有畫風驗收。
@@ -492,0 +494,6 @@
+## 本輪優先項目 1：公開畫風與多 LoRA GPU 驗證（2026-10-05）
+
+- [x] 固定作者 revision、185,697,368 bytes 與完整 SHA256，通用安裝器明確分流 LoRA 目錄；版本以 revision 表示，授權 `other` 保留未知。
+- [x] 三組相同 prompt／seed：無 LoRA、單一畫風、LCM→畫風；7／8／9 節點全部 GPU 生成、作品保存及引擎停止後 GET 核對通過，正式生成資料不變。
+- [x] 人工檢查如實記錄 4 步組合偏淡，不推薦為品質預設；357 項後端測試及 Vue 型別／建置通過，詳見 docs/validation/animagine-multi-lora-rtx3060.md。
+
````

</details>

<a id="commit-7f32d47b0f21e6e97de1f0d6a4502ed39c7ab72e"></a>

### 04:14:15 · [7f32d47](https://github.com/Zimkjdv/Model-Atelier/commit/7f32d47b0f21e6e97de1f0d6a4502ed39c7ab72e) · feat: freeze engine and dependency versions for generated artworks

來源：[完整清單原檔](https://github.com/Zimkjdv/Model-Atelier/blob/7f32d47b0f21e6e97de1f0d6a4502ed39c7ab72e/%E5%B9%B3%E5%8F%B0%E9%96%8B%E7%99%BC%E6%B8%85%E5%96%AE.md)；檔名 `平台開發清單.md`；Git blob `acc9cfe299381e70e3c77c959593baa1ebc22001`。

當時核取框：260，已勾選 227、未勾選 33。作者時間 `2026-10-05T04:14:15+08:00`；提交時間 `2026-10-05T04:14:15+08:00`。

<details>
<summary>完整清單差異（含項目、勾選與驗收變動）</summary>

````diff
--- 平台開發清單.md
+++ 平台開發清單.md
@@ -222 +222 @@
-- [ ] 保存模型、LoRA、工作流程、引擎及依賴版本。
+- [x] 保存模型、LoRA、流程規格／完整 JSON hash、提交前引擎及平台依賴版本；未提供 CUDA／驅動／Git revision／節點版本保持未知，舊紀錄不回填。
@@ -499,0 +500,7 @@
+## 本輪優先項目 2：提交時引擎與依賴版本（2026-10-05）
+
+- [x] Checkpoint／圖生圖／FLUX 提交前最多兩秒觀察，原引擎與平台來源分開；交易凍結、修訂衝突、未知值、UUID 不重查及舊紀錄不回填。
+- [x] 作品复制原任務版本，預覽與歷史設定還原顯示快照；RTX 3060 真實 Animagine／LCM 任務、作品及平台重啟後離線核對通過。
+- [x] 修正 Windows 並行目錄建立造成 `Path.resolve` 等價前綴誤拒絕，保留目錄限制及一次提交；新增決定性回歸測試並回收測試子程序。
+- [x] 365 項後端測試（364 通過、1 項既有權限跳過）、Vue 型別／建置與桌面瀏覽器版本顯示通過。
+
````

</details>

<a id="commit-5c4438218ee3338aede710e5c3f597a8e79a936b"></a>

### 04:36:17 · [5c44382](https://github.com/Zimkjdv/Model-Atelier/commit/5c4438218ee3338aede710e5c3f597a8e79a936b) · feat: export and import versioned creation settings

來源：[完整清單原檔](https://github.com/Zimkjdv/Model-Atelier/blob/5c4438218ee3338aede710e5c3f597a8e79a936b/%E5%B9%B3%E5%8F%B0%E9%96%8B%E7%99%BC%E6%B8%85%E5%96%AE.md)；檔名 `平台開發清單.md`；Git blob `3287af7f8939993e5e76b3d80fb6a26f144b0690`。

當時核取框：264，已勾選 232、未勾選 32。作者時間 `2026-10-05T04:36:17+08:00`；提交時間 `2026-10-05T04:36:17+08:00`。

<details>
<summary>完整清單差異（含項目、勾選與驗收變動）</summary>

````diff
--- 平台開發清單.md
+++ 平台開發清單.md
@@ -10 +10 @@
-本輪進行：公開畫風 LoRA／有序多 LoRA RTX 3060 驗證、引擎及依賴版本快照、設定匯出／匯入。第一項三組生成與離線核對通過，357 項後端測試（356 通過、1 項既有權限跳過）及 Vue build 通過；4 步多 LoRA 對比不足，品質仍待調整。FLUX 約需 29.5 GiB，當前約 14.9 GiB，先處理 P6 的追溯與設定重用；RTX 4080 未實測。
+本輪完成：公開畫風 LoRA／有序多 LoRA RTX 3060 驗證、任務與作品引擎及依賴版本快照、創作設定匯出／匯入。四個隔離 GPU 任務與離線核對通過，370 項後端測試（369 通過、1 項既有權限跳過）、Vue build 與桌面瀏覽器驗收通過；4 步多 LoRA 對比不足，品質仍待調整。FLUX 約需 29.5 GiB，本機當前不足，RTX 4080 未實測。
@@ -221 +221 @@
-- [ ] 支援設定匯出、匯入及從歷史紀錄重新執行。
+- [x] 創作設定 JSON 匯出／匯入、來源快照、完整差異預覽與手動套用新草稿；歷史設定載入後，由使用者明確生成建立新任務，不重送原 ID。
@@ -506,0 +507,7 @@
+## 本輪優先項目 3：創作設定匯出與匯入（2026-10-05）
+
+- [x] 三種流程版本化 JSON、字串 seed、有序 LoRA／圖生圖／FLUX 參數；作品與終止任務可匯出原來源快照及精確 workflow 字串。
+- [x] 256 KiB、完整欄位與參數、來源未核實、跨架構拒絕、重複欄位／非有限數字／注入拒絕；匯入 API 只讀，不保存、不連線、不生成。
+- [x] 選檔／貼上、差異預覽、未保存提示、取消與預覽失效、明確套用新草稿；Vue 代理物件複製錯誤修正後，兩份 checkpoint 草稿與一份 FLUX 草稿的隔離保存通過，正式資料不變。
+- [x] 370 項後端測試（369 通過、1 項既有權限跳過）、Vue 型別／建置及桌面 UI 驗收通過；IAB Blob 下載事件未回報，僅確認 API bytes、下載連結及完整 JSON，其他瀏覽器下載與 390px 待驗收。
+
````

</details>

<a id="commit-8a76fe855fbe457203cf8c354f0c128c36da5610"></a>

### 04:45:36 · [8a76fe8](https://github.com/Zimkjdv/Model-Atelier/commit/8a76fe855fbe457203cf8c354f0c128c36da5610) · feat: match ordered LoRA evidence and retain quality observations

來源：[完整清單原檔](https://github.com/Zimkjdv/Model-Atelier/blob/8a76fe855fbe457203cf8c354f0c128c36da5610/%E5%B9%B3%E5%8F%B0%E9%96%8B%E7%99%BC%E6%B8%85%E5%96%AE.md)；檔名 `平台開發清單.md`；Git blob `6feb7bb0ba690318ad999f3232e5a542f22723fe`。

當時核取框：265，已勾選 233、未勾選 32。作者時間 `2026-10-05T04:45:36+08:00`；提交時間 `2026-10-05T04:45:36+08:00`。

<details>
<summary>完整清單差異（含項目、勾選與驗收變動）</summary>

````diff
--- 平台開發清單.md
+++ 平台開發清單.md
@@ -186,0 +187 @@
+- [x] 有序多 LoRA 條件化紀錄接到創作頁及資源提示：比對原雜湊／架構／順序、強度及取樣設定，保留品質不足的觀察；不借用單一組合或反向順序。其他畫風與廣泛品質評估仍待進行。
@@ -188 +189 @@
-- [x] 最多四個不同 LoRA 有序串接、各別啟用／強度／排序、即時名稱與架構檢查、快照與完整還原；多 LoRA 不沿用單一實測證據，實際 GPU 與畫風品質仍待驗收。
+- [x] 最多四個不同 LoRA 有序串接、各別啟用／強度／排序、即時名稱與架構檢查、快照與完整還原；固定九節點 GPU 載入已驗證，更多組合及畫風品質仍待驗收。
````

</details>

<a id="commit-a21b41e578a235a2876b36787315a8615a94b9f6"></a>

### 04:55:46 · [a21b41e](https://github.com/Zimkjdv/Model-Atelier/commit/a21b41e578a235a2876b36787315a8615a94b9f6) · feat: compare artworks and save revision-safe manual ratings

來源：[完整清單原檔](https://github.com/Zimkjdv/Model-Atelier/blob/a21b41e578a235a2876b36787315a8615a94b9f6/%E5%B9%B3%E5%8F%B0%E9%96%8B%E7%99%BC%E6%B8%85%E5%96%AE.md)；檔名 `平台開發清單.md`；Git blob `b7e7aa8813c3718d71c15480af1d54f9102627d3`。

當時核取框：265，已勾選 234、未勾選 31。作者時間 `2026-10-05T04:55:46+08:00`；提交時間 `2026-10-05T04:55:46+08:00`。

<details>
<summary>完整清單差異（含項目、勾選與驗收變動）</summary>

````diff
--- 平台開發清單.md
+++ 平台開發清單.md
@@ -224 +224 @@
-- [ ] 提供圖片並排比較與人工評分。
+- [x] 最多四張作品原圖並排、生成參數差異及四項人工評分；共用修訂檢查及未保存保護，舊紀錄只讀預設，不改原圖片／快照。
````

</details>

<a id="commit-0ed66ce82acafbc0e8337663b2a0bae17a927043"></a>

### 05:15:06 · [0ed66ce](https://github.com/Zimkjdv/Model-Atelier/commit/0ed66ce82acafbc0e8337663b2a0bae17a927043) · feat: preview bounded illustration comparison plans

來源：[完整清單原檔](https://github.com/Zimkjdv/Model-Atelier/blob/0ed66ce82acafbc0e8337663b2a0bae17a927043/%E5%B9%B3%E5%8F%B0%E9%96%8B%E7%99%BC%E6%B8%85%E5%96%AE.md)；檔名 `平台開發清單.md`；Git blob `f1e258f38d8f0fae82dc08a80ce4427c6b93ad55`。

當時核取框：277，已勾選 247、未勾選 30。作者時間 `2026-10-05T05:15:06+08:00`；提交時間 `2026-10-05T05:15:06+08:00`。

<details>
<summary>完整清單差異（含項目、勾選與驗收變動）</summary>

````diff
--- 平台開發清單.md
+++ 平台開發清單.md
@@ -10 +10 @@
-本輪完成：公開畫風 LoRA／有序多 LoRA RTX 3060 驗證、任務與作品引擎及依賴版本快照、創作設定匯出／匯入。四個隔離 GPU 任務與離線核對通過，370 項後端測試（369 通過、1 項既有權限跳過）、Vue build 與桌面瀏覽器驗收通過；4 步多 LoRA 對比不足，品質仍待調整。FLUX 約需 29.5 GiB，本機當前不足，RTX 4080 未實測。
+本輪完成：有序多 LoRA 歷史條件與品質觀察、作品原圖並排與人工評分、固定一般插畫測試集及有限參數比較方案。382 項後端測試（381 通過、1 項既有 Windows 權限跳過）、Vue build 與桌面瀏覽器驗收通過；沒有新增 GPU 任務或正式資料，使用既有隔離圖片。4 步多 LoRA 對比不足，品質仍待調整；固定測試集跨模型 GPU 品質評測尚未完成。FLUX 約需 29.5 GiB，本機約 13.3 GiB 可用，RTX 4080 未實測。
@@ -139 +139 @@
-- 圖片並排比較仍於 P6 實作。
+- [x] 圖片並排比較與人工評分已於 P6 實作；窄視窗實際操作仍待驗收。
@@ -226 +226,2 @@
-- [ ] 支援有限範圍的參數比較，提交前顯示預計任務數。
+- [x] 固定一般插畫測試集 v1：四個案例、成年旅人雙場景、明確評估要點、版本／檔案 hash；可用於方案預覽，尚未完成跨模型 GPU 品質評測。
+- [x] 有限範圍參數比較：checkpoint 文生圖 Steps／CFG／字串 Seed 單一軸，最多八次單張預覽、完整快照與 JSON 匯出；逐組載入後手動生成，不自動批次或重試。
@@ -514,0 +516,19 @@
+## 本輪優先項目 1：有序 LoRA 歷史條件與品質觀察（2026-10-05）
+
+- [x] 唯讀組合 API 與創作頁：hash／架構／順序匹配歷史載入紀錄，強度與完整取樣條件另外比對；資料異動 409，未知或失效不借用其他組合。
+- [x] 資源提示共用有序比對，保留 4 步結果偏淡的觀察；沒有品質通過旗標、顯卡限制或 VRAM 推估。
+- [x] 374 項後端測試（373 通過、1 項既有權限跳過）、Vue 型別／建置及桌面順序變更驗收通過。完成後 commit `8a76fe8` 並 push，再進行下一項。
+
+## 本輪優先項目 2：作品並排與人工評分（2026-10-05）
+
+- [x] 最多四張完整原圖、差異表、精確 seed 與有序 LoRA；篩選不清除比較選擇，完整其他快照仍由作品預覽查看。
+- [x] 四項 1–5／null 人工分數共用修訂檢查；無效輸入與衝突拒絕，未保存內容保留，原圖／workflow／模型及環境快照不變。
+- [x] 377 項後端測試（376 通過、1 項既有權限跳過）、Vue 型別／建置及桌面 UI 通過；隔離圖的視覺風格觀察為 1/5。完成後 commit `a21b41e` 並 push，再進行下一項。
+
+## 本輪優先項目 3：固定測試集與有限參數比較（2026-10-05）
+
+- [x] 自行編寫四個一般插畫案例，版本與 bytes hash；單一參數軸、完整設定、最多八份單張方案，超界／重複／注入拒絕，不寫草稿或提交 GPU。
+- [x] 完整 JSON 匯出與預覽 hash 核對；逐組明確載入未保存新草稿，保留其餘比較快照，64 位 seed 與 LoRA 順序精確還原。原生成按鈕獨立提交。
+- [x] 382 項後端測試（381 通過、1 項既有 Windows 權限跳過）、Vue 型別／建置及桌面案例／seed／JSON／載入驗收通過。說明見 `docs/experiment-plans.md`；原生下載落盤、窄視窗、自動批次及跨模型 GPU 品質評測仍待後續。
+- [x] 正式 5 任務／3 作品／0 草稿不變，隔離 4 任務／4 作品／2 checkpoint 草稿／1 FLUX 草稿保留；8000／8001／8188／5173 全部停止，分項 commit、push。
+
````

</details>

## 2026-10-08

<a id="commit-7ac19689adea9072ba5e9b10b1f9d58074d4565a"></a>

### 21:16:47 · [7ac1968](https://github.com/Zimkjdv/Model-Atelier/commit/7ac19689adea9072ba5e9b10b1f9d58074d4565a) · feat: validate eight-step and reversed LoRA quality profiles

來源：[完整清單原檔](https://github.com/Zimkjdv/Model-Atelier/blob/7ac19689adea9072ba5e9b10b1f9d58074d4565a/%E5%B9%B3%E5%8F%B0%E9%96%8B%E7%99%BC%E6%B8%85%E5%96%AE.md)；檔名 `平台開發清單.md`；Git blob `6df643e4b2b779e6fbc7e065e69dc542339875c8`。

當時核取框：280，已勾選 250、未勾選 30。作者時間 `2026-10-08T21:16:47+08:00`；提交時間 `2026-10-08T21:16:47+08:00`。

<details>
<summary>完整清單差異（含項目、勾選與驗收變動）</summary>

````diff
--- 平台開發清單.md
+++ 平台開發清單.md
@@ -7 +7 @@
-更新日期：2026-10-05
+更新日期：2026-10-08
@@ -534,0 +535,6 @@
+
+## 優先項目 1：多 LoRA 步數與順序品質驗證（2026-10-08）
+
+- [x] 新增固定 `multi-8` 與 `style-lcm-8` CLI profiles；完整驗檔、有序快照、一次提交、原圖及離線還原，正反順序各自匹配歷史条件。
+- [x] RTX 3060 兩個真實九節點任務成功；8 步及反向順序仍偏淡，不改模型預設或宣稱品質通過，廣泛畫風／多 seed 評估保留待辦。
+- [x] 384 項後端測試（383 通過、1 項既有 Windows 權限跳過）、Vue 型別／建置、API 及原圖觀察；瀏覽器工具無法啟動，UI 實機驗收未完成。見 `docs/validation/animagine-multi-lora-quality-rtx3060.md`。
````

</details>

<a id="commit-df8b14155b8e03fa42889d84ce6e8b28e7595b40"></a>

### 21:26:40 · [df8b141](https://github.com/Zimkjdv/Model-Atelier/commit/df8b14155b8e03fa42889d84ce6e8b28e7595b40) · feat: retain source-scoped job timings and resource snapshots

來源：[完整清單原檔](https://github.com/Zimkjdv/Model-Atelier/blob/df8b14155b8e03fa42889d84ce6e8b28e7595b40/%E5%B9%B3%E5%8F%B0%E9%96%8B%E7%99%BC%E6%B8%85%E5%96%AE.md)；檔名 `平台開發清單.md`；Git blob `68c01900e1bd01085c7a28ec6c4be4135663e451`。

當時核取框：283，已勾選 254、未勾選 29。作者時間 `2026-10-08T21:26:40+08:00`；提交時間 `2026-10-08T21:26:40+08:00`。

<details>
<summary>完整清單差異（含項目、勾選與驗收變動）</summary>

````diff
--- 平台開發清單.md
+++ 平台開發清單.md
@@ -228 +228 @@
-- [ ] 記錄耗時及可取得的資源用量，無法測得的數值不推估填入。
+- [x] 新任務保存平台觀察耗時、原引擎歷史起訖及提交前資源快照；作品沿用，未知值不推估或回填。連續／任務專用峰值仍待實作。
@@ -540,0 +541,6 @@
+
+## 優先項目 2：來源分離的任務量測（2026-10-08）
+
+- [x] 交易內保存提交起始與首次確認終態，原歷史身分／時間／結果完整驗證；CAS 及原 UUID 不覆寫或重新提交，舊紀錄保持未知。
+- [x] 原引擎單次 RAM／装置快照，與版本查詢共用，不新增負載；任務、SSE、作品來源沿用，無峰值推估。
+- [x] 390 項後端測試（389 通過、1 項既有 Windows 權限跳過）、Vue 型別／建置與 RTX 3060 真實量測、作品及離線核對；瀏覽器 UI 實機驗收未完成。見 `docs/job-measurements.md`。
````

</details>

<a id="commit-e3ef1d2261e0c47947b39930cea61312d7d2890b"></a>

### 21:46:41 · [e3ef1d2](https://github.com/Zimkjdv/Model-Atelier/commit/e3ef1d2261e0c47947b39930cea61312d7d2890b) · feat: verify fixed illustration cases across Pony and Animagine

來源：[完整清單原檔](https://github.com/Zimkjdv/Model-Atelier/blob/e3ef1d2261e0c47947b39930cea61312d7d2890b/%E5%B9%B3%E5%8F%B0%E9%96%8B%E7%99%BC%E6%B8%85%E5%96%AE.md)；檔名 `平台開發清單.md`；Git blob `6e85f5ad18c3f94b2c6dec56ea4b68e19755c903`。

當時核取框：289，已勾選 260、未勾選 29。作者時間 `2026-10-08T21:46:41+08:00`；提交時間 `2026-10-08T21:46:41+08:00`。

<details>
<summary>完整清單差異（含項目、勾選與驗收變動）</summary>

````diff
--- 平台開發清單.md
+++ 平台開發清單.md
@@ -10,3 +10,3 @@
-本輪完成：有序多 LoRA 歷史條件與品質觀察、作品原圖並排與人工評分、固定一般插畫測試集及有限參數比較方案。382 項後端測試（381 通過、1 項既有 Windows 權限跳過）、Vue build 與桌面瀏覽器驗收通過；沒有新增 GPU 任務或正式資料，使用既有隔離圖片。4 步多 LoRA 對比不足，品質仍待調整；固定測試集跨模型 GPU 品質評測尚未完成。FLUX 約需 29.5 GiB，本機約 13.3 GiB 可用，RTX 4080 未實測。
-
-### 開發進度（更新至 2026-10-05）
+本輪完成：多 LoRA 的 8 步／反向順序實測、來源分離的任務耗時與提交前資源快照、Pony／Animagine 固定四案例比較。11 個隔離 GPU 任務／作品及離線核對通過；394 項後端測試（393 通過、1 項既有 Windows 權限跳過）、Vue 型別／建置通過。瀏覽器工具無法啟動，本輪 UI 實機驗收未完成。多 LoRA 仍偏淡，固定案例也有構圖偏差，不設為品質保證。FLUX 約需 29.5 GiB，本機約 7.6 GiB 可用，RTX 4080 未實測。
+
+### 開發進度（更新至 2026-10-08）
@@ -225,2 +225,3 @@
-- [ ] 使用固定的一般插畫測試集，比較提示服從、角色一致、視覺風格及構圖。
-- [x] 固定一般插畫測試集 v1：四個案例、成年旅人雙場景、明確評估要點、版本／檔案 hash；可用於方案預覽，尚未完成跨模型 GPU 品質評測。
+- [x] 固定一般插畫測試集：Pony V6 XL／Animagine 4.0 Opt 各四案例，共同參數／seed、原圖與角色雙場景觀察、快照及離線驗證完成；不是最佳預設或全面品質排名。
+- [ ] 更多 seed、模型及作者提示格式的品質比較；其他畫風、參考引導／角色鎖定仍待驗證。
+- [x] 固定一般插畫測試集 v1：四個案例、成年旅人雙場景、明確評估要點、版本／檔案 hash；可用於方案預覽；兩個已安裝模型的固定四案例已完成 GPU 比較，廣泛品質評估仍待進行。
@@ -545 +546 @@
-- [x] 原引擎單次 RAM／装置快照，與版本查詢共用，不新增負載；任務、SSE、作品來源沿用，無峰值推估。
+- [x] 原引擎單次 RAM／裝置快照，與版本查詢共用，不新增負載；任務、SSE、作品來源沿用，無峰值推估。
@@ -546,0 +548,8 @@
+
+## 優先項目 3：固定四案例跨模型 GPU 比較（2026-10-08）
+
+- [x] 單案例 CLI：固定權重、測試集版本／hash／完整案例、有界條件、一個 UUID；原回應遺失只查詢，報告／權重／來源不符拒絕。
+- [x] Pony／Animagine 各四張 1024²、28 steps、CFG 5、相同 seed 的實際生成；原圖／workflow／模型及環境／量測快照、設定還原與停止引擎後 GET 核對全部通過。
+- [x] 開發助手逐張觀察及案例筆記，保留船數／位置／非預期人物與角色衣著細節偏差；四項分數留空，等待使用者判斷。詳見 `docs/illustration-suite.md` 與 `docs/validation/general-illustration-suite-rtx3060.md`。
+- [x] 394 項後端測試（393 通過、1 項既有 Windows 權限跳過）、Vue 型別／建置通過；本輪瀏覽器工具環境故障，UI 實機驗收未完成。
+- [x] 三項各別完成後先 commit、push；正式 5 任務／3 作品／0 草稿未變更，隔離 11 任務／11 作品保留，8000／8001／8188／5173 均停止。
````

</details>

<a id="commit-8d9aa15a2dc10a34b3a817c03716bbc61b190bd3"></a>

### 22:02:17 · [8d9aa15](https://github.com/Zimkjdv/Model-Atelier/commit/8d9aa15a2dc10a34b3a817c03716bbc61b190bd3) · feat: compare individual LoRA model and CLIP strengths

來源：[完整清單原檔](https://github.com/Zimkjdv/Model-Atelier/blob/8d9aa15a2dc10a34b3a817c03716bbc61b190bd3/%E5%B9%B3%E5%8F%B0%E9%96%8B%E7%99%BC%E6%B8%85%E5%96%AE.md)；檔名 `平台開發清單.md`；Git blob `4267f017202f120d279cb18b8cdf4dd46e8ef79e`。

當時核取框：293，已勾選 263、未勾選 30。作者時間 `2026-10-08T22:02:17+08:00`；提交時間 `2026-10-08T22:02:17+08:00`。

<details>
<summary>完整清單差異（含項目、勾選與驗收變動）</summary>

````diff
--- 平台開發清單.md
+++ 平台開發清單.md
@@ -555,0 +556,8 @@
+
+
+## 比較功能優先項目 1：指定 LoRA 強度軸（2026-10-08）
+
+- [x] P4／P6：比較一個已啟用 LoRA 的模型或 CLIP 強度；保留另一種強度、其他 LoRA、啟用狀態、原順序及精確 seed。
+- [x] 只讀預覽、完整匯出及原方案 hash 核對；未知／停用目標、型別、超界與重複值拒絕，不提交或寫草稿。
+- [x] 397 項後端測試（396 通過、1 項既有 Windows 權限跳過）及 Vue 型別／建置通過；工具 sandbox 啟動失敗，UI 實機驗收未完成。沒有新增 GPU 任務或正式資料。
+- [ ] 更多強度／seed 的實際畫風品質仍待評估，不能把參數比較支援當成品質驗證。
````

</details>

<a id="commit-ea310584c69d5a3416d45a0d6feb5498c6aa5d36"></a>

### 22:06:21 · [ea31058](https://github.com/Zimkjdv/Model-Atelier/commit/ea310584c69d5a3416d45a0d6feb5498c6aa5d36) · feat: compare single-image workflows and denoise settings

來源：[完整清單原檔](https://github.com/Zimkjdv/Model-Atelier/blob/ea310584c69d5a3416d45a0d6feb5498c6aa5d36/%E5%B9%B3%E5%8F%B0%E9%96%8B%E7%99%BC%E6%B8%85%E5%96%AE.md)；檔名 `平台開發清單.md`；Git blob `2e0ea1ae2a492c7594f21541f267b726c296e733`。

當時核取框：297，已勾選 266、未勾選 31。作者時間 `2026-10-08T22:06:21+08:00`；提交時間 `2026-10-08T22:06:21+08:00`。

<details>
<summary>完整清單差異（含項目、勾選與驗收變動）</summary>

````diff
--- 平台開發清單.md
+++ 平台開發清單.md
@@ -563,0 +564,8 @@
+
+
+## 比較功能優先項目 2：圖生圖與改動幅度比較（2026-10-08）
+
+- [x] P6：單張 checkpoint 圖生圖方案、denoise 軸；保留同一素材 ID／fit／stretch、精確 seed、有序 LoRA 及完整設定。
+- [x] 文生圖不能借用 denoise 軸；多張／不符素材 ID 拒絕，原素材不可用則保留原值並提示。只讀預覽與匯出不生成或寫草稿。
+- [x] 明確提交選定組後，原生 LoadImage／VAEEncode 工作流程與完整還原通過隔離模擬引擎；401 項後端測試（400 通過、1 項既有 Windows 權限跳過）、Vue 型別／建置通過。
+- [ ] 不同 denoise／模型的 GPU 品質與新 UI 實機驗收待進行；本輪沒有新增 GPU 任務或正式資料。局部編輯、結構／畫風 adapter 仍待整合。
````

</details>

<a id="commit-eab5e76a5babe9d7c10e1289d3c1234e4fb8afb6"></a>

### 22:26:01 · [eab5e76](https://github.com/Zimkjdv/Model-Atelier/commit/eab5e76a5babe9d7c10e1289d3c1234e4fb8afb6) · feat: persist and import immutable comparison plans

來源：[完整清單原檔](https://github.com/Zimkjdv/Model-Atelier/blob/eab5e76a5babe9d7c10e1289d3c1234e4fb8afb6/%E5%B9%B3%E5%8F%B0%E9%96%8B%E7%99%BC%E6%B8%85%E5%96%AE.md)；檔名 `平台開發清單.md`；Git blob `c84126d609587f07cf8cb92d3f6a5b2dd2fb6734`。

當時核取框：305，已勾選 272、未勾選 33。作者時間 `2026-10-08T22:26:01+08:00`；提交時間 `2026-10-08T22:26:01+08:00`。

<details>
<summary>完整清單差異（含項目、勾選與驗收變動）</summary>

````diff
--- 平台開發清單.md
+++ 平台開發清單.md
@@ -10 +10 @@
-本輪完成：多 LoRA 的 8 步／反向順序實測、來源分離的任務耗時與提交前資源快照、Pony／Animagine 固定四案例比較。11 個隔離 GPU 任務／作品及離線核對通過；394 項後端測試（393 通過、1 項既有 Windows 權限跳過）、Vue 型別／建置通過。瀏覽器工具無法啟動，本輪 UI 實機驗收未完成。多 LoRA 仍偏淡，固定案例也有構圖偏差，不設為品質保證。FLUX 約需 29.5 GiB，本機約 7.6 GiB 可用，RTX 4080 未實測。
+本輪完成：指定 LoRA 模型／CLIP 強度軸、單張圖生圖 denoise 比較、完整方案保存／重載／JSON 匯入預覽。408 項後端測試（407 通過、1 項既有 Windows 權限跳過）及 Vue 建置通過；隔離 HTTP 三份方案保存、冪等請求與重啟後 GET 核對完成。正式資料不變，沒有新增 GPU 任務；UI 工具 sandbox 啟動失敗，瀏覽器操作待驗收。前一輪 11 個 GPU 案例的品質觀察保留，FLUX 磁碟與 RTX 4080 仍待驗證。
@@ -228 +228,3 @@
-- [x] 有限範圍參數比較：checkpoint 文生圖 Steps／CFG／字串 Seed 單一軸，最多八次單張預覽、完整快照與 JSON 匯出；逐組載入後手動生成，不自動批次或重試。
+- [x] 有限範圍參數比較：checkpoint 文生圖／單張圖生圖 Steps／CFG／字串 Seed／指定 LoRA 模型或 CLIP 強度，圖生圖另有 denoise 單一軸，最多八次單張預覽、完整快照與 JSON 匯出；逐組載入後手動生成，不自動批次或重試。
+- [x] 完整比較方案本機保存、重載、凍結案例與 JSON 匯入預覽；冪等保存、修訂式封存／還原、來源素材引用保護；載入設定與生成仍需明確操作。
+- [ ] 比較結果與方案自動關聯、更多模型／流程／參數軸待規劃，不提供自動批次與品質評分。
@@ -571,0 +574,10 @@
+
+
+## 比較功能優先項目 3：完整方案保存與匯入（2026-10-08）
+
+- [x] P6：不可變方案 SQLite 保存／重載，冪等 request_id、封存／還原 revision，原圖生圖素材引用保護與保存交易一致。
+- [x] 1 MiB JSON 選檔／貼上、只讀驗證及完整方案預覽；從單一軸重建各組，核對 hash、精確 seed、流程及數量；文件來源不當成相容或品質證明。
+- [x] 原案例快照凍結，測試集變動不替換歷史值；保存及載入方案不改創作表單、不建草稿或任務。使用者仍需明確載入各組並生成。
+- [x] 408 項後端測試（407 通過、1 項既有 Windows 權限跳過）及 Vue 型別／建置；隔離 HTTP 三份方案保存、相同 ID 重讀、CAS、素材引用及平台重啟後 GET-only 核對通過。見 `docs/experiment-storage.md`。
+- [x] 本輪三項各別 commit、push 後才做下一項；正式 5 任務／3 作品／0 草稿／0 方案不變，隔離 3 方案／1 素材／0 任務／0 作品保留，8000／8001／8188／5173 均停止。
+- [ ] UI 工具 sandbox 啟動失敗，本輪瀏覽器／原生下載／窄視窗驗收未完成。更多 GPU 品質、局部編輯／adapter、FLUX 安裝與 RTX 4080 仍待完成。
````

</details>

<a id="commit-79ea409438830a57c8b86f9672a952ec6cee0bfa"></a>

### 22:40:34 · [79ea409](https://github.com/Zimkjdv/Model-Atelier/commit/79ea409438830a57c8b86f9672a952ec6cee0bfa) · test: verify fixed LoRA strength and seed quality on RTX 3060

來源：[完整清單原檔](https://github.com/Zimkjdv/Model-Atelier/blob/79ea409438830a57c8b86f9672a952ec6cee0bfa/%E5%B9%B3%E5%8F%B0%E9%96%8B%E7%99%BC%E6%B8%85%E5%96%AE.md)；檔名 `平台開發清單.md`；Git blob `6ee844de578741d327507c1c33dd9d3ab415328a`。

當時核取框：310，已勾選 276、未勾選 34。作者時間 `2026-10-08T22:40:34+08:00`；提交時間 `2026-10-08T22:40:34+08:00`。

<details>
<summary>完整清單差異（含項目、勾選與驗收變動）</summary>

````diff
--- 平台開發清單.md
+++ 平台開發清單.md
@@ -10 +10 @@
-本輪完成：指定 LoRA 模型／CLIP 強度軸、單張圖生圖 denoise 比較、完整方案保存／重載／JSON 匯入預覽。408 項後端測試（407 通過、1 項既有 Windows 權限跳過）及 Vue 建置通過；隔離 HTTP 三份方案保存、冪等請求與重啟後 GET 核對完成。正式資料不變，沒有新增 GPU 任務；UI 工具 sandbox 啟動失敗，瀏覽器操作待驗收。前一輪 11 個 GPU 案例的品質觀察保留，FLUX 磁碟與 RTX 4080 仍待驗證。
+前一輪完成：指定 LoRA 模型／CLIP 強度軸、單張圖生圖 denoise 比較、完整方案保存／重載／JSON 匯入預覽。408 項後端測試（407 通過、1 項既有 Windows 權限跳過）及 Vue 建置通過；隔離 HTTP 三份方案保存、冪等請求與重啟後 GET 核對完成。正式資料不變，沒有新增 GPU 任務；UI 工具 sandbox 啟動失敗，瀏覽器操作待驗收。前一輪 11 個 GPU 案例的品質觀察保留，FLUX 磁碟與 RTX 4080 仍待驗證。
@@ -583,0 +584,9 @@
+
+
+## 新一輪優先項目 1：LoRA 強度與多 seed 品質驗證（2026-10-08）
+
+- [x] P4：固定單一畫風 LoRA 模型強度 0.5／1.0 × 兩個精確 seed，CLIP 強度與其餘參數不變；新增三個可重跑 CLI profiles。
+- [x] RTX 3060 四個八節點任務成功，完整工作流程／版本／雜湊／有序強度／原圖與設定還原核對；引擎離線後 GET-only 核對通過，原 ID 不重送。
+- [x] 人工檢查四張原圖，記錄組裝步驟缺失、幾何瑕疵及額外物件；不據兩個 seed 設定通用品質預設。見 `docs/validation/animagine-style-strength-rtx3060.md`。
+- [x] 409 項後端測試（408 通過、1 項既有 Windows 權限跳過）；正式資料不變，隔離 4 任務／4 作品保留。
+- [ ] 其他畫風、更廣泛品質、RTX 4080 與訓練資源仍待驗證。
````

</details>

<a id="commit-2a64a9a41a7b4c5a1a6f0fdb6e748cf63bd96930"></a>

### 22:48:13 · [2a64a9a](https://github.com/Zimkjdv/Model-Atelier/commit/2a64a9a41a7b4c5a1a6f0fdb6e748cf63bd96930) · feat: associate immutable experiment variants with jobs and artworks

來源：[完整清單原檔](https://github.com/Zimkjdv/Model-Atelier/blob/2a64a9a41a7b4c5a1a6f0fdb6e748cf63bd96930/%E5%B9%B3%E5%8F%B0%E9%96%8B%E7%99%BC%E6%B8%85%E5%96%AE.md)；檔名 `平台開發清單.md`；Git blob `177f4bd55c0de734f031603ac170e9fb236ea8f6`。

當時核取框：315，已勾選 280、未勾選 35。作者時間 `2026-10-08T22:48:13+08:00`；提交時間 `2026-10-08T22:48:13+08:00`。

<details>
<summary>完整清單差異（含項目、勾選與驗收變動）</summary>

````diff
--- 平台開發清單.md
+++ 平台開發清單.md
@@ -592,0 +593,9 @@
+
+
+## 新一輪優先項目 2：比較方案關聯後端（2026-10-08）
+
+- [x] P6：`/api/generate` 接收已保存方案 ID／hash／variant；交易內核對未封存及完整原設定，原子凍結 context，作品沿用不可變快照。
+- [x] 原請求先恢復、不探查引擎／重送；封存方案、離線、未知／失敗與來源檔案遺失保留原關聯，歷史任務／作品不回填。
+- [x] 結果只讀 API 依原變體列出任務及作品，包含空組、失敗、未知和封存；同 hash 不同方案 ID 分開，來源快照不符不合併。
+- [x] 新增交易競態、精確設定、圖生圖、原請求不重送及資料隔離測試；420 項後端測試（419 通過、1 項既有 Windows 權限跳過）。操作說明見 `docs/experiment-runs.md`。
+- [ ] 前端關聯操作與結果查看接續第三項；不提供自動批次、品質評分或反向補關聯。
````

</details>

<a id="commit-9abddcf5dec70d4ac0661fdd45e53dddbf5b1c2d"></a>

### 23:05:23 · [9abddcf](https://github.com/Zimkjdv/Model-Atelier/commit/9abddcf5dec70d4ac0661fdd45e53dddbf5b1c2d) · feat: show experiment associations and saved results in the studio

來源：[完整清單原檔](https://github.com/Zimkjdv/Model-Atelier/blob/9abddcf5dec70d4ac0661fdd45e53dddbf5b1c2d/%E5%B9%B3%E5%8F%B0%E9%96%8B%E7%99%BC%E6%B8%85%E5%96%AE.md)；檔名 `平台開發清單.md`；Git blob `fd2348102640034e28ae4fc9e6d8120e74fa9d26`。

當時核取框：323，已勾選 288、未勾選 35。作者時間 `2026-10-08T23:05:23+08:00`；提交時間 `2026-10-08T23:05:23+08:00`。

<details>
<summary>完整清單差異（含項目、勾選與驗收變動）</summary>

````diff
--- 平台開發清單.md
+++ 平台開發清單.md
@@ -10 +10 @@
-前一輪完成：指定 LoRA 模型／CLIP 強度軸、單張圖生圖 denoise 比較、完整方案保存／重載／JSON 匯入預覽。408 項後端測試（407 通過、1 項既有 Windows 權限跳過）及 Vue 建置通過；隔離 HTTP 三份方案保存、冪等請求與重啟後 GET 核對完成。正式資料不變，沒有新增 GPU 任務；UI 工具 sandbox 啟動失敗，瀏覽器操作待驗收。前一輪 11 個 GPU 案例的品質觀察保留，FLUX 磁碟與 RTX 4080 仍待驗證。
+本輪完成：LoRA 強度 0.5／1.0 × 兩個精確 seed 的 RTX 3060 品質比較、方案與任務／作品不可變關聯、創作頁載入與結果查看。420 項後端測試（419 通過、1 項既有 Windows 權限跳過）、前端關聯保護檢查及 Vue 型別／建置通過；隔離 5 個 GPU 任務／作品完成，封存阻擋、原 ID 恢復及平台重啟後離線核對通過。正式資料不變，相關服務埠均停止。瀏覽器工具仍因 Windows sandbox 啟動失敗，畫面操作／窄視窗待驗收；FLUX 安裝、其他工作流程及 RTX 4080 仍待驗證。
@@ -230 +230,2 @@
-- [ ] 比較結果與方案自動關聯、更多模型／流程／參數軸待規劃，不提供自動批次與品質評分。
+- [x] 已保存方案逐組手動載入及生成，任務／作品保存原關聯快照；結果區按變體查看任務、縮圖與原圖，舊資料不推測或回填。
+- [ ] 更多模型／流程／參數軸待規劃，不提供自動批次與品質評分。
@@ -601 +602,12 @@
-- [ ] 前端關聯操作與結果查看接續第三項；不提供自動批次、品質評分或反向補關聯。
+- [x] 前端關聯操作與結果查看已在第三項接入；不提供自動批次、品質評分或反向補關聯。
+
+
+## 新一輪優先項目 3：比較關聯與結果介面（2026-10-08）
+
+- [x] 已保存方案逐組載入時帶入原 ID／hash／variant，工作台顯示關聯；完整設定改動後需解除或重載，保存草稿／載入一般設定不會默默繼承關聯。
+- [x] 生成使用原 request_id 及完整關聯暫存；處理／待恢復時阻擋新的比較載入，原請求恢復不取用目前表單。
+- [x] 按組顯示所有原任務、錯誤、空組、已匯入／封存作品與縮圖／原圖；只讀重讀，不刷新引擎或自動生成；原任務與作品顯示凍結比較來源。
+- [x] 前端關聯邏輯檢查及 Vue 型別／建置通過。後端 420 項（419 通過、1 項既有 Windows 權限跳過），真實 RTX 3060 單一關聯任務生成、作品匯入、完整 workflow／快照／原圖 hash 核對、封存新請求 409、切換位址恢復原 ID 及平台重啟後 GET-only 通過。
+- [x] 證據 `runtime/experiment-run-20261008.json`、`runtime/experiment-run-recovery-20261008.json`、`runtime/experiment-runs-live-data-20261008`；隔離 1 方案／1 任務／1 作品／0 草稿，另一組沒有任務。第一項隔離 4 任務／4 作品保留，正式 5 任務／3 作品／0 草稿／0 方案不變。
+- [x] 三項各別 commit、push 後接續下一項；8000／8001／8188／5173 均未監聽。
+- [ ] 瀏覽器工具仍因 Windows sandbox `helper_unknown_error` 無法啟動，畫面點擊、實際下載及窄視窗未驗收；其他畫風、更廣泛品質、局部編輯／adapter、FLUX 安裝及 RTX 4080 仍待完成。
````

</details>

## 2026-10-09

<a id="commit-7e5680faf49ab76980493afd9c778f3610c392a9"></a>

### 02:53:36 · [7e5680f](https://github.com/Zimkjdv/Model-Atelier/commit/7e5680faf49ab76980493afd9c778f3610c392a9) · feat: add owned checkpoint inpainting submissions

來源：[完整清單原檔](https://github.com/Zimkjdv/Model-Atelier/blob/7e5680faf49ab76980493afd9c778f3610c392a9/%E5%B9%B3%E5%8F%B0%E9%96%8B%E7%99%BC%E6%B8%85%E5%96%AE.md)；檔名 `平台開發清單.md`；Git blob `86f4fd12b05cd1eb9be44ecfe087a9dad5f3121e`。

當時核取框：327，已勾選 291、未勾選 36。作者時間 `2026-10-09T02:53:36+08:00`；提交時間 `2026-10-09T02:53:36+08:00`。

<details>
<summary>完整清單差異（含項目、勾選與驗收變動）</summary>

````diff
--- 平台開發清單.md
+++ 平台開發清單.md
@@ -613,0 +614,8 @@
+
+
+## 局部編輯優先項目 1：雙輸入後端（2026-10-09）
+
+- [x] P6：固定 checkpoint-inpaint-v1，原圖／遮罩同尺寸、二值語意與獨立前處理快照；SD 1.x／SDXL 及最多四個有序 LoRA。
+- [x] 兩素材交易引用保護、原生節點嚴格檢查、兩次安全上傳；失敗不提交、unknown 不重送、UUID 原設定恢復與完整離線还原。
+- [x] 新增 14 項測試，完整後端 434 項（433 通過、1 項既有 Windows 權限跳過）。說明見 docs/inpainting.md。
+- [ ] 遮罩操作介面及 RTX 3060 實機驗收接續開發；比較／一般草稿／交換 JSON 不借用舊格式丟棄遮罩。
````

</details>

<a id="commit-ddac4d6c27c1cfe3010fcd49b967dbe6d9e6c893"></a>

### 03:02:02 · [ddac4d6](https://github.com/Zimkjdv/Model-Atelier/commit/ddac4d6c27c1cfe3010fcd49b967dbe6d9e6c893) · feat: add inpainting studio and binary mask editor

來源：[完整清單原檔](https://github.com/Zimkjdv/Model-Atelier/blob/ddac4d6c27c1cfe3010fcd49b967dbe6d9e6c893/%E5%B9%B3%E5%8F%B0%E9%96%8B%E7%99%BC%E6%B8%85%E5%96%AE.md)；檔名 `平台開發清單.md`；Git blob `079702fcdd51f91539804c6c0a1ea81ddb5f8406`。

當時核取框：332，已勾選 295、未勾選 37。作者時間 `2026-10-09T03:02:02+08:00`；提交時間 `2026-10-09T03:02:02+08:00`。

<details>
<summary>完整清單差異（含項目、勾選與驗收變動）</summary>

````diff
--- 平台開發清單.md
+++ 平台開發清單.md
@@ -621,0 +622,9 @@
+
+
+## 局部編輯優先項目 2：遮罩工作台（2026-10-09）
+
+- [x] 獨立表單、筆刷／擦除／清空／反相／PNG 載入及素材保存；座標依原圖換算，白色範圍明確顯示，未保存遮罩阻擋生成。
+- [x] 更換原圖清除遮罩，原素材尺寸檢查、完整 seed、LoRA／參數与模型版本；獨立 pending key、不自動提交或重送。
+- [x] 任務／作品雙輸入快照、原圖／遮罩連結及局部編輯還原路由；完整還原與未保存內容確認，拒絕把遮罩丟進舊草稿／比較格式。
+- [x] 前端遮罩與表單邏輯檢查、既有比較檢查及 Vue 型別／建置通過；第一項後端 434 項已通過。
+- [ ] 瀏覽器工具仍因 sandbox helper 啟動失敗，實際畫面操作／下載／窄視窗未驗收；RTX 3060 接續第三項。
````

</details>

<a id="commit-3e06576576d153c2b4cd1b4105fdbe95b2394d3f"></a>

### 03:17:49 · [3e06576](https://github.com/Zimkjdv/Model-Atelier/commit/3e06576576d153c2b4cd1b4105fdbe95b2394d3f) · test: verify inpainting on RTX 3060 and offline recovery

來源：[完整清單原檔](https://github.com/Zimkjdv/Model-Atelier/blob/3e06576576d153c2b4cd1b4105fdbe95b2394d3f/%E5%B9%B3%E5%8F%B0%E9%96%8B%E7%99%BC%E6%B8%85%E5%96%AE.md)；檔名 `平台開發清單.md`；Git blob `ddfa0dd87d96ee6436b4a582c9aca4e41888b62c`。

當時核取框：339，已勾選 302、未勾選 37。作者時間 `2026-10-09T03:17:49+08:00`；提交時間 `2026-10-09T03:17:49+08:00`。

<details>
<summary>完整清單差異（含項目、勾選與驗收變動）</summary>

````diff
--- 平台開發清單.md
+++ 平台開發清單.md
@@ -7 +7 @@
-更新日期：2026-10-08
+更新日期：2026-10-09
@@ -12 +12 @@
-### 開發進度（更新至 2026-10-08）
+### 開發進度（更新至 2026-10-09）
@@ -36 +36 @@
-- [x] 參考素材用途與單張 checkpoint 圖生圖後端／介面：來源／前處理快照、原生 LoadImage 與 VAEEncode、獨立任務上傳、草稿及作品設定還原，以及 Pony／RTX 3060 實機驗證。adapter 畫風與角色、ControlNet 結構、局部編輯仍待整合。
+- [x] 參考素材用途與單張 checkpoint 圖生圖後端／介面：來源／前處理快照、原生 LoadImage 與 VAEEncode、獨立任務上傳、草稿及作品設定還原，以及 Pony／RTX 3060 實機驗證。checkpoint 局部編輯後端／遮罩工作台與 Pony／Animagine／RTX 3060 已完成固定驗證；adapter 畫風與角色、ControlNet 結構仍待整合。
@@ -215 +215 @@
-- [ ] 逐項評估圖片生成圖片、局部編輯及結構參考流程；單張 checkpoint 圖生圖後端／介面與 Pony／RTX 3060 已驗證，其他流程仍待整合。
+- [ ] 逐項評估圖片生成圖片、局部編輯及結構參考流程；單張圖生圖與 checkpoint 局部編輯已完成後端／介面及固定 RTX 3060 驗證，結構參考與修補品質改善仍待完成。
@@ -621 +621 @@
-- [ ] 遮罩操作介面及 RTX 3060 實機驗收接續開發；比較／一般草稿／交換 JSON 不借用舊格式丟棄遮罩。
+- [x] 遮罩操作介面及 RTX 3060 實機驗收已在第二／三項完成；比較／一般草稿／交換 JSON 不借用舊格式丟棄遮罩。
@@ -630,0 +631,11 @@
+
+
+## 局部編輯優先項目 3：RTX 3060 與離線重啟驗收（2026-10-09）
+
+- [x] 固定模型／素材／取樣 CLI，權重大小及 SHA256 驗檔；原 UUID／完整流程先保存、只提交一次、非法報告拒絕、離線核對僅 GET。
+- [x] Pony 與 Animagine 各一張 768² 成功，遮罩外 520,704 像素差值為零；雙輸入、完整設定、版本／量測、作品匯入與重啟前後 JSON hash 一致。
+- [x] 實機發現並修正遮罩保存的 API 格式，統一原始圖片 body／檔名參數／20 MiB 限制，新增前端請求格式回歸檢查。
+- [x] 439 項後端（438 通過、1 項既有權限跳過）、35 項加強報告驗證回歸、遮罩／比較邏輯與 Vue 型別／建置通過。
+- [x] 兩張原圖保留顏色偏差、遮罩接縫及船身截斷觀察，未宣稱無縫修補或推薦通用品質預設。見 docs/validation/checkpoint-inpaint-rtx3060.md。
+- [x] 正式 5 任務／3 作品／0 素材／0 草稿／0 方案不變；隔離 2 素材／2 任務／2 作品保留。三項各別完成並 commit／push，8000／8001／8188／5173 均停止。
+- [ ] 瀏覽器工具仍無法啟動，實際筆刷／觸控／下載／窄視窗待驗收；羽化／邊界融合、專用 inpainting checkpoint、更多 seed、ControlNet／adapter、FLUX 權重与 RTX 4080 保留後續工作。
````

</details>

<a id="commit-87d277d5716c0c1f3a4307e1b3049d588abe2f95"></a>

### 04:14:14 · [87d277d](https://github.com/Zimkjdv/Model-Atelier/commit/87d277d5716c0c1f3a4307e1b3049d588abe2f95) · Add registered Canny ControlNet workflow submission and restoration

來源：[完整清單原檔](https://github.com/Zimkjdv/Model-Atelier/blob/87d277d5716c0c1f3a4307e1b3049d588abe2f95/%E5%B9%B3%E5%8F%B0%E9%96%8B%E7%99%BC%E6%B8%85%E5%96%AE.md)；檔名 `平台開發清單.md`；Git blob `54ecf4ba78a117e0bf7bbfb96b70a10289727999`。

當時核取框：345，已勾選 307、未勾選 38。作者時間 `2026-10-09T04:14:14+08:00`；提交時間 `2026-10-09T04:14:14+08:00`。

<details>
<summary>完整清單差異（含項目、勾選與驗收變動）</summary>

````diff
--- 平台開發清單.md
+++ 平台開發清單.md
@@ -10 +10 @@
-本輪完成：LoRA 強度 0.5／1.0 × 兩個精確 seed 的 RTX 3060 品質比較、方案與任務／作品不可變關聯、創作頁載入與結果查看。420 項後端測試（419 通過、1 項既有 Windows 權限跳過）、前端關聯保護檢查及 Vue 型別／建置通過；隔離 5 個 GPU 任務／作品完成，封存阻擋、原 ID 恢復及平台重啟後離線核對通過。正式資料不變，相關服務埠均停止。瀏覽器工具仍因 Windows sandbox 啟動失敗，畫面操作／窄視窗待驗收；FLUX 安裝、其他工作流程及 RTX 4080 仍待驗證。
+本輪接續 P6 ControlNet：第一項 Canny 結構參考後端已完成，451 項後端測試（450 通過、1 項既有 Windows 權限跳過）。專用工作台及固定 SDXL 控制模型／RTX 3060 驗收接續實作；一般草稿／比較方案、adapter 畫風／角色、FLUX 安裝與 RTX 4080 仍待完成。
@@ -641,0 +642,10 @@
+
+
+## ControlNet 優先項目 1：登記與 Canny 提交後端（2026-10-09）
+
+- [x] P6：引擎隔離的 ControlNet 清單、版本／來源／架構／類型／hash／授權登記；未知不推測，失敗保留快照。
+- [x] 固定十一節點 Canny 結構條件、空 latent、單張來源與四個有序 LoRA；不借用圖生圖 denoise 語意。
+- [x] 交易及上傳前／提交前的登記競態檢查、原生節點與即時模型驗證、不可覆寫來源；UUID 恢復／unknown 不重送。
+- [x] 任務／作品保留控制版本、原生 Canny／縮放快照、完整 seed 與離線還原；異常圖不部分載入。
+- [x] 新增 12 項測試，完整 451 項（450 通過、1 項既有權限跳過）。見 docs/controlnet.md。
+- [ ] 專用工作台與固定 SDXL Canny／RTX 3060 接續第二／三項；未宣稱畫風／角色鎖定或實機品質。
````

</details>

<a id="commit-8c61d4df91774feaba35cc4b1d7f1f2b26de3422"></a>

### 04:19:48 · [8c61d4d](https://github.com/Zimkjdv/Model-Atelier/commit/8c61d4df91774feaba35cc4b1d7f1f2b26de3422) · Add dedicated Canny studio, ControlNet registry and complete restoration

來源：[完整清單原檔](https://github.com/Zimkjdv/Model-Atelier/blob/8c61d4df91774feaba35cc4b1d7f1f2b26de3422/%E5%B9%B3%E5%8F%B0%E9%96%8B%E7%99%BC%E6%B8%85%E5%96%AE.md)；檔名 `平台開發清單.md`；Git blob `6dd2a6dbcef1fd2463490b00262b6281f0b605f8`。

當時核取框：350，已勾選 311、未勾選 39。作者時間 `2026-10-09T04:19:48+08:00`；提交時間 `2026-10-09T04:19:48+08:00`。

<details>
<summary>完整清單差異（含項目、勾選與驗收變動）</summary>

````diff
--- 平台開發清單.md
+++ 平台開發清單.md
@@ -651,0 +652,9 @@
+
+
+## ControlNet 優先項目 2：結構參考工作台（2026-10-09）
+
+- [x] ControlNet 模型庫登記與搜尋／同步、未知版本與類型、來源／hash／授權；引擎切換忽略過期回覆。
+- [x] 獨立 Canny 工作台：原素材預覽、控制模型、浮點閾值、強度、作用範圍、完整 seed 與有序 LoRA；同架構／成功清單保護。
+- [x] 獨立 pending 請求、未保存替換確認、切換保留；任務／作品控制快照及完整還原路由，不丟入舊草稿格式。
+- [x] Canny／既有遮罩／比較邏輯檢查，Vue 型別與建置通過；第一項 451 項後端已通過。
+- [ ] 瀏覽器工具本輪仍因 Node kernel 啟動失敗，畫面操作與窄視窗待驗收；固定控制權重／RTX 3060 接續第三項。
````

</details>

<a id="commit-7b033934fa75bba06990af37c59c06017feda2e8"></a>

### 04:33:58 · [7b03393](https://github.com/Zimkjdv/Model-Atelier/commit/7b033934fa75bba06990af37c59c06017feda2e8) · Install pinned SDXL Canny weights and verify RTX 3060 durable generation

來源：[完整清單原檔](https://github.com/Zimkjdv/Model-Atelier/blob/7b033934fa75bba06990af37c59c06017feda2e8/%E5%B9%B3%E5%8F%B0%E9%96%8B%E7%99%BC%E6%B8%85%E5%96%AE.md)；檔名 `平台開發清單.md`；Git blob `cfa3c8585b7147ea4b6167f23420b01d90a1b446`。

當時核取框：358，已勾選 318、未勾選 40。作者時間 `2026-10-09T04:33:58+08:00`；提交時間 `2026-10-09T04:33:58+08:00`。

<details>
<summary>完整清單差異（含項目、勾選與驗收變動）</summary>

````diff
--- 平台開發清單.md
+++ 平台開發清單.md
@@ -10 +10 @@
-本輪接續 P6 ControlNet：第一項 Canny 結構參考後端已完成，451 項後端測試（450 通過、1 項既有 Windows 權限跳過）。專用工作台及固定 SDXL 控制模型／RTX 3060 驗收接續實作；一般草稿／比較方案、adapter 畫風／角色、FLUX 安裝與 RTX 4080 仍待完成。
+本輪完成 P6 ControlNet 的登記／Canny 提交後端、專用結構工作台、固定官方 SDXL Canny FP16 安裝與 Pony／Animagine 各一個 RTX 3060 驗收。459 項後端（458 通過、1 項既有 Windows 權限跳過），Canny／遮罩／比較與 Vue 型別／建置通過；離線原 UUID、版本差異與平台重啟核對完成。正式資料不變，服務停止。瀏覽器工具仍無法啟動，畫面／窄視窗待驗收；其他控制模型、adapter、FLUX 安裝及 RTX 4080 仍待完成。
@@ -36 +36 @@
-- [x] 參考素材用途與單張 checkpoint 圖生圖後端／介面：來源／前處理快照、原生 LoadImage 與 VAEEncode、獨立任務上傳、草稿及作品設定還原，以及 Pony／RTX 3060 實機驗證。checkpoint 局部編輯後端／遮罩工作台與 Pony／Animagine／RTX 3060 已完成固定驗證；adapter 畫風與角色、ControlNet 結構仍待整合。
+- [x] 參考素材用途與單張 checkpoint 圖生圖後端／介面：來源／前處理快照、原生 LoadImage 與 VAEEncode、獨立任務上傳、草稿及作品設定還原，以及 Pony／RTX 3060 實機驗證。checkpoint 局部編輯後端／遮罩工作台與 Pony／Animagine／RTX 3060 已完成固定驗證；Canny 結構後端／介面與固定 SDXL／RTX 3060 已整合，其他控制類型與 adapter 畫風／角色仍待整合。
@@ -660,0 +661,12 @@
+
+
+## ControlNet 優先項目 3：固定模型及 RTX 3060 驗收（2026-10-09）
+
+- [x] 官方 SDXL Canny 1.0 FP16 固定修訂／大小／SHA256／授權 manifest，限制 controlnet 目錄、續傳、唯讀容量檢查及不可覆寫現有檔案；完整本機驗檔完成。
+- [x] 單次安全驗收 CLI，兩份固定權重驗檔、完整來源／控制版本、原 UUID 保存／回應遺失不重送、非法報告拒絕、GET-only 離線核對。
+- [x] Pony／Animagine 各一張 768²／20 steps 成功，工作流程、精確 seed、來源／控制快照、作品 hash 及完整還原通過；品質偏差如實保存，未宣稱畫風／角色鎖定。
+- [x] 引擎關閉且登記變更後原請求 200、改參數 409；平台重啟後 GET-only 與完整任務 JSON hash 一致，沒有重送。
+- [x] 新增 8 項 CLI／安裝測試，完整後端 459 項（458 通過、1 項既有權限跳過），Canny／遮罩／比較邏輯與 Vue 型別／建置通過；前處理布林型別與完整 LoRA 強度還原已補強。
+- [x] 隔離 1 素材／2 任務／2 作品保留，正式 5 任務／3 作品／0 素材／0 草稿／0 方案及 settings 指紋不變；8000／8001／8188／5173 均停止。詳見 docs/validation/checkpoint-canny-rtx3060.md。
+- [x] 三項依序完成、各別 commit／push 後接續下一項。
+- [ ] 瀏覽器工具仍無法啟動，畫面／下載／窄視窗未驗收；下一批評估邊緣預覽／保存、更多 seed／強度、depth／pose／adapter、專用局部編輯／羽化、FLUX 安裝容量及 RTX 4080。
````

</details>

<a id="commit-3dc10b8c2d71883b1514c85db9f353c48476e108"></a>

### 09:51:24 · [3dc10b8](https://github.com/Zimkjdv/Model-Atelier/commit/3dc10b8c2d71883b1514c85db9f353c48476e108) · feat: preserve actual Canny conditioning outputs in versioned workflows

來源：[完整清單原檔](https://github.com/Zimkjdv/Model-Atelier/blob/3dc10b8c2d71883b1514c85db9f353c48476e108/%E5%B9%B3%E5%8F%B0%E9%96%8B%E7%99%BC%E6%B8%85%E5%96%AE.md)；檔名 `平台開發清單.md`；Git blob `2d535a1d38cf2af9e1f9b9648e5289926192033b`。

當時核取框：363，已勾選 322、未勾選 41。作者時間 `2026-10-09T09:51:24+08:00`；提交時間 `2026-10-09T09:51:24+08:00`。

<details>
<summary>完整清單差異（含項目、勾選與驗收變動）</summary>

````diff
--- 平台開發清單.md
+++ 平台開發清單.md
@@ -10 +10 @@
-本輪完成 P6 ControlNet 的登記／Canny 提交後端、專用結構工作台、固定官方 SDXL Canny FP16 安裝與 Pony／Animagine 各一個 RTX 3060 驗收。459 項後端（458 通過、1 項既有 Windows 權限跳過），Canny／遮罩／比較與 Vue 型別／建置通過；離線原 UUID、版本差異與平台重啟核對完成。正式資料不變，服務停止。瀏覽器工具仍無法啟動，畫面／窄視窗待驗收；其他控制模型、adapter、FLUX 安裝及 RTX 4080 仍待完成。
+本輪接續 P6 Canny：第一項 v2 實際邊緣輸出與安全本機保存後端完成；專用任務／作品查看介面及兩 seed／兩強度 RTX 3060 比較接續實作。v1 原請求与流程保留，未回填邊緣圖。
@@ -215 +215 @@
-- [ ] 逐項評估圖片生成圖片、局部編輯及結構參考流程；單張圖生圖與 checkpoint 局部編輯已完成後端／介面及固定 RTX 3060 驗證，結構參考與修補品質改善仍待完成。
+- [ ] 逐項評估圖片生成圖片、局部編輯及結構參考流程；單張圖生圖與 checkpoint 局部編輯已完成後端／介面及固定 RTX 3060 驗證，Canny 結構已完成固定整合，其他結構流程與修補品質改善仍待完成。
@@ -672,0 +673,9 @@
+
+
+## Canny 追溯優先項目 1：實際邊緣輸出後端（2026-10-09）
+
+- [x] 固定 v2 十二節點，節點 16 保存同次 Canny 條件；v1 格式／原 UUID 及還原保留，新增 API 不跨端點重送。
+- [x] 明確保存原歷史邊緣 PNG，原引擎位置／二值／尺寸／大小／hash 驗證；只讀 API 不連線引擎或重新計算。
+- [x] SQLite 交易與排他檔案去重，不覆寫遺失／不符／orphan；磁碟／交易失敗只清理本次檔案。獨立快照，不改任務／作品。
+- [x] 作品只匯入節點 7，完整流程還原仍保留第二個 SaveImage；新增 12 項保護測試。
+- [ ] 介面与两 seed／两強度 RTX 3060 比較接續第二／三項。
````

</details>

<a id="commit-c8b1cf578d5a61faa33ef5bafd1d66d1b6d85ccf"></a>

### 09:55:38 · [c8b1cf5](https://github.com/Zimkjdv/Model-Atelier/commit/c8b1cf578d5a61faa33ef5bafd1d66d1b6d85ccf) · feat: show saved Canny edges and preserve legacy submission recovery

來源：[完整清單原檔](https://github.com/Zimkjdv/Model-Atelier/blob/c8b1cf578d5a61faa33ef5bafd1d66d1b6d85ccf/%E5%B9%B3%E5%8F%B0%E9%96%8B%E7%99%BC%E6%B8%85%E5%96%AE.md)；檔名 `平台開發清單.md`；Git blob `4391893714a9f4d4f3e99274519f7c2c5dd00a3d`。

當時核取框：368，已勾選 326、未勾選 42。作者時間 `2026-10-09T09:55:38+08:00`；提交時間 `2026-10-09T09:55:38+08:00`。

<details>
<summary>完整清單差異（含項目、勾選與驗收變動）</summary>

````diff
--- 平台開發清單.md
+++ 平台開發清單.md
@@ -681 +681,10 @@
-- [ ] 介面与两 seed／两強度 RTX 3060 比較接續第二／三項。
+- [ ] 介面已於第二項完成；兩 seed／兩強度 RTX 3060 比較接續第三項。
+
+
+## Canny 追溯優先項目 2：任務／作品邊緣圖介面（2026-10-09）
+
+- [x] 新提交使用 v2；任務與作品可展開唯讀狀態、明確匯入原邊緣 PNG、離線預覽／下載、查看 hash／尺寸／白色像素數。
+- [x] v1／v2 任務／作品標示、完整還原與導向；舊 pending 原 body／UUID／端點不變，新版本機標記不送入 API，未知標記保留並拒絕。
+- [x] 來源切換、KeepAlive 與卸載取消讀取／忽略過期回覆；讀取失敗不沿用舊圖，缺檔不自動重抓。
+- [x] Canny 請求恢復／來源驗證、遮罩與比較檢查，Vue 型別與 production build 通過。
+- [ ] 瀏覽器工具 Node kernel 無法啟動，畫面操作／窄視窗仍待驗收；兩 seed／兩強度 RTX 3060 接續第三項。
````

</details>

<a id="commit-e992b00a990fb531516ba65a093e6a4aa5ac43bc"></a>

### 10:09:33 · [e992b00](https://github.com/Zimkjdv/Model-Atelier/commit/e992b00a990fb531516ba65a093e6a4aa5ac43bc) · test: verify Canny edge seed and strength cases on RTX 3060

來源：[完整清單原檔](https://github.com/Zimkjdv/Model-Atelier/blob/e992b00a990fb531516ba65a093e6a4aa5ac43bc/%E5%B9%B3%E5%8F%B0%E9%96%8B%E7%99%BC%E6%B8%85%E5%96%AE.md)；檔名 `平台開發清單.md`；Git blob `18782c00e5db9bf79cb6a151ad5e487f55f20fff`。

當時核取框：376，已勾選 334、未勾選 42。作者時間 `2026-10-09T10:09:33+08:00`；提交時間 `2026-10-09T10:09:33+08:00`。

<details>
<summary>完整清單差異（含項目、勾選與驗收變動）</summary>

````diff
--- 平台開發清單.md
+++ 平台開發清單.md
@@ -10 +10 @@
-本輪接續 P6 Canny：第一項 v2 實際邊緣輸出與安全本機保存後端完成；專用任務／作品查看介面及兩 seed／兩強度 RTX 3060 比較接續實作。v1 原請求与流程保留，未回填邊緣圖。
+本輪接續 P6 Canny：v2 實際邊緣輸出與安全保存、任務／作品查看介面、兩 seed／兩強度 RTX 3060 與離線重啟驗收完成；修正 Windows 原歷史子目錄。v1 原請求與流程保留，不回填邊緣圖。完整後端 477 項（476 通過、1 項既有 skip）；正式資料不變，測試服務停止。
@@ -681 +681 @@
-- [ ] 介面已於第二項完成；兩 seed／兩強度 RTX 3060 比較接續第三項。
+- [x] 介面已於第二項完成；兩 seed／兩強度 RTX 3060 比較已於第三項完成。
@@ -690,0 +691,12 @@
+
+
+## Canny 追溯優先項目 3：兩 seed／兩強度 RTX 3060 比較（2026-10-09）
+
+- [x] 單次 v2 固定 profile CLI、完整權重驗檔、原 UUID 不重送、實際邊緣 PNG／來源／解碼 RGB／白色像素及完整版本快照。
+- [x] Animagine 四個 768²／20 steps CUDA 任務完成，兩 seed／兩強度保存四作品與四邊緣；條件像素相同，品質偏差如實保留。
+- [x] 修正 ComfyUI Windows 歷史反斜線驗證，仍拒絕外部／..／重複分隔符；首張保留初次失敗報告，再讀原 output，不重生成。
+- [x] 引擎關閉後原 UUID 200、改強度 409、邊緣去重 imported=false；登記變更／平台重啟後四份 GET-only 報告與完整任務 JSON 不變。
+- [x] 五項新增 CLI 與一項 Windows 契約測試，477 項後端（476 通過、1 項既有權限跳過）；Canny／遮罩／比較邏輯與 Vue 型別／建置通過。
+- [x] 隔離 1 素材／4 任務／4 作品／4 邊緣保留，正式 13 settings key 指紋及 5 任務／3 作品不變；8000／8001／8188／5173 皆停止。見 docs/validation/canny-edges-rtx3060.md。
+- [x] 本批三項分別完成、commit／push 後才進行下一項。
+- [ ] 瀏覽器畫面／窄視窗操作、未提交設定即時邊緣預覽、Pony v2／其他 LoRA、depth／pose／adapter、局部編輯品質改善、FLUX 安裝容量與 RTX 4080 接續評估。
````

</details>

## 2026-10-22

<a id="commit-b9bd7d74c256c2f416d19d1cc3f4967f9f4a8676"></a>

### 18:58:55 · [b9bd7d7](https://github.com/Zimkjdv/Model-Atelier/commit/b9bd7d74c256c2f416d19d1cc3f4967f9f4a8676) · feat: add versioned inward feathering for checkpoint inpainting

來源：[完整清單原檔](https://github.com/Zimkjdv/Model-Atelier/blob/b9bd7d74c256c2f416d19d1cc3f4967f9f4a8676/%E5%B9%B3%E5%8F%B0%E9%96%8B%E7%99%BC%E6%B8%85%E5%96%AE.md)；檔名 `平台開發清單.md`；Git blob `bba1813000b2347df1e75449a5721db6152596f3`。

當時核取框：380，已勾選 337、未勾選 43。作者時間 `2026-10-22T18:58:55+08:00`；提交時間 `2026-10-22T18:58:55+08:00`。

<details>
<summary>完整清單差異（含項目、勾選與驗收變動）</summary>

````diff
--- 平台開發清單.md
+++ 平台開發清單.md
@@ -7 +7 @@
-更新日期：2026-10-09
+更新日期：2026-10-22
@@ -10,3 +10,3 @@
-本輪接續 P6 Canny：v2 實際邊緣輸出與安全保存、任務／作品查看介面、兩 seed／兩強度 RTX 3060 與離線重啟驗收完成；修正 Windows 原歷史子目錄。v1 原請求與流程保留，不回填邊緣圖。完整後端 477 項（476 通過、1 項既有 skip）；正式資料不變，測試服務停止。
-
-### 開發進度（更新至 2026-10-09）
+本輪接續 P6 修補品質：內側羽化 v2 後端完成，工作台／預覽及 RTX 3060 比較依序接續。v1 原請求與流程保留。P5 磁碟已足夠，但 BFL 主模型／VAE 固定來源回傳 401 GatedRepo，本機沒有已授權 HF token，實機 FLUX 仍待來源存取。
+
+### 開發進度（更新至 2026-10-22）
@@ -702,0 +703,8 @@
+
+
+## 內側羽化優先項目 1：版本化後端（2026-10-22）
+
+- [x] checkpoint-inpaint-feather-v2 十一節點：二值去噪與灰階合成分離，半徑 0–64 輸出像素，原黑色 alpha 為零；細遮罩消失明確拒絕。
+- [x] CPU 預覽不連線引擎、不建立檔案或任務；方法／Pillow／二值來源／PNG hash 快照、三份排他輸入、失敗／未知不重送。
+- [x] v1 原端點及 UUID 恢復保留；完整 v2 任務／作品還原，讀取合成遮罩不重新計算／回填，新增十二項保護測試。
+- [ ] 工作台預覽／新參數／pending 相容與 RTX 3060 比較依序接續第二／三項。詳見 docs/inpaint-feather.md。
````

</details>

<a id="commit-2c43e470723d05725e6f78c0b2d131696bd0bae1"></a>

### 19:09:17 · [2c43e47](https://github.com/Zimkjdv/Model-Atelier/commit/2c43e470723d05725e6f78c0b2d131696bd0bae1) · feat: preview inward feather masks in the inpaint studio

來源：[完整清單原檔](https://github.com/Zimkjdv/Model-Atelier/blob/2c43e470723d05725e6f78c0b2d131696bd0bae1/%E5%B9%B3%E5%8F%B0%E9%96%8B%E7%99%BC%E6%B8%85%E5%96%AE.md)；檔名 `平台開發清單.md`；Git blob `14b651ab01708bad79ad2333613703c9a9caabd5`。

當時核取框：386，已勾選 342、未勾選 44。作者時間 `2026-10-22T19:09:17+08:00`；提交時間 `2026-10-22T19:09:17+08:00`。

<details>
<summary>完整清單差異（含項目、勾選與驗收變動）</summary>

````diff
--- 平台開發清單.md
+++ 平台開發清單.md
@@ -710,0 +711,10 @@
+
+
+## 內側羽化優先項目 2：工作台與預覽（2026-10-22）
+
+- [x] 羽化參數預設 0、CPU 真實灰階預覽、明確未保存／失效／細遮罩提示；回應大小、RGB PNG／尺寸／SHA256 驗證。
+- [x] v1 pending 仍送原端點，v2 標記不傳入 API；v1 載入新表單時補 0，不改歷史。任務／作品還原導向、原合成遮罩來源／hash 及下載連結。
+- [x] 過期回覆、參數／來源變動、KeepAlive、Blob URL 清理；原素材／二值／合成快照分開顯示。
+- [x] 前端遮罩／Canny／比較邏輯、Vue 型別與建置通過；瀏覽器離線預覽、參數失效、非法半徑、切換保留與 390px 無橫向溢出通過。
+- [x] UI 隔離 2 素材／0 任務／0 作品，正式指紋未變；截圖與說明見 docs/inpaint-feather.md。
+- [ ] 真實 RTX 3060 羽化比較及新歷史介面核對接續第三項；筆刷觸控尚未重驗。
````

</details>

<a id="commit-962216ba12f73b800bd500904d91526bbe499a52"></a>

### 19:29:12 · [962216b](https://github.com/Zimkjdv/Model-Atelier/commit/962216ba12f73b800bd500904d91526bbe499a52) · test: verify feathered inpainting on RTX 3060 with offline recovery

來源：[完整清單原檔](https://github.com/Zimkjdv/Model-Atelier/blob/962216ba12f73b800bd500904d91526bbe499a52/%E5%B9%B3%E5%8F%B0%E9%96%8B%E7%99%BC%E6%B8%85%E5%96%AE.md)；檔名 `平台開發清單.md`；Git blob `8590e42fa9acaf53326b39e704c3a4972dcd00fc`。

當時核取框：395，已勾選 352、未勾選 43。作者時間 `2026-10-22T19:29:12+08:00`；提交時間 `2026-10-22T19:29:12+08:00`。

<details>
<summary>完整清單差異（含項目、勾選與驗收變動）</summary>

````diff
--- 平台開發清單.md
+++ 平台開發清單.md
@@ -10 +10 @@
-本輪接續 P6 修補品質：內側羽化 v2 後端完成，工作台／預覽及 RTX 3060 比較依序接續。v1 原請求與流程保留。P5 磁碟已足夠，但 BFL 主模型／VAE 固定來源回傳 401 GatedRepo，本機沒有已授權 HF token，實機 FLUX 仍待來源存取。
+本輪 P6 內側羽化三項完成：版本化後端、CPU 真實預覽工作台、Pony／Animagine 各兩半徑 RTX 3060 與離線重啟驗收；v1 原請求保留。494 項後端（493 通過、1 既有 skip）、前端檢查／建置與本輪瀏覽器操作通過。正式資料不變，測試服務停止。P5 磁碟已足夠，但 BFL 主模型／VAE 回傳 401 GatedRepo，本機無已授權 HF token，FLUX 仍待來源存取。
@@ -710 +710 @@
-- [ ] 工作台預覽／新參數／pending 相容與 RTX 3060 比較依序接續第二／三項。詳見 docs/inpaint-feather.md。
+- [x] 工作台預覽／新參數／pending 相容與 RTX 3060 比較已於第二／三項完成。詳見 docs/inpaint-feather.md。
@@ -720 +720,14 @@
-- [ ] 真實 RTX 3060 羽化比較及新歷史介面核對接續第三項；筆刷觸控尚未重驗。
+- [x] 真實 RTX 3060 羽化比較及新歷史介面已於第三項核對；筆刷觸控尚未重驗。
+
+
+## 內側羽化優先項目 3：RTX 3060 與持久化驗收（2026-10-22）
+
+- [x] 固定單次 CLI、兩模型權重完整驗檔、原 UUID 不重送、預覽／保存合成 PNG 相同、完整三輸入／來源／版本與精確 seed。
+- [x] Pony／Animagine 各半徑 0／16，四個 CUDA 任務及作品成功；遮罩外 520,704 像素差值均 0、兩模型各自不透明核心 32,548 像素相同；淡出／截斷與色彩偏差保留。
+- [x] 引擎關閉原 UUID 200、改半徑 409；平台重啟後四份 GET-only 報告與原完整任務 JSON 不變。
+- [x] 修正 CLI 作品摘要不含 workflow 的契約，首張只 GET 恢復原證據不重新生成；修正未支援流程誤顯示的設定交換入口，保留 workflow 下載。
+- [x] 真實瀏覽器預覽／390px、歷史羽化來源／下載 hash／精確 seed 與半徑還原通過；筆刷觸控與真實遺失回應的 pending 未重驗。
+- [x] 新增五項 CLI 測試，完整 494 項後端（493 通過、1 既有 skip）；遮罩／Canny／比較及 Vue 型別／建置通過。
+- [x] GPU 隔離 2 素材／4 任務／4 作品、UI 隔離 2 素材／0 任務／0 作品；正式 13 settings key 指紋及 5 任務／3 作品不變，8000／8001／8188／5173 均停止。見 docs/validation/inpaint-feather-rtx3060.md。
+- [x] 本批三項各完成、commit／push 後接續下一項。
+- [ ] P5 固定 BFL 權重需先取得來源存取；P6 專用 inpainting 模型／其他半徑與 seed、depth／pose／adapter、Canny 未提交即時預覽及 RTX 4080 接續評估。
````

</details>

<a id="commit-4ef9c0e6e5d1f5409deffa3f254ca293f054223f"></a>

### 19:39:37 · [4ef9c0e](https://github.com/Zimkjdv/Model-Atelier/commit/4ef9c0e6e5d1f5409deffa3f254ca293f054223f) · feat: add bounded local CPU Canny preview and formal roadmap

來源：[完整清單原檔](https://github.com/Zimkjdv/Model-Atelier/blob/4ef9c0e6e5d1f5409deffa3f254ca293f054223f/ROADMAP.MD)；檔名 `ROADMAP.MD`；Git blob `3133dc9211e2b8134140725deb21e18aa36dd8ad`。

當時核取框：399，已勾選 356、未勾選 43。作者時間 `2026-10-22T19:39:37+08:00`；提交時間 `2026-10-22T19:39:37+08:00`。

<details>
<summary>完整清單差異（含項目、勾選與驗收變動）</summary>

````diff
--- 平台開發清單.md
+++ ROADMAP.MD
@@ -1 +1,9 @@
-# Model Atelier — 平台開發清單
+# Model Atelier — Roadmap
+
+## 待辦統計（2026-10-22，本批開始前）
+
+- 原始核取框：395 項，352 已完成、43 未完成。
+- 主清單（P0–P8 與待確認事項）：27 項未完成；歷史增量紀錄：16 條未完成提醒。
+- 歷史提醒常重複主清單、合併多個功能，亦有部分被後續驗收完成；43 不是獨立功能數。後續統計維持原始核取框與主／歷史分開，不直接以完成三個增量工作扣除三個大項。
+- 本批依序：Canny 送出前 CPU 預覽 API、預覽工作台、RTX 3060 原邊緣與離線／瀏覽器驗收；各項驗證後 commit／push 才開始下一項。
+- P5 固定 FLUX 來源存取仍待取得；RTX 4080 需於該機器驗證，兩者未列為完成。
@@ -733,0 +742,8 @@
+
+
+## Canny 預覽優先項目 1：CPU 預覽後端（2026-10-22）
+
+- [x] 固定本地 ComfyUI Python／稽核原碼的 Kornia CPU 預覽，不需模型或引擎，無任務／檔案／歷史回填。
+- [x] 獨立嚴格輸入、素材驗檔、單一 worker、超時回收與限量讀寫；二值 RGB、尺寸、hash 與實際版本來源驗證。
+- [x] 將開發清單正式更名為 ROADMAP.MD，保留原始 43／主 27／歷史 16 的統計口徑。
+- [x] 本項後端測試通過後 commit／push；工作台與實機驗收接續下一項。
````

</details>

<a id="commit-237c48b95db034d538fad016c3db24b47f7eb1c8"></a>

### 19:45:11 · [237c48b](https://github.com/Zimkjdv/Model-Atelier/commit/237c48b95db034d538fad016c3db24b47f7eb1c8) · feat: add source-verified Canny preview to the studio

來源：[完整清單原檔](https://github.com/Zimkjdv/Model-Atelier/blob/237c48b95db034d538fad016c3db24b47f7eb1c8/ROADMAP.MD)；檔名 `ROADMAP.MD`；Git blob `ddc6cb639ccf44bfc2f546f86233ce7108cce192`。

當時核取框：403，已勾選 360、未勾選 43。作者時間 `2026-10-22T19:45:11+08:00`；提交時間 `2026-10-22T19:45:11+08:00`。

<details>
<summary>完整清單差異（含項目、勾選與驗收變動）</summary>

````diff
--- ROADMAP.MD
+++ ROADMAP.MD
@@ -749,0 +750,8 @@
+
+
+## Canny 預覽優先項目 2：工作台（2026-10-22）
+
+- [x] 明確按鈕計算 CPU 預覽，無模型／引擎亦可使用；顯示尺寸、閾值、縮放與實際版本來源，不冒充原任務輸出。
+- [x] 獨立請求欄位、回應大小與 provenance／PNG／SHA256 驗證；參數與來源變動、KeepAlive、過期回覆及 Blob URL 清理。
+- [x] 前端 Canny／局部編輯／比較檢查與 Vue 型別／production build 通過；實際離線預覽、非法閾值、切換保留／清理與 390px 佈局通過。
+- [x] 隔離 2 素材／4 既有任務／4 既有作品不增加生成；正式指紋不變。原生 GPU 邊緣／保存歷史比對接續第三項。
````

</details>

<a id="commit-ab17b82dd9092f9abb35a7cc6ea635877c3f61bd"></a>

### 19:58:04 · [ab17b82](https://github.com/Zimkjdv/Model-Atelier/commit/ab17b82dd9092f9abb35a7cc6ea635877c3f61bd) · test: verify Canny CPU previews against RTX 3060 and saved history

來源：[完整清單原檔](https://github.com/Zimkjdv/Model-Atelier/blob/ab17b82dd9092f9abb35a7cc6ea635877c3f61bd/ROADMAP.MD)；檔名 `ROADMAP.MD`；Git blob `a54f85eedb11ee6b49681daccfe905a351d3b7a6`。

當時核取框：409，已勾選 369、未勾選 40。作者時間 `2026-10-22T19:58:04+08:00`；提交時間 `2026-10-22T19:58:04+08:00`。

<details>
<summary>完整清單差異（含項目、勾選與驗收變動）</summary>

````diff
--- ROADMAP.MD
+++ ROADMAP.MD
@@ -3 +3,5 @@
-## 待辦統計（2026-10-22，本批開始前）
+## 目前待辦統計（2026-10-22，本批完成後）
+
+核取框共 409 項，369 已完成、40 未完成；主清單 27、歷史提醒 13。本批補驗後關閉三條歷史提醒；P6 的其他結構／參考工作仍未完成。
+
+### 本批開始前的基準
@@ -659 +663 @@
-- [ ] 專用工作台與固定 SDXL Canny／RTX 3060 接續第二／三項；未宣稱畫風／角色鎖定或實機品質。
+- [x] 專用工作台與固定 SDXL Canny／RTX 3060 已於後續完成；2026-10-22 補驗離線介面與原邊緣，不宣稱畫風／角色鎖定。
@@ -668 +672 @@
-- [ ] 瀏覽器工具本輪仍因 Node kernel 啟動失敗，畫面操作與窄視窗待驗收；固定控制權重／RTX 3060 接續第三項。
+- [x] 當時瀏覽器工具無法啟動；2026-10-22 已補驗工作台、離線預覽與 390px，固定控制權重／RTX 3060 已於後續完成。
@@ -680 +684 @@
-- [ ] 瀏覽器工具仍無法啟動，畫面／下載／窄視窗未驗收；下一批評估邊緣預覽／保存、更多 seed／強度、depth／pose／adapter、專用局部編輯／羽化、FLUX 安裝容量及 RTX 4080。
+- [ ] 更多模型／seed／強度、depth／pose／adapter、專用局部編輯品質、FLUX 來源存取及 RTX 4080 待評估；邊緣預覽／保存、羽化與瀏覽器畫面／下載／窄視窗已於後續完成。
@@ -698 +702 @@
-- [ ] 瀏覽器工具 Node kernel 無法啟動，畫面操作／窄視窗仍待驗收；兩 seed／兩強度 RTX 3060 接續第三項。
+- [x] 當時瀏覽器工具無法啟動；2026-10-22 已補驗任務／作品原邊緣、實際下載 hash／還原與窄視窗；兩 seed／兩強度 RTX 3060 已於後續完成。
@@ -710 +714 @@
-- [ ] 瀏覽器畫面／窄視窗操作、未提交設定即時邊緣預覽、Pony v2／其他 LoRA、depth／pose／adapter、局部編輯品質改善、FLUX 安裝容量與 RTX 4080 接續評估。
+- [ ] Pony v2／其他 LoRA、depth／pose／adapter、局部編輯品質改善、FLUX 安裝容量與 RTX 4080 接續評估。
@@ -741 +745 @@
-- [ ] P5 固定 BFL 權重需先取得來源存取；P6 專用 inpainting 模型／其他半徑與 seed、depth／pose／adapter、Canny 未提交即時預覽及 RTX 4080 接續評估。
+- [ ] P5 固定 BFL 權重需先取得來源存取；P6 專用 inpainting 模型／其他半徑與 seed、depth／pose／adapter及 RTX 4080 接續評估；Canny 送出前 CPU 預覽已於後續完成。
@@ -757,0 +762,10 @@
+
+
+## Canny 預覽優先項目 3：RTX 3060／離線歷史驗收（2026-10-22）
+
+- [x] 四個新原生 Canny GPU 案例，比對相同處理後 PNG、閾值、fit／stretch；兩例完全相同，低閾值兩例 51／15 不同像素，如實記錄近似限制。
+- [x] 四個既有 v2 原任務 CPU 預覽與原邊緣像素相同；新增驗收 CLI，不補生成／不匯入，報告與 PNG 不可覆寫。
+- [x] 引擎離線／平台重啟後四份 GET-only 證據一致，原完整任務／作品不變；正式資料指紋未變。
+- [x] 瀏覽器任務／作品原邊緣、實際下載 hash、精確 seed 與參數還原、重啟後預覽與 390px 通過，關閉三條已滿足的歷史提醒。
+- [x] 五項驗收 CLI 與一項程序輸出邊界測試，510 項後端（509 通過、1 既有 skip）；前端檢查及建置通過。詳見 docs/validation/canny-preview-rtx3060.md。
+- [x] 本批三項各別驗證、commit／push 後接續下一項；8000／8001／8188／5173 測試服務停止。
````

</details>

<a id="commit-1d94774df60dcdaacc2a74129ecc916b02eb8528"></a>

### 19:58:33 · [1d94774](https://github.com/Zimkjdv/Model-Atelier/commit/1d94774df60dcdaacc2a74129ecc916b02eb8528) · chore: remove trailing whitespace from preview acceptance test

來源：[完整清單原檔](https://github.com/Zimkjdv/Model-Atelier/blob/1d94774df60dcdaacc2a74129ecc916b02eb8528/ROADMAP.MD)；檔名 `ROADMAP.MD`；Git blob `a54f85eedb11ee6b49681daccfe905a351d3b7a6`。

當時核取框：409，已勾選 369、未勾選 40。作者時間 `2026-10-22T19:58:33+08:00`；提交時間 `2026-10-22T19:58:33+08:00`。

本提交未改動開發清單，原檔與前一提交相同；修正內容見上方 commit。

<a id="commit-0fd7fd39846558e808d9308e2ac073518a41fcb6"></a>

### 20:05:48 · [0fd7fd3](https://github.com/Zimkjdv/Model-Atelier/commit/0fd7fd39846558e808d9308e2ac073518a41fcb6) · feat: freeze inference performance conditions at submission

來源：[完整清單原檔](https://github.com/Zimkjdv/Model-Atelier/blob/0fd7fd39846558e808d9308e2ac073518a41fcb6/ROADMAP.MD)；檔名 `ROADMAP.MD`；Git blob `60ef353ec7bc47ab2f64d1bc0208a32a6b5896ad`。

當時核取框：412，已勾選 373、未勾選 39。作者時間 `2026-10-22T20:05:48+08:00`；提交時間 `2026-10-22T20:05:48+08:00`。

<details>
<summary>完整清單差異（含項目、勾選與驗收變動）</summary>

````diff
--- ROADMAP.MD
+++ ROADMAP.MD
@@ -5,3 +5,3 @@
-核取框共 409 項，369 已完成、40 未完成；主清單 27、歷史提醒 13。本批補驗後關閉三條歷史提醒；P6 的其他結構／參考工作仍未完成。
-
-### 本批開始前的基準
+核取框共 412 項，373 已完成、39 未完成；主清單 26、歷史提醒 13。歷史提醒含重複與合併項目，不等同獨立功能數。
+
+### Canny 預覽批次開始前的基準
@@ -124 +124 @@
-- [ ] 效能紀錄包含模型版本、精度、解析度、步數、批次大小、附加元件、卸載方式與冷／熱啟動條件，避免無條件的秒數承諾。
+- [x] 效能紀錄保存模型／有序附加元件版本、解析度／batch／取樣設定及來源；明示精度／記憶體旗標與實際精度／卸載分開，冷／熱未可靠回報保持未知，固定 GPU 驗收另記實測條件；不作秒數承諾（2026-10-22，docs/execution-context.md）。
@@ -771,0 +772,7 @@
+
+
+## 效能條件優先項目 1：提交時快照（2026-10-22）
+
+- [x] 新任務／作品凍結推論尺寸、batch、取樣、精確 seed、模型／元件／有序 LoRA 版本；未知流程不猜測。
+- [x] 僅保存原引擎回報的允許旗標，隔離 token／路徑；設定不視為實際精度／卸載，冷熱狀態未知。
+- [x] 舊任務不回填、UUID 不重探測；六項新增測試與 Vue 型別／建置通過。
````

</details>

<a id="commit-4df715a4f6fe8461d5d53a982dc630089778ed54"></a>

### 20:15:10 · [4df715a](https://github.com/Zimkjdv/Model-Atelier/commit/4df715a4f6fe8461d5d53a982dc630089778ed54) · test: validate linked img2img denoise comparisons on RTX 3060

來源：[完整清單原檔](https://github.com/Zimkjdv/Model-Atelier/blob/4df715a4f6fe8461d5d53a982dc630089778ed54/ROADMAP.MD)；檔名 `ROADMAP.MD`；Git blob `98e5b5d3a27748f3ab53f3169f398c6bf8d36a49`。

當時核取框：416，已勾選 377、未勾選 39。作者時間 `2026-10-22T20:15:10+08:00`；提交時間 `2026-10-22T20:15:10+08:00`。

<details>
<summary>完整清單差異（含項目、勾選與驗收變動）</summary>

````diff
--- ROADMAP.MD
+++ ROADMAP.MD
@@ -5 +5 @@
-核取框共 412 項，373 已完成、39 未完成；主清單 26、歷史提醒 13。歷史提醒含重複與合併項目，不等同獨立功能數。
+核取框共 416 項，377 已完成、39 未完成；主清單 26、歷史提醒 13。歷史提醒含重複與合併項目，不等同獨立功能數。
@@ -586 +586 @@
-- [ ] 不同 denoise／模型的 GPU 品質與新 UI 實機驗收待進行；本輪沒有新增 GPU 任務或正式資料。局部編輯、結構／畫風 adapter 仍待整合。
+- [ ] 更廣泛 denoise／素材／模型品質、結構／畫風 adapter 待評估；2026-10-22 已完成 Pony／Animagine 各 0.3／0.6 圖生圖及比較關聯 GPU 驗收，瀏覽器結果介面接續報告匯出項目。
@@ -778,0 +779,8 @@
+
+
+## 圖生圖比較優先項目 2：固定 denoise 實機驗收（2026-10-22）
+
+- [x] 單次 CLI 固定兩模型／兩 denoise profile，原 UUID 不重送；完整權重驗檔、同來源與精確 seed、不可變方案關聯及新效能條件快照。
+- [x] RTX 3060 四任務／四作品成功，原圖／前處理／JSON／版本／hash／比較結果核對；仍未達紅木椅與房間提示，像素差值不當品質評分。
+- [x] 引擎離線／平台重啟四份 GET-only 與原完整任務不變；隔離 1 素材／2 方案／4 任務／4 作品，正式指紋不變。
+- [x] 五項新 CLI 測試、521 項後端（520 通過、1 既有 skip）；瀏覽器與結果報告接續第三項。見 docs/validation/image-comparison-rtx3060.md。
````

</details>

<a id="commit-17440f47e2a3f263fa4e3d28399cbb4312c7f571"></a>

### 20:29:42 · [17440f4](https://github.com/Zimkjdv/Model-Atelier/commit/17440f47e2a3f263fa4e3d28399cbb4312c7f571) · feat: export complete offline comparison result reports

來源：[完整清單原檔](https://github.com/Zimkjdv/Model-Atelier/blob/17440f47e2a3f263fa4e3d28399cbb4312c7f571/ROADMAP.MD)；檔名 `ROADMAP.MD`；Git blob `c3af10a4b7e9b2eb4ad748a1e88ba40d3ec3ff97`。

當時核取框：422，已勾選 383、未勾選 39。作者時間 `2026-10-22T20:29:42+08:00`；提交時間 `2026-10-22T20:29:42+08:00`。

<details>
<summary>完整清單差異（含項目、勾選與驗收變動）</summary>

````diff
--- ROADMAP.MD
+++ ROADMAP.MD
@@ -5 +5 @@
-核取框共 416 項，377 已完成、39 未完成；主清單 26、歷史提醒 13。歷史提醒含重複與合併項目，不等同獨立功能數。
+核取框共 422 項，383 已完成、39 未完成；主清單 26、歷史提醒 13。歷史提醒含重複與合併項目，不等同獨立功能數。
@@ -22 +22 @@
-本輪 P6 內側羽化三項完成：版本化後端、CPU 真實預覽工作台、Pony／Animagine 各兩半徑 RTX 3060 與離線重啟驗收；v1 原請求保留。494 項後端（493 通過、1 既有 skip）、前端檢查／建置與本輪瀏覽器操作通過。正式資料不變，測試服務停止。P5 磁碟已足夠，但 BFL 主模型／VAE 回傳 401 GatedRepo，本機無已授權 HF token，FLUX 仍待來源存取。
+最新三項完成：提交時效能條件快照、Pony／Animagine 各兩 denoise 圖生圖比較與離線重啟驗收、比較結果報告及瀏覽器下載／匯入／載入／390px／桌面雙欄驗收。530 項後端（529 通過、1 既有 skip）、前端邏輯／型別／建置通過。正式資料不變，測試服務停止。FLUX 固定 BFL 主模型／VAE 的來源存取仍待取得，RTX 4080 另機驗證待進行。
@@ -242,0 +243 @@
+- [x] 比較結果 JSON 報告：單一 SQLite 快照、完整方案／原流程／版本／量測及作品人工整理、來源與大小驗證、64 位元原 bytes 下載；離線瀏覽器驗收完成（2026-10-22）。
@@ -586 +587 @@
-- [ ] 更廣泛 denoise／素材／模型品質、結構／畫風 adapter 待評估；2026-10-22 已完成 Pony／Animagine 各 0.3／0.6 圖生圖及比較關聯 GPU 驗收，瀏覽器結果介面接續報告匯出項目。
+- [ ] 更廣泛 denoise／素材／模型品質、結構／畫風 adapter 待評估；2026-10-22 已完成 Pony／Animagine 各 0.3／0.6 圖生圖及比較關聯 GPU 驗收，瀏覽器結果介面與報告匯出亦已於第三項驗收。
@@ -596 +597 @@
-- [ ] UI 工具 sandbox 啟動失敗，本輪瀏覽器／原生下載／窄視窗驗收未完成。更多 GPU 品質、局部編輯／adapter、FLUX 安裝與 RTX 4080 仍待完成。
+- [ ] 更多素材／seed 品質、專用局部編輯／adapter、FLUX 來源存取與 RTX 4080 待完成；2026-10-22 已補驗比較方案下載／匯入、精確設定載入及 390px。
@@ -625 +626 @@
-- [ ] 瀏覽器工具仍因 Windows sandbox `helper_unknown_error` 無法啟動，畫面點擊、實際下載及窄視窗未驗收；其他畫風、更廣泛品質、局部編輯／adapter、FLUX 安裝及 RTX 4080 仍待完成。
+- [ ] 其他畫風、更廣泛品質、專用局部編輯／adapter、FLUX 來源存取及 RTX 4080 待完成；2026-10-22 已補驗比較關聯結果、原圖縮圖、報告實際下載與窄視窗。
@@ -786,0 +788,9 @@
+
+
+## 比較報告優先項目 3：結果匯出與介面驗收（2026-10-22）
+
+- [x] 同一 SQLite 快照匯出原方案、明確關聯任務／完整 graph／版本／量測及作品 hash／目前人工整理；未知不回填、不連線引擎。
+- [x] 完整關聯／流程與來源驗證，100 筆／8 MiB 超出明確拒絕；九項測試含並行更新一致性及歷史缺欄位／缺檔。
+- [x] 前端限量串流、來源／SHA256 驗證、原 bytes 精確 64 位元下載、過期回覆／Blob 清理；530 項後端（529 通過、1 既有 skip）、三組前端邏輯／Vue 建置通過。
+- [x] 真實瀏覽器結果報告／原方案下載與匯入、錯誤文件拒絕、variant 精確載入、效能條件顯示、來源切換／離開清理及 390px／桌面雙欄驗收通過。
+- [x] 隔離 1 素材／2 方案／4 任務／4 作品不變、正式指紋不變；本批三項各完成 commit／push 後接續，測試服務停止。見 docs/comparison-report.md。
````

</details>

<a id="latest-snapshot"></a>

<details>
<summary>最後來源完整閱讀版（歷史狀態，非現行待辦）</summary>

以下內容原樣摘錄歸檔前的清單，含 383 個已勾選框、39 個當時未勾選框及原有驗收。現行去重後的待辦以 ROADMAP 為準；原文中的相對路徑均以專案根目錄為基準。

<!-- roadmap-final-snapshot:start -->
# Model Atelier — Roadmap

## 目前待辦統計（2026-10-22，本批完成後）

核取框共 422 項，383 已完成、39 未完成；主清單 26、歷史提醒 13。歷史提醒含重複與合併項目，不等同獨立功能數。

### Canny 預覽批次開始前的基準

- 原始核取框：395 項，352 已完成、43 未完成。
- 主清單（P0–P8 與待確認事項）：27 項未完成；歷史增量紀錄：16 條未完成提醒。
- 歷史提醒常重複主清單、合併多個功能，亦有部分被後續驗收完成；43 不是獨立功能數。後續統計維持原始核取框與主／歷史分開，不直接以完成三個增量工作扣除三個大項。
- 本批依序：Canny 送出前 CPU 預覽 API、預覽工作台、RTX 3060 原邊緣與離線／瀏覽器驗收；各項驗證後 commit／push 才開始下一項。
- P5 固定 FLUX 來源存取仍待取得；RTX 4080 需於該機器驗證，兩者未列為完成。

> 個人 AI 圖像創作與實驗工作台
>
> A self-hosted web studio for anime illustration, reference-guided image creation, and reproducible multi-model experiments.

更新日期：2026-10-22
狀態：開發中；已交付範圍見下方開發進度，各階段其餘項目仍待實作與驗收。

最新三項完成：提交時效能條件快照、Pony／Animagine 各兩 denoise 圖生圖比較與離線重啟驗收、比較結果報告及瀏覽器下載／匯入／載入／390px／桌面雙欄驗收。530 項後端（529 通過、1 既有 skip）、前端邏輯／型別／建置通過。正式資料不變，測試服務停止。FLUX 固定 BFL 主模型／VAE 的來源存取仍待取得，RTX 4080 另機驗證待進行。

### 開發進度（更新至 2026-10-22）

- [x] 建立本地 Python `.venv`、Vue 3 + TypeScript 前端及 FastAPI 後端。
- [x] 完成系統資訊頁：平台主機 GPU、VRAM、RAM、資料磁碟、更新時間及錯誤狀態。
- [x] 完成 ComfyUI 位址保存、連線檢查及引擎回報資訊的獨立呈現。
- [x] 完成前端型別檢查與正式建置；後端設定保存、無 GPU 降級及未知顯存值測試通過。
- [x] 本地瀏覽器驗證硬體資訊與設定保存：RTX 3060 12GiB、約 64GiB RAM；初期 ComfyUI 尚未連線，後續已完成下方引擎與 Pony 實機驗收。
- [x] 完成模型庫第一階段：checkpoint 清單同步、搜尋與篩選、來源與備註保存、偏好模型選擇。
- [x] 模型紀錄依引擎位址分開保存；同步失敗保留快照，模型移除保留備註並標示未列出。
- [x] 七項後端測試與前端建置通過；瀏覽器驗證離線提示，另以隔離測試資料驗證搜尋、備註及偏好選擇。
- [x] 在 `runtime/ComfyUI` 安裝官方 ComfyUI 0.34.0 與獨立 `.venv`，提供 `start-comfyui.ps1`；runtime 不納入 Git。
- [x] RTX 3060 通過 PyTorch CUDA 運算與依賴檢查；真實 ComfyUI `/system_stats`、平台連線及空 checkpoint 清單同步成功。
- [x] 模型庫顯示 ComfyUI 服務回報版本與官方 GitHub 來源；checkpoint 另有版本登記欄位，未取得或未填版本顯示「未知」，不依檔名或 GitHub 最新版本推測。
- [x] 完成創作工作台草稿：提示詞、模型選擇、尺寸、seed、比例預覽、保存與重載、另存新草稿及未保存變更保護。
- [x] 草稿保存模型版本與引擎位址，seed 以字串保存避免精度損失；修訂號防止跨視窗覆寫，十項後端測試通過。
- [x] 瀏覽器驗證無模型時保存草稿、切換尺寸、未保存提示與重載；臨時測試草稿已清理。
- [x] 完成參考素材上傳、預覽、搜尋、命名及可還原封存；驗證真實圖片格式、檔案大小與像素數。
- [x] 草稿可保存最多八張參考素材關聯；被草稿引用的素材禁止封存，資料操作在同一 SQLite 交易檢查。
- [x] 十三項後端測試與前端建置通過；驗證實際上傳 API、瀏覽器預覽、封存還原及素材選取，臨時圖片已清理。
- [x] 完成作品「載入創作設定」API 與按鈕：保留原引擎、64 位元 seed、latent 輸入尺寸、正／負提示詞與取樣設定，載入為新草稿且不自動提交。
- [x] 作品載入保護工作台未保存變更；原引擎、模型清單與版本不符時顯示提示，不默默替換模型或版本。
- [x] 創作草稿支援負面提示詞、steps、CFG、sampler、scheduler、denoise 編輯、保存及提交；舊草稿新增欄位採相容預設值。
- [x] 不支援完整對應表單的工作流程回傳 422，不載入部分參數或覆寫目前內容；完整工作流程仍可下載。
- [x] 34 項後端測試、Vue 型別檢查／建置及作品載入的隔離瀏覽器驗證通過；確認原參數、未保存保護、保存新草稿、舊草稿預設值及再次提交的離線錯誤。
- [x] 參考素材用途與單張 checkpoint 圖生圖後端／介面：來源／前處理快照、原生 LoadImage 與 VAEEncode、獨立任務上傳、草稿及作品設定還原，以及 Pony／RTX 3060 實機驗證。checkpoint 局部編輯後端／遮罩工作台與 Pony／Animagine／RTX 3060 已完成固定驗證；Canny 結構後端／介面與固定 SDXL／RTX 3060 已整合，其他控制類型與 adapter 畫風／角色仍待整合。
- [x] 安裝作者固定修訂的 Pony V6 XL，完整大小與 SHA256 驗證；RTX 3060 真實模型同步、GPU 生成、作品匯入、即時節點進度、設定載入與重啟後離線讀取通過，詳見 `docs/validation/pony-v6-xl-rtx3060.md`。
- [x] 模型庫可登記檔案雜湊、大小、架構及授權資訊，新任務／作品保存當時快照；登記值不視為驗檔、授權或相容性證明，舊紀錄缺少快照保持未知。
- 第一階段僅在 LOCAL 端執行，平台 `.venv` 與 ComfyUI 環境分離。功能穩定後再評估 Docker 部署，不把 Docker 列為本機使用前置需求。
- [ ] 後續 Docker 評估涵蓋資料持久化、GPU 存取、主機硬體資訊來源及 ComfyUI 連線；不預設容器內資訊等於宿主機全部資訊。

## 1. 產品方向與實作原則

- 個人使用、自行部署的 Web 平台，整合一般二次元插畫創作與模型實驗。
- 優先整合可取得權重且符合使用條件的本地模型。
- 沒有公開權重、必須使用官方 API 的服務，統一放在最後階段。
- 公開權重不等於無使用限制；模型登記需保留來源及授權資訊。
- ComfyUI 是執行引擎；Pony、Animagine、FLUX 是模型候選；LoRA 是附加模型能力；各層分開管理。
- 依架構、功能及相容性分類模型，不使用內容尺度作為產品分類。
- 參考圖片用於引導創作，不承諾單張圖片能完全重現畫風或角色。
- 所有模型版本、支援能力及硬體需求，以正式接入時的官方資料與實測為準。

## 2. 實作順序

| 階段 | 範圍 | 備註 |
| --- | --- | --- |
| P0 | 確認環境與架構 | 先確認 GPU、儲存空間及部署位置 |
| P1 | 平台骨架與本地 ComfyUI | 打通提交、進度、結果保存 |
| P2 | Pony V6 XL | 第一個本地 SDXL 模型候選，接入前確認來源與授權 |
| P3 | Animagine XL 4.0 Opt | 固定來源安裝、RTX 3060 文生圖及切回 Pony 已驗證；其他硬體／負載另測 |
| P4 | 通用 LoRA 支援 | 先完成已接入架構的相容性管理 |
| P5 | FLUX.1 [schnell] 公開權重 | 預檢、分離元件庫、安全提交與專用表單已完成；權重安裝、GPU 生成與 LoRA 待驗證 |
| P6 | 參考圖工作流程與實驗管理 | 每套流程分別驗證模型與元件相容性 |
| P7 | 訓練與微調模組評估 | 與推論參數調整分開規劃 |
| P8 | 官方 API 服務 | NovelAI、Mango 2 等候選，先驗證正式接入方式 |

Mango 2 的確切提供者、權重可用性及 API 狀態尚未確認，暫留 P8 待查證，不視為已確定可接入。若確認有可用公開權重，再重新排入本地模型階段。

## 3. P0：環境與技術決策

- [x] 確認現有硬體：使用者有 RTX 3060 與 RTX 4080 兩台機器。
- [x] 確認開發順序：目前在 RTX 3060 主機開發並進行首輪驗證，之後在 RTX 4080 主機驗證。
- 實際 VRAM、RAM、磁碟與軟體環境由平台偵測，不根據顯卡名稱預先填入容量。
- [x] 平台偵測 GPU 型號、VRAM、RAM 與可用磁碟空間，已提供系統資訊頁。
- [x] 首輪 GPU 在本機執行；Web 平台與 ComfyUI 以不同環境及程序運行。
- [x] 首輪使用 Windows 原生推論環境。
- [x] 前端採 Vue 3 + TypeScript，已實作。
- [x] 後端採 Python + FastAPI；ComfyUI 負責模型執行，已實作。
- [x] 確認第一版優先支援 NVIDIA / CUDA 執行環境；具體相容範圍待驗證。
- [x] 初期資料採 SQLite + 本地檔案目錄。
- [x] 模型在 `runtime/ComfyUI`，素材／作品／縮圖與 SQLite 在 `data/`，README 說明備份。
- [x] 啟動腳本綁定 `127.0.0.1`；若開放區網或遠端，再加入驗證與連線保護。

驗收：部署方式、資料目錄和硬體限制已記錄，可據此選擇第一個執行流程。

### 技術選型理由

- 採用 Vue 3 + TypeScript 建立參數表單、模型切換、任務進度及作品管理介面；目前沒有必須使用 React 的需求。
- Vue 與 React 本身不決定美觀或易用程度，介面品質由版面、字體、配色、元件一致性及互動設計決定。
- Python + FastAPI 負責平台 API、資料管理與執行引擎串接；模型推論保留在 ComfyUI 的獨立環境。

### NVIDIA 支援範圍與資源限制

- 平台不以顯卡等級、型號白名單或固定 VRAM 門檻限制使用。瀏覽器端不要求 NVIDIA 顯卡，執行需求取決於連接的模型主機。
- 即使本機無可用 GPU，仍可開啟平台、管理素材與作品、編輯設定及設定遠端引擎；本機推論是否可用另行判斷。
- 第一版針對 NVIDIA / CUDA 開發，不承諾所有 NVIDIA 顯卡都能執行所有模型。
- GPU 世代、驅動、PyTorch、CUDA 及模型運算需求都會影響相容性；正式支援組合需記錄版本並實測。
- VRAM 影響工作負載能否容納，容量不足可能直接執行失敗，不能只解讀為速度較慢。
- 生成速度同時受 GPU 算力、記憶體頻寬、模型、解析度及生成設定影響，不能單靠 VRAM 大小推估。
- 生成與訓練分別評估；能生成圖片不代表能訓練或微調同一模型。
- CPU 卸載等降低顯存需求的方式，僅在工作流程支援且通過驗證時提供，並說明 RAM 與速度上的代價。
- [x] 檢查選定引擎的裝置與 PyTorch 版本，另提供固定本機 ComfyUI Python 的手動 CUDA／驅動檢查；不同來源分開，資料不可得時標示未知。
- [x] 建立模型與工作流程的相容性紀錄，區分已驗證、未驗證及已知不相容。
- [ ] 記錄生圖與訓練各自的實測資源需求，保留硬體、環境及測試設定，不提供未經驗證的效能保證。
- [x] 資源預估不足或尚未實測時提供提示，允許使用者嘗試；不因顯卡型號或估算 VRAM 單獨封鎖提交。
- [ ] 已確認無可用執行裝置、缺少必要元件或工作流程不相容時，只阻擋受影響任務並說明原因，不限制其他平台功能。
- [x] 已確認 CUDA OOM 時保存安全診斷及原設定，失敗任務可載入設定手動調整後建立新請求；不自動改動解析度、精度或模型，未知結果仍恢復原 ID。
- [x] RTX 3060 完成 Pony V6 XL 單張風景生成驗收，保存硬體、環境版本及完整工作流程設定；其他負載另測。
- [ ] 首輪通過後，在現有 RTX 4080 主機重跑相同的基本功能與工作流程，記錄相容性、資源用量及耗時差異。
- [ ] 先在兩台主機比較相同設定，再另行測試 RTX 4080 可承受的較高負載；後者不作為 RTX 3060 的基本驗收門檻。
- RTX 4090 不屬於目前持有硬體及必要驗收範圍；未實測的硬體不標示為已驗證。測試配置不作為顯卡白名單。
- [x] 效能紀錄保存模型／有序附加元件版本、解析度／batch／取樣設定及來源；明示精度／記憶體旗標與實際精度／卸載分開，冷／熱未可靠回報保持未知，固定 GPU 驗收另記實測條件；不作秒數承諾（2026-10-22，docs/execution-context.md）。

研究資料採用原則：不將「4080 固定 3–5 秒一張」「4090 所有模型最高畫質隨便跑」「掛載固定數量 LoRA 就不會 OOM」列為規格。FLUX 等模型的記憶體需求受完整流程與精度影響，24GB 也不代表所有元件可同時常駐 GPU。量化與 CPU 卸載是可評估的記憶體優化方式，GGUF 並非唯一方式；實際支援需逐流程驗證。

## 4. P1：平台骨架與 ComfyUI

- [x] 建立前後端專案與環境設定範例。
- [x] 建立創作工作台、模型庫、作品庫、系統資訊、設定頁的基本導覽。
- [x] 支援設定 ComfyUI 位址與連線健康檢查。
- [x] 平台後端封裝引擎連線，前端使用平台 API。
- [x] 標準 checkpoint 單張文生圖流程已在 Pony V6 XL 驗證，表單可編輯提示詞及取樣欄位。
- [x] 標準 checkpoint 文生圖提交前驗證必填值、平台／引擎取樣範圍及模型是否存在；其他模型架構另行驗證。
- [x] 提交任務並保存平台任務 ID 與引擎任務 ID 的對應。
- [x] 顯示排隊、執行、完成、失敗、取消確認中與取消結果待確認等狀態。
- [x] 接收原任務節點進度事件；斷線重連後查詢佇列／歷史，避免重複提交；RTX 3060 GPU 取樣進度已在瀏覽器確認。
- [x] 支援取消指定排隊任務；保留取消紀錄與結果確認，不清空佇列或停止執行中任務。
- [x] 執行中指定停止：受管理 ComfyUI 來源核對、原子取消能力與完整身分驗證，歷史確認中斷；RTX 3060 已驗證後續任務正常完成，其他版本及硬體另測。
- [x] 保存生成結果、縮圖、執行設定與錯誤資訊（已完成任務手動匯入作品庫）。
- [x] 標準單張文生圖作品可載入原設定為新草稿；已用 Pony GPU 作品驗證精確 seed、取樣設定及再次生成。
- [x] 提供 PowerShell 與 `start-all.bat` 啟動方式、Ctrl+C 停止方式與基本故障排查說明。

### 介面美觀與操作體驗

- [x] 將常用參數直接呈現，進階參數收合，保留使用者設定狀態。
- [x] 依登記架構顯示標準流程與模型起始預設，已知未支援架構說明原因並拒絕新提交；跨架構專用流程仍待實作。
- [x] 清楚呈現任務狀態、排隊取消與失敗診斷；已確認失敗任務可載入原設定手動調整後提交新任務，未知結果不自動重送。
- [x] 作品可一鍵載入支援流程的原設定，作為繼續創作的起點；保留未保存變更確認及來源版本提示。
- [x] 圖片並排比較與人工評分已於 P6 實作；窄視窗實際操作仍待驗收。
- [x] 統一字體、間距、配色、按鈕、表單及載入、空白、錯誤狀態的視覺規範；見 docs/ui-guidelines.md。
- [x] 建立適合桌面操作的工作台布局，較窄視窗可收合設定區，避免主要操作被擠出畫面。
- [x] 表單提供清楚標籤、鍵盤焦點及可讀對比；狀態不只用顏色區分。

介面驗收：使用者能完成選模型、輸入提示詞、調整常用設定、提交、查看狀態及載入作品設定；進階欄位不妨礙基本操作，錯誤與不相容原因能在介面直接理解。

### 系統資訊與硬體自動偵測

- [x] 由平台後端與選定 ComfyUI `/system_stats` 讀取各自硬體資料，不以瀏覽器電腦代表模型執行環境。
- [x] 逐裝置顯示引擎回報名稱、類型及索引；每個任務實際使用的 GPU 無法由此確認，保持未知。
- [x] 顯示引擎回報的 VRAM 總量、已用量與可用量，統一 GiB；CPU 裝置區分記憶體標籤。
- [x] 顯示模型執行主機回報 RAM 總量、已用量與可用量；無效數值保持未知。
- [x] 顯示模型、素材及輸出目錄所在磁碟的總容量與可用空間；同一磁碟不重複加總。
- [x] 分別顯示平台／引擎角色與來源；平台資料磁碟取自實際資料目錄，遠端磁碟未提供時顯示未知。
- [x] 系統資訊自動取得、每 15 秒與手動更新並附時間；本機 Python 檢查僅明確按鈕觸發。
- [x] 遠端介面未提供的 CUDA、驅動及磁碟資訊保持未知並說明原因，不以平台資訊代替或填零。
- [x] 無 GPU／CUDA 不可用／缺環境／逾時／離線分開顯示；平台舊資料與本機快照提示可能已過期，引擎失效時清除舊診斷。
- [x] 第一版以資訊顯示為主；單靠剩餘 VRAM 不保證模型可執行。

驗收：使用瀏覽器完成一次生成，結果與設定在平台重啟後仍可讀取；失敗任務有可理解的原因。系統資訊頁可自動顯示執行主機的硬體與儲存資訊，重新整理後更新數值；無法取得的欄位有明確狀態，遠端部署不會誤顯示為平台主機的硬體。

## 5. P2–P3：本地 SDXL 模型整合

- [x] 固定 Pony V6 XL 作者來源／修訂與 SHA256，記錄模型卡授權標記及依賴；完整授權條款仍待核對。
- [x] Animagine XL 4.0 Opt 固定作者修訂、大小及 SHA256，核對授權及標準流程依賴；完整安裝、RTX 3060 1024×1024 文生圖與離線作品驗收完成，詳見 `docs/validation/animagine-xl-4-0-opt-rtx3060.md`。
- [x] Animagine 固定來源安裝器與唯讀磁碟預檢，安全續傳、完整雜湊、安裝鎖與原子發布；2026-10-05 預檢磁碟已足夠，完成下載，沒有刪除其他模型。
- [x] 支援登記既有本地 checkpoint 目錄，不複製大型檔案；受管理 ComfyUI 需重啟後再同步，其他引擎不套用此設定。
- [x] 模型庫登記名稱、架構、版本、檔案大小、SHA256、來源與授權連結，並保存提交時快照。
- [x] 已提供 Pony V6 XL、SDXL 與 SD 1.x 的明確套用預設；SD 系列共用標準流程，跨架構工作流程另於 P5 實作。
- [x] 依流程能力顯示提示詞、seed、尺寸、步數等設定（目前標準 checkpoint 流程）。
- [x] 只顯示流程實際支援的進階欄位，保存原始參數；未接入架構保留唯讀原值。
- [x] 切換模型重新檢查登記架構與引擎能力，保留原值並明確提示；預設需確認套用，已知不適用架構拒絕新的標準提交。
- [x] 記錄 Pony V6 XL 單張 RTX 3060 生成耗時與設備顯存取樣；其他模型／負載未測量。
- [x] 保存模型遺失、載入失敗與 CUDA OOM 的安全診斷及處理建議，失敗任務可完整載入原設定；保留原流程與錯誤 JSON。

驗收：兩個模型都能完成生成；切換時能正確載入對應預設，作品可追溯到確切模型版本。

## 6. P4：LoRA 通用支援

- [x] 建立依引擎隔離的 LoRA 清單同步、搜尋與登記，包含來源、版本、基礎架構、大小、SHA256、授權及備註；離線保留成功快照。
- [x] 支援選擇、啟用及移除單一 LoRA，保存模型／CLIP 強度與啟用狀態至草稿。
- [x] 比較 checkpoint／LoRA 登記架構，顯示架構相容（未實測）、未驗證或已知不相容；不以檔名、版本推斷，清單失效時保守顯示。
- [x] 提交前阻擋已知不相容組合；單一 LoRA 八節點模板接入即時名稱、介面及強度交集檢查，提交前再次確認引擎與架構登記。
- [x] 單一 LoRA 實機驗證：Pony＋作者公開 LCM SDXL 在 RTX 3060 通過八節點生成、快照與重啟後離線保存；驗收工具及條件見 `docs/validation/pony-lcm-rtx3060.md`，不代表畫師效果或全部 LoRA 已驗證。
- [x] 第二個已接入模型組合：Animagine XL 4.0 Opt＋既有 LCM SDXL 在 RTX 3060 完成 1024×1024 八節點生成、完整快照與離線讀取，見 `docs/validation/animagine-lcm-rtx3060.md`；依兩份 hash 與設定匹配，沒有借用 Pony 實測。
- [x] 將 LoRA 實測條件接到模型庫、創作頁及資源提示；依兩份登記 hash／架構比對組合，強度與取樣參數另外比對，清單失效及未知條件保持未驗證，不限制 GPU 型號或改設定。
- [ ] 評估多個 LoRA 的組合支援及其他畫風 LoRA 的品質。
- [x] 有序多 LoRA 條件化紀錄接到創作頁及資源提示：比對原雜湊／架構／順序、強度及取樣設定，保留品質不足的觀察；不借用單一組合或反向順序。其他畫風與廣泛品質評估仍待進行。
- [x] Animagine＋公開黑白畫風與 LCM→畫風有序九節點，RTX 3060 一次提交、出圖、完整快照及離線還原；固定來源／未知授權如實保存，4 步品質偏淡，不能視為所有畫風驗收。
- [x] 最多四個不同 LoRA 有序串接、各別啟用／強度／排序、即時名稱與架構檢查、快照與完整還原；固定九節點 GPU 載入已驗證，更多組合及畫風品質仍待驗收。
- [x] 將 LoRA 版本及設定保存至生成紀錄：提交時凍結登記來源、版本、架構、SHA256、授權與兩種強度，作品沿用原快照；支援完整單一 LoRA 流程還原及版本差異提示，舊紀錄不回填。

驗收：支援的 LoRA 組合可載入與追溯；不相容組合不會直接送往 GPU 執行。

## 7. P5：FLUX.1 跨架構整合

- [x] 分離元件庫：依引擎原子同步主模型／兩個文字編碼器／VAE，保留未知版本及來源登記，離線不清除上次完整快照（2026-10-05）。

- [x] 選定 FLUX.1 [schnell] 原始 BF16 公開權重，固定作者修訂、大小、SHA256 與模型卡授權；來源有 Hugging Face 帳號／條件確認，平台不代為接受。
- [x] 記錄分離 VAE、CLIP-L、T5 FP8 scaled 的固定來源與版本，模型庫及 CLI 提供唯讀本機磁碟預檢；已有檔案仍需驗檔，不使用 SDXL 表單。
- [ ] 驗證實際推論精度、卸載、GPU／RAM 需求與各元件上游授權；來源選型不代表權重已安裝或可生成。
- [x] 建立 FLUX.1 [schnell] 獨立 9 節點流程、參數描述及安全提交 API；四元件不可變快照、獨立草稿及終止任務完整還原（2026-10-05）。
- [x] 接入專用創作頁、跨流程表單保留、元件版本與來源介面、精確 JSON 匯出及作品還原；GPU 未驗證（2026-10-05）。
- [ ] 驗證載入、生成、結果保存及記憶體不足時的處理。
- [ ] 對此架構的 LoRA 與參考圖功能逐項驗證，未驗證能力保持停用。

驗收：平台可在 SDXL 與選定的 FLUX 變體之間切換，各自具有正確的設定介面及依賴檢查。

## 8. P6：參考圖創作、作品庫與實驗比較

### 參考素材與流程

- [x] 上傳、預覽及管理參考圖片，檢查格式和尺寸。
- [x] 標示參考用途：視覺風格、角色外觀、構圖等；用途僅為整理標籤，不自動產生影像條件。
- [x] 建立每套工作流程的輸入需求與支援能力說明，未整合的參考能力明確停用。
- [ ] 逐項評估圖片生成圖片、局部編輯及結構參考流程；單張圖生圖與 checkpoint 局部編輯已完成後端／介面及固定 RTX 3060 驗證，Canny 結構已完成固定整合，其他結構流程與修補品質改善仍待完成。
- [x] 圖生圖保存參考圖、任務與作品的關聯，凍結前處理設定及版本；未支援流程不套用素材。
- [x] 檢查素材是否被草稿、任務或作品引用；封存於同一資料交易檢查，平台不提供永久刪除 API。

### 作品與實驗

- [x] 作品模型／收藏／狀態組合篩選、筆記搜尋、收藏、最多 10,000 字筆記及原圖／完整流程下載；修訂衝突保留未保存內容，見 `docs/artwork-library.md`。
- [x] 創作設定 JSON 匯出／匯入、來源快照、完整差異預覽與手動套用新草稿；歷史設定載入後，由使用者明確生成建立新任務，不重送原 ID。
- [x] 保存模型、LoRA、流程規格／完整 JSON hash、提交前引擎及平台依賴版本；未提供 CUDA／驅動／Git revision／節點版本保持未知，舊紀錄不回填。
- [x] 最多四張作品原圖並排、生成參數差異及四項人工評分；共用修訂檢查及未保存保護，舊紀錄只讀預設，不改原圖片／快照。
- [x] 固定一般插畫測試集：Pony V6 XL／Animagine 4.0 Opt 各四案例，共同參數／seed、原圖與角色雙場景觀察、快照及離線驗證完成；不是最佳預設或全面品質排名。
- [ ] 更多 seed、模型及作者提示格式的品質比較；其他畫風、參考引導／角色鎖定仍待驗證。
- [x] 固定一般插畫測試集 v1：四個案例、成年旅人雙場景、明確評估要點、版本／檔案 hash；可用於方案預覽；兩個已安裝模型的固定四案例已完成 GPU 比較，廣泛品質評估仍待進行。
- [x] 有限範圍參數比較：checkpoint 文生圖／單張圖生圖 Steps／CFG／字串 Seed／指定 LoRA 模型或 CLIP 強度，圖生圖另有 denoise 單一軸，最多八次單張預覽、完整快照與 JSON 匯出；逐組載入後手動生成，不自動批次或重試。
- [x] 完整比較方案本機保存、重載、凍結案例與 JSON 匯入預覽；冪等保存、修訂式封存／還原、來源素材引用保護；載入設定與生成仍需明確操作。
- [x] 已保存方案逐組手動載入及生成，任務／作品保存原關聯快照；結果區按變體查看任務、縮圖與原圖，舊資料不推測或回填。
- [x] 比較結果 JSON 報告：單一 SQLite 快照、完整方案／原流程／版本／量測及作品人工整理、來源與大小驗證、64 位元原 bytes 下載；離線瀏覽器驗收完成（2026-10-22）。
- [ ] 更多模型／流程／參數軸待規劃，不提供自動批次與品質評分。
- [x] 新任務保存平台觀察耗時、原引擎歷史起訖及提交前資源快照；作品沿用，未知值不推估或回填。連續／任務專用峰值仍待實作。

驗收：任一結果都能追溯輸入、參數、模型和流程；比較任務可追溯各自差異。重現表示設定可恢復，不保證跨硬體或環境逐像素一致。

## 9. P7：訓練與微調模組評估

- [ ] 確認是否有超出推論參數調整的實際訓練需求。
- [ ] 評估資料集管理、標註、版本及訓練工具介面。
- [ ] 規劃獨立環境與 GPU 資源協調，避免與生成任務互相干擾。
- [ ] 規劃訓練產物回登模型庫及評估流程。

此階段不屬於第一版，也不預先承諾支援所有模型的訓練。

## 10. P8：官方 API 服務，最後實作

- [ ] NovelAI：確認官方 API、驗證方式、使用條件、費用及可接入功能。
- [ ] Mango 2：先確認確切模型與提供者，再核對公開權重或官方 API。
- [ ] 只有已確認正式接入方式的服務才列入實作，不假設網站功能等於 API 功能。
- [ ] 建立服務介面，分離本地模型與遠端服務的能力描述。
- [ ] 憑證只保存在後端，不寫入前端或版本控制。
- [ ] 提交前顯示資料將送往的服務及已知費用資訊。
- [ ] 處理限流、逾時、扣費狀態及重試，避免重複付費提交。
- [ ] 依服務支援範圍保存結果及請求設定。

驗收：服務來源與接入條件明確；不支援的功能不顯示為可用；錯誤或重試不會造成不可追蹤的重複請求。

## 11. 第一版邊界

第一版交付 P0、P1 與 P2：ComfyUI + 一個本地模型 + 生成介面 + 任務狀態 + 作品與參數保存 + 系統資訊與硬體自動偵測。

暫不包含：

- 公開社群、分享廣場、多租戶及付費系統。
- 自製節點編輯器。
- 官方 API 服務。
- 模型訓練、一鍵安裝全部模型、自動安裝任意第三方節點。
- 對畫風完全一致、角色完全一致或所有模型互通的保證。

## 12. 待確認事項

- [x] 現有主機與驗證順序已確認：RTX 3060 先開發與驗證，RTX 4080 後續驗證；兩台實際環境資訊待自動偵測。
- [x] 確認硬體資訊由平台自動偵測並顯示，功能實作列於 P1；不要求使用者手動填寫。
- [ ] 推論跑本機或遠端 GPU；是否需要區網存取。
- [x] ComfyUI 已安裝於 `runtime/ComfyUI`；Pony V6 XL 已下載且通過完整 SHA256 與 RTX 3060 生成驗收。
- [x] 第一個模型採 Pony V6 XL，固定來源、修訂與實測紀錄見本輪優先項目 1。
- [x] Animagine XL 選定 4.0 Opt，固定來源見選型紀錄。
- [x] FLUX.1 首輪選定 [schnell] 原始 BF16 主模型，分離 VAE／CLIP-L／T5 FP8 scaled；安裝與專用 GPU 流程仍待執行。
- [ ] Mango 2 的官方來源。

## 13. 官方查核入口

- [ComfyUI 系統需求](https://docs.comfy.org/installation/system_requirements)
- [Diffusers 記憶體優化](https://huggingface.co/docs/diffusers/optimization/memory)
- [Diffusers FLUX 流程與記憶體需求](https://github.com/huggingface/diffusers/blob/main/docs/source/en/api/pipelines/flux.md)
- [ComfyUI 伺服器 API](https://docs.comfy.org/development/comfyui-server/comms_routes)
- [Animagine XL 4.0 模型卡](https://huggingface.co/cagliostrolab/animagine-xl-4.0)（版本候選，不代表已選定）
- [FLUX.1 Kontext Dev 模型卡](https://huggingface.co/black-forest-labs/FLUX.1-Kontext-dev)（用於釐清公開權重與 API 版本差異，不代表已選定）

其他候選模型與服務的官方來源於接入前補齊。


## 本次增量：工作流程提交層

- [x] 標準 checkpoint 文生圖提交 API 與創作頁生成按鈕。
- [x] SQLite 任務紀錄、完整 API 工作流程 JSON 保存及下載。
- [x] 請求 UUID 去重，提交結果不明不自動重送。
- [x] 原引擎佇列／歷史查詢，保存成功／失敗歷史及節點錯誤。
- [x] 缺少 checkpoint、引擎離線、模型清單異常的明確錯誤。
- [x] 19 項後端測試、前端建置、真實引擎空模型及離線驗證。
- [x] Pony V6 XL 已完成成功生成及 VRAM／耗時取樣，見實機驗收紀錄。
- [x] 輸出圖片匯入平台作品庫、預覽與完整資料目錄備份說明。
- [ ] 參考圖、LoRA、FLUX 各自的相容工作流程。

## 本次增量：作品庫

- [x] 成功任務 SaveImage 輸出匯入、原圖與縮圖本機保存。
- [x] 依任務與輸出識別去重；部分下載失敗可再次匯入補齊。
- [x] 作品搜尋、大圖預覽、原圖與完整工作流程下載。
- [x] 正／負提示詞、精確 seed、取樣參數與模型版本快照；無版本紀錄顯示未知。
- [x] 原引擎離線、來源或本機檔案遺失、無效圖片與磁碟寫入錯誤提示。
- [x] 26 項後端測試、前端建置、隔離瀏覽器匯入測試及真實 ComfyUI 圖片讀取測試。
- [x] Pony V6 XL 已完成「生成 → 完成 → 匯入作品」完整實機流程。
- [x] 作品收藏、筆記與封存／還原，保留原圖、參數及版本快照；沒有永久刪除。

## 本次增量：作品載入創作設定（2026-10-02）

- [x] 作品卡片及預覽提供「載入創作設定」，只讀本機快照，不啟動生成任務。
- [x] 從完整標準工作流程解析原引擎、checkpoint、正／負提示詞、精確 seed、latent 尺寸與取樣設定。
- [x] 載入為新草稿；保護目前未保存內容，保留舊草稿、作品與未確認提交請求。
- [x] 原模型版本、引擎不符及模型清單狀態提示；未知版本仍顯示未知。
- [x] 負面提示詞、steps、CFG、sampler、scheduler、denoise 可編輯、保存與提交，舊草稿使用相容預設值。
- [x] 無法完整還原的自訂流程、額外分支或批次回傳 422，可下載原始 JSON；不默默遺漏設定。
- [x] Vue 型別檢查及正式建置通過。
- [x] 34 項後端測試及隔離瀏覽器驗證通過；載入／保存不新增生成任務，再次提交保留完整參數並明確顯示離線失敗。隔離服務與資料已清理。
- [x] 已完成 Pony V6 XL 與 Animagine XL 4.0 Opt 的 RTX 3060 GPU 出圖與離線作品／設定保存驗收；FLUX 與其他硬體未驗證。

## 優先項目 1：安全取消排隊任務（2026-10-02）

- [x] 提供任務取消 API 與操作入口，只移除原引擎中身分相符的排隊項目。
- [x] 以佇列與歷史確認結果，保留工作流程、模型版本與取消紀錄；結果不明時不自動重新提交。
- [x] 任務已開始執行時拒絕排隊刪除；其他排隊與執行中的任務不受影響。
- [x] 修訂號與取消租約防止並行回應覆蓋新狀態，原 prompt ID 不因其他任務的中繼資料被改寫。
- [x] 51 項後端測試、Vue 型別檢查／建置通過；隔離瀏覽器驗證確認取消指定任務、保留其他排隊／執行項目與完整工作流程。測試服務與資料已清理。

## 優先項目 2：即時進度與斷線恢復（2026-10-02）

- [x] 原引擎 WebSocket → 平台 SSE → 創作頁節點進度，精確核對 prompt ID 與工作流程節點。
- [x] 同任務共用上游連線，跨程序監聽租約、訂閱上限、訊息及寫入頻率限制。
- [x] 有限重連及低頻查詢；完成／失敗需歷史確認，保留最後進度與更新時間，不自動重新提交。
- [x] 取消確認與終止狀態不被進度覆寫；離開創作頁、隱藏分頁及 HTTP 中斷清理連線。
- [x] 啟動腳本加入優雅關閉等待上限；更新 requirements 與鎖定版本。
- [x] 69 項後端測試、Vue 型別檢查／建置與依賴檢查通過；隔離瀏覽器驗證進度、重連、完成及監聽清理。

## 優先項目 3：動態取樣選項與提交前相容驗證（2026-10-02）

- [x] 從目前 ComfyUI KSampler 同步 sampler／scheduler 及 steps、CFG、denoise 範圍，按引擎保存快照與同步時間。
- [x] 創作頁提供實際選項、範圍交集及離線／未知／不相容提示；保留草稿及作品原值，不默默重設選項或截短數值。
- [x] 新生成及直接工作流程提交重新讀取能力，所有 KSampler 參數及原引擎確認後才送出；不以過期快照授權生成。
- [x] 精確 request ID 恢復仍回原任務，不重新查能力或重送；直接工作流程也限制精確 seed、平台 latent 尺寸及 batch 1。
- [x] RTX 3060 上真實 ComfyUI 0.34.0 同步成功：45 種 sampler、9 種 scheduler；checkpoint 清單仍為空，未進行 GPU 推論。
- [x] 84 項後端測試、Vue 型別檢查／建置與依賴檢查通過；隔離瀏覽器驗證選項更新、提交前拒絕、原值保存、精確參數及離線快照。測試服務與資料已清理。

## 本輪優先項目 1：Pony 安裝與 P1 實機驗收（2026-10-02）

- [x] 作者固定修訂 manifest、完整檔案大小與 SHA256、續傳／原子發布／安裝互斥；runtime 權重不納入 Git。
- [x] 只提交一次的 NVIDIA GPU 驗收 CLI；保存原 UUID、完整 workflow、精確 seed、耗時範圍與顯存取樣，查詢錯誤不自動重送。
- [x] RTX 3060 真實生成、作品保存、介面節點進度與載入設定通過。
- [x] 停止引擎與平台後，只重啟平台，原圖、模型版本、精確參數與流程可離線讀取並與原報告比對。
- [x] 116 項後端測試、Vue 型別檢查／建置及依賴檢查通過（1 項 Windows symlink 權限跳過），保存實機驗收紀錄 `docs/validation/pony-v6-xl-rtx3060.md`。

## 本輪優先項目 2：模型資料與歷史快照（2026-10-02）

- [x] 模型庫新增架構、大小、完整 SHA256、授權名稱／網址及更新時間，使用者登記與已驗證資訊明確區分。
- [x] 提交保存模型資料快照，作品從原任務複製；修改模型庫、重新匯入及原 ID 恢復不改寫既有快照。
- [x] 舊紀錄缺少資料時顯示未知，不從目前模型庫回填；作品圖片 hash 與模型檔案 hash 分開。
- [x] 同步及離線保留資料，metadata／清單／偏好以 SQLite 原子操作避免覆寫。
- [x] 129 項後端測試（1 項既有 Windows 權限跳過）、Vue 型別檢查／建置通過；真實 Pony 登記與隔離瀏覽器快照、原 ID 恢復、重複匯入及舊作品未知驗收通過。

## 本輪優先項目 3：模型預設與架構相容檢查（2026-10-02）

- [x] 只讀模型 profile API：Pony 依登記 SDXL＋完整固定 hash 匹配，SDXL／SD 1.x 起始預設明註未逐模型驗證，未知不推測。
- [x] 創作頁顯示預設差異與明確確認，只修改七項取樣／尺寸參數；切換模型、載入草稿與作品保留原內容。
- [x] 新表單生成與直接工作流程提交均阻擋已登記 FLUX／SD 3.x／其他不支援架構，保存失敗任務且不發送 prompt。
- [x] 驗證期間重新檢查架構；仍適用標準流程的變更不改原參數或快照，原 ID 恢復不重新查模型或提交。
- [x] 140 項後端測試通過（1 項既有 Windows 權限跳過）、Vue 型別檢查／建置通過；瀏覽器驗證預設確認／取消、切換、同模型草稿與作品還原，隔離 API 驗證兩個入口阻擋且不送 prompt、自訂參數與完整 seed 保留。RTX 4080 仍待實機驗證。
- [x] 驗收服務停止、隔離資料清理，8000／8188／5173／8001 均未監聽；真實模型與作品保留。

## 後續優先項目 1：失敗診斷與原設定恢復（2026-10-02）

- [x] 區分模型遺失、載入失敗、CUDA 顯存不足及其他提交／執行錯誤，依原歷史與節點身分分類，不把未知錯誤猜成 OOM。
- [x] 任務 API 與即時摘要提供安全說明及建議，完整上游歷史／錯誤保存於 JSON，介面不展開原始 traceback。
- [x] 僅已確認失敗任務可完整還原標準流程為新草稿，保留精確 seed、原版本、模型快照與取樣值，並保護未保存內容。
- [x] 載入不提交、原 ID 恢復不重送；手動調整後明確生成才建立新請求，舊任務保持不變。
- [x] 153 項後端測試（1 項既有 Windows 權限跳過）與 Vue 建置通過；隔離瀏覽器驗證診斷、精確 seed、原版本、未保存保護及一次明確新提交。錯誤使用模擬引擎，未刻意造成真實 OOM；服務與隔離資料已清理。

## 後續優先項目 2：既有本地模型目錄（2026-10-03）

- [x] 設定頁登記最多八個本機絕對 checkpoint 目錄，保存順序、修訂衝突及可讀／容量未知提示，不搬移或刪除模型。
- [x] 純標準庫匯出工具產生固定 runtime 設定，原子寫入並限制路徑；啟動腳本檢查匯出結果，失敗時停止，不沿用舊設定。
- [x] ComfyUI 原搜尋範圍保留，額外路徑只套用受管理本機啟動；遠端引擎不宣稱已套用，保存後提示重啟與同步。
- [x] 170 項後端測試（1 項既有 Windows 權限跳過）及 Vue 建置通過，含實際 PowerShell 空白路徑參數與匯出失敗保護測試。
- [x] 真實 ComfyUI 驗證登記／移除後重啟、原 Pony 保留；瀏覽器驗證衝突與重新讀取。測試檔僅用於列舉，未做新推論；測試檔清理、服務停止。

## 後續優先項目 3：來源明確的環境診斷（2026-10-03）

- [x] 選定引擎診斷 API、版本與裝置／RAM／VRAM 數值正規化，附來源及時間；不從 PyTorch 後綴推測 CUDA 或以平台硬體補遠端資訊。
- [x] 固定本機 ComfyUI Python 的明確手動檢查，包含 PyTorch、CUDA 建置版本／可用性、裝置屬性與本機 nvidia-smi 驅動；無模型載入或生成。
- [x] GET 只讀程序內快照，POST 拒絕自訂命令／參數；並行檢查 409、20 秒逾時停止／回收子程序，HTTP 中止不提前解除執行鎖。
- [x] 引擎設定切換後舊回應不覆蓋新來源，另一視窗切換使診斷失效、裝置清空，介面保留輸入並提示確認。
- [x] 190 項後端測試通過（1 項既有 Windows 權限跳過）、Vue 型別檢查／建置及唯讀審查通過。
- [x] RTX 3060 真實環境檢查及 ComfyUI 0.34.0 回報通過；隔離 API／瀏覽器驗證同名多 GPU、無效容量、CPU 標籤、離線與引擎切換。不新增生成任務，正式資料不變；服務停止、隔離資料清理，RTX 4080 仍待實機驗證。

## 本輪優先項目 1：條件化流程驗證紀錄（2026-10-03）

- [x] 模型庫與創作頁顯示 SHA256／架構匹配的實測條件、來源、環境、精度、卸載、耗時與設備顯存取樣。
- [x] 無匹配證據顯示尚未驗證；不以名稱推定相容，也不把登記紀錄當成目前檔案驗證。
- [x] 194 項後端測試通過（1 項既有 Windows symlink 權限跳過），Vue 型別檢查與建置通過，實際模型庫顯示確認。修正 PowerShell 測試輸出遇系統編碼時的解碼例外。
- [ ] 訓練及 RTX 4080 的實測資源紀錄仍待驗證。

## 本輪優先項目 2：創作資源與未驗證條件提示（2026-10-03）

- [x] 提供唯讀資源提示 API 與創作頁入口，保留未知顯存需求，不以歷史取樣當作最低需求。
- [x] 參數差異、沒有實測紀錄、離線與過期回應均有明確處理；不修改生成參數或增加 GPU／VRAM 提交限制。
- [x] 199 項後端測試通過（1 項既有權限跳過），含零可用顯存、離線、未知模型、來源變更及無資料寫入；Vue 型別及建置通過。

## 本輪優先項目 3：本機目錄與磁碟容量（2026-10-03）

- [x] 系統頁列出模型、素材、作品及受管理 ComfyUI 輸出目錄，按實際磁碟區去重統計；不存在／不可讀／未知容量保留明確狀態。
- [x] 額外目錄設定損壞不影響固定目錄查詢，部分總計不假裝完整；遠端引擎不套用本機磁碟資訊。
- [x] 206 項後端測試通過（1 項既有 Windows 權限跳過），Vue 型別與建置通過；實機五個目錄均落於 C 磁碟區，畫面僅加總一次。完成新提示面板的深色主題一致性調整。

## 檢查修正後優先項目 1：必要節點提交前檢查（2026-10-03）

- [x] 針對本次流程的標準節點查詢即時定義；缺少／格式無效／服務失敗均不送出 GPU 任務，保留明確錯誤及失敗紀錄。
- [x] 節點去重並行查詢，舊請求恢復不重送；209 項後端測試通過（1 項既有權限跳過）。
- [ ] 無可用裝置需引擎提供可靠證據，不能只憑空裝置清單推定；P0 此部分保持待驗證。

## 檢查修正後優先項目 2：常用參數與介面偏好（2026-10-03）

- [x] Steps／CFG 與尺寸直接顯示，其餘進階參數收合；保存進階區與素材區展開偏好，與草稿參數分離。
- [x] Vue 型別／正式建置通過，瀏覽器驗證展開進階區後重新載入仍保留，Seed 等原參數不變；未新增草稿或生成。

## 檢查修正後優先項目 3：窄視窗工作台與鍵盤操作（2026-10-03）

- [x] 創作設定可收合，任務區擴展；保留原表單與未保存變更，窄視窗顯示當前參數摘要。
- [x] 導覽補上文字名稱／提示／目前頁面語意、主內容跳轉及一致 focus-visible 樣式。
- [x] 前端型別與正式建置通過；680px／390px 無橫向溢出，鍵盤 Enter 收合與再展開保留內容，跳轉主內容後焦點正確。未建立測試草稿或生成任務。
- 全站視覺規範及所有頁面的無障礙驗收仍可繼續完善，本項驗證以創作工作台與主要導覽為範圍。

## 本輪優先項目 1：共用視覺規範（2026-10-03）

- [x] 建立 theme.css 共用色彩／表單／焦點／提示狀態，主要資料頁引用相同輸入色彩，區分一般通知與警告。
- [x] 記錄 docs/ui-guidelines.md；Vue 型別與建置、設定頁畫面檢查通過。

## 本輪優先項目 2：表單可讀性與操作回饋（2026-10-03）

- [x] 素材、作品讀取狀態及模型／作品／素材搜尋結果以 status 呈現；重複卡片操作包含對應名稱。
- [x] 素材上傳限制、模型 SHA256 格式及目錄限制與輸入欄位建立 describedby 關聯；沿用原生 label 與共用焦點／對比樣式。
- [x] 型別與建置通過，實際鍵盤 Enter 開啟作品、Escape 關閉並返回原按鈕通過；不改寫作品或模型資料。

## 本輪優先項目 3：依流程能力呈現欄位（2026-10-03）

- [x] 模型 profile 提供版本化 workflow 描述與明確欄位；前端驗證描述，僅啟用已接入的標準流程表單。
- [x] 不支援架構保留可查看／保存的原參數，切回 SDXL 恢復原值，不自動套用預設。
- [x] 212 項後端測試（211 通過、1 項既有權限跳過）、前端型別及建置通過。8001 隔離資料實際驗證 FLUX 保留 31 steps、保存草稿及切回 SDXL 恢復欄位；正式資料未修改。

## 本輪優先項目 1：參考素材用途與引用保護（2026-10-05）

- 用途保存／篩選、修訂衝突、正規化來源與版本紀錄；舊素材未知值不回填。
- 參考流程能力 API 區分圖生圖、局部編輯、結構及風格參考；任務與作品引用素材禁止封存。
- 324 項後端測試（323 通過、1 項既有跳過）、Vue 建置與隔離瀏覽器用途保存／篩選驗收通過。


## 本輪優先項目 2：安全的 checkpoint 圖生圖後端（2026-10-05）

- 一張平台素材、等比補白／拉伸、LoadImage → VAEEncode、精確 seed、有序 LoRA 路徑；完整 JSON 與不可回填的來源快照。
- 驗證後才上傳原引擎獨立目錄；UUID 恢復不重新上傳／提交，未知生成結果只查詢。
- 339 項後端測試（338 通過、1 項既有跳過）；真實 Pony／RTX 3060 成功生成 512×512、輸入 SHA256、作品匯入、離線設定還原與引用保護通過。
- UI 下一項接入；其他模型、參考圖加 LoRA 及品質仍待實機測試。


## 本輪優先項目 3：圖生圖創作介面與來源追溯（2026-10-05）

- Checkpoint 文生圖／圖生圖切換、單張來源選擇、等比補白／拉伸預覽、改動幅度及精確 seed；草稿重載、未保存保護、任務／作品還原不自動生成。
- 任務及作品顯示素材與前處理快照；圖生圖不沿用文生圖預設與品質驗證結論。
- Vue 型別／正式建置通過；瀏覽器驗證 0.123 denoise 保存、390px 無溢出、真實 GPU 生成與匯入；關閉引擎後離線警示正確且原參數保留。
- 每項測試後分別 commit、push；本輪正式資料維持原 5 個任務與 3 件作品，隔離驗收資料保留。

## 本輪優先項目 1：Animagine 固定權重與真實 GPU 整合（2026-10-05）

- [x] 6.46 GiB checkpoint 完整大小／SHA256 核對、版本 `4.0 Opt` 登記，不改正式偏好（仍未選定）；隔離測試資料選用 Animagine，專用驗收 CLI 使用原 UUID 與精確 seed，無重送。
- [x] RTX 3060 兩次 1024×1024 風景、同引擎切回 Pony、作品快照與重啟平台後離線 GET 驗證通過；條件登記接入模型庫／資源提示，其他環境保持未驗證。
- [x] 344 項後端測試（343 通過、1 項既有權限跳過）、Vue 型別／正式建置通過。一次既有跨程序報告鎖測試偶發失敗後，單項及完整重跑通過。

## 本輪優先項目 2：Animagine／LCM LoRA 組合（2026-10-05）

- [x] 專用固定參數驗收 CLI，共用一次提交與離線完整快照檢查；Pony CLI 維持原設定。
- [x] RTX 3060 成功生成 1024×1024 一般風景，model strength 1、CLIP strength 0、4 steps、CFG 1、lcm／sgm_uniform；八節點、精確 seed、原圖 hash、模型／LoRA 快照與重啟後離線還原通過。
- [x] 組合證據接入既有模型庫、創作頁與資源提示；解析度／強度／取樣設定改變時不匹配，未推定多 LoRA 或畫風品質。
- [x] 347 項後端測試（346 通過、1 項既有權限跳過），Vue 型別／正式建置通過。

## 本輪優先項目 3：作品庫管理（2026-10-05）

- [x] 收藏、筆記、封存／還原、模型／狀態／收藏組合篩選及筆記搜尋；交易修訂檢查，409 保留表單，不自動覆蓋或重送。
- [x] 舊作品唯讀預設、原圖／workflow／模型快照不變、封存作品仍保護素材引用，重複匯入不重設管理資料。
- [x] 354 項後端測試（353 通過、1 項既有 Windows 權限跳過）、Vue 型別／建置、兩個視窗衝突及桌面瀏覽器驗收通過；viewport override 實際未生效，390px 本轮保持未驗收。
- [x] 正式 5 任務／3 作品／0 草稿不變，隔離四件作品及管理資料保留；服務停止後分項 commit、push。

## 本輪優先項目 1：公開畫風與多 LoRA GPU 驗證（2026-10-05）

- [x] 固定作者 revision、185,697,368 bytes 與完整 SHA256，通用安裝器明確分流 LoRA 目錄；版本以 revision 表示，授權 `other` 保留未知。
- [x] 三組相同 prompt／seed：無 LoRA、單一畫風、LCM→畫風；7／8／9 節點全部 GPU 生成、作品保存及引擎停止後 GET 核對通過，正式生成資料不變。
- [x] 人工檢查如實記錄 4 步組合偏淡，不推薦為品質預設；357 項後端測試及 Vue 型別／建置通過，詳見 docs/validation/animagine-multi-lora-rtx3060.md。

## 本輪優先項目 2：提交時引擎與依賴版本（2026-10-05）

- [x] Checkpoint／圖生圖／FLUX 提交前最多兩秒觀察，原引擎與平台來源分開；交易凍結、修訂衝突、未知值、UUID 不重查及舊紀錄不回填。
- [x] 作品复制原任務版本，預覽與歷史設定還原顯示快照；RTX 3060 真實 Animagine／LCM 任務、作品及平台重啟後離線核對通過。
- [x] 修正 Windows 並行目錄建立造成 `Path.resolve` 等價前綴誤拒絕，保留目錄限制及一次提交；新增決定性回歸測試並回收測試子程序。
- [x] 365 項後端測試（364 通過、1 項既有權限跳過）、Vue 型別／建置與桌面瀏覽器版本顯示通過。

## 本輪優先項目 3：創作設定匯出與匯入（2026-10-05）

- [x] 三種流程版本化 JSON、字串 seed、有序 LoRA／圖生圖／FLUX 參數；作品與終止任務可匯出原來源快照及精確 workflow 字串。
- [x] 256 KiB、完整欄位與參數、來源未核實、跨架構拒絕、重複欄位／非有限數字／注入拒絕；匯入 API 只讀，不保存、不連線、不生成。
- [x] 選檔／貼上、差異預覽、未保存提示、取消與預覽失效、明確套用新草稿；Vue 代理物件複製錯誤修正後，兩份 checkpoint 草稿與一份 FLUX 草稿的隔離保存通過，正式資料不變。
- [x] 370 項後端測試（369 通過、1 項既有權限跳過）、Vue 型別／建置及桌面 UI 驗收通過；IAB Blob 下載事件未回報，僅確認 API bytes、下載連結及完整 JSON，其他瀏覽器下載與 390px 待驗收。

## 本輪優先項目 1：有序 LoRA 歷史條件與品質觀察（2026-10-05）

- [x] 唯讀組合 API 與創作頁：hash／架構／順序匹配歷史載入紀錄，強度與完整取樣條件另外比對；資料異動 409，未知或失效不借用其他組合。
- [x] 資源提示共用有序比對，保留 4 步結果偏淡的觀察；沒有品質通過旗標、顯卡限制或 VRAM 推估。
- [x] 374 項後端測試（373 通過、1 項既有權限跳過）、Vue 型別／建置及桌面順序變更驗收通過。完成後 commit `8a76fe8` 並 push，再進行下一項。

## 本輪優先項目 2：作品並排與人工評分（2026-10-05）

- [x] 最多四張完整原圖、差異表、精確 seed 與有序 LoRA；篩選不清除比較選擇，完整其他快照仍由作品預覽查看。
- [x] 四項 1–5／null 人工分數共用修訂檢查；無效輸入與衝突拒絕，未保存內容保留，原圖／workflow／模型及環境快照不變。
- [x] 377 項後端測試（376 通過、1 項既有權限跳過）、Vue 型別／建置及桌面 UI 通過；隔離圖的視覺風格觀察為 1/5。完成後 commit `a21b41e` 並 push，再進行下一項。

## 本輪優先項目 3：固定測試集與有限參數比較（2026-10-05）

- [x] 自行編寫四個一般插畫案例，版本與 bytes hash；單一參數軸、完整設定、最多八份單張方案，超界／重複／注入拒絕，不寫草稿或提交 GPU。
- [x] 完整 JSON 匯出與預覽 hash 核對；逐組明確載入未保存新草稿，保留其餘比較快照，64 位 seed 與 LoRA 順序精確還原。原生成按鈕獨立提交。
- [x] 382 項後端測試（381 通過、1 項既有 Windows 權限跳過）、Vue 型別／建置及桌面案例／seed／JSON／載入驗收通過。說明見 `docs/experiment-plans.md`；原生下載落盤、窄視窗、自動批次及跨模型 GPU 品質評測仍待後續。
- [x] 正式 5 任務／3 作品／0 草稿不變，隔離 4 任務／4 作品／2 checkpoint 草稿／1 FLUX 草稿保留；8000／8001／8188／5173 全部停止，分項 commit、push。


## 優先項目 1：多 LoRA 步數與順序品質驗證（2026-10-08）

- [x] 新增固定 `multi-8` 與 `style-lcm-8` CLI profiles；完整驗檔、有序快照、一次提交、原圖及離線還原，正反順序各自匹配歷史条件。
- [x] RTX 3060 兩個真實九節點任務成功；8 步及反向順序仍偏淡，不改模型預設或宣稱品質通過，廣泛畫風／多 seed 評估保留待辦。
- [x] 384 項後端測試（383 通過、1 項既有 Windows 權限跳過）、Vue 型別／建置、API 及原圖觀察；瀏覽器工具無法啟動，UI 實機驗收未完成。見 `docs/validation/animagine-multi-lora-quality-rtx3060.md`。

## 優先項目 2：來源分離的任務量測（2026-10-08）

- [x] 交易內保存提交起始與首次確認終態，原歷史身分／時間／結果完整驗證；CAS 及原 UUID 不覆寫或重新提交，舊紀錄保持未知。
- [x] 原引擎單次 RAM／裝置快照，與版本查詢共用，不新增負載；任務、SSE、作品來源沿用，無峰值推估。
- [x] 390 項後端測試（389 通過、1 項既有 Windows 權限跳過）、Vue 型別／建置與 RTX 3060 真實量測、作品及離線核對；瀏覽器 UI 實機驗收未完成。見 `docs/job-measurements.md`。

## 優先項目 3：固定四案例跨模型 GPU 比較（2026-10-08）

- [x] 單案例 CLI：固定權重、測試集版本／hash／完整案例、有界條件、一個 UUID；原回應遺失只查詢，報告／權重／來源不符拒絕。
- [x] Pony／Animagine 各四張 1024²、28 steps、CFG 5、相同 seed 的實際生成；原圖／workflow／模型及環境／量測快照、設定還原與停止引擎後 GET 核對全部通過。
- [x] 開發助手逐張觀察及案例筆記，保留船數／位置／非預期人物與角色衣著細節偏差；四項分數留空，等待使用者判斷。詳見 `docs/illustration-suite.md` 與 `docs/validation/general-illustration-suite-rtx3060.md`。
- [x] 394 項後端測試（393 通過、1 項既有 Windows 權限跳過）、Vue 型別／建置通過；本輪瀏覽器工具環境故障，UI 實機驗收未完成。
- [x] 三項各別完成後先 commit、push；正式 5 任務／3 作品／0 草稿未變更，隔離 11 任務／11 作品保留，8000／8001／8188／5173 均停止。


## 比較功能優先項目 1：指定 LoRA 強度軸（2026-10-08）

- [x] P4／P6：比較一個已啟用 LoRA 的模型或 CLIP 強度；保留另一種強度、其他 LoRA、啟用狀態、原順序及精確 seed。
- [x] 只讀預覽、完整匯出及原方案 hash 核對；未知／停用目標、型別、超界與重複值拒絕，不提交或寫草稿。
- [x] 397 項後端測試（396 通過、1 項既有 Windows 權限跳過）及 Vue 型別／建置通過；工具 sandbox 啟動失敗，UI 實機驗收未完成。沒有新增 GPU 任務或正式資料。
- [ ] 更多強度／seed 的實際畫風品質仍待評估，不能把參數比較支援當成品質驗證。


## 比較功能優先項目 2：圖生圖與改動幅度比較（2026-10-08）

- [x] P6：單張 checkpoint 圖生圖方案、denoise 軸；保留同一素材 ID／fit／stretch、精確 seed、有序 LoRA 及完整設定。
- [x] 文生圖不能借用 denoise 軸；多張／不符素材 ID 拒絕，原素材不可用則保留原值並提示。只讀預覽與匯出不生成或寫草稿。
- [x] 明確提交選定組後，原生 LoadImage／VAEEncode 工作流程與完整還原通過隔離模擬引擎；401 項後端測試（400 通過、1 項既有 Windows 權限跳過）、Vue 型別／建置通過。
- [ ] 更廣泛 denoise／素材／模型品質、結構／畫風 adapter 待評估；2026-10-22 已完成 Pony／Animagine 各 0.3／0.6 圖生圖及比較關聯 GPU 驗收，瀏覽器結果介面與報告匯出亦已於第三項驗收。


## 比較功能優先項目 3：完整方案保存與匯入（2026-10-08）

- [x] P6：不可變方案 SQLite 保存／重載，冪等 request_id、封存／還原 revision，原圖生圖素材引用保護與保存交易一致。
- [x] 1 MiB JSON 選檔／貼上、只讀驗證及完整方案預覽；從單一軸重建各組，核對 hash、精確 seed、流程及數量；文件來源不當成相容或品質證明。
- [x] 原案例快照凍結，測試集變動不替換歷史值；保存及載入方案不改創作表單、不建草稿或任務。使用者仍需明確載入各組並生成。
- [x] 408 項後端測試（407 通過、1 項既有 Windows 權限跳過）及 Vue 型別／建置；隔離 HTTP 三份方案保存、相同 ID 重讀、CAS、素材引用及平台重啟後 GET-only 核對通過。見 `docs/experiment-storage.md`。
- [x] 本輪三項各別 commit、push 後才做下一項；正式 5 任務／3 作品／0 草稿／0 方案不變，隔離 3 方案／1 素材／0 任務／0 作品保留，8000／8001／8188／5173 均停止。
- [ ] 更多素材／seed 品質、專用局部編輯／adapter、FLUX 來源存取與 RTX 4080 待完成；2026-10-22 已補驗比較方案下載／匯入、精確設定載入及 390px。


## 新一輪優先項目 1：LoRA 強度與多 seed 品質驗證（2026-10-08）

- [x] P4：固定單一畫風 LoRA 模型強度 0.5／1.0 × 兩個精確 seed，CLIP 強度與其餘參數不變；新增三個可重跑 CLI profiles。
- [x] RTX 3060 四個八節點任務成功，完整工作流程／版本／雜湊／有序強度／原圖與設定還原核對；引擎離線後 GET-only 核對通過，原 ID 不重送。
- [x] 人工檢查四張原圖，記錄組裝步驟缺失、幾何瑕疵及額外物件；不據兩個 seed 設定通用品質預設。見 `docs/validation/animagine-style-strength-rtx3060.md`。
- [x] 409 項後端測試（408 通過、1 項既有 Windows 權限跳過）；正式資料不變，隔離 4 任務／4 作品保留。
- [ ] 其他畫風、更廣泛品質、RTX 4080 與訓練資源仍待驗證。


## 新一輪優先項目 2：比較方案關聯後端（2026-10-08）

- [x] P6：`/api/generate` 接收已保存方案 ID／hash／variant；交易內核對未封存及完整原設定，原子凍結 context，作品沿用不可變快照。
- [x] 原請求先恢復、不探查引擎／重送；封存方案、離線、未知／失敗與來源檔案遺失保留原關聯，歷史任務／作品不回填。
- [x] 結果只讀 API 依原變體列出任務及作品，包含空組、失敗、未知和封存；同 hash 不同方案 ID 分開，來源快照不符不合併。
- [x] 新增交易競態、精確設定、圖生圖、原請求不重送及資料隔離測試；420 項後端測試（419 通過、1 項既有 Windows 權限跳過）。操作說明見 `docs/experiment-runs.md`。
- [x] 前端關聯操作與結果查看已在第三項接入；不提供自動批次、品質評分或反向補關聯。


## 新一輪優先項目 3：比較關聯與結果介面（2026-10-08）

- [x] 已保存方案逐組載入時帶入原 ID／hash／variant，工作台顯示關聯；完整設定改動後需解除或重載，保存草稿／載入一般設定不會默默繼承關聯。
- [x] 生成使用原 request_id 及完整關聯暫存；處理／待恢復時阻擋新的比較載入，原請求恢復不取用目前表單。
- [x] 按組顯示所有原任務、錯誤、空組、已匯入／封存作品與縮圖／原圖；只讀重讀，不刷新引擎或自動生成；原任務與作品顯示凍結比較來源。
- [x] 前端關聯邏輯檢查及 Vue 型別／建置通過。後端 420 項（419 通過、1 項既有 Windows 權限跳過），真實 RTX 3060 單一關聯任務生成、作品匯入、完整 workflow／快照／原圖 hash 核對、封存新請求 409、切換位址恢復原 ID 及平台重啟後 GET-only 通過。
- [x] 證據 `runtime/experiment-run-20261008.json`、`runtime/experiment-run-recovery-20261008.json`、`runtime/experiment-runs-live-data-20261008`；隔離 1 方案／1 任務／1 作品／0 草稿，另一組沒有任務。第一項隔離 4 任務／4 作品保留，正式 5 任務／3 作品／0 草稿／0 方案不變。
- [x] 三項各別 commit、push 後接續下一項；8000／8001／8188／5173 均未監聽。
- [ ] 其他畫風、更廣泛品質、專用局部編輯／adapter、FLUX 來源存取及 RTX 4080 待完成；2026-10-22 已補驗比較關聯結果、原圖縮圖、報告實際下載與窄視窗。


## 局部編輯優先項目 1：雙輸入後端（2026-10-09）

- [x] P6：固定 checkpoint-inpaint-v1，原圖／遮罩同尺寸、二值語意與獨立前處理快照；SD 1.x／SDXL 及最多四個有序 LoRA。
- [x] 兩素材交易引用保護、原生節點嚴格檢查、兩次安全上傳；失敗不提交、unknown 不重送、UUID 原設定恢復與完整離線还原。
- [x] 新增 14 項測試，完整後端 434 項（433 通過、1 項既有 Windows 權限跳過）。說明見 docs/inpainting.md。
- [x] 遮罩操作介面及 RTX 3060 實機驗收已在第二／三項完成；比較／一般草稿／交換 JSON 不借用舊格式丟棄遮罩。


## 局部編輯優先項目 2：遮罩工作台（2026-10-09）

- [x] 獨立表單、筆刷／擦除／清空／反相／PNG 載入及素材保存；座標依原圖換算，白色範圍明確顯示，未保存遮罩阻擋生成。
- [x] 更換原圖清除遮罩，原素材尺寸檢查、完整 seed、LoRA／參數与模型版本；獨立 pending key、不自動提交或重送。
- [x] 任務／作品雙輸入快照、原圖／遮罩連結及局部編輯還原路由；完整還原與未保存內容確認，拒絕把遮罩丟進舊草稿／比較格式。
- [x] 前端遮罩與表單邏輯檢查、既有比較檢查及 Vue 型別／建置通過；第一項後端 434 項已通過。
- [ ] 瀏覽器工具仍因 sandbox helper 啟動失敗，實際畫面操作／下載／窄視窗未驗收；RTX 3060 接續第三項。


## 局部編輯優先項目 3：RTX 3060 與離線重啟驗收（2026-10-09）

- [x] 固定模型／素材／取樣 CLI，權重大小及 SHA256 驗檔；原 UUID／完整流程先保存、只提交一次、非法報告拒絕、離線核對僅 GET。
- [x] Pony 與 Animagine 各一張 768² 成功，遮罩外 520,704 像素差值為零；雙輸入、完整設定、版本／量測、作品匯入與重啟前後 JSON hash 一致。
- [x] 實機發現並修正遮罩保存的 API 格式，統一原始圖片 body／檔名參數／20 MiB 限制，新增前端請求格式回歸檢查。
- [x] 439 項後端（438 通過、1 項既有權限跳過）、35 項加強報告驗證回歸、遮罩／比較邏輯與 Vue 型別／建置通過。
- [x] 兩張原圖保留顏色偏差、遮罩接縫及船身截斷觀察，未宣稱無縫修補或推薦通用品質預設。見 docs/validation/checkpoint-inpaint-rtx3060.md。
- [x] 正式 5 任務／3 作品／0 素材／0 草稿／0 方案不變；隔離 2 素材／2 任務／2 作品保留。三項各別完成並 commit／push，8000／8001／8188／5173 均停止。
- [ ] 瀏覽器工具仍無法啟動，實際筆刷／觸控／下載／窄視窗待驗收；羽化／邊界融合、專用 inpainting checkpoint、更多 seed、ControlNet／adapter、FLUX 權重与 RTX 4080 保留後續工作。


## ControlNet 優先項目 1：登記與 Canny 提交後端（2026-10-09）

- [x] P6：引擎隔離的 ControlNet 清單、版本／來源／架構／類型／hash／授權登記；未知不推測，失敗保留快照。
- [x] 固定十一節點 Canny 結構條件、空 latent、單張來源與四個有序 LoRA；不借用圖生圖 denoise 語意。
- [x] 交易及上傳前／提交前的登記競態檢查、原生節點與即時模型驗證、不可覆寫來源；UUID 恢復／unknown 不重送。
- [x] 任務／作品保留控制版本、原生 Canny／縮放快照、完整 seed 與離線還原；異常圖不部分載入。
- [x] 新增 12 項測試，完整 451 項（450 通過、1 項既有權限跳過）。見 docs/controlnet.md。
- [x] 專用工作台與固定 SDXL Canny／RTX 3060 已於後續完成；2026-10-22 補驗離線介面與原邊緣，不宣稱畫風／角色鎖定。


## ControlNet 優先項目 2：結構參考工作台（2026-10-09）

- [x] ControlNet 模型庫登記與搜尋／同步、未知版本與類型、來源／hash／授權；引擎切換忽略過期回覆。
- [x] 獨立 Canny 工作台：原素材預覽、控制模型、浮點閾值、強度、作用範圍、完整 seed 與有序 LoRA；同架構／成功清單保護。
- [x] 獨立 pending 請求、未保存替換確認、切換保留；任務／作品控制快照及完整還原路由，不丟入舊草稿格式。
- [x] Canny／既有遮罩／比較邏輯檢查，Vue 型別與建置通過；第一項 451 項後端已通過。
- [x] 當時瀏覽器工具無法啟動；2026-10-22 已補驗工作台、離線預覽與 390px，固定控制權重／RTX 3060 已於後續完成。


## ControlNet 優先項目 3：固定模型及 RTX 3060 驗收（2026-10-09）

- [x] 官方 SDXL Canny 1.0 FP16 固定修訂／大小／SHA256／授權 manifest，限制 controlnet 目錄、續傳、唯讀容量檢查及不可覆寫現有檔案；完整本機驗檔完成。
- [x] 單次安全驗收 CLI，兩份固定權重驗檔、完整來源／控制版本、原 UUID 保存／回應遺失不重送、非法報告拒絕、GET-only 離線核對。
- [x] Pony／Animagine 各一張 768²／20 steps 成功，工作流程、精確 seed、來源／控制快照、作品 hash 及完整還原通過；品質偏差如實保存，未宣稱畫風／角色鎖定。
- [x] 引擎關閉且登記變更後原請求 200、改參數 409；平台重啟後 GET-only 與完整任務 JSON hash 一致，沒有重送。
- [x] 新增 8 項 CLI／安裝測試，完整後端 459 項（458 通過、1 項既有權限跳過），Canny／遮罩／比較邏輯與 Vue 型別／建置通過；前處理布林型別與完整 LoRA 強度還原已補強。
- [x] 隔離 1 素材／2 任務／2 作品保留，正式 5 任務／3 作品／0 素材／0 草稿／0 方案及 settings 指紋不變；8000／8001／8188／5173 均停止。詳見 docs/validation/checkpoint-canny-rtx3060.md。
- [x] 三項依序完成、各別 commit／push 後接續下一項。
- [ ] 更多模型／seed／強度、depth／pose／adapter、專用局部編輯品質、FLUX 來源存取及 RTX 4080 待評估；邊緣預覽／保存、羽化與瀏覽器畫面／下載／窄視窗已於後續完成。


## Canny 追溯優先項目 1：實際邊緣輸出後端（2026-10-09）

- [x] 固定 v2 十二節點，節點 16 保存同次 Canny 條件；v1 格式／原 UUID 及還原保留，新增 API 不跨端點重送。
- [x] 明確保存原歷史邊緣 PNG，原引擎位置／二值／尺寸／大小／hash 驗證；只讀 API 不連線引擎或重新計算。
- [x] SQLite 交易與排他檔案去重，不覆寫遺失／不符／orphan；磁碟／交易失敗只清理本次檔案。獨立快照，不改任務／作品。
- [x] 作品只匯入節點 7，完整流程還原仍保留第二個 SaveImage；新增 12 項保護測試。
- [x] 介面已於第二項完成；兩 seed／兩強度 RTX 3060 比較已於第三項完成。


## Canny 追溯優先項目 2：任務／作品邊緣圖介面（2026-10-09）

- [x] 新提交使用 v2；任務與作品可展開唯讀狀態、明確匯入原邊緣 PNG、離線預覽／下載、查看 hash／尺寸／白色像素數。
- [x] v1／v2 任務／作品標示、完整還原與導向；舊 pending 原 body／UUID／端點不變，新版本機標記不送入 API，未知標記保留並拒絕。
- [x] 來源切換、KeepAlive 與卸載取消讀取／忽略過期回覆；讀取失敗不沿用舊圖，缺檔不自動重抓。
- [x] Canny 請求恢復／來源驗證、遮罩與比較檢查，Vue 型別與 production build 通過。
- [x] 當時瀏覽器工具無法啟動；2026-10-22 已補驗任務／作品原邊緣、實際下載 hash／還原與窄視窗；兩 seed／兩強度 RTX 3060 已於後續完成。


## Canny 追溯優先項目 3：兩 seed／兩強度 RTX 3060 比較（2026-10-09）

- [x] 單次 v2 固定 profile CLI、完整權重驗檔、原 UUID 不重送、實際邊緣 PNG／來源／解碼 RGB／白色像素及完整版本快照。
- [x] Animagine 四個 768²／20 steps CUDA 任務完成，兩 seed／兩強度保存四作品與四邊緣；條件像素相同，品質偏差如實保留。
- [x] 修正 ComfyUI Windows 歷史反斜線驗證，仍拒絕外部／..／重複分隔符；首張保留初次失敗報告，再讀原 output，不重生成。
- [x] 引擎關閉後原 UUID 200、改強度 409、邊緣去重 imported=false；登記變更／平台重啟後四份 GET-only 報告與完整任務 JSON 不變。
- [x] 五項新增 CLI 與一項 Windows 契約測試，477 項後端（476 通過、1 項既有權限跳過）；Canny／遮罩／比較邏輯與 Vue 型別／建置通過。
- [x] 隔離 1 素材／4 任務／4 作品／4 邊緣保留，正式 13 settings key 指紋及 5 任務／3 作品不變；8000／8001／8188／5173 皆停止。見 docs/validation/canny-edges-rtx3060.md。
- [x] 本批三項分別完成、commit／push 後才進行下一項。
- [ ] Pony v2／其他 LoRA、depth／pose／adapter、局部編輯品質改善、FLUX 安裝容量與 RTX 4080 接續評估。


## 內側羽化優先項目 1：版本化後端（2026-10-22）

- [x] checkpoint-inpaint-feather-v2 十一節點：二值去噪與灰階合成分離，半徑 0–64 輸出像素，原黑色 alpha 為零；細遮罩消失明確拒絕。
- [x] CPU 預覽不連線引擎、不建立檔案或任務；方法／Pillow／二值來源／PNG hash 快照、三份排他輸入、失敗／未知不重送。
- [x] v1 原端點及 UUID 恢復保留；完整 v2 任務／作品還原，讀取合成遮罩不重新計算／回填，新增十二項保護測試。
- [x] 工作台預覽／新參數／pending 相容與 RTX 3060 比較已於第二／三項完成。詳見 docs/inpaint-feather.md。


## 內側羽化優先項目 2：工作台與預覽（2026-10-22）

- [x] 羽化參數預設 0、CPU 真實灰階預覽、明確未保存／失效／細遮罩提示；回應大小、RGB PNG／尺寸／SHA256 驗證。
- [x] v1 pending 仍送原端點，v2 標記不傳入 API；v1 載入新表單時補 0，不改歷史。任務／作品還原導向、原合成遮罩來源／hash 及下載連結。
- [x] 過期回覆、參數／來源變動、KeepAlive、Blob URL 清理；原素材／二值／合成快照分開顯示。
- [x] 前端遮罩／Canny／比較邏輯、Vue 型別與建置通過；瀏覽器離線預覽、參數失效、非法半徑、切換保留與 390px 無橫向溢出通過。
- [x] UI 隔離 2 素材／0 任務／0 作品，正式指紋未變；截圖與說明見 docs/inpaint-feather.md。
- [x] 真實 RTX 3060 羽化比較及新歷史介面已於第三項核對；筆刷觸控尚未重驗。


## 內側羽化優先項目 3：RTX 3060 與持久化驗收（2026-10-22）

- [x] 固定單次 CLI、兩模型權重完整驗檔、原 UUID 不重送、預覽／保存合成 PNG 相同、完整三輸入／來源／版本與精確 seed。
- [x] Pony／Animagine 各半徑 0／16，四個 CUDA 任務及作品成功；遮罩外 520,704 像素差值均 0、兩模型各自不透明核心 32,548 像素相同；淡出／截斷與色彩偏差保留。
- [x] 引擎關閉原 UUID 200、改半徑 409；平台重啟後四份 GET-only 報告與原完整任務 JSON 不變。
- [x] 修正 CLI 作品摘要不含 workflow 的契約，首張只 GET 恢復原證據不重新生成；修正未支援流程誤顯示的設定交換入口，保留 workflow 下載。
- [x] 真實瀏覽器預覽／390px、歷史羽化來源／下載 hash／精確 seed 與半徑還原通過；筆刷觸控與真實遺失回應的 pending 未重驗。
- [x] 新增五項 CLI 測試，完整 494 項後端（493 通過、1 既有 skip）；遮罩／Canny／比較及 Vue 型別／建置通過。
- [x] GPU 隔離 2 素材／4 任務／4 作品、UI 隔離 2 素材／0 任務／0 作品；正式 13 settings key 指紋及 5 任務／3 作品不變，8000／8001／8188／5173 均停止。見 docs/validation/inpaint-feather-rtx3060.md。
- [x] 本批三項各完成、commit／push 後接續下一項。
- [ ] P5 固定 BFL 權重需先取得來源存取；P6 專用 inpainting 模型／其他半徑與 seed、depth／pose／adapter及 RTX 4080 接續評估；Canny 送出前 CPU 預覽已於後續完成。


## Canny 預覽優先項目 1：CPU 預覽後端（2026-10-22）

- [x] 固定本地 ComfyUI Python／稽核原碼的 Kornia CPU 預覽，不需模型或引擎，無任務／檔案／歷史回填。
- [x] 獨立嚴格輸入、素材驗檔、單一 worker、超時回收與限量讀寫；二值 RGB、尺寸、hash 與實際版本來源驗證。
- [x] 將開發清單正式更名為 ROADMAP.MD，保留原始 43／主 27／歷史 16 的統計口徑。
- [x] 本項後端測試通過後 commit／push；工作台與實機驗收接續下一項。


## Canny 預覽優先項目 2：工作台（2026-10-22）

- [x] 明確按鈕計算 CPU 預覽，無模型／引擎亦可使用；顯示尺寸、閾值、縮放與實際版本來源，不冒充原任務輸出。
- [x] 獨立請求欄位、回應大小與 provenance／PNG／SHA256 驗證；參數與來源變動、KeepAlive、過期回覆及 Blob URL 清理。
- [x] 前端 Canny／局部編輯／比較檢查與 Vue 型別／production build 通過；實際離線預覽、非法閾值、切換保留／清理與 390px 佈局通過。
- [x] 隔離 2 素材／4 既有任務／4 既有作品不增加生成；正式指紋不變。原生 GPU 邊緣／保存歷史比對接續第三項。


## Canny 預覽優先項目 3：RTX 3060／離線歷史驗收（2026-10-22）

- [x] 四個新原生 Canny GPU 案例，比對相同處理後 PNG、閾值、fit／stretch；兩例完全相同，低閾值兩例 51／15 不同像素，如實記錄近似限制。
- [x] 四個既有 v2 原任務 CPU 預覽與原邊緣像素相同；新增驗收 CLI，不補生成／不匯入，報告與 PNG 不可覆寫。
- [x] 引擎離線／平台重啟後四份 GET-only 證據一致，原完整任務／作品不變；正式資料指紋未變。
- [x] 瀏覽器任務／作品原邊緣、實際下載 hash、精確 seed 與參數還原、重啟後預覽與 390px 通過，關閉三條已滿足的歷史提醒。
- [x] 五項驗收 CLI 與一項程序輸出邊界測試，510 項後端（509 通過、1 既有 skip）；前端檢查及建置通過。詳見 docs/validation/canny-preview-rtx3060.md。
- [x] 本批三項各別驗證、commit／push 後接續下一項；8000／8001／8188／5173 測試服務停止。


## 效能條件優先項目 1：提交時快照（2026-10-22）

- [x] 新任務／作品凍結推論尺寸、batch、取樣、精確 seed、模型／元件／有序 LoRA 版本；未知流程不猜測。
- [x] 僅保存原引擎回報的允許旗標，隔離 token／路徑；設定不視為實際精度／卸載，冷熱狀態未知。
- [x] 舊任務不回填、UUID 不重探測；六項新增測試與 Vue 型別／建置通過。


## 圖生圖比較優先項目 2：固定 denoise 實機驗收（2026-10-22）

- [x] 單次 CLI 固定兩模型／兩 denoise profile，原 UUID 不重送；完整權重驗檔、同來源與精確 seed、不可變方案關聯及新效能條件快照。
- [x] RTX 3060 四任務／四作品成功，原圖／前處理／JSON／版本／hash／比較結果核對；仍未達紅木椅與房間提示，像素差值不當品質評分。
- [x] 引擎離線／平台重啟四份 GET-only 與原完整任務不變；隔離 1 素材／2 方案／4 任務／4 作品，正式指紋不變。
- [x] 五項新 CLI 測試、521 項後端（520 通過、1 既有 skip）；瀏覽器與結果報告接續第三項。見 docs/validation/image-comparison-rtx3060.md。


## 比較報告優先項目 3：結果匯出與介面驗收（2026-10-22）

- [x] 同一 SQLite 快照匯出原方案、明確關聯任務／完整 graph／版本／量測及作品 hash／目前人工整理；未知不回填、不連線引擎。
- [x] 完整關聯／流程與來源驗證，100 筆／8 MiB 超出明確拒絕；九項測試含並行更新一致性及歷史缺欄位／缺檔。
- [x] 前端限量串流、來源／SHA256 驗證、原 bytes 精確 64 位元下載、過期回覆／Blob 清理；530 項後端（529 通過、1 既有 skip）、三組前端邏輯／Vue 建置通過。
- [x] 真實瀏覽器結果報告／原方案下載與匯入、錯誤文件拒絕、variant 精確載入、效能條件顯示、來源切換／離開清理及 390px／桌面雙欄驗收通過。
- [x] 隔離 1 素材／2 方案／4 任務／4 作品不變、正式指紋不變；本批三項各完成 commit／push 後接續，測試服務停止。見 docs/comparison-report.md。
<!-- roadmap-final-snapshot:end -->

</details>


<a id="roadmap-completed-20261025"></a>

## 2026-10-25 · 已完成 ROADMAP 條目歸檔

依使用者要求，將已完成條目的原驗收敘述、提醒與證據移至此處；不新增驗收或改動原結論。來源為 [33512b8 的 ROADMAP](https://github.com/Zimkjdv/Model-Atelier/blob/33512b8df02d35206a3b27a90f6918a8b56b4534/ROADMAP.MD)。日期與測試數均屬各次歷史紀錄；最新未完成工作見 [ROADMAP.MD](ROADMAP.MD)。

### 2026-10-22 整體檢視與改善計畫

#### 範圍、現況與判斷

本輪盤點專案檔案，重點閱讀 FastAPI 組裝／提交／任務／作品／素材儲存、Vue 主介面及四種工作台、共用生成與事件處理、樣式、啟動與驗證腳本、README、功能文件及既有路線圖。以下是原始碼與文件檢視加上自動檢查，並非每個分支的完整稽核；未執行真實瀏覽器操作、讀屏／觸控驗證、GPU 生成或大量資料效能測試。

目前架構為 Vue 工作台 → FastAPI 功能模組 → SQLite 的 `settings(key, value)` JSON 紀錄與本地圖片 → 獨立 ComfyUI。任務另以 SSE／WebSocket 傳遞進度，最終狀態仍由歷史核對。既有優點包括：原 UUID 恢復與避免重送、精確 seed、不可變來源快照、修訂衝突處理、離線作品保存，以及功能與實機證據分開記錄。這些約束應作為改善時的回歸底線，不因抽象化而放寬。

| 面向 | 已確認的現況 | 改善判斷／對應 |
| --- | --- | --- |
| 程式 | 工作台分別包裝 HTTP 與載入狀態；部分檔案將多個狀態操作壓在同一行 | 共用錯誤／取消契約與提升可讀性，保留專用流程差異；Q03、Q10 |
| 架構 | `main.py` 匯入即建立資料目錄／資料表，多個模組透過 `install(app, sys.modules[__name__])` 取得依賴 | 顯式配置與應用程式工廠可改善測試隔離；Q02，不需重寫或改成微服務 |
| 資料與效能 | jobs／artworks／assets 用 `fetchall()` 讀取 JSON；作品頁全量抓取作品與任務再篩選 | 資料量成長風險已確認，實際卡頓尚未量測；Q04 |
| 文件 | README 開頭已列收藏／筆記，後段仍寫「目前尚無作品刪除、收藏或備註」 | 同頁現況矛盾，且歷史驗收與使用說明交錯；Q01 |
| 功能可靠性 | Checkpoint 有 `beforeunload` 保護；其他三種工作台未見同等註冊，KeepAlive 只保留站內切頁狀態 | 補齊重新整理／關頁的未保存保護；Q05，實際瀏覽器行為仍待驗證 |
| UI | 已有共用配色、焦點、收合設定及四種工作流程；App 用區域狀態切頁，未與 URL 同步 | 先改善導覽與能力狀態可見性；Q08。視覺／觸控／無障礙仍依 V01–V06 補驗 |
| 維運 | 已有大量 unittest 與三組前端邏輯腳本；備份主要依文件要求整份 data 保存 | 補可重跑檢查入口、恢復演練與診斷；Q06、Q07、Q09 |

#### 本次檢查基線

- 後端：`.venv/Scripts/python.exe -m unittest discover -s backend -p 'test_*.py'`，530 項，529 通過、1 跳過（Windows symlink 權限條件）；不能推論真實 GPU 或所有 UI 已通過。
- 前端：`npm.cmd run build` 通過 Vue 型別檢查與 Vite 正式建置；`check:experiments`、`check:inpaint`、`check:control` 均通過。首次建置受沙箱父目錄存取限制失敗，提升權限重跑同一指令後通過，未改動程式修復。
- 建置輸出基線：主 JS 約 370.42 kB（gzip 118.39 kB），CSS 約 56.62 kB（gzip 10.14 kB）。這是檔案大小，不是載入時間，也不足以宣稱需要立即拆包。
- 測試顯示 Starlette TestClient 的 httpx 棄用提示；列入 Q06 評估相容版本，不直接更換鎖定依賴。本輪未查詢線上版本或進行依賴漏洞稽核。
- 整體檢視階段僅更新路線圖，Q01–Q10 全部保持未完成；後續 E01 實作另見其驗收紀錄，不將既有測試通過視為新增項目的驗收。

#### 可執行改善項

優先級為本節局部排序：高＝下一輪先處理；中＝本地穩定化階段；低＝有量測或相關維護需求時實作。工作量為相對範圍（小／中／大），不是交付日期。

<a id="q01"></a>

- [x] **Q01 · 文件現況一致性與閱讀入口**（高／小）
  - 依據：`README.md` 的「目前範圍」與後段「作品庫」對收藏／筆記支援說明矛盾，安裝、功能說明與多日期驗收交錯；既有 `docs/review-2026-10-03.md` 是歷史檢查，不是當前全量結果。
  - 作法：README 保留快速開始、現有功能與限制、日常操作與文件索引；功能細節以各 docs 為準，歷史數據連到驗收紀錄／CHANGELOG。補一份架構及資料流說明，標示任務狀態、原引擎綁定與資料存放位置。
  - [x] 驗收 Q01-01：README 改為現行功能／限制，完整舊文保存在有明確日期及來源 commit 的歷史快照；架構資料流、操作指南及文件索引分工。
  - [x] 驗收 Q01-02：依腳本／端點核對 lock 安裝、啟動、首次生成、離線與備份步驟，130 個本地連結／錨點通過；固定模型唯讀預檢通過，來源／硬體及 ComfyUI 非完整 lock 限制已記錄。
  - 2026-10-22：本次為文件整理與命令／來源對照，未重新下載依賴／權重或宣稱新主機 GPU 驗收；現行入口見 [文件索引](docs/index.md)，舊 README 全文見 [歷史快照](docs/history/readme-before-q01-20261022.md)。

<a id="q02"></a>

- [x] **Q02 · 顯式應用程式配置與模組依賴**（中／大）
  - 依據：`backend/main.py` 在匯入時建立 DATA／DB，功能模組由 `install(app, host)` 讀取整個 main 模組；`backend/test_api.py` 等測試需 patch 全域 DB／DATA。
  - 作法：先引入可注入 data root／資料庫／引擎存取的 `create_app` 與小型 context，再逐個模組移轉；初始化放在明確啟動階段。維持既有路由與本機部署，不要求換資料庫或引入完整 ORM。
  - [x] 驗收 Q02-01：create_app 與 AppContext 明確配置資料／DB／引擎 HTTP；雙 app 同時運作隔離設定、相同 UUID 任務、素材與快取；匯入不 mkdir／connect，測試改用自身 context。
  - [x] 驗收 Q02-02：548 項回歸（547 通過、1 項既有權限跳過）；所有 install 模組移轉 context，啟動入口不變，重開 app 及舊 JSON／seed 不改寫驗證通過。
  - 2026-10-22：未改 SQLite schema、資料 key、工作流程或 HTTP 格式；回退僅切換程式版本並重啟。配置與重跑指令見 [應用程式工廠](docs/application-factory.md)。

<a id="q03"></a>

- [x] **Q03 · 前端 API 契約與可取消載入的共用邊界**（中／中）
  - 依據：`App.vue`、`CreationStudio.vue`、`FluxStudio.vue`、`InpaintStudio.vue`、`ControlStudio.vue`、`ArtworkLibrary.vue` 各有 API helper；錯誤解析與取消方式各自實作。已有 `GenerationPanel.vue`／`jobEvents.ts` 共用邏輯，應沿用。
  - 作法：先統一 HTTP 狀態、字串／結構化 422、非 JSON 回應、AbortSignal 與錯誤型別；抽出確實重複的載入狀態。普通 JSON 與保留大整數的原始 bytes／workflow 下載分開，避免 seed 精度流失。
  - [x] 驗收 Q03-01：共用 ApiError／HTTP 解析與 request scope 覆蓋離線、409／422／500、非 JSON、取消及過期回覆；實際四種 SFC 的 KeepAlive／卸載回歸與瀏覽器未保存內容保留通過。
  - [x] 驗收 Q03-02：四流程實際 GenerationPanel 遺失回應恢復，以及修補／Canny v1、v2 原端點與字串 seed／LoRA 順序通過；原 bytes／文字下載不重新序列化，生成／停止／取消無自動重試。
  - 2026-10-22：前端型別／正式建置與 check:api、既有三組邏輯檢查通過；作品 409 保留筆記／修訂號，真實瀏覽器驗證 422 與四流程切換，模擬引擎只收到一次生成。契約、涵蓋範圍與重跑見 [前端 API](docs/frontend-api.md)。

<a id="q04"></a>

- [x] **Q04 · 清單分頁、摘要查詢與資料成長基準**（中／大）
  - 依據：`backend/jobs.py`、`gallery.py`、`assets.py` 的 `list_all()` 全量取值；`gallery_api.py` 在全量資料上篩選及檢查檔案；`ArtworkLibrary.vue` 同時讀取 `artworks?scope=all` 與 `jobs`，再做瀏覽器搜尋。
  - 作法：以隔離資料量測 100／1,000／10,000 筆的 API 耗時、回應 bytes、記憶體與畫面可操作時間；導入有上限且排序穩定的清單 API，將搜尋／篩選移至後端，詳情按需讀取。必要時建立可索引摘要表與版本化遷移，不破壞歷史 JSON。
  - [x] 驗收 Q04-01：分頁搜尋、收藏／模型／封存組合篩選、跨頁選取比較與最新任務可用；新增／更新資料時沒有重複或漏項，既有 API 相容策略明確。
  - [x] 驗收 Q04-02：在相同硬體／資料集記錄前後指標與事先訂定的效能預算；如果遷移，驗證重跑、失敗回退、舊紀錄與不可變快照，不先宣稱效能提升幅度。

- 2026-10-22：新增三類有上限的摘要 API，作品／任務／素材介面改用分頁、後端搜尋與按需詳情；固定查詢成員避免更新位移，跨頁比較及已選素材保留。100／1,000／10,000 同機合成資料前後 API／流量／記憶體及 UI 指標已記錄並通過預算；舊 API 保留，無 schema／JSON 遷移，詳見 [分頁與驗收證據](docs/list-pagination.md)。

<a id="q05"></a>

- [x] **Q05 · 四工作台一致的未保存內容與關頁保護**（高／中）
  - 依據：`CreationStudio.vue` 註冊 dirty 時的 `beforeunload`；`FluxStudio.vue`、`InpaintStudio.vue`、`ControlStudio.vue` 未見對等保護。`App.vue` 的 KeepAlive 可保留站內切頁內容，無法保證重新整理或關頁後仍在。
  - 作法：統一表單／遮罩 dirty 訊號與離頁警示，明示「保留於本頁」和「已保存」的差異；先處理遺失提示，專用流程草稿／交換仍由 R07 決定，不順便建立不完整格式。
  - [x] 驗收 Q05-01：在真實瀏覽器分別測四流程未保存、已保存、正在保存、筆刷編輯後的重新整理／關頁與站內切換；支援時出現警示，記錄行動瀏覽器不保證觸發的限制。
  - [x] 驗收 Q05-02：提示取消後內容不變；確認離開不觸發生成；未確認提交的原 UUID／端點仍可恢復，且 dirty 提示不把已提交內容誤稱為可自動恢復草稿。與 V01／V02 共用操作證據。

- 2026-10-22：四工作台共用 dirty／保存中離頁保護，KeepAlive 隱藏內容仍受保護；Chrome 隔離資料驗證重新整理／關頁取消、保存中與保存後、實際筆刷及確認離開，模擬引擎提交 0 次。前端建置與四組檢查通過，行動限制及範圍見 [說明與證據](docs/unsaved-changes.md)。

<a id="q06"></a>

- [x] **Q06 · 可重跑品質檢查與瀏覽器回歸入口**（高／中）
  - 依據：`frontend/package.json` 有 build 與三個 check 腳本，尚無統一 test 入口；本輪檔案盤點未見已提交的 CI 或瀏覽器測試設定。現有 Node 邏輯檢查不能代替 DOM、下載、焦點與觸控驗收。
  - 作法：提供單一可失敗即停止的檢查命令，串接後端、前端型別／建置與三組腳本；再加入使用隔離 DATA 與模擬引擎的瀏覽器測試，並建立相應 CI。真實 GPU／觸控保留獨立人工驗收；評估 TestClient 棄用提示與鎖版相容性。
  - [x] 驗收 Q06-01：乾淨安裝使用 lock 檔可重跑，任何子檢查失敗回傳非零；測試不讀寫使用者作品、不啟動真實推論，明列跳過原因及依賴警告處理結果。
  - [x] 驗收 Q06-02：自動覆蓋遺失回應只恢復原請求、修訂衝突保留內容、實際 JSON 下載、鍵盤預覽開關與 390px 基本操作；失敗保存可追溯證據，V01–V06 仍逐項驗收，不一鍵宣稱全站通過。

- 2026-10-22：單一 fail-fast 品質入口、精確鎖版 Playwright、臨時 DATA／模擬引擎與 Windows CI 已加入；乾淨安裝、550 項後端（1 權限跳過）、型別／建置、四組契約及 8 項瀏覽器回歸通過，失敗探針確認非零與證據保存。TestClient 警告保留並記錄相容性，Vite／source-map-js 更新修補版後 npm audit 為 0；範圍及重跑見 [品質指南](docs/quality-checks.md)。

<a id="q07"></a>

- [x] **Q07 · 完整備份、離線還原與資料健全性工具**（中／中）
  - 依據：README 要求停平台後備份整份 `data/`；`docs/validation/inpaint-feather-rtx3060.md` 等另指出 runtime 的整份隔離 DATA／報告需保存。設定 JSON 與比較報告都不能取代完整資料備份。
  - 作法：先提供明確停機條件下的備份／唯讀檢查命令，列出資料庫、素材、作品、job_inputs、control_edges 與選定證據的涵蓋範圍；權重與外部 ComfyUI 目錄另列，不偷偷納入巨量檔案。含 hash manifest，恢復到新目錄驗證後再明確切換。
  - [x] 驗收 Q07-01：在隔離目錄完成備份→還原→引擎離線讀取，核對任務／作品數、精確 seed、來源、遮罩、邊緣圖與圖片 hash；若不能保證一致快照，拒絕備份並說明停機需求。
  - [x] 驗收 Q07-02：損壞／缺檔／空間不足能報告且不覆寫原資料；盤點只讀，修復或清理須另行明確操作，不以重新生成取代遺失的歷史檔案。

- 2026-10-23：新增停機 check／backup／verify／restore 與明確資料啟動命令；全 DATA、外置 DB、選定證據及 SHA256 manifest，目的地只接受新目錄。隔離還原、離線來源／遮罩／邊緣及精確 seed、程序鎖、損壞／缺檔／空間不足／來源變動回歸通過；操作與限制見 [完整備份工具](docs/data-backup.md)。

<a id="q08"></a>

- [x] **Q08 · UI 導覽、能力狀態與資訊層級**（中／中）
  - 依據：`App.vue` 用 `page`／`studioMode` 切換，首頁固定系統資訊，四種流程同時呈現；頁面未與 URL 同步。元件採靜態匯入，但現有 bundle 大小本身不足以證明載入有問題。
  - 作法：建立可還原的頁面／流程 URL 或 hash，處理返回、重新整理與焦點；讓首次使用可直接看見「連線→選模型→建立作品」的下一步。清楚區分可提交、缺元件、程式已接入但尚未實機驗證；詳細版本／來源保留在可展開區。量測後才評估延遲載入非當前頁。
  - [x] 驗收 Q08-01：直接開啟、返回／前進、重新整理與錯誤網址均有明確結果；站內切換保留表單，重新整理遵守 Q05，焦點與目前導覽標記一致，沒有因恢復網址自動提交。
  - [x] 驗收 Q08-02：以桌面與 390px 完成首次連線、選流程、生成後找到作品、離線查閱；保留未知／未驗證能力提示。共用 token、對比、按鈕狀態與鍵盤操作沿 V06 驗收；若拆包，另比對首屏與切頁耗時。

- 2026-10-23：頁面／四流程／原匯入任務採用 hash URL，返回前進、錯誤網址、焦點及筆記取消離頁驗證通過；KeepAlive／Q05 保留，無自動提交。1440px／390px 隔離首用、明確生成、匯入及引擎離線原圖通過；能力分層、未知／未驗證與大小比較見 [導覽說明](docs/navigation.md)，未拆包或宣稱 V06 全部完成。

<a id="q09"></a>

- [x] **Q09 · 可追溯且可控的故障診斷**（中／中）
  - 依據：`failures.py`／任務 JSON 已保存分類與上游證據，`/api/health` 僅回報 `ok`；目前主模組未提供統一的結構化診斷事件入口。應補跨 API／任務／引擎的排查能力，不重做既有失敗分類。
  - 作法：統一記錄 request／job ID、流程、階段、耗時及錯誤分類；提供可預覽的診斷匯出，區分服務存活、資料可用與引擎連線狀態。引擎離線不應把可用的離線作品庫判成失效。
  - [x] 驗收 Q09-01：用模擬離線、遺失回應、409 及磁碟錯誤追蹤同一任務；原 UUID 恢復不被誤記為新提交，過期觀察與終態區分清楚。
  - [x] 驗收 Q09-02：預設診斷不包含提示詞、圖片、完整 workflow、憑證或不必要的個人路徑；記錄有大小／保留期限限制，產生診斷不連帶修改任務或重新生成。

- 2026-10-23：新增限量記憶體 request／job／workflow／stage／耗時追蹤、明確恢復與過期觀察事件，以及平台／資料／引擎狀態分離。模擬離線、遺失回應、409、提交後磁碟失敗保持原 UUID 且不重送；1440px／390px 預覽與逐字下載、不改任務及敏感值排除通過。保留上限、API／UI 與驗證見 [診斷說明](docs/diagnostics.md)。

<a id="q10"></a>

- [x] **Q10 · 高風險流程的可讀性與維護規則**（低／中）
  - 依據：`frontend/src/style.css`、部分工作台與後端流程含高密度單行寫法；本輪未見統一 formatter／lint 設定。對同時處理 busy、pending、revision 與恢復的程式，審閱成本較高。
  - 作法：訂定 Python／TypeScript／Vue／CSS 格式與少量有實質價值的靜態檢查；優先整理正在修改的提交、恢復與 UI 狀態邏輯，使用具名函式及清楚的轉移條件。避免一次全庫格式化混入功能差異。
  - [x] 驗收 Q10-01：格式命令可重跑且第二次無差異，檢查入口納入 Q06；整理後能清楚辨識未送出、送出結果未知、確認中與終態的操作邊界。
  - [x] 驗收 Q10-02：純格式／重構與功能改動分開審閱，現有相關測試與前端檢查通過；不為追求抽象而合併不同 workflow 的驗證或更改公開資料格式。

- 2026-10-23：以鎖版 Ruff／Prettier／CSS-tree 建立明確範圍的格式與少量靜態檢查，接入 Q06／CI；16 檔第二次格式零差異、格式語意比對及錯誤探針通過。格式與具名提交／恢復／確認狀態重構分開提交，四流程保存失敗不送出、原 UUID／版本端點恢復、明確回覆清除及後端 revision／終態回歸通過；規則與證據見 [維護指南](docs/maintenance.md) 與 [Q10 驗收](docs/validation/maintenance-20261023.md)。

#### 與原待辦的去重與依賴

- V01–V06 保留真實 UI 驗收責任；Q05／Q08 是具體行為改善，Q06 是讓可自動化部分持續可重跑，三者不能代替觸控、視覺或硬體實測。
- R07 繼續負責專用流程草稿／交換／比較格式；Q05 先補離頁保護，不另列一套相同功能。
- E05 是推論資源取樣；Q04 是平台清單效能、Q09 是應用診斷，各自量測與驗收。
- D01／D02 與 A01–A07 的部署／官方服務先後不變；本輪沒有新增社群、多租戶、付費、自動重試或自動品質評分範圍。

### E01

<a id="e01"></a>

- [x] **E01 · 可靠辨識無可用執行裝置**
  - [x] 驗收 E01-01：引擎程序內的專案唯讀回報確認目前設定的裝置；nonce／版本／來源驗證，空裝置清單、離線、缺回報及異常資料保持未知，CPU 是有效裝置。
  - [x] 驗收 E01-02：標準／直接 workflow／圖生圖／修補 v1、v2／Canny v1、v2／FLUX 只在新提交取得明確不可用證據時阻擋，保留失敗 UUID；草稿、離線作品、CPU 預覽與原有相容性保護均已回歸。
  - 2026-10-22：545 項後端測試（544 通過、1 項既有 symlink 權限跳過）、前端型別／建置與三組邏輯檢查通過；真實隔離 ComfyUI CPU 模式回報可用、HTTP 故障注入及三種瀏覽器提示通過。未刻意破壞真實 GPU／驅動；見 [操作與限制](docs/execution-device.md)、[驗收證據](docs/validation/execution-device-20261022.md)。

### E05

<a id="e05"></a>

- [x] **E05 · 連續資源取樣與任務專用峰值評估**
  - [x] 驗收 E05-01：先定義取樣範圍、頻率與程序歸屬，區分整卡用量、提交前快照及任務專用峰值。
  - [x] 驗收 E05-02：以實際任務驗證量測、保存與顯示；無法可靠歸屬時標示限制，不把單次快照當峰值。
  - 2026-10-23：新任務從首次提交起背景查詢原引擎，獨立 journal 有界保存時間點／缺口及觀察最高值，終態凍結並隨作品保存；不改 revision、不重送生成、不回填歷史。RTX 3060／Animagine 實際取得 22 次取樣，任務與作品一致，離線和 1440px／390px 顯示核對通過。引擎裝置用量不同於 nvidia-smi 整卡用量，任務專用峰值仍為未知；見 [範圍](docs/job-measurements.md)、[E05 證據](docs/validation/resource-sampling-20261023.md)。

### V02

<a id="v02"></a>

- [x] **V02 · 羽化 v1／v2 pending 遺失回應的真實瀏覽器補驗**
  - [x] 驗收 V02-01：在隔離資料實際製造未知／遺失回應，核對原 UUID、端點、遮罩／半徑與重新載入後恢復。
  - [x] 驗收 V02-02：確認只查詢原請求、不自動重送，v1 不被新表單改為 v2；保留原證據。

  2026-10-23：1440px／390px 的 v1／v2 × 引擎回覆遺失／平台異常 JSON 共 8 案例，以及未知版本保護通過。原 pending、完整 body／端點、精確 seed、雙素材與處理輸入／羽化半徑保持一致；重載及輪詢不送生成，手動恢復只返回原 UUID 帳本，引擎每案例仍僅一次提交。修正成功 JSON 或明確錯誤攜帶其他任務 ID 時誤清除 pending；原始請求、任務 JSON、呼叫紀錄與畫面保留於測試證據。見 [V02 驗收紀錄](docs/validation/inpaint-recovery-20261023.md)。V01 實機觸控仍待驗收。

### V03

<a id="v03"></a>

- [x] **V03 · 作品整理、並排比較與人工評分的窄視窗補驗**
  - [x] 驗收 V03-01：在 390px 實際完成篩選、收藏、筆記、封存／還原、未保存保護及修訂衝突處理。
  - [x] 驗收 V03-02：操作原圖並排、參數差異及人工評分的保存／衝突；不以比較報告結果頁的 390px 驗收替代。
  - 2026-10-23：五項 390 × 844 瀏覽器操作完成，雙分頁筆記／評分 409、明確重讀、保存中與 503 保護，以及原圖／workflow bytes、精確 seed 與 LoRA 順序核對通過。修正空篩選提示、預覽保存忙碌狀態與比較區鍵盤捲動；使用臨時合成作品，沒有 GPU 推論或正式資料變更。證據及重跑見 [V03 驗收](docs/validation/artwork-library-20261023.md)；實機觸控與全站 UI 仍依 V01／V06 待驗收。

### V04

<a id="v04"></a>

- [x] **V04 · 比較與量測介面仍缺少的實際操作驗收**
  - [x] 驗收 V04-01：核對 8 步正／反向多 LoRA 新品質紀錄的條件及品質限制，不借用較早桌面匹配驗收。
  - [x] 驗收 V04-02：實際操作指定 LoRA 的 model／CLIP 強度軸，確認其餘強度、順序、精確 seed 及錯誤處理。
  - [x] 驗收 V04-03：核對固定四案例跨模型結果及案例設定載入，不以兩個 denoise 方案的 UI 驗收概括四案例。
  - [x] 驗收 V04-04：核對任務與作品的量測來源、平台／引擎耗時及未知值顯示，不把效能條件快照等同量測 UI。
  - 2026-10-23：1440px／390px 八項回歸覆蓋有序 8 步品質條件、指定 LoRA 兩種強度軸、四案例逐組載入，以及任務／作品原來源、零與未知量測。另在歷史唯讀副本核對 11 件原作品、八次跨模型並排及 22 次設定還原，來源 DB／原圖／workflow 不變；未新增 GPU 推論或品質預設。證據及限制見 [V04 驗收](docs/validation/comparison-measurements-20261023.md)。

### V05

<a id="v05"></a>

- [x] **V05 · 一般創作設定交換的實際下載與窄視窗補驗**
  - [x] 驗收 V05-01：在能觀察下載結果的瀏覽器核對創作設定 JSON 檔案、原 bytes、精確 seed 及匯入預覽。
  - [x] 驗收 V05-02：在 390px 驗證匯出、檔案選取／貼上、取消及套用保護；比較方案 JSON 的驗收不替代此格式。
  - 2026-10-23：1440px／390px 十二項瀏覽器回歸核對 checkpoint、圖生圖、FLUX 及作品來源的實際下載、檔名／磁碟 bytes／精確 seed、檔案選擇器與剪貼簿貼上、取消、舊預覽失效及另存新草稿。修正失敗新檔仍保留舊候選、非嚴格 UTF-8 與讀取期間保護；未生成圖片或改正式資料。證據與限制見 [V05 驗收](docs/validation/settings-transfer-20261023.md)。

### V06

<a id="v06"></a>

- [x] **V06 · 全站視覺規範與無障礙補驗**
  - [x] 驗收 V06-01：逐頁核對視覺狀態、標籤、鍵盤操作、焦點、可讀對比與非顏色狀態提示。
  - [x] 驗收 V06-02：保存各頁桌面／窄視窗的結果及限制；既有工作台與主要導覽驗收不代表全站通過。
  - 2026-10-23：新增 21 項 Chromium 回歸，逐一驗證六主頁／四流程的九個入口與展開、編輯、預覽、讀取、空白及錯誤狀態，保存 1440px／390px 的截圖與 axe JSON。修正文字／漸層對比、收藏 ARIA 值、標題層級、窄版品牌名稱及可捲區焦點。保留 incomplete 判讀與瀏覽器／讀屏限制，不宣稱完整 WCAG 認證；V01-02 實機觸控仍未完成。頁面矩陣及重跑見 [V06 驗收](docs/validation/ui-accessibility-20261023.md)。

### L01

<a id="l01"></a>

- [x] **L01 · 更多多 LoRA 組合及其他畫風品質比較**
  - [x] 驗收 L01-01：固定像素 LoRA 原來源及獨立鍵名相容副本；Animagine 上完成 14 組原生單／雙／三 LoRA、正反順序、model／CLIP 強度、兩個精確 seed 與兩題材，保存完整版本、原圖、設定及逐圖觀察。
  - [x] 驗收 L01-02：原格式四組雖出圖但全鍵未載入，另存拒絕證據；原生批次零未載入警告，LCM 模糊、造型偏移與裁切等品質限制保留。新六筆歷史條件及舊三筆低對比紀錄分開保存，不當成當前畫風品質通過。
  - 2026-10-23：新增固定來源、排他／可追溯 header 轉換、單組工具與 10 項後端／2 項瀏覽器回歸；615 後端（1 跳過）、建置／契約及 93 Chromium 通過。14 份報告停引擎／平台重啟後僅 GET 核對，正式 DATA 八檔 hash 不變。見 [L01 實測與限制](docs/validation/style-matrix-20261023.md)。
  - 圖片提醒：優先沿用 R05 已確認的畫風目標圖；換畫風或樣本不足時，品質比對前主動提醒使用者補齊，見 [圖片提供提醒](docs/anime-style-development.md#image-input-reminders)。

### R01

<a id="r01"></a>

- [x] **R01 · depth／pose 等其他結構參考流程**
  - [x] 驗收 R01-01：逐種核對前處理、控制模型、架構、版本與條件；Canny 的既有驗收不代表其他類型可用。
  - [x] 驗收 R01-02：完成各流程的提交、快照、結果、精確設定還原及實機驗收。
  - 2026-10-23：SDXL pose／depth v3、固定 aux／估計器與控制權重，兩種 RTX3060 唯一生成、同次條件圖／作品及完整還原通過；動漫骨架缺漏、姿勢偏離及深度構圖分界保留。見 [R01 操作與證據](docs/structure-reference.md)。

### R02

<a id="r02"></a>

- [x] **R02 · 畫風與角色參考 adapter**
  - [x] 驗收 R02-01：固定 SDXL Plus ViT-H／編碼器／節點，接入單張嚴格流程、元件登記、來源／224 方圖前處理及完整快照；權重 0／0.6／1 與兩個精確 seed 分開比較。
  - [x] 驗收 R02-02：使用已確認的棕髮綠眼角色，另外比較肖像／書店／公園，12 組 RTX 3060 原圖保存；保留粉髮、服裝帶入、雙人、張傘與背景弱化，不保證身份鎖定或作者畫風完全重現。
  - 2026-10-23：630 項後端（1 既有跳過）、建置／契約與 97 Chromium 通過；12 報告停引擎／改登記／平台重啟後只 GET，1440px／390px 實際下載與精確權重／seed 還原通過，正式 DATA 八檔 hash 不變。見 [R02 證據與限制](docs/validation/reference-adapter-20261023.md)。本輪沒有訓練，每次只用一張參考；22 檔／20 不同內容與 6 張保留評估見 [圖片用途](docs/validation/reference-inputs-20261023.md)。
  - 圖片提醒：真實畫風驗收前核對參考／保留評估圖，缺少時提醒使用者提供；角色驗收另確認同一角色的圖片，不借用不同角色的畫風樣本。見 [圖片提供提醒](docs/anime-style-development.md#image-input-reminders)。

### R03

<a id="r03"></a>

- [x] **R03 · 專用 inpainting 模型與更多羽化／修補品質**
  - [x] 驗收 R03-01：選定並核對專用模型來源與相容性；完成載入、生成、保存及還原驗證。
  - [x] 驗收 R03-02：比較更多素材、半徑與 seed 的接縫、邊界融合及遮罩外保留，保留色偏／截斷等觀察。
  - 2026-10-23：固定 Fooocus head／v2.6 patch＋Animagine，六組專用修補／兩組一般 v2 對照通過生成、唯一作品與完整還原；引擎停止後八組 GET／hash 核對通過。遮罩外像素差皆 0，但 Fooocus 未優於一般修補，色塊／色偏及提示偏離保留；維持實驗選項而非預設。見 [R03 操作](docs/fooocus-inpainting.md)、[逐圖驗收](docs/validation/fooocus-inpainting-20261023.md)。

### R04

<a id="r04"></a>

- [x] **R04 · Pony 搭配 Canny v2 及其他 LoRA 的實測**
  - [x] 驗收 R04-01：另以 Pony v2 完成無 LoRA、IKEA、LCM、LCM → IKEA 與反向五組 RTX 3060 實測，固定控制權重、原素材、seed、各組取樣條件及順序／強度；不借用舊模型證據推定通過。
  - [x] 驗收 R04-02：五份原邊緣／完整 workflow／唯一作品／快照與設定還原通過；1440px／390px 實際下載、引擎離線／改登記／平台重啟核對不重送。各組另記中空材質與平面線框等品質限制，未建立品質推薦。
  - 2026-10-23：新增單次驗收 CLI、固定可重跑椅子 fixture 及精簡證據 JSON；5 任務／5 作品／5 原邊緣、零自動重試，正式 DATA 8 檔 hash 不變。見 [R04 驗收與限制](docs/validation/pony-canny-v2-20261023.md)。

### R05

<a id="r05"></a>

- [x] **R05 · 更多模型、seed、素材與作者提示格式的品質比較**
  - [x] 驗收 R05-01：獨立動漫 v1 測試集、正／反向完整文字比較與單組 CLI；Pony／Animagine 三題材、兩個精確 seed、品質標籤與兩種新素材 denoise 0.3／0.6，共 18 件 GPU 原圖及完整設定／版本／hash 保存。
  - [x] 驗收 R05-02：逐圖記錄提示服從、角色一致、畫風與構圖；保留雙人、開書、裁切及高 denoise 臉／手扭曲等失敗。18 份報告停引擎／平台重啟後僅 GET 核對；有限基準不代表全面模型、作者畫風或角色品質通過。
  - 2026-10-23：6 項新增後端及 1440px／390px 操作驗收，完整 605 項後端（1 跳過）、建置／契約與 91 項瀏覽器通過；正式 DATA 八檔 hash 不變。見 [R05 證據與限制](docs/validation/anime-baseline-20261023.md)。
  - 圖片提醒：指定作者／畫風品質比對前主動核對使用者的目標圖與資料分組；缺圖時可先做無參考基準，該畫風品質保持待驗收。見 [圖片提供提醒](docs/anime-style-development.md#image-input-reminders)。

### R06

<a id="r06"></a>

- [x] **R06 · 更多模型／工作流程／參數比較軸**
  - [x] 驗收 R06-01：新增 checkpoint 模型、sampler_name、scheduler 三軸，涵蓋文生圖／單張圖生圖；單一變因最多 8 組。schema 2 保存原模型登記與完整設定，舊六軸 schema 1 不改寫。
  - [x] 驗收 R06-02：保存／匯入／匯出、逐組載入與任務／作品／報告追溯通過；生成交易核對原登記，原 UUID 恢復不重送，未生成組保持空，無自動批次／重試／品質評分。
  - 2026-10-23：9 項新增後端整合及 1440px／390px 瀏覽器操作，保留精確 seed、停用 LoRA、原素材與未知版本；來源快照非權重驗證。邊界與證據見 [R06 驗收](docs/validation/extended-comparisons-20261023.md)。

### R07

<a id="r07"></a>

- [x] **R07 · 局部編輯／結構流程的一般草稿、設定交換及比較方案評估**
  - [x] 驗收 R07-01：評估專用格式與能力描述，完整保存雙輸入、羽化／控制參數及版本；不借用舊格式丟棄資訊。
  - [x] 驗收 R07-02：支援時另驗證保存／匯入／還原／比較；尚未支援時維持明確拒絕與完整 workflow 下載。
  - 2026-10-23：完成四版本的專用格式方案、唯讀能力 API 與桌面／390px 工作台說明；目前三種操作維持不支援。修正一般草稿默默丟棄遮罩／控制參數的問題，POST／PUT、交換及比較明確拒絕且不部分寫入；有限保留既有回讀封套相容。四版本原任務／作品完整還原及 workflow／64 位 seed 保留通過。R07 是評估及拒絕邊界驗收，不表示專用草稿／交換／比較已上線；見 [R07 決策與證據](docs/specialized-workflow-formats.md)。

### T01

<a id="t01"></a>

- [x] **T01 · 確認實際訓練需求**
  - [x] 驗收 T01-01：依 R02 偏差決定畫風／角色分開的 SDXL UNet LoRA 候選，固定 Animagine 基底身分、用途／排除範圍、兩路徑各 12 件未來比較及四面向人工判準；推論參數、參考圖、資料準備與實際權重更新明確區分。
  - 2026-10-23：需求 v1 與圖片提醒／曝光界線完成，未安裝 trainer、未訓練或新增 GPU 工作；T02 之後仍依使用者排序 R01 → R03，T03／T04 另排。見 [訓練需求](docs/training/requirements.md)、[T01 驗收](docs/validation/training-requirements-20261023.md)。
  - 圖片提醒：決定試訓後依 T02 缺項提醒使用者完成審查或補齊訓練／獨立評估圖；需求討論不要求先備齊訓練集。

### T02

<a id="t02"></a>

- [x] **T02 · 資料集、標註、版本與訓練工具介面評估**
  - [x] 驗收 T02-01：完成 v1 清單／Schema、單行 caption／角色／來源審查、原作分組／固定分割／曝光、版本 hash 與本機檢查／不可覆寫出口；評估固定 sd-scripts 資料介面並保留可追溯紀錄。
  - 2026-10-23：既有 22 檔各建畫風／角色清單，10 張訓練候選、6 張開發評估、6 張排除；caption／來源與角色身分未完成，真實資料出口正確拒絕。合成資料出口與驗證通過，沒有安裝 trainer 或開始訓練。見 [契約與操作](docs/training/dataset-contract.md)、[工具介面](docs/training/tool-interface-research.md)、[T02 驗收](docs/validation/training-dataset-20261023.md)。
  - 圖片提醒：實際訓練前核對每種畫風的訓練／評估分割、標註與來源，先沿用適用的既有資料，只提醒補齊缺少部分；T04 最終驗收另確認保留集未被反覆調參使用。見 [圖片提供提醒](docs/anime-style-development.md#image-input-reminders)。

### T03

<a id="t03"></a>

- [x] **T03 · 訓練獨立環境與 GPU 資源協調**
  - [x] 驗收 T03-01：規劃與平台／推論分離的環境，驗證佔用與釋放、衝突及失敗恢復。
  - [x] 驗收 T03-02：記錄訓練專用資源需求，與 E04 聯動，不讓訓練干擾既有生成任務。
  - 2026-10-25：固定獨立 Windows trainer／依賴／tokenizer，提供封存 run、明確停止／完整狀態續訓及本機生成互斥；RTX 3060 自製幾何資料實測拒絕衝突、停止釋放及新 UUID 續訓至 step 3。上游步數重設失敗保留，修正後核對最終 state。作者圖片未訓練，1024／RTX 4080／畫風品質與 E04 其餘工作負載未認列。見 [操作](docs/training/runtime.md)、[實測與資源](docs/validation/training-runtime-20261025.md)。

### T04

<a id="t04"></a>

- [x] **T04 · 訓練產物回登與評估**
  - [x] 驗收 T04-01：定義模型庫回登、來源／版本／hash／訓練條件及固定比較流程，保存品質限制。
  - 2026-10-25：T03 `db7ab91` 先 commit／push 後實作；完整產物／狀態驗證、來源 sidecar、原生 LoRA 模型庫回登、三題材兩 seed 的 12 格比較與人工模板完成。合成 LoRA 在 RTX 3060 原生載入、保存及引擎離線查回／完整還原通過；只實際生成兩件技術案例，作者品質與最終保留圖仍未認列。見 [操作](docs/training/artifacts.md)、[技術驗收](docs/validation/training-artifacts-20261025.md)。

<a id="v01-01"></a>

### V01-01 · 已完成的遮罩操作驗收

- [x] 驗收 V01-01：實際操作筆刷、擦除、反相、PNG 載入與保存，核對縮放座標及未保存保護。

2026-10-23 的 [瀏覽器驗收](docs/validation/mask-editor-20261023.md)已完成；V01-02 實機觸控與 V01 主項仍留在 ROADMAP，沒有因移動而關閉。
