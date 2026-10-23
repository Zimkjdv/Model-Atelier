# T02 · 資料契約與工具介面驗收

2026-10-23 完成的是 ROADMAP T02-01：可追溯的輸入、標註、版本、來源與候選 trainer 資料出口。需求沿用 [T01](../training/requirements.md)，操作／欄位見 [資料契約 v1](../training/dataset-contract.md)，官方版本與介面取捨見 [工具評估](../training/tool-interface-research.md)。沒有安裝 trainer、呼叫 ComfyUI、執行 GPU 工作或訓練／產生新 LoRA。

## 使用者資料唯讀盤點

來源仍是 `C:\Users\Ryanisop\Desktop\artist_ref\ハシスタジオ_pixiv`，固定 R02 study `hashi-reference-20261023-v1` 的 JSON bytes SHA256 為 `0aed98e520a7f0df7cbb6a2e35b3fba4a8e4dfb1eaba1b0149e151942daf4e75`。逐檔原始 hash／大小／尺寸與 R02 相同，完整解碼通過；原圖沒有改寫。

22 檔有 20 個不同 bytes 內容、19 個同原作／差分群組。兩份清單各保存全部 22 筆，分割相同但用途／subject／trigger 獨立；train 是候選，尚未被匯出或送入 trainer：

| 用途 | R02 原圖編號 | 數量 |
| --- | --- | ---: |
| train 候選 | 1、2、4、7、8、9、12、13、17、22 | 10 |
| development validation | 5、10、11、14、15、16 | 6 |
| excluded | 3、6、18、19、20、21 | 6 |
| 未曝光 final test | 無 | 0 |

#18 與 #8、#20 與 #9 完全重複；#3 是 #2 同原作差分，保留單一代表；#6／19／21 沿用 R02 排除。全部圖片已有 `r02_contact_sheet` 曝光，#1／22 加 `inference_reference`；**R02 只有 #1 與 #22 分別用於單張推論，T02 也沒有訓練**。原圖編號與檔名對照見 [先前圖片紀錄](reference-inputs-20261023.md)。

| 路徑 | 正規化清單 SHA256 | 檢查結果 |
| --- | --- | --- |
| 畫風 hashi-style v1 | `684a5df0ba174b13ef9a396bbcb7b7f0f2f7a3a0647f129328c220cf24134bdd` | 10 筆 caption、10 筆來源用途待審查 |
| 角色 hashi-character v1 | `96a3cfe59202c3ae77dace7744ce3ef538db7e8d2325c0bf88eab90992bc63f2` | 上述 20 個缺項，加 10 筆逐張角色身分待確認 |

兩路徑 `check` 正常完成，回傳碼 2、`data_ready=false`；沒有來源完整性錯誤，均警告無 final test。實際嘗試 export 都在建立目的目錄前拒絕，沒有作者圖訓練包，沒有把同作者圖片全部認列為目標角色。

本地原始紀錄放於忽略的 `runtime/t02-dataset-study-20261023/`：`style-v1.json`、`character-v1.json`、各自 readiness JSON 及 `summary.json`。摘要另存 [可解析證據](training-dataset-20261023.json)，不包含原圖、逐圖 caption 或來源圖片副本；保留版本與缺項數可供接續開發。

## 正向出口與失敗邊界

另以三張本地自製色塊作合成 corpus，明確分 train／validation／test，只有 train 標為 fixture 已審查；成功匯出 **1 張 train PNG／caption**，沒有評估圖進入 train。清單 hash 為 `6f0de00f05924e85b341bd62604b3621ae963b13e5462e4ed37b95b40961b2be`；封存 hash、UTF-8 caption、1024 bucket TOML 與單一 train 絕對路徑皆核對成功。這只證明 CPU 資料準備流程，不是 sd-scripts 實際訓練通過。

自動測試覆蓋嚴格版本／型別／未知欄位、相對路徑與連結、重複 JSON key、大小寫／ID 重複、完全重複與同原作跨 split、來源 hash／大小／尺寸／缺檔、壞圖／動圖、caption／來源／角色審查、已曝光 test、R02 分割與曝光不得降級、輸出不覆寫、超量 metadata、磁碟中斷／來源變更時不封存、額外保留圖與各類檔案竄改、caption／TOML 重新計 hash 後仍須符合契約、EXIF／白底／不放大與 2048 上限。

新模組與測試已加入 `quality-scope.json`，原因是它們處理來源路徑、不可覆寫的資料出口與訓練／評估隔離；本輪未修改舊高風險流程或其資料格式。

驗證命令：

```powershell
.\.venv\Scripts\python.exe -m unittest backend.test_training_data backend.test_training_bundle -v
.\.venv\Scripts\python.exe scripts/check_quality.py
```

驗證結果：T02 新增 **33 項**測試通過；完整品質入口退出碼 0，格式／靜態檢查、**663 後端（1 項既有跳過）**、Vue 型別／建置與契約、**97 Chromium** 全部通過。完整日誌為 `runtime/t02-quality.log`，其 SHA256 入可解析證據。正式 DATA 八檔、R02 凍結清單及 22 張原圖 hash 再次核對不變；沒有 trainer 依賴進入應用程式／ComfyUI venv。

## 承接與提醒

T02 結案不等於資料就緒。T03 開始試訓前提醒使用者完成候選圖 caption／來源用途／逐張角色審查，並按不足的視角、衣著或場景補圖；T04 前另提醒未參與開發的不同原作最終評估圖。目前 6 張保留圖維持開發評估，不能稱為從未看過的盲測。

候選 trainer 仍需 T03 獨立環境、完整解析依賴與 tokenizer 來源／快取、VRAM／精度、run 停止恢復及快取隔離實測；T04 再核對新 LoRA 鍵完整載入與固定 24 件品質比較。資料 TOML 沒有猜定 learning rate／rank／optimizer 或提供訓練啟動命令。依使用者優先順序，T02 後為 **R01 → R03**，T03／T04 另排。
