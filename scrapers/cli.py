"""命令行入口：

使用示例：
  python -m scrapers.cli list
  python -m scrapers.cli scrape biquge --url https://www.xbiquge.la/10/10489/ --max 30
  python -m scrapers.cli scrape piaotian --url https://www.ptwxz.com/html/5/5555/ --max 50
  python -m scrapers.cli remove 斗破苍穹
"""
from __future__ import annotations

import argparse
import logging
import sys
from typing import Type

from tqdm import tqdm

from .base import BaseScraper
from .biquge import BiqugeScraper
from .ingest import ingest_path
from .metadata import MetadataStore, slugify
from .piaotian import PiaotianScraper

SCRAPERS: dict[str, Type[BaseScraper]] = {
    "biquge": BiqugeScraper,
    "piaotian": PiaotianScraper,
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="scrapers", description="本地语料采集 CLI")
    parser.add_argument("-v", "--verbose", action="store_true")
    sub = parser.add_subparsers(dest="cmd", required=True)

    scrape = sub.add_parser("scrape", help="抓取一本书")
    scrape.add_argument("site", choices=sorted(SCRAPERS.keys()))
    scrape.add_argument("--url", required=True, help="书目页 URL（含章节列表）")
    scrape.add_argument("--max", type=int, default=None, help="最多抓多少章（省略=全本）")
    scrape.add_argument("--start", type=int, default=1, help="从第几章开始（默认 1）")
    scrape.add_argument("--delay", type=float, default=None, help="覆盖请求间隔秒数")
    scrape.add_argument("--genre", default="", help="类型标记，如 玄幻")
    scrape.add_argument("--tags", default="", help="逗号分隔标签")

    sub.add_parser("list", help="列出已入库的书")

    remove = sub.add_parser("remove", help="从 metadata 移除一本书（不删文件）")
    remove.add_argument("title_or_slug")

    ingest = sub.add_parser("ingest", help="吃一份 so-novel 的 TXT 输出并入库")
    ingest.add_argument("path", help="so-novel 输出的 TXT 文件或章节目录")
    ingest.add_argument("--genre", default="", help="类型标记")
    ingest.add_argument("--tags", default="", help="逗号分隔标签")
    ingest.add_argument("--overwrite", action="store_true", help="覆盖已存在的章节文件")

    return parser


def cmd_scrape(args: argparse.Namespace) -> int:
    cls = SCRAPERS[args.site]
    kwargs: dict = {}
    if args.delay is not None:
        kwargs["delay_seconds"] = args.delay
    scraper = cls(**kwargs)

    tags = [t.strip() for t in args.tags.split(",") if t.strip()]

    progress_bar: tqdm | None = None

    def on_progress(index: int, total: int, title: str) -> None:
        nonlocal progress_bar
        if progress_bar is None:
            progress_bar = tqdm(total=total, unit="章")
        progress_bar.n = index
        progress_bar.set_description(title[:20])
        progress_bar.refresh()

    try:
        record = scraper.scrape_book(
            args.url,
            max_chapters=args.max,
            start_chapter=args.start,
            on_progress=on_progress,
            genre=args.genre,
            tags=tags,
        )
    finally:
        if progress_bar is not None:
            progress_bar.close()

    print(f"已入库：{record.title} · {record.author}")
    print(f"  章节总数：{record.total_chapters}")
    print(f"  已抓章节：{record.scraped_chapters}")
    print(f"  总字数  ：{record.total_words}")
    return 0


def cmd_list(_: argparse.Namespace) -> int:
    store = MetadataStore()
    books = store.list_books()
    if not books:
        print("（语料库为空）")
        return 0
    for b in books:
        print(
            f"- {b.title} · {b.author or '未知'} "
            f"[{b.source}] {b.scraped_chapters}/{b.total_chapters}章 "
            f"{b.total_words} 字"
        )
    return 0


def cmd_ingest(args: argparse.Namespace) -> int:
    from pathlib import Path

    tags = [t.strip() for t in args.tags.split(",") if t.strip()]
    result = ingest_path(
        Path(args.path),
        genre=args.genre,
        tags=tags,
        overwrite=args.overwrite,
    )
    print(f"已入库：{result.title} · {result.author or '未知作者'}")
    print(f"  slug       ：{result.slug}")
    print(f"  新增章节数  ：{result.chapters_written}")
    print(f"  总字数累计  ：{result.total_words}")
    return 0


def cmd_remove(args: argparse.Namespace) -> int:
    store = MetadataStore()
    slug = args.title_or_slug
    if not store.get(slug):
        slug = slugify(args.title_or_slug)
    if store.remove(slug):
        print(f"已从 metadata 移除：{slug}")
        return 0
    print(f"未找到：{args.title_or_slug}", file=sys.stderr)
    return 1


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    if args.cmd == "scrape":
        return cmd_scrape(args)
    if args.cmd == "list":
        return cmd_list(args)
    if args.cmd == "ingest":
        return cmd_ingest(args)
    if args.cmd == "remove":
        return cmd_remove(args)
    parser.print_help()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
