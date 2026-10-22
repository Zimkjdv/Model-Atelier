# 完整備份、唯讀檢查與離線還原

從專案根目錄執行 `scripts/data_backup.py`。這是**停機備份**：先停止所有平台程序、維護腳本及其他資料寫入者；需要引擎 input／output 時，也先等生成結束並停止引擎。`--platform-stopped` 是操作者明確確認，不能用來繞過仍在寫入的程序。

目前版本的平台 lifespan 與維護命令會使用同一組 OS 程序鎖，阻擋同一使用者同時開啟相同 DATA／DB；SQLite 另取得排他交易。舊平台版本、不合作的外部工具、不同 OS 使用者／TEMP 環境不受此鎖完整協調，因此仍須停機。非空 WAL／SHM／journal、資料不一致或來源於複製期間變動會拒絕；工具不 checkpoint、不修復 SQLite，也不自動清理任何來源。

## 建立與驗證

以下目的地父目錄須預先存在，最後一層目錄須尚不存在；請改成自己的磁碟與名稱：

```powershell
.\.venv\Scripts\python.exe scripts/data_backup.py check --data .\data
.\.venv\Scripts\python.exe scripts/data_backup.py backup --data .\data --destination D:\Backups\atelier-20261023 --platform-stopped
.\.venv\Scripts\python.exe scripts/data_backup.py verify --archive D:\Backups\atelier-20261023
.\.venv\Scripts\python.exe scripts/data_backup.py restore --archive D:\Backups\atelier-20261023 --destination D:\Backups\atelier-restored-20261023
```

每個命令輸出 JSON，成功退出 0；缺檔、hash 不符、忙碌或錯誤退出非零。`check` 唯讀盤點 DATA／SQLite、紀錄數、來源關聯與圖片 hash，仍須停機以取得一致結果。自訂 DB 需在 check／backup 同時加 `--database C:\Path\custom.sqlite3`。外置 DB 會收入 `database/atelier.sqlite3`，還原結果會回報實際 DB 位置。

備份是可直接檢視的目錄，`manifest.json` 列出每個檔案的相對路徑、bytes 與 SHA256、空目錄、DB 位置及盤點結果。涵蓋整份 DATA 的所有現存檔案，包括設定／草稿／任務／作品／實驗的 SQLite、`assets/`、`artworks/`、`job_inputs/`、`control_edges/` 與自訂子目錄；不是只匯出設定 JSON。參考來源、生成預處理來源／遮罩／羽化遮罩、作品原圖與縮圖、已保存邊緣會核對紀錄；未保存的引擎輸出不會自動下載。

需要額外證據可重複指定 `--evidence .\runtime\my-report.json` 或 `--evidence .\runtime\isolated-data`，收入編號的 `evidence/`；避免選入巨大 runtime。權重、外部模型、ComfyUI 環境、input／output 預設均不納入，應另行備份。DATA 下若有 symlink、junction 或其他重解析點，會拒絕，防止意外追入外部權重。

## 還原與明確切換

restore 先完整驗證來源備份，再複製至**新目錄**；不覆寫目前 DATA。檔案再核對 hash、SQLite／來源關聯與數量，保留 `backup-manifest.json`。驗證完成後，可在引擎離線時以新資料開啟平台核對作品、任務、原圖與設定：

```powershell
.\.venv\Scripts\python.exe scripts/serve_local.py --data D:\Backups\atelier-restored-20261023\data --port 8001
```

外置 DB 再加 `--database D:\Backups\atelier-restored-20261023\database\atelier.sqlite3`。開啟 `http://127.0.0.1:8001`；確認後停止原平台，選定原埠啟動此命令即為明確切換。預設 `start-local.ps1` 仍使用專案 data。舊資料保留可回退；不自動搬移、不自動提交或重新生成歷史圖。

空間預檢保留 manifest 的 32 MiB 餘量；最大 100,000 個檔案／32 MiB manifest。複製途中空間不足、斷電或其他失敗時，新目錄保留 `.incomplete`，verify／restore／指定資料啟動均拒絕使用。來源與既有目的地不覆寫；確認內容後由操作者另行處理失敗目錄。沒有排程、保留副本清理或自動修復。

SHA256 可發現損壞，**不驗證備份來源真偽**；請保管可信副本。備份包含原始提示詞、圖片與本機設定，需自行保護存取。跨環境還原設定不保證相同像素。

## Q07 驗證

`python -m unittest backend.test_backup backend.test_app_factory` 使用臨時 DATA、MockTransport 與子程序 CLI，不讀寫使用者資料。完整備份→verify→還原→離線 API 讀取核對兩個任務、作品原圖、最大 uint64 seed、修補來源／遮罩／羽化遮罩與 Canny 邊緣，逐檔 bytes／hash 及來源 DB 不變；另覆蓋正在運作的平台／跨程序鎖、SQLite writer／WAL、損壞／缺檔／壞 JSON／缺失關聯、空間不足／中途失敗、路徑穿越、既有目的地、外置 DB、空目錄與來源變動。完整品質入口另驗證既有功能與瀏覽器。此項不包含 GPU 再生成或硬碟斷電耐受保證。
