# 任務耗時與資源取樣

新建任務保存 `measurements` schema 1，任務列表／詳情、SSE 及作品預覽皆沿用同一原紀錄。舊任務和作品顯示未知；GET 不修改 SQLite，刷新舊紀錄也不回填。

| 欄位 | 來源與意義 |
| --- | --- |
| `dispatch_to_observation_seconds` | 平台 UTC 時鐘：首次開始提交 `/prompt` 至首次確認完成／失敗／取消／停止；包含佇列、網路及查詢間隔，排除先前驗證／圖片上傳。未提交或時鐘倒退保持 null |
| `engine_execution_seconds` | 原引擎已核對身分的歷史 `execution_start` 至對應終態事件，毫秒 timestamp 相減；包含模型載入、取樣、解碼與快取，不是純 GPU 推論 |
| `resources_before_submission` | 與版本查詢共用的原引擎 `/system_stats` 單次回報：RAM、各裝置記憶體、來源網址及查詢時間；沒有額外網路探測、張量配置或模型載入 |
| `continuous_resources` | E05 起新任務的背景取樣：原引擎 `/system_stats`，保存成功／失敗／間隔缺口、取樣尾端及全期觀察最高值；可缺少或為 null |
| `task_vram_peak_bytes` | 原介面無法可靠歸屬單一任務，固定 null，不從整卡、allocator、提交前快照或觀察最高值推估 |

引擎時間要求唯一開始／結束、相同 prompt ID、有效整數毫秒、正確結果與順序；缺失、重複、bool、浮點、反向時間、超界或不符結果保持未知。合法零秒／零可用容量不是未知。平台和引擎時鐘各自計算，不跨時鐘相減推估佇列時間。

記憶體快照可能包含可回收快取與其他程序；CPU 使用記憶體標籤。沒有以平台主機 nvidia-smi 補遠端引擎值，也不能以提交前快照當成實際生成峰值或模型最低需求。原始版本快照格式保留，資源另存量測欄位。

初始提交與首次終態量測在任務交易內保存；CAS 衝突不覆寫，原 UUID 恢復不重查版本／資源或提交。終態量測確認後凍結，不因後續讀取延遲而增長。作品匯入複製原量測，重複匯入保留既有值，評分及筆記不改原快照。

## E05 連續觀察的範圍與界限

首次進入 `submitting` 後登記，ASGI lifespan 的背景工作每輪完成後至少等待 2 秒，再查詢該任務凍結的原引擎；不依賴瀏覽器、SSE 或目前設定。同一原引擎的重疊任務共用一個 GET，報告可能相同，不能因此各自認領用量。每次網路查詢最多 2 秒、256 KiB，不跟隨重新導向或環境代理；不提交／取消／停止任務，不重設 allocator peak。

平台最多同時取樣 16 項，每項最多 1 小時／1800 次，保留最近 120 個時間點、最多 16 種裝置身分，另保留全期 RAM／裝置觀察最高值。超限僅停止取樣，不阻擋生成；零次成功即保持未知。失敗只記固定原因，單點值為 null；超過 4 秒的間隔計入 gaps，無法知道未取樣期間的真實峰值。實際週期包含查詢與排程延遲，短任務可能沒有時間點。

RAM 是引擎所在主機的 total−free。裝置數值是引擎回報的 total−free；本次驗證的 ComfyUI CUDA `free` 包含 allocator 可回收快取，**不是 nvidia-smi 的實體整卡已用量**，也不是單一程序／prompt 峰值。CPU／MPS 可能回報主機記憶體，不能加總成 VRAM。PyTorch `max_memory_allocated` 是該程序 allocator 的峰值，自程序啟動或重設起計，不能把其他任務和快取可靠分離；因此本版不更動引擎、不重設共用計數器、不聲稱取得任務專用峰值。參考 [PyTorch 官方定義](https://docs.pytorch.org/docs/stable/generated/torch.cuda.memory.max_memory_allocated.html)及 [NVIDIA 裝置監測說明](https://docs.nvidia.com/deploy/nvidia-smi/index.html)。

取樣 journal 與任務 revision 分開保存，GET 詳情只投影最新取樣，不寫任務。列表／SSE 沿用最近狀態轉移的快照；詳情重新整理可取得最新時間點。首次確認終態時在原交易內凍結並刪除 journal，延遲回應丟棄；作品沿用凍結資料，離線仍可讀。平台正常停止保存部分觀察和 `platform_shutdown`，重啟不再補齊該次取樣；非正常中斷可在 10 秒 lease 到期後接續，時間缺口會記錄。沒有 E05 欄位的歷史紀錄不啟動取樣、不回填。重跑與實機證據見 [E05 驗收](validation/resource-sampling-20261023.md)。

2026-10-08：390 項後端測試（389 通過、1 項既有 Windows 權限跳過）、Vue 型別／建置通過。RTX 3060 真實九節點任務驗證平台觀察 27.311 秒、引擎歷史 26.029 秒，提交前裝置回報 total 12,884,377,600／free 11,801,722,880／used 1,082,654,720 bytes。任務和作品快照相同，停止引擎後原值保持不變；證據 `runtime/job-measurements-api-20261008.json`。瀏覽器工具環境故障，UI 實機驗收未完成。FLUX 及圖生圖共用接口已經回歸測試，FLUX GPU 仍未驗證。

2026-10-23 · V04：1440px／390px 在任務詳情與作品預覽實際展開量測，核對上述原任務的 27.311／26.029 秒與來源／提交前資源；另以隔離案例驗證不同於目前引擎的原 URL、GPU／CPU 標籤、零秒／零可用容量與未知值。舊紀錄保持未知、讀取不改原任務，作品沿用同一快照。原資料庫前後 hash 相同，未重測 GPU 或估算任務峰值，見 [V04 證據](validation/comparison-measurements-20261023.md)。
