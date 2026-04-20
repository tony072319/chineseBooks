"""ingest.py 单元测试 —— 不走网络。"""
from __future__ import annotations

from pathlib import Path

import pytest

from scrapers.ingest import (
    chapter_number,
    cn_to_int,
    ingest_path,
    parse_directory,
    parse_single_file,
    read_text_auto,
)
from scrapers.metadata import MetadataStore


def test_cn_to_int_handles_common_cases() -> None:
    assert cn_to_int("一") == 1
    assert cn_to_int("十") == 10
    assert cn_to_int("十三") == 13
    assert cn_to_int("三十二") == 32
    assert cn_to_int("一百") == 100
    assert cn_to_int("一百零八") == 108
    assert cn_to_int("一千二百三十四") == 1234
    assert cn_to_int("123") == 123
    assert cn_to_int("乱码") is None


def test_chapter_number_extracts_index() -> None:
    assert chapter_number("第一章 陨落的天才") == 1
    assert chapter_number("第 108 章 新的开始") == 108
    assert chapter_number("第三百二十一章：救赎") == 321
    assert chapter_number("序章 开端") is None
    assert chapter_number("随便什么") is None


def test_parse_single_file_splits_chapters(tmp_path: Path) -> None:
    content = (
        "书名：测试之书\n"
        "作者：测试作者\n"
        "\n"
        "第一章 开场白\n"
        "\n"
        "    这里是第一章的正文内容，主角登场了。\n"
        "    又是一段。\n"
        "\n"
        "第二章 金手指\n"
        "\n"
        "    金手指激活，主角开始崛起。\n"
        "\n"
        "第三章 打脸\n"
        "\n"
        "    碾压对手，读者爽了。\n"
    )
    f = tmp_path / "测试之书.txt"
    f.write_text(content, encoding="utf-8")

    title, author, chapters = parse_single_file(f)
    assert title == "测试之书"
    assert author == "测试作者"
    assert [c.index for c in chapters] == [1, 2, 3]
    assert chapters[0].title == "第一章 开场白"
    assert "主角登场了" in chapters[0].body
    assert "金手指激活" in chapters[1].body


def test_parse_single_file_handles_paren_filename(tmp_path: Path) -> None:
    content = (
        "第一章 A\n"
        "正文 A\n"
        "第二章 B\n"
        "正文 B\n"
    )
    f = tmp_path / "斗破苍穹(天蚕土豆).txt"
    f.write_text(content, encoding="utf-8")
    title, author, _ = parse_single_file(f)
    assert title == "斗破苍穹"
    assert author == "天蚕土豆"


def test_parse_directory_reads_per_chapter_files(tmp_path: Path) -> None:
    book_dir = tmp_path / "测试书(某作者)"
    book_dir.mkdir()
    (book_dir / "第一章 开场.txt").write_text("正文 1\n", encoding="utf-8")
    (book_dir / "第二章 金手指.txt").write_text("正文 2\n", encoding="utf-8")
    (book_dir / "第三章 打脸.txt").write_text("正文 3\n", encoding="utf-8")

    title, author, chapters = parse_directory(book_dir)
    assert title == "测试书"
    assert author == "某作者"
    assert [c.index for c in chapters] == [1, 2, 3]
    assert chapters[1].body == "正文 2"


def test_read_text_auto_decodes_utf8_and_gbk(tmp_path: Path) -> None:
    utf8_path = tmp_path / "utf8.txt"
    utf8_path.write_text("斗破苍穹\n第一章 陨落的天才\n", encoding="utf-8")
    assert "斗破苍穹" in read_text_auto(utf8_path)

    gbk_path = tmp_path / "gbk.txt"
    gbk_path.write_bytes("全职高手\n第一章 封号被废\n".encode("gbk"))
    decoded = read_text_auto(gbk_path)
    assert "全职高手" in decoded
    assert "第一章" in decoded

    utf8_bom = tmp_path / "bom.txt"
    utf8_bom.write_bytes("\ufeff十日终焉\n".encode("utf-8"))
    assert read_text_auto(utf8_bom).startswith("十日终焉")


def test_parse_single_file_works_on_gbk(tmp_path: Path) -> None:
    content = (
        "书名：测试GBK\n"
        "作者：某某\n"
        "\n"
        "第一章 开场\n"
        "中文正文，编码是 GBK。\n"
        "第二章 继续\n"
        "还是中文。\n"
    )
    f = tmp_path / "test_gbk.txt"
    f.write_bytes(content.encode("gbk"))
    title, author, chapters = parse_single_file(f)
    assert title == "测试GBK"
    assert author == "某某"
    assert len(chapters) == 2


def test_parse_single_file_errors_without_chapters(tmp_path: Path) -> None:
    f = tmp_path / "空书.txt"
    f.write_text("这里没有任何章节标题，只有一堆字\n", encoding="utf-8")
    with pytest.raises(ValueError):
        parse_single_file(f)


def test_ingest_path_writes_corpus_and_metadata(tmp_path: Path, monkeypatch) -> None:
    from scrapers import ingest as ingest_mod

    raw_dir = tmp_path / "raw"
    monkeypatch.setattr(ingest_mod, "RAW_DIR", raw_dir)

    content = (
        "书名：斗破\n"
        "作者：土豆\n"
        "\n"
        "第一章 陨落\n"
        "测试正文一。\n"
        "第二章 觉醒\n"
        "测试正文二。\n"
    )
    src = tmp_path / "斗破.txt"
    src.write_text(content, encoding="utf-8")

    store = MetadataStore(tmp_path / "meta.json")
    result = ingest_path(src, store=store, genre="玄幻", tags=["升级流"])

    assert result.title == "斗破"
    assert result.author == "土豆"
    assert result.chapters_written == 2
    assert result.total_words > 0

    book_dir = raw_dir / "斗破"
    files = sorted(p.name for p in book_dir.iterdir())
    assert files == ["0001_第一章 陨落.txt", "0002_第二章 觉醒.txt"]
    assert "测试正文一" in (book_dir / files[0]).read_text(encoding="utf-8")

    record = store.get("斗破")
    assert record is not None
    assert record.genre == "玄幻"
    assert record.tags == ["升级流"]
    assert record.scraped_chapters == 2


def test_ingest_path_is_idempotent(tmp_path: Path, monkeypatch) -> None:
    from scrapers import ingest as ingest_mod
    monkeypatch.setattr(ingest_mod, "RAW_DIR", tmp_path / "raw")

    src = tmp_path / "书.txt"
    src.write_text("第一章 x\n正文\n第二章 y\n正文2\n", encoding="utf-8")
    store = MetadataStore(tmp_path / "meta.json")

    r1 = ingest_path(src, store=store)
    r2 = ingest_path(src, store=store)
    assert r1.chapters_written == 2
    assert r2.chapters_written == 0   # 第二次全部已存在，应跳过

    r3 = ingest_path(src, store=store, overwrite=True)
    assert r3.chapters_written == 2   # overwrite 下重写
