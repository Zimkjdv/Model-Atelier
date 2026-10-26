# 程式庫深度稽核與安全清理計畫（2026-10-27）

依 [SAFE_CODEBASE_AUDIT.md](../prompts/SAFE_CODEBASE_AUDIT.md) 的六個階段進行。本文保存該次唯讀稽核的證據、限制及 B1–B6 清理計畫，不以搜尋不到直接呼叫作為刪除依據。

稽核基準為 `main` 的 `052bf88`；使用者新增的四份規則／稽核 Markdown 已先提交並推送。稽核期間未修改或刪除任何檔案，沒有足夠證據支持整份刪除產品模組或測試。

使用者後續已批准「先保存並提交／推送本報告，再執行 B1 並另行提交／推送」。本報告首次提交時 B1 尚未執行；B2–B6 仍僅為提案。B1 的實際結果另記於文末，不回寫原始稽核結論或歷史驗收。

## 階段 1：理解專案與限制

已閱讀 [AGENTS.md](../AGENTS.md)、[REQUIREMENTS.md](../REQUIREMENTS.md)、[AGENTS-MAINTENANCE.md](../AGENTS-MAINTENANCE.md)，以及架構、部署、資料保存、前端契約和維護文件。需求明確，沒有需要額外釐清的規則衝突。

目前是 Windows 本機單人工作台：Vue → FastAPI → SQLite／本機圖片，另接獨立 ComfyUI；Docker 為選用部署方式。參考 [架構與資料流](architecture.md)、[應用程式工廠](application-factory.md)、[部署邊界](deployment.md)、[維護規則](maintenance.md)。

主要入口及相容責任：

- FastAPI 的 `install(app, context)` 動態註冊、每 app 注入及 ASGI lifespan；原生與容器使用不同啟動入口。
- SQLite `settings` key/value JSON、舊版 workflow／草稿／比較格式；沒有獨立 migration 目錄不表示沒有舊資料相容責任。
- 原 UUID、原引擎、未知結果不重送、不可變快照、取消／停止的確認狀態及運算租約。
- localStorage pending、精確 seed、原始 workflow bytes、KeepAlive 與過期請求失效處理。
- 文件化 CLI、subprocess worker、啟動器及動態安裝的 ComfyUI 擴充。

稽核前後 590 個追蹤檔案的彙總內容 SHA256 相同：`f552946e09f89f0e1d85f1bfe4b54335835ba5574bee141ef8528d78ddd1c603`。計算方式為依 `git ls-files -z` 順序，逐檔累積 UTF-8 路徑、NUL 及該檔內容 SHA256 的原始 digest，再取整體 SHA256；此值描述原始稽核基準，不適用於加入本報告後的版本。

## 階段 2：深度調查範圍

分為後端、前端、工具／部署三路互不重疊的唯讀調查，再交叉核對引用與證據。

| 範圍 | 覆蓋內容 |
| --- | --- |
| 後端 | 92 個產品模組、103 個測試模組、2 個 ComfyUI 擴充模組的 AST／引用掃描；深入閱讀註冊、持久化、任務、專用流程及訓練路徑 |
| 前端 | 86 個來源檔的匯入圖、25 份瀏覽器規格，以及提交恢復、預覽、報告與 Node 契約工具 |
| 工具與配置 | 63 個 Python scripts、21 個模型 JSON、2 個實驗 JSON、訓練 lock／schema、啟動器、Docker／Compose、CI、依賴與品質範圍 |
| 文件與資產 | 操作／驗收文件、本機連結、追蹤圖片及其引用 |

這是全庫盤點及重點路徑深讀，並非逐行審閱全部程式。未開啟使用者資料庫、未檢查 ignored DATA／runtime 內容，也未執行 GPU、訓練或外部服務操作。第三方 runtime、倉庫外 CLI 消費者、現存瀏覽器 localStorage 和真實 Docker 映像未驗證。

## 階段 3：候選、證據與風險

位置與行號均以稽核基準 `052bf88` 為準，後續修改可能造成行號移動。低風險代表有強靜態證據且依賴已合理排查；中風險仍需行為基線與整合驗證；動態入口、公開介面及持久相容路徑若無安全移除證據則保留。

### B1：移除六個未使用的標準函式庫匯入

風險：低。批准範圍僅為以下六行，不包含其他 import、格式整理、設定或測試修改。

| 位置（基準行號） | 符號 | 直接證據 |
| --- | --- | --- |
| [backend/training_control.py](../backend/training_control.py):6 | `Path` | AST 沒有對應名稱讀取 |
| [backend/training_review.py](../backend/training_review.py):7 | `Path` | AST 沒有對應名稱讀取 |
| [scripts/install_structure_preprocessors.py](../scripts/install_structure_preprocessors.py):6 | `os` | AST 沒有對應名稱讀取 |
| [scripts/training_worker.py](../scripts/training_worker.py):5 | `json` | 實際使用 `read_json`／`compute_lease.atomic_json`，沒有使用此匯入 |
| [scripts/verify_flux_extensions.py](../scripts/verify_flux_extensions.py):7 | `Path` | 路徑取自 fixture，沒有使用此名稱 |
| [scripts/verify_hardware.py](../scripts/verify_hardware.py):12 | `sys` | CLI 使用 argparse／base.main，沒有使用此名稱 |

- 已檢查 AST、產品呼叫、相關測試、腳本、文件與 qualified references，未找到透過這些模組取用上述名稱的用途。四份 scripts 未發現以 `eval`／`exec`／`globals`／`locals`／`__import__` 動態讀取這些名稱的路徑。
- 標準函式庫匯入不負責專案註冊；所有原有 HTTP、CLI、參數及資料格式保留。仍無法完全排除倉庫外程式將偶然暴露的模組屬性當 API，這是最壞失敗情況。
- 效益為減少錯誤依賴訊號，規模小但範圍明確。
- 驗證計畫：變更前後比較 AST，僅允許六個 import 差異；執行既有 training control／review／report、worker encoding、hardware acceptance、FLUX extensions、structure workflows 測試；比對四個 CLI help 的輸出與退出碼；跑既有靜態／格式檢查。不得開始安裝、下載、GPU 或訓練。
- 回退方式：獨立提交，必要時 revert 該提交，無資料遷移。歷史驗收 JSON 中的程式 hash 維持原值，新程式版本不能冒充歷史驗收版本。

### B2：修正品質文件的現況／歷史混寫

風險：低。位置：[docs/quality-checks.md](quality-checks.md):11、51。

- 直接證據：文件寫「目前 24 份 spec、四批」，實際有 25 份；[browser_stages](../scripts/check_quality.py):13 每六份分批，因此目前為五批。V06 的「現有 80 項」應標為當時數字，而非覆寫原驗收數。
- 只修正文句，不改品質工具或測試。效益是避免錯誤操作預期；最壞是誤改歷史紀錄。
- 驗證計畫：核對檔案數與分批演算法、檢查本機連結和 diff，保留各日期原測試結果。回退為單獨文件提交的 revert。

### B3：讓 FLUX URL 驗證直接依賴純 schema

風險：中。位置：[backend/flux_workflows.py](../backend/flux_workflows.py):52 的 `Input.valid_engine`。

- 直接證據：驗證器從 `backend.main` 匯入 `Settings`；main 再匯出的正是 [backend.schemas.Settings](../backend/schemas.py):9。該純 schema 的依賴為標準函式庫、Pydantic 及 `lora_settings`。
- 已檢查 main 的相容匯出、FLUX extensions 對 Input 的繼承、路由註冊及直接建構 Input 的測試／scripts。若獨立驗證器在 main 尚未匯入時執行，現有依賴會引入 `app=create_app()` 的完整註冊圖；這不等於寫入 SQLite，但形成隱藏初始化依賴。
- 範圍僅為將內部依賴改成 `backend.schemas.Settings`，保留 main 相容匯出；不改 URL 驗證規則、端點、JSON 或資料 key。
- 效益是解除反向依賴；最壞是影響倉庫外對 `main.Settings` 的 monkeypatch。倉庫內未找到此用途，外部消費者尚未驗證。
- 驗證計畫：前後比對 HTTP／HTTPS、userinfo、query、fragment、非法 port、尾斜線；執行 `test_flux_workflows`、`test_flux_extensions`、`test_app_factory`、`test_settings_transfer`；新程序確認直接使用 Input 不建立 DATA／DB，且 main 的相容匯出仍存在。回退為獨立提交 revert。

### B4：限制羽化預覽的錯誤回應大小

風險：中；屬功能修正，不能混入純清理。位置：[frontend/src/inpaintPreview.ts](../frontend/src/inpaintPreview.ts):6。

- 直接證據：失敗回應直接使用 `response.json()`，沒有 bytes 上限；同檔成功圖片限制 32 MiB，而 [cannyPreview.ts](../frontend/src/cannyPreview.ts):31 的錯誤回應已有 64 KiB 上限。
- 已檢查預覽 UI、驗證器及 `check-inpaint.mjs` 的一般錯誤／成功超限案例。這是確認的靜態差異，尚未執行超大錯誤回應重現，不能宣稱已證實可利用情境。
- 建議另批加入有界錯誤讀取，可沿用 64 KiB 政策；成功圖片、來源與 hash 驗證維持原規則。
- 效益是限制錯誤處理記憶體；最壞是錯誤訊息或 UI 狀態改變。沒有資料遷移，但錯誤行為會改變，需明確批准。
- 驗證計畫：一般 422、超大錯誤、壞 JSON、缺 body、read reject、取消及原成功路徑；執行 inpaint 契約與相關 UI 回歸。回退為獨立功能提交 revert。

### B5：抽取預覽串流讀取的共用機制

風險：中。首批位置：[cannyPreview.ts](../frontend/src/cannyPreview.ts):22、[inpaintPreview.ts](../frontend/src/inpaintPreview.ts):9。

- 直接證據：重複 `getReader → chunks → 超限 cancel → finally releaseLock → Uint8Array`。比較報告與 `TrainingReport.vue` 也有相似機制，但限制與領域驗證不同，不能視為完全相同功能。
- 各讀取器均有 UI 呼叫者；此項是共用機制整理，不是刪除未使用程式。首批只處理 Canny／羽化，保留各自限額、錯誤訊息、PNG、來源及 SHA256 驗證。
- 報告讀取、UTF-8／schema／run／plan／logs scope 驗證，以及 API receipt 的容錯判定先保留原實作，不自動擴大範圍。
- 效益是減少取消／釋放邏輯分岔；最壞是套錯限額、漏釋放 reader 或改變原始 bytes。不可重新序列化原始 workflow 或大整數 seed。
- 驗證計畫：精確上限、分塊、缺 body、read reject、cancel／releaseLock；執行 control／inpaint 契約、前端型別／建置及相關 UI 回歸。若未來擴到報告，需另驗證原 bytes 與 scope。回退為獨立提交 revert。

### B6：共用 Node 契約測試的純 TS 載入助手

風險：中，優先度低。位置：[check-api.mjs](../frontend/check-api.mjs):5、[check-control.mjs](../frontend/check-control.mjs):4、[check-inpaint.mjs](../frontend/check-inpaint.mjs):4、[check-experiment-runs.mjs](../frontend/check-experiment-runs.mjs):4、28。

- 直接證據：重複 readFile、TypeScript transpile、相依替換及 base64 data URL setup；它們仍由 `npm test` 與品質入口實際使用。
- 只共用純 TS 載入 setup，保留全部測試與斷言。`check-studio-reads.mjs` 會編譯 Vue SFC、stub 子元件並接 Vue renderer，行為不同，排除於此批。
- 效益是減少新增相依時的多套維護；最壞是相依順序或快取出錯，使測試未驗到真正來源。
- 驗證計畫：逐支獨立執行，保留全部 fault cases 與退出狀態，確認相依解析失敗仍失敗、不共用可變全域 mock；執行 `npm test`。回退為獨立工具提交 revert。

## 階段 4：分批計畫與保留決定

建議順序為 B1 → B2 → B3；B4 功能修正單獨審核，B5／B6 再按效益安排。每批只執行明確批准的範圍，不自動擴大重構。

| 批次 | 原稽核狀態 | 後續使用者授權 |
| --- | --- | --- |
| B1 | 提案 | 已批准：先保存／推送報告，再執行 B1 並另行提交／推送 |
| B2–B6 | 提案 | 未批准執行 |

以下保留，原因為有使用證據、相容責任，或尚不足以證明可安全移除：

- **整份產品檔與測試**：86 個前端來源檔皆可從 `main.ts` 沿 local import 圖到達；這不代表每個 export 都有用，但沒有孤兒檔刪除證據。Node 契約與瀏覽器測試分別驗 helper／setup 及 DOM／reload／端點／viewport，不能互相取代。
- **相容匯出與舊版本分支**：`main.httpx` 是大量測試的替換點；`main.Settings` 等有相容承諾。舊草稿、schema、workflow marker、localStorage key 仍有保存／恢復責任，不能根據版本較舊移除。
- **相同 AST 的 helper**：`test_adapter_workflows.py:157` 與 `test_control_workflows.py:28` 的 `remote` 雖 AST 相同，但使用不同全域 `definitions()`。條件圖 API 的相似閉包也依賴不同 read／格式／來源政策，未證實可互換。
- **動態腳本與擴充**：training worker、Canny subprocess、故障節點、LoRA observer、ComfyUI device report 有 subprocess／安裝器／decorator 入口。空的 `NODE_CLASS_MAPPINGS` 不代表擴充未使用。
- **歷史比較路徑**：benchmark 的 `legacy-ui` 用於文件化前後效能對照；`install_pony.py` 實為共用固定權重下載器，不能依檔名判為過時殘留。
- **依賴與資產**：六個後端直接依賴及前端直接依賴均有用途；傳遞依賴不能只依直接 import 排除。追蹤圖片有引用；模型 manifest、experiment JSON 和 schema 有動態路徑與公開格式責任。
- **依賴宣告候選**：`check-studio-reads.mjs:4` 直接使用 `@vue/compiler-sfc`，目前由 Vue lock 的 3.5.42 傳遞提供；可另評估顯式 devDependency，不屬可刪依賴，也不混入 B1。
- **容器測試檔**：103 個 `backend/test_*.py` 共 926,860 bytes 隨映像打包；排除收益不到 1 MiB，且容器診斷用途未完全排除，暫緩。不 blanket 排除 scripts，因有生產 worker 和公開維護 CLI。
- **其他微小可疑符號**：`FINAL_NODE`、`control_catalog`／`IMG2IMG_ID` 再匯出，以及 `verify_flux_runtime.install_pony` 的效益小，載入順序或外部匯入責任未充分排除，保留。

## 階段 5：實際驗證與未驗證部分

以下為原始唯讀稽核時實際完成的檢查，不包含後續 B1 執行結果。

| 實際檢查 | 結果 |
| --- | --- |
| 260 個 Python 檔 AST 解析 | 通過，未 import 應用程式 |
| 53 個 JSON 解析 | 通過；不代表全部 schema 語意驗證 |
| Ruff 納管 125 檔 lint／format check，停用快取 | 通過；另檢查 control_workflows 的既有 lint 規則 |
| Vue 型別檢查，`--noEmit --incremental false` | 通過 |
| 10 個 JavaScript 檔 `node --check` | 通過 |
| 1,110 個 Markdown 本機連結路徑／檔名大小寫 | 通過；不代表所有章節錨點與外部 URL 均已驗證 |
| 品質範圍清單 | 125 Python、64 web、2 CSS；無缺檔或重複項 |
| 前端來源匯入圖 | 86／86 可達；不是執行時覆蓋率 |

AST 靜態找到 815 個 `test_` 方法定義，不等於執行測試數或測試通過。唯讀稽核未執行 unittest、Node 契約、正式 build、Playwright、Docker、GPU、安裝或真實訓練，避免產生檔案或操作執行環境；當時尚無新行為測試基線，不能宣稱完整品質綠燈。

批准後先建立一次相關基線，各批跑受影響檢查；跨模組風險再擴大整合驗證。不重跑沒有新診斷價值的相同測試，不刪測試、弱化斷言或降低品質門檻。失敗需先區分既有問題、環境及本次回歸。

## 階段 6：原始稽核結論

初始四個新檔已以 `052bf88` 提交並推送。唯讀稽核本身對程式、測試、依賴和配置的變更為零；前後追蹤檔雜湊一致，Git diff 為空，`main` 與遠端同步。

尚未驗證倉庫外消費者、使用者持久資料／localStorage、第三方 runtime、真實 Docker／GPU 與訓練。這些限制使動態入口、相容分支、整份模組及相似測試應保留。清理以證據、必要性與可回退性為準，不以刪除行數衡量成果。

後續只執行使用者已明確批准的批次。B1 的執行不構成對 B2–B6 的批准。

## B1 執行紀錄（2026-10-27）

使用者明確批准後，先以 `2e195f7` 保存並推送本報告，再執行 B1。程式差異嚴格限定為上述六份 Python 各刪除一行未使用的標準函式庫 import，共六行；未修改測試、CLI、公開介面、依賴、配置、資料格式或歷史驗收。

| 實際驗證 | 結果 |
| --- | --- |
| 修改前相關 unittest 基線 | 39 項全部通過 |
| 修改後同一批 unittest | 39 項全部通過，test ID 清單完全相同，沒有跳過或刪除測試 |
| 六份 Python 原文與 AST 比對 | 每份只移除指定 import，其他原文及 AST 與預期完全相同 |
| 四個 CLI 的 `--help` | 修改前後 stdout、stderr、退出碼完全一致，均 exit 0 |
| `scripts/check_style.py` | 通過：125 份 Python 格式／lint、前端 scoped 格式、Vue 型別與 CSS／style probes |
| `git diff --check` | 通過 |

相關 unittest 命令：

```powershell
.\.venv\Scripts\python.exe -X utf8 -B -m unittest -v backend.test_training_control backend.test_training_review backend.test_training_report backend.test_training_worker_encoding backend.test_hardware_acceptance backend.test_flux_extensions backend.test_structure_workflows
```

CLI 基線使用 `python -X utf8 -B -m <module> --help`，模組為 `scripts.install_structure_preprocessors`、`scripts.training_worker`、`scripts.verify_flux_extensions`、`scripts.verify_hardware`；沒有執行安裝、下載、GPU 或訓練。

本機原始測試輸出、test ID 與 CLI 前後紀錄保存在忽略的 `runtime/audit-b1-20261027/`，不納入 Git。未執行完整後端 suite、前端正式建置或 Playwright；此低風險批次使用對應回歸及既有靜態入口驗證，不宣稱完整 GPU／UI／品質驗收。此提交僅完成 B1。
