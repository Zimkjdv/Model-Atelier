# O02 工作區載入驗收

2026-11-14，Windows 10.0.19045、Intel Core i7-10700F、Edge Chromium 157.0.4341.46、1440×900。在同一主機以正式建置和 loopback 隔離平台量測，前後各 11 次。每次新建瀏覽器 context，使用固定 100 件合成資料及模擬引擎。基線是 `2ffd6e2`。

| 觀測點 | 原中位數 | 拆包後中位數 | 拆包後該步 JS 請求 |
| --- | ---: | ---: | ---: |
| 載入首頁到系統總覽分頁可見 | 246 ms | 236 ms | 1 |
| 首次進作品庫到第一張卡片可見 | 101 ms | 91 ms | 0 |
| 首次進模型庫到版型控制出現 | 83 ms | 92 ms | 4 |
| 首次進簡易創作到起始配方可點擊 | 192 ms | 216 ms | 6 |
| 返回作品庫到第一張卡片可見 | 66 ms | 70 ms | 0 |

首載 JavaScript 的解碼後大小由 737,748 降為 240,364 bytes（約少 67%）。瀏覽器回報的 JS 傳輸量（含標頭）由 738,048 降為 240,664 bytes。Gzip 建置估計為 231.70 → 84.31 kB。首次模型庫及簡易創作各延後下載約 74／129 kB 的 JavaScript，對應表內新增請求。表中時間包含本機 API、瀏覽器及測試操作等待，適用於這組固定條件。

從各版本的 `frontend` 目錄完成正式建置後，使用同一份量測腳本。可指定 `ATELIER_TEST_PYTHON` 與 `ATELIER_TEST_PORT`。報告輸出到 `runtime/quality/o02-before.json`、`o02-after.json`。 [量測腳本](../../frontend/benchmark-workspaces.mjs)

```powershell
$env:ATELIER_BROWSER_CHANNEL = 'msedge'
node benchmark-workspaces.mjs after
```

前端型別、正式建置、格式、lint 與 Node 契約通過。34 項 O02 相關瀏覽器案例通過，涵蓋 500 kB 預算、按需載入、失敗提示及重新載入、快速切頁、未保存表單、跨頁定位，以及原 UUID 與精確 seed 的未知提交恢復。主要報告位於 `runtime/quality/o02-acceptance-report`。其中首次載入時的任務定位起初選到已被近期清單上限擠出的舊任務，改用本案新建立的合成任務後通過，重跑報告位於 `o02-first-task-report`。 [工作區載入案例](../../frontend/tests/workspace-loading.spec.ts)

擴大檢查發現導覽舊選擇器、診斷入口及桌面提示詞高度比對未通過。同一問題在拆包前的基線也有重現，報告位於 `runtime/quality/o02-baseline-failures-report`。系統分頁及參考元件登記曾在並行測試中失敗，隔離重跑兩項通過。 [前端品質入口](../development/quality-checks.md)
