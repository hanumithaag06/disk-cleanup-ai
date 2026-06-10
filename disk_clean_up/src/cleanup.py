from pathlib import Path
import shutil
from datetime import datetime

from logger import log_deletion


DELETED_FOLDER = Path(
    "deleted_files"
)

MONITORED_FOLDER = Path(
    "monitored_folder"
)


def ensure_deleted_folder():

    DELETED_FOLDER.mkdir(
        parents=True,
        exist_ok=True
    )


def move_to_deleted(file_path):

    ensure_deleted_folder()

    source = Path(file_path)

    if not source.exists():

        return False

    destination = (
        DELETED_FOLDER / source.name
    )

    shutil.move(
        str(source),
        str(destination)
    )

    return str(destination)


def move_safe_files(classified_files):

    moved = []

    for file in classified_files:

        if (
            file["decision"]
            != "SAFE_DELETE"
        ):
            continue

        result = move_to_deleted(
            file["path"]
        )

        if result:

            moved.append(
                {
                    **file,
                    "deleted_path": result,
                    "deleted_at": datetime.now().strftime(
                        "%Y-%m-%d %H:%M:%S"
                    )
                }
            )

    if moved:

        log_deletion(
            moved
        )

    return moved


def restore_all_files():

    restored = []

    ensure_deleted_folder()

    for file in DELETED_FOLDER.iterdir():

        if not file.is_file():
            continue

        destination = (
            MONITORED_FOLDER / file.name
        )

        shutil.move(
            str(file),
            str(destination)
        )

        restored.append(
            file.name
        )

    return restored


def permanently_delete_all():

    deleted = []

    if not DELETED_FOLDER.exists():

        return deleted

    for file in DELETED_FOLDER.iterdir():

        if not file.is_file():

            continue

        file.unlink()

        deleted.append(
            file.name
        )

    return deleted