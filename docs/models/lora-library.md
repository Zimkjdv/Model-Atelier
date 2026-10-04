# LoRA 模型庫

2026-10-04：模型庫新增獨立 LoRA 區塊。從目前選定 ComfyUI 的 `/object_info/LoraLoader` 讀取 `lora_name` 選項，依完整引擎網址存入 SQLite `loras:<engine_url>`，與 checkpoint、任務及作品分開。只處理名稱及登記資料，不下載、讀取權重、載入 GPU 或提交任務。

## 使用

將既有 LoRA 放入 ComfyUI 的 `models/loras` 或引擎自己的額外 LoRA 路徑。啟動引擎後，在模型庫按「同步 LoRA 清單」，搜尋名稱並編輯版本、基礎架構、來源、大小、SHA256、授權及備註。平台設定頁的額外 checkpoint 目錄不自動成為 LoRA 目錄。

首次登記的版本、來源、SHA256 與授權留空，基礎架構為未知；不從名稱推測。這些是使用者登記，非實際檔案驗證。同步未列出的紀錄標示「最近清單未列出」，不刪除資料；再次列出時恢復狀態並保留 metadata。即使標示在清單內，也不保證即時可載入。

編輯失敗保留輸入。離線、缺少節點或回覆無效時保留上次成功清單與時間，另外顯示錯誤。切換引擎時資料隔離，過期編輯／同步回傳 409；同步期間更換引擎會丟棄該回覆。SQLite 交易避免同步與部分編輯互相覆蓋。

## API

| 方法與路徑 | 輸入／行為 |
| --- | --- |
| `GET /api/loras` | 讀取選定引擎的登記快照，不連接引擎或修改資料 |
| `POST /api/loras/sync` | `{ "engine_url": "http://127.0.0.1:8188" }`；成功及可保留快照的同步失敗均回傳 catalog，需檢查 `sync_error`；過期引擎 409 |
| `PUT /api/loras/metadata` | 必填 `engine_url`、`name`；選填 `version`、`architecture`、`source_url`、`size_bytes`、`sha256`、`license_name`、`license_url`、`notes`；只更新送出的欄位 |

`architecture` 在 LoRA 紀錄中指其基礎架構，可登記 `unknown`、`sd1`、`sdxl`、`sd3`、`flux`、`other`。來源／授權網址只接受不含帳密、query 或 fragment 的 HTTP(S)；大小須為安全正整數 bytes，SHA256 為完整 64 位十六進位值，空白代表未知。名稱須先經同步登記；未知名稱 404、無效欄位 422。`origin` 與 `metadata_updated_at` 由伺服器提供，不能透過此 API 偽造。

## 驗證範圍

223 項後端測試：222 通過、1 項既有 Windows 權限跳過；Vue 型別檢查與 build 通過。隔離資料庫的瀏覽器驗證涵蓋同步、搜尋、編輯、錯誤保留輸入及重新整理後資料保存。真實本機 ComfyUI 0.34.0 的清單同步成功，現有 LoRA 清單為空、生成佇列為空；尚未驗證任何實際 LoRA 的載入、生成或相容性。正式 Pony、任務與作品沒有修改。
