# test_cache.py

from src.cache_manager import *

print(load_cache())

set_cached_threshold(180)

print(get_cached_threshold())

update_cache(
    "test.txt",
    {
        "decision": "KEEP",
        "days_since_last_access": 100
    }
)

print(
    get_cached_result(
        "test.txt"
    )
)