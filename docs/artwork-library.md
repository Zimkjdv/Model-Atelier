# 作品庫管理

作品匯入後可離線預覽、下載原圖與完整 workflow，並載入已支援流程的原始生成設定。管理資料與生成紀錄分開：收藏、筆記、封存會保存到 SQLite，圖片與任務快照保留原值。

新增的四項人工評分與管理資料共用修訂號；作品卡片可加入最多四張並排比較，操作與完整 `ratings` 格式見 [比較與評分](artwork-comparison.md)。

## 使用

- 在卡片或作品預覽中點「收藏」，再用「只看收藏」篩選。
- 預覽中的作品筆記最多 10,000 字，按「保存筆記」後保存；搜尋也包含筆記與模型版本。
- 篩選可組合使用中／已封存／全部、模型、收藏與文字搜尋。
- 「封存作品」從使用中清單移出；在「已封存」選「還原作品」即可恢复。封存後仍可下載、预览或載入生成設定。
- 筆記尚未保存時，關閉預覽、載入創作設定與離開頁面有放棄變更確認；保存中避免重複操作。

跨視窗更新採修訂號。收藏、筆記與封存共用同一修訂；另一個視窗保存後，舊修訂回傳 409 並保留表單內容。需要重新讀取最新資料再確認修改；不自動重送或合併筆記。重新讀取有未保存筆記時需先確認放棄。

## API

| API | 說明 |
| --- | --- |
| `GET /api/artworks` | 預設僅使用中作品；`scope=active/archived/all`；`favorites_only=true` 僅收藏 |
| `GET /api/artworks/{id}` | 單件資料，包含封存作品 |
| `PATCH /api/artworks/{id}/organization` | 必填整數 `revision`，至少一個 `favorite`、`notes`、`archived`、`ratings`；其他欄位拒絕 |
| `GET /api/artworks/{id}/image` | 原圖；`thumbnail=true` 縮圖、`download=true` 下載 |
| `GET /api/artworks/{id}/workflow` | 原始完整 JSON，保留精確 seed |
| `GET /api/artworks/{id}/creation-settings` | 支援流程的完整設定還原，不提交生成 |

```json
{"revision":0,"favorite":true,"notes":"記錄本次實驗的觀察"}
```

修訂不符回傳 409；UUID 不存在回傳 404；無修訂、空更新、錯誤型別、超長筆記或不可修改欄位回傳 422。更新在同一 SQLite `BEGIN IMMEDIATE` 交易讀取、比對及寫入，跨程序也不会覆蓋舊修訂。相同值的更新不增加修訂號。

新匯入作品初始化 `favorite=false`、`notes=""`、`archived=false`、`revision=0`、`organization_updated_at=null`。舊作品讀取時給相同顯示預設，不回寫歷史紀錄。重複匯入不會重設整理資料。封存仍保留參考素材引用保護；此功能不提供永久刪除或回收磁碟空間。

## 2026-10-05 驗收

354 項後端測試（353 通過、1 項既有 Windows 權限跳過），Vue 型別與正式建置通過。新增測試涵蓋跨程序修訂競爭、無效資料拒絕、舊紀錄唯讀預設、完整歷史與圖片不變、重複匯入、封存後素材保護及圖片遺失時管理功能。

隔離平台使用本輪四件真實 GPU 風景作品。瀏覽器驗證兩個視窗筆記衝突及表單保留、重新讀取、收藏、筆記搜尋、模型篩選、封存／還原與新頁持久讀取。原圖／完整 workflow 與還原設定重新核對，沒有新生成或新增正式作品。畫面保留 `runtime/artwork-organization-ui-20261005.png`、`runtime/artwork-conflict-ui-20261005.png`。

本輪驗證桌面視窗。瀏覽器 viewport override 請求 390px 後實際仍回報 1280px，因此沒有把該次畫面算作窄視窗驗收；響應式樣式已提供，390px 實際操作待補測。
