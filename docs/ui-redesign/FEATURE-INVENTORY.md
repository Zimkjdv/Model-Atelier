# 既有功能保留對照表 · UI 提案 v3

日期：2026-10-27。這是讀取目前 Vue 元件、型別與頁面組合後的設計盤點，不是執行每項功能的測試報告。本次沒有修改正式前後端。

## 本次修正結論

上一版將「資訊分層」做成過度摘要，預覽確實漏了重要現有內容：主機 RAM、每張 GPU 顯存與驅動、多磁碟與目錄清單、開啟資料夾、引擎版本及裝置、本機安裝檢查，以及可編輯的額外模型路徑。這些均為既有能力，不應列為新增功能，也不應只用一個「查看資訊」按鈕代替。

本版恢復深色。系統資訊以可直接看到的五個區塊保留主體資料：平台主機 → 選定引擎 → 目錄與容量 → 本機安裝檢查 → 部署與存取。頁內連結可快速定位，不另藏在設定或層層選單。

預覽覆蓋標記：**具體展示**＝HTML 有對應欄位／版位；**摘要展示**＝HTML 有命名入口與保留清單，完整行為未模擬；**規劃保留**＝以下列明位置，HTML 尚無完整控制。所有展示值均為示意。

## A. 平台主機與執行環境（原有功能，必須保留）

| ID | 原始元件／依據 | 原有資訊或操作 | 新版位置／顯示規則 | 預覽 |
| --- | --- | --- | --- | --- |
| E01 | App.vue | 主機名稱、原生／容器範圍、每 15 秒更新、時間與過期狀態 | 系統→平台主機標頭；錯誤保留上次快照 | 具體展示 |
| E02 | App.vue | 每張 GPU 索引、名稱、顯存可用／總量／已用、使用條、驅動 | 平台主機 GPU 卡；多張各自呈現，GPU 錯誤不遮住 RAM／磁碟 | 具體展示一張；多卡規則保留 |
| E03 | App.vue | RAM 可用／總量／已用與使用條 | 平台主機 RAM 卡，首個區塊直接可見 | 具體展示 |
| E04 | App.vue | 平台資料所在磁碟的可用／總量／已用 | 平台主機磁碟卡，不以籠統百分比取代容量 | 具體展示 |
| E05 | App.vue | OS、平台 Python、資料目錄 | 平台主機資訊列，完整路徑可換行 | 具體展示 |
| E06 | EngineEnvironment.vue | URL、查詢時間、/system_stats 來源、available／offline／invalid、連線設定入口 | 系統→選定引擎標頭；URL 不符不得顯示舊引擎資料 | 具體展示；invalid 規則保留 |
| E07 | EngineEnvironment.vue | ComfyUI、Python、PyTorch、CUDA runtime、CUDA 是否可用、驅動 | 引擎版本資訊格，預設展開，未知保持未知 | 具體展示 |
| E08 | EngineEnvironment.vue | 引擎 OS、RAM 已用／可用／總量 | 引擎區，不混進平台 RAM 卡 | 具體展示 |
| E09 | EnvironmentDevices.vue | 各裝置名稱、類型、索引、VRAM 總量／可用／已用、Torch 記憶體 | 引擎逐裝置卡；Torch 細節可折疊 | 具體展示一張 |
| E10 | EngineEnvironment.vue、environmentTypes.ts | 執行裝置 available／unavailable／unknown、來源、時間、原因與 CPU 有效性 | 引擎狀態列；未知不能推定無 GPU，提交時仍查原引擎 | 具體展示＋規則說明 |
| E11 | LocalEnvironmentCheck.vue | 明確檢查按鈕、本機 Python 路徑、上次檢查、timeout／unavailable／warnings | 系統→本機安裝檢查，保留獨立操作，不跟即時引擎混在一起 | 具體展示 |
| E12 | LocalEnvironmentCheck.vue、EnvironmentDevices.vue | 本機 Python、Torch、CUDA 建置版本／可用、驅動、裝置與 Torch 記憶體 | 本機安裝檢查版本格及裝置詳情；容器顯示不可檢查 Windows 的原因 | 具體展示未知值＋裝置摘要 |
| E13 | DeploymentStatus.vue | 本機／容器存取模式、平台資料位置角色、本機／外部引擎、URL、更新按鈕、信任邊界 | 系統→部署與存取 | 具體展示 |

## B. 目錄與磁碟容量（原有功能，不能簡化成單一百分比）

| ID | 原始元件 | 原有資訊或操作 | 新版位置／顯示規則 | 預覽 |
| --- | --- | --- | --- | --- |
| S01 | StorageOverview.vue | 合計可用／總容量、可讀磁碟區數、partial、快照時間、更新容量 | 系統→目錄與磁碟容量標頭＋摘要 | 具體展示 |
| S02 | StorageOverview.vue | 依 volume 分組、磁碟路徑、目錄數、使用比例、可用／總量、低容量狀態 | 每個磁碟獨立卡；同磁碟多目錄不重複合計；≥90% 沿用警示 | 具體展示兩個磁碟；低容量規則保留 |
| S03 | StorageOverview.vue、backend/storage.py | 目錄 role、登記 path、resolved_path、尚未建立／不可讀／錯誤、未知磁碟分組 | 磁碟卡內逐目錄顯示，其他目錄保留獨立組 | 具體展示路徑；異常摘要 |
| S04 | StorageOverview.vue | 開啟資料夾、can_open、Windows 限定、操作中停用、成功／失敗回應 | 每個目錄右側按鈕；後續保留 directory_id＋expected_path 核對，無能力時說明原因 | 具體展示，原型不開檔案總管 |
| S05 | LocalModelPaths.vue | 額外 checkpoint 目錄可編輯、每行一個最多 8 個、保存、重新讀取 | 設定→模型路徑；系統目錄區提供入口；保留既有可編輯能力 | 具體展示 |
| S06 | LocalModelPaths.vue | dirty／版本衝突、保留輸入／確認捨棄、修訂時間、套用狀態未確認 | 模型路徑表單旁；不得靜默取代使用者輸入 | 摘要展示 |
| S07 | LocalModelPaths.vue | 預設路徑固定保留、額外路徑順序、目錄狀態、各磁碟總量／可用 | 設定→已保存目錄與磁碟狀態 | 具體展示 |
| S08 | LocalModelPaths.vue | 僅受管理的本機 ComfyUI 生效、遠端不適用、手動重啟後同步、同名優先順序 | 表單附近保留，不收進無名稱的「更多」 | 具體展示 |

**實際目錄集合**：已核對 `backend/storage.py`，固定為平台資料、參考素材、作品庫輸出、受管理本機 checkpoint、受管理本機 ComfyUI 輸出，再加已登記的額外 checkpoint。預覽依此集合補齊，不憑空以專案根目錄取代。

**容量語意**：現有 UI 顯示的是目錄所在磁碟的容量，不是遞迴計算資料夾本身佔用大小。若日後增加資料夾大小統計，要另列 N 項並評估掃描成本、符號連結、快取與取消；此次不假裝已提供。

## C. 其他頁面逐項保留核對

| ID | 原始元件 | 必須保留的功能 | 規劃位置 | 預覽 |
| --- | --- | --- | --- | --- |
| C01 | navigation.ts、App.vue、UnsavedChangesNotice.vue | 七主頁、五 mode、舊 URL／返回／重整、dirty 離開保護、KeepAlive | 共用框架；新增實驗入口不能破壞現有路由 | 導覽具體；生命週期規劃保留 |
| C02 | CreationStudio.vue、FluxStudio.vue、FluxExtensionStudio.vue | 新建／載入／保存草稿、支援流程區分、待確認請求 | 工作台頁首草稿列，依實際能力提供 | 摘要展示 |
| C03 | SettingsTransfer.vue、WorkflowFormatSupport.vue | 設定 JSON 匯入／匯出、套用前確認、原始參數、各版本支援範圍 | 工作台「設定交換與支援範圍」入口 | 摘要展示 |
| C04 | CreationStudio.vue、LoraControls.vue | 模型預設差異確認、提示詞／負面詞、尺寸、seed 字串、sampler／scheduler／steps／CFG、最多四個有序 LoRA | 基本設定＋具名進階區；不能因折疊丟值 | 基本具體；全集摘要 |
| C05 | ModelValidation.vue、LoraValidation.vue、StackValidation.vue、GenerationAdvice.vue | 模型／LoRA／有序組合實測、資源建議、驗證條件 | 工作台「相容性與實測」；阻擋原因就近顯示 | 摘要展示 |
| C06 | ImageInput.vue、AssetChoices.vue、ReferenceSnapshot.vue | 單張圖生圖輸入、素材搜尋／分頁、用途與來源快照 | 素材選擇器與輸入卡；整理用參考素材不混同實際推論輸入 | 摘要展示 |
| C07 | InpaintStudio.vue、MaskEditor.vue、InpaintBlendPreview.vue | 遮罩筆刷／擦除／反相／PNG、羽化與合成預覽、v1／v2／Fooocus v3 | 局部修補畫布與設定；完整原設定還原不變 | 畫布版位＋摘要；筆刷未模擬 |
| C08 | ControlStudio.vue、CannyPreview.vue、ControlEdgePreview.vue、StructureOutput.vue | Canny CPU 預覽、參數、預覽來源 hash、pose／depth、實際條件圖／原圖還原 | 結構引導輸入與條件圖，原任務詳情保留結果 | 摘要展示 |
| C09 | ReferenceStudio.vue、ReferenceComponents.vue | 單張 adapter、畫風／角色模式、強度、元件／相容性、來源快照 | 參考任務；不承諾身份鎖定 | 基本具體；元件摘要 |
| C10 | FluxStudio.vue、FluxExtensionStudio.vue | 專用四元件、精度／裝置、LoRA 與 VAE 圖生圖、專用草稿及還原 | 工作台架構選擇下的 FLUX 專屬設定，不能共用 SDXL 全部欄位 | 摘要展示 |
| J01 | GenerationPanel.vue | 歷史任務列表、較舊分頁、更新、進度、錯誤、原 UUID 恢復 | 畫布下任務區；完整列表入口與詳情 | 摘要展示 |
| J02 | GenerationPanel.vue | 取消排隊／條件化停止及確認、載入原設定、原 workflow 下載、待匯入入口 | 任務操作列，依狀態顯示，不因美化刪掉 | 摘要展示 |
| J03 | JobMeasurements.vue | 提交至終態／引擎耗時、提交前資源、連續取樣起訖／來源／成功失敗／間隔缺口／最高觀察／最近點／結束原因 | 任務詳情與作品詳情的「耗時與資源」 | 摘要展示；不是任務專用峰值 |
| J04 | RuntimeSnapshot.vue | 提交時版本、流程 SHA256、引擎依賴、裝置、效能條件／精度旗標／卸載／平台套件 | 任務／作品的歷史來源區；不以目前環境回填 | 摘要展示 |
| G01 | ArtworkLibrary.vue | 搜尋、排序、分頁、收藏、封存／還原、標題／筆記／人工評分、縮圖及大圖 | 作品工具列、卡片、詳情管理區 | 基本具體；部分摘要 |
| G02 | ArtworkLibrary.vue | 明確匯入／補齊圖片、原圖／workflow 下載、載入支援流程原設定 | 作品匯入入口及詳情操作 | 摘要展示 |
| G03 | ArtworkComparison.vue | 最多四張比較、移除單張／清空選擇、並排檢視 | 作品庫選取列＋比較區；與參數實驗不是同一功能 | 摘要展示 |
| G04 | 各 *Snapshot.vue、ControlEdgePreview.vue、StructureOutput.vue | 模型、四元件、ControlNet、adapter／編碼器、LoRA、素材前處理、原實驗與條件圖 | 作品詳情→來源與生成設定，具名分類，不合併成一段泛稱來源 | 摘要展示 |
| A01 | AssetLibrary.vue | 單張上傳、正規化／格式限制、名稱／用途編輯、封存／還原、搜尋／分頁、尺寸大小／版本 | 素材工具列、卡片詳情及編輯操作 | 基本具體；管理摘要 |
| M01 | ModelLibrary.vue、LoraLibrary.vue、ControlLibrary.vue、ReferenceComponents.vue、FluxComponentLibrary.vue | 分類同步、搜尋篩選、架構版本登記、相容性說明、來源／授權／大小／hash | 模型分類頁，明確保留編輯登記而非只看卡片 | 卡片具體；編輯摘要 |
| M02 | FluxPlan.vue | FLUX 接入準備、安裝預檢、固定元件修訂／取得條件／精度／路徑／大小／預期 hash | 模型庫 FLUX 分類的「接入準備」 | 摘要展示；同步不等於安裝驗檔 |
| X01 | ExperimentPlanner.vue、SavedExperimentPlans.vue | 固定案例、比較軸與組數、方案保存／列表／JSON 匯入匯出／確認、逐組載入 | 實驗比較獨立入口，沿用原能力 | 矩陣具體；方案管理摘要 |
| X02 | ExperimentResults.vue、ExperimentReport.vue、ExperimentSnapshot.vue | 任務關聯、各組多次 run、保存結果與原始報告、人工評估與原方案 | 實驗詳情，不能只剩「漂亮的三張圖」 | 摘要展示 |
| T01 | TrainingDatasets.vue、TrainingReviewNavigator.vue | T02 清單匯入、資料集／版本、逐圖 caption／來源／角色／分組、缺項定位、圖片前後導航、出口驗證與 train-only 匯出 | 訓練資料審查與出口兩階段，版本不可變 | 部分具體；清單／角色欄位摘要 |
| T02 | TrainingControl.vue | 凍結設定、明確準備／開始／停止／續訓、原 UUID 恢復、互斥、資源日誌、receipt、安裝／回登／固定比較 | 訓練執行與產物階段，不能只有進度條 | 部分具體；控制全集摘要 |
| T03 | TrainingReport.vue | 選擇原 run、讀取紀錄與診斷報告、下載相同快照 | 訓練「原 run 報告」入口 | 摘要展示 |
| P01 | DiagnosticsPanel.vue | 唯讀狀態檢查、請求／任務識別、JSON 安全預覽與下載 | 設定→診斷 | 具體展示操作版位 |

## 實作前後的保留驗收

1. 本表每列是必須保留的既有能力；「摘要展示／規劃保留」不是刪除授權。正式實作前補齊該頁細節設計，再逐列驗收。
2. 五個系統區塊及主機 RAM／GPU／磁碟、引擎版本、每磁碟／目錄清單應預設可見；只有 Torch 細節、原始紀錄等適合折疊。
3. 保留來源、時戳、錯誤、未知、過期、不可用與容器／遠端邊界。連線成功不代表診斷回報可用，更不代表模型可執行。
4. 涉及操作的每列，除入口存在外還需驗證原狀態／確認／錯誤恢復行為；不得用 toast 代替正式功能。原型 toast 僅表示展示用途。
5. 正式改版需針對 `storage-overview`、`deployment`、`container-deployment`、`execution-device` 相關既有測試及受影響各流程做回歸；本次只驗 HTML，不宣稱後端已驗證。
6. 若後續發現未列出的既有控制，先補本表並保留原行為，不能因這份盤點沒有提及就移除。此表是目前已核對的可見元件／能力，不宣稱已遍歷所有條件分支。

## v3 預覽覆蓋更新

以使用者提供範例統一外觀後，A／B 章系統與目錄功能仍完整保留。新增具體可操作展示：作品瀑布流／固定排版、模型篩選、收藏／封存／還原、最多四張並排比較、詳情尺寸與 MP、素材帶入相容目的、模型對應尺寸、步數／完整 uint64 Seed 驗證、基本遮罩筆刷／擦除／清除與鍵盤中央區塊。遮罩跨流程保留，本頁重整才重設。

前述功能僅操作原型記憶體；下載、設定交換、完整進階參數、訓練與專用工作流仍按表內摘要／規劃保留，不宣稱完整實作。整體風格來源與有意未照搬的規則見 INTEGRATION-NOTES.md。

v3 補充：草稿／設定交換、相容性／實測、任務／歷史已提供具名視窗與操作入口，不只放在頁尾對照摘要。完整行為仍以既有契約實作；取消、停止、下載與生成均不在原型執行。
