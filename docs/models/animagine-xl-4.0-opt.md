# Animagine XL 4.0 Opt 選型紀錄

2026-10-04 選定 Cagliostro Research Lab 的 **4.0 Opt** SDXL checkpoint。這是來源與依賴選型，尚未下載、載入或進行 GPU 驗收；不替代 P3 的第二模型生成驗收。

## 固定來源

以 [作者模型卡](https://huggingface.co/cagliostrolab/animagine-xl-4.0/blob/2b7c1b397761bf5bd3cc42e5b39ec99314a75a96/README.md) 與 [官方檔案資訊](https://huggingface.co/cagliostrolab/animagine-xl-4.0/blob/2b7c1b397761bf5bd3cc42e5b39ec99314a75a96/animagine-xl-4.0-opt.safetensors) 核對，manifest 保存於 `models/animagine-xl-4.0-opt.json`。

| 欄位 | 選定值 |
| --- | --- |
| 作者倉庫 | `cagliostrolab/animagine-xl-4.0` |
| 固定修訂 | `2b7c1b397761bf5bd3cc42e5b39ec99314a75a96` |
| 檔案 | `animagine-xl-4.0-opt.safetensors` |
| 大小 | `6938350040` bytes（約 6.46 GiB） |
| SHA256 | `6327eca98bfb6538dd7a4edce22484a1bbc57a8cff6b11d075d40da1afb847ac` |
| 格式／架構 | safetensors／SDXL；模型卡標示 FP16 |

SHA256 取自官方 API 的 LFS SHA256，非 Git blob ID 或 Xet hash。平台只有在使用者登記 `sdxl` 與此完整 SHA256 時提供專用預設，不根據檔名或版本文字推測；仍未驗證使用者的實際檔案。

## 授權

作者模型卡標記 `openrail++`，引用 [CreativeML Open RAIL++-M 原文](https://huggingface.co/stabilityai/stable-diffusion-xl-base-1.0/blob/462165984030d82259a11f4367a4eed129e94a7b/LICENSE.md)。本次已閱讀條款及 Attachment A；授權有使用限制，再散布及提供第三方服務須遵循原文的條件、通知及授權副本要求。此紀錄不提供法律保證，模型卡描述不能取代條款。

## 執行依賴與預設

第一版使用平台既有 `checkpoint-text2image-v1`：`CheckpointLoaderSimple` 必須輸出 MODEL、CLIP、VAE，接續兩個 `CLIPTextEncode`、`EmptyLatentImage`、`KSampler`、`VAEDecode`、`SaveImage`。使用 ComfyUI 獨立 venv 及其 PyTorch 依賴，無需為平台另裝 Diffusers 或自訂節點。實際權重內的元件完整性仍須載入驗證；缺元件時保留引擎錯誤，不能只憑檔案名稱確認。

作者建議起始值為 1024×1024、28 steps、CFG 5、Euler Ancestral（ComfyUI 名稱 `euler_ancestral`）；平台另外選擇 normal scheduler、denoise 1、batch 1。套用需確認參數差異，保留 prompt、negative prompt、seed 與參考素材。取樣器仍需通過目前引擎的即時能力檢查。平台已有單張圖生圖流程，本模型的該負載尚未驗收，不沿用文生圖紀錄。

## 後續驗收

2026-10-05 已完整下載、驗證大小與 SHA256、登記 `4.0 Opt`，在 RTX 3060 完成兩個不同 seed 的 1024×1024 風景生成、切回 Pony 生成及平台重啟後離線作品讀取。專用 CLI、條件與結果見 [實機驗收](../validation/animagine-xl-4-0-opt-rtx3060.md)。下面保留較早的預檢歷史；RTX 4080 與其他負載仍待測試。

先規劃足夠磁碟空間，下載後驗證完整大小與 SHA256，再登記路徑及模型資料。RTX 3060／4080 分別記錄載入、生成、耗時、顯存與重啟後作品保存；未測試前不宣稱特定速度、最低 VRAM 或生成成功。

2026-10-04 新增 `python -m scripts.install_model animagine-xl-4.0-opt --check` 唯讀預檢與固定來源安裝。安裝前須保留下載剩餘量加 2 GiB；本機約剩 6.92 GiB，低於所需 8.46 GiB，未下載或刪除任何模型。續傳、安裝鎖、雜湊驗證及拒絕覆蓋規則沿用共用安裝器，舊 `scripts.install_pony` 指令仍預設 Pony。

安裝器更新驗證：259 項後端測試（258 通過、1 項既有 Windows 權限跳過），包括固定來源拒絕、唯讀預檢、續傳及來源紀錄；未執行 Animagine 推論。

本次程式驗證：214 項後端測試（213 通過、1 項既有 Windows 權限跳過），Vue 型別檢查與 production build 通過。測試涵蓋 hash／架構匹配、唯讀查詢、不自動覆寫非預設生成參數與模型快照；沒有執行真實模型推論。
