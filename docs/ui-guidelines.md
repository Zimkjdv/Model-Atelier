# 介面視覺規範

共用色彩及控制元件狀態集中於 `frontend/src/theme.css`，頁面只保留布局與內容特有樣式。

- 字體：Inter／Segoe UI／Microsoft JhengHei／sans-serif；表單與按鈕繼承字體。
- 表單：深色輸入底、共用文字與邊框、7px 圓角；主要內容與 placeholder 分層。
- 提示：`.notice` 為一般訊息、`.notice.warning` 為警告、`.notice.success` 為成功。必須附文字，不以顏色單獨表示狀態。
- 錯誤使用 `role=alert` 或合適 live region，操作結果使用 `role=status`；非緊急的連線保存結果沿用 polite status，不強制中斷目前工作。載入文字說明目前動作，空清單說明可採取的下一步；依 [W3C 狀態訊息](https://www.w3.org/WAI/WCAG22/Understanding/status-messages.html) 提供可程式辨識的公告。
- 鍵盤：2px 共用 focus-visible 外框；不可用控制使用 disabled，游標不代表載入狀態。
- 布局：卡片布局留在各元件，相關操作按鈕使用同一 actions 區及可換行間距，窄視窗不強迫固定寬度。
- 尊重系統減少動態效果偏好。

一般文字對比至少 4.5:1、大字至少 3:1；深色漸層需另核對最亮背景，不能只看自動工具的 violations。側欄、GPU 卡片標記及畫布說明使用共用文字 token；裝飾圖示搭配可讀名稱。收藏／選取的 `aria-pressed` 必須為布林值，不能直接傳入資料庫的 0／1。

頁面只保留一個主要 h1，內部表單與卡片依 h2／h3 分層。窄版圖示導覽仍保留可讀名稱；分頁群組以對應 role 命名。可橫向捲動的資料表或診斷預覽可接收鍵盤焦點，套用共用 2px focus-visible；切頁與跳至主內容的 main 焦點不畫控制元件外框。

已逐頁核對六個主頁及四流程的九個入口、1440px／390px 與展開／錯誤等狀態，重跑入口及證據見 [V06 驗收](validation/ui-accessibility-20261023.md)。自動檢查的 incomplete 須配合截圖、鍵盤及漸層端點判讀；不代表完整 WCAG 認證、實體讀屏或實機觸控通過。新增頁面／狀態／主題需更新矩陣。
