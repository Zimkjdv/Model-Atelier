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
| `GET /api/loras/compatibility` | 必填 query `engine_url`、`checkpoint`；唯讀比較同引擎的 checkpoint／全部 LoRA 登記架構，不連接引擎或執行權重 |

`architecture` 在 LoRA 紀錄中指其基礎架構，可登記 `unknown`、`sd1`、`sdxl`、`sd3`、`flux`、`other`。來源／授權網址只接受不含帳密、query 或 fragment 的 HTTP(S)；大小須為安全正整數 bytes，SHA256 為完整 64 位十六進位值，空白代表未知。名稱須先經同步登記；未知名稱 404、無效欄位 422。`origin` 與 `metadata_updated_at` 由伺服器提供，不能透過此 API 偽造。

## 驗證範圍

223 項後端測試：222 通過、1 項既有 Windows 權限跳過；Vue 型別檢查與 build 通過。隔離資料庫的瀏覽器驗證涵蓋同步、搜尋、編輯、錯誤保留輸入及重新整理後資料保存。真實本機 ComfyUI 0.34.0 的清單同步成功，現有 LoRA 清單為空、生成佇列為空；尚未驗證任何實際 LoRA 的載入、生成或相容性。正式 Pony、任務與作品沒有修改。

## 登記架構相容性

在 LoRA 區塊選擇「比較用 checkpoint」，預設使用目前偏好模型；也可選擇其他已登記 checkpoint。此選擇只用於比較，不改變偏好模型、草稿或生成設定。沒有 checkpoint 時保留未選擇狀態。

| API 狀態 | 顯示與依據 |
| --- | --- |
| `compatible` | 「架構相容，未實測」：兩者登記為相同的 SD 1.x、SDXL、SD3 或 FLUX，且成功清單仍列出兩者 |
| `unverified` | 「未驗證」：至少一方架構未知／其他，或同架構但同步失敗／最近未列出；不能根據名稱或雜湊推測 |
| `incompatible` | 「不相容：登記架構不同」：兩者登記為不同的已知架構；即使清單失效，這份登記仍顯示跨架構不符 |

所有判定都有 `verified: false`；即使架構一致，也不能保證 LoRA 對特定基礎模型的效果、權重形狀、節點或 GPU 能成功載入。「其他」不能證明屬於同一架構。API 的 `source` 為 `registered_architecture`，`workflow_supported` 只表示該 checkpoint 登記架構可使用平台模板（SD 1.x／SDXL／未知），不是生成授權或 GPU 檢查。

API 在同一個 SQLite 讀取交易中取得兩份快照，回傳各模型登記更新時間、清單狀態與比較時間，不保存「已驗證」標記。編輯架構或切換 checkpoint 時，畫面清除舊結果並重新查詢；過期請求不覆蓋新結果。回覆與畫面來源／登記資料不一致時提示重新讀取模型庫，再更新 LoRA 相容性，不繼續展示舊判定。

相容性追加驗證：231 項後端測試（230 通過、1 項既有權限跳過），Vue 型別檢查與 build 通過。測試涵蓋全部 36 種架構組合、失敗與遺失清單、異常舊資料、引擎隔離及唯讀行為；隔離瀏覽器驗證三種狀態、checkpoint 切換、兩側架構編輯及偏好模型保留。

## 創作頁與草稿

創作頁支援一個 LoRA 的選擇、啟用／停用、移除及模型／CLIP 強度（有限數值 −20～20）。草稿 `loras` 為最多一個 `{name, enabled, strength_model, strength_clip}` 的陣列；停用保留設定，移除清空陣列，舊草稿唯讀補上空陣列。切換引擎或模型清單失效不會丟失原設定。停用時仍使用原七節點流程。

此階段 236 項後端測試（235 通過、1 項既有權限跳過），Vue 型別檢查及 build 通過；隔離瀏覽器驗證選擇、強度編輯、保存、重新載入、停用及移除。未提交真實 GPU 任務。

## 單一 LoRA 提交

啟用時標準流程新增 `LoraLoader`，MODEL 接至 KSampler，CLIP 同時接至正／負提示詞，VAE 仍取自 checkpoint。生成前拒絕已知架構不同的登記，重新查詢 `LoraLoader` 的即時名稱、MODEL／CLIP 介面及有限強度範圍，使用與平台 −20～20 的交集。名稱遺失 409、節點缺失或強度超界 422、離線 503、無效定義 502；保存失敗任務及完整工作流程。所有等待完成後再次核對引擎与兩側架構，請求 ID 恢復不重新探測或提交。原始 JSON 含 LoRA 時僅接受完整單一 LoRA 模板，額外分支、忽略 CLIP 路徑、多 LoRA 均拒絕。

同架構或架構未知仍標示未實測，由引擎驗證權重；不依 VRAM 限制使用者。基礎七節點歷史紀錄不當作啟用 LoRA 的 GPU 證據。245 項後端測試（244 通過、1 項既有權限跳過）及 Vue build 通過；隔離瀏覽器驗證跨架構阻擋、相同架構提示、提交及歷史查詢，使用模擬引擎而非實際權重。實際單一 LoRA GPU 驗收、版本快照仍待後續項目。
