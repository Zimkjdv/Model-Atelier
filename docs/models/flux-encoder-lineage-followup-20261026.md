# M02：固定 FLUX 編碼器發布與轉換來源追查

查核日期：2026-10-26（Asia/Taipei）。沿用 [F02 條款查核](flux-component-licenses.md)、[固定安裝清冊](../../models/flux1-schnell-plan.json) 與 [條款來源清冊](../../models/flux1-schnell-terms.json)。本次只讀取公開模型卡、提交、討論及官方原碼；沒有下載大權重、替換模型或聯絡作者。此文件記錄公開來源證據，不包含另外執行的本機張量比對結果。

## 結論與範圍

可以補上兩檔的**發布提交與當時的 LFS SHA256**，以及 Apache-2.0 標記加入的時間。仍未取得發布者將這兩個固定輸出 hash 對應至上游權重 revision、轉換程式 revision 與完整執行參數的紀錄；既有 `conversion_lineage_verified=false` 與 `terms_verified=false` 不應因本次找到發布歷史就改為 true。這是本次所查公開範圍的結果，不聲稱作者從未在其他地方公布。

固定整合來源為 [`comfyanonymous/flux_text_encoders@6af2a98e3f615bdfa612fbd85da93d1ed5f69ef5`](https://huggingface.co/comfyanonymous/flux_text_encoders/tree/6af2a98e3f615bdfa612fbd85da93d1ed5f69ef5)：

| 檔案 | 大小（bytes） | LFS SHA256 |
| --- | ---: | --- |
| `clip_l.safetensors` | 246144152 | `660c6f5b1abae9dc498ac2d21e1347d2abdb0cf6c0c0c8576cd796491d9a6cdd` |
| `t5xxl_fp8_e4m3fn_scaled.safetensors` | 5157348688 | `a498f0485dc9536735258018417c3fd7758dc3bccc0a645feaa472b34955557a` |

上述是遠端權重指標與清冊的對應；這次沒有以模型卡文件 hash 代替本機權重完整 hash 驗證。

## 發布歷史可證明的部分

[HF 提交清單](https://huggingface.co/comfyanonymous/flux_text_encoders/commits/main)及[提交 API](https://huggingface.co/api/models/comfyanonymous/flux_text_encoders/commits/main)於查核時共有以下 5 個祖先提交；日期取 API UTC。逐一核對提交差異及祖先檔案樹，沒有額外的轉換腳本、上游下載紀錄或參數檔。

| 日期（UTC） | 提交 | 可直接觀察的內容 |
| --- | --- | --- |
| 2024-08-01 14:07:39 | [`4abe83400f770a9aca6f5d3e402790ca81421998`](https://huggingface.co/comfyanonymous/flux_text_encoders/commit/4abe83400f770a9aca6f5d3e402790ca81421998) | 初始 `.gitattributes`。 |
| 2024-08-01 14:23:15 | [`168aff54c7de740a8946f19cf87b2eda743c6342`](https://huggingface.co/comfyanonymous/flux_text_encoders/commit/168aff54c7de740a8946f19cf87b2eda743c6342) | comfyanonymous 加入 CLIP-L 與 `t5xxl_fp16.safetensors`；CLIP-L 指標已是本案固定 hash。只有 LFS 指標，未說明轉出自哪個上游 revision。 |
| 2024-08-01 14:29:53 | [`2f74b39c0606dae3b2196d79c18c2a40b71f3250`](https://huggingface.co/comfyanonymous/flux_text_encoders/commit/2f74b39c0606dae3b2196d79c18c2a40b71f3250) | 加入未加 scaled 後綴的 `t5xxl_fp8_e4m3fn.safetensors`。不能因此把它認定為 scaled 檔的輸入。 |
| 2024-10-21 03:56:53 | [`3bcfe977a9a2617a0b9025076030e217795fe028`](https://huggingface.co/comfyanonymous/flux_text_encoders/commit/3bcfe977a9a2617a0b9025076030e217795fe028) | comfyanonymous 加入本案 scaled T5 指標與 222 bytes README；提交名稱說明為 scaled T5 FP8，未附量化算法或來源。 |
| 2024-11-20 19:53:25 | [`6af2a98e3f615bdfa612fbd85da93d1ed5f69ef5`](https://huggingface.co/comfyanonymous/flux_text_encoders/commit/6af2a98e3f615bdfa612fbd85da93d1ed5f69ef5) | 只改 README，加入 `license: apache-2.0`；沒有改兩個固定權重指標。 |

[最終固定 README](https://huggingface.co/comfyanonymous/flux_text_encoders/blob/6af2a98e3f615bdfa612fbd85da93d1ed5f69ef5/README.md)說明供 ComfyUI DualClipLoader 使用並連至官方範例，未提供各檔上游 commit、改名對照、抽取／轉型程式、依賴版本、量化設定或適用條款逐元件說明。祖先中 FP16 T5 與 scaled T5 共存，只能證明有發布這些檔案，不能證明轉換方向或輸入檔。

## 作者討論與官方轉換工具

讀取 [HF 討論列表](https://huggingface.co/comfyanonymous/flux_text_encoders/discussions)及[討論 API](https://huggingface.co/api/models/comfyanonymous/flux_text_encoders/discussions)，查核時有 23 筆。針對來源／轉換問題進一步讀取 [#4 tokenizer 是否併入](https://huggingface.co/comfyanonymous/flux_text_encoders/discussions/4)、[#13 scaled 的意義](https://huggingface.co/comfyanonymous/flux_text_encoders/discussions/13)、[#14 是否等同 T5 v1.1 XXL](https://huggingface.co/comfyanonymous/flux_text_encoders/discussions/14)、[#15 如何轉為 FP16 檔](https://huggingface.co/comfyanonymous/flux_text_encoders/discussions/15)及 [#17 FP8 使用警告](https://huggingface.co/comfyanonymous/flux_text_encoders/discussions/17)。這些討論未見發布者回答來源與 recipe；第三方對品質的使用感想不作為轉換或授權證據。

另查 Comfy-Org 官方工具，保留其實際用途與證據限制：

- [`comfy-model-tools@d6797787e6bdb1a1fb0094d588a26f8e71a1c757`](https://github.com/Comfy-Org/comfy-model-tools/tree/d6797787e6bdb1a1fb0094d588a26f8e71a1c757)的 [README](https://github.com/Comfy-Org/comfy-model-tools/blob/d6797787e6bdb1a1fb0094d588a26f8e71a1c757/README.md)記載合併 safetensors、SeedVR2 轉換與 INT8 量化工具，沒有將本案 CLIP-L／T5 輸出 hash 綁至特定轉換。其[公開提交 API](https://api.github.com/repos/Comfy-Org/comfy-model-tools/commits?per_page=100)查得 19 筆，最早為 2026-04-17。
- [`comfy-quants@3d057e9c8e3132ef1853dec96f91d3de0aaf0e6a`](https://github.com/Comfy-Org/comfy-quants/tree/3d057e9c8e3132ef1853dec96f91d3de0aaf0e6a)提供 [FP8 格式](https://github.com/Comfy-Org/comfy-quants/blob/3d057e9c8e3132ef1853dec96f91d3de0aaf0e6a/docs/formats/fp8.md)與[匯出命令](https://github.com/Comfy-Org/comfy-quants/blob/3d057e9c8e3132ef1853dec96f91d3de0aaf0e6a/docs/quantization/fp8.md)，格式另有 `weight_scale`、`input_scale`、`comfy_quant`；[E4M3 格式註冊](https://github.com/Comfy-Org/comfy-quants/blob/3d057e9c8e3132ef1853dec96f91d3de0aaf0e6a/src/comfy_quants/formats/fp8_e4m3.py)預設 scale method 是 `amax`。[FLUX 指南](https://github.com/Comfy-Org/comfy-quants/blob/3d057e9c8e3132ef1853dec96f91d3de0aaf0e6a/docs/quantization/flux.md)處理 diffusion model，不能改當本案文字編碼器的轉換證明。其[公開提交 API](https://api.github.com/repos/Comfy-Org/comfy-quants/commits?per_page=100)查得 26 筆，最早為 2026-05-20。

這些公開工具比 2024 年兩檔發布時間晚。可用於理解現有格式與研究重建，尚無發布者聲明它們或其前身產生本案輸出；也不能由這些 repository 的起始日期推論其他歷史／私人腳本不存在。即使某個算法能產生近似張量，也必須另外區分「可重現輸出」與「作者實際採用的轉換」。

## BFL 參考依賴與條款界線

[BFL 固定 `util.py`](https://github.com/black-forest-labs/flux/blob/802fb4713906133fcbd0d8dc5351620ca4773036/src/flux/util.py)的 `load_clip` 指定 `openai/clip-vit-large-patch14`、長度 77、BF16；`load_t5` 指定 `google/t5-v1_1-xxl`、預設長度 512、BF16。同一修訂的 [`conditioner.py`](https://github.com/black-forest-labs/flux/blob/802fb4713906133fcbd0d8dc5351620ca4773036/src/flux/modules/conditioner.py)呼叫 Transformers `from_pretrained`，這組預設呼叫未傳入固定 `revision`。因此它證明 BFL 參考實作選用的模型 ID，沒有證明 comfyanonymous 兩個檔案的原始權重修訂或 FP8 轉換。

授權來源沿用 F02 的精確連結：整合卡標記 Apache-2.0；[OpenAI CLIP 專案 MIT 全文](https://github.com/openai/CLIP/blob/d05afc436d78f1c48dc0dbf8e5980a9d471f35f6/LICENSE)與[固定上游模型卡](https://huggingface.co/openai/clip-vit-large-patch14/blob/32bd64288804d66eefd0ccbe215aa642df71cc41/README.md)、[Google T5 專案 Apache-2.0 全文](https://github.com/google-research/text-to-text-transfer-transformer/blob/42909aa15d1fbd16c69333aa474a00ae8ed9fde4/LICENSE)與[固定 T5 v1.1 XXL 模型卡](https://huggingface.co/google/t5-v1_1-xxl/blob/3db67ab1af984cf10548a73467f0e5bca2aaaeb2/README.md)是候選上游條款。既有卡片用途／偏誤說明亦保留。沒有新增證據能解釋整合卡標記如何逐一對應 CLIP 原始權重、抽取與散布聲明；不把整合標籤當成上游義務已處理，也不把 BFL 主模型的 Apache-2.0 自動套至全部依賴。

## 尚缺的可追溯欄位

| 欄位 | CLIP-L | T5 FP8 scaled |
| --- | --- | --- |
| 固定整合 revision、輸出 SHA256、發布者與發布提交 | 已取得 | 已取得 |
| 實際上游 repository、權重 revision、輸入檔 hash | 未取得；BFL 模型 ID 僅作候選參考 | 未取得；同 repository FP16 檔也不能自行指定為輸入 |
| 抽取／改名／轉換程式與依賴 revision | 未取得 | 未取得 |
| 完整參數與重現環境 | 未取得；不能由 F16 存儲猜測轉型路徑 | 未取得；包含 scale 算法／粒度、保留精度的層、捨入、裁切、校準及相關 seed |
| 作者對固定輸出適用條款與來源聲明 | 僅整合卡 Apache-2.0 標記；上游權重對應仍缺 | 僅整合卡 Apache-2.0 標記；FP8 轉換來源仍缺 |

下一個能補足來源鏈的證據，是發布者對「輸入權重 hash／revision → 腳本 commit、參數、環境 → 此輸出 hash」的可追溯紀錄，並附對應條款與聲明；或可完整驗證、明確限定結論的重建證據。檔名、架構、推薦模型 ID、局部相等或數值近似，皆不足單獨填成作者來源已確認。

## 小型來源快照

下列內容在查核日經第一方 HTTP 實際讀取；動態 API hash 只辨識本次回應，日後可變動。大權重只查指標。

| 來源 | bytes | SHA256 |
| --- | ---: | --- |
| [固定整合 README](https://huggingface.co/comfyanonymous/flux_text_encoders/raw/6af2a98e3f615bdfa612fbd85da93d1ed5f69ef5/README.md) | 249 | `a7574aa7a1f033923bd1374587892e5f3f761f5e30edfad92521842cd0f75d3a` |
| [scaled 初次發布 README](https://huggingface.co/comfyanonymous/flux_text_encoders/raw/3bcfe977a9a2617a0b9025076030e217795fe028/README.md) | 222 | `12a2bd6123612009dee1fa3fadd14a2ee62147d3438325b8bcc1b1e4936089cc` |
| [HF 提交 API](https://huggingface.co/api/models/comfyanonymous/flux_text_encoders/commits/main) | 1038 | `4af48c16f26fa053cef0652b96a2415b12fe453a13e259ceddc8f954dd991193` |
| [HF 固定樹 API](https://huggingface.co/api/models/comfyanonymous/flux_text_encoders/tree/6af2a98e3f615bdfa612fbd85da93d1ed5f69ef5) | 1446 | `497b935d08bf6d27039956832c653d1479bf41dccf7e87a244c4995f6d12bb30` |
| [HF 討論列表 API](https://huggingface.co/api/models/comfyanonymous/flux_text_encoders/discussions) | 14428 | `229aa4dd805f8606e689b997a1d7d5bab523b8541d41dc0e020fcc30e9fad573` |
| [BFL `conditioner.py`](https://raw.githubusercontent.com/black-forest-labs/flux/802fb4713906133fcbd0d8dc5351620ca4773036/src/flux/modules/conditioner.py) | 1502 | `6207aea305b031fcd7d942a24dfc02330ba3f6dd0b61d929656ad1d5f9e6e075` |
| [Comfy-Org 工具 README](https://raw.githubusercontent.com/Comfy-Org/comfy-model-tools/d6797787e6bdb1a1fb0094d588a26f8e71a1c757/README.md) | 2229 | `74657f67b7a7cccfc458322ab15045e7dbfbac1eb10810bc181e613726abce1a` |
| [Comfy Quants FP8 格式](https://raw.githubusercontent.com/Comfy-Org/comfy-quants/3d057e9c8e3132ef1853dec96f91d3de0aaf0e6a/docs/formats/fp8.md) | 2268 | `8715fb6ffd892fe9954242afee43658897208b7d6e9e94144dea51bfeb423b78` |

## 本機完整檔案與候選 CLIP 數值對應

上述公開來源研究完成後，另執行本機唯讀核對及一個候選上游數值實驗。新增的 [JSON 證據](../validation/flux-encoder-audit-20261026.json)保存完整檔案 SHA256、張量指紋、遠端 Range 與每張量比對結果。它沒有把數值對應寫成發布者實際歷史的確認。

擴充 [本機核對器](../../scripts/inspect_weight_provenance.py)支援固定 CLIP-L／T5 清冊，依明確指定的獨立編碼器類型分組；本機兩份完整 hash 皆與固定權重一致。沿用 M01 的有界 header／offset 檢查及逐張量 SHA256；不載入 Torch、Transformers 或 GPU，不修改權重、正式 DATA 或既有安裝 provenance。

| 固定檔案 | 張量與格式 | 排序後張量內容指紋 SHA256 |
| --- | --- | --- |
| CLIP-L | 196 個 F16；metadata 僅 `format=pt` | `5ec23ddcd21c0e42777415eb2af61d06512bef8d7b7844ef2f2a40b9bd14f19d` |
| T5 FP8 scaled | 389 個：F8_E4M3 169、F16 52、F32 168；metadata 空白 | `c48da1cbdcb1183a22ae4e87a4b0df8c18a167b9c39be93854b9bd672a7f2108` |

T5 的 168 個 F32 張量皆為 scalar `*.scale_weight`，另有 `scaled_fp8` 的空 F8_E4M3 `[0]` marker。這些是讀取檔案得出的格式觀察，沒有證明 scale 採 amax、量化輸入、程式、seed 或校準方式。保留 `conversion_algorithm_inferred=false`。

[CLIP 候選比對器](../../scripts/compare_clip_provenance.py)以 BFL 推薦的模型 ID 為候選，固定到 [`openai/clip-vit-large-patch14@32bd64288804d66eefd0ccbe215aa642df71cc41`](https://huggingface.co/openai/clip-vit-large-patch14/tree/32bd64288804d66eefd0ccbe215aa642df71cc41)。透過 HTTPS Range 只讀取官方 `model.safetensors` 的 71,848 bytes header 與連續文字張量範圍 **74,532–492,316,451**（inclusive，共 **492,241,920 bytes**），沒有下載整份約 1.71 GB 權重或存檔。伺服器必須回 206、精確 Content-Range／total 與未壓縮內容；忽略 Range 的 200 回應在讀取 body 前就拒絕。

官方來源的 196 個對應張量皆為 F32，key／shape 與本機 F16 檔逐一相同；官方另外的 `text_model.embeddings.position_ids`（I64 `[1,77]`）是明列的唯一文字 buffer 差異。使用 NumPy **2.5.2** 的 little-endian `F32 -> F16 astype`，**全部 196 張量的每個輸出 byte 均與本機相同**。候選文字原始範圍 SHA256 為 `c0d267dd7fc60ef848cb6765b38c82f568fb809f0175b3370ebfd840bd3448f2`；JSON 保存每張量的原始 F32／轉換 F16／本機 F16 hash。

這個結果比架構／檔名／抽樣相同更強，證明此固定候選修訂可重建本機全部文字張量值；但沒有重建整份 safetensors 容器 byte、確認發布者實際讀取哪個 revision、使用哪套轉型工具，或釐清整合卡與上游條款的逐元件關係。官方檔案的完整 SHA256 僅記錄 [HF 固定樹](https://huggingface.co/api/models/openai/clip-vit-large-patch14/tree/32bd64288804d66eefd0ccbe215aa642df71cc41)的 LFS 宣告；本次未讀完 vision 區域，`full_file_sha256_verified=false`，不能冒稱完整上游檔案已核對。

清冊只追加發布提交、重新查核日期、指紋、候選數值對應與證據連結，未改固定下載 revision、權重 hash、F02 歷史紀錄或 BFL 主模型／VAE 的查核狀態。M02 `acceptance_complete=false`；兩個編碼器的 `terms_verified=false`、`conversion_lineage_verified=false`，CLIP 的 `historical_publisher_input_confirmed=false`。完整來源鏈仍需前節列出的發布者紀錄。

## 重跑

從專案根目錄執行，為報告選新的檔名；前兩個指令採既有的 runtime 限定／不覆寫報告規則。第三個指令輸出 JSON 至 stdout，需使用已有 NumPy 的受管 ComfyUI Python；只使用 NumPy 與標準函式庫，不啟動 ComfyUI 或模型。若遠端錯誤或張量不符，命令會非零退出，不能把部分輸出當作通過。

```powershell
.\.venv\Scripts\python.exe -m scripts.inspect_weight_provenance --model flux1-schnell-clip_l --report runtime/new-clip-local.json
.\.venv\Scripts\python.exe -m scripts.inspect_weight_provenance --model flux1-schnell-t5xxl --report runtime/new-t5-local.json
.\runtime\ComfyUI\.venv\Scripts\python.exe -m scripts.compare_clip_provenance > runtime/new-clip-candidate.json
.\.venv\Scripts\python.exe -m unittest backend.test_weight_provenance backend.test_clip_provenance backend.test_flux_install backend.test_flux_plan backend.test_flux_catalog backend.test_model_metadata
.\.venv\Scripts\python.exe -m scripts.check_style
```

測試覆蓋本機完整 hash 先於網路查詢、忽略／錯誤／壓縮／截斷／超量 Range、上限、HTTPS redirect、完整 key／shape／dtype、連續 payload、每 byte 比較、全量吻合仍不提升來源或授權旗標，以及不載入 GPU 套件。原始小型回應保存在忽略的 `runtime/m02-review-20261026/`；數值實驗沒有保存遠端權重檔案。
