# Q06 Windows CI 路徑別名回歸

首次 [Q06 CI](https://github.com/Zimkjdv/Model-Atelier/actions/runs/39806275637) 的 lock 安裝通過，但四個既有後端測試失敗：runner 的 TEMP 使用 `RUNNER~1` 等 8.3 別名，`Path.resolve()` 回傳長路徑。三個斷言以未正規化字串比較同一實體位置；模型路徑的故障注入也因比較短路徑而沒有命中已正規化的輸出位置。

本機以 GetShortPathNameW 設定子程序專用 TEMP／TMP，四項同樣失敗（4 tests，4 failures），無需修改產品程式或真實目錄配置。將測試預期值及故障注入目標正規化後重跑，四項通過；新增 `backend.test_windows_temp_alias` 持續重現該 runner 條件，沒有 8.3 支援時明列跳過。

實際模型輸出、解析後越界拒絕、報告目錄範圍及禁止覆寫保護均保留，未放寬產品路徑規則。這次修正獨立提交於 Q04 分頁之前；遠端新 run 的結果需另查，不能將本機綠燈當遠端已通過。
