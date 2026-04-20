"""BaseScraper 行为测试（不走真实网络）。"""
from __future__ import annotations

import types
from pathlib import Path

from scrapers.base import BaseScraper, BookInfo, ChapterRef, _count_words
from scrapers.metadata import MetadataStore


class _FakeScraper(BaseScraper):
    site_name = "fake"

    def __init__(self, pages: dict[str, str], store: MetadataStore) -> None:
        super().__init__(store=store, delay_seconds=0)
        self._pages = pages

    def fetch(self, url: str, *, encoding: str | None = None) -> str:  # type: ignore[override]
        return self._pages[url]

    def parse_book_info(self, html: str, source_url: str) -> BookInfo:
        return BookInfo(title="测试书", author="某人", source_url=source_url)

    def parse_chapter_list(self, html: str, source_url: str) -> list[ChapterRef]:
        return [
            ChapterRef(index=1, title="第一章 开场", url="http://x/c1"),
            ChapterRef(index=2, title="第二章 金手指", url="http://x/c2"),
            ChapterRef(index=3, title="第三章 打脸", url="http://x/c3"),
        ]

    def parse_chapter_content(self, html: str, url: str) -> str:
        return html


def test_scrape_book_writes_files_and_metadata(tmp_path: Path, monkeypatch) -> None:
    # 把 corpus 路径指向 tmp
    from scrapers import base as base_mod
    monkeypatch.setattr(base_mod, "RAW_DIR", tmp_path / "raw")

    store = MetadataStore(tmp_path / "meta.json")
    pages = {
        "http://x/book": "<html/>",
        "http://x/c1": "这是第一章正文。主角出场，被退婚。",
        "http://x/c2": "金手指激活，药老现身。",
        "http://x/c3": "第一次打脸成功。",
    }
    scraper = _FakeScraper(pages, store)
    record = scraper.scrape_book("http://x/book", max_chapters=2)

    assert record.title == "测试书"
    assert record.total_chapters == 3
    assert record.scraped_chapters == 2
    assert record.total_words > 0

    book_dir = tmp_path / "raw" / "测试书"
    files = sorted(p.name for p in book_dir.iterdir())
    assert files == ["0001_第一章 开场.txt", "0002_第二章 金手指.txt"]
    assert "主角出场" in (book_dir / files[0]).read_text(encoding="utf-8")


def test_scrape_book_resumable(tmp_path: Path, monkeypatch) -> None:
    from scrapers import base as base_mod
    monkeypatch.setattr(base_mod, "RAW_DIR", tmp_path / "raw")

    store = MetadataStore(tmp_path / "meta.json")
    pages = {
        "http://x/book": "<html/>",
        "http://x/c1": "章节 1",
        "http://x/c2": "章节 2",
        "http://x/c3": "章节 3",
    }
    s = _FakeScraper(pages, store)
    s.scrape_book("http://x/book", max_chapters=1)
    record = s.scrape_book("http://x/book", max_chapters=3)
    assert record.scraped_chapters == 3
    files = sorted(p.name for p in (tmp_path / "raw" / "测试书").iterdir())
    assert len(files) == 3


def test_count_words_chinese_and_english() -> None:
    assert _count_words("你好world") == 2 + 1   # 2 中文字 + 1 英文词
    assert _count_words("") == 0
    assert _count_words("萧炎斗之气三段") == 7
