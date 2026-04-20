"""analysis 模块的冒烟测试 —— 用 monkeypatch 指向临时 corpus 目录。"""
from __future__ import annotations

from pathlib import Path

import pytest

from analysis.corpus import Book, Chapter


@pytest.fixture
def fake_book(tmp_path: Path, monkeypatch):
    """建一个临时 corpus/raw 指向目录，返回一个工厂函数 add_chapter()。"""
    raw_root = tmp_path / "raw"
    raw_root.mkdir()
    # 让 Book.directory 指向 raw_root/<slug>
    from analysis import corpus as corpus_mod
    monkeypatch.setattr(corpus_mod, "RAW_DIR", raw_root)

    book_slug = "测试书"
    book_dir = raw_root / book_slug
    book_dir.mkdir()

    def add_chapter(idx: int, title: str, body: str) -> None:
        safe = title.replace("/", "_")
        (book_dir / f"{idx:04d}_{safe}.txt").write_text(
            f"# {title}\n\n{body}\n", encoding="utf-8"
        )

    book = Book(slug=book_slug, title=book_slug, author="测试作者", genre="玄幻")
    return book, add_chapter


def test_chapter_word_count_only_counts_chinese() -> None:
    ch = Chapter(
        book_slug="x", index=1, title="t",
        body="hello 你好世界，123！  abc", path=Path("/tmp/x")
    )
    assert ch.word_count == 4


def test_stats_hist_and_outliers(fake_book) -> None:
    from analysis.stats import analyze_chapter_stats
    book, add = fake_book
    add(1, "chap1", "中" * 3000)       # 2500-3500
    add(2, "chap2", "中" * 3800)       # 3500-4500
    add(3, "chap3", "中" * 1200)       # < 1500
    add(4, "chap4", "中" * 15000)      # 长异常
    s = analyze_chapter_stats(book)
    assert s is not None
    assert s.count == 4
    assert s.histogram["< 1500"] == 1
    assert s.histogram["2500-3500"] == 1
    assert s.histogram["3500-4500"] == 1
    assert s.histogram[">= 6000"] == 1
    assert len(s.long_outliers) == 1
    assert s.long_outliers[0][2] == 15000


def test_opening_detects_cliffhanger_and_golden_finger(fake_book) -> None:
    from analysis.opening import analyze_opening
    book, add = fake_book
    body_ch1 = "萧炎走进测试厅，被众人嘲笑。" * 50 + "突然，他看到一枚戒指……"
    body_ch2 = "戒指里传出老头的声音：系统激活。系统给了他一个任务。面板亮起。获得奖励。"
    body_ch3 = "他狠狠打脸了那些嘲讽他的人，震惊！"
    add(1, "测试 1", body_ch1)
    add(2, "测试 2", body_ch2)
    add(3, "测试 3", body_ch3)
    op = analyze_opening(book, first_n=3, scan_n=30)
    assert len(op.chapters) == 3
    assert op.chapters[0].cliffhanger_end is True
    assert "嘲笑" in op.chapters[0].conflict_words
    assert op.first_golden_finger_chapter is not None
    assert op.first_golden_finger_chapter <= 2


def test_tropes_density(fake_book) -> None:
    from analysis.tropes import analyze_tropes
    book, add = fake_book
    add(1, "a", "震惊震惊震惊" + "中" * 100)
    add(2, "b", "打脸" * 3 + "中" * 100)
    hits = analyze_tropes(book)
    names = [h.name for h in hits]
    assert "震惊情绪词" in names
    assert "打脸/羞辱反转" in names


def test_render_book_report_produces_markdown(fake_book) -> None:
    from analysis.report import analyze_book, render_book_report
    book, add = fake_book
    for i in range(1, 6):
        add(i, f"第{i}章 测试", "中" * 2800 + "突然出现了一枚戒指！")
    ba = analyze_book(book)
    assert ba is not None
    md = render_book_report(ba)
    assert "测试书" in md
    assert "## 1 · 整体规模" in md
    assert "## 2 · 章节字数分布" in md
    assert "## 3 · 黄金三章" in md
    assert "## 4 · 套路" in md
