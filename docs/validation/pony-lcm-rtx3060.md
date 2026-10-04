# Pony V6 XL + LCM SDXL 單一 LoRA 實機驗收

2026-10-04 在本機 RTX 3060 通過平台八節點流程。LCM 是公開加速 adapter；本次驗證載入、生成、保存及追溯，不評估畫師畫風、人物品質或通用 LoRA 相容性。

## 來源與重跑

作者 [LCM 模型卡](https://huggingface.co/latent-consistency/lcm-lora-sdxl/blob/a18548dd4956b174ec5b0d78d340c8dae0a129cd/README.md) 與 [ComfyUI 官方範例](https://comfyanonymous.github.io/ComfyUI_examples/lcm/)；固定修訂 `a18548dd4956b174ec5b0d78d340c8dae0a129cd`，大小 `393855224` bytes，SHA256 `a764e6859b6e04047cd761c08ff0cee96413a8e004c9f07707530cd776b19141`。版本未有作者數字標籤，平台記錄 `revision a18548dd4956`。上游標記 Open RAIL++，條款與來源見 `models/lcm-lora-sdxl.json`；不隨 Git 散布權重。

```powershell
.\.venv\Scripts\python.exe -m scripts.install_model lcm-lora-sdxl --check
.\.venv\Scripts\python.exe -m scripts.install_model lcm-lora-sdxl
.\.venv\Scripts\python.exe -m scripts.verify_lora_generation --report runtime/pony-lcm-acceptance-new.json
.\.venv\Scripts\python.exe -m scripts.verify_lora_generation --report runtime/pony-lcm-acceptance-new.json --verify-report
```

先啟動平台與引擎，在模型庫登記兩個 manifest 的精確 hash、架構及版本。生成模式會完整核對本機兩份權重，並檢查最新清單與不可變快照。新生成報告須明確用新檔名；既有報告拒絕重複提交。提交回應遺失時只查原 UUID，不再次生成。`--verify-report` 僅 GET 已保存紀錄，不檢查權重、不啟動引擎、不同步、不匯入。

## 實測條件

| 項目 | 本次條件／結果 |
| --- | --- |
| Checkpoint | Pony V6 XL，hash 見 `models/pony-v6-xl.json` |
| LoRA | 上述 LCM SDXL；model strength 1、CLIP strength 0 |
| 流程 | 平台單一 LoRA 八節點，標準 LoraLoader；沒有 ModelSamplingDiscrete、自訂節點或參考圖 |
| Prompt | 山湖、松林、藍天的純風景；negative 排除人物、動物及文字 |
| 參數 | 768×768、batch 1、4 steps、CFG 1、lcm／sgm_uniform、denoise 1 |
| Seed | `9007199254740993`，JSON 整數與還原字串皆完整保存 |
| GPU／RAM | RTX 3060 12 GiB／約 63.94 GiB RAM |
| 環境 | Windows 10 19045、Python 3.12.10、ComfyUI 0.34.0、PyTorch 2.14.0+cu130、driver 616.56 |
| 精度與卸載 | 模型／CLIP FP16、VAE bfloat16；ComfyUI 預設動態 VRAM、CPU 卸載、PyTorch attention |
| LoRA 載入 | 引擎日誌顯示 SDXL 788 patches attached，CLIP 0；未出現未載入 LoRA key 警告 |
| 引擎耗時 | 冷引擎一次生成 19.60 秒，含模型初始化；未量暖機 |
| 平台牆鐘 | 提交到觀察成功歷史 20.672 秒，含佇列、載入、HTTP 與取樣，不是純 GPU benchmark |
| 顯存取樣 | 每約 2 秒，11 次有效取樣；設備使用量最高 10355736576 bytes（約 9.64 GiB） |
| 任務 | `2f0bc582-7526-4ccc-8820-450edb2b1a4f` |
| 作品 | `924ec5be-bbc8-5cdd-914c-0cee890821f3`，單張 768×768 PNG，1023073 bytes |
| 圖片 SHA256 | `02c5672d4aaa51feaa8bd7da567434559db7a90318e42a8e2f43616d812e1394` |

顯存含其他程序，取樣可能漏掉瞬間峰值，不代表最低需求。此結果限上述組合及參數，不代表其他 LoRA、訓練、RTX 4080、多 LoRA 或其他取樣設定可用。生成風景已人工檢視；未做品質比較或加速收益比較。

原始報告保留本機 `runtime/pony-lcm-acceptance-20261004.json`（不進 Git）；任務／作品保留資料庫及圖片。關閉 ComfyUI、重啟平台後，唯讀驗收再次通過：圖片 SHA256、完整八節點 JSON、模型及 LoRA 原始版本／來源／強度與 64 位 seed 均一致。

程式驗證：264 項後端測試（263 通過、1 項 Windows 權限跳過），涵蓋權重檢查拒絕、提交回應遺失不重送、快照修改偵測及唯讀還原。
