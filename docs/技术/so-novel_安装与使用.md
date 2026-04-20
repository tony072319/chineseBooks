# so-novel · 安装与使用

`so-novel` 是第三方 Java 小说下载工具（[github.com/freeok/so-novel](https://github.com/freeok/so-novel)），维护了 12+ 盗版书源的解析规则。**我们用它负责"下载"，我们自己的 `scrapers/ingest.py` 负责"入库"。**

> 合规提醒：下载仅供**本地学习分析**，不做二次分发，不推到 git（`tools/` 和 `downloads/` 已 gitignore）。

---

## 零 · 为什么不是我们自己写爬虫

- 盗版站反爬（UA、IP、Cloudflare、SPA 渲染）每隔几个月都会变
- so-novel 的 `rules/main.json` 由社区维护，**省去我们逆向成本**
- 我们只维护：**TXT → 我们项目格式 + metadata 登记**（见 `scrapers/ingest.py`）

沙箱内 Claude Code 对盗版站域名在**出口防火墙层面屏蔽**（`x-deny-reason: host_not_allowed`），所以
**下载步骤只能在你自己的电脑上跑**，入库步骤可以在任何地方跑。

---

## 一 · 安装

### 方式 A：原生二进制（推荐，无需手动装 Java）

```bash
cd /home/user/chineseBooks
mkdir -p tools && cd tools

# 根据你的系统选一个：
# Linux x64：
curl -LO https://github.com/freeok/so-novel/releases/download/v1.10.1/sonovel-linux_x64.tar.gz
tar -xzf sonovel-linux_x64.tar.gz
mv sonovel-linux_x64 sonovel

# macOS arm64（Apple Silicon）：
# curl -LO https://github.com/freeok/so-novel/releases/download/v1.10.1/sonovel-macos_arm64.tar.gz
# tar -xzf sonovel-macos_arm64.tar.gz && mv sonovel-macos_arm64 sonovel

# Windows：去 https://github.com/freeok/so-novel/releases 下载 .tar.gz
```

解压后 `tools/sonovel/` 大概 200MB（含打包的 JRE）。

### 方式 B：用 Docker（可选）

```bash
docker pull sonovel/sonovel:latest
# 见 so-novel 自己的 README 配置挂载
```

---

## 二 · 配置

编辑 `tools/sonovel/config.ini`，**关键项**：

```ini
[download]
download-path = downloads
extname = txt                      # 必须改成 txt（默认是 epub，对我们没用）
preserve-chapter-cache = 1         # 重要！保留每章独立 TXT，方便 ingest.py 入库

[crawl]
concurrency = 5                    # 不要太高，5 就够
min-interval = 500                 # ≥500ms
max-interval = 1500
enable-retry = 1
max-retries = 3
```

**默认并发是 50，一定要降到 5 以下**，不要把对方站点拖垮。

---

## 三 · 支持的书源（12 个）

so-novel 的 `rules/main.json` 里默认激活这些（以后可能增删）：

| # | 书源 | 域名 | 备注 |
|---|------|------|------|
| 1 | 香书小说 | `www.xbiqugu.la` | 老牌 |
| 2 | 书海阁小说网 | `www.shuhaige.net` | 搜索过快会丢包 |
| 3 | 梦书中文 | `www.mcxs.info` | |
| 4 | 鸟书网 | `www.99xs.info` | |
| 5 | **笔趣阁22** | `www.22biqu.com` | 推荐 |
| 6 | 笔尖中文 | `www.xbiquzw.net` | |
| 7 | 书林文学 | `www.shu009.com` | |
| 8 | 悠久小说网 | `www.ujxsw.org` | |
| 9 | 阅读库 | `www.yeudusk.com` | |
| 10 | 顶点小说 | `www.wxsy.net` | |
| 11 | **笔趣阁365** | `www.biquge365.net` | 推荐 |
| 12 | 燃文小说网 | `www.ranwen8.cc` | |

**注意**：你之前试的 `bqg683.xyz` / `m.bqgl.cc` / `69shuba.com` **不在这 12 个里**，不能直接用。但 `22biqu.com` / `biquge365.net` 基本都收录了主流书籍。

---

## 四 · 下载一本书

### 4.1 交互式（TUI，推荐新手）

```bash
cd tools/sonovel
./run-linux.sh
# 出现菜单 → 输入书名或作者 → 选源 → 下载
```

### 4.2 命令行（自动化）

需要先拿到**书的详情页 URL**（含章节列表那页）。两种找法：
- 直接在浏览器里打开书源网站 → 搜书 → 复制 URL
- 或跑一次 TUI 让它帮你搜到

```bash
cd tools/sonovel
./runtime/bin/java -XX:+UseZGC -Dconfig.file=config.ini \
    -jar app.jar \
    -u https://www.22biqu.com/biqu5689/ \
    -e txt
```

参数：
- `-u` 书的详情页 URL（**不是章节页**）
- `-e txt` 下载成 TXT

下载产物：
```
downloads/
└── 斗破苍穹(天蚕土豆).txt               # 合并版整本
└── txt/斗破苍穹(天蚕土豆)/              # 每章一个文件（preserve-chapter-cache=1 才有）
    ├── 第一章 陨落的天才.txt
    ├── 第二章 斗之气三段.txt
    └── ...
```

---

## 五 · 入库（关键）

用 `scrapers/ingest.py` 把 so-novel 输出扔进我们的 `corpus/raw/` 和 `metadata.json`。

### 5.1 目录模式（推荐，保留章节结构）

```bash
cd /home/user/chineseBooks
source .venv/bin/activate

python -m scrapers.cli ingest \
    tools/sonovel/downloads/txt/"斗破苍穹(天蚕土豆)" \
    --genre 玄幻 \
    --tags 升级流,复仇,黄金三章
```

### 5.2 单文件模式（合并版 TXT）

```bash
python -m scrapers.cli ingest \
    tools/sonovel/downloads/"斗破苍穹(天蚕土豆).txt" \
    --genre 玄幻 \
    --tags 升级流
```

### 5.3 验收

```bash
python -m scrapers.cli list
# → - 斗破苍穹 · 天蚕土豆 [so-novel] 1600/1600章 5300000 字

ls corpus/raw/斗破苍穹/ | head
# → 0001_第一章 陨落的天才.txt
#    0002_第二章 斗之气三段.txt
#    ...

head -15 corpus/raw/斗破苍穹/0001_*.txt
```

---

## 六 · 典型完整流程（斗破苍穹示例）

```bash
# 1. 第一次用时装 so-novel
cd /home/user/chineseBooks/tools
curl -LO https://github.com/freeok/so-novel/releases/download/v1.10.1/sonovel-linux_x64.tar.gz
tar -xzf sonovel-linux_x64.tar.gz && mv sonovel-linux_x64 sonovel
cd sonovel
# 手动编辑 config.ini：extname=txt, preserve-chapter-cache=1, concurrency=5

# 2. 下载斗破苍穹（约 5-15 分钟，1600 章）
./runtime/bin/java -XX:+UseZGC -Dconfig.file=config.ini \
    -jar app.jar -u https://www.22biqu.com/biqu5689/ -e txt

# 3. 入库
cd /home/user/chineseBooks
source .venv/bin/activate
python -m scrapers.cli ingest tools/sonovel/downloads/txt/"斗破苍穹(天蚕土豆)" \
    --genre 玄幻 --tags 升级流,复仇

python -m scrapers.cli list
```

---

## 七 · 排错

| 现象 | 原因 | 解决 |
|------|------|------|
| `找不到 bookUrl 为 XX 的规则` | 域名不在 `rules/main.json` 里 | 换一个上表 12 个之一的源 |
| `Host not in allowlist` | 该站点拒绝你的 IP | 换另一个源 |
| `Connection refused` / 超时 | 镜像挂了或在修 | 等半小时 or 换源 |
| SSL/PKIX 错误 | so-novel 打包 JDK 的根证书有问题 | 用系统 java：`java -jar app.jar ...` 而非 `./runtime/bin/java` |
| `找不到 bookUrl`（URL 明明在列表里） | 书源要求**带/不带** `www.` / 尾斜杠 | 严格按 `main.json` 里的 `url` 格式（可以 `cat rules/main.json`） |
| Cloudflare 挡住 | 部分源需要 CF 绕过 | 看 so-novel README 配 `cf-bypass` 或换源 |
| `下载路径 = downloads` 找不到文件 | 相对路径基于**运行目录** | 一定要 `cd tools/sonovel` 再跑 |
| ingest 时"未解析出任何章节" | TXT 里的章节标题不标准 | 手动看一眼 TXT，确认标题形如"第X章 ..."；不是就改文件头 |

---

## 八 · Phase 3 前的工作量估计

建议先抓 **10 本精读级 + 20 本扫读级 = 30 本** 就够 Phase 3 起步。每本只抓**前 30-50 章**就够做结构分析。

30 本 × 50 章 × 2 秒/章 ≈ 50 分钟（所有礼貌限速）。

下载完成后：
```bash
for dir in tools/sonovel/downloads/txt/*/; do
    python -m scrapers.cli ingest "$dir" --genre 玄幻
done
python -m scrapers.cli list
```

Phase 3（`analysis/` 脚本）会直接读 `corpus/raw/` 出数据报告，我们 Phase 3 再动手。
