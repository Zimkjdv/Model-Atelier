# Canny CPU 預覽與 RTX 3060 原生邊緣驗收（2026-10-22）

本輪驗收分為四個全新原生 Canny 邊緣案例、四個既有 v2 擴散任務的原邊緣離線比對，以及工作台／歷史／下載／還原操作。新案例只跑 LoadImage → Canny → SaveImage，未載入擴散模型、未新增平台生成任務或作品；不代表額外的動漫生成品質驗證。

## 環境與來源

RTX 3060 12 GiB、RAM 68,654,481,408 bytes、NVIDIA driver 616.56；ComfyUI 0.34.0／Python 3.12.10／Torch 2.14.0+cu130／Kornia 0.8.3／Pillow 12.3.0。原生 Canny 的獨立節點版本未知；已核對本機源碼 SHA256 `5efd352d92d7749b7b9734a1676fee18f4431d44a8e9477822a7a8f38ad26051`。啟動日誌與 /system_stats 確認 cuda:0 RTX 3060；節點以該裝置 float32 執行。CPU worker 明確使用 CPU float32，2 個 Torch 執行緒。

椅子來源沿用上一輪自製 PNG，768²、素材 cfde01f5-272d-4d14-b2a4-779c637c5e7d、SHA256 fb219fb1268aef29671f77ab46dda4a2ea97de11a29ca9aec1b425f246406850。第二張為本輪自製 320×192 漸層、圓形及矩形，素材 1768e7aa-1039-497d-9717-1baf7ae08475；使用相同平台前處理產生 PNG，CPU provenance input SHA256 與上傳 GPU 的 bytes 相符。各案例完整設定、來源 hash、workflow、預先保留 UUID、原生 history、PNG bytes 與像素 hash 保存在忽略的 runtime/canny-native-preview-*-20261022.json 及 .cpu.png／.native.png。

## 實際差異

| 案例 | 輸出尺寸 | 低／高閾值 | 不同像素 / 總像素 | CPU／GPU 白色像素 | CPU／原生端到端秒 |
| --- | --- | --- | --- | --- | --- |
| chair-fit | 768 × 768 | 0.4／0.8 | 0 / 589824 | 4384／4384 | 2.591／0.677 |
| gradient-fit-low | 768 × 512 | 0.01／0.05 | 51 / 393216 | 6307／6312 | 4.482／0.622 |
| gradient-stretch-low | 768 × 512 | 0.01／0.05 | 15 / 393216 | 5530／5529 | 4.289／0.510 |
| gradient-stretch-high | 768 × 512 | 0.4／0.8 | 0 / 393216 | 2666／2666 | 5.026／0.406 |

兩個低閾值案例分別有約 0.0130% 與 0.0038% 像素不同；保留結果，不調整閾值或覆寫成相同。僅能觀察到不同運算裝置下的數值差異，沒有進一步隔離其浮點誤差來源。因此介面明確標示近似預覽，不保證與 GPU／其他版本／遠端引擎逐像素相同。這些少量案例不構成通用誤差上限或品質分數。

CPU 秒數含每次新 Python 匯入與圖片處理；原生秒數含 HTTP 提交與歷史輪詢，使用同一持續運行引擎，沒有做嚴格冷／熱快取控制。不可用此表推論硬體速度倍率或完整擴散生成耗時。

- chair-fit：原生引擎 UUID `fd9335f3-730f-4de2-bfa7-2e1929392e98`；CPU RGB `202545d148f9816a6fdde938e946d5d410241c345e1b05ae731e964d444a634c`；GPU RGB `202545d148f9816a6fdde938e946d5d410241c345e1b05ae731e964d444a634c`。
- gradient-fit-low：原生引擎 UUID `5b7c7164-d0f7-4ee6-ae4a-3bb15d365517`；CPU RGB `67b004e77c1e70e5ddd7aab3f7c280a5bca50ab6f5cdac5d750f90f2455c2c08`；GPU RGB `b7697daeb387454bde941f8301c98eeb66a3deb859c781610d286f74a4dc2acf`。
- gradient-stretch-low：原生引擎 UUID `a139cd97-0ad3-4e7d-bcb8-878788b2845a`；CPU RGB `0cbb4beed238dad95965299f5fe455bbed313be40f0ae9f3ac5b161e01e3c9e7`；GPU RGB `f4af6eb422f69d7d2a878394ebd4385b245df33e53a7752ef954880b4513255a`。
- gradient-stretch-high：原生引擎 UUID `f66da7cc-bb27-4699-871a-55e70814bea0`；CPU RGB `ba491855e21c27917e5485a68442f751759c9b03356df67ecd4db7c81889f13e`；GPU RGB `ba491855e21c27917e5485a68442f751759c9b03356df67ecd4db7c81889f13e`。

## 既有原任務與離線重啟

以新 CLI 對上一輪 Animagine v2 的 A／0.5、A／1.0、B／0.5、B／1.0 各計算一次 CPU 預覽；四份都與原任務保存邊緣相同：4384 白色像素、RGB SHA256 `202545d148f9816a6fdde938e946d5d410241c345e1b05ae731e964d444a634c`。原 PNG 含 workflow metadata，檔案 hash 與 CPU PNG 不同是預期結果，未宣稱檔案相同。

```powershell
.\.venv\Scripts\python.exe -m scripts.verify_canny_preview --platform http://127.0.0.1:8001 --job-id 99ef3d4a-5a44-41e2-9652-00b98aa68305 --report runtime/canny-preview-old-a05-20261022.json
# 已存在證據只做 GET；不重算 CPU、不匯入邊緣、不發 prompt。
.\.venv\Scripts\python.exe -m scripts.verify_canny_preview --platform http://127.0.0.1:8001 --job-id 99ef3d4a-5a44-41e2-9652-00b98aa68305 --report runtime/canny-preview-old-a05-20261022.json --verify-report
```

報告及 CPU PNG 排他寫入；原任務、原邊緣、處理後來源、版本／參數、hash 或比較量測不同均拒絕。ComfyUI 關閉且平台重啟後，四份 --verify-report 全部通過。完整四份原任務與作品物件仍等於隔離複製前資料；沒有補生成或更新歷史。

## 瀏覽器與資料保護

實際 IAB 驗證引擎離線／無模型預覽、來源與閾值變更／計算途中失效、非法閾值、KeepAlive 清理；工作台及作品對話框在 390×844 均無橫向溢出。任務及作品顯示同一原邊緣 768²／4384 像素；實際下載 PNG SHA256 `5330a2b2d63a55697646813d45f496a2a25a5128a1429ad417ae3e09a8dc1d84` 與原保存紀錄一致。載入原任務設定後 seed `9007199254740995`、強度 1、閾值 0.4／0.8、768²、原素材 ID 完整還原；重啟後可再次離線預覽。截圖在 runtime/canny-preview-mobile-20261022.jpg、canny-preview-restored-20261022.jpg。

隔離資料為 2 素材／4 既有任務／4 既有作品／4 既有邊緣；四個新原生測試任務只存在 ComfyUI 的專用 model_atelier_preview_validation/UUID 目錄。正式資料仍為 13 settings key、5 任務／3 作品，指紋 `31af66ed1db203c808bee110c1007a8307ae23867df29b259636f0837502a6eb`。未將本地測試素材／報告／權重提交到 Git。

新增五項比較 CLI 測試及一項程序最大 frame 邊界回歸；完整後端 510 項（509 通過、1 項既有 Windows skip），前端邏輯／型別／建置通過。測試結束後 8000／8001／8188／5173 停止。本輪不涵蓋觸控筆刷、真正遺失回應的 pending、Pony v2／其他 LoRA、depth／pose／adapter、FLUX 權重存取或 RTX 4080。
