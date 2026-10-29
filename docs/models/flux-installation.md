# F01：固定 FLUX 元件安裝與驗檔

安裝、完整驗檔與[快速唯讀預檢／來源選型歷史](#source-selection)集中於本文件。當前操作先依下方 F01 指令；來源選型段落保留 2026-10-04／05 當時未取得權重與未驗 GPU 的事實，後續 F02–F04 證據另按原日期引用。

更新日期：2026-10-25。使用平台 `.venv` 執行下列命令；下載工具不載入 Torch、不啟動引擎或生成。F01 已在本機取得固定來源並安裝、完整驗證四份權重，見 [實際證據](../validation/flux-installation-20261025.md)。不能將工具測試通過當成另一台主機權重已安裝，也不等於 GPU 可生成。

## 先確認硬體與存取

本輪實際檢查為 RTX 3060 12 GiB、系統 RAM 約 63.94 GiB、磁碟約 394 GiB 可用；查詢時間的 RAM 可用約 33 GiB。這只是該次本機快照，不是部署門檻。固定四份檔案合計 27.49 GiB，下載時同一磁碟區另預留 2 GiB。原始 BF16 主模型不能完整常駐此卡 VRAM；F02 另測 FP8／卸載與品質，尚無 GPU 通過結論。依據與 4080 提醒見 [前置判斷](flux-rtx3060-planning.md)。

1. 用自己的帳號開啟 [BFL FLUX.1-schnell](https://huggingface.co/black-forest-labs/FLUX.1-schnell)，自行閱讀並完成頁面要求的存取條件。網頁能登入不代表本機程式已登入，也不代表固定權重已獲准存取。
2. 在專案目錄的 PowerShell 執行官方 CLI：

```powershell
.\runtime\ComfyUI\.venv\Scripts\hf.exe auth login
```

此命令使用目前 ComfyUI 環境已有的官方 `hf`。新機若尚無 CLI，先按 [Hugging Face 官方 CLI 安裝說明](https://huggingface.co/docs/huggingface_hub/guides/cli)安裝，再執行 `hf auth login`；不要複製舊機的 Python 虛擬環境。由使用者在本機完成登入，平台不代為接受存取條件。不要把 token 放到聊天、命令參數、`.env`、manifest 或 Git。

工具依官方 [環境變數契約](https://huggingface.co/docs/huggingface_hub/package_reference/environment_variables)讀取 `HF_TOKEN`，否則讀取 `HF_TOKEN_PATH`／`HF_HOME/token`；未另設時是使用者的 `.cache/huggingface/token`，亦尊重 `XDG_CACHE_HOME`。只讀取現有登入資料，不保存新憑證；報告僅含 `credential_available` 布林值。token 只附於固定 BFL HTTPS 來源，公開編碼器、CDN 及其他重新導向不會收到它；HTTP 降級會停止。

## 檢查、下載與完整驗檔

```powershell
# HEAD 檢查四個來源、檔案大小／partial／安裝鎖與整體磁碟預算。
.\.venv\Scripts\python.exe -m scripts.install_flux check

# 四份必要來源皆通過後，才開始寫入／續傳；最後逐份完整驗證 SHA256。
.\.venv\Scripts\python.exe -m scripts.install_flux install

# 離線重新讀取四份完整檔案核對大小及 SHA256，不讀取憑證或連網。
.\.venv\Scripts\python.exe -m scripts.install_flux verify
```

`check` 不建立目錄、不雜湊權重或下載檔案內容；同大小正式檔為 `present_unverified`。`ready_for_install=true` 只是本次來源／磁碟／檔案預檢可繼續，不能當成已安裝。`verify` 只有四份檔案都符合固定大小及完整 SHA256，才回報 `current_files_verified=true`；仍不代表引擎讀到檔案或 GPU 能生成。CLI 的退出碼 0 表示該命令條件通過、2 表示 check／verify 有缺項、1 表示無法檢查或安裝錯誤，使用者中止為 130。

`install` 先完整驗證已有正式檔，再檢查所有仍需安裝的固定來源及整體磁碟容量；任一來源拒絕時，不先下載其他公開編碼器。依序下載，使用現有有限重試、Range 續傳、2 GiB 餘量、獨占元件安裝鎖及完整 SHA256 後才發布的機制。401／403 不自動重試；連線中斷保留 `.part`，重新執行同命令可續傳。已有四份正確檔案時可離線沿用，不要求再次下載。

正式檔案大小／hash 不符時拒絕覆寫。下載內容 hash 不符時保留 partial，不發布；確認後可針對該元件明確重新下載，例如：

```powershell
.\.venv\Scripts\python.exe -m scripts.install_flux install --restart-role diffusion_model
```

角色限 `diffusion_model`、`vae`、`clip_l`、`t5xxl`，可重複指定。只清空所選元件的 partial；正式檔不覆寫，其他元件 partial 不清除。安裝鎖存在時，先確認原安裝程序是否仍執行，不要直接刪除使用中的鎖。中斷後重新執行會重查已完成檔案，之前已驗證的元件保留，不提供四份一起回滾或自動清理。

## 固定來源與產物

來源、完整 revision、bytes 及 SHA256 沿用 [固定 manifest](../../models/flux1-schnell-plan.json)，並由程式固定登記再次核對；不接受任意 URL、模型或目的路徑。主模型與 VAE 使用 BFL 固定修訂；CLIP-L／T5 使用 ComfyUI 範例引用的固定整合修訂。

| 角色 | `runtime/ComfyUI/models/` 下的正式檔 |
| --- | --- |
| diffusion_model | `diffusion_models/flux1-schnell.safetensors` |
| vae | `vae/ae.safetensors` |
| clip_l | `text_encoders/clip_l.safetensors` |
| t5xxl | `text_encoders/t5xxl_fp8_e4m3fn_scaled.safetensors` |

新安裝檔旁保存 `.provenance.json`，記錄來源、修訂、大小、SHA256、當次完整驗證與逐元件授權查核狀態，沒有憑證或 CDN 簽名 URL。側錄不能替代重新驗檔；`verify` 不靠側錄認定正確。F01 當時的 `terms_verified=false` 保留為歷史；後續新安裝依 [F02 查核](flux-component-licenses.md)記錄 BFL 已讀全文、編碼器轉檔鏈未完整核實的差別，不回填既有側錄。

模型庫的「FLUX.1 接入準備」及 `scripts.flux_preflight` 保持快速唯讀，不讀登入資料、不連網、不雜湊大型檔案；其 `download_supported=false` 表示該 API 沒有下載動作，不否定這份獨立 CLI。API 的 `current_files_verified=false` 仍表示當次查詢沒有做完整 hash，不能因旁邊有舊側錄就變成 true。

## 目前實測與下一步

2026-10-25 初次 `check`：未偵測 CLI 憑證，BFL 主模型／VAE HTTP 401，編碼器 HTTP 200；沒有先下載公開編碼器。使用者完成官方 CLI 登入後，四份固定來源 HEAD 均 HTTP 200，整體動態磁碟預算足夠。實際 `install` 已下載並驗證四份共 29,521,303,916 bytes，全部發布為正式檔案，沒有 GPU 載入或生成。

F01 當時 16 項合成資料回歸涵蓋四元件下載／離線驗檔、完整來源門檻、跨站 token 隔離、HTTP 降級拒絕、完整 hash／拒絕覆寫、有限續傳、分角色重下、整體容量／partial／鎖及 CLI 不讀憑證的離線驗檔。合成測試不下載真實模型、不使用 GPU；真實來源與驗檔另列實際證據。F01 已先 commit／push，後續 [F02 實測](../validation/flux-runtime-20261025.md)與條款缺口分開記錄。

<a id="source-selection"></a>

## 固定來源、快速預檢與來源選型歷史

目前狀態（2026-10-25）：已另完成 [F02 精度／資源觀察](flux-runtime-observation.md)、[F03 平台保存／受控 OOM](flux-workflow.md#generation-acceptance)及 [F04 固定 PVC LoRA／VAE 圖生圖](flux-extensions.md)。通過範圍限文件列出的 RTX 3060／64 GiB RAM、512 配置。此頁下方是來源選型歷史；快速預檢 API 的 false 欄位只表示該端點不下載、不驗檔、不生成，不否定專用工具的歷史實測。

2026-10-25：新增獨立 [F01 安裝／驗檔 CLI](flux-installation.md)，使用官方本機登入與固定四元件來源，[四份實際安裝與完整 hash](../validation/flux-installation-20261025.md)已通過。以下是早期來源選型紀錄，快速預檢仍保持不連網／不驗 hash；CLI 工具測試通過不等於另一台主機已取得權重。

2026-10-05 更新：分離元件庫及專用提交／草稿／JSON API 已完成，見 [流程說明](flux-workflow.md)。以下保留來源選型階段紀錄；預檢的 generation_supported=false 表示尚未確認本機權重可生成，不表示不存在專用 API。安裝與 GPU 出圖仍未驗證。

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
