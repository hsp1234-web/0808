> **[Jules's Note]**
> 本文件描述的是專案早期的 V33 架構。此架構已被後續的「儀表板-管理器-工具箱」及「預烘烤環境」模型取代。本文件僅供歷史參考，最新的架構設計請參閱根目錄下的 `research_0808.md` 文件。

---

# 🏗️ 專案架構藍圖 (V33)

本文檔闡述了「鳳凰之心」專案在 V33 版本後採用的標準化、專業化專案架構。此架構的設計目標是實現**高度的模組化、清晰的職責分離、以及在不同環境下（本地/CI vs. Colab）的穩定、可複現執行**。

---

## 1. 高層次設計哲學

我們遵循業界公認的 Python 專案最佳實踐，其核心思想包括：

- **源碼佈局 (Source Layout)**: 所有的核心應用程式碼都應位於 `src/` 目錄下。這可以防止意外的、依賴相對路徑的導入，並確保專案被正確地安裝。
- **單一職責原則**: 每個檔案、每個模組、每個腳本都應該只有一個明確的、集中的職責。
- **環境隔離**: **絕不**在系統的全域 Python 環境中進行開發或部署。所有操作都必須在一個專案獨有的虛擬環境 (venv) 中進行。
- **依賴管理**: 所有的依賴都應在 `requirements/` 目錄中進行顯式聲明和分組，並透過 `pip-tools` 等工具進行鎖定，以保證環境的可複現性。
- **配置外部化**: 應用程式的配置（如金鑰、資源路徑等）應與程式碼分離，統一存放在 `config/` 目錄中。

---

## 2. 目錄結構詳解

以下是我們標準的目錄結構，以及每個部分的職責說明。

```
/
├── .gitignore             # Git 忽略設定，用於排除 venv、快取等檔案
├── BUG.MD                 # 關於專案歷史中重大 BUG 的分析與復盤文件
├── README.md              # 專案的入口文件，提供快速上手指南
├── archive/               # 【封存】存放舊的、不再使用的參考資料或程式碼
├── config/                # 【設定】存放所有環境設定檔 (如 resource_settings.yml)
├── debug/                 # 【偵錯】存放用於開發與偵錯的輔助腳本
│   ├── colab_runner_debug_1.py # 舊版的 Colab 偵錯腳本
│   ├── debug_ALL.py       # (V33 新增) 全功能自動化偵錯腳本
│   └── report_debug_1.py  # 舊版的報告偵錯腳本
├── docs/                  # 【文件】所有專案的技術文件
│   ├── ARCHITECTURE.md    # (本文件) 專案的架構藍圖
│   ├── CHANGEL.md         # 專案的重大版本變更日誌
│   ├── Colab_Guide.md     # Google Colab 環境的操作指南
│   ├── MISSION_DEBRIEFING.md # 歷史任務的日誌與復盤
│   ├── TEST.md            # 專案的測試策略與執行指南
│   └── e2e.md             # 端對端測試框架的設計細節
├── log_archives/          # 【日誌存檔】存放歷史日誌的壓縮檔
├── pyproject.toml         # Python 專案的標準設定檔 (PEP 518)
├── pytest.ini             # Pytest 測試框架的設定檔
├── reports/               # 【報告】存放由系統生成的各種報告檔案
├── requirements/          # 【依賴】統一管理所有 Python 依賴
│   ├── base.in            # 核心依賴的來源檔案
│   ├── base.txt           # 鎖定的核心依賴
│   ├── dev.in             # 開發依賴的來源檔案
│   ├── dev.txt            # 鎖定的開發依賴
│   └── ...
├── run/                   # 【Colab 入口】為 Colab 環境保留的啟動腳本
│   ├── colab_runner.py    # Colab 儀表板前端啟動器 (V33)
│   └── report.py          # Colab 報告生成觸發器 (V33)
├── scripts/               # 【主要腳本】供開發者/CI 使用的核心自動化腳本
│   ├── local_run.py       # 本地/CI 環境的總啟動器
│   ├── run_server_only.py # 輕量級的後端服務啟動器
│   └── safe_runner.py     # (V68 新增) 帶看門狗的通用安全啟動器，用於監控背景服務
├── src/                   # 【應用程式碼】所有專案的核心原始碼
│   └── phoenix_core/      # 我們的 Python 套件
│       ├── __init__.py
│       ├── api/           # API 相關模組 (FastAPI 路由)
│       ├── background/    # 背景任務相關模組
│       ├── kernel/        # 核心內核模組 (設定、認證、硬體等)
│       ├── modules/       # 各個獨立的功能模組 (資料、監控等)
│       ├── utils/         # 通用的工具函式模組
│       ├── database.py    # 資料庫連線與初始化邏輯
│       ├── db_queries.py  # 資料庫查詢函式
│       ├── main.py        # FastAPI 應用程式主入口
│       ├── report_generator.py # 報告生成核心邏輯
│       └── watchdog.py    # 看門狗監控邏輯
│
└── tests/                 # 【測試碼】所有 pytest 測試
    ├── __init__.py
    ├── conftest.py        # Pytest 的共享 Fixture 設定檔
    ├── e2e/               # 端對端測試
    ├── integration/       # 整合測試
    ├── performance/       # 效能測試
    └── unit/              # 單元測試
```

---

## 3. 執行流程解析

> **[開發者註記 - 2025-08-15]**
> 下述執行流程描述的是歷史版本。在目前的實作中，特別是為了 E2E 測試和本地開發，我們採用了 `circus` 作為程序管理器。相關的啟動腳本是 `scripts/run_server_for_playwright.py`，其設定檔為 `config/circus.ini.template`。這種方式取代了舊的 `local_run.py` 啟動流程，提供了更穩健的背景服務管理。要了解如何快速啟動和驗證當前環境，請參閱根目錄下的 `README.md` 和 `AGENTS.md`。

為了適應不同的使用場景，我們設計了兩條並行但相互關聯的執行路徑：

### **路徑一：本地/CI 自動化流程**

這是最核心、最穩定的執行路徑，由我們的「黃金標準」啟動器驅動。

**[開發者/CI 系統]** `->` **`python scripts/local_run.py`**
1.  **[local_run.py]** 清理並建立 `.venv` 虛擬環境。
2.  **[local_run.py]** 安裝 `requirements/` 中的所有依賴。
3.  **[local_run.py]** 執行 `pip install -e .`，將 `src/phoenix_core` 安裝為可編輯套件。
4.  **[local_run.py]** 呼叫 `src.phoenix_core.main` 中的核心邏輯函式。
5.  **[核心邏輯]** 執行任務，並生成 `state.db`。
6.  **[local_run.py]** 呼叫報告生成邏輯。
7.  **[報告邏輯]** 讀取資料庫，生成 Markdown 報告。
8.  **[local_run.py]** 流程結束。

### **路徑二：Colab 視覺化流程**

這條路徑為使用者提供了互動式的儀表板，其後端由一個穩定的、隔離的服務支撐。

**[Colab 使用者]** `->` **點擊執行 `run/colab_runner.py`**
1.  **[colab_runner.py]** 顯示 HTML 儀表板前端。
2.  **[colab_runner.py]** 在背景啟動 FastAPI 伺服器 (`src.phoenix_core.main:app`)。
3.  **[儀表板前端]**
    *   透過 JavaScript，每秒向後端 API 發送請求 (或直接讀取資料庫)。
    *   接收後端回傳的 JSON 數據，並更新儀表板上的狀態。
4.  **[Colab 使用者]** `->` **中斷 `colab_runner.py` 的執行**
5.  **[colab_runner.py]** 捕捉中斷信號，終止背景服務進程。
6.  **[Colab 使用者]** `->` **點擊執行 `run/report.py`**
7.  **[report.py]** 呼叫報告生成邏輯，生成最終報告。

---

此架構透過清晰的職責劃分和環境隔離，確保了專案在不同場景下的健壯性和可維護性，為未來的迭代開發奠定了堅實的基礎。
