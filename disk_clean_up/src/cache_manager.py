# src/cache_manager.py

import json
from pathlib import Path

CACHE_FILE = Path("data/classification_cache.json")


def ensure_cache_exists():

    CACHE_FILE.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    if not CACHE_FILE.exists():

        CACHE_FILE.write_text(
            json.dumps(
                {
                    "_metadata": {
                        "threshold": None
                    }
                },
                indent=4
            )
        )


def load_cache():

    ensure_cache_exists()

    with open(
        CACHE_FILE,
        "r",
        encoding="utf-8"
    ) as f:

        return json.load(f)


def save_cache(cache):

    ensure_cache_exists()

    with open(
        CACHE_FILE,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            cache,
            f,
            indent=4
        )


def get_cached_result(filename):

    cache = load_cache()

    return cache.get(filename)


def update_cache(
    filename,
    result
):

    cache = load_cache()

    cache[filename] = result

    save_cache(cache)


def get_cached_threshold():

    cache = load_cache()

    return cache.get(
        "_metadata",
        {}
    ).get(
        "threshold"
    )


def set_cached_threshold(
    threshold
):

    cache = load_cache()

    if "_metadata" not in cache:

        cache["_metadata"] = {}

    cache["_metadata"][
        "threshold"
    ] = threshold

    save_cache(cache)


def threshold_changed(
    current_threshold
):

    cached = get_cached_threshold()

    return cached != current_threshold