# 訓練工作區分階段驗收（2026-10-25）

集中保存同日 T05 至 T08 的介面與實機驗收，各階段的資料、通過數、失敗及品質界線分開記錄。自製色塊、技術訓練與既有作者圖片的證據不能互相替代；T03／T04 的訓練與產物實測仍保留獨立紀錄。操作見[訓練工作區](../training/workspace.md)。

- [T05：圖片與標註審查](#t05-review)
- [T06：本機訓練控制](#t06-control)
- [T07：資料缺項導覽](#t07-navigation)
- [T08：訓練報告](#t08-report)

<a id="t05-review"></a>

## T05 · 訓練圖片與標註審查介面驗收

2026-10-25，Windows 原生 Python 3.12.10／Chromium，使用隔離平台 DATA。介面沿用 T02 的 Dataset／Caption／Provenance、來源解碼與完整性檢查、R02 前序 bytes hash 及不可覆寫資料出口；沒有增加 Torch、trainer 或標註模型依賴。操作見 [訓練工作區](../training/workspace.md)。

<a id="t05-review-verified"></a>

### 已驗證

- 匯入必須明確提供原圖目錄及 UTF-8 清單；前序 study 保留原 bytes hash。原圖預覽只接受登記的圖片 ID／修訂，最終評估圖的預覽拒絕，來源 SHA／尺寸變更也拒絕，不把舊圖當成新檢查。
- 每次標註保存使用新版本及修訂比對，舊 JSON 不變；衝突保留本地編輯。圖片集合、hash 與來源不可透過標註欄位改寫；保留圖不可轉 train、曝光不能降級。
- 出口只包含已審查 train；匯出 UUID 先落帳，回應遺失只查回，不重做。模擬磁碟失敗保留 failed／未封存目錄，第二次相同 UUID 不覆寫或重跑。
- Q07 另核對審查清單 hash 與 completed 出口的 dataset／bundle 檔案關聯；刪除已登記出口清單時備份檢查正確失敗。
- 桌面 1440px／窄版 390px 的瀏覽器流程包含選檔、預覽、逐欄審查、離頁取消、保存新版本、缺獨立評估圖提醒、實際 train-only 出口、遺失出口回應後 GET 查回，以及 409 保留編輯。實際原生平台另跑自製色塊的審查／保存／出口及兩個寬度，不以 mock 當成真實來源驗收。

<a id="t05-review-source-images"></a>

### 既有作者圖片

實際匯入 T02 的畫風與角色兩份清單，各 22 筆、20 個不同檔案內容；分割仍為 train 候選 10、development validation 6、final test 0、excluded 6。畫風仍有 20 個標註／來源缺項，角色仍有 30 個標註／來源／身分缺項；沒有自動批准或匯出作者圖資料包。

22 個原始檔案在前後的 SHA256 全部一致，原清單與前序研究不改寫。只有自己產生的色塊資料完成審查與出口，沒有 GPU 訓練或作者品質認列。首次本機 QA 腳本用文字讀取而正規化 study 的 CRLF，正確被 hash 檢查拒絕；改成直接解碼原 bytes 後通過，正式網頁選檔保留換行。

原始記錄位於 `runtime/t05-live-result.json`、`runtime/t05-live-*`、`runtime/t05-quality.log`、`runtime/t05-final-backend.log`。截圖只保存自製色塊介面於 `runtime/t05-live-review-1440.png`／`390.png`，不把作者圖或整份 DATA 加入 Git；可解析摘要見 [JSON](training-review-20261025.json)。

<a id="t05-review-limits"></a>

### 限制

審查人的來源記載不是法律授權認證，人工角色判讀與最終品質仍需使用者確認。原圖不複製入 DATA，需另行備份；已封存資料包搬移後需重匯出，以重建正確的絕對路徑。GET 修訂顯示上次完整檢查，來源有變仍須明確重驗；出口會再次驗證。

此階段不提供自動 caption、批次自動批准或訓練啟動；容器不提供 Windows 原生資料／訓練環境操作。訓練環境、單次啟動與停止／恢復由下一項 T06 接續，T05 必須先 commit、push。

730 項完整後端（1 既有跳過）、18 項最終審查／備份回歸、型別／建置／契約／靜態檢查通過。完整 Chromium 為 113 通過、一項因並行測試清理相同 artifact 目錄而失敗；產品斷言未失敗，改成獨立輸出目錄後，該既有案例與兩項新增含 axe 的審查案例共三項定向重跑通過。原始結果保留，不把首次執行寫成全綠。

<a id="t06-control"></a>

## T06 · 本機訓練執行介面驗收

2026-10-25，Windows／RTX 3060 12 GiB、原生 Python 3.12.10 與固定 sd-scripts 獨立環境。T05 已先以 `29715e7` commit／push，再開始 T06；期間另以 `7ed76e9` 修正既有 Windows CI 啟動 fixture 的冷啟動預算。操作與恢復規則見 [訓練工作區](../training/workspace.md)。

<a id="t06-control-code-and-ui"></a>

### 程式與介面

網頁沿用 T03 的準備／單次 worker／停止／新 run 續訓及 T04 產物／模型庫／固定方案，沒有把 Torch 載入平台 Python。準備 UUID 在背景工作前落帳；重複 UUID 核對相同設定後只查回。啟動以持久標記及原 launch.json 避免重送，worker 的 OS 租約仍是實際 GPU 協調依據。

補上 R02 原 study 及 hash 到 bundle 驗證、凍結 work／manifest 與續訓；舊 CLI prepare 可另傳 `--study`，resume 沿用已封存來源。worker 無法建立程序時記錄 failed、清除控制端身分，不因長期存活的 web PID 誤判 starting／資源未釋放。

自動回歸涵蓋準備不啟動、同 UUID 回復／不同設定拒絕、未審查資料拒絕、在線引擎拒絕、單次啟動、原 run 停止、程序建立失敗、原 checkpoint 新 UUID 續訓、前序來源延續、容器／任意 flags／未知 UUID 拒絕，以及比較請求不重做且只使用真正 listener 位址。

1440px／390px Chromium 模擬已保存但遺失準備／啟動回應，核對原 UUID 查回、沒有第二個 start、停止與資源釋放分開、續訓只 prepared，以及安裝／模型登記／六方案不生成；axe WCAG 2A／2AA／2.1AA 與窄版不溢出通過。實機另以真正平台與 trainer 驗證，不把模擬狀態稱為 GPU 驗收。

<a id="t06-control-scope"></a>

### 範圍

使用隔離 DATA，輸出保留在 `runtime/t06-live-*` 及新 UUID 的 `runtime/training/runs`。自製幾何圖的 train／validation／test 分開，只有 train 一張進 trainer，沒有作者圖；512／rank 4／fp16／AdamW／SDPA、batch 1、seed 42、總步數 6、每步封存。

GUI 安裝／回登仍需 T04 完整來源及 SHA 校驗，建比較方案不生成、不評分、不批准作者圖。其他主機、容器訓練、1024 容量、長時間穩定性與畫風／角色品質未認列；待辦保留。

<a id="t06-control-live-results"></a>

### 實機結果

原 run `ac9d1c0f-2c4a-46cc-acb9-91e4df7bf2db` 在引擎在線時正確拒絕啟動且不寫 start 標記；只停止自己啟動的閒置引擎後，網頁明確開始並在封存 step-1 後要求停止，實際保存至 step-2，確認程序與租約釋放。

從 step-1 準備新 UUID `8be1d928-2375-4ec8-b1b3-596d3929fc4f`，初始為 prepared，未自動開始；之後明確開始剩餘 5 更新，最後 state／checkpoint 確認全程 step 6，完整產物 21,584,828 bytes、SHA256 `e24a9781f040d0c6fb957cfba52c60d149dfc0c705f6ab243cce5277cbe278c7`，原生安裝／模型來源回登成功。實際共兩個 worker，原 run 的 2 更新與重回 step-1 後的 5 更新分開計，不把全程步數當兩次合計成本。

自行恢復驗收引擎後，網頁保存六份比較方案與人工模板，隔離平台內生成 job 數仍為零。起初 QA 腳本過早讀取尚在切換的舊 DOM，誤判 UUID 重用；API 已正確保存新 UUID。核對原 state 後只接續同一個未啟動的新 run，沒有重跑原 run 或另建第三個訓練。最後只停止自己的驗收服務，8188／18106 均未留監聽，維持測前引擎離線狀態。

739 項完整後端（1 既有跳過）、型別／建置／四組契約／靜態與 116 項 Chromium 通過；最後保留圖防護與 UI 主題整理另通過 44 項相關後端及 4 項含 axe 的桌面／窄版案例。原始結果在 `runtime/t06-quality.log`、`runtime/t06-target-final.log`、`runtime/t06-final-browser.log` 及 `runtime/t06-live-result.json`。精簡且不含 GPU UUID 的 [證據 JSON](training-control-20261025.json)保存來源 hash、設定、run／產物／方案識別與 allocator 量測；數字限此工作負載，包含載入／快取，不能當純 GPU 速度或最低容量保證。

最終來源另完成 Docker 多階段建置與真實容器啟動：資料審查／訓練控制均回報不可用，原生環境檢查要求回覆 409；未因新增模組在容器載入 trainer。只停止／移除自己的驗收容器，資料卷保留，其他 Docker 服務不變。

<a id="t07-navigation"></a>

## T07 · 訓練資料缺項導覽

2026-10-25。將原 T05「圖片只按原順序分頁、問題只顯示前 200 項」補成搜尋、用途／缺項篩選、完整缺項分頁及跨頁定位。後端 T02 檢查仍是判斷來源，前端不重寫審查規則、不批准圖片、不更改原圖／分割。

新增元件只接受當前資料集、已保存檢查、選取 ID 與忙碌／未保存狀態；導航只回傳圖片 ID。資料集層級提醒獨立顯示，空結果保留目前編輯；保存前明示缺項仍屬舊修訂。定位清除篩選並切到實際頁，鍵盤焦點進入審查區；最終 test 維持不預覽與不可編輯。

隔離瀏覽器案例使用 125 張自製色塊（122 train、1 validation、1 excluded、1 test），244 個圖片缺項跨五頁，核對第 200 項之後仍可定位。桌面 1440px／390px 檢查搜尋、合併篩選、空結果、跨頁聚焦、下一張缺項、編輯保留及 final test 不發預覽要求；整段導覽沒有 PUT／PATCH。舊 T05 保存／版本衝突／僅 train 匯出案例另回歸。未訓練、未生成、未替作者圖完成審查。

相關四項 Chromium 案例先通過，含兩種寬度的 axe WCAG 2A／2AA／2.1AA、無水平溢出與跨頁焦點。完整品質檢查的 739 項後端（1 既有跳過）、格式／靜態／型別／建置／四組契約通過；完整 Chromium 117 項通過、1 項既有模型庫無障礙案例在最後唯讀 GET `/qa/state` 遇到 ECONNRESET，之後單獨重驗同案例通過。保留整輪退出非零的原始事實，不將它稱為單輪全綠，也未替生成／訓練增加自動重送。

原始輸出位於忽略的 `runtime/t07-browser-final.log`、`runtime/t07-quality.log` 及 `runtime/t07-models-recheck.log`；桌面／窄版導覽截圖另經人工檢視。HTML 教學兩種寬度的本機資源、連結、列印展開、點圖放大／Escape、axe 檢查亦通過。

<a id="t08-report"></a>

## T08 · 訓練紀錄與診斷報告

2026-10-25。T07 已先以 `e09fa3b` commit／push，才開始 T08。沿用已登記 run 與 Windows 原生邊界，提供有界、明確預覽／下載的 JSON 觀察，不載入 trainer 或權重、不生成圖片。

後端以固定欄位擷取參數／資料／基底／環境、狀態、resume、資源與回執，拒絕連結／過大／重複 key 的 metadata；讀取失敗可產出部分報告，live 觀察未知時不認列資源已釋放。預設不讀日誌，明確選擇才附尾段；記錄截斷、缺失、schema、範圍與時間。報告不是原子快照，metadata hash 一致不等於 payload 檔案完整。

回歸涵蓋報告無 worker／payload 讀取／原 run 或 DB 寫入、預設私有欄位排除、明確日誌範圍與截斷、損壞／缺失／manifest 不符、start_unknown 不重送、最多 100 份回執與取樣、超限／NaN、未登記 UUID 及容器拒絕。1440px／390px Chromium 驗證無自動讀取、原始 bytes 下載一致、範圍變更清空、忽略 abort 的舊回應不能覆蓋、新舊 run 識別不符與超限拒絕、axe 與無水平溢出。

另以隔離 DATA 登記既有 T06 的停止及完成 run，只讀取先前自製幾何圖驗收紀錄；在原生平台實際預覽／下載完成 run，兩種寬度各為 17,140 bytes，與下載 SHA256 相符，API 寫入數為零，原 manifest／state／resources／artifacts／worker.log 內容 hash 不變。沒有重新訓練、沒有讀模型 payload、沒有使用作者圖片或改正式 DATA。只停止自己的 18108 驗收服務。報告精簡結果見 [JSON](training-report-20261025.json)，操作見 [工作區](../training/workspace.md#t08-訓練報告)。

746 項完整後端（1 既有跳過）、格式／靜態／型別、前端建置與四組契約通過；此輪完整後端入口明確使用 --skip-browser，瀏覽器另執行訓練審查／缺項導覽／控制／報告共 8 項，兩種寬度與 axe 均通過。T07 已做過整站回歸；T08 沒有把訓練相關回歸稱為整站重跑。最後新增未知狀態保護，15 項相關後端與 check-mode 靜態另通過。

HTML 教學新增第六張真實畫面；桌面／390px 本機資源、章節與連結、放大／Escape、列印展開、axe 無違規。原始紀錄在忽略的 `runtime/t08-quality.log`、`runtime/t08-browser-final.log`、`runtime/t08-final-target.log`、`runtime/t08-style-final.log` 與 `runtime/t08-native-result.json`。
