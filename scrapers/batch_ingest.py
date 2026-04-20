"""批量入库：把仓库根目录下所有上传的 TXT 按预设的 (类型, 标签) 映射跑 ingest。

用法：
    .venv/bin/python -m scrapers.batch_ingest

约定：
- 跑完后不动原 TXT。清理（git rm + 物理删）由 shell 层面做。
- BOOK_META 里没覆盖到的书会以空类型入库，之后可人工补 metadata.json。
"""
from __future__ import annotations

from pathlib import Path

from .config import PROJECT_ROOT
from .ingest import ingest_path

# 类型 + 标签预设。不求一步到位，后续可以手动微调 corpus/metadata.json。
BOOK_META: dict[str, tuple[str, list[str]]] = {
    "斗破苍穹":             ("玄幻", ["升级流", "复仇", "黄金三章", "炼药", "天蚕土豆"]),
    "全职高手":             ("游戏", ["电竞", "职业联赛", "团队", "蝴蝶蓝"]),
    "凡人修仙传":           ("修真", ["凡人流", "仙侠", "忘语"]),
    "盗墓笔记":             ("悬疑", ["盗墓", "冒险", "南派三叔"]),
    "剑来":                 ("仙侠", ["东方仙侠", "成长向", "烽火戏诸侯"]),
    "吞噬星空":             ("玄幻", ["升级流", "洪荒", "星际", "我吃西红柿"]),
    "一念永恒":             ("仙侠", ["仙侠", "耳根"]),
    "武动乾坤":             ("玄幻", ["升级流", "天蚕土豆"]),
    "大主宰":               ("玄幻", ["升级流", "天蚕土豆"]),
    "斗罗大陆Ⅱ绝世唐门":   ("玄幻", ["升级流", "斗罗", "唐家三少"]),
    "圣墟":                 ("玄幻", ["末世复苏", "洪荒", "辰东"]),
    "全球高武":             ("玄幻", ["都市异能", "系统流", "老鹰吃小鸡"]),
    "大王饶命":             ("都市", ["系统流", "搞笑", "会说话的肘子"]),
    "修真聊天群":           ("修真", ["都市修真", "群聊流", "圣骑士的传说"]),
    "天道图书馆":           ("玄幻", ["系统流", "签到", "横扫天涯"]),
    "万界之最强商人":       ("玄幻", ["诸天流", "商战"]),
    "赘婿":                 ("历史", ["架空", "商战", "愤怒的香蕉"]),
    "十日终焉":             ("无限流", ["悬疑", "脑洞", "国风", "杀虫队队员"]),
    "诡秘之主":             ("克苏鲁", ["神秘学", "蒸汽朋克", "爱潜水的乌贼"]),
    "牧神记":               ("仙侠", ["东方神话", "道教", "宅猪"]),
    "遮天":                 ("玄幻", ["洪荒", "世界观", "辰东"]),
}


def batch_ingest(root: Path | None = None) -> list[tuple[str, str]]:
    root = root or PROJECT_ROOT
    results: list[tuple[str, str]] = []
    for txt in sorted(root.glob("*.txt")):
        if txt.name == "requirements.txt":
            continue
        stem = txt.stem
        genre, tags = BOOK_META.get(stem, ("", []))
        try:
            result = ingest_path(txt, genre=genre, tags=tags)
            status = f"✅ {result.chapters_written:>4} 章 / {result.total_words:>8} 字"
        except Exception as exc:  # noqa: BLE001
            status = f"❌ {type(exc).__name__}: {exc}"
        print(f"  {stem:<25} {status}")
        results.append((stem, status))
    return results


if __name__ == "__main__":
    batch_ingest()
