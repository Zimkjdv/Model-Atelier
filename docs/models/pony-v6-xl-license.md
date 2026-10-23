# Pony V6 XL 授權與依賴核對

核對日期：2026-10-23（Asia/Taipei）。範圍為本專案 manifest 指定的 `AstraliteHeart/pony-diffusion-v6`、修訂 `5ec9c05863255568f1b59753e3838107befaa712`、`v6.safetensors`。本次完成公開證據查核，**M01 驗收維持未結案，`terms_verified: false`**：固定來源只有授權標記；另一發布頁對相同 SHA256 的模型列出不同授權及商業推論限制，兩者的適用關係與完整依賴鏈尚未核實。

## 固定權重與來源證據

| 項目 | 查核結果與第一手來源 |
| --- | --- |
| 權重 | `v6.safetensors`，`6938041050` bytes；SHA256 `67ab2fd8ec439a89b3fedb15cc65f54336af163c7eb5e4f2acc98f090a29b0b3`。[固定修訂檔案](https://huggingface.co/AstraliteHeart/pony-diffusion-v6/blob/5ec9c05863255568f1b59753e3838107befaa712/v6.safetensors) |
| 模型卡 | 39 bytes，內容僅 YAML 的 `license: creativeml-openrail-m`；沒有授權全文、全文連結、依賴來源或附加條款。[固定 README](https://huggingface.co/AstraliteHeart/pony-diffusion-v6/blob/5ec9c05863255568f1b59753e3838107befaa712/README.md) |
| README 指紋 | 原始 bytes 的 SHA256 `5e19452d23c8d763b95aee6643804d5787b0852a993bcc6886afdcaec1227241`。[原始檔案](https://huggingface.co/AstraliteHeart/pony-diffusion-v6/raw/5ec9c05863255568f1b59753e3838107befaa712/README.md) |
| 根目錄 | 僅 `.gitattributes`、`README.md`、`v6.safetensors`，未附 `LICENSE` 或其他授權檔。[固定檔案樹](https://huggingface.co/AstraliteHeart/pony-diffusion-v6/tree/5ec9c05863255568f1b59753e3838107befaa712) |

此處 SHA256 是檔案內容指紋，不能與 Git commit、Git blob 或 Xet hash 混用；相同指紋可用來對照發布檔案，不能證明發布者具有完整授權權利。

## 相同權重的另一發布頁與條款差異

2026-10-23 直接讀取 [Civitai 模型 API：257749](https://civitai.com/api/v1/models/257749) 與 [版本 API：290640](https://civitai.com/api/v1/model-versions/290640)，均回應 HTTP 200。前者名稱為 Pony Diffusion V6 XL，`creator.username` 為 `PurpleSmartAI`；後者版本名稱為 `V6 (start with this one)`、`modelId: 257749`，其中 file `228616` 的名稱為 `ponyDiffusionV6XL_v6StartWithThisOne.safetensors`，完整 SHA256 與本專案固定權重相同。這項對照僅限此檔案，不延伸至 Turbo、V6-1.5、V7 或同頁另列的 VAE。

模型 API 的 description 之 License 段落宣告採用**修改版 Fair AI Public License 1.0-SD**，並連到[條款發布者的全文](https://freedevproject.org/faipl-1.0-sd/)。它另外禁止在允許任何變現形式的網站或應用程式提供該模型推論，包含付費推論或付費較快層級，並明述涵蓋衍生模型與合併模型；商業使用須另洽發布者，商業推論特許僅點名 Civitai 與 Hugging Face。這些是該發布頁的聲明，不能把特許擴張至其他服務或本平台。[Civitai 發布內容](https://civitai.com/api/v1/models/257749)

同一回應的旗標為 `allowNoCredit: false`、`allowCommercialUse: ["Image", "RentCivit"]`、`allowDerivatives: true`、`allowDifferentLicense: false`。旗標是平台 metadata，不能取代上述文字及完整條款，也不能單憑 `Image` 推論任何使用情境均獲准。[Civitai metadata](https://civitai.com/api/v1/models/257749)

Civitai description 連到 `twitter.com/AstraliteHeart` 並稱為作者，但本次沒有獨立核實兩站帳號的法律身分、權利歸屬、初次發布時的條款或修改時點。相同檔案 SHA256 足以記錄「不同發布來源的條款差異」；**不能據此斷言何者優先、舊取得者權利失效，或 HF 標記可排除其他來源限制**。[發布頁](https://civitai.com/models/257749/pony-diffusion-v6-xl?modelVersionId=290640)、[公開 API](https://civitai.com/api/v1/models/257749)

Civitai 的模型／版本 ID 可追溯對象，但 API 回應與模型 description 並非不可變修訂。本次 HTTP 原始 bytes 指紋如下；後續不同回應不必然代表授權改變，其他欄位也可能更新。

| 本次回應 | 大小 | SHA256 |
| --- | --- | --- |
| 模型 API 257749 | `19381` bytes | `11c43d2f757632d554a09d2ad2a81515f5bbe3289ec8da2aa5d3134d3c82a3a0` |
| 版本 API 290640 | `11360` bytes | `7ba886288ae390e61851013c938d960634c40bf7623eee6b695575334d78afa0` |
| 模型 description 內 License HTML 段落 | `1227` bytes | `0f7a84a57c91437e080b25daea4840767c26c2bc5e834d338154bc3802396e10` |

最後一列取 UTF-8 編碼的 description，自 `<h2 id="license-` 首次出現處至 description 結尾，未重排 HTML。它是本次片段指紋，不是發布者提供的版本識別。

## 已讀的完整參照條款

以下均已閱讀全文及使用限制，並區分「參照文本讀畢」與「已核實適用本權重」。本專案沒有把參照條款另存成 Pony 發布者附上的授權檔。

| 文本 | 可追溯來源／日期 | 原始 bytes 與 SHA256 |
| --- | --- | --- |
| CreativeML Open RAIL-M | CompVis 官方 Space，固定修訂 `14d42d09bffd871b1666a084fc954a50cff72ac0` 的 [license.txt](https://huggingface.co/spaces/CompVis/stable-diffusion-license/blob/14d42d09bffd871b1666a084fc954a50cff72ac0/license.txt)，文本日期 2022-08-22 | `14385`；`be351ebe7ac01bcdbb018639aadcfd38f136b7dc3f2a3d4d3a24db51d1b210ef` |
| Fair AI Public License 1.0-SD | [Freedom of Development Project 官方全文](https://freedevproject.org/faipl-1.0-sd/)；未找到可核實的不可變修訂識別，使用 2026-10-23 所見版本 | HTML `14576`；`430e926fd41937bb6ec02716534ceadc0386f54efec48e77b2ee4e1aaa0f53c0` |
| CreativeML Open RAIL++-M | Stability AI SDXL base 固定修訂 `462165984030d82259a11f4367a4eed129e94a7b` 的 [LICENSE.md](https://huggingface.co/stabilityai/stable-diffusion-xl-base-1.0/blob/462165984030d82259a11f4367a4eed129e94a7b/LICENSE.md)，文本日期 2023-07-26 | `14109`；`19b6998b569b53ac1fc2158a8a3202c8699a9a4605b47075715d9c96be7fb6d0` |

Open RAIL-M 第 2–6 條在遵守條件下提供使用、修改與散布權；遠端託管也納入散布。需交付授權副本、保留相關通知、標示修改，並以可執行條款傳遞使用限制；產出責任由使用者承擔。Attachment A 限制違法、傷害未成年人、惡意虛假資訊、傷害性個資、騷擾、侵害權利的自動決策、歧視、利用弱勢、醫療建議及特定司法／執法用途。第 7–12 條另含執行限制、商標、免責與責任限制。本次讀畢不表示它就是 Pony 固定發布者所附全文。[完整參照原文](https://huggingface.co/spaces/CompVis/stable-diffusion-license/blob/14d42d09bffd871b1666a084fc954a50cff72ac0/license.txt)

Fair AI 的 Notices 要求交付授權及對應 source code；其定義包含模型但排除訓練資料集。修改後透過網路供使用者互動時，須提供合理取得對應 source code 的方式；僅互動衍生模型時可提供該模型。原文另有相容授權要求、通知後補正、產出不受該授權涵蓋、專利、No Harm、No Liability 及 Prohibited Uses。**這是未修改標準本文摘要**，仍須併讀 Civitai 額外條件，不能只保留標準本文的寬鬆部分。[Fair AI 全文](https://freedevproject.org/faipl-1.0-sd/)

SDXL 的 Open RAIL++-M 也包含散布通知、修改標示、向下傳遞限制、產出責任及 Attachment A；它與 Open RAIL-M 是不同文本，不應用同一 identifier 取代。這是核對 SDXL 上游的參照，尚未證明 Pony 內全部元件確實來自該固定修訂。[SDXL 授權全文](https://huggingface.co/stabilityai/stable-diffusion-xl-base-1.0/blob/462165984030d82259a11f4367a4eed129e94a7b/LICENSE.md)

## SDXL 與文字編碼器依賴

Civitai 發布內容將 V6 XL 描述為 SDXL finetune，但沒有列出訓練起點 checkpoint 的完整 hash、SDXL 修訂、文字編碼器／VAE 的個別來源及修改清單。本次不從「SDXL」架構名稱推導完整權利鏈。[Pony 發布內容](https://civitai.com/api/v1/models/257749)

| 對象 | 已核對的官方資料 | 對此 Pony 權重的限制 |
| --- | --- | --- |
| SDXL base 1.0 | [固定模型卡](https://huggingface.co/stabilityai/stable-diffusion-xl-base-1.0/blob/462165984030d82259a11f4367a4eed129e94a7b/README.md) 指出兩個預訓練編碼器為 OpenCLIP-ViT/G 與 CLIP-ViT/L，並連到各自官方專案；[同修訂 model_index](https://huggingface.co/stabilityai/stable-diffusion-xl-base-1.0/blob/462165984030d82259a11f4367a4eed129e94a7b/model_index.json) 列出雙編碼器、tokenizer、UNet 及 VAE | 是上游架構參照；沒有 Pony 訓練來源的固定修訂證明 |
| OpenAI CLIP 專案 | [官方 LICENSE](https://github.com/openai/CLIP/blob/d05afc436d78f1c48dc0dbf8e5980a9d471f35f6/LICENSE) 為 MIT；原始 `1064` bytes，SHA256 `987e63b32f6c89ff5160e429458a872ff048e6860b590a3912e938f9da8f14db` | 已讀軟體授權，不能替代 Pony 內文字編碼器權重來源／修改的證明 |
| OpenCLIP 專案 | [官方 LICENSE](https://github.com/mlfoundations/open_clip/blob/7067b350050dc409bfdfdbb3f0cc6c9a1651c000/LICENSE) 為 MIT；原始 `1229` bytes，SHA256 `4a5b4f13ea4792a8211a69f32d2b460b6d520e57cd23c6301e707c76a6e97a55` | 專案程式碼授權不自動涵蓋所有訓練權重／資料 |
| LAION CLIP ViT-bigG/14 參照模型 | [固定模型卡](https://huggingface.co/laion/CLIP-ViT-bigG-14-laion2B-39B-b160k/blob/dc11fc353a11981f880f70f7f418e4abdb651463/README.md) 明述模型採 MIT，並記錄訓練資料與使用範圍 | 尚未確認它就是此 Pony 內編碼器的來源，沒有以名稱或維度相符代替 hash／來源對照 |
| VAE、tokenizer 及其餘內含元件 | SDXL 固定模型卡／model_index 可作依賴盤點起點；Civitai 同版本另外提供 VAE 檔案 | 同頁下載項目不證明該檔案內含於固定 Pony checkpoint；個別來源、修訂、修改與授權適用仍未知 |

MIT 本文要求保留著作權及授權通知，並附免責；這是相應官方專案的條件，不是整個 Pony checkpoint 的單一授權。[CLIP](https://github.com/openai/CLIP/blob/d05afc436d78f1c48dc0dbf8e5980a9d471f35f6/LICENSE)、[OpenCLIP](https://github.com/mlfoundations/open_clip/blob/7067b350050dc409bfdfdbb3f0cc6c9a1651c000/LICENSE)

## 平台應採用的結論與後續條件

- manifest 保留 HF 原始 `creativeml-openrail-m` 標記作為來源事實，另存「發布來源條款差異」，不可將 `identifier` 靜默改成任何一份標準條款來掩蓋差異。
- `terms_verified` 維持 `false`；可另記已讀的參照全文、來源、修訂／查核日期、SHA256 與未核實範圍。標記的含義是**固定權重的完整適用授權尚未核實**，不是所有參照條款都未讀過。
- 文件與 UI 不可宣稱 Pony 無條件商用、已取得第三方付費推論權、完整依賴鏈已通過或法律保證。來源查核不改寫既有任務／作品的凍結歷史，也不代表已代使用者取得任何特許。
- 再散布、提供網路服務或變現前，須釐清相同權重兩處聲明的適用關係、取得／散布時條款、衍生／合併模型條件及各元件通知；不能只附一份 Open RAIL-M 標準文本就視為完整。
- 要將完整適用條款標為已核實，仍需可追溯的發布者釐清或正式授權，以及 SDXL／文字編碼器／VAE 等實際來源和通知。訓練資料、第三方著作權、商標、肖像等權利不因模型授權標記而全部取得；本次沒有核實這些權利。

本次查核未要求登入、未取得非公開合約、未聯絡發布者、未接受額外服務契約，也未下載另一份模型。PurpleSmartAI 現行網站的 [Pony V7 頁面](https://purplesmart.ai/pony/content7x) 明確介紹 V7；[舊站服務條款](https://v6.purplesmart.ai/terms) 描述其網站及服務，均不能冒充此固定 V6 權重的完整授權鏈。

## 本專案驗證與保存

現有 `checkpoint-text2image-v1` 使用 `CheckpointLoaderSimple` 的 MODEL／CLIP／VAE，不要求額外模型自訂節點；ComfyUI 的獨立 venv、Python／PyTorch 版本及實際載入結果見 [既有 RTX 3060 驗收](../validation/pony-v6-xl-rtx3060.md)。這是執行依賴與既有成功證據，不能替代內嵌元件的授權來源證明。平台依賴鎖定在 `requirements.lock.txt`，與引擎環境分開。

本次 69 項既有安裝、provenance、模型登記／預設及生成驗收回歸通過（1 項既有 Windows 權限條件跳過）；`python -m scripts.install_model pony-v6-xl --check` 唯讀預檢通過，沒有重新下載／修改權重、重寫舊 provenance、修改正式 DATA 或重新生成。manifest 原下載修訂、大小與權重 SHA256 保持不變；未核實標記會隨新安裝的 provenance 原樣保存。

```powershell
.\.venv\Scripts\python.exe -m unittest backend.test_model_install backend.test_animagine_install backend.test_model_profiles backend.test_model_metadata backend.test_generation_acceptance backend.test_animagine_acceptance
.\.venv\Scripts\python.exe -m scripts.install_model pony-v6-xl --check
```

本次取得的原始參照文本及公開 API 回應留在忽略的 `runtime/m01-license-primary-sources.json`，固定 HF README／tree 回應另留於 `runtime/m01-license/`，不把模型全文、輸出圖片或使用者資料加入 Git。可追溯結論、原文連結與指紋已記於本頁及 manifest；可變來源需依查核日期判讀。
