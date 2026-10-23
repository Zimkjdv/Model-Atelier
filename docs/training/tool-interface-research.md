# T02 · SDXL LoRA 工具與資料介面評估

查核日期：2026-10-23。這份評估選定 **`kohya-ss/sd-scripts` 作為首輪資料出口的候選介面**，以 Hugging Face Diffusers 官方範例作對照。本輪只交付資料契約與出口；沒有安裝 trainer、執行訓練、更新模型權重或交付訓練啟動器。需求與成功條件沿用 [T01](requirements.md)，實際環境、訓練 run 與產物回登留給 T03／T04。

## 固定查核版本與選擇理由

| 項目 | 本次查核版本 | 用途 |
| --- | --- | --- |
| `kohya-ss/sd-scripts` | `11d8cedd0c67b93a10f8b2d75f43554f6f12c794`，官方 commit 日期 2026-10-20，合併訊息為 v0.12.2 | `sdxl_train_network.py`、資料 TOML、caption、儲存介面 |
| `huggingface/diffusers` | `48cdbaef5ee3d718aaee392b44f2099ae511c4a5`，官方 commit 日期 2026-10-22 | `train_text_to_image_lora_sdxl.py` 對照 |
| 現有 ComfyUI | `15eb748b3ec5f8a0a2d470b7fb280e2d7579f916` | 未來產物載入時的鍵名／未載入警告邊界 |

版本來自本次官方 GitHub GET，記錄完整 SHA，而非把浮動分支當成重現版本。[sd-scripts commit](https://github.com/kohya-ss/sd-scripts/commit/11d8cedd0c67b93a10f8b2d75f43554f6f12c794)、[Diffusers commit](https://github.com/huggingface/diffusers/commit/48cdbaef5ee3d718aaee392b44f2099ae511c4a5)。

首選 sd-scripts 的工程理由是：現有基底以完整 SDXL `.safetensors` 保存，其載入程式直接辨識本機檔案，再分派至 SDXL checkpoint loader；不必先為本輪資料準備新增 Diffusers 模型轉換流程。這是介面選擇，**不是已實測 Animagine 或本機 GPU 可訓練的結論**。[載入分派](https://github.com/kohya-ss/sd-scripts/blob/11d8cedd0c67b93a10f8b2d75f43554f6f12c794/library/sdxl_train_util.py#L76-L114)、[safetensors 讀取與 UNet 建構](https://github.com/kohya-ss/sd-scripts/blob/11d8cedd0c67b93a10f8b2d75f43554f6f12c794/library/sdxl_model_util.py#L170-L212)。

## 兩個官方介面的差異

| 面向 | sd-scripts SDXL LoRA | Diffusers SDXL text-to-image LoRA 範例 |
| --- | --- | --- |
| 基底輸入 | `pretrained_model_name_or_path` 是本機檔案時，使用完整 SDXL checkpoint 載入分支；否則走 Diffusers pipeline | 相同參數名稱下，範例逐一以 `from_pretrained(..., subfolder=...)` 讀 scheduler、雙文字編碼器、VAE、UNet；不能直接把單檔路徑視為等價輸入 |
| 圖片與 caption | `dataset_config` 指向 TOML；目錄型 subset 讀同 stem caption | `train_data_dir` 是 ImageFolder，caption 來自 `metadata.jsonl`／指定 caption 欄位；不是直接沿用 `.txt` sidecar 的同一介面 |
| 更新範圍 | `network_module=networks.lora` 加 `network_train_unet_only` 可表達首輪 UNet LoRA，避免套用文字編碼器 LoRA | 範例凍結基底並加入 LoRA；是否訓練文字編碼器另由其參數控制，不能直接套用 sd-scripts flag |
| 輸出 | `save_model_as=safetensors` 與 `networks.lora.save_weights` 有明確安全格式儲存分支 | 呼叫 `StableDiffusionXLPipeline.save_lora_weights`，屬其 pipeline 格式介面 |

基底與資料差異由兩邊原碼確認：[sd-scripts 基底](https://github.com/kohya-ss/sd-scripts/blob/11d8cedd0c67b93a10f8b2d75f43554f6f12c794/library/sdxl_train_util.py#L76-L114)、[dataset_config 載入](https://github.com/kohya-ss/sd-scripts/blob/11d8cedd0c67b93a10f8b2d75f43554f6f12c794/train_network.py#L924-L965)、[Diffusers 模型載入](https://github.com/huggingface/diffusers/blob/48cdbaef5ee3d718aaee392b44f2099ae511c4a5/examples/text_to_image/train_text_to_image_lora_sdxl.py#L610-L658)、[Diffusers caption 參數](https://github.com/huggingface/diffusers/blob/48cdbaef5ee3d718aaee392b44f2099ae511c4a5/examples/text_to_image/train_text_to_image_lora_sdxl.py#L230-L247)。

sd-scripts 的 UNet-only 開關會影響 `train_text_encoder` 與 `network.apply_to`；`save_model_as` 預設亦是 safetensors，但出口仍應明確記錄，不依賴預設。[UNet-only flag](https://github.com/kohya-ss/sd-scripts/blob/11d8cedd0c67b93a10f8b2d75f43554f6f12c794/train_network.py#L1945-L1950)、[是否訓練文字編碼器](https://github.com/kohya-ss/sd-scripts/blob/11d8cedd0c67b93a10f8b2d75f43554f6f12c794/train_network.py#L210-L216)、[套用網路](https://github.com/kohya-ss/sd-scripts/blob/11d8cedd0c67b93a10f8b2d75f43554f6f12c794/train_network.py#L1115-L1118)、[儲存格式參數](https://github.com/kohya-ss/sd-scripts/blob/11d8cedd0c67b93a10f8b2d75f43554f6f12c794/train_network.py#L1891-L1897)、[safetensors 寫入](https://github.com/kohya-ss/sd-scripts/blob/11d8cedd0c67b93a10f8b2d75f43554f6f12c794/networks/lora.py#L1255-L1280)、[Diffusers 輸出](https://github.com/huggingface/diffusers/blob/48cdbaef5ee3d718aaee392b44f2099ae511c4a5/examples/text_to_image/train_text_to_image_lora_sdxl.py#L1276-L1291)。

## 已查證的 dataset TOML 結構

下例是**由官方 schema 與原碼確認的最小出口結構**，不是已用 trainer 跑過的訓練配置。`image_dir` 必須替換成實際匯出包中該路徑的絕對 `train` 目錄；不要填整個作者原圖資料夾。1024、batch 1、bucket 與 repeats 是可追溯的資料出口候選設定，仍需 T03 決定其 VRAM、裁切與訓練適合度。

```toml
[general]
caption_extension = ".txt"
shuffle_caption = false
keep_tokens = 0

[[datasets]]
resolution = [1024, 1024]
batch_size = 1
enable_bucket = true
bucket_no_upscale = true
bucket_reso_steps = 64
validation_split = 0.0

[[datasets.subsets]]
image_dir = "C:/path/to/export/train"
num_repeats = 1
```

| 欄位與層級 | 查核結果與出口約束 |
| --- | --- |
| `[general]` 的 `caption_extension`、`shuffle_caption`、`keep_tokens` | 三者均可向下繼承；subset、dataset 的同名設定優先。明確輸出 `.txt`，因目錄型 subset 的程式預設其實是 `.caption` |
| `[[datasets]]` 的 `resolution` | 接受整數或二維整數尺寸；本專案明確輸出二維陣列 |
| `batch_size`、`enable_bucket`、`bucket_no_upscale`、`bucket_reso_steps` | 屬 dataset 層級的有效欄位；SDXL 額外檢查 bucket 步幅可被 32 整除，64 符合此項結構條件 |
| `validation_split` | 是有效 dataset 欄位；本出口明確設 `0.0`，保留本專案已審查的固定分組，不再隨機切一次 |
| `[[datasets.subsets]]` 的 `image_dir`、`num_repeats` | `image_dir` 必填，圖片直接放於此目錄；重複次數明確填 1。不要靠 `5_character` 這類目錄名稱推測 repeats 或 class tokens |

依據：[官方配置範例與繼承](https://github.com/kohya-ss/sd-scripts/blob/11d8cedd0c67b93a10f8b2d75f43554f6f12c794/docs/config_README-en.md#L23-L91)、[subset 預設](https://github.com/kohya-ss/sd-scripts/blob/11d8cedd0c67b93a10f8b2d75f43554f6f12c794/library/config_util.py#L56-L90)、[實際 schema](https://github.com/kohya-ss/sd-scripts/blob/11d8cedd0c67b93a10f8b2d75f43554f6f12c794/library/config_util.py#L188-L255)、[原碼繼承順序](https://github.com/kohya-ss/sd-scripts/blob/11d8cedd0c67b93a10f8b2d75f43554f6f12c794/library/config_util.py#L430-L458)、[目錄與 repeats 說明](https://github.com/kohya-ss/sd-scripts/blob/11d8cedd0c67b93a10f8b2d75f43554f6f12c794/docs/config_README-en.md#L187-L202)、[SDXL bucket 檢查](https://github.com/kohya-ss/sd-scripts/blob/11d8cedd0c67b93a10f8b2d75f43554f6f12c794/sdxl_train_network.py#L30-L48)。

這是 dataset TOML，**不能單獨啟動完整訓練**。learning rate、optimizer、rank／alpha、steps、precision、checkpoint 與 run 輸出位置未在這裡假裝選定；未來必須和資料版本、基底 hash、工具 SHA 一起凍結。畫風與角色各產生獨立的資料目錄與 TOML，不能因同作者而混成一個角色 subset。

## Caption 的實際讀取規則與專案限制

固定版本的 `read_caption` 優先找同 stem 檔案，例如 `sample.png` 對應 `sample.txt`，以 UTF-8 讀取；未開 wildcard／multiline 時只用第一行並去除首尾空白。它另有舊人臉裁切檔名的 fallback，因此本專案應使用無歧義的穩定檔名，不依賴此 fallback。[實際 caption reader](https://github.com/kohya-ss/sd-scripts/blob/11d8cedd0c67b93a10f8b2d75f43554f6f12c794/library/dreambooth_dataset.py#L30-L65)。

「缺檔」、「零 bytes 檔」和「空白第一行」在 trainer 並不等價：零 bytes 檔觸發 assertion；空白第一行會變成空字串；缺檔可使用 `class_tokens`，若兩者都沒有，這版實碼會警告後沿用空 caption。官方配置文件卻將最後一種情況寫成錯誤，故此處以所固定版本的執行原碼為準，保留差異。[缺檔分支](https://github.com/kohya-ss/sd-scripts/blob/11d8cedd0c67b93a10f8b2d75f43554f6f12c794/library/dreambooth_dataset.py#L239-L270)、[文件中的 class_tokens 說明](https://github.com/kohya-ss/sd-scripts/blob/11d8cedd0c67b93a10f8b2d75f43554f6f12c794/docs/config_README-en.md#L200-L202)。

**本專案出口採較嚴格且明確的規則**：每張訓練圖必須有已審查、非空白的單行 UTF-8 caption；拒絕缺檔、空檔、空白及多行內容，不設定 `class_tokens` 代替遺漏標註。caption 應區分角色身份、可改變的衣著／姿勢／背景與畫風 trigger；trigger 只當候選標籤，不宣稱是模型已有的特殊 token。此規則屬本專案資料契約，不能描述為 trainer 的全部原生限制。

## 分割與評估曝光：trainer 不會讀懂專案 manifest

這版 sd-scripts **確實有原生 validation split**：config 接受 `validation_split`／`validation_seed`，目錄型 DreamBooth dataset 依 subset 中的檔案清單切分；`split_train_val` 以隨機洗牌及比例決定 train／validation。[schema 與 dataset 建立](https://github.com/kohya-ss/sd-scripts/blob/11d8cedd0c67b93a10f8b2d75f43554f6f12c794/library/config_util.py#L484-L524)、[subset 切分](https://github.com/kohya-ss/sd-scripts/blob/11d8cedd0c67b93a10f8b2d75f43554f6f12c794/library/dreambooth_dataset.py#L211-L231)、[比例與隨機實作](https://github.com/kohya-ss/sd-scripts/blob/11d8cedd0c67b93a10f8b2d75f43554f6f12c794/library/dataset.py#L108-L144)。

上述介面沒有解析本專案 manifest 的重複／差分群組、固定用途或既有曝光紀錄，因此**不能推論它會自動尊重專案的 holdout**。本專案的決策是出口時先依已審查的 group／split 物理隔離，只讓 TOML 的 `image_dir` 指向 `train`；development、holdout、排除圖都不放入該目錄，且 `validation_split=0.0`。未來若需要訓練中的 loss validation，必須另設版本化契約；它也不能代替 T01 的人工畫風、角色與內容偏移比較。

固定版已有的 loss validation 不代表完全未曝光的最終評估。R02 看過的保留圖沿用曝光紀錄；若後續用於選型／調參，仍屬開發評估，不得標成盲測集。此項由本專案的 [T01 分割與提醒約定](requirements.md#圖片分割與提醒時點) 承接。

## T03 必須實測的環境與執行邊界

- **獨立訓練環境**：上游 Windows 範例另建 venv，列 Python 3.10；3.11／3.12 標記為未測。其範例安裝 Torch 2.6／CUDA 12.4，而 `requirements.txt` 未包含 Torch，要求依環境先選版本。因此現有推論用 Python 3.12、Torch／CUDA 能載入模型，不能作為 trainer 安裝或訓練保證，也不能直接往 ComfyUI venv 加套件。[Windows 安裝與 Python 範圍](https://github.com/kohya-ss/sd-scripts/blob/11d8cedd0c67b93a10f8b2d75f43554f6f12c794/README.md#L177-L215)、[Torch 依環境選擇](https://github.com/kohya-ss/sd-scripts/blob/11d8cedd0c67b93a10f8b2d75f43554f6f12c794/README.md#L236-L242)。
- **完整依賴鎖定**：本次固定 `requirements.txt` 包含 Accelerate 1.15、Transformers 5.17、Diffusers 0.40 與 safetensors 0.8 等，但部分依賴仍未固定版號。T03 必須保存實際解析結果、Python、Torch／torchvision、GPU 驅動與精度測試，不能僅保存 repo SHA 就稱整個環境可重現。[固定 requirements](https://github.com/kohya-ss/sd-scripts/blob/11d8cedd0c67b93a10f8b2d75f43554f6f12c794/requirements.txt)。
- **Tokenizer 來源**：讀本機完整 checkpoint 仍會另外載入兩個指定模型的 tokenizer；不能因此宣稱首次啟動完全離線。T03 要固定來源修訂、快取與 hash，查清是否發生網路讀取及遺失快取的行為。[SDXL tokenizer 來源與載入](https://github.com/kohya-ss/sd-scripts/blob/11d8cedd0c67b93a10f8b2d75f43554f6f12c794/library/strategy_sdxl.py#L19-L27)。
- **VRAM、快取與 caption 相容**：上游建議混合精度與快取以減少 SDXL 記憶體用量，並不保證本機 12 GiB 一定足夠。若開啟文字編碼器輸出快取，程式要求 UNet-only，且拒絕會使 caption 變動的 shuffle／dropout 等設定；這也是出口先採 `shuffle_caption=false` 的理由，是否啟用快取仍由 T03 實測。[SDXL 記憶體選項](https://github.com/kohya-ss/sd-scripts/blob/11d8cedd0c67b93a10f8b2d75f43554f6f12c794/docs/sdxl_train_network.md#L185-L200)、[實際限制](https://github.com/kohya-ss/sd-scripts/blob/11d8cedd0c67b93a10f8b2d75f43554f6f12c794/sdxl_train_network.py#L35-L44)。
- **原圖與不可變資料包**：T03 不直接讓 trainer 改寫來源或已發版資料包；另建 run 工作副本，記錄與資料包的 hash 關係及快取位置。GPU 與推論的協調、明確啟動／停止、未知結果、失敗恢復、資源釋放與足量磁碟，都仍待 T03 實作與實測；本次不提供會直接開始訓練的命令。

## T04 的產物相容與品質關卡

`.safetensors` 只指出容器格式，不能直接保證每個鍵都會被目前 ComfyUI 載入。sd-scripts LoRA 有 `lora_unet`／雙文字編碼器前綴；現有 ComfyUI 會建立鍵名對應並對未載入鍵發出警告，因此 T04 要用實際新產物、固定基底與既有流程查核完整載入，再做保存／還原與內容比較。[sd-scripts 前綴](https://github.com/kohya-ss/sd-scripts/blob/11d8cedd0c67b93a10f8b2d75f43554f6f12c794/networks/lora.py#L866-L875)、[ComfyUI 未載入鍵處理](https://github.com/Comfy-Org/ComfyUI/blob/15eb748b3ec5f8a0a2d470b7fb280e2d7579f916/comfy/lora.py#L34-L94)、[UNet 鍵名對應](https://github.com/Comfy-Org/ComfyUI/blob/15eb748b3ec5f8a0a2d470b7fb280e2d7579f916/comfy/lora.py#L178-L205)。

畫風與角色各自保存不同產物 ID、完整工具／資料／基底版本及輸出 hash；不能因副檔名、成功儲存或單張外觀相近就標為通過。技術載入、提示服從、角色延續、畫風與構圖依 [T01 的固定驗收](requirements.md#可追溯與可執行的驗收方案) 分開記錄，保留全部失敗。T02 的完成範圍止於可審查的資料與工具介面；T03／T04 仍是未完成的開發與實測項目。
