# 前端通訊、導覽與編輯生命週期

共用 HTTP 入口位於 frontend/src/apiClient.ts，已用於 App、CreationStudio、FluxStudio、InpaintStudio、ControlStudio、ArtworkLibrary、GenerationPanel，以及設定／比較方案交換。各流程的能力、來源、修訂與表單驗證保留在原模組；共用 client 不改變選取模型、參數或快照。

## HTTP 與錯誤

| 介面 | 用途／約束 |
| --- | --- |
| apiJson(path, RequestInit) | 一次 JSON HTTP 請求；原 AbortSignal 傳入，回傳型別是 caller 的約定，不代表自動 domain schema 驗證 |
| api(path, method, body, signal) | 同一 client 的 JSON body 簡寫；只在有 body 時 JSON.stringify，seed 字串不轉成數字 |
| apiResponse | HTTP 檢查後保留成功 response 的未讀 body，供原 bytes／hash／串流驗證使用 |
| apiText | 保留成功回應原文字，設定／方案／workflow 大整數不經 parse 後重寫 |

ApiError 提供 kind（http／network／aborted／invalid-response）、HTTP status、結構化 detail 與 conclusive。字串 detail、detail.message、Pydantic detail 陣列分別解析；欄位陣列最多顯示三筆。HTML／不完整錯誤內容使用通用 HTTP 提示，不顯示原始頁面或網路例外。錯誤 body 讀取上限 64 KiB；成功的大資料限制仍由各功能驗證器處理。

client 不自動重試任何方法、不改寫呼叫參數、不替流程選型。圖片／比較報告等專用子流程保留各自的原始 bytes 與來源／hash 驗證，不將所有串流轉成 JSON。各功能資料的欄位合法性仍須由原 caller 檢查。

## 可取消載入

requestScope.ts 的 begin 取消上一個查詢並提供 signal／isCurrent；cancel 即使底層忽略 AbortSignal，也會使舊回覆失效；dispose 結束該 instance 的全部讀取。取消不重設表單或 pending，不表示已撤銷伺服器上的寫入。

App 保留設定 epoch／網址對照；各工作台分別區分清單、profile、還原等讀取，KeepAlive 離開時取消、返回時重讀，卸載後不採用晚到回覆。原引擎／模型及 restore token 檢查仍保留。作品庫清單與筆記重讀也有 scope，409 保存衝突繼續保留未保存筆記與評分。

非同步讀取取消與[未保存內容保護](#unsaved-changes)分開處理；瀏覽器記憶體不是持久化草稿。

## 提交與未知結果

一般草稿 POST／PUT 僅接受其完整已知設定；專用遮罩／羽化／控制／pending 欄位及其他未知欄位回傳 422，不再默默捨棄。舊回讀封套的 id、created_at、updated_at、model_version、request_id 保留有限相容但不影響保存內容或任務身分。`GET /api/reference-workflows/support?family=...` 是本版平台格式能力，不是引擎可生成證明；版本與拒絕範圍見 [R07](specialized-workflow-formats.md)。

generationRequest.ts 的 submitOnce 接收既有凍結 path／body 與清除 pending 的 callback。成功 JSON 必須是物件，且 id 等於凍結的 request_id；null、陣列、缺少 id 或其他任務 ID 都保留 pending。可確認的 API 拒絕仍沿用原契約清除 pending；若錯誤 detail 帶 job_id，必須屬於原請求，其他任務 ID 不能確認本次提交。傳輸失敗、無法解析的回覆、無 job_id 的伺服器錯誤仍保留原請求，讓使用者明確恢復。確認平台已有原任務不等同引擎已生成成功，終態仍由原任務歷史核對。

localStorage 保存失敗時不送請求；恢復使用原 UUID、設定、LoRA 順序與修補／Canny v1、v2 marker 選出的原端點。submitOnce 不讀現在表單、不自動重送；取消、停止及刷新也不由 client 重試。後端仍以原 UUID 帳本處理查詢／恢復，不新增重複 GPU 工作。

V02 的原始 pending、v1／v2 端點、相同 body、遮罩／半徑、錯誤任務 ID 與未知版本已補上真實瀏覽器回歸；六種生成端點的 Node 契約另覆蓋異常成功 JSON 與錯誤回覆中的其他 job_id。見 [V02 驗收](validation/inpaint-recovery-20261023.md)。

E05 的 `measurements.continuous_resources` 為選填的新任務觀察欄位。後端取樣 journal 不改 job revision；GET 詳情可在 revision 相同時回傳更新的時間點，不能以整個回應物件相等判斷任務狀態是否遭改動。列表／SSE 沿用最近狀態轉移的快照，終態後所有量測凍結；作品保留相同觀察，歷史缺欄位不回填，見 [量測契約](job-measurements.md)。

<a id="navigation"></a>

## 網址導覽與能力狀態

頁面／工作流程使用 hash URL，可直接開啟、重新整理及返回／前進，不需要伺服器 rewrite 或額外 router 依賴：

| 畫面 | 網址片段 |
| --- | --- |
| 系統資訊／首次使用 | `#/system`（空網址亦正規化至此） |
| 簡易創作 | `#/studio/simple` |
| 五種工作台 | `#/studio/checkpoint`、`#/studio/flux`、`#/studio/inpaint`、`#/studio/control`、`#/studio/reference` |
| 模型／參考素材 | `#/models`、`#/assets` |
| 作品／選定匯入任務 | `#/gallery`、`#/gallery?job=<UUID>` |
| 選定作品並排比較 | `#/gallery/compare`（選取內容仍由本次操作決定） |
| 實驗比較／訓練工作區 | `#/experiments`、`#/training` |
| 連線設定 | `#/settings` |

錯誤路徑、流程或額外參數會顯示提示並替換成系統資訊。網址只表示導覽／選定任務，不包含表單、提示詞、圖片、引擎憑證，也不觸發生成、匯入或恢復原提交。作品庫的 job 是待匯入任務選項，不會自動匯入圖片。

創作頁上方提供「簡易創作／進階工作台」。首次點主要導覽的「創作」預設進入簡易模式，之後以瀏覽器 `atelier-creation-mode-v1` 記住所選模式；明確工作台網址、模型／素材帶入及作品還原仍導向指定流程。儲存不可用時只在本次頁面記住偏好。

簡易模式提供 Animagine 4.0 Opt、Pony V6 XL 與 FLUX.1 Schnell 三份 v1 起始配方。模型依既有 manifest 的登記 SHA256／架構匹配，FLUX 逐一匹配四元件；同名檔案不當成相符證據。Checkpoint 取樣參數取自現有模型 profile，FLUX 使用固定 512²／4 steps／FP8／CPU 配置。配方尚無真實成果圖或新增畫質驗收，尺寸先保留原始正方形。

載入配方不生成、不下載模型。「載入起始配方」使用原始描述並保持唯讀；「套用後修改」或「編輯描述」開啟編輯，「還原配方設定」恢復原描述及固定 Seed，取代未保存修改前需確認。描述欄是實際送入模型的英文提示詞，沒有自動翻譯；可換 Seed 後明確再生成、查看完整設定、直接保存結果，或帶到對應進階工作台。四步進度區分選卡、確認、生成與保存；改動表單後，既有結果另顯示提示，不將舊圖計為新表單的成果。

未就緒時逐項列名缺少或登記不匹配的 Checkpoint／FLUX 元件，按處理入口會開啟模型庫對應分類。返回後保留選卡與描述，按「重新檢查」更新可用性及原引擎取樣選項；不自動安裝、換模型或生成。進階已有未保存內容時，轉交先確認，取消會保留兩邊設定；簡易設定站內保留，重新整理前需轉交進階保存草稿。預檢、提交、精確 Seed、原請求恢復、結果預覽與作品保存沿用現有模組。相同流程的簡易／進階工作台共用原提交恢復欄位，快取面板重新啟用時會重讀原請求。

### 起始模板來源

三份 v1 配方的 ID、文字及固定來源共用 `models/simple-creation-templates-v1.json`；模型／元件識別仍由既有 manifest 提供，Checkpoint 參數沿用 profile。一般及 FLUX 生成請求可選填 `template_selection: {template_id, template_version}`，目前僅接受三個固定 ID 及版本 1，拒絕額外欄位。後端依實際提交設定計算修改欄位，在建立任務時凍結 `template_context`：ID／版本、標題、原配方、元件要求、流程、配置證據文件、SHA256 與修改狀態。此資料證明配方來源，不是畫質通過或當前權重內容驗證。

任務詳情及作品保留同一來源快照，簡易成果、生成任務及作品的「生成與來源」可展開查閱。精簡任務清單不含完整來源時，結果區另讀任務詳情；離開或改選時取消過期讀取。相同 UUID 恢復仍核對原 `template_selection`，不重讀新配方改寫舊來源。舊任務／作品無來源時顯示未記錄，不由檔名、圖片或現在的模型推定。

轉交 Checkpoint／FLUX 進階工作台、保存／重載對應草稿及從任務／作品還原，會保留選定模板；重新生成時後端建立新的來源快照並重新比較實際修改。來源獨立於基本生成設定，沒有擴大局部修補、結構引導或參考流程的草稿／交換格式。清空表單或匯入一般設定 JSON 會清除選定模板，JSON 交換目前不攜帶此來源。

所有站內導覽與工作台事件使用同一入口；切換後焦點移到主要內容，頁面標題、`aria-current` 與流程 `aria-pressed` 隨之更新。跳至主要內容連結只移動焦點，不改網址。五種 Studio 由 KeepAlive 保留站內表單；重新整理會重建記憶體，未保存內容遵守 [未保存內容保護](#unsaved-changes)，網址本身不是草稿備份。作品未保存筆記／評分時，返回或點擊導覽均需明確確認；取消恢復原歷史位置、網址及筆記。

系統、設定與工作台提供「連線 → 選模型 → 建立作品」指引，工作台預設收合以保留表單空間。連線顯示已連線、離線或未知；模型同步／登記不代表已載入權重。生成區依原本的 blocking 條件呈現「載入／處理中」「尚缺必要條件」「表單預檢可提交」及「原提交待確認」，沿用既有 disabled 判斷，不另建較寬鬆的提交規則。實際缺項提示保留於下方，詳細能力範圍可展開。

FLUX 的固定配置與 GPU 驗收見[平台接入紀錄](models/flux-workflow.md#generation-acceptance)，不外推到其他配置。各流程只按對應文件的硬體、模型、參數與日期判讀；版本／來源／檔案 hash／執行裝置無法取得時保持未知。模型與任務的詳細來源／版本快照沿用原有展開區。沒有以「可提交」替代品質、授權或 GPU 驗收。

<a id="unsaved-changes"></a>

## 未保存內容與離頁保護

五種工作台共用 `useUnsavedChanges`。表單、LoRA 或遮罩有未保存變更時註冊 `beforeunload`，草稿／遮罩正在保存時也保護；成功保存後才移除對應保護，保存失敗不清除內容。KeepAlive 切頁仍保留表單及筆刷，隱藏工作台的未保存內容也會阻擋整個分頁離開；卸載才移除監聽。

Checkpoint 與 FLUX 可保存完整草稿。局部編輯／Canny／畫風角色參考只保留本頁表單，保存原圖或遮罩並不保存整份設定，專用草稿格式仍由 R07 處理。載入任務／作品設定為未保存的新內容；生成不會把表單標為已保存。

取消瀏覽器警示會留在原頁，內容與筆刷不變。確認離開不會呼叫保存或生成。瀏覽器自行決定是否顯示警示文字，通常需要先與頁面互動；行動瀏覽器、系統強制結束程序或瀏覽器崩潰不保證觸發，請主動保存可保存的內容。

待確認提交按上節的原 UUID／body／端點恢復；重新開啟只提供明確恢復操作，不是未保存草稿的自動備份。

<a id="frontend-verification"></a>

## 重跑與驗收範圍

```powershell
Set-Location frontend
npm.cmd run build
npm.cmd run check:api
npm.cmd run check:experiments
npm.cmd run check:inpaint
npm.cmd run check:control
```

`check:api` 使用專案既有 TypeScript 與 Vue compiler／renderer，驗證 HTTP 錯誤、取消、原文字／bytes、實際 SFC 的 KeepAlive／晚到回覆／卸載、dirty／保存中／卸載監聽、精確 seed／LoRA 保留、原凍結提交流程及作品 409 未保存內容。子元件不渲染，不能據此宣稱真實 DOM、觸控或全站無障礙通過。

瀏覽器回歸另在臨時 DATA／模擬引擎檢查網址直達／刷新／返回、焦點、未保存筆記返回確認、重新整理／關頁警示、保存成功與失敗、遮罩筆畫、未知結果與原請求恢復；fixture 成功圖片為合成 PNG，不代表真實推論。入口與目前範圍見[品質檢查](quality-checks.md)。

Q03／Q05／Q08 的原始四工作台、1440px／390px 與 bundle 數字屬當時歷史，不是目前測試總數或效能保證，見 [CHANGELOG](../CHANGELOG.md)。2026-10-23 新增第五個參考工作台的遺失回應、重新整理、完整還原與切頁保留另見 [R02 驗收](validation/reference-adapter-20261023.md)；六種 descriptor 與 v1／v2 失敗恢復見 [V02](validation/inpaint-recovery-20261023.md)。GPU、實體觸控及全站視覺仍須各自驗收。
