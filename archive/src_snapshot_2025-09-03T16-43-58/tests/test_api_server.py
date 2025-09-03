import pytest
import requests
import uvicorn
import threading
import time
import shutil
from pathlib import Path

# Import the FastAPI app instance and configuration from the main server file
from api.api_server import app, UPLOADS_DIR, ROOT_DIR

# --- Test Configuration ---
TEST_HOST = "127.0.0.1"
TEST_PORT = 8010 # Choose a non-standard port to avoid conflicts
BASE_URL = f"http://{TEST_HOST}:{TEST_PORT}"

# --- Fixtures ---

@pytest.fixture(scope="session")
def server():
    """Fixture to run the FastAPI server in a background thread."""
    config = uvicorn.Config(app, host=TEST_HOST, port=TEST_PORT, log_level="info")
    server = uvicorn.Server(config)

    # Run the server in a separate thread
    thread = threading.Thread(target=server.run)
    thread.daemon = True
    thread.start()

    # Give the server a moment to start up
    time.sleep(2)

    yield

    # The server will be shut down when the test session ends because of the daemon thread.

@pytest.fixture
def temporary_media_file():
    """
    Fixture to prepare a test audio file in the uploads directory
    and clean it up after the test.
    """
    # --- Setup ---
    source_file = ROOT_DIR / "src" / "tests" / "fixtures" / "test_audio.mp3"
    target_dir = UPLOADS_DIR
    target_dir.mkdir(exist_ok=True) # Ensure uploads directory exists
    target_file = target_dir / "test_audio.mp3"

    if not source_file.exists():
        pytest.fail(f"Test fixture not found: {source_file}. Please run setup for Step 1 first.")

    shutil.copy(source_file, target_file)

    yield target_file # Provide the path to the test function

    # --- Teardown ---
    if target_file.exists():
        target_file.unlink()

# --- Test Cases ---

def test_health_check(server):
    """Test the basic health check endpoint to ensure the server is running."""
    response = requests.get(f"{BASE_URL}/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "message": "API Server is running."}

def test_serve_media_file_success(server, temporary_media_file):
    """
    Tests if the server can correctly serve a media file from the /media/ endpoint.
    This simulates the MP3 preview scenario.
    """
    # --- 1. Prepare ---
    # The `temporary_media_file` fixture has already copied the file.
    # The URL should correspond to the file's name under the /media/ mount.
    file_url = f"{BASE_URL}/media/test_audio.mp3"

    # --- 2. Execute ---
    response = requests.get(file_url)

    # --- 3. Assert ---
    # Assert successful response
    assert response.status_code == 200, f"Expected 200 OK, but got {response.status_code}. Response: {response.text}"

    # Assert correct content type for an MP3 file
    # FastAPI's StaticFiles should correctly identify the mime type as audio/mpeg.
    assert response.headers.get("Content-Type") == "audio/mpeg"

    # Assert that the content is what we expect (the dummy file content)
    source_content = (ROOT_DIR / "src" / "tests" / "fixtures" / "test_audio.mp3").read_bytes()
    assert response.content == source_content
