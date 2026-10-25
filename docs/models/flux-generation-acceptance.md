# FLUX 平台生成與失敗復原

F03 使用 [固定四元件](flux-installation.md) 與 [F02 配置](flux-runtime-observation.md)：RTX 3060 12 GiB、約 64 GiB RAM、512×512、batch 1、4 steps、Euler／simple、CFG 1、主模型 `fp8_e4m3fn`、文字編碼器 CPU。精確 seed 為 `9007199254740993`，完整值以字串保存，工作流程 JSON 使用整數。這不是所有精度、尺寸或顯卡的通過保證。

## 平台操作

1. 啟動服務，在模型庫的 FLUX 元件頁同步四份元件，依安裝報告登記來源 revision 與 SHA256；登記本身不會驗證權重。
2. 在創作工作區選「FLUX.1 [schnell]」，填入四個檔名、提示詞與上述配置。可以先保存草稿或匯出完整 JSON。
3. 按一次生成，等待原 UUID 的工作狀態確認。若提交回覆遺失，查詢原任務；不要再次按生成來猜測結果。
4. 成功後保存作品。在作品庫讀取本機圖片、原始 JSON、元件及環境快照；載入設定只填表，不會生成。
5. 若載入失敗或 CUDA OOM，保留失敗任務。先載入原設定、確認錯誤、修正模型或降低尺寸，再明確按生成建立新 UUID。原 UUID 永遠保留原結果。

沒有支援負面提示詞，也不把 SDXL 的附加元件驗收當成 FLUX 可用證據。LoRA／參考圖由 F04 分開處理。

## 可重現驗收

從專案目錄執行（需要已安裝的四份固定權重與 managed ComfyUI Python）：

```powershell
# 先結束原引擎工作並關閉 8188 引擎；工具不會代為停止使用者服務。
.\.venv\Scripts\python.exe -m scripts.flux_acceptance_fixture --run
```

工具先完整驗檔並取得本機運算租約，再建立 `runtime/flux-acceptance/<UUID>/`。獨立平台使用新的 DATA／SQLite；獨立 ComfyUI 明確指定 base directory、database URL、模型搜尋目錄及隨機 loopback port，只有測試專用節點可載入。原平台設定、作品及正常引擎自訂節點不參與測試。工具結束只停止自己建立的兩個程序，失敗報告也保留。

案例依序為正常生成、損壞 safetensors 載入失敗、真實 CUDA allocator OOM、使用者明確建立的新任務，以及引擎已接收但平台故意遺失回覆。最後停止測試引擎，從仍開啟的平台讀取先前作品與設定。每個案例的 `/prompt` 計數必須剛好一次；離線驗證不得增加計數。

OOM 案例只在測試程序設定極小的 CUDA 配額，請求 4 MiB tensor 並立即還原配額，讓實際 PyTorch allocator 拋出例外。這是受控故障注入，**不是自然耗盡 12 GiB VRAM，也不代表測得最大可用解析度**。正常權重名稱走原生 loader；損壞檔／OOM 標記檔僅存在該次測試目錄。請勿將 `scripts/flux_failure_node.py` 安裝到正常引擎。

也能對目前平台執行固定單次生成，或在引擎離線時唯讀驗證先前報告：

```powershell
.\.venv\Scripts\python.exe -m scripts.verify_flux_generation --report runtime/my-flux.json
.\.venv\Scripts\python.exe -m scripts.verify_flux_generation --report runtime/my-flux.json --verify-report
```

新報告以 exclusive create 保留，已存在時拒絕覆寫，未送出任務。`--verify-report` 只使用 GET，核對原 job／artwork UUID、完整 graph、四元件與環境快照、PNG SHA256／尺寸及完整設定。它不重新同步、匯入或提交；原報告不改寫。若生成程序中斷或網路失敗，讀取留下的 UUID，先確認原任務。

實際結果與限制見 [F03 驗收紀錄](../validation/flux-generation-20261025.md)。權重、圖片、原始日誌及 DATA 留在 ignored runtime；Git 僅保存去除本機絕對路徑的摘要。
