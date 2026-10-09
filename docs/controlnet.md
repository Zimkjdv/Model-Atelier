# Canny 結構參考

固定 `checkpoint-canny-controlnet-v1` 使用一張素材、ComfyUI 原生 Canny 與同架構的 ControlNet。支援明確登記的 SD 1.x／SDXL checkpoint，以及最多四個有序 LoRA。這是結構條件，不是畫風或角色鎖定；後端與專用工作台已整合，Pony／Animagine 的固定 RTX 3060 驗收及離線重啟核對已完成，見 [實測與品質觀察](validation/checkpoint-canny-rtx3060.md)。

## 模型登記

- `GET /api/controlnets`：目前引擎的控制模型清單與登記資料。
- `POST /api/controlnets/sync`：JSON `{ "engine_url": "http://127.0.0.1:8188" }`，讀取原生 ControlNetLoader。失敗保留歷史清單並標示錯誤；同步不載入權重。
- `PUT /api/controlnets/metadata`：明確的 engine_url、name，以及版本、來源、architecture、kind、SHA256、bytes 大小、授權與備註。架構及類型不依檔名推測，未填版本顯示未知。kind 可登記 unknown／canny／depth／pose／other，目前只有 canny 可提交。

登記依引擎隔離，移除的模型保留版本資料並標示未列出。成功同步、kind=canny，及與 checkpoint 相同的 sd1／sdxl 架構為此流程的必要條件；登記不是實際權重驗檔或載入證明。

## 提交與保存

`POST /api/control/generate` 接收完整 checkpoint 設定與 request_id。固定 workflow_mode=text2image、denoise=1、單張；image_asset_id 與 reference_ids 的唯一 ID 相同。附加欄位：control_net_name、control_strength（大於 0 至 10）、control_start／control_end（0–1 且 start < end）、canny_low／canny_high（0.01–0.99 且 low < high）。

來源先驗檔，再以 fit 等比補白或 stretch 拉伸至輸出尺寸。模型從 EmptyLatentImage 生成，Canny 只提供正／負條件，沒有以來源圖 latent 作圖生圖。控制範圍用原生節點的 start_percent／end_percent，不能解讀成毫秒。Canny 閾值為原生 Kornia 的浮點參數，不能直接當成 OpenCV 的 0–255 閾值。

基礎十一個節點，已啟用 LoRA 各增加一個。凍結完整 workflow JSON、原始素材與處理後 PNG 大小／雜湊、縮放方法、原生 Canny 參數、checkpoint／ControlNet／LoRA 版本及提交環境。Canny 在原引擎執行，個別節點版本無法取得時保持未知；v1 只保存縮放後來源 PNG，不回填邊緣圖；v2 另保存同次原生邊緣輸出。`GET /api/jobs/{id}/reference-image` 提供該來源。

## 保護與還原

交易內確認模型登記及原子保存素材引用；提交前嚴格核對 LoadImage、Canny、ControlNetLoader、ControlNetApplyAdvanced 的介面、浮點範圍與原引擎即時模型清單。上傳前及 /prompt 前再檢查登記快照；變更則停止。輸入使用平台 UUID 子目錄，核對不可覆寫的上傳回條。缺模型、離線、缺節點等錯誤明確保存，不送出無效流程。

相同 UUID 與完整設定先恢復舊任務，不重新探查素材、模型或引擎；不同設定為 409。/prompt 回應遺失保留 unknown，不能自動重送。一般 /api/generate 拒絕控制參數，避免悄悄退回普通流程。

任務／作品的 creation-settings 可離線完整還原控制模型、參數、來源與版本。節點、角色、前處理或控制快照不一致時拒絕部分載入。清單或版本改變只提示，不改寫原設定。普通草稿、設定交換與比較方案尚未接入，不借用舊格式丟棄控制欄位。

依據：[ComfyUI 官方 ControlNet 文件](https://docs.comfy.org/tutorials/controlnet/controlnet)，以及本機固定 ComfyUI 0.34.0 原始碼。新增 12 項後端測試涵蓋登記隔離／競態、精確圖、上傳／離線／未知結果、原 UUID 恢復、有序 LoRA 及完整還原。完整後端 451 項（450 通過、1 項既有權限跳過）。

## 工作台操作

1. 模型庫的 ControlNet 區塊同步清單，明確登記版本、來源、canny 類型及基礎架構；不把 depth／pose 自動當成 Canny。
2. 在創作工作台切換「Canny 結構參考」，選擇 checkpoint、素材庫原圖與控制模型，更新原引擎取樣選項。清單錯誤、不同引擎／架構與未知類型會顯示原因。
3. 手動調整尺寸、fit／stretch、強度、作用起訖、浮點閾值、提示詞與精確 seed。預覽顯示原素材，沒有假稱已計算邊緣圖；固定空 latent／denoise 1。
4. 按生成後保存完整控制參數；待確認請求使用獨立 localStorage key，恢復不使用目前表單。任務／作品顯示控制模型與來源／前處理快照。
5. 已終止任務或作品載入完整設定會回到結構工作台；未保存內容需明確選擇是否取代。載入不生成、不換模型、不丟棄控制欄位。切換頁面保留表單，重新整理會清除未提交內容，尚無一般草稿／比較方案。

前端 `check:control` 驗證閾值／作用範圍、登記架構／類型／引擎、精確 seed、完整還原及原請求不可變；既有遮罩／比較檢查與 Vue 型別／建置通過。瀏覽器工具本輪仍因 Node kernel 啟動失敗，實際畫面操作／下載／窄視窗待驗收。

## 固定模型與驗收 CLI

安裝採公開 safetensors，限制來源修訂與本機 controlnet 目錄。--check 唯讀、不建立目錄；下載可續傳，保留 2 GiB 磁碟預留，發布前核對大小及完整 SHA256，既有不符檔案拒絕覆寫。

```powershell
.\.venv\Scripts\python.exe -m scripts.install_model controlnet-canny-sdxl-1.0-fp16 --check
.\.venv\Scripts\python.exe -m scripts.install_model controlnet-canny-sdxl-1.0-fp16
```

在模型庫同步並依 models/controlnet-canny-sdxl-1.0-fp16.json 明確登記 1.0 FP16／sdxl／canny、來源、大小與 hash。安裝器不修改平台偏好或自動登記；本輪正式資料不變。重新啟動 ComfyUI 可確認模型清單。

先保存原素材，執行一次固定模型驗收；報告必須不存在，先保存 UUID 再送唯一一次生成。若提交回應遺失，只查原任務，不再生成。

```powershell
.\.venv\Scripts\python.exe -m scripts.verify_control_generation --model pony-v6-xl --source-id <素材UUID> --report runtime/control-pony.json
```

另一次可使用 --model animagine-xl-4.0-opt。固定條件為 768²、20 steps、CFG 5.5、dpmpp_2m／karras、空 latent／denoise 1、seed 9007199254740993、無 LoRA、strength 0.5、作用 0–1、Canny 0.4／0.8，驗收提示為一般椅子；單次最多觀察 15 分鐘，不是品質推薦。

既有完整報告加 --verify-report，以相同模型／素材 ID／平台路徑僅 GET 核對保存紀錄與 PNG，不能補提交或匯入。非法 workflow、控制來源／hash／型別或完整參數會先拒絕，不覆寫原報告。權重在新生成前重新全檔驗證，離線報告核對不需載入或重讀權重。原生 Canny 節點版本保持未知，完整引擎版本另存在 runtime 快照。

## v2 實際邊緣輸出

`checkpoint-canny-controlnet-edge-v2`／`POST /api/control-edge/generate` 接收與 v1 完全相同的設定，追加 SaveImage 節點 16，直接連到本次 Canny 節點 13；最終作品仍為節點 7。沒有另開生成或更換前處理。十二個基礎節點，LoRA 另計。v1 的 UUID、流程與原設定保留，不能跨端點恢復 UUID。

- `GET /api/jobs/{id}/control-edge`：只讀保存狀態、原流程／參考／控制版本來源、PNG hash、bytes、尺寸與白色邊緣像素數；不連線引擎。未保存顯示 not_saved。
- `POST /api/jobs/{id}/control-edge`：使用已確認成功歷史的唯一節點 16 output，從原引擎 /view 明確匯入；不提交 /prompt、不重新計算。固定 UUID 目錄與檔名檢查，串流 32 MiB 限制，須為同尺寸 RGB 二值 PNG。空邊緣也是可保存的結果。
- `GET /api/jobs/{id}/control-edge/image`（可加 download=true）：僅本機 PNG，驗證 SHA256 與尺寸／像素快照；不可用時提示備份還原。
- `GET /api/artworks/{id}/control-edge`：檢查作品完整流程與原任務相符，再取得同份邊緣記錄；圖片使用回傳的 job_id 路徑。

作品匯入只接受 v2 的節點 7，不把條件圖變成作品。邊緣快照獨立保存於 data/control_edges 與 control_edge:<job_id>，不回寫原任務／作品。併發與重複匯入只留一份；已有圖片遺失／hash 改變或 orphan 檔案都拒絕覆寫／自動重抓。檔案及交易失敗只清理本次建立的檔案。停止平台後備份整個 data，才能同時保留證據。

這是已提交任務的實際條件圖，不是目前未提交表單的即時預覽；不能由來源圖重新計算後冒充舊任務輸出。第一項後端已完成 12 項新增測試；後端共 471 項測試通過（含 1 項既有 Windows skip），專用介面及兩 seed／兩強度 GPU 比較接續第二／三項。


## 任務與作品的邊緣圖介面

新的「Canny 結構參考」生成使用 v2。完成後，在任務卡片或作品預覽展開「查看原任務的 Canny 邊緣圖」只讀取本機狀態；尚未保存時，按「從原引擎保存邊緣圖」明確匯入同次輸出。保存後可離線預覽／下載，並顯示尺寸、PNG／流程 SHA256、保存時間、白色像素數與比例；這是量測，不是品質評分。缺檔或不符會提示備份還原，不自動補生成。舊 v1 顯示沒有同次邊緣輸出。

使用原有的 pending localStorage key。沒有流程標記的舊請求仍使用 v1 端點與精確原 body；新請求保存本機 `_atelier_control_workflow_id` 標記，送 v2 時移除標記，不傳入嚴格 API。未知標記會拒絕提交且保留 pending。還原 v1／v2 原設定後，手動生成會建立新的 v2 UUID。介面切換、來源更換及卸載會取消讀取並忽略過期回覆；圖片驗證失敗不沿用舊預覽。

Vue 型別／建置、Canny 請求遷移／來源檢查、既有遮罩與比較檢查通過。瀏覽器控制工具本輪無法啟動，實際點擊／窄視窗視覺驗收仍待完成；尚未宣稱通過瀏覽器操作驗收。
