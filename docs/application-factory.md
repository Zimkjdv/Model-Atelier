# 應用程式工廠與配置

`backend.main.create_app` 建立獨立 FastAPI app，保留原 `backend.main:app` 啟動入口與所有 URL。匯入模組、建立 app 與註冊路由不建立 data／SQLite；ASGI lifespan 啟動時才建立必要目錄與 `settings` 表。SQLite schema 與既有 JSON 不需遷移或回填。

```python
from backend.main import create_app
from fastapi.testclient import TestClient

app = create_app(data_root="runtime/my-isolated-data")
with TestClient(app) as client:  # 執行啟動與關閉生命週期
    assert client.get("/api/health").json() == {"status": "ok"}
```

## 配置介面

| 參數 | 預設／責任 |
| --- | --- |
| root | 專案根目錄，決定受管理 ComfyUI、固定來源及前端 dist 的位置 |
| data_root | root/data，決定素材、作品、job_inputs、control_edges 等保存位置 |
| database | data_root/atelier.sqlite3，可指定既有資料庫；若分離至其他目錄，備份須另包含該檔 |
| engine_client_factory | 預設建立 httpx.AsyncClient；可注入相同 async context manager 介面的實作，接收原 timeout／trust_env／follow_redirects 參數 |

AppContext 位於 `app.state.context`，各 app 的路徑、引擎網址讀取、環境快取、路由鎖與進度 Hub 均獨立。功能模組依原有順序逐項註冊，不再讀取整個 main 模組；純請求型別在 schemas.py，舊的 main.DraftInput 等純型別匯出保留。一般產品程式透過工廠與 HTTP 使用，不需修改 context 內部欄位。

引擎 HTTP 使用 context.http_client；預檢及後續查詢仍使用任務保存的原網址，取消、停止與原 UUID 恢復規則不變。WebSocket 仍由每 app 的進度 Hub 依原 client ID 連線；沒有將裝置快照當全域提交許可。

## 測試與相容

既有 API 測試共用工廠建立臨時資料，不再 patch main.DB／DATA／ROOT。涉及同一 TestClient 回呼中模擬另一請求的舊測試，先明確執行自身 context.initialize，再建立短生命週期 TestClient，避免同一 portal 執行緒的重入；正常服務仍由 ASGI lifespan 初始化。

新增 AppFactoryTests 同時啟動兩個 app，驗證獨立設定、相同 UUID 的不同原引擎任務、素材不可跨 app 讀取、獨立環境快取及引擎 client。另以新 Python 程序攔截 mkdir／SQLite connect，確認 import 無資料建立；重開 app 可讀舊資料，舊草稿精確 seed 與原 JSON 不被改寫。

```powershell
.\.venv\Scripts\python.exe -m unittest backend.test_app_factory
.\.venv\Scripts\python.exe -m unittest discover -s backend -p 'test_*.py'
```

回退只需回到前一版程式並重新啟動；本次未改 SQLite schema、資料 key 或圖片布局，不需轉換資料。請先停止原服務再切換版本，不在運作中的資料上同時混用不同程式版本。
