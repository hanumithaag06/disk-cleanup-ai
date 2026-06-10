# test_move.py

from src.scanner import scan_folder
from src.classifier import classify_files
from src.cleanup import move_safe_files


files = scan_folder()

classified = classify_files(files)

moved = move_safe_files(classified)

print(f"\nMoved {len(moved)} files\n")

for file in moved:
    print(
        f"{file['name']} -> {file['deleted_path']}"
    )