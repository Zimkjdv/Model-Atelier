# PC02 提示詞編輯區整併驗收

日期：2026-11-07（Asia/Taipei）。使用者指出中文轉換器放在原英文欄位下方、表單過長，要求改善外觀與位置，評估和實際生成提示詞整併。

## 完成行為

- 簡易創作、一般 Checkpoint、基礎 FLUX 共用同一個提示詞編輯區；保留 `simple-prompt`、`draft-prompt`、`flux-prompt` 的原 textarea、綁定及欄位預檢，將轉換入口放到標題列。
- 平常顯示單一「實際生成提示詞」及字數，不再堆疊另一張轉換器表單。點「中文轉英文」開啟 native dialog；桌面並排中文與英文預覽，窄視窗上下排列。
- 依後續回饋移除「用中文，構思你的畫面」，僅保留「提示詞助手」作為標題及對話框可讀名稱，避免重複佔用空間。
- 「格式與保留詞」、「本機 LLM 設定」預設收起，摘要顯示目前格式／模型。設定僅在開啟助手時讀取，仍需明確保存。
- 轉換結果標記「待套用」，可修改；點底部套用才更新原英文，關閉助手並在原編輯區提示成功。原負面提示詞及其他生成參數不變，不自動提交圖片。
- 短視窗只捲動內容區，頂部關閉與底部返回／套用保持可見。助手開啟時背景表單不能操作；Escape、關閉與返回還原焦點至原入口。
- 已完成的預覽與中文草稿可關閉後再開繼續，不會自動再轉換或套用。轉換中關閉則取消前端等待，忽略遲到回覆。原英文、上下文、模型、中文或格式改變，及工作台停用仍清除過期結果。
- 唯讀配方不顯示中文入口；開始編輯後才可轉換。配方修改提示、原任務 UUID／端點恢復、LoRA、參考圖及 FLUX 元件入口維持原流程。

## 實際驗證

| 檢查 | 結果 |
| --- | --- |
| `npm.cmd run build` | Vue 型別及 Vite 正式建置通過；既有大於 500 kB chunk 提示保留 |
| `npm.cmd test` | 前端 API、生命週期、原 UUID／未知回覆恢復、實驗、遮罩、控制與預檢契約通過 |
| `npm.cmd run format:check`、`npm.cmd run lint` | 通過 |
| 四份受影響 Chromium spec | 35 個不同案例通過：提示詞助手 12、簡易創作 11、配方 10、FLUX 附加流程 2 |
| 最後標題與成功提示調整後 | 重驗受影響的提示詞助手 12 項，全數通過；未重跑未變動的其他案例 |
| 真實本機平台 | 唯讀 `GET http://127.0.0.1:8000/api/prompt-converter/settings` 回 200；沒有重啟或改寫正式資料 |

12 項助手案例包含 1440／390px 的中英佈局、主工作台寬度不受視窗樣式影響、關閉按鈕不越界、預覽編輯與手動套用、負面提示詞不變、成功提示及焦點還原；另涵蓋連點、來源／原英文／模型／切頁／關閉後的過期回覆、服務與格式錯誤、設定保存、唯讀配方與 FLUX 入口、關閉後續編，以及 390×640 的捲動內容與固定底部操作。桌面與手機助手執行 axe 檢查，無 violations；不當作完整讀屏／觸控認證。

```powershell
# frontend
npm.cmd run build
npm.cmd test
npm.cmd run format:check
npm.cmd run lint
npx.cmd playwright test tests/prompt-converter.spec.ts tests/simple-creation.spec.ts tests/simple-recipes.spec.ts tests/flux-extensions.spec.ts
```

截圖來自隔離 fixture，英文回覆為固定測試資料，不是新的模型耗時／品質證據：

- `runtime/quality/browser-results/prompt-converter-1440px-pr-83a5a-reserve-generation-settings/prompt-editor-1440.png`：整併後主編輯區。
- 同目錄 `converter-1440.png`：桌面並排助手。
- `runtime/quality/browser-results/prompt-converter-390px-pre-7d297-reserve-generation-settings/converter-390.png`：窄視窗助手。
- `runtime/quality/browser-results/prompt-converter-short-mob-c4eae-ing-apply-and-close-in-view/converter-settings-390.png`：390×640 展開設定時的固定操作列。

原尺寸視覺檢查確認圓角、層級、文字／按鈕及響應式排列。過程發現一處 Vue 全域選擇器誤用會影響工作台寬度，已修正為元件內的 scoped selector，並補上整頁寬度／按鈕邊界檢查；另解除既有全域 header 固定高度對助手標題的影響。35 項完整回歸中，Windows fixture 關閉時曾出現 `ConnectionResetError [WinError 10054]` 提示，斷言與退出碼皆通過，沒有隱藏錯誤或增加自動重試。

本次不修改後端契約、模型權重、CPU/GPU 設定或語意轉換規則，不重新執行模型品質或 ComfyUI/GPU 實機驗收。先前語意與 CPU 證據仍見 [PC01](prompt-converter-20261031.md)。
