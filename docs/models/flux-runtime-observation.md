# F02：實際精度、卸載與資源觀察

使用 [F01 固定權重](flux-installation.md)，只提供一個固定的 `flux-schnell-fp8-cpu-512-v1` 技術案例：512×512、batch 1、4 步、CFG 1、Euler／simple、主模型選 FP8 e4m3fn、編碼器選 CPU。提示詞為一般成年人物在圖書館閱讀的動漫插畫，沒有作者圖片或訓練。完整設定／workflow／seed 與實測見 [驗收](../validation/flux-runtime-20261025.md)。

```powershell
# 唯讀讀取本機檔案標頭，不載入 Torch、不連網、不啟動 worker。
.\.venv\Scripts\python.exe -m scripts.verify_flux_runtime

# 先完成工作並停止受管理 ComfyUI，再明確執行固定 GPU 案例。
.\.venv\Scripts\python.exe -m scripts.verify_flux_runtime --run
```

預設標頭檢查只代表儲存 dtype，不是執行精度證據。`--run` 先取得專案運算租約、核對四份完整 SHA256，再凍結設定、精確 seed、來源版本／程式 hash，使用 ComfyUI 的獨立 Python 執行原生節點。沒有自動停引擎；8188 仍有服務或狀態無法確認就拒絕。租約協調本平台的新派送，不鎖定整張顯卡或其他軟體；不要與完整品質檢查並行，部分既有模擬測試也會使用此租約。

worker 先在 CPU 編碼，再載入主模型／取樣及 VAE／解碼，各階段明確卸載並釋放上一個模型；這與完整平台 HTTP 引擎的載入／快取順序分開記錄。它不修改 ComfyUI 原碼、不安裝新節點、不改用 GGUF、不自動下載；HF／Transformers 設定離線，憑證環境變數不傳給 worker。

## 回報內容與邊界

- 檔案標頭只輸出 dtype 的 tensor 數／bytes 與白名單的架構／授權文字，不匯出內嵌縮圖或任意 metadata。
- 在獨立程序內包裝原生 `cast_bias_weight`，原呼叫及回傳值保持原樣；記錄實際權重來源、輸入及回傳張量的 dtype／device，最多 128 種組合，溢位明確計數。這有觀察成本，也不代表每個 kernel／累加器精度；未觀察到的部分保持未知。
- 階段快照記錄實際參數／buffer 的 dtype、CPU／CUDA 邏輯 bytes；含共享 view 時不能當成唯一 storage 或配置的 VRAM。
- 程序 RSS、主機可用 RAM 與整卡 `nvidia-smi` 約每秒取樣，最多留 1,200 筆並保留取樣總數；失敗／未知保持空值。另取同程序 CUDA allocator 的最高配置／保留值。整卡／主機數字包含其他軟體，取樣最高值不是連續真實峰值或最低硬體需求。

每次新 UUID 的 `runtime/flux-runtime-checks/<UUID>/` 保存 `request.json`、`worker.log`、`observation.json`、`run.json` 及成功時的 `output.png`。worker 有 30 分鐘上限；中止／逾時只停止這次擁有的程序，等它退出才釋放租約，保留失敗回執及日誌。初始化失敗可能沒有 observation，回執明確表示缺少，不能當成零用量或成功。

此項驗證一個原生節點技術配置的精度／卸載與資源，不認列完整平台生成、任務保存、離線還原及 OOM 的 F03，也不認列 F04、RTX 4080、32 GiB RAM、較大尺寸或作者品質。最低 RAM／VRAM 仍為未知。條款見 [逐元件查核](flux-component-licenses.md)。
