# T06 本機訓練執行介面驗收

2026-10-25，Windows／RTX 3060 12 GiB、原生 Python 3.12.10 與固定 sd-scripts 獨立環境。T05 已先以 `29715e7` commit／push，再開始 T06；期間另以 `7ed76e9` 修正既有 Windows CI 啟動 fixture 的冷啟動預算。操作與恢復規則見 [訓練工作區](../training/workspace.md)。

## 程式與介面

網頁沿用 T03 的準備／單次 worker／停止／新 run 續訓及 T04 產物／模型庫／固定方案，沒有把 Torch 載入平台 Python。準備 UUID 在背景工作前落帳；重複 UUID 核對相同設定後只查回。啟動以持久標記及原 launch.json 避免重送，worker 的 OS 租約仍是實際 GPU 協調依據。

補上 R02 原 study 及 hash 到 bundle 驗證、凍結 work／manifest 與續訓；舊 CLI prepare 可另傳 `--study`，resume 沿用已封存來源。worker 無法建立程序時記錄 failed、清除控制端身分，不因長期存活的 web PID 誤判 starting／資源未釋放。

自動回歸涵蓋準備不啟動、同 UUID 回復／不同設定拒絕、未審查資料拒絕、在線引擎拒絕、單次啟動、原 run 停止、程序建立失敗、原 checkpoint 新 UUID 續訓、前序來源延續、容器／任意 flags／未知 UUID 拒絕，以及比較請求不重做且只使用真正 listener 位址。

1440px／390px Chromium 模擬已保存但遺失準備／啟動回應，核對原 UUID 查回、沒有第二個 start、停止與資源釋放分開、續訓只 prepared，以及安裝／模型登記／六方案不生成；axe WCAG 2A／2AA／2.1AA 與窄版不溢出通過。實機另以真正平台與 trainer 驗證，不把模擬狀態稱為 GPU 驗收。

## 範圍

使用隔離 DATA，輸出保留在 `runtime/t06-live-*` 及新 UUID 的 `runtime/training/runs`。自製幾何圖的 train／validation／test 分開，只有 train 一張進 trainer，沒有作者圖；512／rank 4／fp16／AdamW／SDPA、batch 1、seed 42、總步數 6、每步封存。

GUI 安裝／回登仍需 T04 完整來源及 SHA 校驗，建比較方案不生成、不評分、不批准作者圖。其他主機、容器訓練、1024 容量、長時間穩定性與畫風／角色品質未認列；待辦保留。

## 實機結果

原 run `ac9d1c0f-2c4a-46cc-acb9-91e4df7bf2db` 在引擎在線時正確拒絕啟動且不寫 start 標記；只停止自己啟動的閒置引擎後，網頁明確開始並在封存 step-1 後要求停止，實際保存至 step-2，確認程序與租約釋放。

從 step-1 準備新 UUID `8be1d928-2375-4ec8-b1b3-596d3929fc4f`，初始為 prepared，未自動開始；之後明確開始剩餘 5 更新，最後 state／checkpoint 確認全程 step 6，完整產物 21,584,828 bytes、SHA256 `e24a9781f040d0c6fb957cfba52c60d149dfc0c705f6ab243cce5277cbe278c7`，原生安裝／模型來源回登成功。實際共兩個 worker，原 run 的 2 更新與重回 step-1 後的 5 更新分開計，不把全程步數當兩次合計成本。

自行恢復驗收引擎後，網頁保存六份比較方案與人工模板，隔離平台內生成 job 數仍為零。起初 QA 腳本過早讀取尚在切換的舊 DOM，誤判 UUID 重用；API 已正確保存新 UUID。核對原 state 後只接續同一個未啟動的新 run，沒有重跑原 run 或另建第三個訓練。最後只停止自己的驗收服務，8188／18106 均未留監聽，維持測前引擎離線狀態。

739 項完整後端（1 既有跳過）、型別／建置／四組契約／靜態與 116 項 Chromium 通過；最後保留圖防護與 UI 主題整理另通過 44 項相關後端及 4 項含 axe 的桌面／窄版案例。原始結果在 `runtime/t06-quality.log`、`runtime/t06-target-final.log`、`runtime/t06-final-browser.log` 及 `runtime/t06-live-result.json`。精簡且不含 GPU UUID 的 [證據 JSON](training-control-20261025.json)保存來源 hash、設定、run／產物／方案識別與 allocator 量測；數字限此工作負載，包含載入／快取，不能當純 GPU 速度或最低容量保證。

最終來源另完成 Docker 多階段建置與真實容器啟動：資料審查／訓練控制均回報不可用，原生環境檢查要求回覆 409；未因新增模組在容器載入 trainer。只停止／移除自己的驗收容器，資料卷保留，其他 Docker 服務不變。
