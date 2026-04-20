"""BaseScraper：所有站点适配器的抽象基类。

职责：
- HTTP 抓取（礼貌限速、退避重试、编码识别）
- 正文 / 目录 / 书籍信息的解析钩子（子类实现）
- 章节文件保存到 corpus/raw/{slug}/{NNNN}_{title}.txt
- 与 MetadataStore 协作登记书籍并更新进度
"""
from __future__ import annotations

import logging
import re
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import chardet
import requests
from bs4 import BeautifulSoup

from .config import (
    DEFAULT_BACKOFF_BASE,
    DEFAULT_DELAY_SECONDS,
    DEFAULT_MAX_RETRIES,
    DEFAULT_TIMEOUT_SECONDS,
    DEFAULT_USER_AGENT,
    RAW_DIR,
)
from .metadata import BookRecord, MetadataStore, slugify

logger = logging.getLogger(__name__)


@dataclass
class BookInfo:
    title: str
    author: str
    source_url: str
    genre: str = ""
    tags: list[str] | None = None


@dataclass
class ChapterRef:
    index: int          # 从 1 开始
    title: str
    url: str


class ScraperError(RuntimeError):
    pass


class BaseScraper(ABC):
    """子类只需实现三个 parse_* 方法和 site_name。"""

    site_name: str = "base"

    def __init__(
        self,
        *,
        user_agent: str = DEFAULT_USER_AGENT,
        delay_seconds: float = DEFAULT_DELAY_SECONDS,
        timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
        max_retries: int = DEFAULT_MAX_RETRIES,
        backoff_base: float = DEFAULT_BACKOFF_BASE,
        store: MetadataStore | None = None,
        session: requests.Session | None = None,
    ) -> None:
        self.delay_seconds = delay_seconds
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries
        self.backoff_base = backoff_base
        self.store = store or MetadataStore()
        self.session = session or requests.Session()
        self.session.headers.update({"User-Agent": user_agent})
        self._last_fetch_at = 0.0

    # ------------------------------ HTTP ------------------------------

    def fetch(self, url: str, *, encoding: str | None = None) -> str:
        """下载一个 URL，返回解码后的文本。限速 + 重试 + 编码识别。"""
        self._sleep_if_needed()
        last_exc: Exception | None = None
        for attempt in range(1, self.max_retries + 1):
            try:
                response = self.session.get(url, timeout=self.timeout_seconds)
                response.raise_for_status()
                self._last_fetch_at = time.monotonic()
                return self._decode(response, encoding)
            except requests.RequestException as exc:
                last_exc = exc
                wait = self.backoff_base ** attempt
                logger.warning(
                    "fetch failed (attempt %s/%s) %s: %s; sleeping %.1fs",
                    attempt, self.max_retries, url, exc, wait,
                )
                time.sleep(wait)
        raise ScraperError(f"fetch failed after {self.max_retries} retries: {url}") from last_exc

    def _sleep_if_needed(self) -> None:
        elapsed = time.monotonic() - self._last_fetch_at
        if elapsed < self.delay_seconds:
            time.sleep(self.delay_seconds - elapsed)

    @staticmethod
    def _decode(response: requests.Response, preferred: str | None) -> str:
        raw = response.content
        if preferred:
            try:
                return raw.decode(preferred)
            except UnicodeDecodeError:
                pass
        # HTTP header 的 charset 常不准，用 chardet 兜底
        guess = chardet.detect(raw).get("encoding") or response.encoding or "utf-8"
        try:
            return raw.decode(guess, errors="replace")
        except LookupError:
            return raw.decode("utf-8", errors="replace")

    def soup(self, html: str) -> BeautifulSoup:
        return BeautifulSoup(html, "lxml")

    # ---------------------------- 子类实现 ----------------------------

    @abstractmethod
    def parse_book_info(self, html: str, source_url: str) -> BookInfo: ...

    @abstractmethod
    def parse_chapter_list(self, html: str, source_url: str) -> list[ChapterRef]: ...

    @abstractmethod
    def parse_chapter_content(self, html: str, url: str) -> str: ...

    # ---------------------------- 主流程 ----------------------------

    def scrape_book(
        self,
        book_url: str,
        *,
        max_chapters: int | None = None,
        start_chapter: int = 1,
        on_progress: Callable[[int, int, str], None] | None = None,
        genre: str = "",
        tags: list[str] | None = None,
    ) -> BookRecord:
        """抓取目录 + 章节，落地到 corpus/raw/，更新 metadata。"""
        logger.info("fetching book index: %s", book_url)
        index_html = self.fetch(book_url)
        info = self.parse_book_info(index_html, book_url)
        chapters = self.parse_chapter_list(index_html, book_url)
        if not chapters:
            raise ScraperError(f"no chapters parsed from {book_url}")

        slug = slugify(info.title)
        record = self.store.get(slug) or BookRecord(
            slug=slug,
            title=info.title,
            author=info.author,
            source=self.site_name,
            source_url=info.source_url,
            genre=genre or info.genre,
            tags=tags or info.tags or [],
        )
        record.total_chapters = len(chapters)
        self.store.upsert(record)

        book_dir = RAW_DIR / slug
        book_dir.mkdir(parents=True, exist_ok=True)

        end_chapter = len(chapters) if max_chapters is None else min(start_chapter + max_chapters - 1, len(chapters))

        scraped = record.scraped_chapters
        total_words = record.total_words

        for chapter in chapters[start_chapter - 1:end_chapter]:
            dest = self._chapter_path(book_dir, chapter)
            if dest.exists():
                logger.debug("skip existing %s", dest.name)
                continue
            try:
                text = self._scrape_one_chapter(chapter)
            except ScraperError:
                logger.exception("chapter %s failed, stopping", chapter.index)
                break
            dest.write_text(f"# {chapter.title}\n\n{text}\n", encoding="utf-8")
            scraped = max(scraped, chapter.index)
            total_words += _count_words(text)
            if on_progress:
                on_progress(chapter.index, len(chapters), chapter.title)

        self.store.update_progress(
            slug,
            scraped_chapters=scraped,
            total_words=total_words,
        )
        return self.store.get(slug)  # type: ignore[return-value]

    def _scrape_one_chapter(self, chapter: ChapterRef) -> str:
        html = self.fetch(chapter.url)
        return self.parse_chapter_content(html, chapter.url).strip()

    @staticmethod
    def _chapter_path(book_dir: Path, chapter: ChapterRef) -> Path:
        safe_title = re.sub(r'[\\/:*?"<>|\r\n\t]+', "_", chapter.title)[:60]
        return book_dir / f"{chapter.index:04d}_{safe_title}.txt"


# --------------------------- 工具函数 ---------------------------

_WORD_RE = re.compile(r"[\u4e00-\u9fff]|[A-Za-z]+")


def _count_words(text: str) -> int:
    """中文按字、英文按词计数，给数据分析用。"""
    return sum(1 for _ in _WORD_RE.finditer(text))
