# 分類容量掃描 API

使用者從系統資訊手動開始掃描，可離開頁面後查閱結果。操作與顯示口徑見[分類容量操作](../operations/setup-and-operations.md#storage-categories)。原始設計與驗收要求保存在 [N07 歷史規格](../history/changelog.md#storage-category-api)。

<a id="storage-category-api"></a>

## 端點與掃描狀態

| 端點 | 輸入與結果 |
| --- | --- |
| `GET /api/storage/categories` | 讀取目前範圍與掃描快照。 |
| `POST /api/storage/scans` | 送出空 JSON 物件 `{}`。回傳 HTTP 202 與快照，掃描 ID 位於 `scan.id`。執行期間的重複請求沿用目前掃描。 |
| `GET /api/storage/scans/{id}` | 以 UUID 讀取最新掃描的快照。若該 ID 已被新掃描取代，回傳 404。 |
| `POST /api/storage/scans/{id}/cancel` | 送出 `{}`，對目前掃描提出取消並回傳快照。背景工作確認停止後才轉為 `cancelled`。找不到 ID 時回傳 404。 |

四個端點共用以下回覆。只有啟動端點會安排掃描，每個平台最多同時執行一份。掃描會在達到 20 萬項或約 30 秒時停止接續遍歷，並將結果標為不完整。 [後端實作](../../backend/storage_categories.py)

| 欄位 | 內容 |
| --- | --- |
| `scope` | 目前解析的 `roots`、額外目錄設定的 `revision`、引擎 `engine_url` 與 `external_engine`、無法統計的分類 `unavailable`，以及範圍 `version`。每份掃描保存開始時的 `scope`。 |
| `scan` | 最新掃描，未掃描時為 `null`。包含 `id`、`status`、`scope`、`started_at`、`finished_at`、`visited`、`error` 及 `stale_reason`。狀態為 `queued`、`running`、`completed`、`partial`、`cancelled` 或 `failed`。 |
| `last_completed` | 最近一次兩類皆完整的結果，尚無結果時為 `null`。 |
| `last_result` | 最近一次 `completed` 或 `partial` 的結果，尚無結果時為 `null`。 |
| `known` | 各分類最近的完整值，包含 `bytes`、`checked_at`、`volumes` 及 `stale_reason`。尚無完整值的分類不出現在物件內。 |

掃描狀態與可靠值保存在 SQLite。查閱時，範圍版本改變或距上次完成達一小時會以 `stale_reason` 標出。程序重啟後，原本仍在排隊或執行的掃描會在快照中顯示中斷失敗。取消或失敗保留上次可查閱的結果。

## 計量與完整性

後端決定範圍。原生平台掃描受管理的模型路徑、已登記的額外模型目錄及作品庫，容器只掃描可存取的作品庫。平台本機路徑與外部引擎的檔案系統分開。

使用磁碟區與檔案身分去重。掃描略過符號連結、重新分析點和跨磁碟項目。兩類目錄重疊或共用檔案時，分類會標為不完整，共用檔案不計入任一分類。

`completed` 與 `partial` 結果包含 `categories.models`、`categories.artworks`、各磁碟區的 `volumes`、問題總數 `issue_count` 與最多 12 筆 `issues`。計量欄位 `metric` 為 `logical_bytes`，介面以 `bytes / 10^9` 顯示 GB，`other_bytes` 維持 `null`。

分類狀態為 `complete`、`partial` 或 `unavailable`。`observed_bytes` 是該次可觀察到的值，只有完整分類會提供 `bytes` 並更新 `known`。未知值以 `null` 表示。多卷及 NTFS 特殊檔案的實機補驗由 ROADMAP 追蹤。 [待補驗項目](../planning/roadmap.md#conditional-followups)
