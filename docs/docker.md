# Docker 本機部署

D02 提供選擇性的 Linux 平台容器；日常 Windows `start-all.bat` 仍可使用，Docker 不是前置需求。已驗證的是 **Windows Docker Desktop／WSL2 平台容器 → 同一台 Windows 的原生 ComfyUI**，沒有把 ComfyUI、權重或 trainer 搬進映像，也沒有開放區網或帳號登入。

## 啟動與停止

先啟動原生 ComfyUI，例如在另一個 PowerShell 執行 `./start-comfyui.ps1`。Docker Desktop 需切到 Linux containers；在專案根目錄執行：

```powershell
docker compose up -d --build --wait
```

開啟 `http://127.0.0.1:8001/`。8001 與原生平台 8000 分開；新資料卷是空的，不會自動匯入原生 `data/`。第一次啟動的引擎預設為 `http://host.docker.internal:8188`；設定頁保存後以資料庫設定為準，修改 `ATELIER_ENGINE_URL` 或重建不會覆蓋已保存設定。引擎模型清單仍須明確同步。

```powershell
docker compose logs --tail 100 platform
docker compose stop
docker compose up -d --wait
```

`stop`／`down` 保留資料卷；**`down -v` 會刪除平台資料**，不要把它當日常停止指令。需要改平台埠可先設 `$env:ATELIER_PORT='8002'`；同一輪命令須使用相同 Compose project 名稱／環境。不要同時讓原生與容器平台操作同一 DATA。

容器使用 UID/GID 10001、唯讀根檔案系統、移除 capabilities、禁止取得額外權限，只有 DATA、協調鎖與暫存空間可寫。Node 與 Python 基底均固定 digest，前端在獨立 build stage 建置；映像只納入程式、前端產物及 JSON manifest，排除 `.git`、`.env`、原圖、權重與 runtime。相依版本沿用既有 lock，更新須另行重建及驗證。

## GPU 與硬體來源

一般 Compose 不需 GPU 直通；真正生成仍由原生 ComfyUI 執行。若希望系統頁取得容器可見的 `nvidia-smi` 裝置資訊，可選用：

```powershell
docker compose -f compose.yaml -f compose.gpu.yaml up -d --build --wait
```

這需要 Docker Desktop WSL2 與可用的 NVIDIA 驅動。沒有 GPU observer 不代表原生引擎不能出圖；observer 可列裝置也不代表平台映像具有 PyTorch／CUDA 推論環境。

| 系統頁資料 | 容器模式的含義 |
| --- | --- |
| 平台 OS／Python | Linux 容器環境，與 Windows 原生引擎分開 |
| 平台 RAM | 容器／Docker VM 可見記憶體，不是 Windows 實體 RAM；未實作 cgroup 可用配額換算 |
| 平台磁碟 | DATA 所在 Linux 檔案系統容量，不是 Windows C 槽可用量或資料夾大小 |
| 平台 GPU | 容器可取得的 `nvidia-smi`，未配置／不可得保持未知 |
| 引擎資訊 | 選定原生 ComfyUI 的 `/system_stats` 與裝置回報 |

本機驗收 RTX 3060 可執行容器 CUDA sample，原生 ComfyUI 也完成一件固定案例；這不是 Docker 推論效能比較或所有 GPU／OS 的相容承諾。完整條件見 [D02 驗收](validation/docker-deployment-20261025.md)。

## 存取邊界

Compose 僅發布 `127.0.0.1:8001:8000`。容器內監聽 0.0.0.0 供 Docker 轉送，外部發布仍限本機；不要移除 ports 中的 `127.0.0.1`。容器入口只信任 loopback 及從自身 Linux 路由取得的**單一明確 gateway IP**，並繼續檢查 loopback Host、完整同來源 Origin 與 Fetch Metadata，不信任 Forwarded 標頭。

不同 Docker Desktop 網路模式若使用其他轉送來源，預設拒絕；先檢查真實來源後，才可設 `ATELIER_CONTAINER_PEERS` 為逗號分隔的明確私有 IP（與 gateway 合計最多五個），不接受整段 CIDR。這是來源適配，不是遠端登入。原生入口不讀取此選項，也不放寬原生 D01 保護。不要啟用 host networking、對外反向代理或公開平台埠。

## 資料卷、備份與還原

預設 project `model-atelier` 有 `model-atelier_atelier-data`（`/data`）及 `model-atelier_atelier-locks`（`/locks`）。`TMPDIR=/locks` 讓 Q07 的跨程序停機檢查在共享鎖卷工作；所有維護容器必須使用相同 DATA 掛載路徑及鎖卷，否則無法協調。標準部署資料根目錄是 `/data`；若另設 `ATELIER_DATA`，備份也必須指定相同根目錄。

以下為預設 project／image 的範例，目的目錄必須尚不存在，重複備份要換新的日期名稱。先停止平台，再執行備份容器；`--platform-stopped` 只是明確聲明，真的仍在運行時工具也會拒絕。

```powershell
docker compose stop
docker compose run --rm --no-deps --entrypoint python -v model-atelier-backups:/home/atelier platform -m scripts.data_backup backup --data /data --destination /home/atelier/backup-20261025 --platform-stopped
docker compose run --rm --no-deps --entrypoint python -v model-atelier-backups:/home/atelier platform -m scripts.data_backup verify --archive /home/atelier/backup-20261025
docker compose up -d --wait
```

上面 `compose run` 沿用專案網路；如果需要完全禁網的備份環境，使用與驗收相同的獨立命令：

```powershell
docker run --rm --network none --read-only -v model-atelier_atelier-data:/data -v model-atelier_atelier-locks:/locks -v model-atelier-backups:/home/atelier --entrypoint python model-atelier:local -m scripts.data_backup backup --data /data --destination /home/atelier/backup-offline-20261025 --platform-stopped
```

還原到**新的卷／新目錄**，不覆蓋來源；`/home/atelier` 已由映像建立為 UID 10001，讓新卷初始化為可寫。

```powershell
docker run --rm --network none --read-only -v model-atelier-backups:/backup -v model-atelier-restored:/home/atelier -v model-atelier_atelier-locks:/locks --entrypoint python model-atelier:local -m scripts.data_backup restore --archive /backup/backup-20261025 --destination /home/atelier/restored
docker run -d --name model-atelier-restored-check --read-only --cap-drop ALL --security-opt no-new-privileges:true --init -p 127.0.0.1:8002:8000 -e ATELIER_DATA=/data/restored/data -v model-atelier-restored:/data -v model-atelier_atelier-locks:/locks model-atelier:local
```

開啟 `http://127.0.0.1:8002/`，核對素材、草稿、原 job／作品、圖片 hash、完整 workflow 與還原設定後再自行決定切換。停止驗證容器用 `docker stop model-atelier-restored-check`，卷先保留。備份卷仍在同一台電腦，不是異地備份；重要封存需另外複製到備份媒體並再次 verify。備份範圍／外部目錄處理見 [Q07](data-backup.md)。

## 與原生功能的差異

- 容器沒有原生 Windows 目錄與 Explorer；開啟資料夾不支援，Windows 路徑不能直接當 Linux 檔案路徑使用。容器內 `/app/runtime/ComfyUI` 也不是宿主機權重目錄。
- 權重、原生 trainer、T03 run、ComfyUI 輸入／輸出與原始驗收證據不會自動進平台資料卷；需各自備份，既有 Windows 路徑的遷移尚未驗收。
- **T03 的 Windows 運算租約不會跨 Docker 同步**；此映像不提供訓練環境或訓練 CLI 支援。使用本機訓練時先停止容器平台，確認原生引擎沒有其他工作，再依 T03 操作。不要同時用容器提交推論及原生試訓，也不要把容器 Q07 資料鎖視為 GPU 租約。
- 容器重建不保證跨環境生成逐像素一致；已保存圖片／設定恢復會核對原檔，不重新生成。作者圖仍待 T02 審查，D02 沒有使用或訓練作者圖片。

## 官方參考

- [Docker Desktop GPU／WSL2](https://docs.docker.com/desktop/features/gpu/)
- [發布埠與 loopback 綁定](https://docs.docker.com/engine/network/port-publishing/)、[Desktop 網路與宿主機連線](https://docs.docker.com/desktop/features/networking/)
- [資料卷生命週期](https://docs.docker.com/engine/storage/volumes/)、[多階段建置](https://docs.docker.com/build/building/multi-stage/)
