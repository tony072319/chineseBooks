"""笔趣阁系适配器。

"笔趣阁"不是单一站点，而是一类镜像：xbiquge、biquge5、biquge.info 等。
它们的结构大体相似：
- 书目页：`<div id="info">` 含标题/作者；`<div id="list"> <dl> <dd> <a>章节` 列目录
- 章节页：`<div id="content">` 放正文
因此把主选择器放成可覆盖的参数，遇到个别镜像不同时可以直接覆盖。
"""
from __future__ import annotations

from urllib.parse import urljoin

from .base import BaseScraper, BookInfo, ChapterRef, ScraperError


class BiqugeScraper(BaseScraper):
    site_name = "biquge"

    info_selector = "#info"
    chapter_list_selector = "#list dd a"
    content_selector = "#content"

    def parse_book_info(self, html: str, source_url: str) -> BookInfo:
        soup = self.soup(html)
        info_block = soup.select_one(self.info_selector)
        title = author = ""
        if info_block:
            h1 = info_block.find(["h1", "h2"])
            if h1:
                title = h1.get_text(strip=True)
            # 作者通常在 "作    者：XXX" 或 "作者：XXX"
            text = info_block.get_text("\n", strip=True)
            for line in text.splitlines():
                if "作" in line and "者" in line:
                    author = line.split("：", 1)[-1].strip() if "：" in line else line.split(":", 1)[-1].strip()
                    break
        if not title:
            title_tag = soup.find("title")
            if title_tag:
                title = title_tag.get_text(strip=True).split("_")[0].strip()
        if not title:
            raise ScraperError(f"无法解析书名: {source_url}")
        return BookInfo(title=title, author=author, source_url=source_url)

    def parse_chapter_list(self, html: str, source_url: str) -> list[ChapterRef]:
        soup = self.soup(html)
        anchors = soup.select(self.chapter_list_selector)
        chapters: list[ChapterRef] = []
        for i, a in enumerate(anchors, start=1):
            href = a.get("href") or ""
            if not href:
                continue
            chapters.append(
                ChapterRef(
                    index=i,
                    title=a.get_text(strip=True),
                    url=urljoin(source_url, href),
                )
            )
        return chapters

    def parse_chapter_content(self, html: str, url: str) -> str:
        soup = self.soup(html)
        content = soup.select_one(self.content_selector)
        if content is None:
            raise ScraperError(f"未找到正文容器: {url}")
        # 常见脚本/广告噪声
        for noise in content.select("script, ins, .adsbygoogle"):
            noise.decompose()
        text = content.get_text("\n", strip=True)
        return _clean_paragraphs(text)


def _clean_paragraphs(text: str) -> str:
    seen_empty = False
    lines: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            if not seen_empty:
                lines.append("")
                seen_empty = True
            continue
        seen_empty = False
        lines.append(stripped)
    return "\n".join(lines)
