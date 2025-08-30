import sys
import subprocess
import time
import os
import re
import signal
from pathlib import Path

# --- Configuration ---
SERVER_READY_TIMEOUT = 120  # As requested by the user
REQUIREMENTS_FILES = [
    "requirements/server.txt",
    "requirements/transcriber.txt"
]
# From colabPro.py.v18.bak, the core command
LAUNCH_COMMAND = ["src/core/orchestrator.py"]
# From colabPro.py.v18.bak, the readiness signal
UVICORN_READY_PATTERN = re.compile(r"Uvicorn running on")

def install_dependencies():
    """Installs all necessary Python dependencies."""
    print("--- Installing Python dependencies ---")

    # Create a temporary merged requirements file
    # This is better than running pip multiple times
    merged_reqs_path = Path("requirements_merged_for_startup.txt")
    with open(merged_reqs_path, "w") as outfile:
        for req_file in REQUIREMENTS_FILES:
            if Path(req_file).is_file():
                with open(req_file, "r") as infile:
                    outfile.write(infile.read())
                    outfile.write("\n")
            else:
                print(f"Warning: Requirement file not found: {req_file}")

    # Use uv if available, otherwise pip
    pip_command = [sys.executable, "-m", "pip", "install", "-q", "-r", str(merged_reqs_path)]
    try:
        # Check for uv
        subprocess.check_call([sys.executable, "-m", "uv", "--version"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        print("Using 'uv' for faster installation.")
        pip_command = [sys.executable, "-m", "uv", "pip", "install", "-q", "-r", str(merged_reqs_path)]
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("'uv' not found, falling back to 'pip'.")

    try:
        subprocess.check_call(pip_command)
        print("✅ Dependencies installed successfully.")
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to install dependencies. Error: {e}")
        sys.exit(1)
    finally:
        # Clean up the merged file
        if merged_reqs_path.exists():
            merged_reqs_path.unlink()


def main():
    """
    Main function to install dependencies, launch the core server,
    and wait for it to be ready with a timeout.
    """
    print("--- Starting Core Services Launcher ---")

    # Step 1: Install dependencies
    install_dependencies()

    # Step 2: Launch the orchestrator process
    print(f"🚀 Launching core orchestrator: {' '.join([sys.executable] + LAUNCH_COMMAND)}")

    # Set PYTHONPATH to include the 'src' directory, similar to colabPro.py
    process_env = os.environ.copy()
    src_path_str = str(Path("src").resolve())
    process_env['PYTHONPATH'] = f"{src_path_str}{os.pathsep}{process_env.get('PYTHONPATH', '')}".strip(os.pathsep)

    # Use preexec_fn=os.setsid to create a new process group.
    # This allows us to kill the entire process tree later.
    server_process = subprocess.Popen(
        [sys.executable] + LAUNCH_COMMAND,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding='utf-8',
        preexec_fn=os.setsid,
        env=process_env
    )

    print(f"Orchestrator process started with PID: {server_process.pid}")
    print(f"Waiting for server to become ready (timeout: {SERVER_READY_TIMEOUT} seconds)...")

    # Step 3: Wait for the server to be ready with a timeout
    start_time = time.time()
    server_ready = False

    try:
        # Using a non-blocking read in a loop
        for line in iter(server_process.stdout.readline, ''):
            print(f"[Orchestrator] {line.strip()}")
            if UVICORN_READY_PATTERN.search(line):
                server_ready = True
                print("\n✅ Server is ready! Uvicorn running.")
                break

            if time.time() - start_time > SERVER_READY_TIMEOUT:
                # We use a custom exception to signal a timeout
                raise TimeoutError("Server failed to start within the timeout period.")

        # After the loop, if server is not ready, the process must have exited.
        if not server_ready:
            print("❌ Orchestrator process exited prematurely before signaling readiness.")

    except TimeoutError as e:
        print(f"❌ {e}")
    except Exception as e:
        print(f"❌ An unexpected error occurred while monitoring the server: {e}")
    finally:
        # If the server is ready, we let it run.
        if server_ready:
            print("\nServer process is now running in the background.")
            print("To stop it, you may need to manually kill the process group.")
            # The script will exit, but the server process will continue running.
        else:
            # If the process is still running (e.g., on timeout), kill it.
            if server_process.poll() is None:
                print("Killing server process due to timeout or error...")
                try:
                    # Kill the entire process group
                    os.killpg(os.getpgid(server_process.pid), signal.SIGTERM)
                    server_process.wait(timeout=5)
                    print("Server process killed.")
                except ProcessLookupError:
                    print("Process already terminated.") # It might have died in the meantime
                except Exception as kill_e:
                    print(f"Error during process cleanup: {kill_e}")

            print("\n--- Launcher script finished with errors. ---")
            sys.exit(1)

        print("\n--- Launcher script finished successfully. ---")


if __name__ == "__main__":
    main()
