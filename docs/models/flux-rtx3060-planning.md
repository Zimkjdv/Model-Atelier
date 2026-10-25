# FLUX.1 與 RTX 3060 的實作前置判斷

更新日期：2026-10-25。使用者提供 FLUX／RTX 3060 討論作為參考，並要求若 RTX 3060 不適合、需要 RTX 4080，須在實作／下載與 GPU 實測前先說明。該對話是待核對的建議，不作為本平台硬體驗收證據。

## 已核對的第一手資料

- [BFL FLUX.1-schnell 模型卡](https://huggingface.co/black-forest-labs/FLUX.1-schnell)：schnell 的少步數設計與 CPU offload 範例。頁面仍顯示取得檔案前需登入／接受存取條件；不能以可讀模型卡當作固定權重已可下載。
- [Diffusers Flux 文件](https://huggingface.co/docs/diffusers/api/pipelines/flux)：量化、模型／逐層 CPU offload、VAE 切片等節省記憶體方法。這是 Diffusers 的範例，不等於本專案 ComfyUI 設定或特定 3060 的效能保證。
- [Diffusers 量化與卸載組合](https://huggingface.co/docs/diffusers/optimization/speed-memory-optims)：表格是 RTX 4090 與特定配置的量測，不直接當 3060／4080 的速度或容量門檻。
- [ComfyUI 官方 Flux 範例](https://comfyanonymous.github.io/ComfyUI_examples/flux/)：提供降低權重／文字編碼器記憶體的 FP8 選項，並提醒精度可能影響品質；不是所有元件同時載入 GPU 的保證。
- [ComfyUI-GGUF 原專案](https://github.com/city96/ComfyUI-GGUF)：GGUF 需其自訂載入節點，主模型改用 Unet Loader (GGUF)，量化 T5 也有不同 loader；專案對 LoRA 支援仍有實驗說明。不能改個檔名就當成原生 UNETLoader 相容。

官方文件支持「可研究節省記憶體的配置」，但上述資料沒有替本平台固定來源、固定 ComfyUI／節點、RTX 3060 12 GiB、特定 RAM／尺寸組合作出驗收。對話中的 GGUF Q4／512² 單張與 RAM 32GB 只能作起始規劃，尤其 32GB 不認列為官方最低 RAM；也不把 schnell 的少步數當作權重顯存需求同比下降。

## 建議排程與實作邊界

T07 → T08 完成後，依 F01 → F02 → F03 → F04 推進。2026-10-25 [F01](flux-installation.md) 已取得固定來源並完成四份實際權重安裝／完整 hash。接續以現有 [FLUX 專用流程](flux-workflow.md)評估 `weight_dtype` 的 FP8 與 CPU 編碼器選項，記錄實際精度、卸載、RAM／VRAM、時間、成功／失敗及品質。第一次小型試跑可規劃 512×512、batch 1，逐級增加；這仍是待驗證策略，來源安裝不算 GPU 通過。

後續 [F02](../validation/flux-runtime-20261025.md) 已在這台 RTX 3060／約 64 GiB RAM 完成兩次原生 512×512、4 步、FP8 主模型／CPU 編碼器案例，記錄實際 CPU→CUDA BF16 cast 與 CPU 常駐參數。程序 RSS 取樣最高約 36–37 GiB，主機共用用量接近 64 GiB；不能承諾 32 GiB RAM 或更大尺寸。尚未要求為此小型配置改用 4080，完整平台保存／OOM 與其他配置仍依後續待辦實測。

若要 GGUF Q4，須另核對固定量化來源與檔案 hash、條款、ComfyUI-GGUF 原碼／依賴版本、自訂節點介面及量化 T5。流程識別、來源快照、失敗恢復、LoRA／參考能力與舊紀錄還原需獨立接入；不能悄悄替換既有固定 BF16 manifest，也不把它標成原 F01 權重已安裝。尚未選定或安裝 GGUF 路線。

## 執行前先提醒使用者

1. 列出官方依據的適用版本，與目前 3060 12 GiB／實際系統 RAM、剩餘磁碟對照；無官方最低值就標未知。
2. 如容量可能超出、必須量化／卸載、速度或品質有代價，先說明；不能把「3060 能跑 FLUX」的泛用討論當作大檔下載或較高負載的可執行證據。
3. 如固定目標配置需要改用 4080，先告知原因、依據與可替代配置，再安排後續實作與實測。GPU 需求與 BFL 來源存取是兩個獨立條件。
4. 3060、4080、原精度與量化流程分開保存證據；3060 成功不認列 E02／E03 的 4080 驗收。

此文件是查核與規劃補充，不取代 [ROADMAP](../../ROADMAP.MD#f02) 的 GPU／精度待驗收狀態。權重下載與實際 hash 另列 [F01 證據](../validation/flux-installation-20261025.md)，沒有更換固定主模型來源。
