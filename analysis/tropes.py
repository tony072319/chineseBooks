"""套路关键词密度扫描：量化每 1 万字中某类套路词的出现次数。"""
from __future__ import annotations

from dataclasses import dataclass, field

from .corpus import Book

TROPES: dict[str, list[str]] = {
    "打脸/羞辱反转": ["打脸", "狠狠打脸", "丢脸"],
    "震惊情绪词":   ["震惊", "吃惊", "骇然", "大惊失色", "脸色一变", "瞪大眼睛"],
    "嘲讽/冷笑":     ["嘲笑", "嘲讽", "讥讽", "冷笑", "讥笑"],
    "废柴/废物":     ["废物", "废柴"],
    "天才/妖孽":     ["天才", "妖孽", "惊才绝艳", "奇才"],
    "修炼术语":      ["修炼", "修行", "修为"],
    "斗气/灵气":     ["斗气", "灵气", "真气"],
    "修真境界":      ["练气", "筑基", "金丹", "元婴", "化神", "渡劫"],
    "系统提示":      ["叮", "系统提示", "恭喜宿主", "获得", "奖励", "任务完成"],
    "金手指物品":    ["戒指", "玉佩", "古玉", "神秘"],
    "重生/穿越":     ["重生", "穿越", "前世", "二十一世纪"],
    "签到/抽奖":     ["签到", "抽奖", "开始签到"],
    "救美/英雄":     ["救了她", "救下她", "护在身后", "挡在"],
    "回城/归家":     ["回到家", "回城", "回家乡"],
    "惊艳/倾城":     ["惊艳", "倾城", "绝美", "国色天香"],
    "卑微/下跪":     ["跪下", "求饶", "跪地", "叩头"],
    "吞噬/进化":     ["吞噬", "进化", "蜕变"],
    "爆体/毁天":     ["爆体", "毁天灭地", "石破天惊"],
    "装逼/牛逼":     ["装逼", "牛逼", "嘚瑟", "显摆"],
    "丹药/炼器":     ["丹药", "炼丹", "炼器", "符箓"],
}


@dataclass
class TropeHit:
    name: str
    total: int = 0
    per_10k: float = 0.0
    first_chapter: int | None = None
    matched_keywords: list[str] = field(default_factory=list)


def analyze_tropes(book: Book) -> list[TropeHit]:
    state: dict[str, TropeHit] = {name: TropeHit(name=name) for name in TROPES}
    total_words = 0

    for ch in book.iter_chapters():
        total_words += ch.word_count
        for name, keywords in TROPES.items():
            ch_total = 0
            matched: set[str] = set(state[name].matched_keywords)
            for kw in keywords:
                c = ch.body.count(kw)
                if c:
                    ch_total += c
                    matched.add(kw)
            if ch_total:
                hit = state[name]
                hit.total += ch_total
                if hit.first_chapter is None:
                    hit.first_chapter = ch.index
                hit.matched_keywords = sorted(matched)

    results = []
    for hit in state.values():
        if hit.total == 0:
            continue
        hit.per_10k = hit.total / max(total_words, 1) * 10000
        results.append(hit)

    results.sort(key=lambda h: (-h.per_10k, h.name))
    return results
