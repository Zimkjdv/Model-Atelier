# Windows CI 失敗調查與回歸紀錄

這裡依日期集中路徑別名與瀏覽器分批的歷史調查。各輪的失敗、定向重驗、本機完整檢查與遠端 Actions 結果分開保留；沒有把後續修正回寫成先前已通過。日常命令與目前報告位置見[品質檢查](../quality-checks.md)。

- [2026-10-22：Q06 短路徑回歸](#windows-temp-alias-20261022)
- [2026-10-23：參考安裝與資料包修正](#windows-temp-alias-20261023)
- [2026-10-25：瀏覽器分批](#browser-batching-20261025)

<a id="windows-temp-alias-20261022"></a>

## 2026-10-22 · Q06 Windows TEMP 短路徑回歸

首次 [Q06 CI](https://github.com/Zimkjdv/Model-Atelier/actions/runs/39806275637) 的 lock 安裝通過，但四個既有後端測試失敗：runner 的 TEMP 使用 `RUNNER~1` 等 8.3 別名，`Path.resolve()` 回傳長路徑。三個斷言以未正規化字串比較同一實體位置；模型路徑的故障注入也因比較短路徑而沒有命中已正規化的輸出位置。

本機以 GetShortPathNameW 設定子程序專用 TEMP／TMP，四項同樣失敗（4 tests，4 failures），無需修改產品程式或真實目錄配置。將測試預期值及故障注入目標正規化後重跑，四項通過；新增 `backend.test_windows_temp_alias` 持續重現該 runner 條件，沒有 8.3 支援時明列跳過。

實際模型輸出、解析後越界拒絕、報告目錄範圍及禁止覆寫保護均保留，未放寬產品路徑規則。這次修正獨立提交於 Q04 分頁之前；遠端新 run 的結果需另查，不能將本機綠燈當遠端已通過。

<a id="windows-temp-alias-20261023"></a>

## 2026-10-23 · 參考安裝與資料包的短路徑修正

最近 [R03 CI](https://github.com/Zimkjdv/Model-Atelier/actions/runs/39952054376)、[R01 CI](https://github.com/Zimkjdv/Model-Atelier/actions/runs/39949826859) 及 [T02 CI](https://github.com/Zimkjdv/Model-Atelier/actions/runs/39944284570) 都在後端同樣兩處失敗，尚未進入瀏覽器階段：

- `ReferenceInstallTests.test_fixed_weight_categories_readonly_plan_and_source_pin`：下載計畫已解析實體長路徑，測試仍以 TEMP 的短路徑直接比較。
- `BundleTests.test_export_only_train_and_verify_caption_toml`：TOML 已保存解析後的絕對 `image_dir`，測試仍期待 `RUNNER~1` 別名。

這些是同一實體位置的不同文字表示。沿用 [既有 Windows 別名回歸](windows-ci.md#windows-temp-alias-20261022)，在子程序專用 TEMP／TMP 使用 `GetShortPathNameW` 建立的真實 8.3 路徑，新增這兩個目標後，六個子測試恰有相同兩個失敗。其餘四個既有路徑防護測試通過，無需變更安裝位置或資料集輸出。

只將兩個預期值改成 `.resolve()` 後比較；保留完整目錄與 TOML 路徑斷言，不做包含／後綴比對。產品程式、來源固定、唯讀 `--check`、禁止越界及不覆寫契約維持。短路徑回歸、參考工具安裝及資料包共 15 項測試通過；短路徑回歸另包含六項子測試。無 8.3 支援時既有明示 skip 規則保留。

重跑：

```powershell
.\.venv\Scripts\python.exe -m unittest backend.test_windows_temp_alias backend.test_reference_acceptance.ReferenceInstallTests backend.test_training_bundle -v
.\.venv\Scripts\python.exe scripts/check_style.py
```

本機紅／綠紀錄位於忽略的 `runtime/ci-path-alias-before.log` 與 `ci-path-alias-after.log`。修正提交的新遠端 run 才能證明 GitHub Actions 全套通過，舊 SHA 的失敗不會因新提交自動變綠。

<a id="browser-batching-20261025"></a>

## 2026-10-25 · Windows CI 瀏覽器分批驗證

日期：2026-10-25。本次 F02 的最終品質檢查一併處理已存在的 CI 失敗，沒有修改產品的請求重試或生成邏輯。

<a id="browser-batching-20261025-failure-evidence"></a>

### 已取得的失敗證據

- [T08 CI](https://github.com/Zimkjdv/Model-Atelier/actions/runs/40161251226)：trace 的模型庫 `GET /api/models` 回報 `net::ERR_NO_BUFFER_SPACE`，頁面正確顯示讀取失敗；測試繼續等待不存在的模型卡，45 秒後失敗，finally 的清理請求因 context 已關閉而蓋過原始錯誤。整套再於 480 秒截止，112 項通過、1 項失敗、7 項未執行。
- [F01 CI](https://github.com/Zimkjdv/Model-Atelier/actions/runs/40162769334)：後端與前置檢查通過，單次瀏覽器套件仍於 480 秒總截止；不能將這次遠端結果記為 CI 通過。

原始 job log、失敗模型頁 trace 留在本機忽略的 runtime。這證明有瀏覽器網路資源錯誤及整套時間預算問題，尚不能據此認定產品存在特定記憶體洩漏。

<a id="browser-batching-20261025-verification"></a>

### 調整與驗證

`scripts/check_quality.py` 依名稱排序目前 24 份 spec，每六份為一批；每批有新的 Node／Playwright／Chromium、臨時 DATA／平台與不同埠。相同的單 worker、45 秒單案、零重試與每批八分鐘預算保留，失敗立即停止。每批原始證據與 HTML 使用不同目錄；單獨 Playwright 命令仍可重跑指定案例，HTML 路徑由配置的環境變數指定，完整入口不以 CLI reporter 覆蓋它。

runner 合成回歸核對每份 spec 只納入一次、批次大小、獨立埠／目錄、所有階段的失敗退出，以及後面批次失敗不重試或覆寫之前證據。本機完整結果：後端 **770 項通過（1 既有跳過）**，型別／建置／契約通過；Chromium 四批分別 **21、30、27、42 項**，合計 **120 全部通過**。最後報告路徑及模型庫文字調整另以單頁檢查確認，不把本機結果當成 GitHub runner 已通過。

新的 CI 沿用同一完整入口及既有 20 分鐘 job 預算，仍需檢視推送後的實際結果。操作與報告位置見 [品質指南](../quality-checks.md)。

F03 補查：[F02 CI](https://github.com/Zimkjdv/Model-Atelier/actions/runs/40164681392)在後端階段因 Windows TEMP 的路徑別名比較失敗，尚未跑到瀏覽器；已將 runtime parent 與 workspace 兩側正規化，並補等價非正規路徑回歸。這是另一個具體錯誤，沒有將它歸因於瀏覽器分批。見 [F03 調查](flux-generation-20261025.md#故障邊界與調查)。
