# Windows Actions 暫存短路徑修正（2026-10-23）

最近 [R03 CI](https://github.com/Zimkjdv/Model-Atelier/actions/runs/39952054376)、[R01 CI](https://github.com/Zimkjdv/Model-Atelier/actions/runs/39949826859) 及 [T02 CI](https://github.com/Zimkjdv/Model-Atelier/actions/runs/39944284570) 都在後端同樣兩處失敗，尚未進入瀏覽器階段：

- `ReferenceInstallTests.test_fixed_weight_categories_readonly_plan_and_source_pin`：下載計畫已解析實體長路徑，測試仍以 TEMP 的短路徑直接比較。
- `BundleTests.test_export_only_train_and_verify_caption_toml`：TOML 已保存解析後的絕對 `image_dir`，測試仍期待 `RUNNER~1` 別名。

這些是同一實體位置的不同文字表示。沿用 [既有 Windows 別名回歸](quality-windows-paths-20261022.md)，在子程序專用 TEMP／TMP 使用 `GetShortPathNameW` 建立的真實 8.3 路徑，新增這兩個目標後，六個子測試恰有相同兩個失敗。其餘四個既有路徑防護測試通過，無需變更安裝位置或資料集輸出。

只將兩個預期值改成 `.resolve()` 後比較；保留完整目錄與 TOML 路徑斷言，不做包含／後綴比對。產品程式、來源固定、唯讀 `--check`、禁止越界及不覆寫契約維持。短路徑回歸、參考工具安裝及資料包共 15 項測試通過；短路徑回歸另包含六項子測試。無 8.3 支援時既有明示 skip 規則保留。

重跑：

```powershell
.\.venv\Scripts\python.exe -m unittest backend.test_windows_temp_alias backend.test_reference_acceptance.ReferenceInstallTests backend.test_training_bundle -v
.\.venv\Scripts\python.exe scripts/check_style.py
```

本機紅／綠紀錄位於忽略的 `runtime/ci-path-alias-before.log` 與 `ci-path-alias-after.log`。修正提交的新遠端 run 才能證明 GitHub Actions 全套通過，舊 SHA 的失敗不會因新提交自動變綠。
