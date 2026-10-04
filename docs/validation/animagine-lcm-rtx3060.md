# Animagine XL 4.0 Opt + LCM SDXL 單一 LoRA 驗收

2026-10-05 在 RTX 3060 成功完成原生八節點生成。此項確認公開加速 adapter 的載入、保存與追溯，不评估畫師效果、多 LoRA 組合或加速收益。

兩個固定來源、完整大小、SHA256 與授權在 `models/animagine-xl-4.0-opt.json`、`models/lcm-lora-sdxl.json`。生成前完整核對本地權重；Animagine 版本 `4.0 Opt`，LCM 版本為固定作者修訂 `revision a18548dd4956`。權重不隨 Git 再散布。

| 項目 | 實測結果 |
| --- | --- |
| 環境 | Windows 10 19045；RTX 3060 12 GiB；約 63.94 GiB RAM |
| Python／引擎 | 3.12.10／ComfyUI 0.34.0，commit `15eb748b3ec5f8a0a2d470b7fb280e2d7579f916` |
| CUDA 環境 | PyTorch 2.14.0+cu130；NVIDIA 616.56 |
| 精度／卸載 | model、CLIP FP16；VAE bfloat16；預設 dynamic VRAM、async CPU offload |
| 圖片 | 單張 1024×1024 PNG；一般山湖風景、沒有參考圖 |
| 參數 | 4 steps、CFG 1、lcm／sgm_uniform、denoise 1、batch 1 |
| LoRA 強度 | model 1、CLIP 0；引擎顯示 SDXL 788 patches attached |
| Seed | `9007199254740993`，workflow JSON 整數與還原字串完整保留 |
| 任務／作品 | `d33b1f7d-4352-4b43-8a8b-034d85118f1d`／`ac51142f-df57-5c1c-ad6a-386a1ee6fd7d` |
| 原圖大小／SHA256 | 1,823,322 bytes／`fcc391e745999091e83a1d59d21e8fbc47204a5adec06a0cb2f315199b296930` |
| 引擎冷執行 | 21.97 秒；含模型初始化 |
| 提交至平台確認成功 history | 23.0 秒；含排隊、載入、HTTP、查詢與取樣 |
| 設備顯存取樣 | 12 次有效值，最高 10,730,078,208 bytes，約 9.99 GiB |

設備用量包含其他程序，可能漏掉瞬時峰值，不是最低顯存需求。沒有暖機、訓練、其他硬體、其他強度、取樣參數或多 LoRA 實測；Pony 的紀錄也不代替此組合。

平台確認 successful history 後匯入原圖；核對原圖解碼／尺寸／hash、完整 workflow、checkpoint 與 LoRA 不可變快照、來源版本及還原強度。關閉引擎、重啟隔離平台後只 GET 原任務與作品再次驗證，沒有新生成。報告及四個本輪驗收任務保存在 `runtime/animagine-live-data-20261005`，不寫入正式作品庫。

紀錄新增至 `models/lora-validation-records.json`，現有模型庫、創作頁及資源提示依兩份登記 hash／架構比對；強度、解析度與取樣參數另外比對。紀錄只描述已測條件，不證明目前的登記值等於目前權重。

```powershell
.\.venv\Scripts\python.exe -m scripts.verify_animagine_lora --report runtime/animagine-lcm-new.json
.\.venv\Scripts\python.exe -m scripts.verify_animagine_lora --report runtime/animagine-lcm-new.json --verify-report
```

先啟動平台與引擎、同步清單并登記兩份 manifest 的固定 hash／架構／版本。新生成使用新報告；丟失回應查詢原 UUID，不重送。驗證模式只讀已保存的圖片與快照，可在 ComfyUI 離線時執行。
