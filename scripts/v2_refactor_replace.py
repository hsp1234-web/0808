import os
import re
from pathlib import Path

def get_renamed_basenames(root_dir):
    """
    Gets a list of file basenames (without extension) that have been renamed.
    e.g., if we have 'api_server_v2.py', this will return 'api_server'.
    """
    renamed_basenames = set()
    for root, _, files in os.walk(root_dir):
        for file in files:
            if '_v2.' in file:
                # Extracts 'api_server' from 'api_server_v2.py'
                basename = file.split('_v2.')[0]
                renamed_basenames.add(basename)
    return list(renamed_basenames)

def update_file_content(file_path, renames):
    """
    Reads a file, performs replacements using regex, and writes it back if changes were made.
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except UnicodeDecodeError:
        print(f"Skipping non-text file: {file_path}")
        return

    original_content = content
    modified_content = content

    # 1. Update Python import statements idempotently
    # e.g., from db.client -> from db.client_v2
    # but NOT from db.client_v2 -> from db.client_v2_v2
    for name in renames:
        # This regex finds 'from pkg.module' or 'import pkg.module' and adds _v2
        # only if it's not already there.
        # \b is a word boundary to avoid matching parts of longer names.
        pattern = re.compile(fr'\b(from|import)\s+([\w\.]*?{re.escape(name)})(?!_v2)\b')
        modified_content = pattern.sub(r'\1 \2_v2', modified_content)

    # 2. Update hardcoded file path strings idempotently
    for name in renames:
        for ext in [".py", ".json", ".js", ".cjs", ".mp3"]:
            # This regex finds a filename string like "name.py" and adds _v2
            # only if it's not already there.
            pattern = re.compile(fr'([\'"])([\w\/\-]*?{re.escape(name)})(?!_v2)({re.escape(ext)})([\'"])')
            modified_content = pattern.sub(fr'\1\2_v2\3\4', modified_content)


    # 3. Update the SRC_DIR path for v2 in specific files that need it
    if "api_server_v2.py" in str(file_path) or "orchestrator_v2.py" in str(file_path):
        # This replacement is simple and can be done directly.
        modified_content = modified_content.replace('("src",', '("src_v2",')
        modified_content = modified_content.replace('("src")', '("src_v2")')
        modified_content = modified_content.replace('/ "src" /', '/ "src_v2" /')


    if modified_content != original_content:
        print(f"Updating content in: {file_path}")
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(modified_content)
    else:
        print(f"No changes needed for: {file_path}")


def main():
    src_v2_dir = Path("src_v2")
    if not src_v2_dir.is_dir():
        print(f"Error: Directory '{src_v2_dir}' not found.")
        return

    # Get the list of original names, e.g., 'api_server', 'client'
    renamed_basenames = get_renamed_basenames(src_v2_dir)
    print(f"Found {len(renamed_basenames)} basenames of renamed files: {sorted(renamed_basenames)}")

    files_to_scan = []
    # Scan all text-based files where references might occur.
    for ext in ["**/*.py", "**/*.js", "**/*.cjs", "**/*.html"]:
        files_to_scan.extend(src_v2_dir.glob(ext))

    print(f"\nScanning {len(files_to_scan)} files for content updates...")
    for file_path in files_to_scan:
        update_file_content(file_path, renamed_basenames)

    print("\nContent update process complete.")

if __name__ == "__main__":
    main()
