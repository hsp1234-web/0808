import os
from pathlib import Path

def revert_file_content(file_path):
    """
    Reads a file, replaces "src_v2/" with "src/", and writes it back.
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except UnicodeDecodeError:
        print(f"Skipping non-text file: {file_path}")
        return

    original_content = content
    modified_content = content.replace('"src_v2/', '"src/')
    modified_content = modified_content.replace("'src_v2/", "'src/")

    # Also handle the specific case in api_server for the STATIC_DIR
    modified_content = modified_content.replace('ROOT_DIR / "src_v2" / "static"', 'ROOT_DIR / "src" / "static"')

    if modified_content != original_content:
        print(f"Reverting paths in: {file_path}")
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(modified_content)

def main():
    src_dir = Path("src")
    if not src_dir.is_dir():
        print(f"Error: Directory '{src_dir}' not found.")
        return

    files_to_scan = []
    for ext in ["**/*.py", "**/*.js", "**/*.cjs"]:
        files_to_scan.extend(src_dir.glob(ext))

    print(f"\nScanning {len(files_to_scan)} files to revert 'src_v2' paths...")
    for file_path in files_to_scan:
        revert_file_content(file_path)

    print("\nPath reversion process complete.")

if __name__ == "__main__":
    main()
