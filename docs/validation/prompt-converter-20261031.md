# PC01 中文轉英文提示詞驗收

日期：2026-10-31（Asia/Taipei）。使用者要求先記錄可能驗收項目再實作；本次先在 ROADMAP 加入六項條件，之後實作 API／共用 Vue 元件與本機模型。最初使用的 L01 編號與歷史 LoRA 工作重複，已改為 PC01；既有歷史 L01 不變。

## 完成功能及界線

- 簡易創作編輯狀態、一般 Checkpoint 與基礎 FLUX 提供中文輸入、自然英文／標籤格式、可編輯英文預覽與明確套用。唯讀配方不提供轉換；套用後沿用現有修改配方提示。
- Ollama 為獨立 client、loopback-only、不跟隨 redirect、不使用系統代理；拒絕雲端模型。服務／模型設定存 SQLite，與 ComfyUI 設定及 client 分開。
- `/api/show` 檢查模型後才發出 `/api/chat`。結構化 JSON、英文與完成原因檢查、256 KiB 回覆上限及 120 秒整次上限。每程序一次一筆，無自動重試或下載。
- 觸發詞需明確列在保留詞欄，程式補回省略的原文字串；不推測未知 LoRA 觸發詞，不自動合併原英文。Pony 品質前綴由程式提供。負面提示詞不改。
- 輸入、格式、原英文、模型／上下文變更，以及切頁／卸載，使舊預覽失效；連點、過期與中止有測試。轉換不建立圖片任務；最終套用才改正向提示詞，圖片仍需明確生成。
- 新後端檔、測試與驗收工具，以及 Vue 元件／spec 已列入 quality scope，原因是外部服務通訊與非同步表單更新需要持續檢查。未新增依賴，無資料遷移。

## 本機權重與執行

| 項目 | 實際觀察 |
| --- | --- |
| CPU／RAM | Intel Core i7-10700F @ 2.90GHz；68,654,481,408 bytes RAM（約 63.94 GiB） |
| Ollama | v0.40.13，可攜版於 `runtime/prompt-llm/ollama` |
| 發布包 | `ollama-windows-amd64.zip`；SHA256 `7afa38624fa62ee5d8293422d0ab084c1bb4603134c7f4dafce11a033b57cc19`，下載後核對發布資產 digest 才解壓 |
| 模型 | `qwen3.5:2b`；實際回報 qwen35／1.9B／Q8_0，非先前建議的 Q4 |
| 本機模型 digest | `0689d44085e06d165161a8a9a1731344278cfb5aade63a3c3dbdb48ab54b130a` |
| 安裝清單 size | 2,683,396,812 bytes；不視為 RAM 最低需求 |
| 推論要求 | CPU `num_gpu=0`、context 8192、temperature 0.1、presence_penalty 0、seed 42、num_predict 1200、think false、keep_alive 0 |
| 實際裝置證據 | Ollama runner 記錄 `reason=cpu-only`、`--no-mmproj-offload` 與 `-ngl 0`；不是只依請求宣稱 CPU |
| 完成後 | `/api/ps` 回 `models: []`，模型已卸載 |

下載及模型清單、固定輸出與時間保留於[機器紀錄](prompt-converter-20261031.json)。原始服務 log 在忽略的 `runtime/prompt-llm/serve-error.log`，安裝 URL／hash 在 `runtime/prompt-llm/installation.json`。服務透過專案腳本綁定 loopback 並停用雲端，沒有變更系統自啟。

## 固定案例與有限語意觀察

以下是最終指令及設定的單次結果。全數 HTTP 200，約 7.11–8.92 秒，平均約 7.68 秒；每次完成即卸載，時間含載入及模型資訊查詢。這不是大量 benchmark 或硬體最低需求。

| 案例 | 檢查的內容 | 最終觀察 |
| --- | --- | --- |
| 黑貓／水彩／無項圈 | 數量、顏色、位置、畫風、否定 | `A black cat sitting by a window, without a collar, in a watercolor style.` |
| 兩位成年女性 | 並排、左紅右藍、無其他人 | 完整保留 `Two adult women`、`on the left ... red coat`、`on the right ... blue coat` 與 `no other people` |
| 成年男性與雙手物品 | 左手合上的書、右手白杯、木椅 | adult、closed book、left hand、white cup、right hand、wooden chair 均保留 |
| 清晨湖泊 | 薄霧、遠方松樹、無人與建築 | 場景及兩項排除保留；沒有額外建築或人物 |
| Pony 標籤 | 成年女性、綠眼、短黑髮、黃雨衣、雨街 | 短標籤輸出；程式加 `score_9, score_8_up, score_7_up` |
| 保留觸發詞 | 圖書館閱讀、鉛筆素描、不要彩色 | `atelier_char_v1` 逐字保留，reading／library／pencil sketch／no color 保留 |

調整過程有實際發現：共用標籤範例曾使自然英文省略左右對應，且另一輪出現未指定的 `serene`。修正為格式專用指令、明確保留年齡／左右與禁止額外形容詞，並覆蓋模型預設 presence_penalty。最終固定案例核對如上；不因此宣稱任意描述都不會漏譯或潤飾，預覽仍需核對。

## 真實頁面與測試

隔離平台使用 `runtime/prompt-llm/live-platform-data`／埠 18767，連接真正 Ollama，無 mock 轉換回覆。瀏覽器輸入兩位女性／左右外套案例及 `atelier_demo_v1`，實際 9,532 ms，核對左右、逐字保留詞、套用前原英文不變、套用後一致，以及 API 圖片任務總數仍為 0。[頁面機器紀錄](prompt-converter-browser-20261031.json)。

原始 1440／390 全頁截圖為 `runtime/prompt-llm/live-1440.png`、`live-390.png`。另以已取得的相同實機回覆重播純 UI 視覺核對，保存 `viewport-source-1440.png`、`viewport-preview-1440.png`、`viewport-source-390.png`、`viewport-preview-390.png`；這四張是重播畫面，未重做 LLM 品質試跑。原尺寸檢視確認欄位、預覽與套用按鈕可見、無水平溢出。

| 檢查 | 結果與範圍 |
| --- | --- |
| 後端六個受影響 suite | 38 通過：轉換器、app factory、template context、simple examples、local access、workflow description |
| `scripts/check_style.py` | 通過：scope 格式、Ruff、Vue 型別、CSS 及 lint；包含新增檔案 |
| `npm.cmd run build` | 通過；既有大於 500 kB chunk 提示仍存在 |
| `npm.cmd test` | 通過：API、生命週期、原 UUID／未知回覆恢復、實驗、遮罩、控制與預檢等契約 |
| 新增瀏覽器案例 | 9 項涵蓋 1440／390、預覽後編輯／套用、負面不變、連點、來源／原英文／模型／切頁過期、503／404／504／502／異常成功回覆、設定與配方保護 |
| 既有簡易創作／配方 | 21 項通過；不重做未變動案例 |
| FLUX 附加流程 | 1440／390 各通過；既有原 UUID 恢復、64 位 seed、草稿／作品還原、圖生圖、水平溢出與 axe 斷言保留 |
| PowerShell | 兩個腳本語法通過；`-Background` 對已有本機服務正確偵測，未重複啟動 |

完整全庫測試與 GPU 共存／出圖品質不是這次驗收。32 個不同瀏覽器案例分為新增 9、既有簡易 21 與 FLUX 附加 2；各以最後受影響版本結果認列，不把重跑次數當案例數。

既有 FLUX 附加流程回歸最初卡在新版已收合的架構選單／進階欄位／任務資訊，已依實際 UI 補展開操作，不刪除原凍結恢復、精確 seed、保存、匯入、圖生圖與無障礙斷言。完成互動後，390px 的既有工具列固定 362px 導致文件寬 458px；保留並加強原溢出斷言以列出越界元素，將該工具列改為不超出父容器，並讓進階工作台任務列於窄版換行。最後 390px 原測試及 axe 通過，桌面固定寬度保持相同。第一個寬度修正一度套到同值的導覽規則，差異檢查後已還原，最終僅修改實際越界的 FLUX 工具列。

## 現有平台啟用

確認原平台 25 筆任務皆為終態、訓練清單無 run 後嘗試重啟，工具自動核准審查以 `blocked by policy` 拒絕停止現有程序的操作。因此沒有停止原 8000 服務、沒有改寫正式模型設定或生成任何圖片；原服務對新 API 仍回 404。實作與正式 dist 已完成，需使用者停止後重開平台（`start-local.ps1` 或原啟動方式），再重新整理頁面。新版啟動器在已安裝可攜版時會啟動或沿用 Ollama。

PC01 的功能驗收與原服務切換分開記錄，不能把隔離平台通過當成原 8000 已切換完成。未知描述、其他小模型、GPU 執行、遠端 Ollama、Docker 主機轉接及真正出圖品質均未驗收。
