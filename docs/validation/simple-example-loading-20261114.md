# 簡易創作範例圖載入驗收

以 Windows 上的 Chromium 156.0.8078.4、1440 × 900 桌面視窗、正式建置和隔離平台量測。修改前使用 `cf84e5f` 的建置。每版各用三個新瀏覽器 context，首次直接進入簡易創作，依序切到清晨咖啡館、展開並收合範例，再切到 LoRA 任務並展開對照。三次結果一致。以下為 Resource Timing 的 `encodedBodySize` 合計，範圍為 `/assets/` 下的 PNG 及 WebP，表格不含 HTTP 標頭。

| 動作 | 改前請求數／bytes | 改後請求數／bytes |
| --- | ---: | ---: |
| 簡易創作首訪 | 3／3,089,888 | 3／56,008 |
| 切換至清晨咖啡館，維持收合 | 0／0 | 0／0 |
| 展開清晨咖啡館範例 | 1／1,330,165 | 1／1,330,165 |
| 收合後切換至 LoRA 任務 | 0／0 | 0／0 |
| 展開 LoRA 作用對照 | 3／2,133,502 | 2／1,460,490 |

首訪圖片減少 98.2%。同一階段的 `transferSize` 由 3,090,788 降至 56,908 bytes。改前展開 LoRA 對照時還會請求另一個收合中的範例圖，改後只請求對照的兩張圖。Vite 的原圖 URL 登記仍存在，實際下載由瀏覽器渲染所開啟的範例觸發。原始量測保存於本機 `runtime/quality/o08-before.json` 與 `runtime/quality/o08-after.json`。

三張 328 × 328 WebP 分別由 `docs/guide/images/examples/` 下同名的 Animagine、Pony、FLUX PNG 轉為 RGB 後，以 Pillow 的 Lanczos 縮放、WebP `quality=80` 與 `method=6` 產生，只用於起始配方卡。詳細範例及對照保留原始 PNG 與原配方 JSON。 [卡片縮圖](../../frontend/src/assets/simple-example-previews) · [原圖](../guide/images/examples) · [配方紀錄](../guide/examples)

瀏覽器回歸覆蓋首訪流量上限、收合時不建立圖片、展開單一範例或對照才請求圖片、切換配方收合、圖片失敗時維持預留比例並保留原圖連結。另逐位元比對下載 JSON，核對原 PNG 的 SHA256 與 Seed 字串 `9007199254740994`。量測與回歸使用隔離平台，畫質及實機生成證據沿用原始紀錄。 [瀏覽器回歸](../../frontend/tests/simple-example-loading.spec.ts) · [原配方驗收](simple-recipes-20261030.md)
