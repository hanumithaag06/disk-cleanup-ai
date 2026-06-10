# src/summary.py

def print_scan_summary(results):

    keep_count = sum(
        1
        for item in results
        if item["decision"] == "KEEP"
    )

    delete_count = sum(
        1
        for item in results
        if item["decision"] == "SAFE_DELETE"
    )

    recoverable_space = sum(
        item["size_mb"]
        for item in results
        if item["decision"] == "SAFE_DELETE"
    )

    print("\n========== SCAN SUMMARY ==========")

    print(
        f"Files Scanned: {len(results)}"
    )

    print(
        f"KEEP: {keep_count}"
    )

    print(
        f"SAFE_DELETE: {delete_count}"
    )

    print(
        f"Recoverable Space: "
        f"{recoverable_space:.2f} MB"
    )

    print("==================================\n")