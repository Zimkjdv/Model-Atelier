# GitHub 專案借用初評（2026-10-23）

本文件是初步選型：本輪僅讀官方 README、原始碼、授權與 GitHub API，尚未新增整合、安裝、執行第三方程式或完成實機驗收。成本為依介面差異的工程判斷，沒有量測可承諾的加速百分比。

建議讓未完成的 **R01 → R03** 優先採用現有前處理／ComfyUI 節點，再完成本平台的表單、快照、保存還原與品質驗收。已完成項目依具體缺陷逐步借鏡，現階段沒有證據支持整套重寫。

## 候選與版本錨點

以下 HEAD 為查詢當時的 `main`，不是已驗證的相容版本。五者均未封存；狀態來源為各專案官方 repository API，後續可能改變。

| 候選 | 本次固定 HEAD／提交日期 | LICENSE 檔內容 | 建議用途 |
| --- | --- | --- | --- |
| [comfyui_controlnet_aux](https://github.com/Fannovel16/comfyui_controlnet_aux) | [`a587a4c1594524c1d2de5cd1a86cd868ff448e1c`](https://github.com/Fannovel16/comfyui_controlnet_aux/commit/a587a4c1594524c1d2de5cd1a86cd868ff448e1c)／2026-10-11 | [Apache-2.0](https://github.com/Fannovel16/comfyui_controlnet_aux/blob/a587a4c1594524c1d2de5cd1a86cd868ff448e1c/LICENSE.txt) | R01 姿勢／深度條件圖前處理 |
| [comfyui-inpaint-nodes](https://github.com/Acly/comfyui-inpaint-nodes) | [`5b7681746fe19e563113d27366ba85236bc1ba5b`](https://github.com/Acly/comfyui-inpaint-nodes/commit/5b7681746fe19e563113d27366ba85236bc1ba5b)／2026-10-04 | [GNU GPL v3](https://github.com/Acly/comfyui-inpaint-nodes/blob/5b7681746fe19e563113d27366ba85236bc1ba5b/LICENSE) | R03 專用修補節點與遮罩品質 |
| [krita-ai-diffusion](https://github.com/Acly/krita-ai-diffusion) | [`828b70c33c5c97f326e03170cd693beef798231e`](https://github.com/Acly/krita-ai-diffusion/commit/828b70c33c5c97f326e03170cd693beef798231e)／2026-10-03 | [GNU GPL v3](https://github.com/Acly/krita-ai-diffusion/blob/828b70c33c5c97f326e03170cd693beef798231e/LICENSE) | R01／R03 workflow 組裝與畫布互動借鏡 |
| [InvokeAI](https://github.com/invoke-ai/InvokeAI) | [`cbc5ab0595d17e81289108b77229cd3886af7669`](https://github.com/invoke-ai/InvokeAI/commit/cbc5ab0595d17e81289108b77229cd3886af7669)／2026-10-23 | [Apache-2.0](https://github.com/invoke-ai/InvokeAI/blob/cbc5ab0595d17e81289108b77229cd3886af7669/LICENSE)，另有 [NOTICE](https://github.com/invoke-ai/InvokeAI/blob/cbc5ab0595d17e81289108b77229cd3886af7669/NOTICE) | 畫布、作品與任務呈現方式借鏡 |
| [sd-scripts](https://github.com/kohya-ss/sd-scripts) | [`11d8cedd0c67b93a10f8b2d75f43554f6f12c794`](https://github.com/kohya-ss/sd-scripts/commit/11d8cedd0c67b93a10f8b2d75f43554f6f12c794)／2026-10-20 | [Apache-2.0](https://github.com/kohya-ss/sd-scripts/blob/11d8cedd0c67b93a10f8b2d75f43554f6f12c794/LICENSE.md) | 延續 T02 已選的訓練工具介面，供 T03 評估 |

未封存狀態查詢：[controlnet_aux API](https://api.github.com/repos/Fannovel16/comfyui_controlnet_aux)、[inpaint-nodes API](https://api.github.com/repos/Acly/comfyui-inpaint-nodes)、[Krita API](https://api.github.com/repos/Acly/krita-ai-diffusion)、[InvokeAI API](https://api.github.com/repos/invoke-ai/InvokeAI)、[sd-scripts API](https://api.github.com/repos/kohya-ss/sd-scripts)。

## 借用方式與本平台邊界

| 方式 | 適用範圍 | 要補的工作 |
| --- | --- | --- |
| 外部工具／節點 | 優先用於 R01 前處理、R03 推論、未來 T03 trainer | 固定版本與依賴、能力檢查、輸入輸出契約、錯誤處理及本機驗收 |
| 原碼與流程借鏡 | 遮罩處理順序、分層 UI、歷史與排隊呈現 | 理解設計後對應 Vue／FastAPI 的模組與資料模型，依需要保留來源紀錄 |
| 複製修改程式 | 邊界清楚且確實比自行實作省工的局部 | 逐檔核對授權／NOTICE／上游來源，記錄修改與測試，承擔後續維護 |
| 整套 UI／任務引擎移植 | 本輪不建議 | 同時引入另一套執行與持久化語義，未有證據顯示可節省總整合成本 |

平台已有 Vue → FastAPI → SQLite／本地檔案 → 獨立 ComfyUI 的分工，且不接受任意第三方節點圖；各專用流程需要完整模板與能力檢查。借用節點不改變此邊界，見[既有架構](architecture.md)。

保留 UUID 冪等、原引擎關聯、不可變提交快照、精確 seed、未知提交結果的查核，以及訓練資料契約。上游的「重試」按鈕或新任務語義，不能直接取代平台的未知結果處理。[架構與任務狀態](architecture.md)、[T02 資料契約](training/dataset-contract.md)。

## R01：優先評估現成 pose／depth 前處理

固定版本提供 `DWPreprocessor`（條件圖與姿勢 keypoints）及 `DepthAnythingV2Preprocessor`（相對深度圖），可接入現有獨立 ComfyUI，省去自行實作姿勢／深度估計演算法。這些是 hint 前處理，仍須另選匹配 SDXL 的 ControlNet 權重與流程；README 中的 SD1.5 範例不能直接當作 Animagine 相容證據。[DWPose 原碼](https://github.com/Fannovel16/comfyui_controlnet_aux/blob/a587a4c1594524c1d2de5cd1a86cd868ff448e1c/node_wrappers/dwpose.py)、[相對深度節點](https://github.com/Fannovel16/comfyui_controlnet_aux/blob/a587a4c1594524c1d2de5cd1a86cd868ff448e1c/node_wrappers/depth_anything_v2.py)、[功能與模型對照](https://github.com/Fannovel16/comfyui_controlnet_aux/blob/a587a4c1594524c1d2de5cd1a86cd868ff448e1c/README.md#nodes)。

整合前需固定依賴與估計器權重；其 requirements 並非完整 lock，節點會呼叫 `from_pretrained`，不能假定初次運行離線。DWPose 的 provider 探測清單甚至包含 CPU provider，因此啟動訊息不能代替實際裝置／速度量測；README 舊 CUDA 指引也不直接套入目前環境。[依賴清單](https://github.com/Fannovel16/comfyui_controlnet_aux/blob/a587a4c1594524c1d2de5cd1a86cd868ff448e1c/requirements.txt)、[provider 與模型載入](https://github.com/Fannovel16/comfyui_controlnet_aux/blob/a587a4c1594524c1d2de5cd1a86cd868ff448e1c/node_wrappers/dwpose.py#L11-L27)。

建議先選一種 pose 或 depth 完成最小串接，保存來源圖、實際條件圖、前處理參數／版本與 hash，再驗證單次提交、離線讀取、精確還原與固定品質案例；通過後擴充第二種。這是 R01 內的實作方式建議，不改變原定 R01 → R03 順序。[R01 驗收](../ROADMAP.MD#r01)。

## R03：優先評估 comfyui-inpaint-nodes

官方提供 Fooocus SDXL inpaint patch、LaMa／MAT 預填、遮罩膨脹／侵蝕／羽化、去雜值與色彩匹配；README 同時提供 simple、refine、outpaint 範例。這些與 R03 的接縫、邊界融合與遮罩外保留直接相關。[固定版 README](https://github.com/Acly/comfyui-inpaint-nodes/blob/5b7681746fe19e563113d27366ba85236bc1ba5b/README.md)、[節點原碼](https://github.com/Acly/comfyui-inpaint-nodes/blob/5b7681746fe19e563113d27366ba85236bc1ba5b/nodes.py)。

優先以外部 ComfyUI 節點組成少數受支援的專用模板，平台實作選項驗證與快照；預估整合成本中等。直接搬入 FastAPI 會連帶引入 torch、ComfyUI model patcher 與 GPU 管理，從原碼依賴看沒有必要。[依賴與模型 patch](https://github.com/Acly/comfyui-inpaint-nodes/blob/5b7681746fe19e563113d27366ba85236bc1ba5b/nodes.py#L5-L38)。

先處理以下界線，再決定採用版本：

- HEAD 使用 `comfy_api.latest.io.ComfyNode`；本機 ComfyUI 0.34.0 靜態核對已有對應 API 檔案，仍須逐節點檢查 schema、依賴、載入與完整 workflow，尚未安裝驗證。[新版節點 API](https://github.com/Acly/comfyui-inpaint-nodes/blob/5b7681746fe19e563113d27366ba85236bc1ba5b/nodes.py#L18)。
- Fooocus 需要額外 head／patch 權重；官方限制為一般 SDXL checkpoint，Turbo／Lightning／Hyper 蒸餾合併版不適用。Animagine 候選仍需實測，不能由 SDXL 名稱直接宣告通過。[使用限制](https://github.com/Acly/comfyui-inpaint-nodes/blob/5b7681746fe19e563113d27366ba85236bc1ba5b/README.md#fooocus-inpaint)。
- refine 的 `latent_inpaint` 與 `latent_samples` 接線不同；遮罩降噪強度與最終合成遮罩也有不同目的。錯接可能產生品質問題，應保存處理版本與各參數。[conditioning](https://github.com/Acly/comfyui-inpaint-nodes/blob/5b7681746fe19e563113d27366ba85236bc1ba5b/README.md#inpaint-conditioning)、[合成遮罩](https://github.com/Acly/comfyui-inpaint-nodes/blob/5b7681746fe19e563113d27366ba85236bc1ba5b/README.md#denoise-to-compositing-mask)。
- 色彩匹配節點針對整張輸出都出現色偏的情形；不能當作每次必開的品質保證。遮罩外保留與色偏仍依固定案例實測。[色彩匹配適用條件](https://github.com/Acly/comfyui-inpaint-nodes/blob/5b7681746fe19e563113d27366ba85236bc1ba5b/README.md#color-match-masked)。

驗收沿用 R03：同素材、同模型、同 seed 比較基準與候選；保存原遮罩、處理後遮罩、半徑與合成方式，記錄接縫、色偏、截斷及遮罩外改變。安裝成功或產生一張圖不能取代品質比較。[R03 原定範圍](../ROADMAP.MD)。

## Krita AI Diffusion：借用工作流程設計

官方支援選區修補、畫布即時預覽、ControlNet 姿勢／深度、參考圖、區域提示、排隊與歷史；推論後端同樣是 ComfyUI，適合查驗 R01／R03 如何組合節點。[固定版 README](https://github.com/Acly/krita-ai-diffusion/blob/828b70c33c5c97f326e03170cd693beef798231e/README.md#features)。

可讀的具體接縫是 `backend/workflow.py` 的控制條件與遮罩處理順序，以及 `comfy_workflow.py` 對節點名稱／輸入的封裝。依這些設計建立本平台專用流程，預估成本中等；直接移植整個插件成本高。[workflow](https://github.com/Acly/krita-ai-diffusion/blob/828b70c33c5c97f326e03170cd693beef798231e/ai_diffusion/backend/workflow.py#L605)、[Comfy workflow builder](https://github.com/Acly/krita-ai-diffusion/blob/828b70c33c5c97f326e03170cd693beef798231e/ai_diffusion/backend/comfy_workflow.py#L59)。

直接搬 UI／任務模型並不順接 Vue：插件依賴 Krita，任務模型使用 PyQt6 的 QObject／signal；其 Comfy client 也有自己的排隊、上傳與事件處理。[Krita 環境要求](https://github.com/Acly/krita-ai-diffusion/blob/828b70c33c5c97f326e03170cd693beef798231e/README.md#installation)、[Qt 任務模型](https://github.com/Acly/krita-ai-diffusion/blob/828b70c33c5c97f326e03170cd693beef798231e/ai_diffusion/model/jobs.py#L143)。

不能只抄節點名稱：官方資源表固定 ComfyUI 與各 custom node revision；目前插件的 inpaint-nodes pin 也不是該專案查詢當時 HEAD。這是相容組合的參考，尚不是本平台驗證結果。[資源版本表](https://github.com/Acly/krita-ai-diffusion/blob/828b70c33c5c97f326e03170cd693beef798231e/ai_diffusion/backend/resources.py#L13-L60)。

其 client 會主動提供 `prompt_id` 並檢查回傳值，錯配時要求 ComfyUI 0.3.45 以上；可借鏡相容檢查，但不能直接搬其例外處理就宣稱與本平台持久化 UUID／unknown 語義相同。[提交實作](https://github.com/Acly/krita-ai-diffusion/blob/828b70c33c5c97f326e03170cd693beef798231e/ai_diffusion/backend/comfy_client.py#L302-L325)。

## InvokeAI：以畫布、歷史與佇列的互動借鏡為主

官方提供網頁畫布、inpaint／outpaint、節點工作流程、作品 board／gallery、模型管理與設定回取。適合作為使用流程比較對象，不能由功能清單推定本平台應全部補齊。[固定版 README](https://github.com/invoke-ai/InvokeAI/blob/cbc5ab0595d17e81289108b77229cd3886af7669/README.md#features)。

原碼同時包含 webv1、webv2；本次主要看 webv2。其 React／TanStack 前端與 Vue 不同，後端雖同用 FastAPI，queue API 仍連到 Invoke 自身 invoker、session 與資料庫服務，整包移植成本高。[webv2 dependencies](https://github.com/invoke-ai/InvokeAI/blob/cbc5ab0595d17e81289108b77229cd3886af7669/invokeai/frontend/webv2/package.json#L51-L74)、[queue API](https://github.com/invoke-ai/InvokeAI/blob/cbc5ab0595d17e81289108b77229cd3886af7669/invokeai/app/api/routers/session_queue.py#L261-L281)。

可借鏡的具體設計包括：

- 活躍任務與已保存作品分開呈現、進度預覽不納入作品計數；有助於出現預覽／作品混淆的實際問題時比較。[queue 設計](https://github.com/invoke-ai/InvokeAI/blob/cbc5ab0595d17e81289108b77229cd3886af7669/invokeai/frontend/webv2/src/features/queue/README.md)。
- 從任務快照讀提示與尺寸，保留事件順序欄位；可作歷史回取或舊事件覆寫問題的檢查案例。[history snapshot](https://github.com/invoke-ai/InvokeAI/blob/cbc5ab0595d17e81289108b77229cd3886af7669/invokeai/frontend/webv2/src/features/queue/core/historySnapshot.ts)、[事件契約](https://github.com/invoke-ai/InvokeAI/blob/cbc5ab0595d17e81289108b77229cd3886af7669/invokeai/frontend/webv2/src/features/queue/data/events.ts#L30-L42)。
- 將預填、生成、遮罩合成分成明確步驟；實作借鏡前先核對白色代表保留或重繪，其畫布契約不能直接套用到本平台遮罩。[canvas graph](https://github.com/invoke-ai/InvokeAI/blob/cbc5ab0595d17e81289108b77229cd3886af7669/invokeai/frontend/webv2/src/features/generation/core/canvas/compileCanvasGraph.ts#L421-L504)。

以上是可對照的設計，不是本輪已證實的平台缺陷。已完成的 UI、歷史、作品庫、取消／停止流程先保留；只有具體問題、可重現案例與改善目標成立，才安排局部修改。

## 訓練、授權與完成判定

前述畫布／ControlNet／修補整合主要服務推論，不能替代 T03 的訓練環境／GPU 協調或 T04 的產物回登／品質比較。T02 已對 sd-scripts 固定版本研究，不必再搬一套推論平台作為 trainer。[訓練工具介面研究](training/tool-interface-research.md)、[訓練需求](training/requirements.md)。

採納程式碼前須逐項記錄來源、固定 commit、檔案授權、修改與適用 NOTICE；此處只整理 LICENSE 事實，不作整合方案的法律結論。程式碼授權不能自動涵蓋權重、訓練圖片、模型輸出或第三方依賴，權重應另核對來源與條件。

先借用缺少的能力，平台繼續掌握提交、版本、資料與驗收。硬體限制、未備妥的實機觸控、圖片來源用途與人工品質判讀，仍需各自解決，不能因採用既有專案便標記通過。

## 後續開發採用方式

每個新功能先查 2–3 個貼近現有架構的候選，先讀原碼與限制，再選外部依賴、局部複用或介面借鏡。以「選型＋適配＋驗收＋未來維護」評估總成本；功能清單、星數與截圖只能當線索，不能代替成本或品質證據。

未完成的 R01／R03 先用這個方式減少底層重造；T03／T04 仍另排並沿用 T02 契約。已完成項目只在具體痛點、缺陷或可量測改善成立時開局部改動，保留原工作流程與歷史資料格式；避免為外觀接近其他平台而全面改寫。每項實作仍依使用者約定，驗收、commit、push 後才進下一項。
