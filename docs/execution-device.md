# 引擎執行裝置回報

E01 使用正在執行的 ComfyUI 程序回報目前設定的裝置，不使用平台 GPU 型號、可用 VRAM、空 `devices` 或本機診斷快照判定另一個引擎能否執行。

## 安裝與查看

受管理本機引擎由 `start-comfyui.ps1` 在啟動前執行 `scripts/install_execution_device.py`，將本專案的 `comfyui_extensions/model_atelier_execution_device` 兩個檔案更新到受管理 ComfyUI 的同名 `custom_nodes` 目錄。其他擴充不被更動，不下載第三方程式，也不改寫 ComfyUI 原始碼；重新啟動才會載入。重新執行安裝不重寫相同內容，路徑重新導向／符號連結會拒絕。

遠端或自行啟動的 ComfyUI：將上述完整目錄放到該引擎的 `custom_nodes/` 並重新啟動；若使用 `--disable-all-custom-nodes`，需明確加上 `--whitelist-custom-nodes model_atelier_execution_device`。未安裝或被停用時保持未知，既有生成流程仍可用。這是唯讀回報擴充，`NODE_CLASS_MAPPINGS` 為空，不提供生成節點。

系統資訊顯示裝置狀態、來源與時間。此畫面是顯示快照；提交時會查詢任務原引擎，不能拿畫面上的舊結果阻擋新任務。提交時的結果保存於 `runtime_metadata.execution_device`，作品沿用原快照；舊紀錄缺此欄位時保持未知，不回填。

## 回報契約

引擎端點：`GET /model_atelier/execution-device?probe_id=<UUID>`。UUID 必須是標準小寫格式，缺少／錯誤 UUID 或額外參數回傳 400；每次查詢產生新 UUID，回應附 `Cache-Control: no-store`。

回應為 schema 1，producer 固定 `model-atelier-execution-device-v1`，包含相同 `probe_id`、`status`、`reason`、`device`（type／index）與 `backend_available`。沒有任意命令、檔案讀取或流程執行介面。

| 狀態 | 明確依據 | 新生成行為 |
| --- | --- | --- |
| available | 引擎 `get_torch_device()` 取得目前設定裝置；若該後端有受支援的 `is_available()`，沒有明確否定 | 繼續既有驗證；不是模型／顯存／品質保證 |
| unavailable / device_selection_failed | 同一引擎裝置選取函式明確發生 RuntimeError／AssertionError，無法取得設定裝置 | 保存失敗任務，HTTP 409，不上傳輸入、不送 `/prompt` |
| unavailable / backend_unavailable | 已取得的 cuda、mps、xpu、npu 或 mlu 設定裝置，其執行後端 `is_available()` 明確回傳布林 false | 同上；不是顯卡型號白名單，也不表示整台主機沒有 GPU |
| unknown | 缺擴充、離線、逾時、HTTP 錯誤、資料缺漏、錯誤 producer／版本／nonce、過大回應、未完成查詢或其他例外 | 不增加裝置阻擋，仍檢查模型、元件、架構與必要節點 |

CPU 是有效設定裝置，不因 `torch.cuda.is_available()` 為 false 而阻擋 CPU 模式。其他後端取得裝置成功時也不依名稱封鎖。只讀取選取結果與可用性，不載入模型、配置測試張量、切換裝置或啟用 CPU fallback。明確選取失敗與後端查詢不完整分開處理，原始例外不回傳。

平台查詢最多等待 2 秒，接受的回應上限 16 KiB。只採用本次 nonce 與任務原引擎的合法回報；查詢期間選定引擎改變，顯示狀態改為未知，新提交維持原有 `engine_changed` 保護。

## 任務與恢復

所有生成入口（`/api/generate`、`/api/jobs`、inpaint／inpaint-feather、control／control-edge、flux 的 generate）在既有模型／節點驗證後、輸入上傳與 `/prompt` 之前檢查即時回報。明確不可用時，`failure_info.code` 為 `execution_device_unavailable`，保留原設定、精確 seed、UUID 與證據。

原 UUID 再次提交只返回原紀錄，不重新檢查或重送。修復裝置後，載入設定並明確建立新的請求；修復後的新任務或其他引擎不受舊失敗回報影響。草稿保存、已匯入作品離線讀取、素材與 CPU 羽化預覽不經這個生成門檻。

可用性是提交前觀察，不能保證排隊後裝置仍可用，也不保證模型一定載入成功；執行期 OOM 與其他失敗仍沿用原有引擎歷史核對與診斷。預檢不替代實際 GPU 出圖測試。

## 重跑檢查

```powershell
.\.venv\Scripts\python.exe -m unittest backend.test_execution_device
.\runtime\ComfyUI\.venv\Scripts\python.exe scripts\verify_execution_device.py
```

第二個指令以實際 aiohttp 路由進行故障注入，無模型、無測試張量。需要額外驗證真正 ComfyUI 的 CPU 模式時，先執行固定安裝器，再使用：

```powershell
.\.venv\Scripts\python.exe scripts\install_execution_device.py
.\runtime\ComfyUI\.venv\Scripts\python.exe scripts\verify_execution_device.py --managed-cpu
```

此檢查使用臨時資料目錄、記憶體資料庫與未使用的本機連接埠，只載入本專案回報擴充；結束會停止本次程序樹並清理臨時資料，不停止使用者既有引擎。需要已安裝的受管理 ComfyUI 環境。驗收條件與限制見 [紀錄](validation/execution-device-20261022.md)。
