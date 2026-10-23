# SDXL 畫風／角色外觀參考 v1

`checkpoint-ipadapter-reference-v1` 使用一張素材、SDXL Plus ViT-H adapter 與獨立 ViT-H/14 影像編碼器。這是**推論時參考**，不訓練 LoRA、不修改模型權重、不將素材庫全部輸入。兩種模式分開選擇：畫風使用 `style transfer`，角色外觀使用 `linear`；角色模式不是 FaceID，也不保證身份鎖定。

本輪收到的 22 檔／20 個不同內容、實際選用的兩張圖片、6 張保留評估圖及未訓練備註見 [圖片用途紀錄](../validation/reference-inputs-20261023.md)。單張流程的實機比較及失敗見 [R02 驗收](../validation/reference-adapter-20261023.md)。

## 固定來源與安裝

| 元件 | 固定版本 | 本機類別／登記 |
| --- | --- | --- |
| [IP-Adapter Plus SDXL ViT-H](https://huggingface.co/h94/IP-Adapter/blob/018e402774aeeddd60609b4ecdb7e298259dc729/README.md) | `018e402774aeeddd60609b4ecdb7e298259dc729`；847,517,512 bytes | `models/ipadapter`；架構 `sdxl`、家族 `sdxl-plus-vit-h` |
| [CLIP Vision ViT-H/14](https://huggingface.co/h94/IP-Adapter/tree/018e402774aeeddd60609b4ecdb7e298259dc729/models/image_encoder) | 同一修訂；2,528,373,448 bytes | `models/clip_vision`；架構 `other`、家族 `clip-vit-h-14` |
| [ComfyUI_IPAdapter_plus](https://github.com/cubiq/ComfyUI_IPAdapter_plus/tree/a0f451a5113cf9becb0847b92884cb10cbdec0ef) | `a0f451a5113cf9becb0847b92884cb10cbdec0ef` | `custom_nodes/ComfyUI_IPAdapter_plus`；上游 GPL-3.0 |

影像編碼器取自 `models/image_encoder`，不是 SDXL 目錄內的 bigG，也不是 checkpoint 的文字 CLIP。兩份權重的大小、SHA256、固定下載位置及來源標籤保存在 [adapter manifest](../../models/ip-adapter-plus-sdxl-vit-h.json)、[ViT-H manifest](../../models/clip-vision-vit-h.json)；節點逐檔 Git blob SHA1 見 [節點 manifest](../../models/ipadapter-nodes.json)。權重模型卡標記 Apache-2.0，依賴適用條件未完整核對，`terms_verified=false`；節點原碼授權與權重／參考圖條件分開記錄。

```powershell
.\.venv\Scripts\python.exe -m scripts.install_model ip-adapter-plus-sdxl-vit-h --check
.\.venv\Scripts\python.exe -m scripts.install_model ip-adapter-plus-sdxl-vit-h
.\.venv\Scripts\python.exe -m scripts.install_model clip-vision-vit-h
.\.venv\Scripts\python.exe -m scripts.install_ipadapter_nodes
.\.venv\Scripts\python.exe -m scripts.install_ipadapter_nodes --check
```

下載器只接受固定來源並核對完整大小／SHA256，拒絕覆蓋不同內容的正式權重。節點安裝器只下載已檢閱的五份 Python、README、pyproject 與 LICENSE，核對每份 Git blob，保留原碼；不執行上游安裝腳本、不安裝任意套件、不自動升級 ComfyUI。既有節點內容不同時拒絕覆蓋。`--check` 只讀，不下載或寫檔。

安裝後明確重啟你管理的 ComfyUI。若使用 `--disable-all-custom-nodes`，須把 `ComfyUI_IPAdapter_plus` 加入明確 whitelist；平台不自動替使用者重啟引擎或開啟其他節點。本輪 ComfyUI 0.34.0 既有環境已包含 torch／torchvision／einops，沒有為此安裝 FaceID 的 insightface。其他環境需先核對相依與節點介面。

## 工作台操作

1. 在「參考素材」上傳一張 PNG／JPEG／WebP（20 MiB、1600 萬像素以內）；用途標籤只供管理。
2. 到「畫風／角色參考」，選擇原引擎的 SDXL checkpoint；checkpoint 必須在模型庫明確登記架構。
3. 展開「同步與登記參考元件」，明確同步 adapter／編碼器清單，再依上表登記家族、架構、版本、hash、大小、來源及授權。檔名不會自動推定家族，人工登記不等於驗檔。
4. 選「畫風參考」或「角色外觀參考」、一張素材、adapter 及編碼器；設定權重與作用起訖、提示詞、精確 seed 及輸出參數，再明確按「生成圖片」。
5. 終態任務可載入原設定；作品庫可保存原圖、查看原元件／素材快照、下載完整流程，或載入回此專用工作台。載入不自動生成，取代表單前會提示未提交變更。

權重範圍 `0–2`，預設 `0.6` 僅為起始值；`0` 是同流程不施加參考作用的對照。起始／結束在 `0–1` 且起始小於結束。增強權重可能把髮色、服裝、姿勢、背景或其他內容帶入，不代表更準確。首版單張輸出、空 latent、`denoise=1`、固定 `fit` 補白，不組合 LoRA、多圖、FaceID、Canny 或局部編輯。

## 前處理、來源與還原

- 原素材先經既有匯入正規化；其原始內容 hash、EXIF 校正、Pillow 版本與正規化 PNG hash 分開保存。平台不保存原始檔，需保留自己的原圖。
- 生成前重新讀取本機 PNG 並核對大小、SHA256、尺寸、封存狀態；透明合白底、LANCZOS 等比縮放、置中補白為 **224 × 224 RGB PNG**。輸出畫布尺寸獨立，避免參考尺寸隨輸出寬高變動。
- `generation_preprocessing` 固定 `ipadapter-square-input` v1，保存 Pillow 版本、補白／縮放、處理後大小及 hash；`adapter_preprocessing` 保存模式、weight_type、concat、V only、224 及原引擎編碼方式。作用權重、起訖在完整 `reference_settings` 凍結。
- 原引擎節點依 `comfy.clip_vision.clip_preprocess` 編碼方圖；API 未回報節點獨立版本時保存 `node_version=null`，不把文件的已測修訂冒充當前引擎證明。驗收紀錄另保存本機實際固定原碼版本與 hash。
- 流程為 `LoadImage → IPAdapterAdvanced`，同時接入 `IPAdapterModelLoader` 與 `CLIPVisionLoader`，輸出 MODEL 接到 KSampler；參考圖不編碼成初始 latent。checkpoint、提示詞、取樣、解碼及 SaveImage 仍是完整 owned template。
- 建立 UUID 時在 SQLite 交易內核對兩元件、checkpoint 與素材；預檢後、上傳後、POST 前再次核對登記。即時節點缺失、型別／選項／範圍改變、來源改動均不得變成部分生成。
- 處理後圖保存於 `DATA/job_inputs/{uuid}.png`，只上傳原引擎的 UUID 專屬位置且不覆寫。上傳回執確認路徑，不宣稱驗證遠端內容。
- 同 UUID 先返回原任務，再檢查目前引擎、檔案或登記；不同模式／權重／來源衝突回 409。未知結果保留原 pending、原 UUID、完整 body、`_atelier_reference_workflow_id` 與端點；未知版本不改為新流程、不自動重送。
- 還原核對整張流程、唯一來源、前處理及兩元件快照；無法完整還原時拒絕部分載入。引擎離線、元件改登記或消失時保留原設定並提示，不從新清單回填歷史。

## API 與支援邊界

| API | 用途 |
| --- | --- |
| `GET /api/reference/workflow` | 模式、版本與前處理規格；已測節點修訂不是即時驗證 |
| `GET /api/reference-components` | 離線可讀的原引擎元件清單 |
| `POST /api/reference-components/sync` | `{comfy_url}`；兩份即時清單須一起成功，失敗保留上次資料 |
| `PUT /api/reference-components/metadata` | `{engine_url, role, name, family, ...ModelMetadata}`；角色 `ipadapter`／`clip_vision` |
| `POST /api/reference/generate` | 嚴格參考設定與持久 UUID；不接受 pending marker、一般 experiment 或未知欄位 |
| `GET /api/library/jobs?workflow=reference` | 獨立分頁清單，不混入一般 checkpoint 任務 |
| `GET /api/jobs/{id}/reference-image` | 原任務已保存的 224 方圖 |
| `GET /api/jobs/{id}/creation-settings` | 終態原設定；作品使用對應 artwork 端點 |
| `GET /api/reference-workflows/support?family=reference` | 草稿／交換／比較尚未開放，完整設定還原及 workflow 下載可用 |

完整 request 由一般 checkpoint 取樣欄位加上 `image_asset_id`、僅該 ID 的 `reference_ids`、`reference_mode`、`ipadapter_name`、`clip_vision_name`、`reference_weight`、`reference_start`、`reference_end` 構成；`workflow_mode=text2image`、`reference_resize=fit`、`loras=[]`、`denoise=1`。`seed` 一律十進位字串，完整 workflow 下載直接保留後端原 JSON，不經瀏覽器重新 stringify。

一般草稿、設定交換及比較方案會明確拒絕此 ID、專用欄位與 marker，避免漏存模式、來源或元件。新增這個流程沒有開放自動批次、重新訓練或自動評分；T01／T02 另處理訓練需求及資料契約。

## 單組 GPU 驗收

`scripts.verify_reference_generation` 每次只建立一個 UUID、固定 Animagine／adapter／編碼器版本、兩組 seed 與三個題材；來源 ID 與正規化 SHA256 必須明確指定。保留原圖、完整 workflow、原來源／元件／環境快照與還原證據。報告檔存在時拒絕再生成；`--verify-report` 只讀原任務及作品，不同步、不讀權重、不生成。

```powershell
.\.venv\Scripts\python.exe -m scripts.verify_reference_generation --source-id <asset-uuid> --source-sha256 <normalized-png-sha256> --mode character --weight 0.6 --scene portrait --seed 18446744073709551615 --platform http://127.0.0.1:8000 --expected-engine http://127.0.0.1:8188 --report runtime/my-reference-check.json
# 同一完整命令加 --verify-report，核對原 UUID；不建立另一個任務。
```
