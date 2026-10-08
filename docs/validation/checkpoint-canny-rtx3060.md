# SDXL Canny／RTX 3060 固定驗收（2026-10-09）

Pony V6 XL、Animagine XL 4.0 Opt 各一個真實 CUDA 任務，原生 Canny、固定官方 ControlNet FP16 成功生成及匯入。原 UUID 恢復、控制登記變更提示及平台重啟後 GET-only 完整核對通過。這是固定整合驗收，不是跨 seed 的品質或最低硬體需求證明。

## 固定來源

[官方 SDXL Canny 模型卡](https://huggingface.co/diffusers/controlnet-canny-sdxl-1.0/blob/eb115a19a10d14909256db740ed109532ab1483c/README.md)：版本 1.0 FP16、完整修訂 `eb115a19a10d14909256db740ed109532ab1483c`，遠端 diffusion_pytorch_model.fp16.safetensors；本機 controlnet-canny-sdxl-1.0-fp16.safetensors。

大小 **2,502,139,136 bytes**、SHA256 **b2e7d3921058a442cc80430d1ec8847f42599c705e2451c95e77cf4dcf8d6c25**。安裝前有約 7.50 GiB 可用，含 2 GiB 預留通過；串流下載、完整驗檔及 provenance 保存，不安裝 .bin／任意自訂節點、不覆寫現有檔案。

模型卡正文及固定 config（cross_attention_dim=2048、text_time）識別 SDXL，實機由 ControlNetLoader 正常載入；模型卡 base_model 標頭與正文矛盾，不用該標頭推測 SD1 支援。授權標示 Open RAIL++，保留 [固定上游條款](https://huggingface.co/stabilityai/stable-diffusion-xl-base-1.0/blob/462165984030d82259a11f4367a4eed129e94a7b/LICENSE.md)。來源及登記不是無限制使用或訓練證明。

Pony／Animagine 權重沿用既有固定 manifest，執行前重新核對本機完整大小及 SHA256；ControlNet 是兩模型共用的結構元件，沒有把它當 checkpoint。

## 條件與環境

- RTX 3060 12 GiB、RAM 約 64 GiB、NVIDIA driver 616.56；ComfyUI 0.34.0、Python 3.12.10、PyTorch 2.14.0+cu130。
- NORMAL_VRAM、動態顯存載入、CPU async weight offloading；checkpoint／ControlNet float16，VAE bfloat16，CLIP float16。不是全模型常駐 GPU。
- 自製 768² 高對比黑白椅子線稿，素材 ID c430da21-fd14-4e72-8137-cee0e88181f8；不存在人像或外部作品來源。
- 768²、20 steps、CFG 5.5、dpmpp_2m／karras、denoise 1、seed **9007199254740993**，無 LoRA。控制強度 0.5、作用 0–1、原生 Canny 閾值 0.4／0.8，fit；這些是固定驗收條件，不是推薦品質預設。
- 提示為單張紅色木椅、空房間、三分之四視角、乾淨插畫、日光；兩模型使用各自前綴，不能把結果當成相同文字輸入的公平模型排名。

| 模型 | 一次提交至成功歷史觀察 | 引擎歷史執行 | 整卡取樣最大已用 VRAM | 圖片 bytes |
| --- | ---: | ---: | ---: | ---: |
| Pony V6 XL | 36.562 秒 | 34.377 秒 | 11.166 GiB | 936,936 |
| Animagine XL 4.0 Opt | 29.734 秒 | 29.033 秒 | 11.238 GiB | 602,534 |

前者含佇列、HTTP、載入／同步及觀察延遲；後者含引擎載入及快取，皆非純 GPU benchmark。Pony 是引擎冷啟動後首張，Animagine 接著跑、可能沿用控制／VAE 快取，耗時不可直接比較。顯存為約 2 秒整卡取樣，含其他程序／快取，未量測任務獨占峰值或最低顯存。

## 原圖觀察

已查看原素材與兩張保存圖片。兩結果大致沿用椅背、座面與腳的線稿位置。Pony 呈現偏暗的細金屬骨架／半透明座背，沒有達成紅色木材，紋理也不是預期乾淨插畫。Animagine 為紅棕色木質椅與厚框架，接近輪廓，但自行加入窗戶、木地板及強烈陰影；材質與細部仍有差異。

不宣稱精確構圖鎖定、畫風一致或角色鎖定；沒有量測邊緣對齊分數，也沒有把肉眼觀察變成品質通過。此模板目前沒有另存 Canny 邊緣 PNG，來源前處理 PNG、節點與參數／版本快照均保留。

## 持久化與復原證據

| 模型 | 任務 UUID | 作品 UUID | 原圖 SHA256 |
| --- | --- | --- | --- |
| Pony | 44432ef9-c6c9-4e47-bcf7-af1fd03160e9 | 831dbb18-e445-5199-b3d7-41e6448dc936 | 588d3329f716bce6e2e8fe9946788b07f8a620dfec9b6aeaddb0cd5aaad53fbf |
| Animagine | 236e0c60-ec35-48a5-bdaf-0590c2270ce6 | fdd92cbe-5d27-59b8-bf9b-0766640a9ff5 | 90bdad59c34b2e17ff00967d6408eee6cd2b9911cb2c6af9e42b6ef146b22028 |

關閉引擎後，把隔離 ControlNet 登記版本改成 changed-for-recovery。以兩個原 UUID／原設定恢復均 200、與舊完整任務 JSON 相同；同 UUID 改強度均 409。創作還原保留原 1.0 FP16 控制快照並提示差異，不回填新版本。

兩報告在引擎離線時 GET-only 核對成功；再關閉並重啟平台，重做 GET-only 且任務 JSON hash 不變。Pony 任務 hash 2aa90ce9e407d5d84af14ee8ffcc1bb7bb9c6fb1c2f426249d830b2e47fa6e72，Animagine d3054b60a5443c00ab0aa906e9aa69ea5372936f67f83b55687c9a7ab9598b76。没有新增或重送生成。

隔離證據在 runtime/control-live-data-20261009（1 素材／2 任務／2 作品／0 草稿／0 方案）、control-pony-20261009.json、control-animagine-20261009.json、control-recovery-20261009.json、control-inputs-20261009.json。runtime 不納入 Git，備份由使用者持有；此文件保留來源、條件、ID 與雜湊。

正式資料維持 5 任務／3 作品／0 素材／0 草稿／0 方案，正式 settings 指紋核對不變；模型安裝檔留在 runtime/ComfyUI/models/controlnet。8000／8001／8188／5173 均停止。

## 測試與限制

完整後端 459 項（458 通過、1 項既有 Windows 權限跳過），新增 8 項 CLI／安裝測試；非法報告、精確來源／版本、遺失回應不重送、GET-only、修改來源／還原、CPU 降級及控制目錄／續傳／固定来源涵蓋。補強前處理版本不可接受布林值，Canny 表單完整保留 −20～20 的 LoRA 強度，與後端一致。

Canny／既有遮罩／比較前端邏輯及 Vue 型別／建置通過。瀏覽器工具仍因 Node kernel 啟動失敗，實際畫面、下載及窄視窗未验收。SD1 的真實控制模型、SDXL 其他 seed／強度／LoRA 組合、depth／pose、邊緣圖保存、adapter 畫風／角色、FLUX 權重與 RTX 4080 保留後續工作。
