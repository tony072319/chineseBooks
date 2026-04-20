"""全局常量与路径。"""
from __future__ import annotations

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CORPUS_DIR = PROJECT_ROOT / "corpus"
RAW_DIR = CORPUS_DIR / "raw"
METADATA_PATH = CORPUS_DIR / "metadata.json"

DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)

DEFAULT_DELAY_SECONDS = 2.0
DEFAULT_TIMEOUT_SECONDS = 20
DEFAULT_MAX_RETRIES = 3
DEFAULT_BACKOFF_BASE = 2.0
