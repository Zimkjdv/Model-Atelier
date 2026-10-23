# 全部 ROADMAP 項目的上游參考地圖（2026-10-23）

本次涵蓋 ROADMAP 全部 47 個主項：26 項完成、21 項未完成。下表「完成」沿用 ROADMAP 勾選，不能把研究結果當成實機驗收。建議保持 R01 → R03 的開發順序；T03／T04 另排。成熟度是「已有可閱讀的完整產品／模組實作」，不是承諾本機相容或動漫品質。

## 平台候選與固定來源

以下讀取官方 GitHub README、LICENSE 及列出的原碼；未安裝、執行、移植。版本是研究錨點，不要求把現有 ComfyUI 升至 HEAD。

| 代號／候選 | 固定 SHA、README、授權 | 實際參考位置與適配判斷 |
| --- | --- | --- |
| K：Krita AI Diffusion | `828b70c33c5c97f326e03170cd693beef798231e`；[README](https://github.com/Acly/krita-ai-diffusion/blob/828b70c33c5c97f326e03170cd693beef798231e/README.md)、[GPL v3](https://github.com/Acly/krita-ai-diffusion/blob/828b70c33c5c97f326e03170cd693beef798231e/LICENSE) | [backend/workflow.py](https://github.com/Acly/krita-ai-diffusion/blob/828b70c33c5c97f326e03170cd693beef798231e/ai_diffusion/backend/workflow.py)：依模型架構、選區、ControlNet、LoRA 組圖；README 明列 Illustrious、line art、pose、depth、IP-Adapter，四者中最貼近動漫繪畫操作。Qt／Krita 元件不直接移入 Vue。 |
| I：InvokeAI | `cbc5ab0595d17e81289108b77229cd3886af7669`；[README](https://github.com/invoke-ai/InvokeAI/blob/cbc5ab0595d17e81289108b77229cd3886af7669/README.md)、[Apache-2.0](https://github.com/invoke-ai/InvokeAI/blob/cbc5ab0595d17e81289108b77229cd3886af7669/LICENSE) | [session_queue_default.py](https://github.com/invoke-ai/InvokeAI/blob/cbc5ab0595d17e81289108b77229cd3886af7669/invokeai/app/services/session_queue/session_queue_default.py)：佇列、摘要、冪等衝突與資料庫責任切分。README 的 Canvas、Board/Gallery、metadata recall 可供 UI 評估；React UI 與獨立推論核心不適合整套替換。 |
| S：SwarmUI | `d74f8ce40d1e49161da61ddb74f87e6ebf11f7ad`；[README](https://github.com/mcmonkeyprojects/SwarmUI/blob/d74f8ce40d1e49161da61ddb74f87e6ebf11f7ad/README.md)、[MIT](https://github.com/mcmonkeyprojects/SwarmUI/blob/d74f8ce40d1e49161da61ddb74f87e6ebf11f7ad/LICENSE.txt) | [WorkflowGenerator.cs](https://github.com/mcmonkeyprojects/SwarmUI/blob/d74f8ce40d1e49161da61ddb74f87e6ebf11f7ad/src/BuiltinExtensions/ComfyUIBackend/WorkflowGenerator.cs)：表單轉 Comfy 圖、能力集合、分步組裝；可借鏡模型能力呈現及 grid 操作。官方自稱 v0.9.8 Beta／Almost-Release，不能描述為已穩定正式版；C#/.NET 實作不直接移植。 |
| C：ComfyUI | `bc5f880dbdd43e426077f42ccec53bb577ffee9f`；[README](https://github.com/Comfy-Org/ComfyUI/blob/bc5f880dbdd43e426077f42ccec53bb577ffee9f/README.md)、[GPL v3](https://github.com/Comfy-Org/ComfyUI/blob/bc5f880dbdd43e426077f42ccec53bb577ffee9f/LICENSE) | [model_management.py](https://github.com/Comfy-Org/ComfyUI/blob/bc5f880dbdd43e426077f42ccec53bb577ffee9f/comfy/model_management.py)：VRAM／裝置／offload 實作。保留獨立引擎；官方支援表可作能力調查入口，不能取代本機權重、節點及工作流驗證。 |

K／I 的固定版本沿用[初評](github-reuse-assessment-20261023.md)，本輪重新讀取固定版 README、授權與上述原碼。S／C 的 SHA 本輪由官方 commit API 取得：[SwarmUI](https://api.github.com/repos/mcmonkeyprojects/SwarmUI/commits/d74f8ce40d1e49161da61ddb74f87e6ebf11f7ad)、[ComfyUI](https://api.github.com/repos/Comfy-Org/ComfyUI/commits/bc5f880dbdd43e426077f42ccec53bb577ffee9f)。其他節點、trainer 的固定來源見初評與 [T02 工具介面](training/tool-interface-research.md)。

## 逐項映射

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
| Q10 維護規則 | 完成 | 無需上游替換 | 持續遵守 maintenance.md 的格式／狀態／功能分開提交。 |
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
| R03 inpainting | 未完成 | 優先 Acly inpaint 節點＋K 選區流程 | 見初評；小遮罩、接縫、遮罩外保留、動漫線條品質必測。 |
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

## 可立即落實的開發方法

1. 每次開發讀本表對應項及固定版來源，先寫最小輸入／輸出契約，再決定節點整合或局部移植；不因上游有功能就增加範圍。
2. 首先 R01 的一種前處理，再 R03 的一種修補模板。保留 Vue → FastAPI → SQLite／本地檔案 → 獨立 ComfyUI，不搬入另一個平台的推論核心。
3. 實作記錄上游 repo／SHA／檔案／授權、改動、依賴及測試。來源碼授權和模型權重條款分開核對；若直接移植，保留相應著作權／NOTICE 並評估散布義務。
4. 保留 UUID 冪等、原引擎、不可變快照及 64-bit seed 字串。具體差異：K 的 generate_seed 原碼因 Qt 限制只產生 32-bit seed，不能直接套用本平台已支援的大整數契約。
5. 完成項目的優化需附具體缺陷或量測證據及回歸；硬體、觸控、權重來源和品質驗收都不能以找到上游原碼取代。

相關本地依據：[架構](architecture.md)、[維護規則](maintenance.md)、[ROADMAP](../ROADMAP.MD)。以上沒有改變任何勾選狀態，也沒有下載模型或執行第三方程式。
