# 固定插畫測試集的單案例實機驗收

R05 另提供動漫集 `experiments/anime-illustration-v1.json`，不改寫通用集及其歷史 hash。可在 UI 選擇，或執行下方單組指令；模型選擇同通用集，案例為 `anime-portrait`、`anime-full-body`、`anime-station`，seed 僅接受兩個明確字串值。`common` 使用原案例文字；`quality-tags` 只在正向提示詞加入模型對應品質標籤，反向提示詞與其他參數完全保留，並非完整作者最佳設定，也沒有指定畫師標籤。

```powershell
.\.venv\Scripts\python.exe -m scripts.verify_anime_suite --model animagine-xl-4.0-opt --case anime-portrait --seed 18446744073709551615 --prompt-format quality-tags --platform http://127.0.0.1:8001 --expected-engine http://127.0.0.1:8188 --report runtime/anime-portrait-new.json
.\.venv\Scripts\python.exe -m scripts.verify_anime_suite --model animagine-xl-4.0-opt --case anime-portrait --seed 18446744073709551615 --prompt-format quality-tags --platform http://127.0.0.1:8001 --expected-engine http://127.0.0.1:8188 --report runtime/anime-portrait-new.json --verify-report
```

一指令一個 UUID、獨占新報告、完整權重驗檔、原圖與原設定核對、失去回應只查原 UUID 及 `--verify-report` 僅 GET 的規則與通用工具相同。這個入口不自行建立批次；本輪有限矩陣及人工原圖觀察另記驗收文件。指定作者畫風與角色身份結論需要使用者目標圖；依[圖片提醒](anime-style-development.md#image-input-reminders)補資料後另驗，不由標籤或成功出圖推論。

一般插畫測試集 v1 可從創作頁的比較方案選取，也可用 `scripts.verify_illustration_suite` 對已安裝、固定來源的 Pony V6 XL／Animagine XL 4.0 Opt 執行一次單案例 GPU 驗收。

```powershell
.\.venv\Scripts\python.exe -m scripts.verify_illustration_suite --model animagine-xl-4.0-opt --case lake --platform http://127.0.0.1:8001 --report runtime/suite-animagine-lake-new.json
.\.venv\Scripts\python.exe -m scripts.verify_illustration_suite --model animagine-xl-4.0-opt --case lake --platform http://127.0.0.1:8001 --report runtime/suite-animagine-lake-new.json --verify-report
```

`--model` 僅接受 `pony-v6-xl`、`animagine-xl-4.0-opt`；`--case` 僅接受 `chair`、`lake`、`traveler-bookshop`、`traveler-station`。先啟動平台與 ComfyUI，登記固定來源模型後才可生成。`8001` 範例是開發驗收的隔離平台，不是日常必需服務；使用正式 `8000` 會建立正式任務／作品，請明確選擇目的平台。

所有案例使用相同 1024×1024、28 steps、CFG 5、euler_ancestral／normal、denoise 1、seed `9007199254740993`、無 LoRA／參考圖；模型之間只換 checkpoint，案例之間只換固定正提示詞與標題。不是每個模型的作者最佳提示格式或品質預設，也不能當作全面模型排名。

每次 invocation 只提交一個新 UUID。報告路徑必須位於本專案 `runtime/` 且不存在；先獨占保留報告，再驗證本機權重 SHA256／大小、登記版本／架構、原引擎 CUDA 及節點能力。測試集版本、bytes hash、完整案例及條件寫入報告；提交前測試集改變會拒絕。失去回應只查詢原 UUID，任何失敗都保留原 ID，不自動重送。

成功後匯入單張圖片，核對 PNG、大小、完整 workflow、精確 seed、設定還原、原模型／環境及量測快照。`--verify-report` 只做既有記錄 GET，不驗本機權重、不同步、匯入或生成；報告的模型／案例／測試集 hash 不符時拒絕驗證。品質不是 CLI 的自動通過條件，仍需查看原圖及案例要點。

2026-10-08 已完成兩個模型 × 四個案例的 RTX 3060 GPU 實測、原圖觀察及引擎停止後保存核對，見 [結果與限制](validation/general-illustration-suite-rtx3060.md)。此批資料位於 `runtime/roadmap-live-data-20261008`，不混入正式作品庫。作品筆記登記案例及開發助手的視覺觀察，分數保持未評分；可使用既有作品並排與人工評分功能自行比較。這批歷史任務早於[保存方案的結果關聯](experiment-runs.md)，不依相同提示詞回填關聯；目前可另行保存新方案並明確逐組生成。沒有自動批次或自動品質評分。更多 seed、模型、參考引導及 RTX 4080 仍待實測。

2026-10-23 · V04：補齊 1440px／390px 的四案例跨模型原圖並排及原設定載入，另逐組驗證固定案例預覽；沒有新增 GPU 任務，詳見 [V04 驗收](validation/comparison-measurements-20261023.md)。
