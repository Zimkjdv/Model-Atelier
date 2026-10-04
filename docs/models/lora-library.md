# LoRA 模型庫

目前創作流程已擴充為最多四個不同 LoRA 的有序串接、排序、強度、快照及完整還原，見 [有序流程說明](multi-lora-workflow.md)。下方階段紀錄保留各次驗收範圍；單一實測不代表多 LoRA 的 GPU 或畫風品質已驗證。

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
| `compatible` | 「架構相容（此查詢未實測）」：兩者登記為相同的 SD 1.x、SDXL、SD3 或 FLUX，且成功清單仍列出兩者；實機證據另看組合紀錄 |
| `unverified` | 「未驗證」：至少一方架構未知／其他，或同架構但同步失敗／最近未列出；不能根據名稱或雜湊推測 |
| `incompatible` | 「不相容：登記架構不同」：兩者登記為不同的已知架構；即使清單失效，這份登記仍顯示跨架構不符 |

所有判定都有 `verified: false`；即使架構一致，也不能保證 LoRA 對特定基礎模型的效果、權重形狀、節點或 GPU 能成功載入。「其他」不能證明屬於同一架構。API 的 `source` 為 `registered_architecture`，`workflow_supported` 只表示該 checkpoint 登記架構可使用平台模板（SD 1.x／SDXL／未知），不是生成授權或 GPU 檢查。

API 在同一個 SQLite 讀取交易中取得兩份快照，回傳各模型登記更新時間、清單狀態與比較時間，不保存「已驗證」標記。編輯架構或切換 checkpoint 時，畫面清除舊結果並重新查詢；過期請求不覆蓋新結果。回覆與畫面來源／登記資料不一致時提示重新讀取模型庫，再更新 LoRA 相容性，不繼續展示舊判定。

相容性追加驗證：231 項後端測試（230 通過、1 項既有權限跳過），Vue 型別檢查與 build 通過。測試涵蓋全部 36 種架構組合、失敗與遺失清單、異常舊資料、引擎隔離及唯讀行為；隔離瀏覽器驗證三種狀態、checkpoint 切換、兩側架構編輯及偏好模型保留。

## 創作頁與草稿

創作頁支援一個 LoRA 的選擇、啟用／停用、移除及模型／CLIP 強度（有限數值 −20～20）。草稿 `loras` 為最多一個 `{name, enabled, strength_model, strength_clip}` 的陣列；停用保留設定，移除清空陣列，舊草稿唯讀補上空陣列。切換引擎或模型清單失效不會丟失原設定。停用時仍使用原七節點流程。

此階段 236 項後端測試（235 通過、1 項既有權限跳過），Vue 型別檢查及 build 通過；隔離瀏覽器驗證選擇、強度編輯、保存、重新載入、停用及移除。未提交真實 GPU 任務。

## 單一 LoRA 提交

啟用時標準流程新增 `LoraLoader`，MODEL 接至 KSampler，CLIP 同時接至正／負提示詞，VAE 仍取自 checkpoint。生成前拒絕已知架構不同的登記，重新查詢 `LoraLoader` 的即時名稱、MODEL／CLIP 介面及有限強度範圍，使用與平台 −20～20 的交集。名稱遺失 409、節點缺失或強度超界 422、離線 503、無效定義 502；保存失敗任務及完整工作流程。所有等待完成後再次核對引擎與兩側架構，請求 ID 恢復不重新探測或提交。原始 JSON 含 LoRA 時僅接受完整單一 LoRA 模板，額外分支、忽略 CLIP 路徑、多 LoRA 均拒絕。

同架構或架構未知仍標示未實測，由引擎驗證權重；不依 VRAM 限制使用者。基礎七節點歷史紀錄不當作啟用 LoRA 的 GPU 證據。245 項後端測試（244 通過、1 項既有權限跳過）及 Vue build 通過；隔離瀏覽器驗證跨架構阻擋、相同架構提示、提交及歷史查詢，使用模擬引擎而非實際權重。實際單一 LoRA GPU 驗收仍待後續項目。

## 生成紀錄、作品與設定還原

新任務的 `lora_metadata` 為實際啟用的 LoRA 快照陣列。每筆含 `name`、`version`（未登記為「未知」）、`architecture`、`source_url`、`size_bytes`、`sha256`、`license_name`、`license_url`、`metadata_updated_at`、`origin: user_registered`、`captured_at`、`enabled: true`、`strength_model` 與 `strength_clip`。在任何引擎請求之前保存，不隨後續登記編輯、同步、同 ID 恢復、狀態更新或重複匯入改寫。沒有啟用 LoRA 的新提交是空陣列；舊紀錄讀取為 null，代表當時登記未知，不以目前模型庫回填。

任務清單／詳情與即時事件提供快照，作品匯入複製原任務快照。作品預覽、任務以及設定還原來源區塊可查看版本、強度、檔案識別與來源。`GET /api/artworks/{id}/creation-settings` 和已確認失敗任務的 `GET /api/jobs/{id}/creation-settings` 可完整還原七節點或單一 LoRA 八節點模板，支援重新排列的節點 ID，精確保留 64 位 seed、提示詞及兩種強度。額外分支或未支援設定會整體拒絕，不部分載入。停用的草稿 LoRA 不在實際流程內，因此生成紀錄還原為未啟用 LoRA；停用設定本身保留在原草稿。

還原不載入權重、不提交任務、不修改正式偏好模型。可用性僅查原引擎登記快照，回應的 `availability.loras` 含 `name` 與 `available`／`missing`／`unknown` 狀態；來源引擎不同、版本未知、清單遺失或登記識別改變時顯示提醒。原快照不保證權重檔未被替換；再次生成仍使用目前安裝的權重並重新檢查。從模型庫返回創作頁重新讀取 LoRA 登記，保留原選擇與強度。

此階段 254 項後端測試（253 通過、1 項既有 Windows 權限跳過），Vue 型別檢查與 build 通過。隔離瀏覽器驗證模擬任務快照、合成測試圖片匯入、登記改版後原作品快照不變、來源差異提示與完整設定還原。未下載任何 LoRA、未執行真實 GPU LoRA 生成；ROADMAP 的實機組合驗證仍未勾選。

## 條件化組合實測（2026-10-04）

後續已完成作者公開 LCM SDXL LoRA 的固定來源安裝與 RTX 3060 實機驗收，詳見 `docs/validation/pony-lcm-rtx3060.md`。模型庫的「查看組合實測」、創作頁及資源提示共用 `POST /api/loras/validation` 的證據邏輯，與只比較登記架構的 API 分開。紀錄經審閱後保存於 `models/lora-validation-records.json`；只有兩側 hash／架構及有效清單匹配才列出實測，取樣設定與強度必須另外完整匹配。

查詢不讀取當前檔案、不載入 GPU、不修改登記或設定；未知、失效、損壞、重複或過大的紀錄保持未驗證。登記於查詢期間變更回傳 409；前端在參數、組合或引擎改變時中止舊請求。條件包括單張純風景、精度、CPU 卸載、環境與實際時間定義；沒有暖機測量時顯示未量測。Pony 七節點預設不宣稱涵蓋啟用 LoRA 的流程，歷史提交提示標明為原紀錄。

此階段 270 項後端測試（269 通過、1 項既有 Windows 權限跳過），Vue 型別檢查與 production build 通過。瀏覽器驗證模型庫查詢、原作品離線載入、正確參數匹配、CLIP 強度／Steps 變更失去匹配及離線資源提示；瀏覽器沒有再次提交生成。其他畫風、多 LoRA、訓練與 RTX 4080 尚待測試。
