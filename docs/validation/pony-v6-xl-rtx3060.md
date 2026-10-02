# Pony V6 XL：RTX 3060 本地驗收

日期：2026-10-02。這是平台整合驗收，不是模型品質排行或硬體效能保證。

## 模型與環境

| 項目 | 實測值 |
| --- | --- |
| 模型 | Pony V6 XL；作者 AstraliteHeart |
| 固定來源 | [作者 Hugging Face 修訂](https://huggingface.co/AstraliteHeart/pony-diffusion-v6/tree/5ec9c05863255568f1b59753e3838107befaa712)，`v6.safetensors` |
| 本地名稱 | `pony-v6-xl.safetensors` |
| 檔案大小 | 6,938,041,050 bytes |
| 完整 SHA256 | `67ab2fd8ec439a89b3fedb15cc65f54336af163c7eb5e4f2acc98f090a29b0b3`，下載後完整檔案驗證 |
| 授權資訊 | 固定修訂模型卡標記 `creativeml-openrail-m`，未附全文；完整條款尚未核對 |
| GPU / VRAM | NVIDIA GeForce RTX 3060 / nvidia-smi 回報 12 GiB |
| 系統 | Windows 10 19045、Python 3.12.10、約 63.94 GiB RAM |
| 引擎 | ComfyUI 0.34.0，commit `15eb748b3ec5f8a0a2d470b7fb280e2d7579f916` |
| CUDA 環境 | PyTorch 2.14.0+cu130、NVIDIA 驅動 616.56 |
| 載入方式 | ComfyUI 預設動態 VRAM；模型 float16、VAE bfloat16；CPU offload 由引擎管理，沒有 LoRA 或參考圖 |
| 執行位置 | 平台 `127.0.0.1:8000`、本機 ComfyUI `127.0.0.1:8188`，分開 `.venv` |

來源與預期 hash 在 `models/pony-v6-xl.json`，安裝後來源證明在 runtime checkpoint 同目錄 `.provenance.json`。

## 設定與結果

單張 768×768、20 steps、CFG 5.5、DPM++ 2M / Karras、denoise 1、batch 1。提示詞為山湖、森林與天空的風景，負面提示排除人物、動物、文字與浮水印。完整提示詞在驗收 CLI 與 runtime 報告中。

| 項目 | 結果 |
| --- | --- |
| 首次生成 seed | `9007199254740993`，大於 JavaScript 可精確表示的整數範圍 |
| 首次任務 | `e24da88f-3de2-4248-9693-abcc1272154e` |
| 首次作品 | `13bf2cc2-15b4-587f-a933-ef67559fe687` |
| 首次提交到確認成功 history | 22.880 秒；含冷載入、排隊、HTTP 與取樣／查詢開銷 |
| 引擎回報首次執行 | 22.55 秒；與平台觀測時間定義不同 |
| VRAM 觀察最高值 | 10,451,156,992 bytes，約 9.73 GiB；12 次有效設備總用量取樣，間隔至少 2 秒 |
| 介面再次生成 seed | `9007199254740994`，由載入作品後手動修改 seed 再按生成 |
| 介面任務／作品 | `872000cc-e07a-4aa6-b095-39c0adefc19a` / `68bd0260-cf46-5099-bf2b-6535a6259075` |
| 介面進度 | 瀏覽器確認節點 5、90%（18 / 20）及「即時進度已連線」；之後以成功 history 確認完成 |
| 引擎回報再次執行 | 8.85 秒，模型已載入；未另外取得相同定義的 VRAM／平台耗時基準 |

VRAM 是 nvidia-smi 的設備總用量，包含其他程序及桌面，取樣可能錯過瞬時峰值；不能解讀為此工作流程最低必要顯存。不同解析度、其他模型、附加元件、訓練與 RTX 4080 未在本次驗證。

## 完成的驗收

- 安裝器核對完整大小與 SHA256 後才發布正式 checkpoint；正式檔與下載暫存不重複保存。
- 真實 ComfyUI 同步非空模型清單，平台保留登記版本 `V6 XL` 與固定修訂來源。
- CLI 只提交一個 UUID，確認 successful history，匯入作品並驗證原圖解碼、尺寸、SHA256、完整 workflow 與精確 seed。
- 瀏覽器預覽原圖與設定；載入作品後保留 768×768、seed 字串與完整取樣參數；載入本身沒有生成。
- 創作頁再次生成收到真實 GPU 節點 SSE 進度，成功後透過作品庫按鈕匯入第二張作品。
- 關閉本次啟動的 ComfyUI 與平台，確認服務埠停止，再只啟動平台；ComfyUI 保持離線。
- `--verify-report` 只 GET 原任務／作品，核對原報告圖片 hash、完整流程、版本及所有還原參數。新瀏覽器頁也可預覽兩張已匯入作品。

本機報告為 `runtime/pony-v6-xl-acceptance.json`，介面任務快照為 `runtime/pony-ui-acceptance.json`，預覽截圖為 `runtime/pony-real-generation.png`。權重、報告及作品不提交 Git；作品與 SQLite 在 `data/`，備份時一起保存。

116 項後端測試、Vue 型別檢查／正式建置與平台依賴檢查通過。1 項建立 symlink 的安裝器測試因 Windows 權限跳過；驗收工具另外以模擬連結驗證報告路徑防護。驗收結束後確認 8000、8188、5173、8001 均未監聽。

## 重跑

依 README 安裝及啟動服務後，執行 `scripts/verify_local_generation.py`。新的生成必須選未使用的 `--report` 名稱；原報告加 `--verify-report` 只讀驗證。報告保留原任務 ID，逾時或不明結果不能自動重送。
