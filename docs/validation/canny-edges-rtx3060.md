# Canny v2 邊緣輸出／兩 seed × 兩強度 RTX 3060 驗收（2026-10-09）

Animagine XL 4.0 Opt＋固定 SDXL Canny 1.0 FP16 完成四個真實 CUDA 任務，保存實際條件 PNG、唯一生成作品、完整 workflow／來源／控制版本與精確 seed。引擎離線、登記版本變更及平台重啟後，四份 GET-only 報告全部通過，沒有重送生成。這是固定整合及差異觀察，不是通用品質排名。

## 固定來源與環境

控制模型沿用 [上一輪固定來源](checkpoint-canny-rtx3060.md)，官方 Hugging Face diffusers/controlnet-canny-sdxl-1.0、修訂 eb115a19a10d14909256db740ed109532ab1483c、1.0 FP16、2,502,139,136 bytes、SHA256 b2e7d3921058a442cc80430d1ec8847f42599c705e2451c95e77cf4dcf8d6c25。本輪每次生成前全檔驗證控制權重與 Animagine 權重；沒有新增下載。Animagine 4.0 Opt 來源與固定 SHA256 見 [manifest](../../models/animagine-xl-4.0-opt.json)。

RTX 3060 12 GiB、RAM 68,654,481,408 bytes、NVIDIA driver 616.56；ComfyUI 0.34.0、Python 3.12.10、Torch 2.14.0+cu130。NORMAL_VRAM、DynamicVRAM、CPU async offload；checkpoint／CLIP／ControlNet FP16、VAE bfloat16。原生 Canny 節點版本未知，不從引擎版本推測。

768 × 768、20 steps、CFG 5.5、dpmpp_2m／karras、denoise 1、空 latent、batch 1、無 LoRA、Canny 0.4／0.8、作用 0–1。兩個超過 JavaScript 安全整數的 seed 以字串保存，graph 為精確整數。提示為 single red wooden chair, empty room, three quarter view, clean illustration, daylight, no humans，保留 Animagine 品質前綴。素材為上一輪自製高反差椅子，來源 ID cfde01f5-272d-4d14-b2a4-779c637c5e7d，正規化 PNG SHA256 fb219fb1268aef29671f77ab46dda4a2ea97de11a29ca9aec1b425f246406850；使用 fit 預處理。

## 時間與資源量測

| 案例 | Seed 字串 | 強度 | 提交至成功歷史觀察秒 | 原引擎起訖秒 | 整卡取樣最大 used GiB |
| --- | --- | --- | --- | --- | --- |
| seed-a-strength-05 | 9007199254740993 | 0.5 | 31.906 | 30.591 | 11.131 |
| seed-a-strength-10 | 9007199254740993 | 1.0 | 16.141 | 14.065 | 10.196 |
| seed-b-strength-05 | 9007199254740995 | 0.5 | 16.141 | 14.122 | 10.103 |
| seed-b-strength-10 | 9007199254740995 | 1.0 | 16.094 | 14.037 | 10.014 |

第一個案例為本輪冷載入；其餘沿用同一引擎的模型快取，不能用此表推論強度造成加速。平台耗時包含佇列、網路、查詢及取樣，引擎起訖包含模型載入與快取；整卡記憶體取樣不是任務專用峰值，也不是最低 VRAM 需求。477 項測試回歸在第三個案例期間於平台 Python 環境執行，仍可能影響 CPU／I/O，未視為純 GPU benchmark。

## 實際邊緣與作品觀察

v2 十二節點保留完整 graph，節點 13 的 Canny tensor 同時接到控制條件與 SaveImage 16；只有節點 7 是作品。四份邊緣 PNG 都是 768² RGB 二值，4,384 白色像素／589,824 像素（約 0.743%），解碼 RGB 像素 SHA256 均為 202545d148f9816a6fdde938e946d5d410241c345e1b05ae731e964d444a634c。這表示本次四個案例使用相同邊緣像素；像素比例不是品質分數。

各 PNG 含不同流程 metadata，因此檔案 SHA256 不同，不能宣稱原始檔案逐位元相同：
- seed-a-strength-05：4847e42e8058a90ca965f875940df3e7d90c3885c2af57e33300b38f1df52886
- seed-a-strength-10：eaea317336cfd5bb2072420089f044c31a2a5b6de3bf68bc0245ae01df1f2099
- seed-b-strength-05：ce449e65ac525ac09a9aea2a42330366f3345a2aa4e7428218cb9134321cc38c
- seed-b-strength-10：5330a2b2d63a55697646813d45f496a2a25a5128a1429ad417ae3e09a8dc1d84

肉眼觀察：A／0.5 為較厚紅棕色椅框、填滿椅背與座面，新增大窗、木地板及強烈光影；A／1.0 更接近細線輪廓，但成為中空細框椅，沒有木質椅背／座面。B／0.5 把部分大輪廓解讀成背景門窗框，椅子縮小；B／1.0 回到較大細框椅，也仍是中空線框與強烈陰影。較高強度在這兩個 seed 的輪廓較接近來源，但沒有滿足完整材質／場景要求。未量測邊緣對齊分數，未宣稱高強度普遍較好、畫風或角色鎖定。其他提示、Pony v2／LoRA、SD1 控制權重及 RTX 4080 待實測。

## 保存與恢復證據

| 案例 | 原任務 UUID | 作品 UUID | 作品 PNG SHA256 |
| --- | --- | --- | --- |
| seed-a-strength-05 | 99ef3d4a-5a44-41e2-9652-00b98aa68305 | 9a814d55-d2d4-50f1-a3e7-dd571c44aee3 | 7dee950483b1852110a65471665efa5a5014cfc39190a6938f723cb391238f24 |
| seed-a-strength-10 | cd3e553d-21c8-4331-88cc-e823a103c8c0 | 3da0df07-e220-596c-b111-8a5336986986 | ec8108a76eface0a87749379727d530a2d5dbd44703d106221b4cc89a7f23353 |
| seed-b-strength-05 | 6105286a-6005-4f66-9598-f3870b4048cf | c21811f6-f8aa-5289-90c0-1115b018126a | b0cb53607c1153f98ea41def84b74b293bbe93724377e61c3a3bbc996f6c60e6 |
| seed-b-strength-10 | 34f6e337-5406-4abb-87a7-32683f042402 | 39749c27-5dc7-58ef-bf32-30b74a5d8494 | b79d5d44bc7e4e91a0350ee78f335c414771483f34000f19f1d5787fcc9239b8 |

首次 A／0.5 生成及作品保存成功，但邊緣匯入拒絕 Windows 歷史的反斜線子目錄；修正僅接受相同 UUID 的固定目錄兩種分隔符，仍拒絕 ..、重複分隔符及外部目錄，保存／請求原歷史拼法。保留首次失敗報告與原 UUID，再明確匯入原 output，沒有再次 /prompt。CLI 也修正整數 0／1 與 API 浮點 0.0／1.0 的序列化比對，驗證／報告使用原完整 graph。首張提交設定與原時間保留，不把匯入修復時間混入 GPU 耗時。

關閉 ComfyUI 後，四個原 UUID／原設定恢復均 200、改強度均 409，重複保存邊緣 imported=false；沒有新增任務。隔離控制登記改為 changed-after-comparison，還原仍保留原 1.0 FP16 快照。四份 CLI --verify-report 僅 GET 核對成功；平台再停止／重啟後重做，完整任務 JSON 仍等於原資料：
- seed-a-strength-05：8f63e8ea84fb378cdfef82d98143ea952957e9c82dd9ed7a19dce2dbcf754295
- seed-a-strength-10：eafc5243f7ea1bba24096ea5163fac62d51db5369b631e999a1ed5b259aee032
- seed-b-strength-05：5b133e079781f91ff711cc180871e6122a82031e8969fb0781c0f48b37522868
- seed-b-strength-10：d98e8e15266179b2900bad43c3c7d60326880546a2c2958214607f1ca5034cf2

隔離資料 runtime/control-compare-live-data-20261009 保留 1 素材／4 任務／4 作品／4 邊緣記錄，報告 runtime/control-edge-<profile>-20261009.json、control-compare-recovery-20261009.json；首次失敗在 control-edge-seed-a-strength-05-first-import-failed-20261009.json。runtime 不納入 Git，備份需保留整份隔離 DATA，包含 SQLite、素材、處理輸入、作品與 control_edges；檔案遺失不自動覆寫或補生成。

正式資料仍為 5 任務／3 作品／0 素材／0 草稿／0 比較方案，13 個 settings key 指紋前後均為 31af66ed1db203c808bee110c1007a8307ae23867df29b259636f0837502a6eb。8000／8001／8188／5173 均停止。

## 程式驗證與限制

新增五項 v2 CLI 測試及一項 Windows 實際子目錄契約測試，涵蓋四組精確設定、回應遺失不重送、GET-only、異常／缺失／改變邊緣證據、未知來源與不同 profile 拒絕；477 項後端（476 通過、1 項既有 Windows 權限 skip）。Canny v1／v2 pending、來源檢查及 Vue 型別／production build 通過，既有遮罩／比較檢查通過。

瀏覽器控制工具本輪 Node kernel 無法啟動，畫面操作／下載點擊及窄視窗仍待驗收。保存的是已提交任務的實際條件圖；未提交表單的即時邊緣預覽仍未提供。
