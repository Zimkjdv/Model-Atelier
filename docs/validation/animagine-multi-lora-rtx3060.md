# Animagine 畫風及多 LoRA 驗收（2026-10-05）

這次驗證公開 SDXL 黑白說明書畫風 adapter，與 LCM 有序組合。三次任務均在隔離平台完成 GPU 生成、作品匯入、完整 JSON／精確 seed／版本／強度還原；關閉 ComfyUI 及平台後，只重啟平台，原報告 `--verify-report` 的 GET 核對全部通過。正式資料沒有新增任務、作品或草稿；只同步並登記新 LoRA。

來源：作者 [固定模型卡](https://huggingface.co/ostris/ikea-instructions-lora-sdxl/blob/eaa7f67c93be0b22f00c0225d1f31232d91a052a/README.md) 與 [固定權重](https://huggingface.co/ostris/ikea-instructions-lora-sdxl/blob/eaa7f67c93be0b22f00c0225d1f31232d91a052a/ikea_instructions_xl_v1_5.safetensors)。185,697,368 bytes，SHA256 `d0e5fcbe1e6e2a364011bf27a66e8a40c05d02195d3e422cc393436388b8da17`。作者沒有可確認的語意版本號，以 `revision eaa7f67c93be` 表示；授權僅標 `other`，條款未知，不推定可商用或再散布。manifest 保存此限制，權重不進 Git。

環境：RTX 3060 12 GiB、約 64 GiB RAM、Windows／Python 3.12.10、ComfyUI 0.34.0、PyTorch 2.14.0+cu130。checkpoint 為固定 Animagine 4.0 Opt，SHA256 見其獨立驗收。引擎正常顯存模式、動態 VRAM、CPU 卸載、checkpoint FP16、VAE BF16；沒有修改引擎精度設定。

三組共用 1024×1024、batch 1、denoise 1、seed 字串 `9007199254740993`；提示詞為黑白線稿、椅子組裝、白背景、無人物。

| 條件 | 參數 | 節點 | 提交至歷史確認 | 引擎日誌耗時 | 整卡顯存取樣峰值 |
| --- | --- | --- | --- | --- | --- |
| baseline，無 LoRA，冷啟動 | 28 steps／CFG 5／euler_ancestral／normal | 7 | 33.859 秒 | 32.19 秒 | 10,695,475,200 bytes，17 筆 |
| style，單一畫風，模型已載入 | 同 baseline；model 1、CLIP 1 | 8 | 29.407 秒 | 28.88 秒 | 10,810,818,560 bytes，15 筆 |
| multi，LCM → 畫風，模型已載入 | 4 steps／CFG 1／lcm／sgm_uniform；LCM 1/0，畫風 1/1 | 9 | 11.563 秒 | 10.90 秒 | 10,497,294,336 bytes，7 筆 |

耗時包含模型或 patch 準備，不是純採樣 benchmark。顯存為低頻整卡取樣，包含其他程序，並非連續峰值、任務專用或最低需求。沒有 RTX 4080、更多 LoRA、圖生圖／LoRA 或訓練實測。

人工檢查：baseline 與 style 均有清楚椅子線稿，style 的椅子與說明書布局有所改變；這個單一提示詞本身就要求線稿，不能據此量化風格模仿程度。multi 結果線条非常淡、對比明顯不足，品質不視為通過；4 steps／CFG 1 不直接推薦作為畫風預設。多 LoRA 參數與更多提示詞仍需人工比較。介面條件化證據目前只支援單一 LoRA；多項仍保守提示未登記，沒有借用單一組合的品質或資源結論。

安裝及驗收：

```powershell
.\.venv\Scripts\python.exe -m scripts.install_model ikea-instructions-lora-sdxl --check
.\.venv\Scripts\python.exe -m scripts.install_model ikea-instructions-lora-sdxl
# 先啟動平台及 ComfyUI、同步並登記固定模型與 LoRA；每次生成必須使用新報告路徑。
.\.venv\Scripts\python.exe -m scripts.verify_multi_lora --profile baseline --report runtime/my-baseline.json
.\.venv\Scripts\python.exe -m scripts.verify_multi_lora --profile style --report runtime/my-style.json
.\.venv\Scripts\python.exe -m scripts.verify_multi_lora --profile multi --report runtime/my-multi.json
# 原報告驗證只 GET，不重新查權重或生成。
.\.venv\Scripts\python.exe -m scripts.verify_multi_lora --profile multi --report runtime/my-multi.json --verify-report
```

本機證據在 `runtime/style-live-data-20261005/`，三份報告保留 UUID、原圖 hash、工作流程、有序 metadata、還原設定與顯存取樣。357 項後端測試（356 通過、1 項既有 Windows 權限跳過），Vue 型別及正式建置通過。
