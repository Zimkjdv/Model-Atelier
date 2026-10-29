# F03：FLUX HTTP 生成、作品保存、離線與 OOM

日期：2026-10-25。完整通過 run：`f7fbc72f-5ecd-4482-8734-ecf1dca8ca42`；[機器可讀摘要](flux-generation-20261025.json)、[重跑與操作](../models/flux-workflow.md#generation-acceptance)。

使用 RTX 3060 12 GiB、約 63.939 GiB RAM、ComfyUI `15eb748b3ec5f8a0a2d470b7fb280e2d7579f916`、Torch 2.14.0+cu130。四份原固定權重重新完整 SHA256 通過，沒有替換來源；每份 revision／bytes／SHA256 及完整 graph／參數保存在摘要。配置為 512×512、batch 1、4 steps、CFG 1、Euler／simple、主模型 `fp8_e4m3fn`、編碼器 CPU、seed 字串 `9007199254740993`。

## 實際結果

| 案例 | 結果 | 提交至終態觀察時間 |
| --- | --- | ---: |
| 正常平台生成 | `queued → completed`，一張 512×512 PNG 保存成功 | 50.203 秒 |
| 損壞 safetensors | `failed`，`model_load_failed`，UNETLoader／ValueError | 0.672 秒 |
| CUDA 配額故障注入 | `failed`，`cuda_oom`，UNETLoader／torch.OutOfMemoryError | 2.687 秒 |
| 明確建立新 UUID | `completed`；原生引擎使用快取，原失敗紀錄不變 | 0.484 秒 |
| 接收後故意遺失回覆 | 先為 `unknown`，只查原 UUID 後 `completed` | 36.516 秒 |

時間包含 HTTP、排隊、輪詢與確認，並非純 GPU 推論；快取重試不當成新一次 GPU 量測。五個不同 UUID，各向 `/prompt` 寫入一次。失敗案例重新查詢相同請求只回原 ledger，未增加引擎提交；新任務由驗收流程明確要求。未知回覆案例的真實引擎已收到工作，平台端丟棄回執，後續沒有重送。

正常圖片為 324,328 bytes，SHA256 `89138d6d245cb47502386d8d805cf1346527f48bd5bd2bc2f3e2e519fe66e4e5`。作品圖片、工作流程匯出、原 job／artwork UUID、精確 seed、四元件及環境快照與還原設定都核對一致。已檢視實際 PNG 可正常顯示；這不代表畫風或角色品質通過。

停止自己的測試引擎後，從獨立平台只發出 GET，仍可核對同一圖片 bytes／SHA256、graph 及設定，提交計數保持 5。最後兩個自有服務都已停止、運算租約已釋放；原正常 ComfyUI 資料庫測試前後 SHA256 相同。

## 故障邊界與調查

OOM 是此張 GPU 的實際 allocator 在極小程序配額下拒絕 4 MiB allocation，並非 mock 例外；不是自然耗盡 12 GiB，也沒有測得最高解析度。測試掛鉤只在新 engine base 的唯一白名單 extension，普通模型名稱仍呼叫原 loader。它不會安裝到正常 runtime。配額恢復為該獨立程序已知的 1.0 預設。

先前工具嘗試均保留於 ignored runtime，不能算完整通過：曾修正作品 GET 摘要不含 graph、原生節點映射禁止覆蓋，以及此 Torch build 的 CUDA 配額 getter 回傳異常值而在 finally 蓋過 OOM。最終流程已通過全部案例，回歸也驗證清理不覆蓋原例外。另發現 ComfyUI 預設會跨 base directory 遷移舊 DB；原檔已還原並核對 hash，最終工具明確指定獨立 database URL，前後 hash 再核對一致。

本次沒有重新量測 HTTP 期間 RAM／VRAM 峰值。[F02 原生流程資源量測](flux-runtime-20261025.md)分開保留；不能將其直接視為 HTTP 流程峰值，更不能承諾 32 GiB RAM、RTX 4080、較大尺寸、LoRA 或參考圖可用。編碼器轉檔來源缺口仍保留在 M02。

獨立引擎只白名單故障測試 extension，未載入 nonce 裝置探測路由，因此保存的 `execution_device.status` 如實保持 `unknown / not_reported`；GPU 執行依據為實際引擎 CUDA 載入與 allocator 例外，沒有將缺少回報改寫成 available。

F02 的 [CI run](https://github.com/Zimkjdv/Model-Atelier/actions/runs/40164681392)實際因 Windows TEMP 路徑別名的 `Unsafe runtime path` 失敗，並非 GPU 工作。已讓兩側比較同一 canonical workspace，仍拒絕逸出 runtime 的路徑；用非正規但等價的暫存路徑補回歸。後續推送的 CI 結果須獨立確認。

最終本機完整品質入口通過：775 項後端測試（1 項既有跳過）、格式／型別、建置與全部契約；Chromium 四批 21／30／27／42，合計 120 項通過。Markdown 1,033 個本機連結檢查無誤；ROADMAP 為 14 主項／19 子項。GPU 驗收服務與完整測試未同時執行。
