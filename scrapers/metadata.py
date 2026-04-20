"""语料元数据管理：读写 corpus/metadata.json。"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Iterable

from .config import METADATA_PATH


@dataclass
class BookRecord:
    slug: str
    title: str
    author: str
    source: str            # "biquge" / "piaotian" / ...
    source_url: str
    genre: str = ""
    tags: list[str] = field(default_factory=list)
    total_chapters: int = 0
    scraped_chapters: int = 0
    total_words: int = 0
    is_complete: bool = False
    added_at: str = ""
    updated_at: str = ""
    notes: str = ""


class MetadataStore:
    def __init__(self, path: Path = METADATA_PATH) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self._write({"books": {}})

    def _read(self) -> dict:
        with self.path.open("r", encoding="utf-8") as f:
            return json.load(f)

    def _write(self, data: dict) -> None:
        with self.path.open("w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def list_books(self) -> list[BookRecord]:
        data = self._read()
        return [BookRecord(**item) for item in data.get("books", {}).values()]

    def get(self, slug: str) -> BookRecord | None:
        data = self._read()
        raw = data.get("books", {}).get(slug)
        return BookRecord(**raw) if raw else None

    def upsert(self, record: BookRecord) -> BookRecord:
        now = datetime.now().isoformat(timespec="seconds")
        if not record.added_at:
            record.added_at = now
        record.updated_at = now

        data = self._read()
        data.setdefault("books", {})[record.slug] = asdict(record)
        self._write(data)
        return record

    def remove(self, slug: str) -> bool:
        data = self._read()
        books = data.get("books", {})
        if slug not in books:
            return False
        del books[slug]
        self._write(data)
        return True

    def update_progress(
        self,
        slug: str,
        *,
        total_chapters: int | None = None,
        scraped_chapters: int | None = None,
        total_words: int | None = None,
        is_complete: bool | None = None,
    ) -> BookRecord | None:
        record = self.get(slug)
        if record is None:
            return None
        if total_chapters is not None:
            record.total_chapters = total_chapters
        if scraped_chapters is not None:
            record.scraped_chapters = scraped_chapters
        if total_words is not None:
            record.total_words = total_words
        if is_complete is not None:
            record.is_complete = is_complete
        return self.upsert(record)


def slugify(title: str) -> str:
    """把中文书名转成文件系统安全的 slug（保留中文，剥离非法字符）。"""
    bad = set('/\\:*?"<>|\r\n\t')
    cleaned = "".join("_" if c in bad else c for c in title).strip()
    return cleaned or "untitled"


def ensure_iterable(value: str | Iterable[str] | None) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [v.strip() for v in value.split(",") if v.strip()]
    return list(value)
