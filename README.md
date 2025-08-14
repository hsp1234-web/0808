# 後端品質保證進化藍圖 - 實作範例

本專案旨在實作「後端品質保證進化藍圖」中所描述的核心概念。透過一個簡化的後端服務模型，我們展示了如何建立一個以「數據驅動」為核心的診斷體系，為 AI 助理提供進行根本原因分析所需的「數位證據」。

## 核心概念

這個實作範例圍繞兩個核心概念構建：

1.  **結構化日誌 (Structured Logging)**: 所有服務的日誌都以統一的 JSON 格式輸出，使機器能夠輕易地解析和查詢。
2.  **全鏈路追蹤 ID (Correlation ID)**: 任何進入系統的請求都會被分配一個唯一的 `correlation_id`，此 ID 會在所有服務間傳遞，讓我們能將一次操作在後端所有環節的日誌串聯起來。

## 專案結構

```
.
├── services/               # 核心後端服務
│   ├── __init__.py
│   ├── api_server.py       # 模擬 API 伺服器，請求的進入點
│   ├── orchestrator.py     # 業務流程編排器
│   └── worker.py           # 執行具體任務的工作者
├── utils/                  # 共用工具模組
│   ├── __init__.py
│   └── logger.py           # 結構化日誌 (JSON Formatter) 的實作
├── logs/                   # 存放集中化的日誌檔案
│   └── backend.log         # 所有服務的日誌都會寫入此檔案
├── evidence_packages/      # 存放生成的「數位證據包」
│   └── ...
├── main.py                 # 用於啟動模擬流程的主腳本
└── create_evidence_package.py # 用於從日誌中提取證據包的工具
```

## 如何使用

請遵循以下步驟來體驗整個流程：

### 步驟 1: 運行模擬以產生日誌

首先，我們需要運行主腳本 `main.py` 來模擬一系列的後端請求。這將會觸發所有服務，並在 `logs/backend.log` 中產生對應的結構化日誌。

在終端機中執行：
```bash
python3 main.py
```
運行後，您會看到模擬過程的輸出，並被告知日誌已成功寫入。

### 步驟 2: 產生數位證據包

模擬運行完畢後，`logs/backend.log` 檔案中會包含多次請求的日誌。現在，我們可以針對某一次特定的請求（由 `correlation_id` 標識）來產生「數位證據包」。

1.  **查看日誌並選擇一個 ID**:
    打開 `logs/backend.log` 檔案。您會看到多個 JSON 物件，每一個都代表一條日誌。找到您感興趣的請求，並複製其 `correlation_id` 的值。

    *提示：您可以選擇在模擬中失敗的那個請求的 ID，以查看包含錯誤資訊的完整證據包。*

2.  **執行證據包生成工具**:
    使用您複製的 `correlation_id` 作為參數，執行 `create_evidence_package.py` 腳本。

    例如 (請將 ID 替換為您自己的):
    ```bash
    python3 create_evidence_package.py f55905ff-bdad-47cf-8517-75b9dc45c139
    ```

3.  **查看證據包**:
    腳本執行成功後，會在 `evidence_packages/` 目錄下生成一個名為 `evidence_{correlation_id}.json` 的檔案。

    打開這個檔案，您會看到一個 JSON 陣列，其中包含了與該 `correlation_id` 相關的所有日誌，並按照時間順序排列。這份檔案就是一份高度聚焦、專為單次失敗事件量身打造的「數位證據包」，可以被直接提交給 AI 助理進行分析。
