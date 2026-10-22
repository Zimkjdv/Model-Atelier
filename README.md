# Model Atelier

個人 AI 圖像創作與實驗工作台。Vue 3 + TypeScript 前端、FastAPI 後端，透過獨立 ComfyUI 執行生成；SQLite 與圖片保存在本機。

現行待辦與驗收以 [ROADMAP.MD](ROADMAP.MD) 為準；開發與歷史實測見 [CHANGELOG.MD](CHANGELOG.MD)。文件整理日期：2026-10-22。

## 快速開始

Windows／PowerShell 使用者先準備 Git、Python 3.12 與 Node.js；本專案曾驗證 Python 3.12.10、Node.js 24.19.0。從專案根目錄執行：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.lock.txt
Set-Location frontend
npm.cmd ci
npm.cmd run build
Set-Location ..
.\start-local.ps1
```

開啟 [本機平台](http://127.0.0.1:8000)。前端由 FastAPI 提供，不需另外啟動 Node。尚未開啟引擎時仍可保存草稿、整理素材、瀏覽已匯入作品；新資料庫不附作品或權重。

生成另需獨立 ComfyUI、相容 PyTorch 與 checkpoint；完整步驟見 [安裝與操作](docs/setup-and-operations.md)。已有環境時另開終端執行 `./start-comfyui.ps1`，設定引擎網址並同步模型庫。`start-all.bat` 是兩個啟動腳本的捷徑，不代替安裝。

## 第一次生成

1. 啟動平台與 ComfyUI；設定頁確認引擎網址，預設 `http://127.0.0.1:8188`。
2. 模型庫同步 checkpoint，選擇模型並登記正確架構／版本；空清單表示還需安裝模型。
3. 工作台選 Checkpoint／SDXL，填入提示詞與參數。模型預設需確認套用，保存草稿不會生成。
4. 明確按生成並查看任務；提交回應遺失時恢復原 UUID，避免重送。完成後到作品庫明確匯入／補齊圖片。
5. 已匯入作品可離線預覽、下載原圖／workflow、載入支援流程的原設定；載入不會自動生成。

首次硬體與模型配置需自行驗證。RTX 3060 的 Pony／Animagine 固定案例見 [驗收索引](docs/index.md#實機與歷史證據)；RTX 4080、FLUX GPU 生成與訓練仍有待辦。

## 功能與限制

| 範圍 | 已提供 | 限制與說明 |
| --- | --- | --- |
| Checkpoint | 文生圖、單張圖生圖、精確字串 seed、草稿、設定交換、最多四個有序 LoRA | batch 固定 1；[參考流程](docs/models/reference-workflows.md)、[LoRA](docs/models/multi-lora-workflow.md) |
| 局部編輯 | 遮罩筆刷／擦除／反相／PNG、v1 修補與 v2 內側羽化、原設定還原 | 一般草稿／交換／比較仍待 R07；[修補](docs/inpainting.md)、[羽化](docs/inpaint-feather.md) |
| Canny | ControlNet 庫、結構引導、CPU 預覽、v2 原邊緣保存與離線查看 | depth／pose／角色 adapter 未接入；[流程](docs/controlnet.md)、[預覽](docs/canny-preview.md) |
| FLUX.1 [schnell] | 元件庫、固定來源預檢、獨立表單／草稿／交換、提交與還原 | 固定來源存取／安裝及 GPU 生成驗收未完成；[FLUX](docs/models/flux-workflow.md) |
| 作品與素材 | 原圖／縮圖、搜尋、收藏、筆記、人工評分、封存／還原、素材用途與引用保護 | 封存不釋放檔案，無一般作品永久刪除；[整理](docs/artwork-library.md)、[比較](docs/artwork-comparison.md) |
| 實驗 | 固定案例、有限比較方案、保存／匯入、任務關聯與原始 JSON 報告 | 各組手動生成，無自動重試或品質評分；[方案](docs/experiment-plans.md)、[結果](docs/experiment-runs.md) |
| 執行 | 進度、取消／條件化停止、失敗保存、環境與資源快照、E01 裝置回報 | 未知不推定無 GPU；[裝置回報](docs/execution-device.md) |

尚未提供訓練、多租戶／付費、自訂節點編輯器或官方付費 API。設定還原不保證跨環境逐像素一致；實測的來源條件與品質偏差均保留。

## 日常操作

- 停止：平台與引擎各自在所屬終端按 Ctrl+C；停止平台不會中斷引擎工作。不要結束所有 Python 程序。
- 備份：停平台後保存完整 data，含 SQLite、素材、作品、job_inputs、control_edges。權重、外部目錄與需要的 runtime 證據另備份，見 [備份還原](docs/setup-and-operations.md#備份與還原)。
- 埠：8000 平台、8188 引擎、5173 Vite 開發預設；8001 等隔離埠不是日常依賴，見 [操作指南](docs/setup-and-operations.md)。

## 開發與文件

後端：`.venv/Scripts/python.exe -m unittest discover -s backend -p 'test_*.py'`。前端在 frontend 執行 `npm.cmd run build`、`check:api`、`check:experiments`、`check:inpaint`、`check:control`；不等同實機 GPU 或完整 UI 驗收。

- [文件索引](docs/index.md)：按工作流程找說明、API 與驗收。
- [架構與資料流](docs/architecture.md)：模組、任務狀態、原引擎與資料位置。
- [整理前 README 全文](docs/history/readme-before-q01-20261022.md)：舊限制與歷史測試數僅供追溯。
