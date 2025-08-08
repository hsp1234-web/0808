# V63 - Colab 安裝器修正技術報告

**日期**: 2025-08-04
**作者**: Jules (AI Software Engineer)
**狀態**: 已完成

## 1. 問題背景 (Context)

在 `V62` 版本的 `run/colab_runner.py` 中，我們觀察到一個致命的啟動錯誤。當腳本試圖在 Colab 環境中建立虛擬環境並安裝核心依賴時，程序會因一個非預期的參數錯誤而崩潰。

錯誤日誌明確指向 `uv pip install` 指令：
```
[CRITICAL] 安裝套件 aiohttp==3.12.15 失敗:
error: unexpected argument '--ignore-installed' found
```

本報告旨在深入分析此問題的根本原因，並記錄我們的解決方案，以作為未來開發的參考。

## 2. 根本原因分析 (Root Cause Analysis)

問題的核心在於 **工具鏈的參數不相容性**。

1.  **歷史包袱 (`pip` 的行為)**：在過去使用原生 `pip` 作為安裝器的版本中，我們引入了 `--ignore-installed` 參數。根據專案的歷史研究文件 `docs/research.md`，這樣做的目的是為了解決一個 `pip` 的特定問題：`pip` 在安裝時會偵測到 Colab 全域環境中已存在的套件，並「智慧地」跳過在我們的本地虛擬環境 (`.venv`) 中的安裝。然而，後續的執行器（如 Uvicorn）嚴格限制在 `.venv` 中尋找模組，因此導致 `ModuleNotFoundError`。`--ignore-installed` 參數強制 `pip` 忽略全域套件，確保所有依賴都確實安裝在虛擬環境中。

2.  **新工具 (`uv`) 的引入**: 為了大幅提升安裝速度，我們根據 `docs/research.md` 的建議，將安裝工具從 `pip` 全面升級為 `uv`。`research.md` 中的對照實驗明確指出，`uv` 在建立虛擬環境和安裝依賴上，比 `pip` 有超過 10 倍的性能優勢。

3.  **錯誤的參數遷移**: 在將安裝指令從 `pip` 遷移到 `uv` 的過程中，開發者錯誤地保留了 `--ignore-installed` 這個參數。然而，`uv` 的命令列工具並沒有這個參數，它的設計哲學使其在透過 `--python` 旗標明確指定了目標虛擬環境的 Python 解譯器後，就能夠正確且乾淨地在該環境中進行安裝，自然地就避免了 `pip` 的那個老問題。

**結論**: 這次的失敗，是一次典型的在技術棧升級過程中，未能充分理解新工具的特性，而錯誤地保留了舊工具的「補丁」所導致的問題。

## 3. 解決方案與實作 (Solution and Implementation)

解決方案非常直接且清晰：

*   **目標檔案**: `run/colab_runner.py`
*   **定位**: `ServerManager` 類別中的 `_setup_environment` 方法。
*   **修改前**:
    ```python
    install_command = ["uv", "pip", "install", "--python", str(venv_python), "--ignore-installed", dep]
    ```
*   **修改後**:
    ```python
    install_command = ["uv", "pip", "install", "--python", str(venv_python), dep]
    ```

我們簡單地移除了 `uv` 不支援的 `--ignore-installed` 參數。

同時，為了配合這次修正，我們將 `run/colab_runner.py` 中的所有版本標識從 `V62` 更新為 `V63`，並在檔案頂部的更新日誌和 `docs/CHANGEL.md` 中清楚地記錄了這次變更。

## 4. 經驗教訓與未來建議 (Lessons Learned and Future Recommendations)

1.  **深入理解工具鏈**: 在引入或替換核心工具鏈（如套件管理器、編譯器、測試框架）時，必須投入時間去閱讀其官方文件，理解其設計理念和命令列參數的差異，絕不能假設新工具會與舊工具的行為完全一致。
2.  **註解的重要性**: 在使用 `--ignore-installed` 這樣的「補丁」或「Workaround」時，應該在程式碼旁留下清晰的註解，解釋為什麼需要它。這樣在未來進行重構或升級時，其他開發者才能判斷這個補丁是否仍然必要。
3.  **信任現代化工具**: `uv` 是一個現代化的 Python 工具，其設計已經解決了許多 `pip` 和 `venv` 的歷史痛點。我們應該更信任這些新工具的預設行為，而不是將舊有的思維定勢強加其上。

此次事件再次凸顯了在快速迭代的軟體開發中，保持技術文件（如 `research.md`）的更新與傳承，以及在進行技術棧遷移時保持嚴謹和細心的重要性。
