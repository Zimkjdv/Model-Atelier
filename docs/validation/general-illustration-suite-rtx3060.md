# 一般插畫固定測試集／RTX 3060（2026-10-08）

兩個既有固定來源 checkpoint × 四個自編案例，共八個單張 GPU 任務。CLI 見 [使用說明](../illustration-suite.md)；每個 invocation 各別保存一個原 UUID，不自動重送。原圖、模型／環境／量測快照、精確 workflow 及設定還原均核對，ComfyUI 停止後再使用 GET 驗證八份報告通過。

測試集 `general-illustration` v1，SHA256 `3adada6b8ce0aa69313ee0604dc280e96a6db6616b5e892d6b4f3f5feefe6ff7`。共同條件：1024×1024、28 steps、CFG 5、euler_ancestral／normal、denoise 1、seed `9007199254740993`、無 LoRA／參考素材；共同負提示詞為 `blurry, low quality, text, watermark`。只有 checkpoint 與案例正提示詞不同，沒有模型專用標籤優化。

平台主機 RTX 3060 12 GiB／約 64 GiB RAM、Windows 10 19045；ComfyUI 0.34.0、Python 3.12.10、PyTorch 2.14.0+cu130、驅動 616.56，預設動態 VRAM／CPU offload、模型／CLIP FP16、VAE bfloat16。固定來源大小／SHA256 每次重驗，登記版本 Pony `V6 XL`／Animagine `4.0 Opt`；來源與授權見各模型接入文件。沒有新增權重下載。

## 原圖視覺觀察

以下為開發助手逐張檢視原圖的主觀觀察；沒有代替使用者填數字分數、取平均或自動品質通過。共同條件不是作者最佳預設，不能概括所有提示格式、風格、角色、seed 或硬體表現。人物雙場景是文字條件比較，沒有角色 adapter／鎖定能力。

| 模型／案例 | 平台提交至觀察／原引擎起訖（s） | 原圖觀察 |
| --- | --- | --- |
| animagine-xl-4.0-opt / chair | 38.454 / 38.165 | 木椅與說明書可辨識，線條清楚；有棕色木紋，未完全符合純黑白，也未清楚畫出組裝步驟。 |
| animagine-xl-4.0-opt / lake | 24.901 / 24.736 | 山湖、日出與松樹清楚；出現多艘船，左下船只有局部，未精確符合單船構圖。 |
| animagine-xl-4.0-opt / traveler-bookshop | 24.914 / 24.651 | 短黑髮、圓眼鏡、藍外套、紅書與暖窗光皆可辨識，完整人物；雙手持書不完全可見。 |
| animagine-xl-4.0-opt / traveler-station | 24.882 / 24.719 | 站台、紅書及雙手動作可辨識，黑髮眼鏡藍外套保留；與書店的臉形、衣領／扣子有差異，不是角色鎖定。 |
| pony-v6-xl / chair | 40.845 / 38.775 | 灰黑線稿，出現椅子與桌面／辦公物件，沒有清楚木椅組裝說明；提示服從不足。 |
| pony-v6-xl / lake | 27.021 / 25.295 | 湖山與右側松樹可辨識；近處船在右側且有人物，違反 no humans 與左下小船要求。 |
| pony-v6-xl / traveler-bookshop | 25.135 / 24.934 | 黑髮、眼鏡、藍外套、紅書、書架與完整人物保留；筆觸及光色偏柔和，雙手可見。 |
| pony-v6-xl / traveler-station | 27.101 / 25.618 | 黑髮、眼鏡、藍外套及紅書延續，帶列車元素的走道；站台邊界不明確，褲子／鞋子／外套細節與書店不同。 |

Animagine 在此批呈現較清楚的輪廓與場景光影，Pony 的畫面筆觸較柔和；兩者都能保留旅人的共同外觀要素，但衣著及臉部細節仍改變。山湖構圖與木椅指示仍有偏差，不能將八次生成成功視為提示完全符合或畫風品質認證。

平台秒數包含佇列與查詢間隔；引擎起訖包括載入／快取。各模型首個案例有不同載入／初始化條件，單次結果不作速度排名或純 GPU benchmark。提交前記憶體快照可在原任務／作品查看；整卡取樣不是任務專用峰值或最低 VRAM，詳見 [量測定義](../job-measurements.md)。

## 保存與驗收

- 八份報告：`runtime/suite-{model}-{case}-20261008.json`，完整來源／案例／測試集 hash、原圖 hash、原 UUID 與設定；同條件 CLI `--verify-report` 只讀原紀錄。
- 原任務／作品：`runtime/roadmap-live-data-20261008`；作品筆記包含案例名稱及上述觀察，可用既有搜尋和最多四張並排功能比較。四項評分皆 null，等待使用者判斷。
- 結果摘要：`runtime/suite-observations-20261008.json`，不納入 Git 或正式作品庫。沒有自動分組／批次提交或實驗計劃持久化。
- 394 項後端測試（393 通過、1 項既有 Windows 權限跳過）、Vue 型別／建置通過。瀏覽器工具環境故障，新的 UI 實機驗收未完成。
- 更多模型與 seed、作者提示格式比較、參考引導／局部編輯、FLUX GPU 與 RTX 4080 仍待後續；有限測試不把廣泛品質待辦全數勾選。
