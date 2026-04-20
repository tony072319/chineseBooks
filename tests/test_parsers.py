"""笔趣阁 / 飘天文学 HTML 解析器单元测试（不走网络）。

用固定的 HTML 片段喂给 parse_* 方法，验证选择器与清洗逻辑。
"""
from __future__ import annotations

from scrapers.biquge import BiqugeScraper
from scrapers.piaotian import PiaotianScraper


BIQUGE_INDEX_HTML = """
<html><head><title>斗破苍穹_天蚕土豆_笔趣阁</title></head>
<body>
  <div id="info">
    <h1>斗破苍穹</h1>
    <p>作    者：天蚕土豆</p>
    <p>类    别：玄幻</p>
  </div>
  <div id="list">
    <dl>
      <dt>《斗破苍穹》正文</dt>
      <dd><a href="/10/10489/0001.html">第一章 陨落的天才</a></dd>
      <dd><a href="/10/10489/0002.html">第二章 斗之气三段</a></dd>
      <dd><a href="/10/10489/0003.html">第三章 客人</a></dd>
    </dl>
  </div>
</body></html>
"""

BIQUGE_CHAPTER_HTML = """
<html><body>
<div id="content">
  <p>萧炎，斗之气三段。</p>
  <p>测试长老淡漠的宣布在测试厅中回荡。</p>

  <script>var ad = 1;</script>
  <ins class="adsbygoogle"></ins>
  <p>周围哗然。</p>
</div>
</body></html>
"""


def test_biquge_parse_book_info():
    s = BiqugeScraper()
    info = s.parse_book_info(BIQUGE_INDEX_HTML, "https://example.com/10/10489/")
    assert info.title == "斗破苍穹"
    assert info.author == "天蚕土豆"
    assert info.source_url == "https://example.com/10/10489/"


def test_biquge_parse_chapter_list():
    s = BiqugeScraper()
    chapters = s.parse_chapter_list(BIQUGE_INDEX_HTML, "https://example.com/10/10489/")
    assert len(chapters) == 3
    assert chapters[0].index == 1
    assert chapters[0].title == "第一章 陨落的天才"
    assert chapters[0].url == "https://example.com/10/10489/0001.html"


def test_biquge_parse_chapter_content_strips_ads():
    s = BiqugeScraper()
    text = s.parse_chapter_content(BIQUGE_CHAPTER_HTML, "http://x")
    assert "斗之气三段" in text
    assert "var ad" not in text
    assert "adsbygoogle" not in text


PIAOTIAN_INDEX_HTML = """
<html><head><title>牧神记-宅猪-飘天</title></head>
<body>
  <h1>牧神记</h1>
  <table>
    <tr><td>作    者：宅猪</td></tr>
  </table>
</body></html>
"""

PIAOTIAN_LIST_HTML = """
<html><body>
<div class="centent">
  <ul>
    <li><a href="1.html">第一章 大墟的祖父</a></li>
    <li><a href="2.html">第二章 盲人族长</a></li>
    <li><a href="note">其它</a></li>
  </ul>
</div>
</body></html>
"""

PIAOTIAN_CHAPTER_HTML = """
<html><body>
<div class="title">第一章 大墟的祖父</div>
上一章 下一章 加入书签<br><br>
秦牧小时候父母双亡，被祖父收养。<br>
他从小身体凡庸，不能感应天地元气。<br>
祖父却说这反而是他的造化。<br>
</body></html>
"""


def test_piaotian_parse_book_info():
    s = PiaotianScraper()
    info = s.parse_book_info(PIAOTIAN_INDEX_HTML, "https://example.com/bookinfo/1/1.html")
    assert info.title == "牧神记"
    assert info.author == "宅猪"


def test_piaotian_parse_chapter_list_filters_noise():
    s = PiaotianScraper()
    chapters = s.parse_chapter_list(PIAOTIAN_LIST_HTML, "https://example.com/html/1/1/")
    assert [c.title for c in chapters] == ["第一章 大墟的祖父", "第二章 盲人族长"]
    assert chapters[0].url == "https://example.com/html/1/1/1.html"


def test_piaotian_parse_chapter_drops_navigation():
    s = PiaotianScraper()
    text = s.parse_chapter_content(PIAOTIAN_CHAPTER_HTML, "http://x")
    assert "秦牧" in text
    assert "上一章" not in text
    assert "加入书签" not in text
