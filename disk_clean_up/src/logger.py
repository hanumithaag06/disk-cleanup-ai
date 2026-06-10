import json
from pathlib import Path
from datetime import datetime


LOG_FILE = Path("logs/deletion_log.json")


def log_deletion(files):

    LOG_FILE.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    entry = {
        "timestamp":
            datetime.now().strftime(
                "%Y-%m-%d %H:%M:%S"
            ),
        "files": files
    }

    if LOG_FILE.exists():

        with open(
            LOG_FILE,
            "r",
            encoding="utf-8"
        ) as f:

            try:
                data = json.load(f)

            except:
                data = []

    else:
        data = []

    data.append(entry)

    with open(
        LOG_FILE,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            data,
            f,
            indent=4
        )