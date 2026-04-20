"""语料读取：从 corpus/metadata.json + corpus/raw/ 构造 Book / Chapter 对象。"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from functools import cached_property
from pathlib import Path
from typing import Iterator

from scrapers.config import METADATA_PATH, PROJECT_ROOT, RAW_DIR

REPORTS_DIR = PROJECT_ROOT / "reports"
CHAPTER_FILE_RE = re.compile(r"^(\d+)_(.+)\.txt$")
_CN_CHAR = re.compile(r"[\u4e00-\u9fff]")


@dataclass
class Chapter:
    book_slug: str
    index: int
    title: str
    body: str
    path: Path

    @cached_property
    def word_count(self) -> int:
        """中文字数：只数汉字，忽略标点和空白。"""
        return len(_CN_CHAR.findall(self.body))

    @property
    def first_n_chars(self, n: int = 500) -> str:
        cleaned = re.sub(r"\s+", "", self.body)
        return cleaned[:n]

    @property
    def last_n_chars(self, n: int = 60) -> str:
        cleaned = re.sub(r"\s+", "", self.body)
        return cleaned[-n:]


@dataclass
class Book:
    slug: str
    title: str
    author: str
    genre: str = ""
    tags: list[str] = field(default_factory=list)
    total_chapters: int = 0
    total_words: int = 0

    @property
    def directory(self) -> Path:
        return RAW_DIR / self.slug

    def chapter_files(self) -> list[Path]:
        return sorted(self.directory.glob("*.txt"))

    def iter_chapters(self, limit: int | None = None) -> Iterator[Chapter]:
        count = 0
        for path in self.chapter_files():
            m = CHAPTER_FILE_RE.match(path.name)
            if not m:
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
            lines = text.splitlines()
            if lines and lines[0].startswith("# "):
                title = lines[0][2:].strip()
                body = "\n".join(lines[1:]).strip()
            else:
                title = m.group(2)
                body = text.strip()
            yield Chapter(
                book_slug=self.slug,
                index=int(m.group(1)),
                title=title,
                body=body,
                path=path,
            )
            count += 1
            if limit is not None and count >= limit:
                return

    def chapter(self, index: int) -> Chapter | None:
        pattern = f"{index:04d}_*.txt"
        for path in self.directory.glob(pattern):
            text = path.read_text(encoding="utf-8", errors="replace")
            lines = text.splitlines()
            title = lines[0][2:].strip() if lines and lines[0].startswith("# ") else ""
            body = "\n".join(lines[1:]).strip() if title else text
            return Chapter(
                book_slug=self.slug,
                index=index,
                title=title,
                body=body,
                path=path,
            )
        return None


def load_all_books() -> list[Book]:
    if not METADATA_PATH.exists():
        return []
    with METADATA_PATH.open("r", encoding="utf-8") as f:
        data = json.load(f)
    books: list[Book] = []
    for slug, meta in data.get("books", {}).items():
        books.append(
            Book(
                slug=slug,
                title=meta.get("title", slug),
                author=meta.get("author", ""),
                genre=meta.get("genre", ""),
                tags=list(meta.get("tags", [])),
                total_chapters=int(meta.get("total_chapters", 0)),
                total_words=int(meta.get("total_words", 0)),
            )
        )
    return books


def load_book(slug: str) -> Book | None:
    for b in load_all_books():
        if b.slug == slug:
            return b
    return None
