# Animagine XL 4.0 Opt：RTX 3060 本地驗收

日期：2026-10-05。這是平台整合及固定條件驗收，不是畫風品質或硬體效能保證。

## 安裝與環境

從 [作者固定修訂](https://huggingface.co/cagliostrolab/animagine-xl-4.0/tree/2b7c1b397761bf5bd3cc42e5b39ec99314a75a96) 下載 `animagine-xl-4.0-opt.safetensors`。完整 6,938,350,040 bytes 與 SHA256 `6327eca98bfb6538dd7a4edce22484a1bbc57a8cff6b11d075d40da1afb847ac` 核對通過；來源／授權與依賴見 [模型紀錄](../models/animagine-xl-4.0-opt.md)。權重及 `.provenance.json` 保存在 runtime，不納入 Git。

預檢時約有 18 GiB，超過下載加 2 GiB 保留量的 8.46 GiB。本次沒有刪除其他模型或使用者檔案。

| 項目 | 實測環境 |
| --- | --- |
| GPU／VRAM | NVIDIA GeForce RTX 3060；nvidia-smi 12 GiB |
| RAM／系統 | 約 63.94 GiB；Windows 10 19045 |
| Python／PyTorch | 3.12.10／2.14.0+cu130 |
| ComfyUI | 0.34.0，commit `15eb748b3ec5f8a0a2d470b7fb280e2d7579f916` |
| NVIDIA 驅動 | 616.56 |
| 精度與卸載 | 模型、CLIP float16；VAE bfloat16；預設動態 VRAM、async CPU offload |
| 平台／引擎 | 隔離資料庫 `127.0.0.1:8001`／真實引擎 `127.0.0.1:8188` |

## 生成結果

作者起始設定：1024×1024、28 steps、CFG 5、Euler Ancestral。平台選用 normal scheduler、denoise 1、batch 1，沒有 LoRA 或參考圖片。提示詞為一般山湖、森林、天空，排除人物與動物；完整提示詞在專用 CLI 與報告。

| 指標 | 首次樣本 | 已載入模型的第二次樣本 |
| --- | --- | --- |
| Seed | `9007199254740993` | `9007199254740994` |
| 任務 | `8da56cd5-11b7-42d9-b305-f354b82ed08c` | `2598e480-5ded-48c9-8cd6-df3500f5c497` |
| 作品 | `d7f3c647-fbd5-531a-a8f3-2f8590c08ec8` | `43054152-84ad-51e3-9a93-6c53d1f4d10c` |
| 提交至平台確認成功 history | 36.391 秒 | 22.765 秒 |
| 引擎回報執行 | 35.75 秒 | 22.35 秒 |

第二次樣本換 seed 使 KSampler 重新執行，不把快取回應當成暖推論。首次 18 次有效設備用量取樣最高為 10,867,441,664 bytes，約 10.12 GiB；包含桌面及其他程序，可能漏掉瞬時峰值，不是最低顯存需求。時間包含的工作不同，不能視為純 GPU benchmark。

驗收確認真實 CUDA 裝置、即時 checkpoint／取樣能力、完整本地 hash、凍結的模型版本快照、成功 history、原圖格式與尺寸／hash、完整七節點 JSON、精確 seed 與作品設定還原。另在同一引擎切回 Pony 驗證生成；重啟隔離平台並關閉引擎後，原作品仍可只讀驗證。

正式模型庫保留 `4.0 Opt` 與固定来源；驗收任務／作品位於 `runtime/animagine-live-data-20261005`，沒有混入日常作品庫。條件紀錄在 `models/validation-records.json`，依登記 hash／架構匹配，不能證明目前檔案或新的任務已驗證。RTX 4080、訓練、不同尺寸、參考圖片與畫風品質未在此項驗收。

## 重跑

```powershell
.\.venv\Scripts\python.exe -m scripts.install_model animagine-xl-4.0-opt --check
.\.venv\Scripts\python.exe -m scripts.install_model animagine-xl-4.0-opt
.\.venv\Scripts\python.exe -m scripts.verify_animagine_generation --report runtime/animagine-new-first.json
.\.venv\Scripts\python.exe -m scripts.verify_animagine_generation --repeat --report runtime/animagine-new-repeat.json
```

先啟動平台與 ComfyUI、同步清單並登記固定版本／架構／大小／hash。新生成使用新報告名稱；原報告加 `--verify-report` 只 GET 任務及作品，`--repeat` 報告須保留該旗標。未知結果保留原 UUID，不重新生成。同一份報告的跨程序搶占仍使用原子獨佔建立。
