# 指定執行中任務停止：RTX 3060（2026-10-04）

平台只使用原引擎 `/api/jobs/{prompt_id}/cancel`。目前核對 ComfyUI commit `15eb748b3ec5f8a0a2d470b7fb280e2d7579f916` 的 `server.py`、`execution.py`、`comfy_execution/jobs.py`：`interrupt_if_running` 在佇列 mutex 內核對執行 ID 並設置中斷旗標；下一次 `execute_async` 重設旗標。舊 `/interrupt` 具有快照與中斷之間的競態，平台不使用。

`start-comfyui.ps1` 透過唯讀來源雜湊檢查，只有上述三份檔案匹配才宣告 `model_atelier_atomic_job_cancel_v1`，值為已審查的 commit。CRLF／LF 正規化後計算 SHA256。更新或修改來源後，停止能力關閉，正常生成仍可使用。能力宣告是受信任引擎的協定契約，不是遠端來源的密碼學證明；其他啟動方式需先審查同樣語意，不可僅因版本相同或路由存在而宣告。

平台 `POST /api/jobs/{id}/stop` 使用原引擎，即時核對完整佇列 workflow 與任務身分，修訂與 60 秒租約保護並行操作。只送一次指定停止；結果不明時 `stop_unknown`，後續 stop／refresh 只查詢，不重送。HTTP 200、`cancelled: true` 或佇列消失都不能證明停止；需要身分相符的完整 history prompt 及可信節點 `execution_interrupted` 訊息才顯示 `stopped`。任務已完成或發生其他失敗時保留真實結果、輸出與原始 JSON。

實機使用 ComfyUI 0.34.0、RTX 3060 12GiB、Python 3.12.10、PyTorch 2.14.0+cu130 與 Pony V6 XL。兩個中性山景任務依序提交，尺寸 512×512、CFG 5.5、`dpmpp_2m/karras`、denoise 1、batch 1、無 LoRA。

| 任務 | 設定 | 確認結果 |
| --- | --- | --- |
| `8672cc4d-d19a-416d-bfcb-9fb035139c0b` | 80 steps、seed `9007199254740995` | 指定停止後歷史含 `execution_interrupted`；平台顯示已停止生成 |
| `9cd22954-7c05-49bb-a5f8-8314c7aa5102` | 4 steps、seed `9007199254740996` | 下一任務成功，歷史保存 SaveImage 輸出；未受停止旗標影響 |

本機報告 `runtime/running-stop-20261004.json` 與畫面 `runtime/running-stop-ui-20261004.jpg` 不納入 Git；兩份正式任務紀錄及引擎輸出保留。瀏覽器確認完成／停止狀態及 workflow／history 下載入口。281 項後端測試（280 通過、1 項既有 Windows 權限跳過），Vue 型別／建置通過。未驗證 RTX 4080、其他引擎版本、多 GPU 或所有節點對中斷的即時反應速度。
