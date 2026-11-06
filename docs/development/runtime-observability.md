# 執行環境、裝置與任務量測

本頁集中維護三種不同來源的觀察：提交前的環境快照、原引擎的即時裝置回報，以及任務耗時與背景資源取樣。先依下表選擇資料用途；它們不能互相代替，也不能用來保證最低硬體需求或生成品質。

| 要確認的事項 | 契約 |
| --- | --- |
| 提交前的版本、流程與效能條件 | [執行環境快照](#runtime-snapshots) |
| 原引擎目前選用的裝置與明確不可用狀態 | [執行裝置回報](#execution-device) |
| 平台／引擎耗時、提交前資源與連續取樣 | [任務量測](#job-measurements) |

<a id="runtime-snapshots"></a>

## 任務及作品的執行環境快照

新任務通過必要節點檢查後、提交 GPU prompt 前，以原引擎 `/system_stats` 保存 `runtime_metadata`。查詢最多等待兩秒；HTTP 失敗、逾時、格式無效或超過 256 KiB 的回應保持未知，不因版本未知阻擋已通過驗證的流程。引擎與架構在等待後再次檢查；若原任務被其他程序更新，修訂檢查拒絕覆蓋及提交。

快照包含：

- schema 版本及提交前觀察時間。
- 已完整匹配的標準文生圖、圖生圖或 FLUX 流程規格 ID，以及完整 JSON 的 canonical SHA256、原生節點名稱。不能匹配完整文生圖模板的原始 API 流程使用 `checkpoint-api-workflow-v1`，不假裝為七節點模板。
- 平台 Python，以及 FastAPI、Starlette、Pydantic、HTTPX、Pillow、Uvicorn、WebSockets 的實際安裝版本；只來自平台 Python 程序。
- 原引擎回報的 ComfyUI、Python、PyTorch，以及指定 Comfy 套件的 `installed`／`required` 分開欄位。未知值使用 null；不保存完整環境變數、命令列或任意套件清單。

此端點沒有提供可靠 CUDA、驅動、Git revision 及各節點版本，這些欄位保持未知；不使用平台 GPU 診斷代替遠端引擎，也不從 PyTorch 的 `+cu130` 推定運行時 CUDA。R02 與 R01 的專用模板另允許固定介面的自訂節點，所需修訂與實際版本未知分開記錄，不接受任意節點圖。

SQLite 在原任務 `validating` 且快照尚未保存時，透過一次交易凍結版本。一般更新、取消、進度、歷史刷新不能改寫它。原 UUID 恢復在任何版本查詢前回傳舊任務，不重送；新作品直接複製原任務快照，重複匯入不更新。舊任務、作品與提交前驗證失敗紀錄沒有快照時保持未知，不回填。作品預覽及載入歷史設定可查看快照；原始任務 JSON 也保留它。

快照是提交前觀察，不能證明等待佇列後引擎未更新，也不保證跨版本／硬體逐像素重現。模型、LoRA、FLUX 元件及參考圖版本仍由各自的原始快照追溯。

<a id="execution-context"></a>

### 提交時效能條件

新任務的 runtime_metadata.execution_context（schema_version 1）在既有提交前觀察交易凍結；作品沿用同一份資料，原 UUID 恢復不重新探測或更新。舊紀錄沒有此欄位時保持未知，沒有資料庫遷移或回填。

快照包含推論 workload、流程 ID、尺寸／batch 的來源、取樣節點與設定、字串精確 seed、模型／元件版本與 SHA256、有序 LoRA 原快照。圖生圖／局部編輯／Canny 尺寸取自已凍結參考設定；未知流程不猜測幾何。硬體及耗時沿用同一提交階段既有的來源分離快照，完整 graph 保持原樣。

/system_stats.system.argv 僅保留允許清單中的精度及記憶體旗標；不保存完整命令列、路徑、token、旗標值或未識別選項。衝突旗標完整保留，不選出假定有效值。缺少／無效 argv 記為未回報；空清單代表沒有明示旗標，不能推定預設精度／卸載。

實際 dtype、實際卸載與冷／熱快取目前沒有可靠的逐任務回報，分別為 null／unknown；啟動設定不能代替執行證據。既有固定驗收文件另外保存觀察到的載入精度與冷／熱條件，與一般任務的未知狀態分開。此能力不驗證訓練需求、最低 VRAM、推論品質或新 GPU 相容性。

任務／作品的提交時引擎與依賴版本區塊顯示此快照，可隨原 JSON 下載。裝置是否明確不可用由[即時裝置回報](#execution-device)判定；任務耗時與背景取樣則由[量測契約](#job-measurements)管理，不以提交前條件冒充實際執行結果。

<a id="runtime-verification"></a>

### 歷史驗證與限制

2026-10-05 的固定 Animagine／LCM RTX 3060 任務 `6e767729-a4ab-49c8-9853-4e947ad58e6a` 與作品 `1975697f-d9d0-5f71-b552-39d7c37e65ab` 保存 ComfyUI 0.34.0、引擎 Python 3.12.10、PyTorch 2.14.0+cu130 與五個 Comfy 套件；引擎停止、平台重啟後，快照、原圖、完整 JSON、精確 seed 與設定 GET 保持相同。原隔離證據記錄位置為 `runtime/style-live-data-20261005/runtime-snapshot.json` 與 `runtime/runtime-version-ui-20261005.png`；它們是當時本機證據，不是目前環境版本或正式資料新增生成的聲明。

當時另修正 Windows Python 3.12 並行建立目錄偶爾保留 `\\?\` 前綴的等價路徑誤拒絕，仍解析實體位置並核對 runtime 範圍及 symlink／junction；跨程序測試核對只有一份報告可授權生成且失敗回收全部子程序。效能條件測試涵蓋精確 seed、有序 LoRA、素材流程尺寸、未知／衝突／私密 argv 與原 UUID 不重探測。歷史通過數見 [CHANGELOG](../history/changelog.md)，不能代替目前重跑或其他硬體的驗收。

<a id="execution-device"></a>

## 引擎執行裝置回報

E01 使用正在執行的 ComfyUI 程序回報目前設定的裝置，不使用平台 GPU 型號、可用 VRAM、空 `devices` 或本機診斷快照判定另一個引擎能否執行。

### 安裝與查看

受管理本機引擎由 `scripts/start-comfyui.ps1` 在啟動前執行 `scripts/install_execution_device.py`，將本專案的 `comfyui_extensions/model_atelier_execution_device` 兩個檔案更新到受管理 ComfyUI 的同名 `custom_nodes` 目錄。其他擴充不被更動，不下載第三方程式，也不改寫 ComfyUI 原始碼；重新啟動才會載入。重新執行安裝不重寫相同內容，路徑重新導向／符號連結會拒絕。

遠端或自行啟動的 ComfyUI：將上述完整目錄放到該引擎的 `custom_nodes/` 並重新啟動；若使用 `--disable-all-custom-nodes`，需明確加上 `--whitelist-custom-nodes model_atelier_execution_device`。未安裝或被停用時保持未知，既有生成流程仍可用。這是唯讀回報擴充，`NODE_CLASS_MAPPINGS` 為空，不提供生成節點。

系統資訊顯示裝置狀態、來源與時間。此畫面是顯示快照；提交時會查詢任務原引擎，不能拿畫面上的舊結果阻擋新任務。提交時的結果保存於 `runtime_metadata.execution_device`，作品沿用原快照；舊紀錄缺此欄位時保持未知，不回填。

### 回報契約

引擎端點：`GET /model_atelier/execution-device?probe_id=<UUID>`。UUID 必須是標準小寫格式，缺少／錯誤 UUID 或額外參數回傳 400；每次查詢產生新 UUID，回應附 `Cache-Control: no-store`。

回應為 schema 1，producer 固定 `model-atelier-execution-device-v1`，包含相同 `probe_id`、`status`、`reason`、`device`（type／index）與 `backend_available`。沒有任意命令、檔案讀取或流程執行介面。

| 狀態 | 明確依據 | 新生成行為 |
| --- | --- | --- |
| available | 引擎 `get_torch_device()` 取得目前設定裝置；若該後端有受支援的 `is_available()`，沒有明確否定 | 繼續既有驗證；不是模型／顯存／品質保證 |
| unavailable / device_selection_failed | 同一引擎裝置選取函式明確發生 RuntimeError／AssertionError，無法取得設定裝置 | 保存失敗任務，HTTP 409，不上傳輸入、不送 `/prompt` |
| unavailable / backend_unavailable | 已取得的 cuda、mps、xpu、npu 或 mlu 設定裝置，其執行後端 `is_available()` 明確回傳布林 false | 同上；不是顯卡型號白名單，也不表示整台主機沒有 GPU |
| unknown | 缺擴充、離線、逾時、HTTP 錯誤、資料缺漏、錯誤 producer／版本／nonce、過大回應、未完成查詢或其他例外 | 不增加裝置阻擋，仍檢查模型、元件、架構與必要節點 |

CPU 是有效設定裝置，不因 `torch.cuda.is_available()` 為 false 而阻擋 CPU 模式。其他後端取得裝置成功時也不依名稱封鎖。只讀取選取結果與可用性，不載入模型、配置測試張量、切換裝置或啟用 CPU fallback。明確選取失敗與後端查詢不完整分開處理，原始例外不回傳。

平台查詢最多等待 2 秒，接受的回應上限 16 KiB。只採用本次 nonce 與任務原引擎的合法回報；查詢期間選定引擎改變，顯示狀態改為未知，新提交維持原有 `engine_changed` 保護。

### 任務與恢復

所有生成入口（`/api/generate`、`/api/jobs`、inpaint／inpaint-feather、control／control-edge、flux 的 generate）在既有模型／節點驗證後、輸入上傳與 `/prompt` 之前檢查即時回報。明確不可用時，`failure_info.code` 為 `execution_device_unavailable`，保留原設定、精確 seed、UUID 與證據。

原 UUID 再次提交只返回原紀錄，不重新檢查或重送。修復裝置後，載入設定並明確建立新的請求；修復後的新任務或其他引擎不受舊失敗回報影響。草稿保存、已匯入作品離線讀取、素材與 CPU 羽化預覽不經這個生成門檻。

可用性是提交前觀察，不能保證排隊後裝置仍可用，也不保證模型一定載入成功；執行期 OOM 與其他失敗仍沿用原有引擎歷史核對與診斷。預檢不替代實際 GPU 出圖測試。

### 重跑檢查

```powershell
.\.venv\Scripts\python.exe -m unittest backend.test_execution_device
.\runtime\ComfyUI\.venv\Scripts\python.exe scripts\verify_execution_device.py
```

第二個指令以實際 aiohttp 路由進行故障注入，無模型、無測試張量。需要額外驗證真正 ComfyUI 的 CPU 模式時，先執行固定安裝器，再使用：

```powershell
.\.venv\Scripts\python.exe scripts\install_execution_device.py
.\runtime\ComfyUI\.venv\Scripts\python.exe scripts\verify_execution_device.py --managed-cpu
```

此檢查使用臨時資料目錄、記憶體資料庫與未使用的本機連接埠，只載入本專案回報擴充；結束會停止本次程序樹並清理臨時資料，不停止使用者既有引擎。需要已安裝的受管理 ComfyUI 環境。驗收條件與限制見 [紀錄](../validation/execution-device-20261022.md)。

<a id="job-measurements"></a>

## 任務耗時與資源取樣

新建任務保存 `measurements` schema 1，任務列表／詳情、SSE 及作品預覽皆沿用同一原紀錄。舊任務和作品顯示未知；GET 不修改 SQLite，刷新舊紀錄也不回填。

| 欄位 | 來源與意義 |
| --- | --- |
| `dispatch_to_observation_seconds` | 平台 UTC 時鐘：首次開始提交 `/prompt` 至首次確認完成／失敗／取消／停止；包含佇列、網路及查詢間隔，排除先前驗證／圖片上傳。未提交或時鐘倒退保持 null |
| `engine_execution_seconds` | 原引擎已核對身分的歷史 `execution_start` 至對應終態事件，毫秒 timestamp 相減；包含模型載入、取樣、解碼與快取，不是純 GPU 推論 |
| `resources_before_submission` | 與版本查詢共用的原引擎 `/system_stats` 單次回報：RAM、各裝置記憶體、來源網址及查詢時間；沒有額外網路探測、張量配置或模型載入 |
| `continuous_resources` | E05 起新任務的背景取樣：原引擎 `/system_stats`，保存成功／失敗／間隔缺口、取樣尾端及全期觀察最高值；可缺少或為 null |
| `task_vram_peak_bytes` | 原介面無法可靠歸屬單一任務，固定 null，不從整卡、allocator、提交前快照或觀察最高值推估 |

引擎時間要求唯一開始／結束、相同 prompt ID、有效整數毫秒、正確結果與順序；缺失、重複、bool、浮點、反向時間、超界或不符結果保持未知。合法零秒／零可用容量不是未知。平台和引擎時鐘各自計算，不跨時鐘相減推估佇列時間。

記憶體快照可能包含可回收快取與其他程序；CPU 使用記憶體標籤。沒有以平台主機 nvidia-smi 補遠端引擎值，也不能以提交前快照當成實際生成峰值或模型最低需求。原始版本快照格式保留，資源另存量測欄位。

初始提交與首次終態量測在任務交易內保存；CAS 衝突不覆寫，原 UUID 恢復不重查版本／資源或提交。終態量測確認後凍結，不因後續讀取延遲而增長。作品匯入複製原量測，重複匯入保留既有值，評分及筆記不改原快照。

### E05 連續觀察的範圍與界限

首次進入 `submitting` 後登記，ASGI lifespan 的背景工作每輪完成後至少等待 2 秒，再查詢該任務凍結的原引擎；不依賴瀏覽器、SSE 或目前設定。同一原引擎的重疊任務共用一個 GET，報告可能相同，不能因此各自認領用量。每次網路查詢最多 2 秒、256 KiB，不跟隨重新導向或環境代理；不提交／取消／停止任務，不重設 allocator peak。

平台最多同時取樣 16 項，每項最多 1 小時／1800 次，保留最近 120 個時間點、最多 16 種裝置身分，另保留全期 RAM／裝置觀察最高值。超限僅停止取樣，不阻擋生成；零次成功即保持未知。失敗只記固定原因，單點值為 null；超過 4 秒的間隔計入 gaps，無法知道未取樣期間的真實峰值。實際週期包含查詢與排程延遲，短任務可能沒有時間點。

RAM 是引擎所在主機的 total−free。裝置數值是引擎回報的 total−free；本次驗證的 ComfyUI CUDA `free` 包含 allocator 可回收快取，**不是 nvidia-smi 的實體整卡已用量**，也不是單一程序／prompt 峰值。CPU／MPS 可能回報主機記憶體，不能加總成 VRAM。PyTorch `max_memory_allocated` 是該程序 allocator 的峰值，自程序啟動或重設起計，不能把其他任務和快取可靠分離；因此本版不更動引擎、不重設共用計數器、不聲稱取得任務專用峰值。參考 [PyTorch 官方定義](https://docs.pytorch.org/docs/stable/generated/torch.cuda.memory.max_memory_allocated.html)及 [NVIDIA 裝置監測說明](https://docs.nvidia.com/deploy/nvidia-smi/index.html)。

取樣 journal 與任務 revision 分開保存，GET 詳情只投影最新取樣，不寫任務。列表／SSE 沿用最近狀態轉移的快照；詳情重新整理可取得最新時間點。首次確認終態時在原交易內凍結並刪除 journal，延遲回應丟棄；作品沿用凍結資料，離線仍可讀。平台正常停止保存部分觀察和 `platform_shutdown`，重啟不再補齊該次取樣；非正常中斷可在 10 秒 lease 到期後接續，時間缺口會記錄。沒有 E05 欄位的歷史紀錄不啟動取樣、不回填。重跑與實機證據見 [E05 驗收](../validation/resource-sampling-20261023.md)。

2026-10-08：390 項後端測試（389 通過、1 項既有 Windows 權限跳過）、Vue 型別／建置通過。RTX 3060 真實九節點任務驗證平台觀察 27.311 秒、引擎歷史 26.029 秒，提交前裝置回報 total 12,884,377,600／free 11,801,722,880／used 1,082,654,720 bytes。任務和作品快照相同，停止引擎後原值保持不變；證據 `runtime/job-measurements-api-20261008.json`。瀏覽器工具環境故障，UI 實機驗收未完成。FLUX 及圖生圖共用接口已經回歸測試，FLUX GPU 仍未驗證。

2026-10-23 · V04：1440px／390px 在任務詳情與作品預覽實際展開量測，核對上述原任務的 27.311／26.029 秒與來源／提交前資源；另以隔離案例驗證不同於目前引擎的原 URL、GPU／CPU 標籤、零秒／零可用容量與未知值。舊紀錄保持未知、讀取不改原任務，作品沿用同一快照。原資料庫前後 hash 相同，未重測 GPU 或估算任務峰值，見 [V04 證據](../validation/comparison-measurements-20261023.md)。

2026-10-26：新增 [E03 相同設定的兩機觀察與獨立較高負載](../validation/hardware-comparison-20261026.md)。比較器對缺來源、未知精度／快取或不同完整設定拒絕產生時間比；歷史任務的耗時只在新報告從原 history 計算，不回填舊紀錄。

2026-10-26：[E04 資源登記](../validation/hardware-resources-20261026.md)分開列出九筆推論與兩筆 RTX 4080 合成訓練。訓練 allocator、worker RSS／Windows peak working set、整卡取樣各有來源，不以推論 RAM／裝置觀察替代。
