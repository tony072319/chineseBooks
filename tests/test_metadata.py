"""MetadataStore 单元测试（不走网络）。"""
from __future__ import annotations

from pathlib import Path

from scrapers.metadata import BookRecord, MetadataStore, slugify


def test_store_roundtrip(tmp_path: Path) -> None:
    store = MetadataStore(tmp_path / "meta.json")
    assert store.list_books() == []

    record = BookRecord(
        slug="斗破苍穹",
        title="斗破苍穹",
        author="天蚕土豆",
        source="biquge",
        source_url="http://example.com/book/1",
        genre="玄幻",
        tags=["升级流", "复仇"],
    )
    store.upsert(record)

    fetched = store.get("斗破苍穹")
    assert fetched is not None
    assert fetched.title == "斗破苍穹"
    assert fetched.added_at  # 自动填充
    assert fetched.updated_at

    updated = store.update_progress(
        "斗破苍穹",
        total_chapters=1600,
        scraped_chapters=50,
        total_words=120000,
        is_complete=False,
    )
    assert updated is not None
    assert updated.scraped_chapters == 50
    assert updated.total_chapters == 1600

    assert store.remove("斗破苍穹") is True
    assert store.get("斗破苍穹") is None


def test_slugify_strips_unsafe_chars() -> None:
    assert slugify("斗破/苍穹") == "斗破_苍穹"
    assert slugify('诡秘*之"主') == "诡秘_之_主"
    assert slugify('*诡秘"之主') == "_诡秘_之主"
    assert slugify("  牧神记  ") == "牧神记"
    assert slugify("") == "untitled"
