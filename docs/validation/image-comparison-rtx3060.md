# 圖生圖 denoise 比較與方案關聯驗收（2026-10-22）

Pony V6 XL、Animagine XL 4.0 Opt 各完成 denoise 0.3／0.6 一次真實 CUDA 圖生圖，共兩個保存方案、四個任務與四件作品。各 CLI 呼叫只送一組，原 UUID 在提交前保存；回應不明不重送。這是固定流程整合與品質觀察，不代表畫風或角色鎖定。

## 固定條件

使用既有兩個模型 manifest，每次生成前完整校驗本機權重大小與 SHA256。RTX 3060 12 GiB、RAM 68,654,481,408 bytes、driver 616.56、ComfyUI 0.34.0、Python 3.12.10、Torch 2.14.0+cu130。啟動日誌觀察到模型／CLIP float16、VAE bfloat16、NORMAL_VRAM、DynamicVRAM、CPU async offload 2 streams；一般任務的結構化快照只保留引擎明示旗標，未將日誌人工觀察回填成自動精度或冷熱證據。

同一張自製 768² 高反差椅子、fit、20 steps、CFG 5.5、dpmpp_2m／karras、batch 1、無 LoRA，seed 字串 9007199254740993。兩個模型各用自己的品質前綴，其後相同：single red wooden chair, empty room, three quarter view, clean illustration, daylight, no humans。來源素材 a1c3579d-542c-4c79-b8c9-b4ba7c8dfe41，PNG SHA256 fb219fb1268aef29671f77ab46dda4a2ea97de11a29ca9aec1b425f246406850；每個任務保存相同處理後 PNG 的 hash／bytes 與前處理版本。

Pony 方案 3e27bc4d-50c5-48a7-84cd-95a7583e5bad，Animagine 方案 53b08137-e8bf-4f76-a519-04a2a45793f9；各方案只有 denoise 軸 0.3、0.6。任務／作品凍結 plan ID、hash、variant、完整設定與模型版本；原圖、前處理、八節點完整 workflow 及精確 seed 均核對。

## 觀察

| 案例 | 提交至成功歷史秒 | 原引擎起訖秒 | 整卡取樣最大 used GiB | 平均 RGB 絕對差 | 有變動像素 / 589824 |
| --- | --- | --- | --- | --- | --- |
| pony-03 | 27.844 | 26.936 | 9.621 | 1.979179 | 586882 |
| pony-06 | 11.812 | 10.147 | 9.460 | 2.496207 | 585986 |
| animagine-03 | 27.969 | 25.889 | 9.705 | 1.105929 | 498232 |
| animagine-06 | 11.922 | 10.107 | 9.626 | 1.709089 | 397518 |

每個模型的 0.3 為本輪首次載入；0.6 沿用同一引擎及模型快取。時間含載入、佇列、HTTP 與查詢，不能據此判定較高 denoise 更快。整卡取樣不是連續或任務專用峰值，也不是最低 VRAM。

四張都大致保留白底黑線椅子；Pony 0.6 的線條較彎、略有雜訊，Animagine 0.6 有較粗線條及右側接角變形。兩模型均沒有依提示生成紅色木質實體椅子與房間。平均差值主要反映線條及背景小幅像素變化，變動像素多不代表品質好；不能泛化為任一 denoise 的最佳值或保證素材精確保留。未測量語意相似度、畫風或角色一致性分數。

- pony-03：任務 `f56da87f-622f-4136-9ab6-e2d190d2fa22`、作品 `3b2813b1-d3e5-5416-9204-76773e1e8d60`、PNG SHA256 `f6909bd425d425317b000d308cd4cb5a0532a7fdeccb29d1528806700c5d7da9`。
- pony-06：任務 `9ac8eea2-21d1-4490-a147-809ef1c4f73f`、作品 `5cd6fc1b-db29-5b7c-8d89-59b54231d9cf`、PNG SHA256 `2d021dccec4c4eea91ea860d9966c208182d6f6595e3b2323cdbd795263c55ec`。
- animagine-03：任務 `b9544801-77b3-40de-8278-9af95e36b14c`、作品 `3a4b5760-4535-5d55-af21-bc341778cea4`、PNG SHA256 `b7d52118d7367610b8c0800dc8b92a3ad03d39c3b1924a3d4b85816fa3abdae2`。
- animagine-06：任務 `3ffe0d05-76f3-436d-97aa-03f396b3cb29`、作品 `33b8bf37-a840-51c7-b06c-19475d7f590c`、PNG SHA256 `7938614c4fef0c7a286ffc475fd8887cdfe5789976247dfc0dd943ecc4dfc9ce`。

## CLI 與離線恢復

先經既有 API 預覽／保存上列固定方案，再逐組呼叫：

```powershell
.\.venv\Scripts\python.exe -m scripts.verify_image_comparison --platform http://127.0.0.1:8001 --model pony-v6-xl --source-id a1c3579d-542c-4c79-b8c9-b4ba7c8dfe41 --plan-id 3e27bc4d-50c5-48a7-84cd-95a7583e5bad --denoise 0.3 --report runtime/image-comparison-pony-03-20261022.json
```

其他三次明確改 model／plan ID／denoise 與不同報告檔名；不以 CLI 自動批次。報告已存在拒絕新生成。相同指令加 --verify-report 僅 GET 原方案、完整任務／作品／前處理／結果關聯與圖片；不同步清單、不查引擎、不補生成。方案封存不影響歷史核對，新生成仍拒絕。

引擎關閉、平台停止並重啟後，四份 GET-only 驗證全數通過，完整任務物件未變。隔離 runtime/image-comparison-live-data-20261022 為 1 素材／2 方案／4 任務／4 作品；正式資料仍 13 settings key／5 任務／3 作品，指紋 31af66ed1db203c808bee110c1007a8307ae23867df29b259636f0837502a6eb。CLI 報告、圖片、權重與資料庫不提交 Git。

五項新測試涵蓋兩個 profile、提交回應遺失只恢復原 UUID、封存／權重失敗、非法報告不連線、來源改變與 GET-only 以及差值語意。完整後端 521 項（520 通過、1 既有 skip）。新比較結果報告與瀏覽器驗收接續第三項；更多素材、seed、作者提示、LoRA、inpainting／adapter 與 RTX 4080 尚待評估。
