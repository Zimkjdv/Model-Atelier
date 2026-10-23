# R04 · Pony Canny v2 與有序 LoRA 實機驗收

2026-10-23，RTX 3060 完成五個獨立 UUID，包含無 LoRA、IKEA、LCM 及兩種排列；每組均驗證原邊緣 PNG、完整 workflow、唯一作品、版本／來源快照與完整設定還原。相容性與保存恢復在這些固定條件通過；人工品質觀察未建立推薦預設。

先前 [Pony／Animagine Canny v1](checkpoint-canny-rtx3060.md) 與 [Animagine Canny v2](canny-edges-rtx3060.md) 證據保持獨立。本次實際跑 Pony v2，沒有用前兩份結果推定通過。完整可解析的來源、設定、順序／強度、UUID、圖檔／像素／workflow／任務 hash 與量測見 [證據 JSON](pony-canny-v2-20261023.json)。權重與生成原圖不納入 Git。

## 固定來源與環境

- Pony V6 XL：修訂 `5ec9c05863255568f1b59753e3838107befaa712`、6,938,041,050 bytes、SHA256 `67ab2fd8ec439a89b3fedb15cc65f54336af163c7eb5e4f2acc98f090a29b0b3`。
- SDXL Canny 1.0 FP16：修訂 `eb115a19a10d14909256db740ed109532ab1483c`、2,502,139,136 bytes、SHA256 `b2e7d3921058a442cc80430d1ec8847f42599c705e2451c95e77cf4dcf8d6c25`。
- LCM LoRA SDXL：修訂 `a18548dd4956b174ec5b0d78d340c8dae0a129cd`、393,855,224 bytes、SHA256 `a764e6859b6e04047cd761c08ff0cee96413a8e004c9f07707530cd776b19141`，model 1／CLIP 0。
- IKEA Instructions SDXL：修訂 `eaa7f67c93be0b22f00c0225d1f31232d91a052a`、185,697,368 bytes、SHA256 `d0e5fcbe1e6e2a364011bf27a66e8a40c05d02195d3e422cc393436388b8da17`，model 1／CLIP 1。

每組生成前全檔驗證 checkpoint、控制權重及本組 LoRA，沒有新增下載。來源頁與授權登記由證據 JSON 的 pinned_weights 指向固定 manifest 修訂；Pony 的 M01 適用條款與 IKEA 授權仍未知，GPU 成功不改變這些狀態。

自製椅子來源沿用 2026-10-09 圖片，現保存為 [可重跑 fixture](../../experiments/fixtures/canny-chair-v1.png)。原檔 SHA256 `59b2f8be5ed80f966bbac6a61838cabb2a8a1eca5cc17921696e22b6e7e4d8d7`；素材正規化後為 `fb219fb1268aef29671f77ab46dda4a2ea97de11a29ca9aec1b425f246406850`，與舊證據相同。fit 處理後 RGB PNG hash 為原檔 hash；素材 UUID `2a471468-0861-408b-93b4-24c541e3bca1`。新 CLI 會拒絕不同正規化來源，未默默換圖。

RTX 3060 12 GiB、RAM 68,654,481,408 bytes、driver 616.56；ComfyUI 0.34.0、Git `15eb748b3ec5f8a0a2d470b7fb280e2d7579f916`、Python 3.12.10、PyTorch 2.14.0+cu130。NORMAL_VRAM、動態顯存與 async CPU offload、PyTorch attention；checkpoint／CLIP／ControlNet FP16、VAE bfloat16。個別原生節點版本仍未知，不以整個引擎版本補值。Windows 單 GPU 提示、未安裝 Triton／無 HIP 後端保留原日誌；沒有 LoRA key 未載入或執行例外。

## 五個有限組別

全部使用 `checkpoint-canny-controlnet-edge-v2`、768²、batch 1、空 latent／denoise 1、seed 字串 `9007199254740993`、Canny 0.4／0.8、控制強度 0.5、作用 0–1。提示詞與負面提示詞五組相同：

```text
score_9,score_8_up,score_7_up,rating_safe,source_anime,single red wooden chair, empty room, three quarter view, clean illustration, daylight, no humans
people, person, text, watermark, blurry
```

| Profile | LoRA 順序 | Steps／CFG | Sampler／Scheduler | Workflow 節點 |
| --- | --- | --- | --- | ---: |
| baseline | 無 | 20／5.5 | dpmpp_2m／karras | 12 |
| style | IKEA | 20／5.5 | dpmpp_2m／karras | 13 |
| lcm | LCM | 8／1 | lcm／sgm_uniform | 13 |
| lcm-style | LCM → IKEA | 8／1 | lcm／sgm_uniform | 14 |
| style-lcm | IKEA → LCM | 8／1 | lcm／sgm_uniform | 14 |

LCM 組改用其固定取樣條件，不能與非 LCM 組當成公平品質／速度排名。每次 CLI invocation 只准一個 UUID，已有報告拒絕覆寫；本輪逐組明確執行，沒有產品自動批次或失敗重試。新 CLI 與測試加入明確品質 scope，來源 fixture 納入 Git；未修改既有 v1／v2 生成格式。

| Profile | 提交至成功歷史觀察秒 | 原引擎起訖秒 | 整卡取樣最高 used GiB | 取樣筆數 |
| --- | ---: | ---: | ---: | ---: |
| baseline | 44.329 | 42.399 | 11.311 | 21 |
| style | 30.453 | 29.379 | 11.244 | 15 |
| lcm | 19.328 | 18.745 | 11.249 | 10 |
| lcm-style | 21.844 | 20.179 | 11.212 | 11 |
| style-lcm | 19.406 | 17.698 | 11.197 | 10 |

第一組冷載入，其餘共用引擎及部分快取。平台時間包含 HTTP／載入／佇列／觀察；整卡低頻取樣約兩秒一次，包含其他程序與快取，不是任務專用峰值或最低顯存。E05 的 task_vram_peak_bytes 保持 null。完整回歸在五組生成結束後執行，未把此表當純 GPU benchmark。

## 原圖品質與邊緣

逐張查看來源與五件保存原圖：

- baseline：輪廓大致沿用線稿，深色細框、半透明椅背及強陰影；未達紅色木材與乾淨插畫要求。
- style：紅棕色細框較清楚，增加橫向支架與陰影，椅背／座面仍中空；未成為木質實體或說明書畫風。本提示未要求說明書，不能據此否定 IKEA 的其他用途。
- lcm：平面紅色線稿較貼近來源，背景有模糊垂直色帶；缺乏椅子體積、椅背／座面及木質材質。
- lcm-style：紅棕線框、淺灰背景與弱陰影，仍中空且平面，未見材質或插畫品質改善。
- style-lcm：肉眼近似正向組，仍為平面線框；RGB 像素 hash 不同，未宣稱逐像素一致或所有 LoRA 順序等效。

五件原邊緣均為節點 13 同一 conditioning tensor 直接送到 SaveImage 16：768² 二值 RGB、4,384 白像素／589,824（約 0.743%），decoded RGB SHA256 `202545d148f9816a6fdde938e946d5d410241c345e1b05ae731e964d444a634c`，與既有 Animagine v2 相同。PNG metadata 包含各自 workflow，因此原檔 hash 各異，詳見 JSON；沒有用 CPU 近似預覽取代原邊緣。只有節點 7 匯入作品，沒有把邊緣混入作品庫。

## 保存、下載與重啟還原

| Profile | 任務 UUID | 作品 UUID |
| --- | --- | --- |
| baseline | 5025d913-ec7d-4b29-ae48-b626cd0f7adf | 36f4e609-d771-5630-af3c-7e6aa2a7e4c3 |
| style | 0f6f7be0-866d-4848-9563-a4d94d0f6ed2 | 5176e8e9-6f61-5f13-a872-ab6c77c6035d |
| lcm | 0133b163-c192-4bc1-a974-c76e25c54995 | 6a053d0b-6805-5944-8ff3-00249ed5527f |
| lcm-style | 51b43e3e-2567-45a2-a8c5-e15151f2a970 | 6fa5e0a3-a4d9-5d5e-a235-af1161b5f04e |
| style-lcm | 5dbd9866-0976-4dc8-9b26-7ac8b9cc04c9 | ba0cddc4-a756-554b-8ff8-555094e1505c |

1440px／390px 共 10 次實際作品頁操作，下載原圖、原邊緣 PNG 及完整 workflow；下載 bytes／hash、精確大整數 seed、來源、控制模型、Canny／取樣參數、有序 LoRA 強度全部核對，還原等待原素材可見，沒有新生成。另在引擎離線、登記版本改變後重跑同樣 10 次操作，原檔不變；選單未即時更新取樣能力時仍明示未確認，不用歷史成功冒充本次引擎驗證。

關閉本輪引擎，把隔離 checkpoint／ControlNet／LoRA 登記版本改成 changed-r04-recovery；五個原 UUID 恢復皆 200、返回完全相同任務 JSON，改同 UUID 控制強度皆 409。兩階段各 88 次 GET-only 核對五份報告（一次離線、一次停止後重啟平台），原來源／版本、任務 JSON、作品／邊緣 hash 全部不變，引擎日誌仍只有五次 prompt。平台內 5 任務／5 作品／1 素材／5 邊緣記錄／0 草稿／0 方案。正式 DATA 8 個檔案前後 hash 一致，僅停止本輪啟動的服務。

本機忽略證據位於 `runtime/r04-live-20261023`：五份 profile JSON、SQLite／素材／處理輸入／作品／control_edges、ComfyUI 日誌、browser.json／下載檔與兩寬度 PNG、offline.json、restarted.json、job-hashes.json、formal-before／after 與 final-cleanup.json。保留整份資料才能重做離線檢查；遺失原檔不補生成。

## 重跑與限制

先把 fixture 明確匯入獨立平台，依四份 manifest 登記原引擎模型；不自動修改正式資料。各 profile 分別執行，報告須不存在：

```powershell
.\.venv\Scripts\python.exe -m scripts.verify_pony_canny_loras --profile baseline --source-id <素材UUID> --platform http://127.0.0.1:<平台埠> --expected-engine http://127.0.0.1:<引擎埠> --report runtime/pony-canny-v2-baseline.json
```

另選 style、lcm、lcm-style 或 style-lcm 各自執行，不含自動迴圈。使用原 profile、source-id、端點及報告加 `--verify-report` 僅 GET 核對，不 sync／驗權重／匯入／重新生成。

5 項新增整合涵蓋五 profile、遺失回應單次提交、GET-only、順序／hash／強度／還原篡改拒絕、缺權重／登記與固定來源拒絕。18 項 Canny 驗收回歸通過。完整 `scripts/check_quality.py` 通過格式／靜態、599 項後端（1 項既有 Windows 權限跳過）、Vue 建置／四組契約及 89 項 Chromium（約五分鐘）；R06 CI 匯入等待另有兩種寬度的受控延遲回歸。日誌 `runtime/r04-target.log`、`runtime/r04-quality.log`、`runtime/r04-browser.log`。

本輪只涵蓋一張椅子、單 seed／控制強度與兩種既有 LoRA。R05 的更多品質條件、R01 depth／pose、R02 adapter、RTX 4080 與訓練仍待驗證；不自動評分、不保證畫風／角色／材質一致，也不因本次生成成功關閉 M01 或未知授權。
