# 中文描述轉英文提示詞

簡易創作進入「套用後修改」或「編輯描述」後，以及一般 Checkpoint／FLUX 工作台，均使用同一個「實際生成提示詞」編輯區。點標題列的「中文轉英文」開啟提示詞助手，確認後套用回原欄位。轉換服務是獨立的本機 Ollama，不經過 ComfyUI，也不會提交圖片任務。

## 操作

1. 點「實際生成提示詞」標題旁的「中文轉英文」，在助手填入中文畫面描述。桌面並排顯示中文與英文結果，窄視窗上下排列。
2. 「格式與保留詞」預設收起，需要時再展開。Pony／Animagine 預設逗號標籤，一般模型與 FLUX 預設自然英文。需要保留的 LoRA 觸發詞、角色名稱逐行填入保留詞欄；轉換器不會猜測任意 LoRA 的觸發詞，也不會自動合併原英文。
3. 按「轉成英文提示詞」，核對標為「待套用」的英文預覽，可直接修正。確認人數、左右關係、動作、顏色及否定後，再按底部的「套用英文提示詞」；視窗關閉，原編輯區顯示更新後的英文及成功提示。套用會取代整段正向提示詞，負面提示詞不會改動。
4. 照原流程明確按「生成圖片」。只轉換、預覽、套用或檢查連線都不會生成。

助手開啟時，背景表單不能操作，避免尚未套用預覽就誤按生成。按 Escape、「返回編輯」或右上角關閉會保留已完成的中文草稿與英文預覽；再開啟可繼續編輯。若仍在轉換則取消等待並忽略遲到回覆。短視窗只捲動助手內容，底部套用／返回與頂部關閉保持可見；關閉後焦點回到原入口。

Pony 會由程式加上固定 `score_9, score_8_up, score_7_up` 前綴，不讓 LLM 猜測模型品質標籤。觸發詞若被模型省略，由程式逐字補回。其他模型不會自動加入品質、作者或評級前綴；Animagine 的其他建議標籤可在英文預覽自行補上。

描述最多 2,000 字；最多 20 個保留詞、每個 150 字，整份轉換輸入另受 6,000 UTF-8 bytes 限制，避免超過模型上下文。預覽可修改至 20,000 字。這是翻譯輔助，語意保留靠指令及人工預覽，不宣稱每次都完整或提升出圖品質。

## 本機服務

已有 Ollama 時啟動服務，明確安裝模型：

```powershell
ollama serve
# 在另一個終端執行；已有服務時不需再 serve。
ollama pull qwen3.5:2b
```

助手的「本機 LLM 設定」預設收起，摘要顯示模型名稱，需要時才展開保存服務網址與模型，再按「檢查連線與模型」。開啟助手時才讀取設定，唯讀配方不顯示轉換入口。預設 `http://127.0.0.1:11434`／`qwen3.5:2b`。保存到現有平台 SQLite 的 `prompt_converter_v1` key，各工作台共用；不修改 ComfyUI 網址，不保存中文描述或轉換紀錄到資料庫。最終套用的英文仍隨原任務／作品快照保存。

本次機器另已安裝可攜版於 `runtime/prompt-llm/ollama`，權重在 `runtime/prompt-llm/models`，均不進 Git。從官方 [Ollama Windows 發布包](https://github.com/ollama/ollama/releases) 安裝到相同位置後，也可使用：

```powershell
.\start-prompt-llm.ps1
```

此腳本只綁定 `127.0.0.1:11434`，指定專案權重目錄並停用雲端。`start-local.ps1`（包含 `start-all.bat` 啟動的平台）發現可攜版時會在背景啟動；關閉平台時只停止它自己啟動的服務。已有 Ollama 服務則沿用，不停止外部服務，也不變更系統登入啟動設定。獨立執行腳本時可按 Ctrl+C 停止。

可攜版未安裝時不影響原平台啟動；使用原生安裝的 Ollama 仍需先啟動它自己的服務。權重只會在明確執行下載指令時下載，UI 不會自動下載、切換模型或轉用遠端服務。

第一版要求 CPU（`num_gpu=0`）、8,192 context、關閉思考、`keep_alive=0` 完成即卸載。CPU 路線目的是減少與繪圖的顯存競爭；尚未驗證繪圖同時運作的容量或速度。首輪 Qwen3.5-2B 實際是 Q8_0，不以模型名稱猜測量化或檔案大小，見[實測](validation/prompt-converter-20261031.md)。

## 邊界與錯誤

- 僅接受 HTTP loopback 網址（localhost 正規化為 127.0.0.1），拒絕遠端、憑證、網址路徑與重新導向；不使用系統代理。雲端模型名稱及 Ollama 回報的遠端模型亦拒絕。
- `/api/show` 先核對已安裝模型，再以 `/api/chat` 請求結構化 JSON。非完整英文、截斷／錯誤 JSON 或超過 256 KiB 的回覆不提供套用。
- 每個平台程序一次一筆轉換，重複請求回 409；總等待上限 120 秒。失敗不自動重試，錯誤文字不轉送上游原始內容。
- 修改中文、保留詞、格式、原提示詞、模型／工作台上下文，或離開工作台時，舊預覽與等待結果失效。「取消等待」會停止前端等待，服務端可能仍完成當次 CPU 請求；未完成前另一轉換可能回 409。
- 中文草稿與預覽有重新整理／關頁的未保存保護，站內快取保留中文。它們不屬於可匯出的生成設定；重新整理前請自行保留需要的內容。
- 目前入口為簡易創作、一般 Checkpoint、基礎 FLUX；獨立局部修補、結構與參考工作台尚未增加入口。
- Docker 中 loopback 指容器；不會藉本功能轉接到 Windows 主機或開放遠端 Ollama。

## API 與驗證

| API | 功能 |
| --- | --- |
| `GET/PUT /api/prompt-converter/settings` | 查閱／明確保存本機網址與模型 |
| `GET /api/prompt-converter/status` | 核對模型資訊，不載入聊天推論 |
| `POST /api/prompt-converter/convert` | 接收 description、style、profile、protected_terms；回英文預覽、實際模型／量化與整次耗時 |

`create_app(prompt_client_factory=...)` 可注入獨立 httpx client，與引擎 client／診斷分開；不在平台載入 Torch。既有資料不需遷移，舊任務不會回填轉換資訊。

```powershell
.\.venv\Scripts\python.exe -m unittest backend.test_prompt_converter
.\.venv\Scripts\python.exe scripts/verify_prompt_converter.py
# 前端建置完成後，在 frontend 執行：
npx.cmd playwright test tests/prompt-converter.spec.ts
```

實機工具使用臨時平台資料及六個固定公開中文案例，回覆存 `runtime/prompt-llm/acceptance.json`；只呼叫本機 LLM，不提交 ComfyUI、不更動正式資料。契約測試、瀏覽器模擬、實際模型語意與真正出圖品質分開認列。

上游介面依 [Ollama Chat API](https://docs.ollama.com/api/chat) 與 [Qwen3.5-2B 模型頁](https://ollama.com/library/qwen3.5:2b)。

整併後的介面、鍵盤與窄視窗驗收見 [2026-11-07 UI 紀錄](validation/prompt-editor-20261107.md)；原模型語意與 CPU 量測仍以 2026-10-31 紀錄為準。
