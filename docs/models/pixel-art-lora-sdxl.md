# Pixel Art LoRA SDXL：固定來源與相容副本

L01 選用 [Hadimeeee 的固定修訂](https://huggingface.co/Hadimeeee/pixel-art-lora-sdxl/blob/5440ac9c42ab16fea0d65e25bd149fc0f21b1271/README.md)作有限的像素畫／有序組合比較。作者描述的原用途是玩偶照片轉像素角色，另有去背、Canny、ControlNet 與量化流程；本平台只測原生 ComfyUI 文生圖 LoRA，不執行該庫 Python，也不推定完整照片轉換流程或動漫作者畫風已驗收。

## 來源與格式

| 欄位 | 原始來源 | 本地相容副本 |
| --- | --- | --- |
| manifest | `models/pixel-art-lora-sdxl.json` | `models/pixel-art-lora-sdxl-comfy-v1.json` |
| 修訂／版本 | `5440ac9c42ab16fea0d65e25bd149fc0f21b1271` | `key-map-v1 / upstream 5440ac9c42ab` |
| 檔名 | `pixel_art_lora_sdxl.safetensors` | `pixel_art_lora_sdxl_comfy_v1.safetensors` |
| bytes | 185963768 | 185969440 |
| SHA256 | `30ef3c19f6bf6c621a4a90722722df78af915c8f4e9b35f91a66d2ea7a079444` | `eef9b71806b7715760af4f8ab5a038b29daf41272ab30782f38381aee096f1be` |

官方 API 的檔案大小與 LFS SHA256 已核對。原始檔的 1,120 個張量鍵在目前 ComfyUI 0.34.0 全部被回報未載入；原始四次任務即使出圖，也不列為 LoRA 載入通過，失敗證據另保留。像素提示詞本身已有像素外觀，不能用畫面「看起來像素」證明權重套用。

`scripts.convert_pixel_lora` 只接受這個固定完整 hash 的來源。它將已知 SDXL attention LoRA 鍵名映射為原生 `lora_unet_…` 別名，保留每個 tensor 的 dtype、shape、offset、rank 配對及完整資料區 bytes；不改權重數值或自動處理任意模型。資料區 SHA256 為 `21c448739400fee2dc5f5c68f4f218004a3bc55499f4ebf9bf7ef2ad6d02c68a`。原始檔保留，副本具有獨立檔名、hash、版本及轉換 provenance，並非作者另發的一個模型。

該檔只有 UNet 張量、沒有 CLIP 張量；CLIP 強度仍可如實保存，但不能預期每次調整都有效。本批 model 1／CLIP 1 與 model 1／CLIP 0.5 的 decoded RGB 相同，只適用該組條件。

## 安裝與單組驗收

```powershell
.\.venv\Scripts\python.exe -m scripts.install_model pixel-art-lora-sdxl --check
.\.venv\Scripts\python.exe -m scripts.install_model pixel-art-lora-sdxl
.\.venv\Scripts\python.exe -m scripts.convert_pixel_lora --check
.\.venv\Scripts\python.exe -m scripts.convert_pixel_lora
```

`--check` 不寫檔。下載僅使用固定作者 safetensors，沿用續傳／鎖／完整驗檔及 2 GiB 預留。轉換在同目錄用暫存檔、fsync、驗檔及排他發布；已有副本只沿用完全相符的 bytes，差異檔案不覆寫。未知鍵、重複鍵、非法 offset／shape、缺少配對或不符來源拒絕。轉換副本不是遠端下載 alias，不將原始 bytes 冒充副本的 hash。

使用者在自己的平台明確同步 LoRA 清單後，選擇 **comfy_v1** 檔案，按副本 manifest 登記 SDXL 架構、版本、大小、hash、來源與授權欄位。同步／登記不生成；CLI 也要求同一原引擎的固定 checkpoint／LoRA 登記，不根據檔名推定實際版本。

```powershell
.\.venv\Scripts\python.exe -m scripts.verify_style_matrix --profile lcm-pixel --subject anime-portrait --seed 18446744073709551615 --platform http://127.0.0.1:8001 --expected-engine http://127.0.0.1:8188 --report runtime/l01-new.json
.\.venv\Scripts\python.exe -m scripts.verify_style_matrix --profile lcm-pixel --subject anime-portrait --seed 18446744073709551615 --platform http://127.0.0.1:8001 --expected-engine http://127.0.0.1:8188 --report runtime/l01-new.json --verify-report
```

一指令一個新 UUID，報告檔須不存在；失去回應只查原 UUID，不重送。`--verify-report` 只 GET 原任務／作品及原設定，不讀權重、同步、匯入或生成。`8001` 是隔離平台範例，使用正式平台會新增正式資料。完整 profiles、取樣分組、原圖與品質失敗見 [L01 驗收](../validation/style-matrix-20261023.md)。

## 使用條件與限制

固定作者模型卡標記 Apache-2.0；該修訂清單未附獨立 LICENSE，基礎模型及資料適用鏈未在本輪完整核實，兩份 manifest 均保持 `terms_verified=false`。轉換保留原來源狀態，沒有把未知改成已驗證；權重不納入 Git。

本輪只驗證 RTX 3060／固定 Animagine／指定 LoRA 條件。使用者的作者目標及同角色圖片仍未提供；需要指定畫風品質結論時，依[圖片提醒](../anime-style-development.md#image-input-reminders)補資料後另驗，不借用這批結果。
