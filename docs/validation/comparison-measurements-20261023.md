# V04 · 比較與量測介面補驗

日期：2026-10-23。對應 [ROADMAP V04](../../ROADMAP.MD#v04) 四個子項，分別核對歷史品質條件、指定 LoRA 強度軸、固定四案例結果與設定載入、任務及作品量測。

## 環境與兩種證據

Windows、Python 3.12、Node.js 24、鎖定的 Playwright 1.64.1 Chromium。每種操作都在 1440 × 900 與 390 × 900 實際 viewport 執行，頁面 `innerWidth` 另有斷言。

1. **可重跑的八項瀏覽器回歸**：`frontend/tests/comparison-validation.spec.ts` 使用臨時 DATA、真實 FastAPI／SQLite 與隔離 PNG。`scripts/comparison_fixture.py` 以固定 manifest 雜湊登記模型，讓真實 registry 比對；這只是模擬登記，不驗當前權重。量測案例為人工建立的 7／2.5 秒、零秒及舊紀錄。每案核對生成數不變，沒有引擎推論。
2. **既有 GPU 紀錄的離線 UI 核對**：只讀 `runtime/roadmap-live-data-20261008` 與原報告，核對兩件 8 步 LoRA、八件固定案例與一件量測作品，共 11 件。指定資料及圖片複製到新的臨時 DATA；獨立服務拒絕生成及資料寫入，所有引擎 HTTP 由 MockTransport 攔截為離線。兩種寬度共完成八次跨模型並排與 22 次原設定載入，沒有重新生成或回填歷史關聯。

第二種證據保留實際 GPU 原圖與原量測，不能以第一種的合成圖片替代。兩者均沒有操作正式作品庫。

## V04-01 · 8 步正反多 LoRA 品質紀錄

從目前創作設定操作順序、steps 及 CLIP 強度，真實查詢 `/api/loras/stack-validation`，核對以下紀錄：

| 紀錄 ID | 順序／強度 | 條件與時間 |
| --- | --- | --- |
| `animagine-multi-8-rtx3060-20261008` | LCM model 1／CLIP 0 → IKEA model 1／CLIP 1 | 8 steps、CFG 1、lcm／sgm_uniform、1024²；平台 29.734 秒、引擎 27.597 秒，首輪包含冷載入及初始化 |
| `animagine-style-lcm-8-rtx3060-20261008` | IKEA model 1／CLIP 1 → LCM model 1／CLIP 0 | 相同取樣條件；平台 13.907 秒、引擎 13.422 秒，同引擎部分節點快取及 patch 重建 |

正向另有較早 4 步紀錄；本次明確展開 **2026-10-08／8 steps**，未用 2026-10-05 的桌面匹配代替。改為 9 步或修改 CLIP 強度後，畫面顯示參數未匹配；反向只對應自己的紀錄 ID 與順序。

確認畫面保留對比不足、未改善至推薦品質、decoded RGB 雜湊不同、不能推定所有順序等效，以及整卡取樣非最低需求等限制。亦查看兩張原圖，仍呈淡線條；沒有把查詢成功、8 步或不同耗時當成品質改善／速度排名。原品質定義見 [原始觀察](animagine-multi-lora-quality-rtx3060.md)。

## V04-02 · 指定 LoRA model／CLIP 強度軸

兩種寬度皆操作 `lora_strength_model` 與 `lora_strength_clip`，指定第三個已啟用 LoRA，值為 `[-1, 0, 0.5]`。逐組完整設定與基準比對：只改指定強度及展示標題，其他 LoRA 強度、原有順序、第二個停用項目、負提示詞及 seed `18446744073709551615` 保留。

實際載入 model 0、CLIP -1 組別到創作表單，逐欄核對後按保存草稿，核對保存 API 的完整設定。原草稿沒有被覆寫，載入／保存都不提交生成。缺少目標、正規化後重複值、21 超界、數字字串及目標被停用時，預覽回傳 422，畫面顯示錯誤並保留原表單／精確 seed；不改選其他 LoRA 或偷偷截斷值。

## V04-03 · 固定四案例跨模型結果與設定載入

測試集 `general-illustration` v1、bytes SHA256 `3adada6b8ce0aa69313ee0604dc280e96a6db6616b5e892d6b4f3f5feefe6ff7`，四案為 chair、lake、traveler-bookshop、traveler-station。

可重跑測試在 Pony V6 XL 與 Animagine 4.0 Opt 分別預覽四組，逐組載入正提示詞；完整比較確認只替換案例提示詞、標題與指定 seed 軸，checkpoint、負提示詞、28 steps、CFG 5、1024²、euler_ancestral／normal 及其餘設定保留。四案例乘三值超過八組時整體拒絕，沒有部分方案或任務。

離線副本另將 **原八件 GPU 作品**按相同案例跨模型並排，核對 1024² 原圖 API、PNG SHA256、原筆記與未評分狀態，再各自載入作品的原案例設定；這不是兩個 denoise 方案或新合成圖的結果驗收。八次並排涵蓋兩種寬度；390px 實際水平捲動查看第二欄。保留 [原始四案例品質限制](general-illustration-suite-rtx3060.md)：椅子說明、單船／無人構圖及人物細節仍有偏差，未接入角色鎖定，也沒有自動分數或模型排名。歷史任務早於保存方案關聯，不依相同提示詞回填 plan／variant。

## V04-04 · 任務與作品量測

分別展開工作台的任務詳情與作品預覽「任務耗時與資源來源」，確認：

- 平台提交至首次終態觀察、原引擎歷史起訖各有標籤及定義，不相減推算佇列時間，也不稱為純 GPU 耗時。
- 原引擎 URL、`/system_stats` 來源與提交前時間保留；隔離回歸的原來源故意不同於目前平台引擎，不能用目前主機代替。
- GPU 顯存與 CPU 記憶體標籤不同；RAM／裝置已用及可用容量、零可用容量如實顯示。零秒為 `0.000 秒`，缺資料保持未知。
- 舊紀錄沒有量測時明示未知；讀取後原任務 JSON 不變，作品量測等於原任務，任務專用 VRAM 峰值仍未知。

實際舊量測作品 `f205d822-8bcd-597c-ae6b-6b78971c6ade` 在 UI 顯示平台 **27.311 秒**、引擎 **26.029 秒**、原 `http://127.0.0.1:8188/system_stats` 及 RTX 3060 提交前資源。兩件 8 步作品早於量測欄位，保持未知；沒有從版本／效能條件快照推估新值。原定義見 [量測說明](../job-measurements.md)。

## 重跑、附件與資料不變

```powershell
.\.venv\Scripts\python.exe scripts/check_quality.py
# 單獨執行 V04；先完成前端建置
Set-Location frontend
npm.cmd run build
npm.cmd run test:browser -- comparison-validation.spec.ts
```

每案 45 秒、單 worker、零重試。`/qa/comparison-context` 只存在臨時測試服務；完成後還原原模型／LoRA 登記並移除本組合成任務／作品紀錄，避免污染後續導覽測試。首次全量執行發現的測試登記污染保留於 `runtime/v04-quality-before.log`、`runtime/v04-before-browser/`；已修正 fixture 清理，未改產品模型清單語意。

完整品質入口退出碼 0：範圍內格式／靜態檢查、574 項後端回歸（1 項既有 Windows symlink 權限跳過）、Vue 型別／正式建置、四組 Node 契約及 **47 項瀏覽器案例**通過。記錄為 `runtime/v04-quality.log`。新增 fixture 模組及瀏覽器測試均加入明確品質 scope；沒有全庫格式化或新增依賴。

瀏覽器 JSON 附件包括 `ordered-evidence.json`、`strength-axes.json`、`four-cases.json`、`measurements.json`；兩種寬度各保存品質條件、錯誤、四案例及任務／作品量測截圖，位於忽略的 `runtime/quality/`。

歷史 UI 核對的本機輔助程式為 `runtime/v04_historical_server.py`、`runtime/v04_historical_ui.cjs`；結果 `runtime/v04-historical-ui.json`、截圖 `runtime/v04-historical-ui/`，服務使用 18766，驗收後停止。26 次引擎讀取均由 mock 攔截離線，沒有引擎 POST。來源 SQLite 前後 SHA256 同為 `2c1cf39b2080446186fb0b34dcd7c05a10272e6437ee92ff6773a0d367c133ba`；11 件原圖雜湊及 workflow 內容核對，原任務 JSON 不變。原始圖片、報告與 DATA 依既有規則不加入 Git。

本次完成 V04 的介面補驗；沒有新增 GPU 品質實測、模型預設、相容性保證或產品 API。實機觸控、全站無障礙及更多 seed／硬體仍依其他 ROADMAP 項目驗收。
