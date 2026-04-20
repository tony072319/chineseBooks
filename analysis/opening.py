"""黄金三章 / 开头分析：
- 第 1-3 章字数、开头 500 字摘要、结尾钩子
- 扫描前 N 章找"金手指"首次密集出现的章节
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from .corpus import Book, Chapter

# 金手指信号词：按类型聚类
GOLDEN_FINGER_KEYWORDS: dict[str, list[str]] = {
    "系统流": ["系统", "面板", "属性栏", "任务", "签到", "奖励", "恭喜宿主", "叮", "商城"],
    "老爷爷/传承": ["老头", "老者", "前辈", "戒指", "玉佩", "残魂", "传承", "传人"],
    "重生/穿越": ["重生", "穿越", "前世", "上一世", "醒来", "二十一世纪", "魂穿"],
    "血脉/觉醒": ["血脉", "觉醒", "激活", "天赋", "异瞳", "体质"],
    "丹田/经脉/灵气": ["丹田", "经脉", "灵气", "真气", "斗气"],
    "空间/秘境": ["空间", "秘境", "玄妙", "小世界", "空间戒指"],
    "神秘物品": ["神秘", "古老", "上古", "异宝", "神兵"],
}

# 章末钩子信号：结尾标点 + 情绪字
CLIFFHANGER_PUNCT = re.compile(r"[？！…]+[」\"」'']?\s*$|[.]{3,}\s*$")
CLIFFHANGER_KEYWORDS = ["突然", "猛然", "竟然", "忽然", "陡然", "却听", "却见", "传来", "响起"]

# 第一章开场信号
OPENING_CONFLICT = ["嘲笑", "嘲讽", "讥讽", "讥笑", "冷笑", "废物", "废柴", "退婚",
                     "欺辱", "凌辱", "羞辱", "轻视", "看不起", "咒骂", "骂声"]


@dataclass
class OpeningChapter:
    index: int
    title: str
    word_count: int
    first_300: str
    last_60: str
    conflict_words: dict[str, int] = field(default_factory=dict)
    golden_finger_hits: dict[str, dict[str, int]] = field(default_factory=dict)
    cliffhanger_end: bool = False
    cliffhanger_signal: str = ""


@dataclass
class OpeningAnalysis:
    chapters: list[OpeningChapter] = field(default_factory=list)
    first_golden_finger_chapter: int | None = None
    first_golden_finger_type: str | None = None
    first_golden_finger_hits: list[str] = field(default_factory=list)


def _count_kw_hits(body: str, keywords: list[str]) -> dict[str, int]:
    return {kw: body.count(kw) for kw in keywords if kw in body}


_TRAILING_NOISE = re.compile(r"[-=—_*※ \t\r\n]{4,}\s*$")   # "-----" 之类的分隔线


def _strip_trailing_noise(text: str) -> str:
    """去掉章节正文尾部 TXT80 之类加的分隔线。"""
    prev = None
    while prev != text:
        prev = text
        text = _TRAILING_NOISE.sub("", text).rstrip()
    return text


def _analyze_chapter(ch: Chapter) -> OpeningChapter:
    body = _strip_trailing_noise(ch.body)
    compact = re.sub(r"\s+", "", body)
    first_300 = compact[:300]
    last_60 = compact[-60:]

    conflict_hits = _count_kw_hits(body, OPENING_CONFLICT)

    gf_hits: dict[str, dict[str, int]] = {}
    for gf_type, kws in GOLDEN_FINGER_KEYWORDS.items():
        hits = _count_kw_hits(body, kws)
        if hits:
            gf_hits[gf_type] = hits

    last_part = compact[-120:]
    cliffhanger = bool(CLIFFHANGER_PUNCT.search(last_part))
    signal_hit = next((kw for kw in CLIFFHANGER_KEYWORDS if kw in last_part), "")

    return OpeningChapter(
        index=ch.index,
        title=ch.title,
        word_count=ch.word_count,
        first_300=first_300,
        last_60=last_60,
        conflict_words=conflict_hits,
        golden_finger_hits=gf_hits,
        cliffhanger_end=cliffhanger,
        cliffhanger_signal=signal_hit,
    )


def analyze_opening(book: Book, first_n: int = 3, scan_n: int = 30) -> OpeningAnalysis:
    result = OpeningAnalysis()

    first_gf: tuple[int, str, list[str]] | None = None
    for ch in book.iter_chapters(limit=scan_n):
        if ch.index <= first_n:
            result.chapters.append(_analyze_chapter(ch))

        # 扫描前 scan_n 章寻找首次金手指密集出现
        if first_gf is None:
            best_type: str | None = None
            best_total = 0
            best_hits: list[str] = []
            for gf_type, kws in GOLDEN_FINGER_KEYWORDS.items():
                hits = [kw for kw in kws if kw in ch.body]
                total = sum(ch.body.count(kw) for kw in hits)
                if total >= 3 and total > best_total:
                    best_type = gf_type
                    best_total = total
                    best_hits = hits
            if best_type is not None:
                first_gf = (ch.index, best_type, best_hits)

    if first_gf is not None:
        result.first_golden_finger_chapter = first_gf[0]
        result.first_golden_finger_type = first_gf[1]
        result.first_golden_finger_hits = first_gf[2]

    return result
