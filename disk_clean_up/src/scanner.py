# src/scanner.py
import hashlib
from collections import defaultdict
from pathlib import Path
from datetime import datetime
from typing import Optional


def get_category(filename, extension):
    name = filename.lower()
    if any(k in name for k in ["cache", "temp", "tmp", "log", "dump"]):
        return "temporary"
    if any(k in name for k in ["backup", "archive", "snapshot"]):
        return "archive"
    if any(k in name for k in ["project", "report", "notes"]):
        return "user_document"
    if any(k in name for k in ["export", "download"]):
        return "generated_file"
    if extension in [".pdf", ".txt"]:
        return "document"
    if extension in [".zip", ".iso"]:
        return "archive"
    if extension in [".tmp", ".log"]:
        return "temporary"
    return "unknown"


def hash_file(path: str, chunk_size: int = 65536) -> Optional[str]:
    """SHA-256 hash of a file's contents. Returns None on error."""
    try:
        h = hashlib.sha256()
        with open(path, "rb") as f:
            while chunk := f.read(chunk_size):
                h.update(chunk)
        return h.hexdigest()
    except Exception as e:
        print(f"Hash error {path}: {e}")
        return None


def find_duplicates(files_data: list[dict]) -> list[dict]:
    """
    Groups files by size first (fast pre-filter), then by SHA-256 hash.
    Within each duplicate group, keeps the newest file (lowest age),
    marks the rest as duplicates.
    Returns the full files_data list with duplicate metadata added.
    """
    # Pre-filter: group by size — files with unique sizes can't be duplicates
    size_groups = defaultdict(list)
    for f in files_data:
        size_groups[f["size_mb"]].append(f)

    hash_groups = defaultdict(list)
    for size, group in size_groups.items():
        if len(group) < 2:
            continue  # unique size → skip hashing
        for f in group:
            digest = hash_file(f["path"])
            if digest:
                f["_hash"] = digest
                hash_groups[digest].append(f)

    duplicate_count = 0
    for digest, group in hash_groups.items():
        if len(group) < 2:
            continue
        # Keep the most recently accessed file; mark the rest as duplicates
        group.sort(key=lambda f: f["days_since_last_access"])
        original = group[0]
        for dupe in group[1:]:
            dupe["is_duplicate"] = True
            dupe["duplicate_of"] = original["path"]
            dupe["decision"] = "SAFE_DELETE"
            dupe["confidence"] = 0.99
            dupe["reason"] = f"Exact duplicate of {Path(original['path']).name}"
            duplicate_count += 1
            print(
                f"[DUPLICATE] {dupe['name']} "
                f"→ original: {original['name']}"
            )

    if duplicate_count:
        print(f"\nFound {duplicate_count} duplicate file(s)")

    # Clean up temp hash key
    for f in files_data:
        f.pop("_hash", None)

    return files_data


def scan_folder(folder_path="monitored_folder"):
    """Recursively scan a folder and collect file metadata."""
    files_data = []
    folder = Path(folder_path)

    if not folder.exists():
        print(f"Folder not found: {folder}")
        return []

    for file in folder.rglob("*"):
        if not file.is_file():
            continue
        try:
            stat = file.stat()
            size_mb = round(stat.st_size / (1024 * 1024), 2)
            created_date = datetime.fromtimestamp(stat.st_ctime).strftime("%Y-%m-%d %H:%M:%S")
            last_accessed = datetime.fromtimestamp(stat.st_atime)
            days_since_last_access = (datetime.now() - last_accessed).days
            extension = file.suffix.lower()
            category = get_category(file.name, extension)

            files_data.append({
                "name": file.name,
                "path": str(file.resolve()),
                "size_mb": size_mb,
                "created_date": created_date,
                "extension": extension,
                "category": category,
                "days_since_last_access": days_since_last_access,
                "is_duplicate": False,
                "duplicate_of": None,
            })
        except Exception as e:
            print(f"Error scanning {file}: {e}")

    # Duplicate detection runs before LLM classification
    files_data = find_duplicates(files_data)
    return files_data


if __name__ == "__main__":
    files = scan_folder()
    print(f"\nScanned {len(files)} files\n")
    for file in files:
        print(file)