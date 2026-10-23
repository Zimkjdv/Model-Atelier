# 動漫相關上游候選：原碼與流程查核

查核日期：2026-10-23。以 GitHub 官方 API、固定 commit 的 README 與原碼為依據；本輪沒有安裝、下載權重或執行上游。成熟度依可讀原碼、操作文件、測試／版本歷史及維護活動判斷，不用星數代替相容性驗證。下列「建議」是本平台整合判斷，尚未代表本機驗收通過。

## 候選與固定來源

| 候選／類型 | 固定 commit | 維護與成熟證據 | 原碼授權觀察 |
| --- | --- | --- | --- |
| [Regional Prompter](https://github.com/hako-mikan/sd-webui-regional-prompter)／通用、動漫構圖適用 | `b10c496dbcb9c94be0d5d64edda8511460cc9d28` | 未封存；API 最近 push 2026-09-04；README 有 Attention／Latent、區域 LoRA、WebUI／Forge 相容矩陣及限制 | GitHub API 標示 AGPL-3.0；直接移植前核對固定版本與逐檔來源 |
| [ADetailer](https://github.com/Bing-su/adetailer)／通用、包含 2D 偵測模型 | `3a599f5d4607d8f9d8b9fc5a15526197418dae1a` | 未封存；最近 push 2026-10-19；包含 tests 與 CI，README 提供遮罩處理順序、模型表及限制 | AGPL-3.0；README 說明 WebUI／Ultralytics 衍生關係，權重另核對 |
| [Anime Segmentation](https://github.com/skytnt/anime-segmentation)／動漫專用 | `55d874013a2811cdf59c365059174c7823acf5b4` | 未封存；最近 push 2025-05-21；有訓練、推論、ONNX 匯出及公開示範；維護頻率較低，不等同現代環境已通過 | Apache-2.0；支援網路與下載權重／資料集來源仍分開核對 |
| [sd-scripts](https://github.com/kohya-ss/sd-scripts)／通用、動漫 LoRA 適用 | `11d8cedd0c67b93a10f8b2d75f43554f6f12c794` | 未封存；最近 push 2026-10-20；README 0.12.2、詳細變更紀錄、CI／回歸與 SDXL 資料介面 | Apache-2.0；模型、訓練素材與依賴授權獨立 |
| [WD14 Tagger WebUI](https://github.com/picobyte/stable-diffusion-webui-wd14-tagger)／動漫 booru 標籤適用 | `e72d984bdbed832ba83e2a443238c3851b9088ae` | 未封存；最近 push 2024-05-14；有批次標註、模型比較、pylint workflow；維護較舊，列次選參考 | API 無統一 SPDX；README 寫 public domain，但明確排除 borrowed parts，不能把整庫當公有領域 |

API 查核入口：[Regional Prompter](https://api.github.com/repos/hako-mikan/sd-webui-regional-prompter)、[ADetailer](https://api.github.com/repos/Bing-su/adetailer)、[Anime Segmentation](https://api.github.com/repos/skytnt/anime-segmentation)、[sd-scripts](https://api.github.com/repos/kohya-ss/sd-scripts)、[WD14 Tagger](https://api.github.com/repos/picobyte/stable-diffusion-webui-wd14-tagger)。push 日期是整個倉庫活動訊號，不代表特定功能的最後修正日。`skytnt/anime-seg` GitHub 路徑返回 404；正確原碼倉庫為 `anime-segmentation`，`anime-seg` 是其 README 指向的 Hugging Face 權重名稱。

## 可節省時間的整合方式

### R03：先借鑑自動遮罩與局部修補流程

ADetailer 的流程是生成 → 偵測 → 遮罩 → 修補；[固定 README](https://github.com/Bing-su/adetailer/blob/3a599f5d4607d8f9d8b9fc5a15526197418dae1a/README.md) 說明 confidence、面積篩選、位移、膨脹／侵蝕、合併／反轉及個別修補提示。[mask.py](https://github.com/Bing-su/adetailer/blob/3a599f5d4607d8f9d8b9fc5a15526197418dae1a/adetailer/mask.py) 提供具體處理順序，tests/test_mask.py 是邊界測試參考。

建議本平台先沿用既有遮罩資產與 Comfy 工作流程，增加可預覽、可手動修正的偵測遮罩候選，再比較羽化、接縫與遮罩外保留。ADetailer 是 A1111 擴充；README 明說開發測試以 SD1.5／A1111 為主，不能據此宣稱本平台 SDXL 相容。自動修臉可能改掉棕髮綠眼角色特徵，應保留開關、原圖和前後比較。模型表中的 2D 能力也不代表我們的畫風已通過。

動漫專用的 Anime Segmentation 適合「角色前景選區」輔助。[inference.py](https://github.com/skytnt/anime-segmentation/blob/55d874013a2811cdf59c365059174c7823acf5b4/inference.py) 的 get_mask 保持長寬比縮放、補邊、移除補邊後還原原尺寸，能作為座標一致性參考；它輸出前景遮罩，不能取代姿勢骨架、深度或角色身分辨識。README 命令寫 `--data-dir`，該固定原碼 parser 實際為 `--data`，採用時以原碼核對。建議隔離推論或另驗證 ONNX 執行，測試頭髮、透明配件、多人與背景相近色；不直接把訓練依賴加進平台環境。

### R01／R02／L01／R05：區域提示可借鏡，不能直接取代已完成流程

[Regional Prompter README](https://github.com/hako-mikan/sd-webui-regional-prompter/blob/b10c496dbcb9c94be0d5d64edda8511460cc9d28/README.md) 有區域比例、共用／基底提示、區域 LoRA 與可視化範本，可作為多人髮色串色、衣著與背景分離的後續試驗基礎。[attention.py](https://github.com/hako-mikan/sd-webui-regional-prompter/blob/b10c496dbcb9c94be0d5d64edda8511460cc9d28/scripts/attention.py) 直接依賴 WebUI modules／Forge 探測與 attention hook，不能複製進 FastAPI 或當 Comfy 節點使用。

建議先用 Comfy 原生區域 conditioning 做最小比較；只有可量測改善且現有節點不足，才評估額外節點或獨立實作。它不提供 R01 所需的姿勢／深度前處理，也不替代 R02 IP-Adapter 或 T04 身分驗收。L01 多 LoRA 與 R05 提示基準可增加區域開關的有限對照，但舊證據保持不變；區域 Latent 模式可能增加生成時間，須量測而非假定加速。

### T01–T04：沿用 sd-scripts 邊界，標籤只作人工審查草稿

sd-scripts 已是 T02 固定候選，詳見 [既有介面研究](training/tool-interface-research.md)。T03 採獨立環境與受控工作入口，平台負責資料版本、GPU 工作協調、取消與失敗狀態；T04 負責 LoRA 產物 hash、回登與固定比較。上游已解決訓練演算法與資料讀取，可省去自製 trainer，但不包含本平台的工作持久化與權重回登驗收。新增模型支援或記憶體優化不應直接套用到 SDXL，須逐項核對適用架構。

[WD14 README](https://github.com/picobyte/stable-diffusion-webui-wd14-tagger/blob/e72d984bdbed832ba83e2a443238c3851b9088ae/README.md) 提供單張／批次 booru 標籤；[interrogator.py](https://github.com/picobyte/stable-diffusion-webui-wd14-tagger/blob/e72d984bdbed832ba83e2a443238c3851b9088ae/tagger/interrogator.py) 依賴 WebUI 全域設定、ONNX providers 與 Hugging Face 下載。建議只參考標籤篩選／人工修訂流程，優先評估 sd-scripts 已有標註工具以減少另一組依賴。下載來源與版本須顯式固定，不能默默首次連網下載。自動輸出只能填入待審 caption 草稿，不能自動標記 approved、確認角色身分或來源用途；保持 T02 單行 caption、原作分組、保留集及曝光紀錄。

## 建議採用次序與驗收界線

1. 維持 R01 → R03；本份候選中，R03 的遮罩流程最能直接借鑑。R01 應使用另行研究的 Comfy 原生前處理與匹配 SDXL 控制模型。
2. R03 通過基本專用修補後，再小範圍比較動漫前景選區；不把新增去背功能擴張成 R03 完成的先決條件。
3. T03／T04 依既定排程使用 sd-scripts；標註輔助先改善人工審查耗時，不跳過使用者來源與角色審查。
4. Regional Prompter 列 R02／L01／R05 後續品質改善參考，先有具體串色問題與比較資料再新增區域 UI。

每次整合至少保存固定上游版本、採用的功能／檔案來源、依賴與權重版本、輸入／前處理／遮罩座標、實測限制。直接採用原碼前逐檔核對授權並保留通知；流程借鑑與原碼移植分開記錄。五個候選的本機相容性、VRAM、畫風效果、恢復／還原行為均尚未驗證，研究完成不關閉任何 ROADMAP 實作驗收框。
