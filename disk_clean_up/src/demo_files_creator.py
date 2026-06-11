from pathlib import Path
import os
import random
import time


def generate_demo_files(
    folder="monitored_folder",
    files_per_run=15
):
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)

    file_types = {
        "backup": [".zip", ".iso"],
        "cache": [".tmp", ".log"],
        "temp": [".tmp"],
        "log": [".log"],
        "report": [".pdf", ".txt"],
        "archive": [".zip", ".iso"],
        "download": [".zip", ".iso"],
        "project": [".txt", ".pdf"],
        "notes": [".txt"],
        "export": [".zip", ".pdf"],
        "snapshot": [".zip", ".pdf"],
        "dump": [".zip", ".log"],
        "video": [".iso"],
        "image": [".zip"],
        "audio": [".txt"]
    }

    now = time.time()

    for _ in range(files_per_run):

        category = random.choice(list(file_types.keys()))
        ext = random.choice(file_types[category])

        file_number = random.randint(1, 999)

        filename = f"{category}_{file_number:03d}{ext}"

        filepath = folder / filename

        # avoid overwrite
        while filepath.exists():
            file_number = random.randint(1, 999)
            filename = f"{category}_{file_number:03d}{ext}"
            filepath = folder / filename

        size_kb = random.randint(100, 10000)

        with open(filepath, "wb") as f:
            f.write(os.urandom(size_kb * 1024))

        age_days = random.randint(1, 1000)

        timestamp = now - (age_days * 86400)

        os.utime(filepath, (timestamp, timestamp))

    print(f"Added {files_per_run} files")

    # ── Inject one guaranteed duplicate ──────────────────
    existing_files = list(folder.iterdir())
     
    if existing_files:
        original = random.choice(existing_files)

        # Build a duplicate filename that won't collide
        stem = original.stem + "_copy"
        dupe_path = folder / (stem + original.suffix)
        counter = 1
        while dupe_path.exists():
            dupe_path = folder / (f"{stem}_{counter}{original.suffix}")
            counter += 1

        # Copy exact bytes → identical SHA-256
        dupe_path.write_bytes(original.read_bytes())

        # Give it a different age so the scanner keeps the newer one
        dupe_age_days = random.randint(1, 1000)
        dupe_timestamp = now - (dupe_age_days * 86400)
        os.utime(dupe_path, (dupe_timestamp, dupe_timestamp))

        print(f"Injected duplicate: {dupe_path.name} → original: {original.name}")


if __name__ == "__main__":
    generate_demo_files()