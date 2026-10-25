# T08 訓練紀錄與診斷報告

2026-10-25。T07 已先以 `e09fa3b` commit／push，才開始 T08。沿用已登記 run 與 Windows 原生邊界，提供有界、明確預覽／下載的 JSON 觀察，不載入 trainer 或權重、不生成圖片。

後端以固定欄位擷取參數／資料／基底／環境、狀態、resume、資源與回執，拒絕連結／過大／重複 key 的 metadata；讀取失敗可產出部分報告，live 觀察未知時不認列資源已釋放。預設不讀日誌，明確選擇才附尾段；記錄截斷、缺失、schema、範圍與時間。報告不是原子快照，metadata hash 一致不等於 payload 檔案完整。

回歸涵蓋報告無 worker／payload 讀取／原 run 或 DB 寫入、預設私有欄位排除、明確日誌範圍與截斷、損壞／缺失／manifest 不符、start_unknown 不重送、最多 100 份回執與取樣、超限／NaN、未登記 UUID 及容器拒絕。1440px／390px Chromium 驗證無自動讀取、原始 bytes 下載一致、範圍變更清空、忽略 abort 的舊回應不能覆蓋、新舊 run 識別不符與超限拒絕、axe 與無水平溢出。

另以隔離 DATA 登記既有 T06 的停止及完成 run，只讀取先前自製幾何圖驗收紀錄；在原生平台實際預覽／下載完成 run，兩種寬度各為 17,140 bytes，與下載 SHA256 相符，API 寫入數為零，原 manifest／state／resources／artifacts／worker.log 內容 hash 不變。沒有重新訓練、沒有讀模型 payload、沒有使用作者圖片或改正式 DATA。只停止自己的 18108 驗收服務。報告精簡結果見 [JSON](training-report-20261025.json)，操作見 [工作區](../training/workspace.md#t08-訓練報告)。

746 項完整後端（1 既有跳過）、格式／靜態／型別、前端建置與四組契約通過；此輪完整後端入口明確使用 --skip-browser，瀏覽器另執行訓練審查／缺項導覽／控制／報告共 8 項，兩種寬度與 axe 均通過。T07 已做過整站回歸；T08 沒有把訓練相關回歸稱為整站重跑。最後新增未知狀態保護，15 項相關後端與 check-mode 靜態另通過。

HTML 教學新增第六張真實畫面；桌面／390px 本機資源、章節與連結、放大／Escape、列印展開、axe 無違規。原始紀錄在忽略的 `runtime/t08-quality.log`、`runtime/t08-browser-final.log`、`runtime/t08-final-target.log`、`runtime/t08-style-final.log` 與 `runtime/t08-native-result.json`。
