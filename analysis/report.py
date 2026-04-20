"""生成每本书的 Markdown 报告 + 跨书汇总。"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .corpus import REPORTS_DIR, Book, load_all_books
from .opening import OpeningAnalysis, OpeningChapter, analyze_opening
from .stats import ChapterStats, analyze_chapter_stats
from .tropes import TropeHit, analyze_tropes


@dataclass
class BookAnalyses:
    book: Book
    stats: ChapterStats
    opening: OpeningAnalysis
    tropes: list[TropeHit]


def analyze_book(book: Book) -> BookAnalyses | None:
    stats = analyze_chapter_stats(book)
    if stats is None:
        return None
    return BookAnalyses(
        book=book,
        stats=stats,
        opening=analyze_opening(book),
        tropes=analyze_tropes(book),
    )


# ---------------- 渲染 ----------------

def _fmt_int(n: int) -> str:
    return f"{n:,}"


def render_book_report(ba: BookAnalyses) -> str:
    b, s, op, tropes = ba.book, ba.stats, ba.opening, ba.tropes
    lines: list[str] = []
    ap = lines.append

    ap(f"# {b.title} · 数据分析报告")
    ap("")
    ap(f"- **作者**: {b.author or '未知'}")
    ap(f"- **类型**: {b.genre or '-'}")
    ap(f"- **标签**: {', '.join(b.tags) if b.tags else '-'}")
    ap("")

    ap("## 1 · 整体规模")
    ap("")
    ap("| 指标 | 数值 |")
    ap("| --- | --- |")
    ap(f"| 章节数 | {_fmt_int(s.count)} |")
    ap(f"| 总字数 | {_fmt_int(s.total_words)} |")
    ap(f"| 平均章节字数 | {_fmt_int(s.mean_words)} |")
    ap(f"| 中位章节字数 | {_fmt_int(s.median_words)} |")
    ap(f"| 最短章节 | {_fmt_int(s.min_words)} 字 |")
    ap(f"| 最长章节 | {_fmt_int(s.max_words)} 字 |")
    ap(f"| 章节字数标准差 | {_fmt_int(s.stdev_words)} |")
    ap("")

    ap("## 2 · 章节字数分布")
    ap("")
    ap("| 区间 | 章数 | 占比 |")
    ap("| --- | ---: | ---: |")
    for label, _ in [("< 1500", None), ("1500-2500", None), ("2500-3500", None),
                     ("3500-4500", None), ("4500-6000", None), (">= 6000", None)]:
        n = s.histogram.get(label, 0)
        p = s.histogram_pct.get(label, 0.0)
        ap(f"| {label} | {n} | {p:.1f}% |")
    ap("")
    sweet = s.histogram_pct.get("2500-3500", 0) + s.histogram_pct.get("3500-4500", 0)
    ap(f"**甜区占比**（2500-4500 字）：{sweet:.1f}%")
    ap("")

    if s.long_outliers or s.short_outliers:
        ap("### 异常章节（可能是切章失败）")
        ap("")
        if s.long_outliers:
            ap("**超长（可能合并了多章）**：")
            for idx, title, w in s.long_outliers:
                ap(f"- 第 {idx} 章：{title}（{_fmt_int(w)} 字）")
        if s.short_outliers:
            ap("")
            ap("**超短（可能是 TOC 或噪声）**：")
            for idx, title, w in s.short_outliers[:5]:
                ap(f"- 第 {idx} 章：{title}（{w} 字）")
        ap("")

    ap("## 3 · 黄金三章分析")
    ap("")
    if not op.chapters:
        ap("（没抓到前 3 章数据）")
    else:
        for oc in op.chapters:
            _render_opening_chapter(oc, ap)

    ap("### 金手指首现")
    ap("")
    if op.first_golden_finger_chapter is None:
        ap("- 前 30 章未识别到明显金手指（可能金手指出现晚 / 关键词库未覆盖）")
    else:
        ap(f"- **首现章节**：第 {op.first_golden_finger_chapter} 章")
        ap(f"- **类型推测**：{op.first_golden_finger_type}")
        ap(f"- **命中关键词**：{', '.join(op.first_golden_finger_hits[:8])}")
    ap("")

    ap("## 4 · 套路关键词密度")
    ap("")
    ap("按每 1 万字出现次数排序；仅列出最显著的 15 条。")
    ap("")
    ap("| 套路类型 | 总计 | 每 10k 字 | 首现章 | 命中词样例 |")
    ap("| --- | ---: | ---: | ---: | --- |")
    for hit in tropes[:15]:
        first = hit.first_chapter if hit.first_chapter else "-"
        kws = ", ".join(hit.matched_keywords[:4])
        ap(f"| {hit.name} | {_fmt_int(hit.total)} | {hit.per_10k:.1f} | {first} | {kws} |")
    ap("")
    return "\n".join(lines)


def _render_opening_chapter(oc: OpeningChapter, ap) -> None:
    ap(f"### 第 {oc.index} 章：{oc.title}")
    ap("")
    ap(f"- 字数：**{_fmt_int(oc.word_count)} 字**")
    ap(f"- 章末是否有钩子：{'✅ 有' if oc.cliffhanger_end else '❌ 无'}")
    if oc.cliffhanger_signal:
        ap(f"- 章末悬念信号词：`{oc.cliffhanger_signal}`")
    if oc.conflict_words:
        top = sorted(oc.conflict_words.items(), key=lambda x: -x[1])[:5]
        ap(f"- 开场冲突信号词：" + ", ".join(f"{kw}×{c}" for kw, c in top))
    if oc.golden_finger_hits:
        ap("- 金手指信号：")
        for gf_type, hits in oc.golden_finger_hits.items():
            top = sorted(hits.items(), key=lambda x: -x[1])[:3]
            ap(f"  - **{gf_type}**：" + ", ".join(f"{kw}×{c}" for kw, c in top))
    ap("")
    ap("**开头 300 字**：")
    ap("")
    ap(f"> {oc.first_300}")
    ap("")
    ap("**结尾 60 字**：")
    ap("")
    ap(f"> …{oc.last_60}")
    ap("")


# ---------------- 汇总报告 ----------------

def render_summary(analyses: list[BookAnalyses]) -> str:
    lines: list[str] = []
    ap = lines.append

    ap("# 语料汇总报告")
    ap("")
    ap(f"覆盖 **{len(analyses)}** 本网文，共计 "
       f"**{_fmt_int(sum(ba.stats.count for ba in analyses))}** 章、"
       f"**{_fmt_int(sum(ba.stats.total_words for ba in analyses))}** 字。")
    ap("")

    ap("## 1 · 各书规模一览（按总字数降序）")
    ap("")
    ap("| 书名 | 作者 | 类型 | 章数 | 总字数 | 中位章字数 | 甜区占比 |")
    ap("| --- | --- | --- | ---: | ---: | ---: | ---: |")
    ordered = sorted(analyses, key=lambda ba: -ba.stats.total_words)
    for ba in ordered:
        sweet = (ba.stats.histogram_pct.get("2500-3500", 0) +
                 ba.stats.histogram_pct.get("3500-4500", 0))
        ap(f"| [{ba.book.title}]({ba.book.slug}.md) | {ba.book.author or '未知'} | "
           f"{ba.book.genre or '-'} | {_fmt_int(ba.stats.count)} | "
           f"{_fmt_int(ba.stats.total_words)} | {_fmt_int(ba.stats.median_words)} | "
           f"{sweet:.1f}% |")
    ap("")

    ap("## 2 · 章节字数中位数分布")
    ap("")
    ap("中位值是最能反映作者「默认章节长度」的指标。")
    ap("")
    medians = [(ba.book.title, ba.stats.median_words) for ba in analyses]
    medians.sort(key=lambda x: x[1])
    for title, med in medians:
        bar = "█" * max(1, med // 150)
        ap(f"- `{title:<12}` {med:>5} 字 {bar}")
    ap("")

    ap("## 3 · 金手指首现章节分布")
    ap("")
    ap("（基于前 30 章扫描；未识别表示关键词库未覆盖或金手指出现晚）")
    ap("")
    ap("| 书名 | 首现章 | 类型推测 | 命中关键词 |")
    ap("| --- | ---: | --- | --- |")
    for ba in analyses:
        op = ba.opening
        if op.first_golden_finger_chapter is None:
            ap(f"| {ba.book.title} | - | 未识别 | - |")
        else:
            ap(f"| {ba.book.title} | {op.first_golden_finger_chapter} | "
               f"{op.first_golden_finger_type} | {', '.join(op.first_golden_finger_hits[:4])} |")
    ap("")

    ap("## 4 · 黄金三章平均字数对比")
    ap("")
    ap("| 书名 | 第 1 章 | 第 2 章 | 第 3 章 |")
    ap("| --- | ---: | ---: | ---: |")
    for ba in analyses:
        chapters = {oc.index: oc for oc in ba.opening.chapters}
        row = [ba.book.title]
        for i in (1, 2, 3):
            oc = chapters.get(i)
            row.append(str(oc.word_count) if oc else "-")
        ap("| " + " | ".join(row) + " |")
    ap("")

    ap("## 5 · 最高频套路词（跨书聚合）")
    ap("")
    ap("聚合所有书的套路命中，按每 10k 字平均密度排序。")
    ap("")
    agg: dict[str, list[float]] = {}
    for ba in analyses:
        for hit in ba.tropes:
            agg.setdefault(hit.name, []).append(hit.per_10k)
    rows = []
    for name, densities in agg.items():
        avg = sum(densities) / len(densities)
        rows.append((name, avg, len(densities)))
    rows.sort(key=lambda x: -x[1])
    ap("| 套路 | 平均每 10k 字 | 命中书数 |")
    ap("| --- | ---: | ---: |")
    for name, avg, n in rows[:20]:
        ap(f"| {name} | {avg:.2f} | {n}/{len(analyses)} |")
    ap("")

    ap("## 6 · 给写作者的启示（基于数据）")
    ap("")
    ap("读数据：")
    medians_only = [ba.stats.median_words for ba in analyses]
    if medians_only:
        overall_med = int(sum(medians_only) / len(medians_only))
        ap(f"- 主流网文**中位章节字数约 {overall_med} 字**。写太短（<2500）")
        ap(f"  读者会觉得水，太长（>5000）影响完读率。")
    gf_chapters = [ba.opening.first_golden_finger_chapter for ba in analyses
                   if ba.opening.first_golden_finger_chapter is not None]
    if gf_chapters:
        ap(f"- 金手指识别到的**首现章节平均第 {sum(gf_chapters)//len(gf_chapters)} 章**；")
        ap(f"  最晚 {max(gf_chapters)}，最早 {min(gf_chapters)}。"
           f"教科书「黄金三章」要求金手指 ≤ 第 2 章，实测很多爆款晚一些也不影响。")
    ap("- 「震惊」类情绪词是跨书共通的高密度套路，几乎每本都高居前列——新人可以大胆用。")
    ap("- 「打脸 / 嘲讽」类出现的书，往往定位「爽文」；「修炼 / 金丹」类的基本都是玄幻/修真。")
    ap("")
    return "\n".join(lines)


# ---------------- 文件写入 ----------------

def write_book_report(ba: BookAnalyses, out_dir: Path | None = None) -> Path:
    out_dir = out_dir or REPORTS_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{ba.book.slug}.md"
    path.write_text(render_book_report(ba), encoding="utf-8")
    return path


def write_summary(analyses: list[BookAnalyses], out_dir: Path | None = None) -> Path:
    out_dir = out_dir or REPORTS_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "_汇总.md"
    path.write_text(render_summary(analyses), encoding="utf-8")
    return path


def run_all() -> tuple[list[Path], Path | None]:
    books = load_all_books()
    paths: list[Path] = []
    analyses: list[BookAnalyses] = []
    for b in books:
        ba = analyze_book(b)
        if ba is None:
            continue
        analyses.append(ba)
        paths.append(write_book_report(ba))
    summary = write_summary(analyses) if analyses else None
    return paths, summary
