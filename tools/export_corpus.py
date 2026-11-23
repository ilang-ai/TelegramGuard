#!/usr/bin/env python3
"""把自学习 spam 硬库导出到仓库 corpus/ —— 不自动跑，每次迭代 bot 发版时手动跑一次，随发版提交。

用法（在 bot 根目录）：
    venv/bin/python tools/export_corpus.py

做的事：
1. 读 data/bot.db 里的 spam_lib / spam_contacts（只取出现 ≥ 2 次的条目，和容灾硬判用的是同一套门槛）
2. 写 corpus/spamlib-antispam-bot-vYYYY.MM.DD.ilang.md（I-Lang v5.0，同 modules/spamlib.export_ilang）
3. corpus/ 里只留最新一份，旧版本在 git 历史里
"""
import asyncio
import os
import sys
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

# config 从环境变量读；手动跑时顺手把 .env 装进来（systemd 跑 bot 时由 EnvironmentFile 负责）
if os.path.exists(".env"):
    for line in open(".env", encoding="utf-8"):
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())

from modules import spamlib  # noqa: E402
from modules.db import close_db  # noqa: E402


async def main():
    corpus = os.path.join(ROOT, "corpus")
    os.makedirs(corpus, exist_ok=True)
    ver = datetime.now(timezone.utc).strftime("%Y.%m.%d")
    path = os.path.join(corpus, "spamlib-antispam-bot-v%s.ilang.md" % ver)
    st = await spamlib.stats()
    out = await spamlib.export_ilang(path)
    for f in os.listdir(corpus):
        if f.startswith("spamlib-") and f.endswith(".ilang.md") and os.path.join(corpus, f) != out:
            os.remove(os.path.join(corpus, f))
    await close_db()
    print("corpus: %s (%d bytes)" % (os.path.relpath(out, ROOT), os.path.getsize(out)))
    print("library: %d entries (%d active), %d contacts (%d active), %d total hits"
          % (st["entries"], st["active"], st["contacts"], st["contacts_active"], st["hits"]))


if __name__ == "__main__":
    asyncio.run(main())
