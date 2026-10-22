# 比較結果報告

在創作工作台展開「固定測試集與參數比較 → 保存方案與 JSON 匯入」，重載已保存方案，於結果區按「準備比較結果報告」，再下載 JSON。無需引擎連線；不產生任務或匯入作品。

`GET /api/experiments/plans/{UUID}/report?expected_plan_sha256={hash}` 回傳 kind `model-atelier-comparison-results`、schema_version 1。保存方案及所有明確關聯任務／作品在同一 SQLite 讀取交易取得；不根據相同 seed／流程猜測關聯。核對原 plan hash、完整 context 與組設定、完整 workflow（含 seed 整數型別）、作品原任務。來源有損壞或缺少相符關聯回 409，方案不存在回 404；不匯出部分資料。

報告包含生成時間、原方案及修訂／封存狀態、各組所有保存的任務狀態、workflow／SHA256、版本／LoRA／參考／環境／量測快照，以及作品 hash、尺寸、目前人工評分、筆記與收藏／封存狀態。舊 runtime／量測缺失保持 null，不以目前環境回填。最多合計 100 筆任務與作品、8 MiB，超出回 413；不默默截斷。

檔案存在旗標在 DB 交易後另行檢查，屬存在性觀察；current_file_hash_verified=false，未再次讀取校驗原圖。報告不含原圖 bytes、引擎即時歷史或 API 憑證，也不是可匯入的生成方案／資料備份。任務當時資料與目前人工整理值的時間範圍分開說明。

回應為 application/json、Cache-Control:no-store、nosniff、固定 UUID 檔名及 X-Atelier-SHA256。前端限量串流讀取、驗證 kind／版本／原方案 ID／hash 及整份 bytes SHA256；下載保留原 bytes，不重新 JSON.stringify，完整 workflow 的 64 位元 seed 不受 JavaScript 數字精度影響。來源切換、KeepAlive 離開或卸載取消請求並回收 Blob URL；狀態之後改變需重新準備報告。

## 2026-10-22 驗收

九項新增後端測試涵蓋離線完整快照、不寫 DB、空／封存方案、同內容不同 ID 不推測、錯誤來源與損壞流程／關聯、大小／筆數上限、非匯出作品欄位不消耗預算、舊欄位／缺檔，以及 WAL 並行更新時仍讀取同一原快照。完整後端 530 項（529 通過、1 既有 skip），三組前端邏輯與 Vue 型別／建置通過。

使用 [兩模型 denoise GPU 比較資料](validation/image-comparison-rtx3060.md) 做實際 IAB 驗收：離線重載兩個方案、查看兩個已完成變體與原作品、準備／下載 Animagine 結果報告 22,338 bytes，SHA256 aeebedb45f77b345078c0266fbc47fd37b495c159c789e76bca2e3b756d79fdb。報告包含兩個原任務、各一作品、seed 字串 9007199254740993、denoise 0.3／0.6、新效能條件與來源 hash。此 hash 僅對應該次生成時間的報告；再次準備會產生新的時間與 hash。

原比較方案 JSON 另行下載，plan hash 4ba1b1564ec281b2b06f3498e4127ea27795be44ce1baf7d89c6069c150ed647；貼上後驗證／預覽成功，沒有保存新方案或任務。結果報告貼入方案匯入會被拒絕，原預覽仍可使用；載入 variant-2 後為圖生圖、768²、精確 seed、denoise 0.6、原素材與 Animagine。作品詳細版本區顯示效能條件，實際精度／卸載／冷熱保留未知。

切換 Pony 清除舊報告下載；離開／返回工作台也清除下載。390×844 無橫向溢出（scrollWidth 375），1280×900 結果雙欄（scrollWidth 1265）；截圖與下載證據位於忽略的 runtime/comparison-report-mobile-20261022.jpg、comparison-report-desktop-20261022.jpg、comparison-report-browser-20261022.json。

驗收沒有新增任務、作品、草稿或方案；隔離仍為 1 素材／2 方案／4 任務／4 作品。正式資料指紋不變。測試服務於結束後停止，FLUX 來源存取／其他品質與 RTX 4080 仍待驗證。
