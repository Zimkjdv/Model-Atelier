# D01 本機部署與存取邊界驗收

2026-10-25，使用者明確選擇維持同一台電腦使用。沒有開放區網、公開服務或新增遠端 GPU 主機；D01 的遠端認證條件尚未被啟用，不把本機限制稱為遠端登入能力。

## 已驗證內容

本機平台新增全域來源 IP／Host／Origin 檢查，位於所有 API／靜態檔案之前。原啟動腳本維持 loopback，並加入 `--no-proxy-headers`。測試 fixture 改用實際的 localhost Host／來源，而不是將 `testserver` 加入正式白名單。

七項專用 ASGI 測試通過：本機與 IPv6／IPv4-mapped peer、相同 Origin 正常；非本機 peer 即使偽造 forwarding headers 仍 403；不同 Host／scheme／port、null 或含帳密／路徑／query／fragment 的 Origin、重複標頭與跨站 API 均拒絕。被拒絕的設定寫入不改變資料，WebSocket 在進入 handler 前以 1008 關閉；外部頁面可以導覽首頁，但不能藉此讀取 API。

`scripts.verify_local_access` 以真正 loopback HTTP 啟動自己的平台與隔離 DATA：四種惡意來源寫入皆 403，同來源寫入 200，設定保持不變，forwarded headers 未影響實際來源。原始報告留在 `runtime/d01-live-20261025.json`，未啟動 GPU、提交生成或變更正式 DATA。

系統頁新增「部署與存取」，分開描述平台／引擎／儲存來源。1440px／390px 瀏覽器回歸核對模式、鍵盤更新、失敗保留舊資料、跨來源寫入拒絕及窄版不溢出；圖片與檢查證據由 Playwright 保存在忽略的 `runtime/quality`。718 項後端（1 既有跳過）、建置／契約與 108 項既有 Chromium 通過。新增兩項首次因測試把 mock-engine.invalid 當成本機引擎而失敗，修正預期後兩項定向重跑通過；原始失敗及完整結果日誌保留在 runtime/d01-quality.log，最後重跑日誌為 runtime/d01-deployment-browser-final.log。

## 限制

本機模式信任同一台電腦的使用者／程式，沒有帳號認證；無 Origin 的 localhost CLI 仍可操作。來源檢查不替代 OS 權限、TLS 或未來遠端認證。平台只能回報自身程序／檔案系統與選定引擎提供的資訊，不宣稱取得其他主機完整硬體。D02 的容器橋接與持久化另行驗證，沒有套用原生路徑或硬體結論。
