# D02 Docker 本機部署驗收

2026-10-25，Windows／Docker Desktop 4.95.0、WSL2 Linux containers；Docker Engine／CLI 29.8.2、Compose 5.6.0。RTX 3060 12 GiB，原生 ComfyUI 0.34.0、Python 3.12.10、PyTorch 2.14.0+cu130。容器使用 Python 3.12.15。操作見 [Docker 說明](../docker.md)，可解析摘要見 [證據 JSON](docker-deployment-20261025.json)。

## 範圍與建置

使用自己的 Compose project `atelier-d02-20261025`，loopback 18101 與獨立還原容器 18102，資料、鎖、備份、還原各為新 named volume；沒有掛載正式 Windows DATA 或權重，也沒有更動其他 Docker 容器。沿用既有 Windows 原生 ComfyUI 8188，沒有擴大其監聽範圍。

多階段映像先以固定 Node digest 建置前端，再以固定 Python digest 及既有 requirements lock 安裝平台。實際容器為 UID/GID 10001、唯讀 root、移除 capabilities、no-new-privileges，發布位址經 inspect 確認只有 127.0.0.1。健康檢查及實際 HTTP 均通過；真正 bridge gateway 為 172.21.0.1，沒有加入全網段信任或額外 peer。

原生 D01 的嚴格預設不變。容器另通過明確 gateway／其他 peer 拒絕、Host／Origin 拒絕、路由取得及已保存引擎優先於環境預設的四項回歸；兩個真正 HTTP 平台各拒絕四組 Host／Origin／Fetch Metadata／偽造 forwarding 寫入，設定維持不變。

## GPU、資訊來源與實際生成

1. 基本 Compose 可連原生 ComfyUI 並出圖，平台 GPU 資訊不可得時保持空清單。
2. 使用 NVIDIA 官方固定 sample digest 實際執行 nbody CUDA kernel，RTX 3060／Compute 8.6 成功；只視為 GPU 存取證據，不作速度比較。
3. 同一平台映像加 GPU observer 後，`nvidia-smi` 回報 RTX 3060、12,288 MiB；實際 `compose.gpu.yaml` 亦成功取得裝置。平台沒有安裝 PyTorch 或充當推論引擎。
4. 平台 `/api/system` 為 Linux／container，RAM 約 33.62 GB；引擎回報 win32、RAM 約 68.65 GB。系統頁標示容器來源，不混成 Windows 實體資源；容器不提供 Windows 原生 Python 安裝檢查按鈕。
5. 以既有固定 Animagine XL 4.0 Opt（實檔大小及 SHA256 核對）生成一件 512×512／4 steps／cfg 5／euler_ancestral／normal 技術案例。seed 為字串 `18446744073709551615`，workflow 保存為精確整數。原 UUID 僅提交一次，完成後明確匯入作品，核對原圖 hash、完整 workflow、模型 metadata 與全部創作設定；不代表畫風品質或容器 GPU 推論通過。

使用自製 16×16 單色素材及簡單樹木提示，沒有使用作者圖片。生成原始報告保留於 `runtime/d02-generation.json`；工具 `python -m scripts.verify_container_generation --platform http://127.0.0.1:18101 --expected-engine http://host.docker.internal:8188` 預設拒絕覆蓋既有報告。`--verify-report` 只 GET 原 job／作品，不重新生成。

## 持久化、停機備份與恢復

- 保存一件素材、一份草稿、一個完成 job 及一件作品。平台運行時，以相同 `/data` 與共享 `/locks` 啟動另一個備份容器，即使聲明 `--platform-stopped` 仍正確拒絕。
- 僅停止本次平台後，禁網維護容器完成 Q07 backup／verify，四個檔案均完整，盤點為 artwork／asset／draft／job 各一；SQLite 與所有受管檔案一併保存。
- 同卷 force-recreate 平台，刻意把初始引擎環境改為無效網址，資料庫保存的原生引擎設定仍勝出。素材、草稿、原工作／作品及完整 workflow 雜湊均不變。
- 另在禁網維護容器把備份恢復到全新卷／新目錄，啟動獨立平台；兩個平台的原圖 hash、原 seed、全部創作設定、模型 metadata、workflow 原始 bytes hash、素材及草稿內容皆一致。
- 再把還原平台切離 bridge 網路，容器內 `/api/engine` 明確回報離線，透過 localhost 對原 job／作品執行同一固定 verifier 的 GET-only 核對仍成功。原生 ComfyUI 無需停止，沒有重送 GPU 工作。

1440px／390px 的實際容器 Chromium 系統頁也通過模式、硬體來源提示及不溢出檢查，截圖保存在 `runtime/d02-system-1440.png`、`runtime/d02-system-390.png`。隔離完整品質流程完成 722 項後端（其中一項既有跳過）、型別／建置、四組契約及 112 項 Chromium；最後補上原生安裝檢查提示後，另完成建置、靜態檢查及兩項容器 UI 定向重跑。Docker 建置、實測及維護原始紀錄留在 `runtime/d02-*`，圖片、權重及整份 runtime 不進 Git。

最終映像重建、原 job GET-only 核對及兩份 Compose 配置驗證通過；908 個本地文件連結／anchor 核對通過。結束時只停止本次兩個驗收容器，資料／備份卷保留，原生 ComfyUI 仍可連線且佇列為空。

## 未涵蓋事項

此驗收限定同機 Windows／Docker Desktop WSL2 與既有 ComfyUI；沒有驗收原生 Linux 宿主機、遠端 GPU、多租戶或公開部署。平台 RAM／磁碟為容器可見環境，沒有 cgroup 配額換算或 Windows C 槽換算；GPU sample 不代表任意工作負載可跑。

Windows 原生 DATA 的跨 OS 路徑遷移、Explorer 開資料夾、容器 trainer 與 T03 跨 OS GPU 租約均未支援。訓練前必須先停止容器平台並依 T03 檢查引擎；此處共享資料鎖只協調容器 DATA 維護。權重、引擎輸出、trainer 與外部證據仍須獨立備份。RTX 4080、實體觸控、FLUX 合法存取、Pony 條款與作者圖審查仍依 ROADMAP 保留待辦。
