# FLUX.1 [schnell]：固定來源與安裝預檢

2026-10-04 選定第一個 FLUX 接入目標為 BFL 的原始 BF16 `FLUX.1 [schnell]`，配套採獨立 VAE、CLIP-L 及較省記憶體的 T5-XXL FP8 scaled。此為接入選型，不是已安裝或已支援生成。

作者模型卡標示 Apache-2.0、1～4 步的蒸餾模型，並提供 CPU 卸載範例。查核當時 Hugging Face repository 為 gated，需要帳號及使用條件確認；本專案不代為登入、接受條件或保存憑證。它有本地權重，與 P8 官方生成 API 服務分開。[BFL 模型卡](https://huggingface.co/black-forest-labs/FLUX.1-schnell)

ComfyUI 範例使用分離的主模型、兩個文字編碼器與 VAE，並列出 T5 FP8 scaled 及主模型載入 FP8 的降低記憶體選項。本計畫先保留作者主模型原始 BF16 檔案，選定 T5 FP8 scaled；主模型執行精度、卸載及品質需在專用流程另外實測，不承諾 RTX 3060／4080 必定可跑或任何固定秒數。[ComfyUI FLUX 範例](https://comfyanonymous.github.io/ComfyUI_examples/flux/)

| 元件 | 固定來源修訂 | 檔案大小 bytes | 受管理目錄 |
| --- | --- | --- | --- |
| `flux1-schnell.safetensors` | BFL `741f7c3ce8b383c54771c7003378a50191e9efe9` | 23,782,506,688 | `models/diffusion_models` |
| `ae.safetensors` | BFL 同上 | 335,304,388 | `models/vae` |
| `clip_l.safetensors` | comfyanonymous `6af2a98e3f615bdfa612fbd85da93d1ed5f69ef5` | 246,144,152 | `models/text_encoders` |
| `t5xxl_fp8_e4m3fn_scaled.safetensors` | comfyanonymous 同上 | 5,157,348,688 | `models/text_encoders` |

完整 SHA256、精度、取得條件與來源分類保存於 `models/flux1-schnell-plan.json`。大小、修訂與雜湊來自 Hugging Face metadata API 的檔案資訊，未下載或重新驗證權重。編碼器採 ComfyUI 範例引用的整合來源，非 BFL 自製元件；該 repository 的授權標記為 Apache-2.0，不等同於所有上游元件條款已完整核對。[編碼器來源](https://huggingface.co/comfyanonymous/flux_text_encoders)

四個元件合計 29,521,303,916 bytes（27.49 GiB），另每個磁碟區預留 2 GiB。2026-10-04 本機預檢：同一 C 磁碟區約 6.82 GiB 可用，需要約 29.49 GiB 的完整下載／替換預算，因此空間不足。此計畫不會自動刪除其他模型、作品或 partial。原始權重檔的磁碟大小不等於 GPU VRAM 最低需求；主模型執行時轉 FP8 也不縮小這份原始下載檔。

模型庫提供「FLUX.1 接入準備」與更新按鈕。`GET /api/model-plans/flux1-schnell` 只讀固定 manifest 與受管理本機目錄，不連線引擎、不下載、不建立目錄、不雜湊大型檔案、不修改 SQLite。即使設定為遠端引擎，這份報告只代表本專案 `runtime/ComfyUI`。四個目錄名稱以本次已安裝 ComfyUI 的標準搜尋路徑核對；額外路徑／遮蔽、真正節點介面與檔案載入仍需後续專用流程檢查。

同大小檔案是 `present_unverified`，大小不符為 `size_mismatch`；讀不到或路徑解析出受管理範圍為 `unknown`，不以零容量或「已安裝」代替。空間估算保守計入全部元件，不根據未驗證檔案扣除預算。預檢通過只表示磁碟預算足夠，`generation_supported`、`download_supported` 與當前檔案已驗證欄位仍為 false。

PowerShell 唯讀檢查：

```powershell
.\.venv\Scripts\python.exe -m scripts.flux_preflight
```

結束碼 0：磁碟預算足夠；2：不足或未知；1：來源／預檢錯誤。任何結果都不啟動下載或生成。

本階段驗收：300 項後端測試（299 通過、1 項既有 Windows 權限跳過）、Vue 型別／build 與本機瀏覽器驗證通過。引擎離線仍可查看四份固定版本與磁碟預檢；未新增任務、草稿或作品。後續仍需：來源條件與上游元件授權確認、安裝／完整驗檔、FLUX 專用表單與 workflow、GPU 生成與結果保存、OOM 處理、LoRA 與參考圖相容性。
