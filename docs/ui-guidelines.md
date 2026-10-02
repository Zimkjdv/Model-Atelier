# 介面視覺規範

共用色彩及控制元件狀態集中於 `frontend/src/theme.css`，頁面只保留布局與內容特有樣式。

- 字體：Inter／Segoe UI／Microsoft JhengHei／sans-serif；表單與按鈕繼承字體。
- 表單：深色輸入底、共用文字與邊框、7px 圓角；主要內容與 placeholder 分層。
- 提示：`.notice` 為一般訊息、`.notice.warning` 為警告、`.notice.success` 為成功。必須附文字，不以顏色單獨表示狀態。
- 錯誤使用 `role=alert`，操作結果使用 `role=status`；載入文字說明目前動作，空清單說明可採取的下一步。
- 鍵盤：2px 共用 focus-visible 外框；不可用控制使用 disabled，游標不代表載入狀態。
- 布局：卡片布局留在各元件，相關操作按鈕使用同一 actions 區及可換行間距，窄視窗不強迫固定寬度。
- 尊重系統減少動態效果偏好。

已套用創作、模型、作品與模型目錄的共用輸入色彩。維持現有操作流程與參數，不改寫保存資料。
