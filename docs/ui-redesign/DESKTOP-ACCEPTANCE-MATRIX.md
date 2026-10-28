# 桌面子分類、階段與創作支援驗收

日期：2026-10-29。基準為已核准的 [preview.html](preview.html)，本輪沒有修改原預覽，也沒有新增手機版範圍。正式版額外資訊與安全限制保留；下列必要差異另行說明，不以修改基準或隱藏控制項認列完成。

預覽檔 SHA-256：`f88076148aab2ff1471137f7b60a1be55c72c0d0f1219e52f981c462c9e76433`。九份分類／階段紀錄均核對同一 hash，Git 中預覽檔無變更。

## 驗收層級與結果

| 層級 | 本輪實際驗證 | 不代表的範圍 |
| --- | --- | --- |
| 桌面操作與樣式 | 1280×800、1440×900、1920×1080；模型 30 格、訓練 12 格、目的／架構 30 格，共 72 格 | 沒有宣稱每個文字區塊高度逐像素相同或全站人工無障礙認證 |
| 預覽回歸 | 五個創作圖示的 SVG 元素、路徑與尺寸；三尺寸既有主區塊幾何、側欄、設定／素材／作品／系統與創作空舞台檢查 | 幾何比對不是資料、任務或推論成功證據 |
| 後端支援契約 | 專用流程格式限制、FLUX 附加流程與模型 profile 共 23 項測試通過 | 模型登記、列出權重或通過契約不等於權重／相容性／品質已驗證 |
| 既有實機紀錄 | 連結下方各流程原紀錄，保留其硬體、版本與配置界線 | 本輪沒有重新執行 GPU 生成、trainer、權重下載或安裝 |

完整量測、每格版型與資料筆數、訓練資料集／匯出／合成 run 身分，以及預覽 hash 見 [機器可讀證據](desktop-acceptance-evidence.json)。測試程式見 [desktop-acceptance-matrix.spec.ts](../../frontend/tests/desktop-acceptance-matrix.spec.ts)。

## 一、模型五類 × 兩種版型

「通過」包括：分類切換、兩版型可見且資料名稱相同、正確的分類同步端點實際回覆成功、卡片三欄、左右位置／寬度與原預覽相符、卡片背景／框線／圓角相符，以及無整頁水平溢出。每類另測未保存版本文字在清單／卡片間保留、編輯時同步停用、取消後恢復同步。

| 子分類 | 版型 | 1280×800 | 1440×900 | 1920×1080 | 分類專用同步 |
| --- | --- | --- | --- | --- | --- |
| Checkpoint | 清單 | 通過 | 通過 | 通過 | `/api/models/sync` |
| Checkpoint | 卡片 | 通過 | 通過 | 通過 | 同上 |
| LoRA | 清單 | 通過 | 通過 | 通過 | `/api/loras/sync` |
| LoRA | 卡片 | 通過 | 通過 | 通過 | 同上 |
| 結構控制 | 清單 | 通過 | 通過 | 通過 | `/api/controlnets/sync` |
| 結構控制 | 卡片 | 通過 | 通過 | 通過 | 同上 |
| 元件 | 清單 | 通過 | 通過 | 通過 | `/api/reference-components/sync` |
| 元件 | 卡片 | 通過 | 通過 | 通過 | 同上 |
| FLUX 元件 | 清單 | 通過 | 通過 | 通過 | `/api/flux/components/sync` |
| FLUX 元件 | 卡片 | 通過 | 通過 | 通過 | 同上 |

使用真正隔離 FastAPI 清單與 metadata：Checkpoint、FLUX／LoRA 登記及結構／參考元件同步皆由合成引擎提供，不以瀏覽器把一份假清單回給五類。FLUX 保留 diffusion model、text encoders、VAE 分組，四個生成角色沒有被合成單一 Checkpoint。同步不下載或安裝權重。

原有來源、版本、授權、SHA256、檔案大小、架構及相容性／驗證工具保留在具名詳情或原登記表單。清單預設與深色方向不變。本輪驗收當次切換，不宣稱 N06 跨次偏好保存完成。

## 二、訓練四階段分別驗收

每個尺寸都透過檔案選擇器匯入一份新的三圖審查清單，捕捉該次匯入回覆的 UUID；階段 1、2 沿用同一資料集與修訂，階段 3、4 沿用該匯出 UUID 及明確標記的合成 run。沒有拿清單第一筆或另一組資料冒充目前表單。

| 階段 | 驗收操作／限制 | 1280×800 | 1440×900 | 1920×1080 |
| --- | --- | --- | --- | --- |
| 1 審查資料 | 三欄審查版型及階段列對照原預覽；只顯示待補預設勾選；標註與來源依據可編輯；1→2→1 保留未保存內容；取消切往控制階段保留原頁；保存並看下一張後修訂從 1 變 2 | 通過 | 通過 | 通過 |
| 2 匯出資料包 | 有待補或未保存時不可匯出；保存後真實後端出口檢查通過，明確匯出回覆 completed；核對資料集／修訂、bundle_verified、只匯出 1 張 train 與 training_started=false，本組的 validation／excluded 不加入訓練 | 通過 | 通過 | 通過 |
| 3 準備訓練 | 保留獨立環境檢查、已封存資料包、訓練 seed `4294967295`、總步數與保存間隔；3→4→3 保留設定；只有明確按準備才送出一次 prepare；使用階段 2 的匯出身分 | 通過 | 通過 | 通過 |
| 4 執行與產物 | 兩欄摘要與原預覽對照；讀取同一合成 run；0 步不當未知，5 步呈現實際進度，更新失敗保留快照，缺乏步數顯示未知並移除百分比；原 run／日誌／產物控制仍在下方 | 通過 | 通過 | 通過 |

前兩階段是實際審查保存與資料包匯出。本輪三圖樣本含 train、validation、excluded；test 最終評估圖不預覽／不匯出的既有規則保留，但未在本矩陣重新建立 test 樣本。準備／環境／run 回覆由頁面路由注入，以免啟動真實 trainer；回覆中的資料集與匯出身分來自前兩階段，配置也核對本次準備內容。三個尺寸的 `/start` 呼叫均為零，生成提交數亦不增加。合成狀態不認列為真正準備或完成訓練。

本輪沒有重新執行停止／新 run 續訓／產物安裝；其既有能力與驗收紀錄保留於 [訓練控制](../validation/training-control-20261025.md)、[訓練產物](../validation/training-artifacts-20261025.md) 及原有測試。

## 三、五種創作目的 × Checkpoint／FLUX

表內「介面通過」指已測目的選取、實際路由／表單、所需控制、共用圖示與設定欄寬度、生成按鈕位於視窗內、無水平溢出及不自動提交；不將缺少素材、元件或 metadata 的流程寫成可立即生成。三種桌面尺寸均通過下列每一列。

| 目的 | Checkpoint 實際支援與本輪介面驗收 | FLUX 實際支援與本輪介面驗收 |
| --- | --- | --- |
| 文字創作 | SD 1.x／SDXL 一般 Checkpoint 工作台；`text2image`。介面通過 | Schnell 分離四元件 `flux1-schnell-text2image-v1`；獨立提示詞與草稿。介面通過 |
| 圖片重繪 | SD 1.x／SDXL 單張 VAE 圖生圖；`image2image`。來源、縮放與 Denoise 仍需明確設定。介面通過 | 獨立 `flux1-schnell-image2image-v1`；固定 512×512／4 steps／FP8 e4m3fn／CPU 編碼器，Denoise 必須小於 1；填 1 顯示欄位錯誤並阻擋生成。介面通過 |
| 局部修補 | 一般雙輸入／內側羽化 v2，以及 Fooocus SDXL 專用 v3，版本及對應元件分開。可切兩者；來源／遮罩不足時阻擋生成；保留遮罩編輯與生成結果切換。介面通過 | 沒有 FLUX 修補流程。點目的會進入獨立 Checkpoint 修補頁，須明確選相容模型與素材；沒有 FLUX 轉換或提交，原 FLUX 表單保留。未支援狀態通過 |
| 結構引導 | Canny 配對 SD 1.x／SDXL；Pose／Depth 是 SDXL 專用 v3，需匹配 ControlNet 及預處理器。三種可切換，結構預覽入口保留。介面通過 | 沒有 FLUX ControlNet／Pose／Depth 接入。目的導向獨立 Checkpoint 結構頁，不沿用 FLUX 權重。原 FLUX 表單保留；未支援狀態通過 |
| 風格參考 | SDXL 的 IP-Adapter Plus ViT-H 與匹配 CLIP Vision；畫風／角色外觀兩模式分開。兩模式可切，元件與來源不足仍阻擋。介面通過 | 沒有 FLUX Redux／IP-Adapter 畫風或角色流程。目的導向獨立 Checkpoint 參考頁；不把 VAE 圖生圖當成身份／畫風鎖定。原 FLUX 表單保留；未支援狀態通過 |

FLUX 的三個未支援格子是「確認沒有誤轉換／誤提交」，不是功能完成。從其獨立工作台返回時原提示詞仍保留，所有目的切換均不增加引擎提交。

FLUX 的 PVC model-only LoRA 是五目的以外的額外獨立流程，並非「風格參考」等同物；其固定版本、強度與配置限制、一般草稿拒收及不可與圖生圖混用仍保留。本輪後端契約測試涵蓋此界線，沒有重新認列 LoRA 推論品質。

### 可保存與交換的格式界線

| 流程群 | 草稿／參數交換 | 其他保留能力 |
| --- | --- | --- |
| 一般 Checkpoint 文字／圖片重繪 | 沿用一般草稿與設定交換 | 精確 uint64 Seed、修訂、來源與完整 workflow |
| Schnell 純文生圖 | 獨立 FLUX 草稿與對應設定交換 | 四元件來源與當次環境，不降級成 Checkpoint |
| FLUX 附加 LoRA／VAE 圖生圖 | 獨立附加流程草稿；一般交換與比較方案不收不支援格式 | 原 UUID、完整參數、來源／元件快照與 workflow |
| 專用修補／結構／畫風角色 | 一般草稿、設定匯出／匯入與比較方案仍未開放專用格式 | 可載入完整已保存設定、下載完整 workflow；不捨棄雙輸入、羽化、控制參數或來源。workflow 本身不包含圖片 |

後端 `/api/reference-workflows/support` 是平台格式能力聲明，不是對當前引擎的檔案／節點即時認證。23 項本輪後端測試核對未支援格式會明確拒絕，未透過改 UI 認列為已接通。

### 既有實機證據與本輪界線

- Checkpoint 主舞台的正式實圖沿用 [G01–G04 紀錄](PRIMARY-FLOWS-IMPLEMENTATION.md) 中指定任務及配置；本輪沒有再生成。
- 修補、羽化與 Fooocus：見 [一般修補](../validation/checkpoint-inpaint-rtx3060.md)、[羽化修補](../validation/inpaint-feather-rtx3060.md)、[Fooocus 專用](../validation/fooocus-inpainting-20261023.md)。
- 結構與外觀參考：見 [結構紀錄](../validation/structure-reference-20261023.json)、[IP-Adapter 紀錄](../validation/reference-adapter-20261023.md)。不擴張成所有權重或角色一致性認證。
- Schnell：見 [純文生圖](../validation/flux-generation-20261025.md)、[獨立 LoRA／VAE 圖生圖](../validation/flux-extensions-20261025.md)。既有 GPU 驗收限固定四元件、RTX 3060、512×512／4 steps／FP8／CPU 編碼器等紀錄條件；一般文生圖參數可填其他合法值，不表示那些配置已經實測。

## 四、必要差異、原因與使用者可見行為

| 差異 | 原因 | 使用者可見行為／本輪處理 |
| --- | --- | --- |
| 五個創作目的圖示路徑曾不同 | 正式版殘留相似但不相同的線條、矩形與圓形座標，不是安全需求 | 已改回原預覽路徑；SVG 子元素與 22px 尺寸比對通過，未改預覽配合正式版 |
| 模型列的垂直起點與高度可能較預覽大 | 真正同步會回覆結果；參考元件有匹配說明，FLUX 另保留檔案類別分組及準備計畫 | 清單／卡片左緣、內容寬度與三欄樣式相符；同步成功訊息及來源說明會增加上方高度。量測保留實際 y 值，不宣稱所有子分類的起點／列高相同 |
| 模型不能一律提供「套用到創作」 | 原預覽部分按鈕只有示意；正式模型／元件沒有同一套安全套用語意 | Checkpoint 可明確帶入；LoRA、ControlNet、adapter 與 FLUX 分離元件保留各自來源、登記與相容性工具，不用無作用的套用按鈕冒充功能 |
| Checkpoint／FLUX 分成獨立工作台 | 權重角色、參數、草稿與工作流程不同，不能共用 Checkpoint loader 或默默改寫原設定 | 以架構入口與專用路由區分；切換目的不提交，原表單保留。未實作的三種 FLUX 專用目的不被包裝成支援 |
| 遮罩／條件預覽及結果各有切換入口 | 正式版需保留真實畫布、遮罩保存及同次條件圖；原型只有示意互動 | 編輯器與結果共存，沒有為了大圖刪除遮罩、結構預覽或歷史來源 |
| 訓練來源欄位比原型多 | 需保存標註審查、用途依據、分組與版本，並防止最終評估圖提早曝光 | 基本欄位先顯示，補充欄位在具名詳情；待補項目與修訂實際回報，不照抄原型的 9／12 |
| 訓練摘要不是 620／1000 的展示進度 | 原型明寫該進度與審查資料無關；正式版只能使用原 run 回報 | 顯示 0、真實回報步數或未知；失敗保留上次快照。準備與開始仍是兩個明確操作，原 UUID、續訓、資源與產物入口保留 |
| 專用流程未開放一般交換／比較格式 | 一般格式可能遺失來源、遮罩或控制參數 | 顯示能力限制或拒絕處理；仍可還原完整歷史設定與下載 workflow，不部分保存或默默降級 |
| 真實結果、硬體與容量讀值不同於原型 | 示意山巒、版本、GPU 與分類容量不是真實資料 | 讀實際結果與來源；未知保持未知。N07 分類容量、N05 任務抽屜及 N06 偏好保存仍按 [獨立待辦](BACKEND-CAPABILITIES-BACKLOG.md) 列管 |

這些差異都有具體資料或契約理由。其他漏項不能以「優化」概括帶過；本輪沒有改預覽、刪除正式能力或加入手機版。

## 五、可重跑方式與證據

在 `frontend`，完成正式建置後執行：

```powershell
npm.cmd run build -- --configLoader runner
npx.cmd playwright test tests/desktop-acceptance-matrix.spec.ts
npx.cmd playwright test tests/preview-alignment.spec.ts --grep "approved HTML geometry"
```

根目錄的後端支援檢查：

```powershell
.\.venv\Scripts\python.exe -m unittest backend.test_workflow_support backend.test_flux_extensions backend.test_model_profiles -q
```

本機實際使用新的臨時 `scripts/browser_fixture.py --port 18770`，透過忽略於 Git 的 runner 設定管理服務生命週期，避免此環境先前的自動清理等待。測試本身、正式前端與隔離後端相同，沒有連正式 DATA 或真正推論引擎；完成後停止臨時服務。

本輪不同瀏覽器案例共 13 項通過：新增 1 項圖示回歸、9 項分類／階段／架構矩陣，以及既有 3 項預覽幾何。九項矩陣內是 72 格驗收，沒有把每次重跑重複計數。另有 23 項後端支援測試、正式建置及範圍內格式／型別／CSS lint 通過。不是全套瀏覽器或全套後端回歸；建置仍有主 JS 超過 500 kB 的既有提醒。

所有格子的畫面與各案 JSON 保留在 `runtime/quality/matrix-accepted/1280`、`matrix-results-large`；補齊匯出報告核對後的三組訓練最終紀錄在 `matrix-training-final`，原三尺寸幾何在 `matrix-geometry-results`。這些執行產物不進 Git。以下代表畫面與合併證據已納入版本：

| 尺寸 | FLUX 元件卡片與分組 | 訓練審查 | 專用修補工作台 |
| --- | --- | --- | --- |
| 1280×800 | [畫面](desktop-models-1280.png) | [畫面](desktop-training-1280.png) | [畫面](desktop-purposes-1280.png) |
| 1440×900 | [畫面](desktop-models-1440.png) | [畫面](desktop-training-1440.png) | [畫面](desktop-purposes-1440.png) |
| 1920×1080 | [畫面](desktop-models-1920.png) | [畫面](desktop-training-1920.png) | [畫面](desktop-purposes-1920.png) |

同一來源圖片串接生成、作品匯入、詳情、比較、離線下載、封存還原及錯誤復原的逐步紀錄，另見 [上一輪連續流程驗收](ISOLATED-JOURNEY-ACCEPTANCE.md)，不以本次頁面矩陣取代。
