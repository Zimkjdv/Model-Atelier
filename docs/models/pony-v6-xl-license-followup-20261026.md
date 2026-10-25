# M01：Pony V6 XL 第一手來源補查

查核日期：2026-10-26（Asia/Taipei）。範圍限本專案固定的 HF 修訂 `5ec9c05863255568f1b59753e3838107befaa712`、`v6.safetensors`、SHA256 `67ab2fd8ec439a89b3fedb15cc65f54336af163c7eb5e4f2acc98f090a29b0b3`。本頁補充 [先前查核](pony-v6-xl-license.md)，不取代原紀錄。

本次找到可直接閱讀的**作者官網 V6 專頁**，支持 Civitai 的修改版 Fair AI 聲明；但沒有找到說明該聲明與固定 HF Open RAIL-M 標記適用關係的發布者澄清，也未找到內含模型／編碼器／VAE 的精確來源版本。因此，這項補查仍不足以將完整適用條款與依賴鏈標為已核實，`terms_verified` 應維持 false。這是所查公開證據的狀態，不是決定授權優先序的法律結論。

## 新增：作者官方 V6 頁面

直接讀取 [PurpleSmartAI 的 Pony Diffusion V6 頁面](https://purplesmart.ai/pony/content6x) 得 HTTP 200。頁面明確將 V6 描述為 SDXL finetune，License 區段連到 [Fair AI Public License 1.0-SD 全文](https://freedevproject.org/faipl-1.0-sd/)，並聲明附加的變現推論限制適用於網站／應用及衍生、合併模型；商業使用另洽發布者。這是對 V6 的直接第一手聲明，可與本次仍可取得的 [Civitai 模型發布 API](https://civitai.com/api/v1/models/257749) 對照。

官網 V6 的 License 區段未附「HF 標記為何不同」的說明，也未列出 Civitai API 另有的具名特許句；不能由缺少該句推定特許取消。頁面未提供條款的不可變版本、變更歷史或特定舊取得時間的適用說明。[V6 官網原頁](https://purplesmart.ai/pony/content6x)、[Civitai 發布內容](https://civitai.com/api/v1/models/257749)

官網頁面的 HTML 包含會變動的 email 保護編碼，本次連續讀取的完整 HTML hash 不同，不能把它直接判作授權變更。本次另做有界文字定位：stdlib `HTMLParser` 排除 script/style，將可見文字以空格連接、折疊 whitespace，從 `License This model` 截至 `Subscribe to our Newsletter` 前並 strip；得 **493 UTF-8 bytes**、SHA256 **`45e91efc1065b444b12fefe8e10004c4b9aba1399b379b05d6e307ab7f887cc2`**。這是自定義擷取片段指紋，沒有冒稱發布者提供的修訂。

## 固定 HF 與 Civitai 的重新核對

| 第一手來源 | 本次觀察 |
| --- | --- |
| [HF 固定 revision API](https://huggingface.co/api/models/AstraliteHeart/pony-diffusion-v6/revision/5ec9c05863255568f1b59753e3838107befaa712) | revision 仍為指定值；cardData 只提供 `creativeml-openrail-m` |
| [HF 固定 README 原文](https://huggingface.co/AstraliteHeart/pony-diffusion-v6/raw/5ec9c05863255568f1b59753e3838107befaa712/README.md) | 39 bytes；SHA256 `5e19452d23c8d763b95aee6643804d5787b0852a993bcc6886afdcaec1227241`，與先前相同，仍只有 YAML 標記 |
| [HF 固定樹 API](https://huggingface.co/api/models/AstraliteHeart/pony-diffusion-v6/tree/5ec9c05863255568f1b59753e3838107befaa712) | 仍只有 `.gitattributes`、README、權重；權重 6,938,041,050 bytes，LFS oid 與固定 SHA256 相同，沒有另附完整授權或元件 manifest |
| [HF main commit API](https://huggingface.co/api/models/AstraliteHeart/pony-diffusion-v6/commits/main) | 兩筆：2024-01-23 的 `5ec9c05…` 上傳權重，以及 2023-08-25 的 `f606167…` initial commit；沒有後續 main 授權修訂可供核對 |
| [Civitai 版本 API 290640](https://civitai.com/api/v1/model-versions/290640) | file 228616 的完整 SHA256 與固定權重相同；版本 description 為 null。另列 VAE 的下載項目不能證明該 VAE 內含於此 checkpoint |
| [Civitai 模型 API 257749](https://civitai.com/api/v1/models/257749) | creator 仍為 PurpleSmartAI。License HTML 區段仍為 1,227 bytes、SHA256 `0f7a84a57c91437e080b25daea4840767c26c2bc5e834d338154bc3802396e10`；修改版 Fair AI 及具名推論特許聲明與先前相同 |
| [Fair AI 標準全文](https://freedevproject.org/faipl-1.0-sd/) | 仍可讀取全文，HTML 14,576 bytes、SHA256 `430e926fd41937bb6ec02716534ceadc0386f54efec48e77b2ee4e1aaa0f53c0`，與先前相同。標準全文須與發布者附加聲明區分 |

Civitai 的 download／like 等 metadata 會變動，其完整 API hash 與先前不同，並不代表 License 區段改變。此處只對照實際取得的發布內容與固定檔案，不以同名、AutoV2 短 hash 或另列的 VAE 推導權重身分。

## 排除不適用的頁面與未接受的 PR

- [官網預設 `/pony`](https://purplesmart.ai/pony) 本次導向 [V7 頁面](https://purplesmart.ai/pony/content7x)，其中的 AuraFlow 與 Pony License 描述不是 V6 的來源證明。
- [官網 `/license`](https://purplesmart.ai/license) 顯示 2025-04-04 的 Pony License 全文，其定義指向「在該協議下提供」的材料，沒有以固定 V6 檔案 hash 或 HF 修訂明確指定本次對象。不能僅因它位於同一官網，就把該全文套到仍另列 Fair AI 的 [V6 專頁](https://purplesmart.ai/pony/content6x)。
- [舊站 Terms](https://v6.purplesmart.ai/terms) 開頭明述適用網站及服務，仍不是本固定 V6 權重的完整發布授權鏈。
- 本次讀取 [HF 六筆 discussion／PR 清單](https://huggingface.co/api/models/AstraliteHeart/pony-diffusion-v6/discussions)，並逐筆核對 `/discussions/1` 至 `/discussions/6` 的 API 事件；沒有看到 repo owner 的授權澄清。其餘使用者提出的 rename／README／diffusers PR，不能當作 owner 已採納的授權變更。main 的固定來源仍以上表為準。

## 仍缺少的可追溯資料

作者 V6 官網與 Civitai 可補強「發布者現在聲明哪些條款」，但未補上以下資料：

1. 固定 HF 檔案與該發布聲明之明確關聯，以及不同來源標記、取得時間與修改版條件的適用說明。
2. V6 真正訓練起點 checkpoint 的 revision／完整 hash；「SDXL finetune」只描述架構關係。
3. 固定 Pony checkpoint 內 CLIP-L、OpenCLIP、VAE 及其他元件的實際上游版本／修改與通知。

本次只檢查上述可讀取的公開第一手來源；沒有聯絡發布者、接受額外合約、下載另一份模型或改寫既有 provenance。後續若取得發布者釐清、固定元件 manifest 或可驗證的逐張量來源對照，應另存來源與查核日期，再決定哪些缺口可以關閉；單純再讀標準授權全文不會自動補足這些資料。

## 本機元件核對與可重跑工具

新增 CPU-only `scripts.inspect_weight_provenance`，按照 [safetensors 官方格式](https://github.com/safetensors/safetensors/blob/main/README.md#format)有界解析 header、驗證 dtype／形狀／不重疊且無缺口的完整資料範圍，一次串流核對全檔 SHA256 及各張量內容。沒有載入 Torch、模型、GPU 或來源宣稱的程式碼，也不修改正式 DATA、權重或既有 provenance。

本機固定權重核對通過，2,515 個張量均為 F16；依明確 key 前綴分為 diffusion model 1,680、CLIP-L 197、CLIP-G 390、VAE 248。metadata 的 `modelspec.title` 是 `v6-full-te`，但未提供來源 revision 或授權；名稱本身不能證明是否或如何修改編碼器。每組保存依張量名稱排序的內容指紋，包含名稱／dtype／shape／bytes／張量 SHA256，可供將來取得上游時對照，不能只憑指紋宣稱已找到上游。

完整結構、元件 byte 數與指紋、來源回應狀態／hash、兩項外部缺口見 [JSON 證據](../validation/pony-license-audit-20261026.json)。報告明確保留 `acceptance_complete=false`、`terms_verified=false` 與元件 `upstream_revision=null`，不以本機讀取成功代替授權證明。

```powershell
.\.venv\Scripts\python.exe -m scripts.inspect_weight_provenance --model pony-v6-xl --report runtime/new-pony-provenance.json
.\.venv\Scripts\python.exe -m unittest backend.test_weight_provenance backend.test_model_install backend.test_animagine_install backend.test_model_profiles backend.test_model_metadata backend.test_generation_acceptance backend.test_animagine_acceptance
```

新工具與測試列入 quality scope，因其產生來源核對證據。回歸涵蓋 metadata 不能提升授權狀態、錯誤檔案 hash、重複 JSON keys、offset 缺口／重疊、無效形狀與有界 header、空／scalar 張量、唯讀及不載入 GPU 套件。原始網站回應保存在忽略的 `runtime/m01-review-20261026/`，不將整份網站內容加入 Git。
