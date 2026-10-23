# 前端 HTTP 契約與載入生命週期

Q03 的共用入口位於 frontend/src/apiClient.ts，已用於 App、CreationStudio、FluxStudio、InpaintStudio、ControlStudio、ArtworkLibrary、GenerationPanel，以及設定／比較方案交換。各流程的能力、來源、修訂與表單驗證保留在原模組；共用 client 不改變選取模型、參數或快照。

## HTTP 與錯誤

| 介面 | 用途／約束 |
| --- | --- |
| apiJson(path, RequestInit) | 一次 JSON HTTP 請求；原 AbortSignal 傳入，回傳型別是 caller 的約定，不代表自動 domain schema 驗證 |
| api(path, method, body, signal) | 同一 client 的 JSON body 簡寫；只在有 body 時 JSON.stringify，seed 字串不轉成數字 |
| apiResponse | HTTP 檢查後保留成功 response 的未讀 body，供原 bytes／hash／串流驗證使用 |
| apiText | 保留成功回應原文字，設定／方案／workflow 大整數不經 parse 後重寫 |

ApiError 提供 kind（http／network／aborted／invalid-response）、HTTP status、結構化 detail 與 conclusive。字串 detail、detail.message、Pydantic detail 陣列分別解析；欄位陣列最多顯示三筆。HTML／不完整錯誤內容使用通用 HTTP 提示，不顯示原始頁面或網路例外。錯誤 body 讀取上限 64 KiB；成功的大資料限制仍由各功能驗證器處理。

client 不自動重試任何方法、不改寫呼叫參數、不替流程選型。圖片／比較報告等專用子流程仍保留各自的原始 bytes 與來源／hash 驗證；本次沒有把所有串流轉成 JSON。各功能資料的欄位合法性仍須由原 caller 檢查。

## 可取消載入

requestScope.ts 的 begin 取消上一個查詢並提供 signal／isCurrent；cancel 即使底層忽略 AbortSignal，也會使舊回覆失效；dispose 結束該 instance 的全部讀取。取消不重設表單或 pending，不表示已撤銷伺服器上的寫入。

App 保留設定 epoch／網址對照；四工作台各自區分清單、profile、還原等讀取，KeepAlive 離開時取消、返回時重讀，卸載後不採用晚到回覆。原引擎／模型及 restore token 檢查仍保留。作品庫清單與筆記重讀也有 scope，409 保存衝突繼續保留未保存筆記與評分。

Q05 的重新整理／關頁提示是另一項；本次只處理非同步讀取生命週期，不把瀏覽器記憶體當成持久化草稿。

## 提交與未知結果

generationRequest.ts 的 submitOnce 接收既有凍結 path／body 與清除 pending 的 callback。成功 JSON 必須是物件，且 id 等於凍結的 request_id；null、陣列、缺少 id 或其他任務 ID 都保留 pending。可確認的 API 拒絕仍沿用原契約清除 pending；若錯誤 detail 帶 job_id，必須屬於原請求，其他任務 ID 不能確認本次提交。傳輸失敗、無法解析的回覆、無 job_id 的伺服器錯誤仍保留原請求，讓使用者明確恢復。確認平台已有原任務不等同引擎已生成成功，終態仍由原任務歷史核對。

localStorage 保存失敗時不送請求；恢復使用原 UUID、設定、LoRA 順序與修補／Canny v1、v2 marker 選出的原端點。submitOnce 不讀現在表單、不自動重送；取消、停止及刷新也不由 client 重試。後端仍以原 UUID 帳本處理查詢／恢復，不新增重複 GPU 工作。

V02 的原始 pending、v1／v2 端點、相同 body、遮罩／半徑、錯誤任務 ID 與未知版本已補上真實瀏覽器回歸；六種生成端點的 Node 契約另覆蓋異常成功 JSON 與錯誤回覆中的其他 job_id。見 [V02 驗收](validation/inpaint-recovery-20261023.md)。

E05 的 `measurements.continuous_resources` 為選填的新任務觀察欄位。後端取樣 journal 不改 job revision；GET 詳情可在 revision 相同時回傳更新的時間點，不能以整個回應物件相等判斷任務狀態是否遭改動。列表／SSE 沿用最近狀態轉移的快照，終態後所有量測凍結；作品保留相同觀察，歷史缺欄位不回填，見 [量測契約](job-measurements.md)。

## 驗證（2026-10-22）

```powershell
Set-Location frontend
npm.cmd run build
npm.cmd run check:api
npm.cmd run check:experiments
npm.cmd run check:inpaint
npm.cmd run check:control
```

全部通過。check:api 使用既有 TypeScript 與 Vue compiler／renderer，不新增測試套件：

- HTTP 409／422／500、字串／結構化／欄位錯誤、非 JSON、離線、取消及原文／原 bytes。
- 實際四種 SFC 的 setup 與 KeepAlive 生命週期：離開／返回、底層忽略 abort、晚到回覆、卸載及未保存 prompt／完整 seed／LoRA 保留。子元件不渲染，不執行 GPU。
- 實際四種 GenerationPanel：遺失回應保留 pending，修改表單後明確恢復仍送原 UUID／body／端點；另驗證修補與 Canny v1／v2 六個 descriptor、精確 seed、有序 LoRA、確認／未知結果及不重試。
- 實際 ArtworkLibrary 的 409 操作保留筆記、評分與原修訂號。

隔離平台與模擬引擎另在真實瀏覽器操作：填入未保存提示詞與 seed `18446744073709551615`，觸發欄位陣列 422 後內容仍在，四流程切換返回後保持；模擬 `/prompt` 遺失回應後顯示結果待確認，累計引擎提交恰為一次。測試頁與 8001 服務已停止；helper／資料保留在忽略的 runtime/q03_browser_check.py、runtime/q03-ui-data，正式資料未改。

SFC renderer 驗證不代表真實 DOM／觸控或全站無障礙通過；上述瀏覽器只驗證列出的操作。沒有重新載入模型或 GPU 生成。後端相容基線為 Q02 的 548 項回歸（547 通過、1 項既有權限跳過）；Q03 只修改前端與文件。
