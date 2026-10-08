# 多 LoRA 步數與順序品質觀察（2026-10-08）

沿用固定 Animagine 4.0 Opt、LCM SDXL 與公開 IKEA 黑白畫風 LoRA，來源／版本／完整 SHA256 見 [原驗收](animagine-multi-lora-rtx3060.md)。本次重新核對實際權重大小及 SHA256；新增固定 CLI profile，不調整模型預設。

相同無人物木椅說明書提示詞、負提示詞、seed `9007199254740993`、1024×1024、CFG 1、lcm／sgm_uniform、denoise 1、batch 1。LCM model／CLIP 為 1／0，畫風為 1／1。兩個標準九節點任務各只提交一次，均成功生成、匯入原圖並核對完整 workflow、不可變模型／LoRA／環境快照與原設定還原。

| Profile | 有序 LoRA | Steps | 提交至觀察歷史 | 引擎歷史起訖 | 整卡取樣最高／有效樣本 |
| --- | --- | --- | --- | --- | --- |
| `multi-8` | LCM → IKEA | 8 | 29.734 s | 27.597 s | 10,996,416,512 bytes／15 |
| `style-lcm-8` | IKEA → LCM | 8 | 13.907 s | 13.422 s | 9,922,674,688 bytes／8 |

RTX 3060 12 GiB、Windows 10 19045、Python 3.12.10、ComfyUI 0.34.0、PyTorch 2.14.0+cu130、驅動 616.56；模型／CLIP FP16、VAE bfloat16，ComfyUI 動態 VRAM／CPU offload。第一組包含冷載入與初始化；第二組部分節點快取並重新準備 patch。耗時差異不能當作順序速度比較；整卡低頻取樣包含其他程序，不是连续峰值、任務專用顯存或最低需求。

人工觀察：8 步仍偏淡、對比不足。正反順序視覺上非常接近，未見可辨識的改善，但 decoded RGB 雜湊不同（正向 `8e969e93b762993a5d2c08e4694fc4878fdca11070909b347ba6c27b581a956e`，反向 `54f15baa01435703e843a3a9ffb2c93615c68effa6da00f6f70a886138b61cfb`），不宣稱逐像素一致或所有 LoRA 順序等效。此單一提示／seed 不足以量化畫風模仿程度；兩組都不設為推薦品質預設。其他畫風、強度、多 seed、圖生圖、訓練及 RTX 4080 仍待驗證。

```powershell
.\.venv\Scripts\python.exe -m scripts.verify_multi_lora --profile multi-8 --platform http://127.0.0.1:8001 --report runtime/animagine-multi-8-20261008.json
.\.venv\Scripts\python.exe -m scripts.verify_multi_lora --profile style-lcm-8 --platform http://127.0.0.1:8001 --report runtime/animagine-style-lcm-8-20261008.json
```

每份新 report 必須使用不存在的路徑；已存在時只使用同一 profile 的 `--verify-report`，只做 GET，不同步、生成或匯入。原報告及兩件作品保留在 `runtime/roadmap-live-data-20261008` 與 `runtime/`，不納入 Git 或正式作品庫。原 4 步結果仍保留；registry 按有序雜湊及強度／參數分別匹配，不借用正向證據給反向順序。

384 項後端測試（383 通過、1 項既有 Windows 權限跳過）、Vue 型別／建置與真實 API 驗收通過。瀏覽器工具因環境啟動錯誤無法執行，本次沒有新增 UI 實機驗收。
