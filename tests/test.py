from src.scanner import scan_folder
from src.classifier import classify_files

files = scan_folder()

result = classify_files(files)

for item in result:
    print(item)