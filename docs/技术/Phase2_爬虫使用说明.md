# Phase 2 · 语料采集管线使用说明

> **合规声明**：本管线仅用于**本地学习分析**。抓取得到的文本不得二次分发、不得提交到任何公共仓库。`corpus/raw/` 已在 `.gitignore` 中排除。

---

## 1 · 能做什么

- 从笔趣阁系 / 飘天文学系镜像抓取小说全文
- 按书名自动建目录、按章节号命名文件
- 礼貌限速（默认每请求 ≥ 2 秒）+ 自动重试 + 编码识别
- 元数据落在 `corpus/metadata.json`，断点续抓

## 2 · 安装

```bash
cd /home/user/chineseBooks
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## 3 · 用法

### 3.1 抓一本书（笔趣阁）

```bash
python -m scrapers.cli scrape biquge \
    --url https://www.xbiquge.la/10/10489/ \
    --max 30 \
    --genre 玄幻 \
    --tags 升级流,复仇
```

参数：
- `--url` 书目页（含章节列表那一页）
- `--max` 抓多少章（省略=全本，新人先抓 30-50 章即可）
- `--start` 从第几章开始（默认 1）
- `--delay` 覆盖请求间隔（默认 2 秒，**不要调低**）
- `--genre` 类型标记（玄幻/修真/都市/…）
- `--tags` 逗号分隔（升级流,签到流）

### 3.2 抓飘天文学

```bash
python -m scrapers.cli scrape piaotian \
    --url https://www.ptwxz.com/html/5/5555/ \
    --max 30 \
    --genre 仙侠
```

### 3.3 查看已入库书目

```bash
python -m scrapers.cli list
```

### 3.4 删除一条元数据

```bash
python -m scrapers.cli remove 斗破苍穹
```
（仅清 metadata，不删 `corpus/raw/` 下的文件。）

## 4 · 目录约定

```
corpus/
├── metadata.json            # 已入库书目（提交到 git，无正文）
└── raw/                     # ⛔ gitignored，本地学习用
    └── {书名}/
        ├── 0001_第一章 陨落的天才.txt
        ├── 0002_第二章 斗之气三段.txt
        └── ...
```

每个章节文件以 Markdown 风格保存：
```
# 第一章 陨落的天才

正文段落...
```

## 5 · 镜像地址说明

**笔趣阁**不是单一站点，而是一堆镜像，常见：
- `www.xbiquge.la`（较稳定）
- `www.biquge5.com`
- `www.biquge.info`
- `www.biqu520.net`

**飘天文学**常见：
- `www.ptwxz.com`
- `www.piaotian.com`

**镜像常失效**，遇到抓不到的：
1. 先用浏览器打开 URL 确认还活着
2. 用 curl 看 HTTP 状态（403/404 说明站点变了）
3. 换一个镜像试试
4. 如果选择器失效（解析不到书名或章节），可以直接覆盖 `BiqugeScraper.chapter_list_selector` 等属性

## 6 · 自定义镜像选择器

大多数笔趣阁镜像的结构相同，但偶有个例：

```python
from scrapers.biquge import BiqugeScraper

class MyMirrorScraper(BiqugeScraper):
    info_selector = ".book-info"
    chapter_list_selector = ".chapter-list li a"
    content_selector = ".read-content"
```

## 7 · 运行测试

```bash
pytest tests/ -v
```

目前包含：
- `test_metadata.py`：MetadataStore 增删查改
- `test_parsers.py`：HTML 选择器健壮性（纯离线）
- `test_base.py`：抓取流程、断点续抓、字数统计

## 8 · 礼貌爬取原则（硬约束）

- ❌ **不要**把 `--delay` 调到 1 秒以下
- ❌ **不要**并发抓多本（当前管线也不支持）
- ❌ **不要**上 proxy 池绕过对方限速
- ✅ 遇到 403/429 **立刻停手**，换个时间段
- ✅ 抓 30-50 章够做分析，不要整本拉

## 9 · 下一步

进入 **Phase 3** 前需要先用本管线抓 **30 本语料**（每本 30-50 章就好）。
语料就位后，Phase 3 会在 `analysis/` 下写：
- `structure.py`：章节字数、章节数分布
- `opening.py`：黄金三章自动识别
- `tropes.py`：套路关键词识别
- `reports/{书名}.md`：逐本分析报告
