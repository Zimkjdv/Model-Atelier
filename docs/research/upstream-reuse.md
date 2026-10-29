# 上游選型、原碼證據與採用邊界

研究日期2026-10-23，另保留2026-10-25 F04補記；2026-10-29合併三份研究。本次只整理既有內容，沒有重新上網查版本／授權、安裝、下載權重或執行上游。以下固定SHA、維護狀態、成本及優先次序都屬研究當時判斷；最新完成狀態以[ROADMAP](../../ROADMAP.md)及各項驗收為準，不以找到原碼宣稱整合或品質通過。

<a id="reuse-assessment"></a>

## 採用策略與固定來源

後續實作紀錄：2026-10-23 已按此策略完成 [R01 pose／depth 整合與有限實測](../structure-reference.md)，保留動漫骨架缺漏與構圖偏差；以下選型文字保留研究時判斷，實作狀態以 ROADMAP 與驗收文件為準。

R03 後續：[Fooocus 專用修補與八組比較](../fooocus-inpainting.md)已完成。功能可載入、生成、保存／離線還原，但本次動漫素材未得到優於一般 v2 的品質證據；不採用為預設或品質推薦，保留明確選擇的實驗入口與逐圖失敗觀察。LaMa／MAT、自動選區與 refine 仍是未接入候選，不由 R03 狀態推定完成。

### 優先採用決策

可以節省底層演算法與工作流程探索時間；最適合的方式是沿用現有 ComfyUI 邊界，選少量已實作節點，再補本平台的資料保存、能力檢查與驗收。以下是依原碼與介面差異作出的工程建議，並非已量測成效。

| 次序／範圍 | 優先來源 | 可沿用的工作 | 本平台仍需完成 |
| --- | --- | --- | --- |
| 1：R01 | controlnet_aux、Krita workflow | pose／depth 前處理與條件圖接線 | SDXL 控制權重、表單、版本／來源快照、原設定還原、動漫案例比較 |
| 2：R03 | comfyui-inpaint-nodes、Krita | 專用修補、預填、遮罩合成 | 模型相容性、接縫／色偏／遮罩外保留與角色特徵比較 |
| 後續：R03 選區輔助 | Anime Segmentation、Impact Pack；ADetailer 流程 | 動漫前景遮罩、偵測／裁切／修補／貼回 | 預覽與人工修改、座標還原、有限生成次數；不擴張為 R03 必要條件 |
| 後續：T02 標註效率、T03／T04 | sd-scripts；必要時 WD14 | 已有訓練器與標籤草稿 | 人工審查、獨立訓練環境、GPU 協調、產物回登與品質比較 |
| 已完成功能的局部改善 | InvokeAI、Krita、SwarmUI；Regional Prompter 設計 | 畫布／歷史／模型管理／區域提示的具體流程 | 先記錄可重現痛點或量測基準，再決定小範圍修改 |

動漫優先不表示只看名稱含 anime 的專案：動漫專用的前景分割／booru 標註與通用的 ComfyUI 修補／ControlNet 可互補。實際畫風主要仍取決於模型、參考條件與案例驗收；整合通用節點不能直接保證作者畫風或角色一致。

建議讓未完成的 **R01 → R03** 優先採用現有前處理／ComfyUI 節點，再完成本平台的表單、快照、保存還原與品質驗收。已完成項目依具體缺陷逐步借鏡，現階段沒有證據支持整套重寫。

### 候選與版本錨點

以下五個 HEAD 為查詢當時的 `main`，不是已驗證的相容版本。五者均未封存；狀態來源為各專案官方 repository API，後續可能改變。其他候選分列於本文件補充及兩份對照文件。

| 候選 | 本次固定 HEAD／提交日期 | LICENSE 檔內容 | 建議用途 |
| --- | --- | --- | --- |
| [comfyui_controlnet_aux](https://github.com/Fannovel16/comfyui_controlnet_aux) | [`a587a4c1594524c1d2de5cd1a86cd868ff448e1c`](https://github.com/Fannovel16/comfyui_controlnet_aux/commit/a587a4c1594524c1d2de5cd1a86cd868ff448e1c)／2026-10-11 | [Apache-2.0](https://github.com/Fannovel16/comfyui_controlnet_aux/blob/a587a4c1594524c1d2de5cd1a86cd868ff448e1c/LICENSE.txt) | R01 姿勢／深度條件圖前處理 |
| [comfyui-inpaint-nodes](https://github.com/Acly/comfyui-inpaint-nodes) | [`5b7681746fe19e563113d27366ba85236bc1ba5b`](https://github.com/Acly/comfyui-inpaint-nodes/commit/5b7681746fe19e563113d27366ba85236bc1ba5b)／2026-10-04 | [GNU GPL v3](https://github.com/Acly/comfyui-inpaint-nodes/blob/5b7681746fe19e563113d27366ba85236bc1ba5b/LICENSE) | R03 專用修補節點與遮罩品質 |
| [krita-ai-diffusion](https://github.com/Acly/krita-ai-diffusion) | [`828b70c33c5c97f326e03170cd693beef798231e`](https://github.com/Acly/krita-ai-diffusion/commit/828b70c33c5c97f326e03170cd693beef798231e)／2026-10-03 | [GNU GPL v3](https://github.com/Acly/krita-ai-diffusion/blob/828b70c33c5c97f326e03170cd693beef798231e/LICENSE) | R01／R03 workflow 組裝與畫布互動借鏡 |
| [InvokeAI](https://github.com/invoke-ai/InvokeAI) | [`cbc5ab0595d17e81289108b77229cd3886af7669`](https://github.com/invoke-ai/InvokeAI/commit/cbc5ab0595d17e81289108b77229cd3886af7669)／2026-10-23 | [Apache-2.0](https://github.com/invoke-ai/InvokeAI/blob/cbc5ab0595d17e81289108b77229cd3886af7669/LICENSE)，另有 [NOTICE](https://github.com/invoke-ai/InvokeAI/blob/cbc5ab0595d17e81289108b77229cd3886af7669/NOTICE) | 畫布、作品與任務呈現方式借鏡 |
| [sd-scripts](https://github.com/kohya-ss/sd-scripts) | [`11d8cedd0c67b93a10f8b2d75f43554f6f12c794`](https://github.com/kohya-ss/sd-scripts/commit/11d8cedd0c67b93a10f8b2d75f43554f6f12c794)／2026-10-20 | [Apache-2.0](https://github.com/kohya-ss/sd-scripts/blob/11d8cedd0c67b93a10f8b2d75f43554f6f12c794/LICENSE.md) | 延續 T02 已選的訓練工具介面，供 T03 評估；當時README 0.12.2、詳細變更、CI／回歸與SDXL資料介面，程式／權重／素材條件各自核對 |

未封存狀態查詢：[controlnet_aux API](https://api.github.com/repos/Fannovel16/comfyui_controlnet_aux)、[inpaint-nodes API](https://api.github.com/repos/Acly/comfyui-inpaint-nodes)、[Krita API](https://api.github.com/repos/Acly/krita-ai-diffusion)、[InvokeAI API](https://api.github.com/repos/invoke-ai/InvokeAI)、[sd-scripts API](https://api.github.com/repos/kohya-ss/sd-scripts)。

### 借用方式與本平台邊界

| 方式 | 適用範圍 | 要補的工作 |
| --- | --- | --- |
| 外部工具／節點 | 優先用於 R01 前處理、R03 推論、未來 T03 trainer | 固定版本與依賴、能力檢查、輸入輸出契約、錯誤處理及本機驗收 |
| 原碼與流程借鏡 | 遮罩處理順序、分層 UI、歷史與排隊呈現 | 理解設計後對應 Vue／FastAPI 的模組與資料模型，依需要保留來源紀錄 |
| 複製修改程式 | 邊界清楚且確實比自行實作省工的局部 | 逐檔核對授權／NOTICE／上游來源，記錄修改與測試，承擔後續維護 |
| 整套 UI／任務引擎移植 | 本輪不建議 | 同時引入另一套執行與持久化語義，未有證據顯示可節省總整合成本 |

平台已有 Vue → FastAPI → SQLite／本地檔案 → 獨立 ComfyUI 的分工，且不接受任意第三方節點圖；各專用流程需要完整模板與能力檢查。借用節點不改變此邊界，見[既有架構](../architecture.md)。

保留 UUID 冪等、原引擎關聯、不可變提交快照、精確 seed、未知提交結果的查核，以及訓練資料契約。上游的「重試」按鈕或新任務語義，不能直接取代平台的未知結果處理。[架構與任務狀態](../architecture.md)、[T02 資料契約](../training/dataset-contract.md)。

### R01：優先評估現成 pose／depth 前處理

固定版本提供 `DWPreprocessor`（條件圖與姿勢 keypoints）及 `DepthAnythingV2Preprocessor`（相對深度圖），可接入現有獨立 ComfyUI，省去自行實作姿勢／深度估計演算法。這些是 hint 前處理，仍須另選匹配 SDXL 的 ControlNet 權重與流程；README 中的 SD1.5 範例不能直接當作 Animagine 相容證據。[DWPose 原碼](https://github.com/Fannovel16/comfyui_controlnet_aux/blob/a587a4c1594524c1d2de5cd1a86cd868ff448e1c/node_wrappers/dwpose.py)、[相對深度節點](https://github.com/Fannovel16/comfyui_controlnet_aux/blob/a587a4c1594524c1d2de5cd1a86cd868ff448e1c/node_wrappers/depth_anything_v2.py)、[功能與模型對照](https://github.com/Fannovel16/comfyui_controlnet_aux/blob/a587a4c1594524c1d2de5cd1a86cd868ff448e1c/README.md#nodes)。

整合前需固定依賴與估計器權重；其 requirements 並非完整 lock，節點會呼叫 `from_pretrained`，不能假定初次運行離線。DWPose 的 provider 探測清單甚至包含 CPU provider，因此啟動訊息不能代替實際裝置／速度量測；README 舊 CUDA 指引也不直接套入目前環境。[依賴清單](https://github.com/Fannovel16/comfyui_controlnet_aux/blob/a587a4c1594524c1d2de5cd1a86cd868ff448e1c/requirements.txt)、[provider 與模型載入](https://github.com/Fannovel16/comfyui_controlnet_aux/blob/a587a4c1594524c1d2de5cd1a86cd868ff448e1c/node_wrappers/dwpose.py#L11-L27)。

建議先選一種 pose 或 depth 完成最小串接，保存來源圖、實際條件圖、前處理參數／版本與 hash，再驗證單次提交、離線讀取、精確還原與固定品質案例；通過後擴充第二種。這是 R01 內的實作方式建議，不改變原定 R01 → R03 順序。[R01 驗收](../../CHANGELOG.md#r01)。

### R03：優先評估 comfyui-inpaint-nodes

官方提供 Fooocus SDXL inpaint patch、LaMa／MAT 預填、遮罩膨脹／侵蝕／羽化、去雜值與色彩匹配；README 同時提供 simple、refine、outpaint 範例。這些與 R03 的接縫、邊界融合與遮罩外保留直接相關。[固定版 README](https://github.com/Acly/comfyui-inpaint-nodes/blob/5b7681746fe19e563113d27366ba85236bc1ba5b/README.md)、[節點原碼](https://github.com/Acly/comfyui-inpaint-nodes/blob/5b7681746fe19e563113d27366ba85236bc1ba5b/nodes.py)。

優先以外部 ComfyUI 節點組成少數受支援的專用模板，平台實作選項驗證與快照；預估整合成本中等。直接搬入 FastAPI 會連帶引入 torch、ComfyUI model patcher 與 GPU 管理，從原碼依賴看沒有必要。[依賴與模型 patch](https://github.com/Acly/comfyui-inpaint-nodes/blob/5b7681746fe19e563113d27366ba85236bc1ba5b/nodes.py#L5-L38)。

先處理以下界線，再決定採用版本：

- HEAD 使用 `comfy_api.latest.io.ComfyNode`；本機 ComfyUI 0.34.0 靜態核對已有對應 API 檔案，仍須逐節點檢查 schema、依賴、載入與完整 workflow，尚未安裝驗證。[新版節點 API](https://github.com/Acly/comfyui-inpaint-nodes/blob/5b7681746fe19e563113d27366ba85236bc1ba5b/nodes.py#L18)。
- Fooocus 需要額外 head／patch 權重；官方限制為一般 SDXL checkpoint，Turbo／Lightning／Hyper 蒸餾合併版不適用。Animagine 候選仍需實測，不能由 SDXL 名稱直接宣告通過。[使用限制](https://github.com/Acly/comfyui-inpaint-nodes/blob/5b7681746fe19e563113d27366ba85236bc1ba5b/README.md#fooocus-inpaint)。
- refine 的 `latent_inpaint` 與 `latent_samples` 接線不同；遮罩降噪強度與最終合成遮罩也有不同目的。錯接可能產生品質問題，應保存處理版本與各參數。[conditioning](https://github.com/Acly/comfyui-inpaint-nodes/blob/5b7681746fe19e563113d27366ba85236bc1ba5b/README.md#inpaint-conditioning)、[合成遮罩](https://github.com/Acly/comfyui-inpaint-nodes/blob/5b7681746fe19e563113d27366ba85236bc1ba5b/README.md#denoise-to-compositing-mask)。
- 色彩匹配節點針對整張輸出都出現色偏的情形；不能當作每次必開的品質保證。遮罩外保留與色偏仍依固定案例實測。[色彩匹配適用條件](https://github.com/Acly/comfyui-inpaint-nodes/blob/5b7681746fe19e563113d27366ba85236bc1ba5b/README.md#color-match-masked)。

驗收沿用 R03：同素材、同模型、同 seed 比較基準與候選；保存原遮罩、處理後遮罩、半徑與合成方式，記錄接縫、色偏、截斷及遮罩外改變。安裝成功或產生一張圖不能取代品質比較。[R03 原定範圍](../../ROADMAP.md)。

### Krita AI Diffusion：借用工作流程設計

官方支援選區修補、畫布即時預覽、ControlNet 姿勢／深度、參考圖、區域提示、排隊與歷史；推論後端同樣是 ComfyUI，適合查驗 R01／R03 如何組合節點。[固定版 README](https://github.com/Acly/krita-ai-diffusion/blob/828b70c33c5c97f326e03170cd693beef798231e/README.md#features)。

可讀的具體接縫是 `backend/workflow.py` 的控制條件與遮罩處理順序，以及 `comfy_workflow.py` 對節點名稱／輸入的封裝。依這些設計建立本平台專用流程，預估成本中等；直接移植整個插件成本高。[workflow](https://github.com/Acly/krita-ai-diffusion/blob/828b70c33c5c97f326e03170cd693beef798231e/ai_diffusion/backend/workflow.py#L605)、[Comfy workflow builder](https://github.com/Acly/krita-ai-diffusion/blob/828b70c33c5c97f326e03170cd693beef798231e/ai_diffusion/backend/comfy_workflow.py#L59)。

直接搬 UI／任務模型並不順接 Vue：插件依賴 Krita，任務模型使用 PyQt6 的 QObject／signal；其 Comfy client 也有自己的排隊、上傳與事件處理。[Krita 環境要求](https://github.com/Acly/krita-ai-diffusion/blob/828b70c33c5c97f326e03170cd693beef798231e/README.md#installation)、[Qt 任務模型](https://github.com/Acly/krita-ai-diffusion/blob/828b70c33c5c97f326e03170cd693beef798231e/ai_diffusion/model/jobs.py#L143)。

不能只抄節點名稱：官方資源表固定 ComfyUI 與各 custom node revision；目前插件的 inpaint-nodes pin 也不是該專案查詢當時 HEAD。這是相容組合的參考，尚不是本平台驗證結果。[資源版本表](https://github.com/Acly/krita-ai-diffusion/blob/828b70c33c5c97f326e03170cd693beef798231e/ai_diffusion/backend/resources.py#L13-L60)。

其 client 會主動提供 `prompt_id` 並檢查回傳值，錯配時要求 ComfyUI 0.3.45 以上；可借鏡相容檢查，但不能直接搬其例外處理就宣稱與本平台持久化 UUID／unknown 語義相同。[提交實作](https://github.com/Acly/krita-ai-diffusion/blob/828b70c33c5c97f326e03170cd693beef798231e/ai_diffusion/backend/comfy_client.py#L302-L325)。

### InvokeAI：以畫布、歷史與佇列的互動借鏡為主

官方提供網頁畫布、inpaint／outpaint、節點工作流程、作品 board／gallery、模型管理與設定回取。適合作為使用流程比較對象，不能由功能清單推定本平台應全部補齊。[固定版 README](https://github.com/invoke-ai/InvokeAI/blob/cbc5ab0595d17e81289108b77229cd3886af7669/README.md#features)。

原碼同時包含 webv1、webv2；本次主要看 webv2。其 React／TanStack 前端與 Vue 不同，後端雖同用 FastAPI，queue API 仍連到 Invoke 自身 invoker、session 與資料庫服務，整包移植成本高。[webv2 dependencies](https://github.com/invoke-ai/InvokeAI/blob/cbc5ab0595d17e81289108b77229cd3886af7669/invokeai/frontend/webv2/package.json#L51-L74)、[queue API](https://github.com/invoke-ai/InvokeAI/blob/cbc5ab0595d17e81289108b77229cd3886af7669/invokeai/app/api/routers/session_queue.py#L261-L281)。

可借鏡的具體設計包括：

- 活躍任務與已保存作品分開呈現、進度預覽不納入作品計數；有助於出現預覽／作品混淆的實際問題時比較。[queue 設計](https://github.com/invoke-ai/InvokeAI/blob/cbc5ab0595d17e81289108b77229cd3886af7669/invokeai/frontend/webv2/src/features/queue/README.md)。
- 從任務快照讀提示與尺寸，保留事件順序欄位；可作歷史回取或舊事件覆寫問題的檢查案例。[history snapshot](https://github.com/invoke-ai/InvokeAI/blob/cbc5ab0595d17e81289108b77229cd3886af7669/invokeai/frontend/webv2/src/features/queue/core/historySnapshot.ts)、[事件契約](https://github.com/invoke-ai/InvokeAI/blob/cbc5ab0595d17e81289108b77229cd3886af7669/invokeai/frontend/webv2/src/features/queue/data/events.ts#L30-L42)。
- 將預填、生成、遮罩合成分成明確步驟；實作借鏡前先核對白色代表保留或重繪，其畫布契約不能直接套用到本平台遮罩。[canvas graph](https://github.com/invoke-ai/InvokeAI/blob/cbc5ab0595d17e81289108b77229cd3886af7669/invokeai/frontend/webv2/src/features/generation/core/canvas/compileCanvasGraph.ts#L421-L504)。

以上是可對照的設計，不是本輪已證實的平台缺陷。已完成的 UI、歷史、作品庫、取消／停止流程先保留；只有具體問題、可重現案例與改善目標成立，才安排局部修改。

### ComfyUI 原生補充：Impact Pack 與 WD14

以下兩者均未封存，但仍是待驗證候選；官方 API 查詢入口：[Impact Pack](https://api.github.com/repos/ltdrdata/ComfyUI-Impact-Pack)、[WD14 Tagger](https://api.github.com/repos/pythongosssss/ComfyUI-WD14-Tagger)。

| 候選 | 固定版本／提交日期 | 來源與判斷 |
| --- | --- | --- |
| ComfyUI-Impact-Pack | `429d0159ad429e64d2b3916e6e7be9c22d025c3c`／2026-04-19，分支 Main | [README](https://github.com/ltdrdata/ComfyUI-Impact-Pack/blob/429d0159ad429e64d2b3916e6e7be9c22d025c3c/README.md)、[GPL v3](https://github.com/ltdrdata/ComfyUI-Impact-Pack/blob/429d0159ad429e64d2b3916e6e7be9c22d025c3c/LICENSE.txt)。已有 detector、SEGS、detailer、裁切／貼回及相容性變更紀錄，可評估為 R03 基本修補完成後的外部節點。 |
| ComfyUI-WD14-Tagger | `9e0a6e700299182fc05c58b62e7ad9f72182a78b`／2025-07-11 | [README](https://github.com/pythongosssss/ComfyUI-WD14-Tagger/blob/9e0a6e700299182fc05c58b62e7ad9f72182a78b/README.md)、[MIT](https://github.com/pythongosssss/ComfyUI-WD14-Tagger/blob/9e0a6e700299182fc05c58b62e7ad9f72182a78b/LICENSE)。動漫 booru 標籤候選；有批次、一般／角色門檻與排除標籤，維護較舊，不能當作最新模型選型。 |

Impact Pack 比直接移植 A1111 的 ADetailer 更貼近現有引擎，但它是通用工具；動漫偵測效果仍取決於另選權重。`UltralyticsDetectorProvider` 需要獨立 Impact Subpack，不能只安裝主包就宣稱具備全部功能。其 README 的 8.24 要求 ComfyUI 至少 0.3.63；本機 0.34.0 的版本號不代表依賴與完整流程已驗證。先選最少節點，明確保存各區域遮罩、裁切座標、seed、修補次數與輸出，不沿用 auto retry 節點；多次 detailer 採樣也不能隱藏為一次推論。[固定 README 與限制](https://github.com/ltdrdata/ComfyUI-Impact-Pack/blob/429d0159ad429e64d2b3916e6e7be9c22d025c3c/README.md)。

WD14 可減少第一次人工輸入標籤，但只寫待審草稿，不自動確認角色身分、來源用途、caption approved 或變更資料分割。其 [wd14tagger.py](https://github.com/pythongosssss/ComfyUI-WD14-Tagger/blob/9e0a6e700299182fc05c58b62e7ad9f72182a78b/wd14tagger.py) 在模型缺少時會下載，且依賴 Comfy server／ONNX runtime；不能直接匯入 FastAPI。若採用，先固定匹配的 ONNX 與 tags CSV、hash、provider、門檻與排除規則，明確準備離線模型。優先比較 T02 已選 sd-scripts 的標註工具是否足夠，避免同時維護兩套相同能力。

這兩個候選與動漫專用分割、Regional Prompter 是後續優化選項，沒有因此新增必做功能或延後 R01 → R03。

### 訓練、授權與完成判定

前述畫布／ControlNet／修補整合主要服務推論，不能替代 T03 的訓練環境／GPU 協調或 T04 的產物回登／品質比較。T02 已對 sd-scripts 固定版本研究，不必再搬一套推論平台作為 trainer。[訓練工具介面研究](../training/tool-interface-research.md)、[訓練需求](../training/requirements.md)。

採納程式碼前須逐項記錄來源、固定 commit、檔案授權、修改與適用 NOTICE；此處只整理 LICENSE 事實，不作整合方案的法律結論。程式碼授權不能自動涵蓋權重、訓練圖片、模型輸出或第三方依賴，權重應另核對來源與條件。

先借用缺少的能力，平台繼續掌握提交、版本、資料與驗收。硬體限制、未備妥的實機觸控、圖片來源用途與人工品質判讀，仍需各自解決，不能因採用既有專案便標記通過。

### 後續開發採用方式

每個新功能先查 2–3 個貼近現有架構的候選，先讀原碼與限制，再選外部依賴、局部複用或介面借鏡。以「選型＋適配＋驗收＋未來維護」評估總成本；功能清單、星數與截圖只能當線索，不能代替成本或品質證據。

每個實作項目留下簡短採用紀錄：需求與基準 → 候選及固定 SHA → 採用節點／原碼位置與授權 → 相容依賴／權重 → 最小有限案例結果 → 平台封裝與回歸 → 是否採納。先在獨立引擎環境驗證，不把上游整套 requirements 合併進 FastAPI；若沒有品質或總維護成本的改善，就保留現有功能並記錄不採用原因。需要使用者補圖片時，沿用[圖片提醒](../anime-style-development.md#image-input-reminders)及 T02 的資料用途審查，不因標籤工具可讀取整個資料夾就把圖片全納入訓練。

未完成的 R01／R03 先用這個方式減少底層重造；T03／T04 仍另排並沿用 T02 契約。已完成項目只在具體痛點、缺陷或可量測改善成立時開局部改動，保留原工作流程與歷史資料格式；避免為外觀接近其他平台而全面改寫。每項實作仍依使用者約定，驗收、commit、push 後才進下一項。


### 2026-10-25 F04 落地補記

已以現有 ComfyUI 原生 `LoraLoaderModelOnly`、`LoadImage`、`VAEEncode` 接入兩個獨立 Schnell 流程，保留本平台的 UUID、來源快照、作品保存與草稿格式；未移植另一套推論／訓練服務。公開 PVC Schnell LoRA 只當作固定相容性案例，模型卡條款宣告及尚未證明的資料來源分開保存。RTX 3060 四案例已有 [實測](../validation/flux-extensions-20261025.md)，後續作者圖片與未知能力的界線見 [F04 指引](../models/flux-extensions.md)。


<a id="anime-candidates"></a>

## 動漫專題：分割、區域提示、修補與標註

下列是同次研究的專用補充；sd-scripts及標註／訓練邊界與上節相同，不因此新增trainer或跳過人工審查。

### 候選與固定來源

| 候選／類型 | 固定 commit | 維護與成熟證據 | 原碼授權觀察 |
| --- | --- | --- | --- |
| [Regional Prompter](https://github.com/hako-mikan/sd-webui-regional-prompter)／通用、動漫構圖適用 | `b10c496dbcb9c94be0d5d64edda8511460cc9d28` | 未封存；API 最近 push 2026-09-04；README 有 Attention／Latent、區域 LoRA、WebUI／Forge 相容矩陣及限制 | GitHub API 標示 AGPL-3.0；直接移植前核對固定版本與逐檔來源 |
| [ADetailer](https://github.com/Bing-su/adetailer)／通用、包含 2D 偵測模型 | `3a599f5d4607d8f9d8b9fc5a15526197418dae1a` | 未封存；最近 push 2026-10-19；包含 tests 與 CI，README 提供遮罩處理順序、模型表及限制 | AGPL-3.0；README 說明 WebUI／Ultralytics 衍生關係，權重另核對 |
| [Anime Segmentation](https://github.com/skytnt/anime-segmentation)／動漫專用 | `55d874013a2811cdf59c365059174c7823acf5b4` | 未封存；最近 push 2025-05-21；有訓練、推論、ONNX 匯出及公開示範；維護頻率較低，不等同現代環境已通過 | Apache-2.0；支援網路與下載權重／資料集來源仍分開核對 |
| [WD14 Tagger WebUI](https://github.com/picobyte/stable-diffusion-webui-wd14-tagger)／動漫 booru 標籤適用 | `e72d984bdbed832ba83e2a443238c3851b9088ae` | 未封存；最近 push 2024-05-14；有批次標註、模型比較、pylint workflow；維護較舊，列次選參考 | API 無統一 SPDX；README 寫 public domain，但明確排除 borrowed parts，不能把整庫當公有領域 |

API 查核入口：[Regional Prompter](https://api.github.com/repos/hako-mikan/sd-webui-regional-prompter)、[ADetailer](https://api.github.com/repos/Bing-su/adetailer)、[Anime Segmentation](https://api.github.com/repos/skytnt/anime-segmentation)、[sd-scripts](https://api.github.com/repos/kohya-ss/sd-scripts)、[WD14 Tagger](https://api.github.com/repos/picobyte/stable-diffusion-webui-wd14-tagger)。push 日期是整個倉庫活動訊號，不代表特定功能的最後修正日。`skytnt/anime-seg` GitHub 路徑返回 404；正確原碼倉庫為 `anime-segmentation`，`anime-seg` 是其 README 指向的 Hugging Face 權重名稱。

### 可節省時間的整合方式

#### R03：先借鑑自動遮罩與局部修補流程

ADetailer 的流程是生成 → 偵測 → 遮罩 → 修補；[固定 README](https://github.com/Bing-su/adetailer/blob/3a599f5d4607d8f9d8b9fc5a15526197418dae1a/README.md) 說明 confidence、面積篩選、位移、膨脹／侵蝕、合併／反轉及個別修補提示。[mask.py](https://github.com/Bing-su/adetailer/blob/3a599f5d4607d8f9d8b9fc5a15526197418dae1a/adetailer/mask.py) 提供具體處理順序，tests/test_mask.py 是邊界測試參考。

建議本平台先沿用既有遮罩資產與 Comfy 工作流程，增加可預覽、可手動修正的偵測遮罩候選，再比較羽化、接縫與遮罩外保留。ADetailer 是 A1111 擴充；README 明說開發測試以 SD1.5／A1111 為主，不能據此宣稱本平台 SDXL 相容。自動修臉可能改掉棕髮綠眼角色特徵，應保留開關、原圖和前後比較。模型表中的 2D 能力也不代表我們的畫風已通過。

動漫專用的 Anime Segmentation 適合「角色前景選區」輔助。[inference.py](https://github.com/skytnt/anime-segmentation/blob/55d874013a2811cdf59c365059174c7823acf5b4/inference.py) 的 get_mask 保持長寬比縮放、補邊、移除補邊後還原原尺寸，能作為座標一致性參考；它輸出前景遮罩，不能取代姿勢骨架、深度或角色身分辨識。README 命令寫 `--data-dir`，該固定原碼 parser 實際為 `--data`，採用時以原碼核對。建議隔離推論或另驗證 ONNX 執行，測試頭髮、透明配件、多人與背景相近色；不直接把訓練依賴加進平台環境。

#### R01／R02／L01／R05：區域提示可借鏡，不能直接取代已完成流程

[Regional Prompter README](https://github.com/hako-mikan/sd-webui-regional-prompter/blob/b10c496dbcb9c94be0d5d64edda8511460cc9d28/README.md) 有區域比例、共用／基底提示、區域 LoRA 與可視化範本，可作為多人髮色串色、衣著與背景分離的後續試驗基礎。[attention.py](https://github.com/hako-mikan/sd-webui-regional-prompter/blob/b10c496dbcb9c94be0d5d64edda8511460cc9d28/scripts/attention.py) 直接依賴 WebUI modules／Forge 探測與 attention hook，不能複製進 FastAPI 或當 Comfy 節點使用。

建議先用 Comfy 原生區域 conditioning 做最小比較；只有可量測改善且現有節點不足，才評估額外節點或獨立實作。它不提供 R01 所需的姿勢／深度前處理，也不替代 R02 IP-Adapter 或 T04 身分驗收。L01 多 LoRA 與 R05 提示基準可增加區域開關的有限對照，但舊證據保持不變；區域 Latent 模式可能增加生成時間，須量測而非假定加速。

#### T01–T04：沿用 sd-scripts 邊界，標籤只作人工審查草稿

sd-scripts 已是 T02 固定候選，詳見 [既有介面研究](../training/tool-interface-research.md)。T03 採獨立環境與受控工作入口，平台負責資料版本、GPU 工作協調、取消與失敗狀態；T04 負責 LoRA 產物 hash、回登與固定比較。上游已解決訓練演算法與資料讀取，可省去自製 trainer，但不包含本平台的工作持久化與權重回登驗收。新增模型支援或記憶體優化不應直接套用到 SDXL，須逐項核對適用架構。

[WD14 README](https://github.com/picobyte/stable-diffusion-webui-wd14-tagger/blob/e72d984bdbed832ba83e2a443238c3851b9088ae/README.md) 提供單張／批次 booru 標籤；[interrogator.py](https://github.com/picobyte/stable-diffusion-webui-wd14-tagger/blob/e72d984bdbed832ba83e2a443238c3851b9088ae/tagger/interrogator.py) 依賴 WebUI 全域設定、ONNX providers 與 Hugging Face 下載。建議只參考標籤篩選／人工修訂流程，優先評估 sd-scripts 已有標註工具以減少另一組依賴。下載來源與版本須顯式固定，不能默默首次連網下載。自動輸出只能填入待審 caption 草稿，不能自動標記 approved、確認角色身分或來源用途；保持 T02 單行 caption、原作分組、保留集及曝光紀錄。

### 建議採用次序與驗收界線

1. 維持 R01 → R03；本份候選中，R03 的遮罩流程最能直接借鑑。R01 應使用另行研究的 Comfy 原生前處理與匹配 SDXL 控制模型。
2. R03 通過基本專用修補後，再小範圍比較動漫前景選區；不把新增去背功能擴張成 R03 完成的先決條件。
3. T03／T04 依既定排程使用 sd-scripts；標註輔助先改善人工審查耗時，不跳過使用者來源與角色審查。
4. Regional Prompter 列 R02／L01／R05 後續品質改善參考，先有具體串色問題與比較資料再新增區域 UI。

每次整合至少保存固定上游版本、採用的功能／檔案來源、依賴與權重版本、輸入／前處理／遮罩座標、實測限制。直接採用原碼前逐檔核對授權並保留通知；流程借鑑與原碼移植分開記錄。五個候選的本機相容性、VRAM、畫風效果、恢復／還原行為均尚未驗證，研究完成不關閉任何 ROADMAP 實作驗收框。


<a id="roadmap-map"></a>

## 2026-10-23 ROADMAP映射快照

以下47主項、27已完成／20未完成是研究當時的快照，**不是當前待辦**；後來F01–F04、E02等已有獨立進展。保留原分類及判斷供追溯，不重寫成新研究或改動現行ROADMAP勾選。

### 映射來源代號

K＝Krita、I＝InvokeAI，固定SHA／授權沿用上方共同版本表。研究額外核對：[Krita README](https://github.com/Acly/krita-ai-diffusion/blob/828b70c33c5c97f326e03170cd693beef798231e/README.md)與[workflow.py](https://github.com/Acly/krita-ai-diffusion/blob/828b70c33c5c97f326e03170cd693beef798231e/ai_diffusion/backend/workflow.py)，其中Illustrious、line art、pose、depth、IP-Adapter最接近動漫繪畫，但Qt不直接移入Vue；[InvokeAI README](https://github.com/invoke-ai/InvokeAI/blob/cbc5ab0595d17e81289108b77229cd3886af7669/README.md)與[session_queue_default.py](https://github.com/invoke-ai/InvokeAI/blob/cbc5ab0595d17e81289108b77229cd3886af7669/invokeai/app/services/session_queue/session_queue_default.py)提供Canvas、Board/Gallery、metadata recall及摘要／冪等／資料庫分工，仍不整套替換推論核心。

S／C是映射額外引用的固定來源：

| 代號／候選 | 固定SHA、README、授權 | 參考位置與限制 |
| --- | --- | --- |
| S：SwarmUI | `d74f8ce40d1e49161da61ddb74f87e6ebf11f7ad`；[README](https://github.com/mcmonkeyprojects/SwarmUI/blob/d74f8ce40d1e49161da61ddb74f87e6ebf11f7ad/README.md)、[MIT](https://github.com/mcmonkeyprojects/SwarmUI/blob/d74f8ce40d1e49161da61ddb74f87e6ebf11f7ad/LICENSE.txt) | [WorkflowGenerator.cs](https://github.com/mcmonkeyprojects/SwarmUI/blob/d74f8ce40d1e49161da61ddb74f87e6ebf11f7ad/src/BuiltinExtensions/ComfyUIBackend/WorkflowGenerator.cs)：表單轉Comfy圖、能力集合、模型能力及grid；當時v0.9.8 Beta／Almost-Release，不是已穩定正式版；C#/.NET不直接移植 |
| C：ComfyUI | `bc5f880dbdd43e426077f42ccec53bb577ffee9f`；[README](https://github.com/Comfy-Org/ComfyUI/blob/bc5f880dbdd43e426077f42ccec53bb577ffee9f/README.md)、[GPL v3](https://github.com/Comfy-Org/ComfyUI/blob/bc5f880dbdd43e426077f42ccec53bb577ffee9f/LICENSE) | [model_management.py](https://github.com/Comfy-Org/ComfyUI/blob/bc5f880dbdd43e426077f42ccec53bb577ffee9f/comfy/model_management.py)：VRAM／裝置／offload；官方支援表不能取代本機權重／節點／workflow驗證 |

S／C由當時官方commit API固定：[SwarmUI](https://api.github.com/repos/mcmonkeyprojects/SwarmUI/commits/d74f8ce40d1e49161da61ddb74f87e6ebf11f7ad)、[ComfyUI](https://api.github.com/repos/Comfy-Org/ComfyUI/commits/bc5f880dbdd43e426077f42ccec53bb577ffee9f)。其他節點／trainer沿用上方來源及[T02介面研究](../training/tool-interface-research.md)，不要求把現有引擎升到HEAD。

### 逐項映射

來源代號均指上方固定版來源。以下是工程選型判斷；「借鏡」表示候選設計，尚未證明比現有實作更好。「保留」代表沒有找到需要重寫的具體缺陷。

| 主項 | 狀態 | 參考／採用方式 | 本平台仍需完成或保留的條件 |
| --- | --- | --- | --- |
| Q01 文件入口 | 完成 | K／I 的功能到指南分層，借鏡 | 保留現有索引；新增上游對照連結即可。 |
| Q02 配置與依賴 | 完成 | I 服務分工，借鏡 | 保留 create_app／AppContext；不搬其推論核心。 |
| Q03 API 契約 | 完成 | I 佇列摘要型別，借鏡 | 保留 Vue 型別、取消載入與現有契約測試。 |
| Q04 分頁與成長 | 完成 | I 佇列摘要／資料庫查詢，借鏡 | 只在量測發現瓶頸後比較；保留 SQLite 摘要投影。 |
| Q05 未保存保護 | 完成 | K 的創作工作流，僅 UX 候選 | 未查到可直接取代現有 pending 契約的元件；保留。 |
| Q06 品質檢查 | 完成 | K 原庫 tests，可參考案例分類 | 不替換本平台品質入口；新增節點必須加本地回歸。 |
| Q07 備份還原 | 完成 | 無直接適配的已核實元件 | 保留 SQLite＋對應檔案一致性工具，上游模型搬移不等於備份。 |
| Q08 導覽與狀態 | 完成 | S 的 Generate／工作流分層、I Gallery，借鏡 | 具體使用問題出現後才改；保持能力可用與否的明確狀態。 |
| Q09 診斷 | 完成 | C 裝置資訊與 S 能力集合，借鏡 | 保留可控診斷及去敏感資訊；引擎訊息不當成實測。 |
| Q10 維護規則 | 完成 | 無需上游替換 | 持續遵守[維護邊界](../architecture.md#submission-invariants)的格式、狀態與功能分開提交。 |
| E01 裝置辨識 | 完成 | C model_management，交叉查證 | 保留既有裝置驗證；遠端引擎和平台裝置不可混用。 |
| E02 RTX 4080 實測 | 未完成 | C 僅作設定參考 | 必須取得指定主機並實測，原碼不能補足。 |
| E03 雙機比較 | 未完成 | C 僅作環境對照 | 相同權重／seed／流程的實機數據仍必要。 |
| E04 推論與訓練資源 | 未完成 | C＋T02 trainer 介面，借鏡 | 推論、訓練分開測；不得以通用 VRAM 宣傳數字代替。 |
| E05 資源取樣 | 完成 | C 的 VRAM 狀態，僅交叉查證 | 保留任務 journal／峰值未知語義；不重寫。 |
| V01 筆刷觸控 | 未完成 | K 畫布／選區操作，借鏡 | 實體觸控裝置仍缺；使用者已同意保留待驗收。 |
| V02 pending 恢復 | 完成 | I 佇列與冪等只作比較 | 保留原 UUID／原引擎／未知結果查核，不採自動重送。 |
| V03 整理比較窄窗 | 完成 | I Board／Gallery，借鏡 | 以具體窄窗操作缺陷為改動依據，保留人工評分。 |
| V04 比較量測 UI | 完成 | S Grid Generator，流程借鏡 | 不導入自動批次；保留既有量測定義。 |
| V05 設定交換 | 完成 | K 預設與 S 參數表單，借鏡 | 保留專用格式版本、精確 seed、拒絕部分轉換。 |
| V06 視覺與無障礙 | 完成 | I Canvas／Gallery，視覺參考 | 上游外觀不是無障礙通過證據；保持本地驗收。 |
| M01 Pony 授權 | 未完成 | 無替代工具 | 必須回到指定權重作者完整條款；其他 UI 支援 Pony 不能解決。 |
| L01 多 LoRA 品質 | 完成 | K LoRA／style 操作，借鏡 | 保留固定案例結果；新組合另驗，無需重做既有項目。 |
| F01 FLUX 安裝 | 未完成 | C 官方支援／範例入口 | 指定權重來源存取、hash、安裝仍必須完成。 |
| F02 FLUX 精度資源 | 未完成 | C model_management，流程參考 | 實際精度、offload、元件授權逐項核對。 |
| F03 FLUX 端到端 | 未完成 | C＋S 組圖能力，借鏡 | 本平台提交／OOM／保存還原仍須實機驗收。 |
| F04 FLUX 擴充 | 未完成 | C／K／S 功能入口，候選調查 | 各模型家族相容性獨立確認，不能套 SDXL adapter。 |
| R01 pose／depth | 完成 | 優先 aux 外部節點＋K 組圖流程 | 已完成固定 SDXL pose／depth 與條件圖；見 structure-reference.md，動漫偵測偏差保留。 |
| R02 參考 adapter | 完成 | K IP-Adapter 操作，借鏡 | 保留既有證據；新參考方式才新增品質比較。 |
| R03 inpainting | 完成 | 優先 Acly inpaint 節點＋K 選區流程 | 已完成 Fooocus 固定模板與八組比較；品質未優於一般 v2，保留實驗選項，見 fooocus-inpainting.md。 |
| R04 Pony Canny | 完成 | K／S 條件與 LoRA 組圖，借鏡 | 保留已驗證結果；M01 未完成不由此消除。 |
| R05 品質案例 | 完成 | K style presets，借鏡 | 作者提示效應仍以固定模型與人工結果判斷。 |
| R06 比較軸 | 完成 | S Grid Generator，流程參考 | 現有比較軸足夠先保留，不為對齊功能而新增批次。 |
| R07 格式邊界評估 | 完成 | S 組圖與 K workflow input，借鏡 | 保留已完成的格式評估與草稿／提交快照區隔；不把評估完成當成局部編輯／Canny 已支援一般交換。 |
| T01 需求 | 完成 | 無需重寫 | 保留風格／角色兩軌與驗收範圍。 |
| T02 資料工具 | 完成 | sd-scripts，沿用已核實介面 | 保留去重分組、holdout、標註／來源人工審查與封包驗證。 |
| T03 訓練環境 | 未完成 | sd-scripts 外部工具，優先 | 獨立 venv／依賴與 GPU 協調，不匯入 FastAPI；原始圖標註未完成。 |
| T04 產物評估 | 未完成 | K LoRA 使用流程＋本平台既有比較 | 產物 hash／來源、Comfy key 載入及固定 baseline 驗證。 |
| D01 遠端存取 | 未完成 | S 遠端部署入口，僅方案參考 | 需先決定信任範圍、認證及連線保護；不能直接公開引擎埠。 |
| D02 Docker | 未完成 | S README 雲端範例，候選入口 | README 的 Runpod 模板註明第三方維護，非本平台官方方案；需另做持久化／GPU／還原驗證。 |
| A01 NovelAI | 未完成 | 通用平台不能代替官方來源 | 先查官方服務契約與公開介面，不採逆向或帳號抓取套件。 |
| A02 Mango 2 | 未完成 | 無可核實對應，不指定第三方 | 先確認服務身分與官方來源，不能憑名稱整合。 |
| A03 服務介面 | 未完成 | I API 模型／C partner nodes 僅概念參考 | 官方能力和本平台不可變請求快照先對齊。 |
| A04 憑證 | 未完成 | 未核實可直接採用的專用元件 | 設計後端保管及遮蔽；不從 UI 範例照抄明文保存。 |
| A05 傳送與費用 | 未完成 | 未核實可直接套用的費用 UI | 必須來自指定服務實際計價／傳送內容；保留提交前確認。 |
| A06 重試扣費 | 未完成 | I 冪等佇列作概念參考 | 服務端是否有冪等／查詢能力需官方確認，未知扣費不可自動重送。 |
| A07 遠端保存 | 未完成 | I metadata recall，流程借鏡 | 保存請求／供應商版本／原始結果，憑證不進作品快照。 |

### 契約上的具體差異

上游方法先依原碼、最小輸入／輸出與有限案例選型，不改變Vue→FastAPI→SQLite／本地檔案→獨立ComfyUI。例：Krita的generate_seed因Qt限制只產生32-bit，不能取代本平台64-bit字串。硬體、觸控、權重來源與品質仍需各自驗收；已完成項只因可重現缺陷或量測改善修改。以上研究未改勾選、下載模型或執行第三方程式，實作沿用[架構](../architecture.md)及[維護規則](../quality-checks.md#static-checks)。
