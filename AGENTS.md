# Agent Instructions

This document provides instructions for AI agents working on this codebase.

## V2 Architecture Refactor

We are currently in the process of a major refactor, moving from a monolithic single-page application (SPA) to a multi-page application (MPA) architecture. This new architecture is referred to as "v2".

### Key Changes:

-   **Backend**: The backend is being refactored into a service-oriented architecture.
    -   `api_server_v2.py`: The main entry point for the backend API.
    -   `orchestrator_v2.py`: Manages the lifecycle of tasks.
    -   `worker_v2.py`: Processes individual tasks.
-   **Frontend**: The frontend is being split into multiple, independent HTML pages.
    -   `index_v2.html`: The main landing page.
    -   `downloader_v2.html`: Page for downloading files.
    -   `transcribe_v2.html`: Page for transcribing audio.
    -   `youtube_report_v2.html`: Page for displaying YouTube reports.
-   **Testing**: E2E tests for the v2 architecture are located in `src/tests/` and are suffixed with `_v2.js` or `_v2.cjs`. The Playwright config is `playwright.config.v2.js`.

### Development Workflow:

1.  **Run the backend in `mock` mode for frontend development and testing.** This simplifies the setup by not requiring real API keys or background workers.
    ```bash
    python src/core/orchestrator_v2.py mock
    ```
2.  **Run Playwright tests for the v2 architecture.**
    ```bash
    # Set the API_MODE for the test runner process itself
    API_MODE=mock npx playwright test --config=playwright.config.v2.js
    ```

### Communication Protocol:

-   **Language**: Please use Traditional Chinese for all user-facing communication, including commit messages, PR descriptions, and in-app text. Code comments can be in English for clarity for a wider audience, but Traditional Chinese is preferred if it doesn't compromise clarity.

-   **File Naming**:
    -   All new files related to the v2 architecture **must** have a `_v2` suffix in their filename (e.g., `my_feature_v2.py`, `styles_v2.css`).
    -   Test files must follow the pattern `*.spec_v2.js` or `*.spec_v2.cjs`.

-   **CSS Styling**:
    -   **Decision**: Per a recent architectural decision, all CSS for the v2 MPA pages **must be inlined** into the `<style>` tag of each respective HTML file.
    -   **Rationale**: This is to ensure each page is a self-contained component, simplifying deployment and eliminating dependencies on external CSS files, which was a source of bugs in the previous SPA architecture. Avoid creating separate `.css` files for v2 pages.

-   **Documentation**:
    -   Keep `plan_v2.md` updated with the latest progress.
    -   Document any significant changes or decisions in `Log.md`.

---

## Recommended Development Practices (JULES, 2025-09-03)

To improve stability and development speed, the following tools and practices are recommended for future work on this project.

### 1. E2E Test Debugging with Playwright Trace Viewer

When an E2E test fails, especially due to timeouts or unexpected UI states, the first step should be to analyze its trace file.

-   **How to Generate a Trace**: Run the test command with the `--trace on` flag.
    ```bash
    API_MODE=mock npx playwright test your_test_file.spec.js --config=playwright.config.v2.js --trace on
    ```
-   **How to View a Trace**: After the test fails, the output will provide a command to view the trace file. It opens a GUI that allows for "time travel" debugging, showing the DOM, console, and network requests at every step of the test.
    ```bash
    npx playwright show-trace <path-to-trace.zip>
    ```

### 2. Isolated Component Development with Storybook

For developing or debugging individual UI components (like a task item, a button, or a modal), using an E2E test is very inefficient. Storybook is the industry-standard tool for building UI components in isolation.

-   **Benefit**: It allows you to render a component with specific inputs ("props") without running the backend or the rest of the application. This makes debugging rendering logic much faster.
-   **Recommendation**: Consider setting up Storybook for this project to create a library of all reusable v2 components.

### 3. Frontend-Only Mocking with Mock Service Worker (MSW)

While the backend has a `mock` mode, frontend development can be further decoupled by using a frontend-level API mocking library.

-   **Benefit**: MSW intercepts outgoing `fetch` requests at the network level within the browser. This allows frontend developers to define API responses directly in the frontend code, completely removing the dependency on a running backend server during UI development.

### 4. Unit Testing for Business Logic

For complex Javascript logic (e.g., functions that process WebSocket data, manage application state), E2E tests are not the right tool.

-   **Recommendation**: Introduce a Javascript unit testing framework like **Vitest** or **Jest**. This allows you to test individual functions in milliseconds, ensuring the core business logic is correct before testing it as part of the larger application.

---

### Final Checks:

Before submitting your work, please ensure the following:
1. All v2 E2E tests pass (`API_MODE=mock npx playwright test --config=playwright.config.v2.js`).
2. All code is formatted according to the project's standards (e.g., using a linter/formatter if available).
3. `plan_v2.md` and `Log.md` are up-to-date.
4. The final commit message and PR description are in Traditional Chinese.
