# F04：獨立 LoRA 與 FLUX 原圖重繪實測

日期：2026-10-25。F03 已先以 `6ac8bae` commit／push，才開始 F04；該筆 [GitHub Actions](https://github.com/Zimkjdv/Model-Atelier/actions/runs/40166211208)已確認成功。

本輪完整 GPU run：`32279896-4238-47d1-8bf4-988f8dade41f`；[機器可讀摘要](flux-extensions-20261025.json)、[操作與支援範圍](../models/flux-extensions.md)。

## 實際配置與結果

RTX 3060 12 GiB、約 63.939 GiB RAM，ComfyUI `15eb748b3ec5f8a0a2d470b7fb280e2d7579f916`、Torch 2.14.0+cu130。重新完整驗證四份固定權重及 PVC LoRA，全部 SHA256 相符。四案例均為 512×512、4 步、batch 1、Euler／simple、CFG 1、主模型 FP8 e4m3fn、CPU 文字編碼器，seed 字串 `9007199254740993`。完整參數及元件／來源／版本保留在摘要。

| 案例 | 單次提交至終態 | 實際驗證 |
| --- | ---: | --- |
| PVC LoRA 強度 0 | 51.375 秒 | 原生 model-only loader，0 個 patch |
| 相同配置強度 0.7 | 11.578 秒 | 304 個原生參數 patch；RGB 像素 hash 與零強度不同 |
| 自製房屋原圖 A | 23.094 秒 | FLUX VAEEncode／4 步取樣、denoise 0.6，來源與前處理保存 |
| 相同參數、原圖 B | 7.109 秒 | 房屋位置不同，輸出 RGB 像素 hash 不同 |

時間包含載入、快取、HTTP 與輪詢，不作冷啟動效能比較。LoRA 原檔有 988 個載入權重 key，原生 patch observation 確認 304 個參數被附加；未見 `lora key not loaded`。掛鉤僅讀取回傳的原生 patcher 及 key 數，未改動權重。載入器不修改 CLIP／T5；沒有套用 Schnell 訓練 adapter。

原圖 A／B 由程式繪製簡單房屋，經本平台素材 API 匯入、正規化、完整 SHA256 核對、前處理與一次上傳；沒有使用作者圖或遠端輸入路徑。完整 16 通道 FLUX latent 由本模型 VAE 建立，沒有套用 SDXL latent／IP-Adapter。幾何圖結果主要保留輸入外觀；這項測試證明參考構圖與流程追溯，不是動漫畫風／指定角色品質通過。

四個獨立 UUID 各一次 `/prompt`；每個作品 PNG 及 RGB 像素各自雜湊，檢查來源快照、LoRA 強度、原圖 ID、denoise／resize、完整 graph、字串 seed 與環境。停止自己的引擎後，四個原作品均只用 GET 核對通過，提交計數仍為 4。兩個自有服務已停止，原正常引擎資料庫前後 hash 相同。

本次另外載入第一方 nonce 裝置探測，四個快照皆回報 `available`；未將 F03 測試引擎當時的 `unknown` 歷史記錄改寫。本輪沒有重新量測 RAM／VRAM 峰值、RTX 4080、較大尺寸、多 LoRA 或 LoRA＋原圖混用。

## 來源及條款記錄

固定 [PVC 作者來源](https://huggingface.co/p1atdev/flux.1-schnell-pvc-style-lora/blob/183e446eaf99fe2954db8810aa2cf440db325f5d/README.md)已完整讀取：7,727 bytes，README SHA256 `e62a6145da2653b430f2145ac2074d498f1a57f328b79be012c197062e88b0eb`。作者標示 Schnell 基底與訓練方式，模型卡宣告 Apache-2.0；固定倉庫未找到獨立 LICENSE。權重 171,969,920 bytes，完整 SHA256 `0864bb5162a05a69e26362450d6e35834ca1b674beb49bdc9c45509073f7e4ed`。

來源的訓練資料／全部權利鏈未完整證明，manifest `terms_verified=false`；相容性測試不會改成授權通過。使用 [ComfyUI 原生固定版本](https://github.com/Comfy-Org/ComfyUI/blob/15eb748b3ec5f8a0a2d470b7fb280e2d7579f916/nodes.py)及既有平台保存流程，沒有導入額外推論框架。作者／角色圖片的後續提醒另列於 [操作文件](../models/flux-extensions.md#下一輪圖片提醒)。

## 平台與瀏覽器驗證

回歸涵蓋未知／SDXL／錯誤版本 LoRA 拒絕、混用模式與非有限數值拒絕、固定配置邊界、上傳失敗不提交／重試、原 UUID 讀取、完整離線還原、輸入 PNG 保存讀取、專用清單篩選及草稿 revision 衝突。一般草稿與設定交換不降級接收附加流程。

1440px／390px Chromium 實際操作完整草稿、原 JSON 下載（保留 uint64）、未知 LoRA 停用、遺失回覆的相同 UUID／body／端點恢復、作品庫回到正確子流程，以及原圖草稿及提交。兩個案例都做 axe 全規則檢查及完整頁面截圖；它們使用合成引擎，不當作 GPU 證據。測試另外找出並修正新流程的任務分頁／已保存原圖讀取白名單缺口，以及桌面品牌連結可見字與無障礙名稱不一致。

最終本機檢查：完整 780 項後端測試（1 項既有跳過），另新增驗收工具清理後仍須核對正常引擎資料庫的回歸，包含此項的 38 項相關測試通過（1 項既有跳過）。格式／型別、正式建置與契約測試通過；Chromium 五批合計 122 項通過（21／29／28／35／9），包括修正文案與窄版無障礙名稱斷言後的批次重跑，先前失敗證據保留。1,062 個 Markdown 本機連結均有效；ROADMAP 保留 13 主項／17 子項未完成。
