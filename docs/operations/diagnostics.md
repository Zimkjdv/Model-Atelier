# 可追溯且可控的故障診斷

設定頁的「故障診斷」先顯示狀態，再按「預覽診斷 JSON」，檢視後明確下載。可依任務 UUID 或平台請求 ID 篩選，兩者同填為交集；改條件會清除舊預覽。下載的是**當次預覽的完全相同文字**，不另發請求產生不同內容，也不自動分享。

## 識別碼與事件

每個 API 請求由平台產生新的 UUID，以 `X-Request-ID` 回傳，不採用用戶傳入的同名 header。生成區在可取得時顯示失敗的請求 ID，`ApiError.requestId` 保留此值。原任務 UUID 不變：相同提交的恢復會記為 `submission_recovered`，不新增 `submission_new`，也不重新呼叫引擎 `/prompt`。

事件只保留固定欄位：時間、序號、request／job ID、已知流程識別碼、階段、耗時、HTTP 方法／狀態碼、固定分類，以及必要的任務狀態。API 路徑採程式定義的路由模板，未知 URL 僅顯示 unmatched／靜態入口，不保存實際網址或 query。引擎呼叫按提交、預檢、歷史、佇列、圖片、輸入上傳與狀態分組，不保存引擎位址。

任務事件在交易成功後記錄已保存狀態；`observation_stale` 的 outcome 為 `ignored_stale`，`state` 是實際保留的狀態，`attempted_state` 是被拒絕的觀察。`terminal` 只由實際狀態計算，不能把過期觀察當成新的終態。耗時是該 HTTP 請求開始後的累積時間，engine 事件則是單次 HTTP 呼叫耗時，不是 GPU 推論時間。

沿用 `failures.py` 的既有分類，另區分 conflict、storage_unavailable、submission_uncertain 等通訊／儲存情況。提交遺失回應與寫入失敗不代表引擎未收到；保留原 UUID 並查詢原任務，不自動重送。正常關閉進度連線的取消事件另行標記。既有完整任務／歷史 JSON 仍按原端點保存，不會因診斷回填或改寫。

## 狀態 API 與限制

| 端點 | 行為 |
| --- | --- |
| `GET /api/health` | 保留原 `{"status":"ok"}` 存活相容契約 |
| `GET /api/status` | 分別回報 service 存活、data 可讀、上次明確檢查的 engine 狀態 |
| `GET /api/status?probe_engine=true` | 明確唯讀 GET 引擎 system_stats；不查任務歷史，不提交推論 |
| `GET /api/diagnostics[?job_id=<UUID>&request_id=<UUID>]` | `no-store` 的安全欄位預覽；不連接引擎、不修改任務 |

data 可讀只檢查目錄與 SQLite 可查詢，**不測寫入、不掃描所有原圖健全性**；完整停機檢查用 [Q07 工具](data-backup.md)。引擎連線顯示 connected／offline／invalid／unknown，保存觀察時間，超過 60 秒在新狀態報告中視為未知。引擎離線不會把可讀的本機作品庫設為失效。磁碟／SQLite 錯誤回傳不含原始路徑的 503，保留 request ID；存活端點仍獨立。

事件只在**目前程序記憶體**保留，最多 500 筆、序列化事件合計 256 KiB、24 小時；新增或讀取時清除逾期／超額項，重啟清空，不建立額外 log 檔或背景上傳。每個 app／worker 分開，不提供跨重啟或多 worker 的集中日誌。介面另限制 512 KiB 預覽，舊任務只有本版觀察之後的事件；進度背景作業會沿用啟動其觀察的請求 ID。

預設**不含提示詞、圖片、完整 workflow、原始引擎錯誤／堆疊、模型檔名、憑證、headers 或個人路徑**。UUID 與時間仍可關聯創作活動，分享前請檢視。這份報告不是完整備份，也不取代需要另行審查的原始引擎日誌。

## Q09 驗證

`backend.test_diagnostics` 以 MockTransport／AsyncMock 與臨時 DATA 驗證離線、遺失回應、409、上游已收到後磁碟寫入失敗、原 UUID 恢復且 `/prompt` 僅一次、過期觀察不覆蓋終態、引擎離線讀原圖、資料不可讀與服務存活分離、預覽前後 DB bytes 不變、容量／期限／重啟清空、錯誤條件 UUID、隱私 canary 與 app 隔離。HTTP／JSON 傳輸仍沿用 Q03 取消與原 bytes 契約。

`frontend/tests/diagnostics.spec.ts` 以 1440px／390px 真實瀏覽器驗證 ID 篩選、離線與資料可讀標示、預覽後實際 JSON 下載逐字相同、敏感值不出現、任務前後相同及引擎生成計數不增加。品質入口保留失敗 trace／影片與畫面；這些是隔離自動驗證，沒有實機 GPU 推論或全站 V06 驗收。
