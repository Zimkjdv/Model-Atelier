# Windows CI 瀏覽器分批驗證

日期：2026-10-25。本次 F02 的最終品質檢查一併處理已存在的 CI 失敗，沒有修改產品的請求重試或生成邏輯。

## 已取得的失敗證據

- [T08 CI](https://github.com/Zimkjdv/Model-Atelier/actions/runs/40161251226)：trace 的模型庫 `GET /api/models` 回報 `net::ERR_NO_BUFFER_SPACE`，頁面正確顯示讀取失敗；測試繼續等待不存在的模型卡，45 秒後失敗，finally 的清理請求因 context 已關閉而蓋過原始錯誤。整套再於 480 秒截止，112 項通過、1 項失敗、7 項未執行。
- [F01 CI](https://github.com/Zimkjdv/Model-Atelier/actions/runs/40162769334)：後端與前置檢查通過，單次瀏覽器套件仍於 480 秒總截止；不能將這次遠端結果記為 CI 通過。

原始 job log、失敗模型頁 trace 留在本機忽略的 runtime。這證明有瀏覽器網路資源錯誤及整套時間預算問題，尚不能據此認定產品存在特定記憶體洩漏。

## 調整與驗證

`scripts/check_quality.py` 依名稱排序目前 24 份 spec，每六份為一批；每批有新的 Node／Playwright／Chromium、臨時 DATA／平台與不同埠。相同的單 worker、45 秒單案、零重試與每批八分鐘預算保留，失敗立即停止。每批原始證據與 HTML 使用不同目錄；單獨 Playwright 命令仍可重跑指定案例，HTML 路徑由配置的環境變數指定，完整入口不以 CLI reporter 覆蓋它。

runner 合成回歸核對每份 spec 只納入一次、批次大小、獨立埠／目錄、所有階段的失敗退出，以及後面批次失敗不重試或覆寫之前證據。本機完整結果：後端 **770 項通過（1 既有跳過）**，型別／建置／契約通過；Chromium 四批分別 **21、30、27、42 項**，合計 **120 全部通過**。最後報告路徑及模型庫文字調整另以單頁檢查確認，不把本機結果當成 GitHub runner 已通過。

新的 CI 沿用同一完整入口及既有 20 分鐘 job 預算，仍需檢視推送後的實際結果。操作與報告位置見 [品質指南](../quality-checks.md)。
