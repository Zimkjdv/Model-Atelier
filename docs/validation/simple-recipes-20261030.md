# 簡易創作十五份配方與畫風任務驗收

日期：2026-10-30（Asia/Taipei；JSON 保存原 UTC 時間）。

本次交付每個模型新增四份、合計十五份模型配方，以及兩個可直接操作的畫風任務。原三份模板及歷史證據未覆寫；新增登錄檔分別為 [模型配方](../../models/simple-creation-extra-templates-v1.json)、[畫風任務](../../models/simple-style-templates-v1.json)、[真實成果索引](../../models/simple-creation-extra-examples-v1.json)。

## 操作與資料範圍

簡易創作先選三個模型之一，再選模型內五份配方，另有 LoRA／圖片畫風任務。載入不生成，原描述唯讀，修改需明確編輯；生成、預覽、保存及原請求恢復沿用現有服務。

- LoRA：Animagine 4.0 Opt＋固定原生鍵名像素 LoRA，MODEL 1／CLIP 1，保留 `pixel art`。不混搭其他 LoRA 或圖片流程；其他強度留在進階工作台。
- 圖片畫風：Animagine＋SDXL Plus ViT-H＋CLIP Vision ViT-H，單張、style、fit、起始 0／結束 1。可選已存素材、上傳或使用自產示範圖；參考程度 0–1／步距 0.1，只有 0／0.6 有固定對照。換參考圖是新的任務輸入，不能宣稱重現示範品質。
- 來源：一般／FLUX／參考 API 接受十七個固定 v1 模板 ID。後端以實際參數及元件快照計算修改，保存不可變 `template_context`。同 UUID 更換或移除模板拒絕，恢復不重讀新配方。
- 參考任務可帶到 ReferenceStudio，完整保留來源圖、設定及模板；任務／作品可還原再生成。仍無一般草稿、JSON 交換、LoRA、多圖或身份鎖定的新增支援。

## 真實 GPU 生成

RTX 3060 12GB、ComfyUI 0.34.0、PyTorch 2.14.0+cu130。新增十二個模型配方與兩個畫風任務共十四個唯一 UUID，各提交一次、完成並保存一件作品；沒有以 fixture 取代成果。使用獨立 `runtime/simple-recipes-20261030/data`／`simple-style-20261030/data`，沒有寫入正式 DATA。

Animagine 1024²／28 steps／CFG 5／Euler Ancestral／normal；Pony 768²／20 steps／CFG 5.5／DPM++ 2M／Karras；Schnell 固定四元件、512²／4 steps／CFG 1／Euler／simple、FP8 e4m3fn／CPU 編碼器。新增模型 Seed 為字串 `9007199254740994`–`9007199254740997`；畫風任務沿用固定 `9007199254740993`。

每組四個模型配方前完整讀取權重核對 SHA256，逐次提交前再核對大小及檔案時間未變；兩個畫風任務各於提交前完整核對相關權重。公開 JSON 保存實際核對範圍，不宣稱每張都重新計算大檔 SHA256。原始 PNG bytes 未修改，大小、尺寸與雜湊可由後端測試核對。

| 模型／任務 | 新增配方及實測紀錄 | 有限原圖觀察 |
| --- | --- | --- |
| Animagine | [咖啡館](../guide/examples/animagine-cafe-v1.json)、[森林旅人](../guide/examples/animagine-adventurer-v1.json)、[和服賞櫻](../guide/examples/animagine-kimono-v1.json)、[書房青年](../guide/examples/animagine-library-v1.json) | 衣著、場景與光線可見；部分髮長、視角及裁切偏離提示，手腳未完整入鏡 |
| Pony | [動漫旅人](../guide/examples/pony-traveler-v1.json)、[黃昏車站](../guide/examples/pony-station-v1.json)、[窗邊貓咪](../guide/examples/pony-cat-v1.json)、[雨夜街景](../guide/examples/pony-city-v1.json) | 車站偏鐵路橋、貓未精確位於窗台、雨巷仍有人與擬文字；旅人背側面未驗臉部 |
| Schnell | [魔法工坊](../guide/examples/flux-workshop-v1.json)、[浮空島嶼](../guide/examples/flux-island-v1.json)、[日系旅人](../guide/examples/flux-traveler-v1.json)、[圓形機器人](../guide/examples/flux-robot-v1.json) | 工坊有擬文字、樹木數量有偏差、旅人背景有人、澆水壺與花盆融合 |
| 像素 LoRA | [新任務原圖與來源](../guide/examples/style-lora-v1.json)；[歷史無 LoRA](../guide/examples/lora-baseline-v1.json)／[歷史有 LoRA](../guide/examples/lora-style-v1.json) | 像素色塊、眼鏡、紅圍巾可見；書本裁切、手部未完整驗證；歷史對照不是本輪新生成 |
| 圖片畫風 | [新任務原圖與來源](../guide/examples/style-reference-v1.json)；[權重 0](../guide/examples/reference-zero-v1.json)／[權重 0.6](../guide/examples/reference-style-v1.json) | 自產參考帶入藍色髮束與葉片，並非只轉移線條；兩組既有對照保留原資料 |

觀察由開發助手檢視原圖記錄，不是使用者品質簽核。圖片為自編提示詞／自產參考，沒有指定作者或角色原圖；不認列作者相似度、角色身份、完整手部骨架、多 Seed 泛化或所有硬體配置通過。固定 Seed 也不保證跨環境像素一致。

## 程式與介面驗證

50 項相關後端測試通過：`backend.test_simple_examples`、`backend.test_template_context`、`backend.test_adapter_workflows`、`backend.test_submissions`、`backend.test_settings_transfer`、`backend.test_model_profiles`。涵蓋全部新增配方的完整 workflow／Seed／PNG 雜湊、原三份 digest 不變、LoRA／元件要求、參考 API 來源、UUID 一致性、作品保存及還原。

前端 `npm test`、型別與正式建置（本機使用 `--configLoader runner`）、格式及靜態檢查通過。保留既有 Vite bundle 超過 500 kB 提示，沒有據此宣稱產品全套回歸通過。

產品瀏覽器共 33 個不同案例最終通過，其中本輪新增 10 個：各模型五份選項、十二份精確配方／下載、LoRA／參考任務的生成／保存／修改、缺項分類、圖片上傳、丟失回應後跨模式原 UUID 恢復，以及取消轉交。1440／390px 的新增任務無整頁橫溢，整個 app shell 的所選 axe WCAG 2A／2AA 自動規則無違規；不等於完整讀屏或實機觸控認證。

最初整合為 30／33；一個群組查詢將新增五配方誤算入三模型入口，另外兩個舊參考測試仍直接點擊已隱藏的技術區。已依實際「來源與流程資訊」「任務與歷史資訊」與目前工作流程按鈕調整測試，保留原有資料／恢復檢查；三個失敗案例修正後全數通過。新範例測試最初也曾因 fixture 先登記風格 LoRA 再被 FLUX 初始化覆蓋而失敗；調整測試準備順序後通過，未放寬正式匹配規則。

四尺寸（1280／1440／1920／390px）離線導覽案例全部通過，涵蓋 37 個圖片參照、十二份新增完整配方、原三份成果及畫風對照、章節跳轉、原圖放大／Escape／焦點還原、列印前展開及結束還原，無整頁橫溢、遠端請求或頁面例外。兩張 UI 截圖已原圖檢視；它們使用獨立 fixture，成果圖片另有真實 GPU 紀錄，兩者不混稱。

最終證據合併 `runtime/quality/simple-recipes-delivery-*`（30 個通過案例及原失敗）、`simple-recipes-followup-*`（四個導覽通過案例）、`simple-recipes-repair-*`（三個修正案例及重新拍攝 1440px 導覽截圖）。沒有為湊單一報告而重跑所有已通過案例，也沒有宣稱全站回歸通過。

## 真人觀察

已提供使用真實引擎、獨立 DATA 的本機驗收入口，邀請使用者完成「選配方→生成→保存→修改再生成」，記錄完成與否、是否展開技術設定、卡住位置與求助次數。尚未收到觀察回報，方案 11.1 的真人驗收保留未勾選；自動操作結果不能代填。

任意中文翻譯、更多比例與未知流程組合屬原方案的後續選項，未在本次任務暗中啟用服務或擴大相容承諾。
