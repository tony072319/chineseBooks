"""把 so-novel 下载产物转成我们项目的语料格式。

so-novel 有两种输出形态（按 config.ini 里 `preserve-chapter-cache` 决定）：

1. **单文件模式**：`downloads/<书名>(作者).txt`
   整本一个文件，头部是"书名/作者"元信息，章节以 `第X章 标题` 作为分隔线。

2. **目录模式**（推荐，`preserve-chapter-cache=1`）：
   `downloads/txt/<书名>(作者)/第X章 标题.txt` 每章一个文件。

两种都支持：
    python -m scrapers.cli ingest /path/to/so-novel-output --genre 玄幻 --tags 升级流
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

from .config import RAW_DIR
from .metadata import BookRecord, MetadataStore, slugify

logger = logging.getLogger(__name__)

# 典型章节标题格式：
#   第一章 XXX
#   第 1 章 XXX
#   第1章：XXX
#   第一百零八章 XXX
#   第001章 XXX
CHAPTER_HEADING = re.compile(
    r"^\s*第\s*[零一二三四五六七八九十百千万亿0-9]+\s*[章节回卷]\s*[\s：:．.、-]?\s*(.*\S)?\s*$"
)

# so-novel 文件名样式：`第一章 XXX.txt`
FILENAME_CHAPTER = re.compile(
    r"^(?:\d+[_\.\s]+)?(第\s*[零一二三四五六七八九十百千万亿0-9]+\s*[章节回卷]\s*.+?)\.txt$"
)

BOOK_DIR_PATTERN = re.compile(r"^(.+?)[（(](.+?)[)）]$")  # "斗破苍穹（天蚕土豆）"

_CN_NUM_MAP = {ch: i for i, ch in enumerate("零一二三四五六七八九", start=0)}
_CN_UNITS = {"十": 10, "百": 100, "千": 1000, "万": 10000, "亿": 10**8}


@dataclass
class ParsedChapter:
    index: int
    title: str
    body: str


@dataclass
class IngestResult:
    title: str
    author: str
    chapters_written: int
    total_words: int
    slug: str


# ---------------- 中文数字转 int（容错，识别不了就返回 None） ----------------

def cn_to_int(text: str) -> int | None:
    text = text.strip()
    if text.isdigit():
        return int(text)
    if not text:
        return None
    total = 0
    current = 0
    for ch in text:
        if ch in _CN_NUM_MAP:
            current = _CN_NUM_MAP[ch]
        elif ch in _CN_UNITS:
            unit = _CN_UNITS[ch]
            total += (current or 1) * unit
            current = 0
        else:
            return None
    return total + current


def chapter_number(title: str) -> int | None:
    """从章节标题提取章节号（阿拉伯或中文皆可）。"""
    m = re.match(r"^\s*第\s*([零一二三四五六七八九十百千万亿0-9]+)\s*[章节回卷]", title)
    if not m:
        return None
    return cn_to_int(m.group(1))


# ---------------- 解析单本书 ----------------

def _split_book_dir_name(dirname: str) -> tuple[str, str]:
    """把 "斗破苍穹（天蚕土豆）" 拆成 (书名, 作者)。"""
    m = BOOK_DIR_PATTERN.match(dirname)
    if m:
        return m.group(1).strip(), m.group(2).strip()
    return dirname.strip(), ""


def parse_directory(path: Path) -> tuple[str, str, list[ParsedChapter]]:
    """目录模式：`<书名>(作者)/第X章 XX.txt`。"""
    title, author = _split_book_dir_name(path.name)

    chapters: list[ParsedChapter] = []
    txt_files = sorted(path.glob("*.txt"))
    if not txt_files:
        raise ValueError(f"目录 {path} 下没有 .txt 章节文件")

    fallback_index = 0
    for f in txt_files:
        match = FILENAME_CHAPTER.match(f.name)
        if match:
            chapter_title = match.group(1).strip()
        else:
            chapter_title = f.stem

        num = chapter_number(chapter_title)
        if num is None:
            fallback_index += 1
            num = fallback_index
        body = f.read_text(encoding="utf-8", errors="replace").strip()
        chapters.append(ParsedChapter(index=num, title=chapter_title, body=body))

    # 去重（目录模式偶尔会有重复章节号），取最长 body
    bucket: dict[int, ParsedChapter] = {}
    for c in chapters:
        prev = bucket.get(c.index)
        if prev is None or len(c.body) > len(prev.body):
            bucket[c.index] = c
    chapters = sorted(bucket.values(), key=lambda c: c.index)
    return title, author, chapters


def parse_single_file(path: Path) -> tuple[str, str, list[ParsedChapter]]:
    """单文件模式：整本书一个 TXT，头部"书名/作者"，章节以标题行分隔。"""
    text = path.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()

    title = path.stem
    author = ""
    body_start = 0

    for i, line in enumerate(lines[:20]):
        stripped = line.strip()
        if stripped.startswith("书名"):
            title = _right_of_colon(stripped) or title
            body_start = i + 1
        elif stripped.startswith("作者"):
            author = _right_of_colon(stripped) or author
            body_start = i + 1

    # 如果文件名是"书名(作者)"风格，优先用那个
    name_m = BOOK_DIR_PATTERN.match(path.stem)
    if name_m:
        title = name_m.group(1).strip()
        author = name_m.group(2).strip() or author

    chapters: list[ParsedChapter] = []
    current_title: str | None = None
    current_lines: list[str] = []
    fallback_index = 0

    def flush() -> None:
        nonlocal current_title, current_lines, fallback_index
        if current_title is None:
            return
        num = chapter_number(current_title)
        if num is None:
            fallback_index += 1
            num = fallback_index
        body = "\n".join(current_lines).strip()
        chapters.append(ParsedChapter(index=num, title=current_title, body=body))
        current_title = None
        current_lines = []

    for line in lines[body_start:]:
        if CHAPTER_HEADING.match(line):
            flush()
            current_title = line.strip()
        elif current_title is not None:
            current_lines.append(line)
    flush()

    if not chapters:
        raise ValueError(f"从 {path} 未解析出任何章节（没有识别到章节标题）。")

    return title, author, chapters


def _right_of_colon(s: str) -> str:
    for sep in ("：", ":"):
        if sep in s:
            return s.split(sep, 1)[1].strip()
    return ""


# ---------------- 入库 ----------------

_WORD_RE = re.compile(r"[\u4e00-\u9fff]|[A-Za-z]+")


def _count_words(text: str) -> int:
    return sum(1 for _ in _WORD_RE.finditer(text))


def _safe_filename(title: str) -> str:
    cleaned = re.sub(r'[\\/:*?"<>|\r\n\t]+', "_", title)
    return cleaned[:60]


def ingest_path(
    source: Path,
    *,
    store: MetadataStore | None = None,
    genre: str = "",
    tags: list[str] | None = None,
    overwrite: bool = False,
    source_name: str = "so-novel",
) -> IngestResult:
    """入口：自动判断 source 是目录还是单文件并解析入库。"""
    source = Path(source)
    store = store or MetadataStore()
    tags = tags or []

    if source.is_dir():
        title, author, chapters = parse_directory(source)
    elif source.is_file():
        title, author, chapters = parse_single_file(source)
    else:
        raise FileNotFoundError(source)

    if not title:
        raise ValueError(f"无法识别书名：{source}")

    slug = slugify(title)
    record = store.get(slug) or BookRecord(
        slug=slug,
        title=title,
        author=author,
        source=source_name,
        source_url=str(source),
        genre=genre,
        tags=tags,
    )
    if author and not record.author:
        record.author = author
    if genre:
        record.genre = genre
    if tags:
        record.tags = tags

    book_dir = RAW_DIR / slug
    book_dir.mkdir(parents=True, exist_ok=True)

    written = 0
    total_words = record.total_words if not overwrite else 0
    max_index = record.scraped_chapters if not overwrite else 0

    for ch in chapters:
        dest = book_dir / f"{ch.index:04d}_{_safe_filename(ch.title)}.txt"
        if dest.exists() and not overwrite:
            continue
        dest.write_text(f"# {ch.title}\n\n{ch.body}\n", encoding="utf-8")
        written += 1
        total_words += _count_words(ch.body)
        max_index = max(max_index, ch.index)

    record.total_chapters = max(record.total_chapters, max_index, len(chapters))
    record.scraped_chapters = max_index
    record.total_words = total_words
    store.upsert(record)

    return IngestResult(
        title=title,
        author=author,
        chapters_written=written,
        total_words=total_words,
        slug=slug,
    )
