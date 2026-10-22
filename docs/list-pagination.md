# 清單分頁、摘要與資料成長驗證

作品庫、生成任務、素材庫與三種 Checkpoint 工作台的素材選項改用有上限的摘要清單。作品搜尋、收藏／模型／封存與素材用途篩選在後端執行，文字搜尋使用 Unicode casefold 與字面子字串，不把 `%`、`_` 當萬用字元。模型建議最多 500 個，可直接輸入完整名稱篩選。

作品預覽／比較、素材原始處理資訊與任務完整快照按需取得；跨頁比較最多四張，已選原圖／遮罩／參考素材跨頁保留。任務每次讀取最近 40 筆，可明確載入較早項目；作品匯入選單只查已完成任務。沒有自動提交、重試或自動匯入。

## HTTP 契約與一致性

`GET /api/library/artworks`、`/api/library/jobs`、`/api/library/assets` 共用：

| 參數／回應 | 說明 |
| --- | --- |
| limit | 預設 40，上限 100；超出回傳 422 |
| q | 最多 200 字；搜尋名稱、模型、版本、筆記、作品提示詞與 LoRA 資料 |
| scope | active／archived／all；作品與素材適用 |
| favorites_only、model | 作品收藏及完整模型名稱，可與搜尋、封存組合 |
| status、workflow | 任務狀態與 checkpoint／flux／inpaint／control／all 流程群組 |
| purpose | 素材用途，未登記的舊資料視為 unspecified |
| cursor | 回傳的 next_cursor／previous_cursor；須保留相同條件與頁面大小 |
| items、total、offset | 本頁摘要、查詢成員總數、頁面位置；不含 workflow 或完整環境快照 |
| models、models_truncated | 最多 500 個模型建議及截斷標記，不限制手動輸入模型名稱 |
| missing_ids | 查詢建立後已被移除的項目，明確列出，不靜默以其他項目補位 |

第一次讀取以 SQLite read transaction 固定符合條件的 key 順序，依 imported_at（作品）或 created_at（任務／素材）降冪，再依 key 降冪處理同時間。之後游標固定本次成員，新增資料在重新整理後才出現；修改收藏、封存或筆記不移動成員，各頁摘要仍讀最新值。這是固定成員、即時內容，不是歷史內容快照；詳情與更新仍使用最新 revision／409 保護。

每個 app 的程序記憶體最多保留 8 組、合計 50,000 個 key，10 分鐘到期，LRU 可提前淘汰；不快取完整 JSON。超過 50,000 個符合項目回傳 413，要求縮小範圍。游標格式錯誤為 400，條件不同為 409，過期／淘汰／重啟／不同 app 為 410，介面提示重新整理。預設本機啟動為單程序，多 worker 不能共用這些游標；不要把它當跨程序持久分頁協定。

僅讀取本頁 JSON 摘要，圖片存在檢查也是本頁最多 2 × limit 次。首次仍需掃描、排序 key 與查詢模型建議，成本並非固定時間；此次量測未需要建立摘要表或索引遷移。SQLite JSON、schema、不可變 workflow／來源／seed 均未改寫。

舊 `/api/artworks`、`/api/jobs`、`/api/assets` 仍保留原陣列格式與行為，供既有腳本相容；它們仍可能全量讀取，新清單應使用 library 端點。單筆作品及任務詳情保留原端點，新增 `GET /api/assets/{UUID}`。workflow／報告下載仍走原 bytes，不經瀏覽器重新序列化。

## 效能預算與量測

本次固定資料與預設 40 筆頁面的驗收預算：首批 API 中位數 ≤ 1,500 ms，後續頁 ≤ 150 ms，回應 ≤ 64 KiB，Python 配置峰值 ≤ 8 MiB，程序增量 RSS ≤ 32 MiB；瀏覽器開啟作品庫到完成指定搜尋 ≤ 2,500 ms。量測程式會在分頁版超出預算時失敗。

資料集每個規模各有同樣數量的作品、任務、素材，固定 UUID、同時間排序、收藏／封存／五種模型，含 4 KiB workflow、1 KiB 環境／處理資訊與最大 seed；圖檔未建立，因此這是缺檔也可瀏覽的本機清單成本，不能推論大量真實縮圖解碼成本。全部在臨時 DATA，沒有讀取使用者作品或啟動推論。

硬體：Windows 10 build 19045、Python 3.12.10、Intel Family 6 Model 165、64 GiB RAM；瀏覽器 Chromium 156.0.8078.4。原 API 在 Q06 commit `0d975b1` 的行為量測；原 UI 另從該 commit 建置。API 以 TestClient 與 tracemalloc 記錄三次中位數、Python 配置峰值及每 5 ms 取樣的 RSS 增量；不含建資料成本，RSS 增量不是整個程序峰值。UI 每組一次，heap 回報是 Chromium 粗略值，不能當精密記憶體比較。

| 每種類別筆數 | 作品 API 原／新 ms | 原／新回應 bytes | 原／新 Python 峰值 bytes | 新後續頁 ms |
| ---: | ---: | ---: | ---: | ---: |
| 100 | 80.47／24.08 | 208252／19327 | 1804291／215152 | 20.18 |
| 1,000 | 773.84／67.88 | 2082524／19328 | 17088543／322396 | 19.44 |
| 10,000 | 7689.16／564.61 | 20825238／19329 | 170453551／1564183 | 20.81 |

10,000 筆的任務 API 為 2889.71 → 196.48 ms、14860001 → 14260 bytes；素材 API 為 1918.12 → 136.73 ms、13318572 → 13340 bytes。全部分頁資料組符合預算；完整三類資料、RSS、後續頁與 UI 原始指標見 [JSON 證據](validation/listing-performance-20261022.json)。

| 每種類別筆數 | 原 UI 可搜尋 ms | 分頁 UI 可搜尋 ms | 分頁 UI 清單流量 bytes |
| ---: | ---: | ---: | ---: |
| 100 | 697 | 649 | 34308 |
| 1,000 | 2110 | 708 | 34310 |
| 10,000 | 等待首卡 30 秒逾時，無完成指標 | 1793 | 34312 |

這是同機合成資料的改善證據，不宣稱所有資料、磁碟或瀏覽器都有相同倍數。真正圖片、冷磁碟、多程序與更大資料仍需個別量測；50,000 上限不表示該規模已符合效能預算。

## 重跑、相容與回退

```powershell
.\.venv\Scripts\python.exe scripts/benchmark_listing.py --mode legacy --output runtime/q04-before.json
.\.venv\Scripts\python.exe scripts/benchmark_listing.py --mode paged --output runtime/q04-after.json
.\.venv\Scripts\python.exe scripts/check_quality.py
Set-Location frontend
node benchmark-listing.mjs paged
```

API 兩種模式使用同一資料定義且不修改外部資料。重跑原 UI 需先將 `git archive 0d975b1 frontend` 解至忽略的 `runtime/q04-baseline-ui/`，在其中 frontend 安裝 lock 依賴並建置，再於目前 frontend 執行 `node benchmark-listing.mjs legacy`；程式會使用該固定 UI 與同一合成資料。效能量測請依序執行，不與其他測試共用 fixture 埠或量測時段。

最後全量後端共 558 項（557 通過、1 項既有 symlink 權限跳過）；前端型別／正式建置、四組契約與 9 項瀏覽器回歸通過。後端驗證摘要上限、組合篩選、Unicode、同時間、跨頁新增／更新、明確刪除項目、過期／淘汰／app 隔離、只檢查本頁圖片，以及查詢前後原 JSON／schema 完全相同。瀏覽器增加跨頁比較、組合篩選、較早已完成任務與素材選取案例，既有 Q05／Q06 案例仍須通過。

沒有資料遷移，不需要失敗回填或 rollback schema；重新啟動會清掉游標快取，舊紀錄仍原樣可讀。回退到 Q06 的後端及前端後一起重啟即可；勿把新前端配舊後端，或在執行中的同一資料上混用程式版本。
