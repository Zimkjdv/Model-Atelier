# 部署方式與本機存取

2026-10-25 使用者確認：**維持同一台電腦使用**。平台與 ComfyUI 分開執行，但目前不需要其他區網裝置、獨立 GPU 主機或公開網站。本輪 D01 完成此決策及本機邊界；Docker 是 D02 的選擇性部署方式，不改變這個使用範圍。

## 本機模式

日常仍由 `start-all.bat` 啟動平台 8000 與受管理 ComfyUI 8188，瀏覽器開啟 `http://127.0.0.1:8000/`。平台啟動腳本明確綁定 127.0.0.1，並停用 Uvicorn forwarded-header 信任。直接啟動時：

```powershell
.\.venv\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --no-proxy-headers --timeout-graceful-shutdown 5
```

新版本需重新啟動平台程序；更新前端建置不會替舊 Python 程序載入保護。

全域 ASGI 存取保護在 API 與靜態檔案之前核對實際來源 IP、Host 與瀏覽器 Origin；只有 loopback peer／Host、相同 scheme／host／port 的 Origin 可通過。無 Origin 的本機 CLI 可操作。拒絕重複或無效的 Host／Origin、非本機 peer 與跨站 API 請求；外部連結仍可導覽到本機首頁。WebSocket 不符合時拒絕升級，現有 SSE 遵守相同 HTTP 邊界。偽造 Forwarded／X-Forwarded-For 不會取得額外信任。

這個模式**沒有帳號登入**，不驗證 Windows 使用者身分；同一台電腦的使用者與程式皆視為可信。loopback／Origin 保護不是遠端認證或租戶隔離。不要用 `--host 0.0.0.0`、反向代理、隧道或單純加入 CORS 來宣稱已支援遠端存取；將來需要區網時，須另立需求並驗證帳號／憑證、加密、來源限制與主機角色。

## 來源與角色

系統頁「部署與存取」透過唯讀 `GET /api/deployment` 顯示模式與選定引擎；失敗保留上次資料並提供明確更新。此查詢不聯絡引擎、不修改設定、不生成。

| 內容 | 實際來源 |
| --- | --- |
| 平台 GPU／RAM／磁碟／Python | 執行平台的程序／作業系統及其 `nvidia-smi`；不是另一台引擎的硬體 |
| 引擎環境與裝置 | 目前選定引擎的 `/system_stats` 與 E01 回報；離線／無法取得保持未知 |
| 圖片、素材、資料庫、備份 | 平台 DATA 與實際檔案系統 |
| 額外 checkpoint 目錄與開啟資料夾 | 本專案受管理本機路徑；不代表外部引擎的磁碟 |
| T03 訓練與運算租約 | 本專案原生 Windows 環境及受管理引擎，其他軟體或另一個 checkout 不受控制 |

既有「選定引擎網址」仍是後端向外連線的設定；它不會開放瀏覽器入站權限，也不會把平台硬體數字改成該引擎的數字。新頁面明確標示本機／外部引擎，不從網址推測外部主機的實體位置。

## 驗證與參考

`python -m scripts.verify_local_access --output runtime/my-local-access-check.json` 啟動自己的短暫 loopback 平台及隔離 DATA，驗證真正 HTTP 的 Host／Origin／跨站拒絕、同來源寫入及未信任 forwarding headers；結束只停止自己的程序。ASGI 回歸另涵蓋非本機 peer、IPv6、重複 headers、WebSocket、資料不變及原引擎角色。

實測與範圍見 [D01 驗收](validation/local-deployment-20261025.md)。對照安裝版本的 Starlette／Uvicorn 原碼以及官方 [Host middleware](https://github.com/Kludex/starlette/blob/main/starlette/middleware/trustedhost.py)、[Uvicorn 設定](https://github.com/Kludex/uvicorn/blob/main/docs/settings.md)；本專案另外核對來源 IP 與完整 Origin，不複製外部平台的帳號或佇列模組。
