"""结构统计：章节字数分布、超长章、总体规模。"""
from __future__ import annotations

from dataclasses import dataclass, field
from statistics import mean, median, pstdev
from typing import Callable

from .corpus import Book

# 章节字数区间：覆盖 1500-4500 为主流网文甜区
BINS: list[tuple[str, Callable[[int], bool]]] = [
    ("< 1500",     lambda w: w < 1500),
    ("1500-2500",  lambda w: 1500 <= w < 2500),
    ("2500-3500",  lambda w: 2500 <= w < 3500),
    ("3500-4500",  lambda w: 3500 <= w < 4500),
    ("4500-6000",  lambda w: 4500 <= w < 6000),
    (">= 6000",    lambda w: w >= 6000),
]

LONG_OUTLIER_THRESHOLD = 10000   # 超过 1 万字视为切章异常
SHORT_OUTLIER_THRESHOLD = 500    # 少于 500 字视为噪声章


@dataclass
class ChapterStats:
    count: int
    total_words: int
    min_words: int
    max_words: int
    median_words: int
    mean_words: int
    stdev_words: int
    histogram: dict[str, int] = field(default_factory=dict)
    histogram_pct: dict[str, float] = field(default_factory=dict)
    long_outliers: list[tuple[int, str, int]] = field(default_factory=list)
    short_outliers: list[tuple[int, str, int]] = field(default_factory=list)


def analyze_chapter_stats(book: Book) -> ChapterStats | None:
    words: list[int] = []
    long_out: list[tuple[int, str, int]] = []
    short_out: list[tuple[int, str, int]] = []
    for ch in book.iter_chapters():
        w = ch.word_count
        words.append(w)
        if w > LONG_OUTLIER_THRESHOLD:
            long_out.append((ch.index, ch.title, w))
        elif w < SHORT_OUTLIER_THRESHOLD:
            short_out.append((ch.index, ch.title, w))

    if not words:
        return None

    total = sum(words)
    histogram = {label: sum(1 for w in words if pred(w)) for label, pred in BINS}
    hist_pct = {label: (cnt / len(words) * 100) for label, cnt in histogram.items()}

    return ChapterStats(
        count=len(words),
        total_words=total,
        min_words=min(words),
        max_words=max(words),
        median_words=int(median(words)),
        mean_words=int(mean(words)),
        stdev_words=int(pstdev(words)) if len(words) > 1 else 0,
        histogram=histogram,
        histogram_pct=hist_pct,
        long_outliers=sorted(long_out, key=lambda x: -x[2])[:10],
        short_outliers=sorted(short_out, key=lambda x: x[2])[:10],
    )
