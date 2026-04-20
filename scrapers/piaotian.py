"""飘天文学（ptwxz / piaotian）适配器。

典型结构：
- 书目页：`https://www.ptwxz.com/bookinfo/<cat>/<id>.html`
  - <h1> 书名；<table> 含作者
  - 目录入口通常在"开始阅读"按钮，指向 `/html/<cat>/<id>/`
- 目录页：`https://www.ptwxz.com/html/<cat>/<id>/`
  - `<div class="centent"> <ul> <li> <a>` 列章节
- 章节页：内容在正文 body，段落间有 `<br>`，没有明确容器
  - 通常以 "上一页" / "下一页" 为界，需要手动截取
- 编码：GB2312 / GBK
"""
from __future__ import annotations

import re
from urllib.parse import urljoin

from .base import BaseScraper, BookInfo, ChapterRef, ScraperError


class PiaotianScraper(BaseScraper):
    site_name = "piaotian"
    default_encoding = "gbk"

    def fetch(self, url: str, *, encoding: str | None = None) -> str:  # type: ignore[override]
        return super().fetch(url, encoding=encoding or self.default_encoding)

    def parse_book_info(self, html: str, source_url: str) -> BookInfo:
        soup = self.soup(html)
        title = ""
        author = ""

        h1 = soup.find("h1")
        if h1:
            title = h1.get_text(strip=True)

        # 作者信息通常在第二个 table 中，格式"作    者：XXX"
        text = soup.get_text("\n", strip=True)
        author_match = re.search(r"作\s*者[：:]\s*(\S+)", text)
        if author_match:
            author = author_match.group(1)

        if not title:
            title_tag = soup.find("title")
            if title_tag:
                title = re.split(r"[_\-|]", title_tag.get_text(strip=True))[0].strip()
        if not title:
            raise ScraperError(f"无法解析书名: {source_url}")

        return BookInfo(title=title, author=author, source_url=source_url)

    def parse_chapter_list(self, html: str, source_url: str) -> list[ChapterRef]:
        soup = self.soup(html)
        container = soup.select_one("div.centent") or soup.select_one("div.content") or soup
        anchors = container.select("ul li a") or container.find_all("a")
        chapters: list[ChapterRef] = []
        for i, a in enumerate(anchors, start=1):
            href = a.get("href") or ""
            title = a.get_text(strip=True)
            if not href or not title:
                continue
            if not re.search(r"\.html?$", href):
                continue
            chapters.append(
                ChapterRef(
                    index=i,
                    title=title,
                    url=urljoin(source_url, href),
                )
            )
        return chapters

    def parse_chapter_content(self, html: str, url: str) -> str:
        # 飘天的正文没有标准容器，需要把 <br> 转行然后去掉头尾导航
        # BeautifulSoup 把 <br> 当作换行源
        soup = self.soup(html)
        # 去掉脚本、样式、导航
        for tag in soup(["script", "style", "iframe", "a"]):
            tag.decompose()
        raw = soup.get_text("\n", strip=True)
        lines = [line for line in raw.splitlines() if line.strip()]
        # 取最长的连续内容块
        body = _extract_body(lines)
        if not body:
            raise ScraperError(f"未提取到正文: {url}")
        return "\n".join(body)


def _extract_body(lines: list[str]) -> list[str]:
    """从清洗后的行列表中猜测正文段。

    启发式：跳过开头导航/广告，取长度 > 20 的段落作为正文。"""
    body: list[str] = []
    for line in lines:
        if len(line) < 4:
            continue
        # 常见噪声
        if any(kw in line for kw in ("上一章", "下一章", "加入书签", "返回书目", "章节错误")):
            continue
        body.append(line)
    return body
