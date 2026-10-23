# Fooocus SDXL 專用修補（R03）

`checkpoint-fooocus-inpaint-v3` 在一般 SDXL 基底上套用 Fooocus 專用 head／v2.6 patch，再對已保存遮罩重繪；最後沿用本平台的獨立內側羽化遮罩，合成回已縮放原圖。首版限定固定來源 Animagine 4.0 Opt、denoise 1、不組合 LoRA。一般 v1／v2 修補及其歷史仍可使用。

## 固定來源與相容範圍

- 外部節點：[Acly/comfyui-inpaint-nodes](https://github.com/Acly/comfyui-inpaint-nodes/tree/5b7681746fe19e563113d27366ba85236bc1ba5b)，固定 `5b7681746fe19e563113d27366ba85236bc1ba5b`／1.4.4；[原碼與接線](https://github.com/Acly/comfyui-inpaint-nodes/blob/5b7681746fe19e563113d27366ba85236bc1ba5b/nodes.py)、[GPL v3](https://github.com/Acly/comfyui-inpaint-nodes/blob/5b7681746fe19e563113d27366ba85236bc1ba5b/LICENSE)。原碼在獨立 ComfyUI 執行，沒有搬入 FastAPI。
- 官方權重：[head manifest](../models/fooocus-inpaint-head.json)、[v2.6 patch manifest](../models/fooocus-inpaint-v26.json)，固定作者 repository 修訂、大小與 SHA256。模型卡只標示 `openrail`，未附完整條款，manifest 保留未核實狀態；節點授權不等於權重或基底無限制使用。
- 基底：[Animagine 4.0 Opt](models/animagine-xl-4.0-opt.md)。後端要求其固定名稱、SDXL、hash 與大小登記；登記本身不能證明遠端檔案內容，實機驗收另全檔查核。

上游禁止 Turbo／Lightning／Hyper 等蒸餾合併版；本平台首版以固定基底及拒絕所有 LoRA 限制範圍。此模板使用 `VAEEncodeForInpaint` 接 Fooocus，因此 denoise 必須 1；上游 refine 的雙 latent 流程尚未接入，不能降低 denoise 後當成同一模板。

## 安裝與操作

將上述固定節點放在獨立引擎 `custom_nodes/comfyui-inpaint-nodes`，依該版本依賴準備引擎環境並重新啟動 ComfyUI。權重明確安裝：

```powershell
.\.venv\Scripts\python.exe -m scripts.install_model fooocus-inpaint-head --check
.\.venv\Scripts\python.exe -m scripts.install_model fooocus-inpaint-head
.\.venv\Scripts\python.exe -m scripts.install_model fooocus-inpaint-v26
```

檔案位於 `runtime/ComfyUI/models/inpaint`。安裝器固定來源且驗證大小／hash，不覆寫不符的正式檔案，不改動模型庫登記。

1. 模型庫確認固定 Animagine 的來源／hash／大小與 SDXL 登記。
2. 局部編輯選原圖、相同原始尺寸的遮罩；白色編輯、黑色保留。選「Fooocus SDXL 專用修補 v3」，會顯示 denoise 1；不會自動替換基底或清除 LoRA，條件不符時明示阻擋原因。
3. 設定提示、精確 seed、尺寸、grow_mask_by 與內側羽化半徑；可先用 CPU 預覽合成遮罩。預覽不載入專用模型或生成。
4. 明確生成。專用 endpoint 為 `POST /api/fooocus-inpaint/generate`，表單需 `inpaint_model=fooocus-v2.6`。模板的節點 16 載入固定 head／patch、17 接受節點 4 的去噪 latent，KSampler 使用專用 patch 模型；節點 7 仍是唯一作品。
5. 任務／作品可完整還原模型模式、原圖／遮罩／合成遮罩、半徑與精確 seed；展開來源快照查看固定權重。歷史下載不依目前表單重算。一般草稿、設定交換及比較方案尚未提供專用格式，嚴格拒絕部分保存。

固定模型／套件來源記於不可變來源快照；實際遠端節點 Git 版本未知時保持未知。提交前檢查新版 COMBO／舊選項清單、權重名稱與節點輸入輸出，原登記在交易及上傳／提交前核對。未知提交結果只恢復原 UUID，不自動生成新請求。

三份本地輸入仍存於 `data/job_inputs`；`reference-image`、`reference-mask`、`reference-blend-mask` 可離線查看與下載。完整 DATA 備份涵蓋這些檔案與原任務／作品；原設定還原後不會自動生成。

## 有限品質比較

固定 RTX3060／ComfyUI 0.34.0、Animagine 4.0 Opt、768²、20 steps、CFG 5、euler_ancestral／normal、grow 6、denoise 1。兩張素材取自 R01 生成作品，分別測試公園背景加入白花灌木與藍外套刺繡；沒有重新使用作者原圖作訓練。

每張素材明確執行：Fooocus seed A／半徑 0、A／16、B／16，以及一般 v2 seed A／16 對照，共八組。A=`9007199254740993`，B=`18446744073709551615`；A0→A16 觀察半徑，A16→B16 觀察 seed，v2→Fooocus A16 比較專用模型。各組唯一 UUID 與原圖／遮罩／處理後 PNG／模型來源／原流程分開保存，不是自動品質評分。

可解析結果、逐圖觀察與限制見 [R03 驗收](validation/fooocus-inpainting-20261023.md)。本機原始報告／DATA 在 `runtime/r03-live-20261023`，權重與圖片不納入 Git，需另行備份。

重跑 CLI 每次只執行一組，既有報告拒絕新生成；`--verify` 只 GET 核對原設定、輸入、遮罩與作品 hash，不補提交或匯入。例：

```powershell
.\.venv\Scripts\python.exe -m scripts.verify_fooocus_generation --target park --source <768方圖PNG> --radius 16 --seed 9007199254740993 --report runtime/new-fooocus.json
.\.venv\Scripts\python.exe -m scripts.verify_fooocus_generation --report runtime/new-fooocus.json --verify
```
