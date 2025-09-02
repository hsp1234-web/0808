import subprocess
import sys
import logging
import multiprocessing
import time
import argparse
from pathlib import Path

# --- Logging Setup ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
log = logging.getLogger('E2E_Test_Launcher')

def run_playwright_tests(test_files: list):
    """
    Target function to run Playwright tests in a subprocess.
    """
    log.info("Subprocess started: Running Playwright tests...")

    if test_files:
        test_args = test_files
        log.info(f"--- Running specified Playwright tests: {test_args} ---")
    else:
        # 預設執行 comprehensive UI 測試
        test_args = ["src/tests/e2e_comprehensive_ui.spec.js"]
        log.info(f"--- No specific test file provided, running default: {test_args} ---")

    # 使用 bun 來執行，因為專案依賴 bun
    command = ["bun", "playwright", "test"] + test_args
    try:
        # 使用 Popen 以便我們可以串流輸出，但為了簡單起見，暫時用 run
        result = subprocess.run(command, check=True, text=True, encoding='utf-8')
        sys.exit(0)
    except subprocess.CalledProcessError as e:
        log.error(f"Playwright tests failed with exit code {e.returncode}.")
        sys.exit(e.returncode)
    except FileNotFoundError:
        log.error("`bun` command not found. Please ensure bun is installed and in your PATH.")
        sys.exit(1)

def install_node_deps():
    """Install Node.js dependencies using bun."""
    log.info("--- Checking and installing Node.js dependencies (bun) ---")
    try:
        subprocess.run(["bun", "install"], check=True, capture_output=True, text=True, encoding='utf-8')
        log.info("✅ Node.js dependencies installed successfully.")
    except Exception as e:
        log.error(f"❌ Failed to install Node.js dependencies: {e}", exc_info=True)
        raise

def install_python_deps():
    """Install all Python dependencies, including the project in editable mode."""
    log.info("--- Installing all Python dependencies ---")
    try:
        packages_to_install = ["psutil", "requests", "uv", "httpx"]
        command = [sys.executable, "-m", "pip", "install"] + packages_to_install

        project_root = Path(__file__).resolve().parent.parent
        requirements_dir = project_root / "requirements"

        if requirements_dir.is_dir():
            req_files = sorted(list(requirements_dir.glob("*.txt")))
            log.info(f"Found requirement files: {[f.name for f in req_files]}")
            for req_file in req_files:
                command.extend(["-r", str(req_file)])

        log.info("Installing external dependencies...")
        subprocess.check_call(command)
        log.info("✅ External dependencies installed successfully.")

        log.info("Installing the project in editable mode (-e)...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-e", "."])
        log.info("✅ Project installed successfully in editable mode.")

    except Exception as e:
        log.error(f"❌ Failed to install Python dependencies: {e}", exc_info=True)
        raise

def main():
    """
    Main launcher to manage the test subprocess with a timeout.
    """
    parser = argparse.ArgumentParser(description="E2E Test Launcher")
    parser.add_argument('test_files', nargs='*', help='Specific Playwright test files to run. If not provided, runs the default comprehensive UI test.')
    parser.add_argument('--timeout', type=int, default=300, help='Global timeout for the entire test run in seconds.')
    args = parser.parse_args()

    log.info(f"--- Starting E2E Test Launcher (Total timeout: {args.timeout} seconds) ---")
    log.info(f"--- Test files to run: {args.test_files or 'Default'} ---")

    try:
        install_node_deps()
        install_python_deps()
    except Exception:
        log.critical("Dependency installation failed. Cannot proceed with tests.", exc_info=True)
        sys.exit(1)

    # 將要傳遞給子程序的參數打包
    process_args = (args.test_files,)
    test_process = multiprocessing.Process(target=run_playwright_tests, args=process_args)
    test_process.start()
    test_process.join(timeout=args.timeout)

    if test_process.is_alive():
        log.error(f"!!!!!!!!!! Test execution timed out after {args.timeout} seconds !!!!!!!!!!")
        test_process.terminate()
        test_process.join(5)
        if test_process.is_alive():
            test_process.kill()
        log.warning("Test subprocess was forcibly terminated.")
        sys.exit(1)
    else:
        if test_process.exitcode == 0:
            log.info(f"✅ Tests completed successfully within the time limit.")
        else:
            log.error(f"❌ Tests failed with exit code: {test_process.exitcode}.")
        sys.exit(test_process.exitcode)

if __name__ == "__main__":
    main()
