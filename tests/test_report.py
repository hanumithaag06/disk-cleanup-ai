from src.report_generator import (
    generate_classification_report
)

from src.scanner import scan_folder
from src.classifier import classify_files


files = scan_folder(
    "monitored_folder"
)

results = classify_files(
    files,
    threshold_days=180
)

generate_classification_report(
    results
)

print(
    "classification_report.pdf generated"
)