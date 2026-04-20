"""命令行入口：

    python -m analysis.cli               # 分析全部已入库的书
    python -m analysis.cli --book 斗破苍穹  # 只分析单本
"""
from __future__ import annotations

import argparse
import logging
import sys

from .corpus import REPORTS_DIR, load_all_books, load_book
from .report import analyze_book, run_all, write_book_report, write_summary


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="analysis", description="Phase 3 语料分析")
    p.add_argument("--book", help="只分析一本（传 slug，如 斗破苍穹）")
    p.add_argument("-v", "--verbose", action="store_true")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO,
                        format="%(levelname)s %(message)s")

    if args.book:
        book = load_book(args.book)
        if book is None:
            print(f"没找到书：{args.book}", file=sys.stderr)
            print("已入库：", file=sys.stderr)
            for b in load_all_books():
                print(f"  - {b.slug}", file=sys.stderr)
            return 1
        ba = analyze_book(book)
        if ba is None:
            print(f"{book.slug} 没有章节文件，跳过", file=sys.stderr)
            return 1
        path = write_book_report(ba)
        print(f"✅ {path}")
        return 0

    paths, summary = run_all()
    for p in paths:
        print(f"✅ {p}")
    if summary:
        print(f"📊 {summary}")
    if not paths:
        print("语料库为空，先跑 `python -m scrapers.cli list` 确认", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
