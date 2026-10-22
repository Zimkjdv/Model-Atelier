# E01 執行裝置回報驗收（2026-10-22）

本次驗收關閉 ROADMAP 的 E01-01／E01-02。範圍是「原引擎目前設定的執行裝置」，不宣稱辨識整台主機的全部 GPU，也不證明模型可執行或跨環境品質。

## 自動驗證

後端 `.venv/Scripts/python.exe -m unittest discover -s backend -p 'test_*.py'`：545 項，544 通過、1 項既有 Windows symlink 權限跳過（約 28 秒）。其中 `backend.test_execution_device` 15 項涵蓋：

- 八種提交入口／流程：標準表單、直接 workflow、圖生圖、修補 v1／v2、Canny v1／v2、FLUX。明確不可用時回傳 409，任務為 failed，沒有圖片上傳或 `/prompt` 呼叫，也沒有新 job_inputs 檔案；原 UUID 恢復返回原紀錄，不再連線。
- 版本、producer、nonce、欄位型別、CPU 與後端矛盾、過期回報、空清單、HTTP 404／503、離線、過大回應及逾時皆不誤判不可用。
- CPU、cuda、mps、xpu、npu、mlu 及其他裝置類型不因型號被封鎖；後端明確 false 與裝置選取失敗才產生不可用證據；缺函式、其他例外與未完成查詢保持未知，原始例外不外露。
- 查詢期間引擎改變不提交；修復後的新 UUID 或另一個引擎可提交，原失敗及快照不被更新。
- 缺 checkpoint、缺必要節點、已知不支援架構仍保留原本保護；裝置失敗後仍能保存草稿、讀取既有原圖及產生 CPU 羽化預覽。
- 固定安裝器可重跑且保留其他擴充；在 ComfyUI Python 子程序中，使用真正 aiohttp 路由與 localhost HTTP 驗證錯誤 nonce／額外參數回傳 400、不可用／CPU／未知／選取失敗四種回報及 no-store。

其餘回歸覆蓋既有提交、取消／停止、進度、模型／LoRA／元件相容、修訂衝突、素材／作品保存、精確 seed 與不可變快照。Starlette TestClient 的 httpx 棄用提示仍存在，依 Q06 處理。

前端 `npm.cmd run build` 通過 Vue 型別檢查及正式建置；`check:experiments`、`check:inpaint`、`check:control` 全部通過。JS 372.10 kB／gzip 119.02 kB，CSS 56.62 kB／gzip 10.14 kB，僅為此次建置檔案大小。

## 真正 ComfyUI CPU 模式

使用受管理 ComfyUI Python 執行 `scripts/verify_execution_device.py --managed-cpu`，以 `--cpu`、獨立 user／input／output／temp、記憶體 SQLite、動態 localhost port 啟動，禁用其他 custom nodes 並只允許本專案回報擴充。實際引擎返回：

```json
{
  "schema_version": 1,
  "producer": "model-atelier-execution-device-v1",
  "status": "available",
  "reason": "device_selected",
  "device": {"type": "cpu", "index": null},
  "backend_available": null
}
```

原始回應另包含相同請求 nonce，本次為 `2346febe-caee-4223-9e71-1d6e9512b41c`。本次腳本全部通過，測試程序樹已停止。第一次執行暴露 Windows venv launcher 子程序仍持有 log 的清理問題，驗收腳本已改為停止本次程序樹後清理，再重跑通過。

CPU 模式驗證的是實際擴充載入與回報；不可用情境使用真實 HTTP 路由搭配故障注入，不刻意拔除／停用 GPU、修改驅動或耗盡真實顯存。沒有載入權重或生成圖片，不沿用其他 GPU 推論驗收。

## 瀏覽器介面

以獨立資料庫的隔離平台與模擬引擎，在真實瀏覽器實際更新系統資訊，確認三種狀態：

1. 明確不可用顯示警示、生成前停止說明、草稿／素材／作品仍可用及來源／時間。
2. 切換 CPU 回報後顯示「已取得設定的執行裝置」與 cpu，說明不保證模型載入或顯存足夠。
3. 切換未知回報後顯示「執行裝置狀態未知」，不從空裝置清單或本機 CUDA 推定無 GPU。

已檢查警示區的畫面可讀性；這不是全站無障礙或 390px／觸控驗收，V01–V06 保留。瀏覽器驗收頁已關閉、隔離 8001 服務已停止；隔離 helper／資料在忽略的 runtime 下，正式作品與設定未改動。受管理引擎的回報檔案已安裝，日常引擎下次啟動時載入。

## 可追溯入口

契約與重跑指令見 [執行裝置說明](../execution-device.md)；回歸來源為 `backend/test_execution_device.py`、`scripts/verify_execution_device.py`。硬體更多負載、RTX 4080 與其他流程品質仍依 E02–E05 及各自驗收，不由本次通過推定。
