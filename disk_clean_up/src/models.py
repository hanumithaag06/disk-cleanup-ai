# models.py
from dataclasses import dataclass, field
from typing import Optional

@dataclass
class FileEntry:
    path: str
    size_kb: float
    age_days: int
    classification: Optional[str] = None
    explanation: Optional[str] = None
    confidence: Optional[float] = None
    deleted: bool = False
    is_duplicate: bool = False
    duplicate_of: Optional[str] = None   # path of the file this is a copy of