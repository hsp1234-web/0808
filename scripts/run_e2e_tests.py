import subprocess
import sys
import logging
import multiprocessing
import time
from pathlib import Path

# --- Logging Setup ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
log = logging.getLogger('E2E_Test_Launcher')

def run_playwright_tests():
    """
    Target function to run Playwright tests in a subprocess.
    """
    log.info("Subprocess started: Running Playwright tests...")
    # Focusing on the main validation test
    command = ["npx", "playwright", "test", "src/tests/e2e_main_validation.spec.js"]
    try:
        subprocess.run(command, check=True, text=True, encoding='utf-8')
        sys.exit(0)
    except subprocess.CalledProcessError as e:
        log.error(f"Playwright tests failed with exit code {e.returncode}.")
        sys.exit(e.returncode)
    except FileNotFoundError:
        log.error("`npx` command not found. Please ensure Node.js and npm/npx are installed and in your PATH.")
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
        # 1. Install standalone packages and requirements files
        packages_to_install = ["psutil", "requests", "uv"]
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

        # 2. Install the project itself in editable mode
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
    timeout_seconds = 180 # Increased timeout to be safe
    log.info(f"--- Starting E2E Test Launcher (Total timeout: {timeout_seconds} seconds) ---")

    try:
        install_node_deps()
        install_python_deps()
    except Exception:
        log.critical("Dependency installation failed. Cannot proceed with tests.", exc_info=True)
        sys.exit(1)

    test_process = multiprocessing.Process(target=run_playwright_tests)
    test_process.start()
    test_process.join(timeout=timeout_seconds)

    if test_process.is_alive():
        log.error(f"!!!!!!!!!! Test execution timed out after {timeout_seconds} seconds !!!!!!!!!!")
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
