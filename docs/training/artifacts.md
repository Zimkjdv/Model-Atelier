# T04 訓練產物回登與固定評估

完成的是本機 SDXL UNet LoRA 的回登與比較流程；作者畫風／角色品質仍待真實資料審查、試訓與人工驗收。2026-10-25 的 [技術驗收](../validation/training-artifacts-20261025.md)僅使用 T03 自製幾何圖片產物。網頁沿用現有 LoRA 模型庫、比較方案、作品並排與人工筆記，新增操作由 CLI 進行。

## 回登與追溯

`register` 只接受 T03 狀態 completed、程序／租約已釋放、最終完整狀態已達預算的 run。核對 run manifest、產物 receipt、完整最終 checkpoint 的 hash，以及真正 `.safetensors` 的大小／SHA；failed、stopped、未封存或被修改的結果不能回登。

通過後複製至受管理 ComfyUI 的 `models/loras/ma-trained-<UUID>.safetensors`。旁邊的 `.training.json` 與 `.sha256` 保存原 run／manifest、基底來源及 hash、資料版本／trigger／分割清單 hash、完整訓練設定、環境與 trainer 版本、續訓來源、權重識別及品質限制。原 run 和輸出保留，不覆寫；同 run 且識別完整相同的明確重做可返回原登記。中斷留下的未封存檔案會拒絕覆寫，需先人工檢查，不能當作成功。

`publish` 先重驗實際安裝權重，再透過既有 LoRA 同步／metadata API 回登到目前平台。僅支援本專案受管理的 `http://127.0.0.1:8188`；不把本機檔案假定為遠端引擎上的模型。版本使用完整 run UUID，備註包含資料／基底／trainer／manifest hash、trigger 與來源封存檔名。同步缺失、同名 hash 衝突、原引擎變更或 API 失敗會停止，不提交生成、不重送不明寫入結果；再次明確操作會先查回目前登記。

模型庫既有 `origin: user_registered` 契約保留，並不新增自稱可信的來源類型。技術產物備註標示 `TECHNICAL TEST ONLY`；其他新產物標示未評估。來源封存檔不代表授權審核，產物條款保持未審核，仍須保留基底與資料來源限制。平台登記之後若修改實際權重，舊作品快照仍是歷史識別，不能代替再次核對檔案。

## 操作

先完成 [T03 run](runtime.md)，啟動受管理 ComfyUI 與平台；保存 prepare 返回的 UUID。

```powershell
$atelierRunId = 'YOUR-COMPLETED-RUN-UUID'
.\.venv\Scripts\python.exe -m scripts.training_artifact register --run-id $atelierRunId
.\.venv\Scripts\python.exe -m scripts.training_artifact publish --run-id $atelierRunId
# 確認模型庫的原基底已登記固定版本、SDXL、實際大小與 SHA。
.\.venv\Scripts\python.exe -m scripts.training_artifact evaluation --run-id $atelierRunId --output runtime/training/my-evaluation-v1
# 明確保存六份原生方案，各含兩個 seed；沒有批次生成。
.\.venv\Scripts\python.exe -m scripts.training_artifact save-plans --output runtime/training/my-evaluation-v1
```

`--platform` 可指定另一個 loopback 平台埠；產物仍限定受管理引擎。CLI 不開放遠端平台。模型庫同步完成後可看到新版本、權重 hash 與來源備註；比較頁可載入保存的方案，再逐組明確生成。不要編輯 `evaluation.json`：`evaluation.sha256` 錨定原內容，修改會拒絕保存方案。同一份凍結方案保存中斷後，可明確使用原 request_id 查回／補齊，不產生重複方案或生成任務。

## 固定比較與人工判斷

比較先核對原基底與候選在平台的版本／架構／大小／hash，並重驗本機候選檔案。沿用 [T01 規則](requirements.md)：畫風用動漫 v1 的肖像、全身、車站三題材；角色用固定 R02 的肖像、書店、公園文字，去除參考圖 adapter。原文件 bytes SHA 和完整 prompt／檢查項隨方案封存，不從檔名猜測角色。

兩條路徑各為 **3 題材 × 2 個精確 seed × 基準／候選＝12 件計畫輸出**。seed 是 `9007199254740993`、`18446744073709551615` 字串；兩分支使用相同 trigger／提示詞、1024、28 steps、CFG 5、euler_ancestral／normal。基準 LoRA 為空陣列；候選僅新 UNet LoRA，model 1、CLIP 0。每題材／分支保存一個原生 seed 比較，共六份方案。方案建立或保存都不生成圖片。

`review-template.json` 是可另存填寫的人工審查表，連結原 evaluation hash；六個配對格分別記錄基準／候選作品 ID、畫風、身份、提示服從、絕對品質與失敗原因。不要只挑成功圖。每次正式生成前重驗安裝檔／回登資料，生成後核對原工作流程及權重快照，再用既有作品並排、評分、筆記與比較報告保留全部結果。原生 seed 方案本身不鎖定磁碟上的權重；來源封存與事後快照核對缺一不可。

至少四格改善只是預先設定的初步訊號；人物數、身份、服裝、物件或構圖錯誤仍要分別記錄。基準也失敗不代表候選品質通過。四面向未知保持未評分，工具不自動評分或把 `quality_accepted` 改成 true。

**圖片提醒：**現有作者素材仍有 caption／來源用途及角色逐張身分審查缺項，真正試訓前先完成 [T02 本批缺項](../validation/training-dataset-20261023.md)。進入最終作者品質比較前，提醒使用者提供或確認未參與訓練、選型或反覆調參的獨立保留圖；既有六張已曝光資料只能作開發評估，不能自稱未看過的最終測試。技術幾何資料不代替這些圖片。

## 單次技術驗收與備份

`python -m scripts.verify_trained_lora --run-id <UUID> --branch candidate` 明確執行一次 512／4 steps 的技術生成，`--branch baseline` 執行一次無 LoRA 基準；不是上述 12 件品質比較。預設報告已存在時拒絕新生成。加 `--verify-report` 只以 GET 核對原 job／作品／hash／完整設定，原引擎離線也可查回，不重新生成。可用 `--platform`、`--expected-engine`、`--report` 指定隔離驗收平台及新報告。

備份需包含原 T03 run、T02 bundle、固定基底、安裝的權重與 sidecar／SHA、evaluation／SHA、人工審查副本，以及平台 DATA 的方案、任務、作品和圖片。只有權重不能完整追溯來源；只有方案也不包含評估圖片或保證重現。這些 runtime／模型／使用者資料不進 Git。
