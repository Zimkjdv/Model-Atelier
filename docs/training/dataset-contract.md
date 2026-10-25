# T02 · 本機訓練資料契約 v1

這是 [T01 需求](requirements.md) 的 CPU 資料準備工具：建立清單、檢查原圖、審查標註、匯出獨立資料包。**不安裝 trainer、不載入權重、不啟動訓練或生成**。T05 已提供沿用此契約的[資料審查網頁](workspace.md)；一般素材用途、R02 單張推論與本契約分開。

版本為 `schema_version: 1`，機器格式見 [JSON Schema](../../schemas/training-dataset-v1.schema.json)，跨圖片條件由 [資料檢查器](../../backend/training_data.py) 驗證。工具介面選定固定 SHA 的 sd-scripts 候選，來源與未實測限制見 [官方介面評估](tool-interface-research.md)。

## 清單與審查

| 層級 | 欄位與規則 |
| --- | --- |
| 資料集 | `dataset_id`、`version`、`kind: style/character`、`subject_id`、獨立 `trigger`、需求版本；畫風與角色分開清單／資料包 |
| 基底 | Animagine XL 4.0 Opt 的 ID、版本、SDXL、檔案 SHA256／大小及來源 revision，須與 T01 的本地模型 manifest 一致；這只核對登記，沒有重新讀取 6.9 GB 權重或證明 trainer 相容 |
| 原圖 | 穩定 `id`、來源根目錄內的相對 `path`、原始 bytes SHA256／大小、未旋轉的原尺寸；Unicode 檔名可用，不接受絕對路徑、上層路徑、反斜線、磁碟代號或連結 |
| 分組 | `group_id` 表示同原作／差分；完全相同 bytes 必須同組。不同裁切／差分需人工合併，工具不自動辨識近似圖；同組不得跨有效 train／validation／test；同組最多一張訓練候選 |
| 分割 | `train` 是待審查訓練候選；`validation` 是開發評估；`test` 是未曝光最終評估；`excluded` 必須記錄 `exclusion_reason`。排除副本可保留原群組而不參與訓練 |
| 曝光 | `r02_contact_sheet`、`inference_reference`、`tuning`、`training`、`final_evaluation`；test 有任何既有曝光即拒絕。這是人工／歷史紀錄，工具不能證明人從未看過圖片 |
| 角色 | `identity: unreviewed/target/other/mixed` 與 `character_ids`；角色路徑的每張 train 必須明確標為 target，且只列本資料集 subject；同作者不等於同角色 |
| 內容與畫風 | `caption.content` 是非空白單行內容描述；`caption.style_description` 單獨記錄畫風觀察，不會自動附加到 trainer caption。`status: approved` 及非空白 `reviewed_by` 才算完成內容審查 |
| 來源用途 | `provenance` 記錄 attribution、work_id、source_url、training_use、usage_note、reviewed_by。只有 `training_use: recorded` 且用途註記／審查人完整才准許匯出；recorded 是人員紀錄，不是工具作出的權利保證。未知資訊保留空白，不推測作者或授權 |
| 前序研究 | 有 `parent_study` 時，保存 R02 study ID 與原始 JSON bytes SHA256；check／export／verify 都必須提供該凍結清單，並核對全部來源身分、分組、用途及至少既有曝光，不能把 holdout 改作 train |

清單為 UTF-8 JSON；拒絕未知欄位、重複 JSON key、非整數／不支援版本、型別轉換、重複 ID／大小寫路徑。上限為 10,000 筆且序列化清單不超過 8 MiB。原圖接受單張 PNG／JPEG／WebP，1 byte–64 MiB、最多 4,000 萬像素，會完整解碼並核對 SHA、大小與尺寸；這是 CLI 上限，沒有擴大平台素材上傳限制。

`data_ready` 只表示本工具的**資料出口檢查**通過：至少一張 train、一張 development validation、訓練標註與來源紀錄完整，角色路徑另需身分確認。缺最終 test 會警告但不阻擋訓練資料準備；不代表樣本數／涵蓋足夠、已可訓練或品質已通過 T04。

## 執行命令

從專案根目錄使用既有應用程式 venv，不需 trainer、Torch 或額外依賴。以下命令只準備資料；`init` 不會複製圖片、寫回原圖或自動完成審查。

```powershell
$sourceRoot = 'C:\Users\Ryanisop\Desktop\artist_ref\ハシスタジオ_pixiv'
$studyFile = 'runtime/r02-reference-study/study-manifest.json'
$manifestFile = 'runtime/training/hashi-style-v2.json'

.\.venv\Scripts\python.exe -m scripts.training_dataset init `
  --source-root $sourceRoot --study $studyFile --output $manifestFile `
  --dataset-id hashi-style --version v2 --kind style `
  --subject-id hashi-style --trigger ma_hashi_style_v2

.\.venv\Scripts\python.exe -m scripts.training_dataset check $manifestFile `
  --source-root $sourceRoot --study $studyFile `
  --report runtime/training/hashi-style-v2-readiness.json
```

角色路徑另用 `--kind character --dataset-id hashi-character --subject-id brown-green-character --trigger ma_brown_green_v2` 建立不同清單及輸出位置。沒有 R02 前序的全新資料集可省略 `--study`；init 只按完全相同 hash 去重，預設全部不同內容為 train 候選，必須人工建立合理的原作群組與獨立評估分割。

回傳碼：`0` 成功／資料出口檢查通過，`2` 為 check 成功完成但資料未就緒，`1` 為格式、來源／檔案或匯出錯誤。stdout 是 JSON，錯誤 JSON 在 stderr；`--report` 另寫 UTF-8 完整缺項。清單／報告／資料包都拒絕覆寫，也拒絕輸出到原圖目錄或其上層，請用新版本／新路徑。

人員完成審查時，另存新版本清單並更新 `version`。以一張**合成示例**說明應填欄位，不能把這段認列為實際作者圖已審查：

```json
{
  "caption": {
    "content": "1girl, long brown hair, green eyes, blue coat, reading a book",
    "style_description": "細線條、柔和陰影；需與實際圖片逐張核對",
    "status": "approved",
    "reviewed_by": "實際審查人"
  },
  "provenance": {
    "attribution": "已核對的來源名稱；未知則空白",
    "work_id": "",
    "source_url": "",
    "training_use": "recorded",
    "usage_note": "實際核對的來源與本次用途依據；不能只複製此範例",
    "reviewed_by": "實際審查人"
  }
}
```

角色路徑還需逐張填 `identity: target`、`character_ids: ["brown-green-character"]`；其他角色、混合或不確定圖片應排除／另分組，不為通過檢查而全部填 target。

## 不可覆寫的資料出口

check 通過之後才可執行：

```powershell
.\.venv\Scripts\python.exe -m scripts.training_dataset export $manifestFile `
  --source-root $sourceRoot --study $studyFile `
  --output runtime/training/exports/hashi-style-v2

.\.venv\Scripts\python.exe -m scripts.training_dataset verify-bundle `
  runtime/training/exports/hashi-style-v2 --study $studyFile
```

資料包結構：

```text
<new-bundle>/
  dataset.json         完整清單；含未匯出的評估／排除紀錄
  dataset.toml         固定 sd-scripts 候選資料介面，只指向本包 train
  train/<image-id>.png 正規化副本；只限通過審查的 train
  train/<image-id>.txt 單行 UTF-8：trigger, caption.content
  bundle.json          最後寫入的封存紀錄；hash、大小、前處理、Pillow 版本
```

輸出圖先按 EXIF 旋轉、透明合成白底、轉 RGB PNG、最長邊縮至 2048；不放大、不裁切並移除原 metadata。前處理版本是 `exif-white-rgb-png-max2048-v1`，原圖 hash 與出口 PNG hash 分開保存，Pillow 版本亦入封存。1024 bucket 的訓練裁切與 VRAM 適合度仍待 T03 實測。

dataset TOML 使用官方已核對欄位：1024²、batch 1、bucket 步幅 64、不放大、repeats 1、`shuffle_caption=false`、`validation_split=0.0`。它只引用絕對的 train 目錄；validation／test／excluded **沒有圖片副本進入 trainer 資料夾**。sd-scripts 原生有隨機 validation split，但不讀專案原作群組與曝光，所以本輪不讓它重新分割。

工具先檢查全部來源再建立全新目錄，寫入 train 時重新核對來源，封存前再次核對所有來源。磁碟／來源變更或中斷時可能留下不完整目錄，**不自動刪除、不覆寫重試**；缺 `bundle.json` 即不能驗證，保留供檢查並另用新位置。這不是原子目錄發佈或對外簽章。

verify-bundle 不讀原圖、不連網；檢查封存、清單與基底身分、metadata 條件、精確檔案集合、bytes hash／大小、PNG 格式與尺寸、caption 及 TOML，額外放入保留圖也會拒絕。它檢查一致性，不能對抗有人重新改寫全部清單與 hash；最初原圖到副本的關係由 export 時的查核與受保管封存建立。

TOML 含絕對路徑，移動資料包後驗證會拒絕；在新位置由原圖與固定清單重新 export，保留舊包。正式訓練時另建立 run 工作副本，保存與封存包的 hash 關係，避免 trainer 快取污染已封存資料，屬 T03。

`dataset_id + version` 是人工版本標籤，正規化清單 SHA256 才識別內容；工具禁止覆寫已有輸出，但不維護跨目錄的全域版本登記。修改 caption／分割／用途／前處理均應建立新版本；比較 hash，不只比較名稱。

## 本批資料的缺項與補圖提醒

本輪兩份清單皆為 **10 train 候選／6 development validation／0 final test／6 excluded**，不是 20 張已訓練素材。10 張的 caption、來源用途仍待審查，角色路徑另外 10 張身分待確認；目前不能匯出作者訓練資料。完整編號、hash 與驗收見 [T02 紀錄](../validation/training-dataset-20261023.md)。

現在不要求使用者為完成 T02 補圖。**決定進 T03 試訓時**，提醒使用者一起確認既有 10 張候選的實際內容／來源用途、逐張目標角色，以及不同服裝、視角、姿勢／背景是否足夠；不足才請提供相應圖片。**T04 最終比較前**，再提醒提供未參與訓練、參考選型、調參或既有聯絡表檢視的不同原作評估圖，不能把目前 6 張開發圖改稱未曝光盲測。

資料及衍生包放於已忽略的 `runtime/`，原圖留在使用者提供的來源目錄；自行備份清單、study、封存包與來源。Git 只收契約、程式與不含原圖的驗收摘要。下一項依指定順序為 R01 → R03；T03／T04 仍另排。
