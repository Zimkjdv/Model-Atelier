# F04：Schnell LoRA 與原圖重繪

這兩種流程各自實作、各自驗收，皆使用 [F03 固定四元件與 512 配置](flux-workflow.md#generation-acceptance)。目前支援固定 PVC LoRA 的模型權重套用，以及原生 VAE 圖生圖；Redux、IP-Adapter、身份參考、多 LoRA、LoRA＋圖生圖混用及未知組合維持停用。技術證據見 [F04 實測](../validation/flux-extensions-20261025.md)。

## 先完成安裝與登記

1. 完成 [四元件安裝及完整驗檔](flux-installation.md)，啟動本機 ComfyUI 與平台。
2. 在專案目錄下載固定 LoRA；新增約 164 MiB，不需要新的推論套件：

   ```powershell
   .\.venv\Scripts\python.exe -m scripts.install_model flux-schnell-pvc-style-lora --check
   .\.venv\Scripts\python.exe -m scripts.install_model flux-schnell-pvc-style-lora
   ```

   沿用既有安裝器的續傳、獨占鎖、完整 SHA256 及不覆寫正式檔規則。權重與 provenance 保留在 ignored runtime，不進 Git。
3. 到模型庫同步 FLUX 元件及 LoRA。按本機完整驗檔結果登記四元件的 `revision <完整 commit>`、SHA256；主模型架構為 FLUX。LoRA 登記如下：

   | 欄位 | 固定值 |
   | --- | --- |
   | 名稱 | `flux-schnell-pvc-style.safetensors` |
   | 架構 | `flux` |
   | 版本 | `revision 183e446eaf99fe2954db8810aa2cf440db325f5d` |
   | 大小 | `171969920` bytes |
   | SHA256 | `0864bb5162a05a69e26362450d6e35834ca1b674beb49bdc9c45509073f7e4ed` |

   四元件的來源與 hash 見 [F01](flux-installation.md)及 [固定清單](../../models/flux1-schnell-plan.json)。登記資料不會替你驗檔；檔案更換後必須重驗，不能只改名字。

## 從介面操作

1. 進入「創作工作台」→「FLUX.1 [schnell]」→「FLUX LoRA／圖生圖」。此頁與純文生圖各自保留表單及未確認請求。
2. 選「Schnell PVC LoRA」，確認固定 LoRA 名稱，設定模型強度 0–1。實測對照為 0 與 0.7，CLIP 強度固定 0；提示詞可加入 `pvc figure`。這不是通用 FLUX／SDXL LoRA 自動相容工具。
3. 或選「VAE 圖生圖（構圖重繪）」，在素材庫匯入原圖，從分頁選項選擇一張未封存素材。設定等比補白或拉伸，以及 0.05 以上、小於 1 的重繪強度；本輪實測為 0.6。輸入會正規化為 512×512 RGB PNG，再編碼為 FLUX latent。
4. 填入提示詞與字串 seed。此版尺寸／步數／精度固定為 512×512、4 步、FP8 e4m3fn、CPU 編碼器；其他配置不默默套用。可以保存完整附加草稿、另存、匯出原始 JSON，再明確生成。
5. 任務或作品的「載入原設定」會回到此頁，保留 LoRA 強度或原圖 ID／縮放／重繪設定。若有未保存內容，先確認再取代。原始 PNG、輸入前處理 hash、元件、LoRA 與環境快照隨任務保存；引擎離線時仍可讀取已保存作品。
6. 提交回覆遺失時，只恢復原 UUID／原端點；不以目前表單建立替代請求。修正失敗設定後，才明確按生成建立新 UUID。原圖上傳回執未知時不自動再上傳。

附加草稿使用獨立版本格式與 revision 衝突保護。一般設定交換檔暫不接收這兩種流程；請使用本頁完整草稿、原任務／作品還原及原始工作流程下載。圖生圖的 JSON 預覽含預覽 UUID 路徑，**不包含原圖，也不會自動上傳**；需要素材時由平台建立新任務處理。

## 實作來源與範圍

- [固定作者模型卡](https://huggingface.co/p1atdev/flux.1-schnell-pvc-style-lora/blob/183e446eaf99fe2954db8810aa2cf440db325f5d/README.md)記錄此 LoRA 直接以 Schnell 與訓練 adapter 訓練。使用其公開權重驗證相容性，沒有在本機重新訓練，也沒有載入該訓練 adapter 做推論。
- 直接連接 [固定 ComfyUI 原生節點](https://github.com/Comfy-Org/ComfyUI/blob/15eb748b3ec5f8a0a2d470b7fb280e2d7579f916/nodes.py)：`LoraLoaderModelOnly` 只修改 diffusion model；`LoadImage → VAEEncode → KSampler → VAEDecode` 使用 FLUX 本身的 VAE。平台只建立及驗證 graph，沒有複製另一套推論引擎或新增自訂推論節點。
- [ComfyUI 圖生圖教學](https://docs.comfy.org/tutorials/basic/image-to-image)說明原圖 latent 與 denoise 的關係；官方範例所用的 SD 1.5 不能作為 FLUX 驗收。此處另以真實 Schnell GPU／HTTP 流程測試。

模型卡宣告 Apache-2.0，但固定倉庫沒有獨立 LICENSE 全文，也未完整證明所有訓練資料權利鏈；[manifest](../../models/flux-schnell-pvc-style-lora.json) 的 `terms_verified` 保持 false。模型卡已閱讀，SHA256 固定；技術相容性不代表授權審查或商用品質完成。CLIP／T5 的既有轉檔來源缺口仍保留 M02。

原圖流程目前只證明來源保存、實際 VAE／取樣執行、構圖影響與完整還原。幾何輸入測試主要保留原圖外觀，不能把像素有差異當成動漫風格轉換成功，更不保證指定角色一致。

## 下一輪圖片提醒

本輪使用自製幾何圖及公開 PVC LoRA，未使用指定作者資料夾訓練。若接著驗證指定作者／棕髮綠眼角色的品質，請提醒使用者先確認 [T02 圖片審查](../validation/training-dataset-20261023.md)，並確認獨立保留圖沒有參與訓練或調參；需要補圖時應明確提醒用途與缺項，不能自動將原先 20 張全視為訓練來源。

## 重跑驗收

```powershell
# 先結束原引擎工作，關閉 managed 8188 引擎；工具不會代為停止使用者服務。
.\.venv\Scripts\python.exe -m scripts.verify_flux_extensions --run
```

沿用 F03 的獨立 DATA／資料庫／loopback 引擎與運算租約；額外讀取固定 LoRA 全檔 hash、安裝第一方唯讀裝置探測與只在測試程序觀察原生 LoRA patch 的掛鉤。它不修改 tensor 或安裝到正常引擎。報告保存在 `runtime/flux-acceptance/<UUID>/`；只停止自己的服務。

驗收依序提交零強度 LoRA、0.7 LoRA，以及兩張不同構圖的自製幾何原圖。檢查真實 patch 數與 RGB 像素 hash，而非只比較帶有不同 workflow metadata 的 PNG bytes。四案例各提交一次，保存後關閉引擎，只用 GET 再核對原作品與完整來源快照。RTX 4080、較大尺寸、32 GiB RAM 與訓練仍需分開驗證。
