# F02：FLUX 四元件條款與來源查核

查核日期：2026-10-25。對象限 [固定四份權重](../../models/flux1-schnell-plan.json)；逐一來源、修訂、全文／模型卡的 bytes 與 SHA256 見 [查核清冊](../../models/flux1-schnell-terms.json)。權重本體的完整 hash 驗證見 [F01](../validation/flux-installation-20261025.md)，不能以文件 hash 代替。

2026-10-26 的 [M02 補查](flux-encoder-lineage-followup-20261026.md)另補發布提交、本機指紋及 CLIP 全部 196 張量與候選 OpenAI 固定修訂的 F32 → F16 數值吻合；這是新增證據，沒有回寫本頁 2026-10-25 的歷史判斷，也沒有確認發布者實際上游／recipe 或適用條款。完整來源鏈旗標仍為 false。

| 元件 | 已核對的來源與條款 | 保留的條件／缺口 |
| --- | --- | --- |
| schnell 主模型 | BFL 固定 HF 模型卡、檔內 Apache-2.0 標記、BFL 的完整 Apache-2.0 條文 | HF 來源有帳號／存取條件；模型卡另列用途要求，須一併保留 |
| VAE `ae` | 檔內 Apache-2.0 標記；BFL 官方 README 明確說明 autoencoder 權重亦為 Apache-2.0 | 固定來源仍須 HF 存取；不因其他 dev 變體同名就改套 dev 主模型條款 |
| CLIP-L | 固定整合模型卡標記 Apache-2.0；BFL 參考實作指定 `openai/clip-vit-large-patch14`，OpenAI CLIP 專案完整 LICENSE 為 MIT | 整合來源沒有提供本檔的確切上游 revision／轉檔履歷；沒有證明它逐張量等同該上游版本 |
| T5 FP8 scaled | 固定整合模型卡標記 Apache-2.0；BFL 參考實作指定 `google/t5-v1_1-xxl`，Google 模型卡標記及 T5 完整 LICENSE 為 Apache-2.0 | 固定 FP8 scaled 檔缺少可追溯的原始 revision／轉換腳本／參數；不以標籤當成整條來源鏈已驗證 |

## 一手依據與條件

- [BFL 固定 HF 模型卡](https://huggingface.co/black-forest-labs/FLUX.1-schnell/blob/741f7c3ce8b383c54771c7003378a50191e9efe9/README.md)已由使用者完成存取後讀取，3,681 bytes；該修訂沒有獨立 LICENSE 檔。模型卡列出 schnell 的個人／科學／商業用途與限制，另列禁止違法、侵害未成年人、散布有害個資／虛假內容、騷擾、非自願裸露及影響權利的全自動決策等用途。這些模型卡要求與 Apache 本文分開記錄，沒有將模型卡只縮成授權標籤。
- [BFL 官方 README](https://github.com/black-forest-labs/flux/blob/802fb4713906133fcbd0d8dc5351620ca4773036/README.md)區分各變體，並明確說明 autoencoder 權重為 Apache-2.0；[schnell 完整條文](https://github.com/black-forest-labs/flux/blob/802fb4713906133fcbd0d8dc5351620ca4773036/model_licenses/LICENSE-FLUX1-schnell)已讀完。本文列出的散布條件包括附授權、標明修改、保留相關聲明及適用 NOTICE；另有專利、商標及免責條款，不把 Apache 名稱解讀為所有用途／第三方權利已獲保證。
- [固定整合來源](https://huggingface.co/comfyanonymous/flux_text_encoders/blob/6af2a98e3f615bdfa612fbd85da93d1ed5f69ef5/README.md)僅 249 bytes，說明 DualCLIPLoader 並標記 Apache-2.0，沒有原始權重版本或完整轉換紀錄。[BFL 編碼器參考原碼](https://github.com/black-forest-labs/flux/blob/802fb4713906133fcbd0d8dc5351620ca4773036/src/flux/util.py)提供上述上游模型 ID；這是官方參考依賴，不能直接當成固定整合檔已完成來源證明。
- [OpenAI CLIP 完整 MIT 條文](https://github.com/openai/CLIP/blob/d05afc436d78f1c48dc0dbf8e5980a9d471f35f6/LICENSE)包含保留版權及許可聲明與免責要求；[固定上游模型卡](https://huggingface.co/openai/clip-vit-large-patch14/blob/32bd64288804d66eefd0ccbe215aa642df71cc41/README.md)另列研究用途、部署／語言限制與偏誤，分開保存，未把模型卡的用途描述改寫成額外 MIT 條款。
- [Google T5 完整 Apache-2.0](https://github.com/google-research/text-to-text-transfer-transformer/blob/42909aa15d1fbd16c69333aa474a00ae8ed9fde4/LICENSE)及 [T5 v1.1 XXL 固定模型卡](https://huggingface.co/google/t5-v1_1-xxl/blob/3db67ab1af984cf10548a73467f0e5bca2aaaeb2/README.md)已核對；模型卡說明預訓練範圍與下游用途限制，不代表 FP8 轉換歷程已取得。

## 程式中的狀態

`license_review.source_terms_reviewed=true` 表示已記錄來源聲明、完整參考條文及缺口。主模型／VAE 的 `terms_verified=true` 限於可追溯作者來源與這次條款查核，並非對個別下游用途或所有第三方權利的認證。CLIP-L／T5 的確切轉檔鏈仍未知，`terms_verified=false`、`conversion_lineage_verified=false`；清冊的整體來源鏈驗證亦為 false。

新安裝的 provenance 使用這些逐元件記錄，模型庫顯示相應名稱與限制。F01 當時的側錄仍保存原本「尚未查核」狀態，不自動回填歷史。編碼器追溯缺口另列 [M02](../../ROADMAP.md#m02)，不隱藏於已完成的 F02；本清冊不涵蓋整個平台、所有 tokenizer／套件及輸入圖片的授權。
