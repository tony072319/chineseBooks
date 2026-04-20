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

import chardet

from .config import RAW_DIR
from .metadata import BookRecord, MetadataStore, slugify

logger = logging.getLogger(__name__)

# 标准章节标题格式：
#   第一章 XXX
#   第 1 章 XXX
#   第一百零八章 XXX
#   新世界 第一章 XXX                 （续集带 1 个前缀）
#   第一篇 一夜觉醒 第一章 罗峰         （卷/篇 + 章，带 2 个前缀）
# 允许 0-3 个短前缀块（如"第X卷 XX"），整行 ≤80 字
CHAPTER_HEADING = re.compile(
    r"^\s*(?:\S{1,10}\s+){0,3}"
    r"第\s*([零一二三四五六七八九十百千万亿0-9]{1,15})\s*章"
    r"(?=[\s：:．.、，,。\-（(]|$)"
)

# 非标章节格式（如《大王饶命》用 "1、庙会"、"2、老乞丐" 这种）：
#   1、XXX  |  1.XXX  |  1 XXX  |  一、XXX
CHAPTER_HEADING_NUMERIC = re.compile(
    r"^\s*(\d{1,4}|[零一二三四五六七八九十百千]{1,6})"
    r"\s*[、．\.。]\s*"
    r"(.{1,50}?)\s*$"
)

# 文件名提取章节标题：`第一章 XXX.txt`
FILENAME_CHAPTER = re.compile(
    r"^(?:\d+[_\.\s]+)?(第\s*[零一二三四五六七八九十百千万亿0-9]+\s*[章节回卷]\s*.+?)\.txt$"
)

MAX_HEADING_LINE_LEN = 80
MAX_CHAPTER_NUMBER = 5000


def detect_chapter_heading(line: str, numeric_style: bool = False) -> tuple[int, str] | None:
    """若 line 是章节标题，返回 (章号, 完整标题)；否则返回 None。

    默认识别标准 "第X章" 格式。当 numeric_style=True 时也识别 "1、XX" 这种。
    """
    stripped = line.strip()
    if not stripped or len(stripped) > MAX_HEADING_LINE_LEN:
        return None
    m = CHAPTER_HEADING.match(stripped)
    if m:
        num = cn_to_int(m.group(1))
        if num is not None and 0 < num <= MAX_CHAPTER_NUMBER:
            return num, stripped
    if numeric_style:
        m = CHAPTER_HEADING_NUMERIC.match(stripped)
        if m:
            num = cn_to_int(m.group(1))
            if num is not None and 0 < num <= MAX_CHAPTER_NUMBER:
                return num, stripped
    return None

BOOK_DIR_PATTERN = re.compile(r"^(.+?)[（(](.+?)[)）]$")  # "斗破苍穹（天蚕土豆）"

# 从文件名中剥离常见的"（校对版全本）"、"作者：XXX"、外层 《》 等装饰，返回纯书名
_FILENAME_NOISE_PATTERNS = [
    re.compile(r"[ \t]*作\s*者\s*[:：]\s*.+$"),          # 尾部 "作者：耳根"
    re.compile(r"[（(][^（）()]*?"
               r"(?:校对|精校|全本|完结|完本|完整|最新|修订|简体|繁体|小说|TXT|txt)"
               r"[^（）()]*?[)）]"),                      # "（校对版全本）" / "(完本)" 等
    re.compile(r"^《|》$"),                               # 外层书名号
]


def normalize_filename_title(raw: str) -> str:
    """清洗文件名里的噪声，留下纯粹的书名。

    >>> normalize_filename_title("《仙逆》（校对版全本）作者：耳根")
    '仙逆'
    >>> normalize_filename_title("斗破苍穹(天蚕土豆)")
    '斗破苍穹'
    """
    s = raw.strip()
    while True:
        prev = s
        for pat in _FILENAME_NOISE_PATTERNS:
            s = pat.sub("", s).strip()
        if s == prev:
            break
    m = BOOK_DIR_PATTERN.match(s)
    if m:
        s = m.group(1).strip()
    return s.strip() or raw

_CN_NUM_MAP = {ch: i for i, ch in enumerate("零一二三四五六七八九", start=0)}
_CN_UNITS = {"十": 10, "百": 100, "千": 1000, "万": 10000, "亿": 10**8}


def read_text_auto(path: Path) -> str:
    """自动识别 TXT 文件编码（utf-8 / gb18030 / big5 等），返回解码后的字符串。

    策略：先试 UTF-8（覆盖大部分现代文件），再试 GB18030（覆盖绝大多数中文
    简体文件，是 GBK/GB2312 的超集），最后用 chardet 兜底。chardet 对短中文
    样本会误判（常识别成 koi8-u/ISO-8859 之类），所以不做第一选择。
    """
    raw = path.read_bytes()
    for enc in ("utf-8-sig", "utf-8", "gb18030"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    guess = (chardet.detect(raw[:200_000]).get("encoding") or "utf-8").lower()
    try:
        return raw.decode(guess, errors="replace")
    except LookupError:
        return raw.decode("utf-8", errors="replace")


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
    m = re.search(r"第\s*([零一二三四五六七八九十百千万亿0-9]+)\s*章", title)
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
        body = read_text_auto(f).strip()
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
    text = read_text_auto(path)
    lines = text.splitlines()

    title = normalize_filename_title(path.stem)
    author = ""
    body_start = 0

    for i, line in enumerate(lines[:30]):
        kv = _parse_header_kv(line)
        if kv is None:
            continue
        key, value = kv
        if key == "书名":
            title = value or title
            body_start = i + 1
        elif key == "作者":
            author = value or author
            body_start = i + 1

    # 处理"斗破苍穹(天蚕土豆)"这种文件名：括号内是作者
    name_m = BOOK_DIR_PATTERN.match(path.stem)
    if name_m and "校对" not in name_m.group(2) and "全本" not in name_m.group(2):
        title = normalize_filename_title(name_m.group(1).strip())
        author = name_m.group(2).strip() or author

    def _split(numeric_style: bool) -> list[ParsedChapter]:
        out: list[ParsedChapter] = []
        cur_title: str | None = None
        cur_num: int | None = None
        cur_lines: list[str] = []

        def _flush() -> None:
            nonlocal cur_title, cur_num, cur_lines
            if cur_title is None:
                return
            body = "\n".join(cur_lines).strip()
            out.append(ParsedChapter(index=cur_num or 0, title=cur_title, body=body))
            cur_title = None
            cur_num = None
            cur_lines = []

        for line in lines[body_start:]:
            detected = detect_chapter_heading(line, numeric_style=numeric_style)
            if detected is not None:
                _flush()
                cur_num, cur_title = detected
            elif cur_title is not None:
                cur_lines.append(line)
        _flush()
        return out

    chapters = _split(numeric_style=False)
    # 标准 "第X章" 没识别到任何章节，或章节数少得可疑（< 20），换成宽松模式重试
    if len(chapters) < 20:
        alt = _split(numeric_style=True)
        if len(alt) > len(chapters):
            chapters = alt

    if not chapters:
        raise ValueError(f"从 {path} 未解析出任何章节（没有识别到章节标题）。")

    # 丢弃明显是噪声的章节（body < 200 字，多半是正文里偶然出现"第X章"）
    filtered = [c for c in chapters if len(c.body) >= 200]
    if not filtered:
        filtered = chapters  # 全本都很短时保底

    # 按位置单调重编号（处理续集章号重置 / 乱序 / 重复）
    for pos, c in enumerate(filtered, start=1):
        c.index = pos

    return title, author, filtered


_HEADER_NOISE = re.compile(
    r"(?:栏目|类型|类别|来源|上传|时间|字数|总字数|作品类型|主要角色|简介)[：:]?"
)


def _parse_header_kv(line: str) -> tuple[str, str] | None:
    """从 TXT 头部一行抽 (key, value)。兼容 "书名：XXX" 和 "作    者    XXX"。"""
    stripped = line.strip()
    m = re.match(r"^(作\s*者|书\s*名)[\s\t：:\u3000]+(.+?)$", stripped)
    if not m:
        return None
    key = re.sub(r"\s+", "", m.group(1))
    value = m.group(2).strip()
    # 砍掉多余信息（"作者 某某  栏目:xxx  字数:yyy" 这种）
    value = re.split(r"[\t\u3000]|\s{2,}", value, maxsplit=1)[0]
    value = _HEADER_NOISE.split(value, maxsplit=1)[0]
    return key, value.strip()


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
