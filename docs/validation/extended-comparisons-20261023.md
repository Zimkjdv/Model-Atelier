# R06 · 模型與取樣參數比較擴充

日期：2026-10-23。新增範圍是 checkpoint 文生圖與單張圖生圖的三個比較軸。局部編輯／羽化／Canny 維持 R07 的明確拒絕；FLUX 仍未開放。

| 新軸 | 值與前提 | 保留內容 |
| --- | --- | --- |
| `checkpoint` | 原引擎最近成功同步、登記為相同 SD 1.x 或 SDXL 架構的精確名稱字串 | 原引擎、精確 seed、提示詞、尺寸、取樣參數、有序 LoRA／強度、圖片輸入 |
| `sampler_name` | 精確取樣器名稱字串，提交前由原引擎驗證 | 原 checkpoint 登記快照及其他參數 |
| `scheduler` | 精確排程器名稱字串，提交前由原引擎驗證 | 原 checkpoint 登記快照及其他參數 |

仍是單一變因、1–4 值、最多四案例且總數最多 8 組、每次一張。固定案例明確替換正提示詞，組別標題註記比較值；不更改 LoRA 或其他參數以遷就模型。預覽／保存／匯入／匯出／載入／報告皆不生成，逐組需明確手動提交；沒有自動批次、重試、品質評分或資源估算。

新軸使用 `model-atelier-comparison-plan` schema 2，保存基準及全部變體，按基準與變體首次出現順序保存 `model_snapshots`：原引擎、名稱、登記版本／架構／大小／SHA256、來源／授權欄位及登記時間，origin 固定 `user_registered`。未登記版本保持「未知」、hash 保持空白，並警告同名未登記權重變動不能偵測。這不是實際權重驗證或授權適用證明。

版本 2 的 hash 將整數值浮點數與整數視為相同 JSON 數值，例如 Python `7.0` 與瀏覽器 `7`；seed 仍為精確字串。預覽、匯入及任務交易共用此規則。六個既有軸保留 schema 1 及原 hash，未遷移歷史 JSON。版本與軸不符、快照缺失／順序錯誤／原引擎不符，以及重算 hash 卻修改其他變體參數，均整份拒絕。

保存方案回讀、匯入及原文件匯出，以文件原快照重建驗證，不查引擎或替換新登記。新預覽匯出再核對原 hash，登記改變須重新預覽。生成預留交易內重讀同一 SQLite 登記，核對原快照、現登記與捕獲的版本／架構／大小／hash；不符回傳 409、零新任務及零引擎呼叫。已有 UUID 的恢復仍先返回原任務，登記變更／離線不重送。context 2 保存 `expected_model_metadata`，作品深層沿用，報告共用 context 建構器；未生成組 runs 保持空。

驗收：

- 9 項新增後端整合：兩流程 × 三軸的其餘欄位／停用 LoRA／最大 seed、8 組上限與拒絕、離線原快照交換、篡改、瀏覽器數值表示、過期匯出、登記競態、任務／作品／報告與原 UUID 恢復、未知資料及版本 1 相容。
- 1440px 文生圖／390px 圖生圖：三軸預覽、兩模型快照、保存、實際 JSON 下載、重載、檔案匯入、手動載入第一組、明確提交一次、作品匯入與結果／報告追溯；第二組沒有任務。合成 fixture 原引擎只提供第一模型，未宣稱第二模型可推論。每組結束還原 fixture 登記與引擎模式。
- context／報告與前端元件先以 `ab41b8a` 獨立格式提交，Python AST、Vue 編譯／模板／CSS 與 TypeScript 正規化輸出一致；新增模組與測試加入明確品質 scope。

重跑：`python -m unittest backend.test_extended_experiments`、`npm --prefix frontend run build`，再於 frontend 執行 `npx playwright test tests/extended-experiments.spec.ts`；完整入口 `python scripts/check_quality.py`。本輪格式／靜態、594 項後端（1 項既有 Windows 權限跳過）、Vue 建置／四組契約通過。初次瀏覽器驗收發現 fixture 缺少 VAEEncode 介面，補齊後以獨立埠／輸出目錄重跑全套，89 項通過（5 分鐘）；並行驗收共用輸出曾導致兩項檔案消失錯誤，不是產品失敗，最終重跑未共用輸出。忽略的本機證據為 `runtime/r06-quality.log`、`runtime/r06-browser.log`、`runtime/r06-browser-all.log`，最終下載 JSON、載入與結果 PNG 在 `runtime/r06-browser-results/extended-experiments-*`。

本次合成圖僅驗證資料與操作邊界，不提供 GPU 品質結論；沒有新增權重或變更正式 DATA。

遠端 CI 補驗：`c152c1a` 的 594 項後端通過，89 項瀏覽器中一項逾時。下載 run 39916161751 的 trace（ZIP SHA256 `24a33a16f0567f07c2aeb5d13e4222fa78bb6debc0043278173554ea3f4ffab3`）後，確認停在匯入驗證按鈕仍停用：測試未等重載完成便以 setInputFiles 設定停用的檔案輸入，change handler 正確拒絕處理。補上可用狀態與讀檔完成的等待，另以受控回覆閘門重現重載期間停用；兩種寬度通過（8.1 秒）。沒有放寬單案 45 秒、全套八分鐘或加入重試。本機診斷與回歸為 `runtime/r06-ci-trace.zip`、`runtime/r06-ci-fix.log`。
