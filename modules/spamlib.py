"""自学习 spam 硬库 —— 只做收敛。

2026-11-23 机主定的算法（原话要点）：「每次判定有新的就落库，最简化的方法落库；容灾硬判；每周凌晨 3 点
自动维护库，删除重复、多余的；一个自我学习的事情；两个 bot 都上；库公开，每周在 GitHub 发版一次，
做成 I-Lang 格式，让 AI 也学会。」

四个入口：
- learn(text)            AI 判为 spam 时调用。归一化 → sha1 做主键，UPSERT（count+1，last_seen）。
                         重复条目在结构上就不存在。顺手把联系方式（t.me 链接、@号、微信号、QQ、手机号）抽进 spam_contacts。
- hard_judge(text)       AI 不可用 / 答案解析不出来时调用。全本地、零费用：
                         联系方式命中 → spam；归一化哈希命中 → spam；字符三元组 Jaccard ≥ 0.85 → spam。
                         只认见过 ≥ 2 次的条目：AI 偶尔误判，见一次的只进库不生效。
- weekly_maintain()      每周日 03:00（北京时间）由 JobQueue 调：删 90 天没再见且 count=1 的条目，VACUUM，
                         然后导出 I-Lang 文件到 data/spamlib/ 供每周公开发版。
- export_ilang(path)     生成 I-Lang v5.0 文件（只含 count ≥ 2 的条目）。

库只在容灾时用，平时判定链不变；只学 spam，不学正常消息。
"""
import hashlib
import logging
import os
import re
import time
from datetime import datetime, timezone

import config
from modules.db import db_exec

try:
    from modules import lexicon as _lex
except Exception:  # pragma: no cover
    _lex = None

logger = logging.getLogger(__name__)

MIN_COUNT = int(getattr(config, "SPAMLIB_MIN_COUNT", 2))
SIM_THRESHOLD = float(getattr(config, "SPAMLIB_SIM_THRESHOLD", 0.85))
STALE_DAYS = int(getattr(config, "SPAMLIB_STALE_DAYS", 90))
MIN_LEN = 8            # 归一化后不足 8 个字符的文本不入库（"你好""谢谢"这种没有判定价值）
CACHE_TTL = 600        # 硬判用的内存缓存 10 分钟刷新一次
KEEP_EXPORTS = 8       # data/spamlib/ 里最多留 8 份导出
BOT_NAME = getattr(config, "SPAMLIB_BOT_NAME", "antispam.bot")
# 自己的 bot 用户名不能当联系方式学进去（群里 @ 它是正常行为）
EXCLUDE_TOKENS = {t.lower() for t in getattr(config, "SPAMLIB_EXCLUDE_TOKENS", ("@ilangguardbot", "@shadowrocketaibot"))}

_CONTACT_RES = [
    re.compile(r"t\.me/[a-z0-9_+]{3,}"),
    re.compile(r"(?<![a-z0-9_])@[a-z][a-z0-9_]{4,31}"),
    # 微信号：各种写法 + 可选的「号」和分隔符；裸的 v/q 必须带冒号（"v:abc_88"），免得吃掉英文里的 v
    re.compile(r"(?:vx|wx|v信|微信|薇信|威信|weixin|wechat|v[:：]|q[:：])[号:：\s]*([a-z][a-z0-9_-]{4,19})"),
    re.compile(r"(?:qq|扣扣)[号:：\s]*(\d{5,11})"),
    re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)"),
]
_WS = re.compile(r"\s+")
_cache = {"t": 0.0, "entries": [], "contacts": set()}
_tables_ready = False


# ---------------------------------------------------------------- 基础
def normalize(text):
    t = text or ""
    if _lex is not None and hasattr(_lex, "normalize"):
        try:
            t = _lex.normalize(t)
        except Exception:
            pass
    t = t.lower()
    return _WS.sub(" ", t).strip()


def _hash(norm):
    return hashlib.sha1(norm.encode("utf-8")).hexdigest()


def _trigrams(norm):
    s = norm.replace(" ", "")
    return {s[i:i + 3] for i in range(len(s) - 2)} if len(s) >= 3 else {s} if s else set()


def _jaccard(a, b):
    if not a or not b:
        return 0.0
    inter = len(a & b)
    return inter / float(len(a) + len(b) - inter)


def extract_contacts(norm):
    out = set()
    for rx in _CONTACT_RES:
        for m in rx.finditer(norm):
            tok = m.group(1) if m.groups() else m.group(0)
            tok = tok.strip().lower()
            if tok and tok not in EXCLUDE_TOKENS:
                out.add(tok)
    return out


def _now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


async def ensure_tables():
    global _tables_ready
    if _tables_ready:
        return

    async def _do(db):
        await db.execute(
            "CREATE TABLE IF NOT EXISTS spam_lib ("
            " hash TEXT PRIMARY KEY, norm TEXT NOT NULL, count INTEGER NOT NULL DEFAULT 1,"
            " first_seen TEXT, last_seen TEXT)")
        await db.execute(
            "CREATE TABLE IF NOT EXISTS spam_contacts ("
            " token TEXT PRIMARY KEY, count INTEGER NOT NULL DEFAULT 1, first_seen TEXT, last_seen TEXT)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_spam_lib_count ON spam_lib(count)")
        await db.commit()
    await db_exec(_do)
    _tables_ready = True


# ---------------------------------------------------------------- 落库（收敛）
async def learn(text):
    """AI 判为 spam → 入库。返回 (是否新条目, 抽到的联系方式集合)。"""
    norm = normalize(text)
    if len(norm) < MIN_LEN:
        return (False, set())
    await ensure_tables()
    h = _hash(norm)
    now = _now()
    contacts = extract_contacts(norm)

    async def _do(db):
        cur = await db.execute("SELECT count FROM spam_lib WHERE hash=?", (h,))
        row = await cur.fetchone()
        if row:
            await db.execute("UPDATE spam_lib SET count=count+1, last_seen=? WHERE hash=?", (now, h))
            new = False
        else:
            await db.execute("INSERT INTO spam_lib (hash, norm, count, first_seen, last_seen) VALUES (?,?,1,?,?)",
                             (h, norm[:2000], now, now))
            new = True
        for tok in contacts:
            await db.execute(
                "INSERT INTO spam_contacts (token, count, first_seen, last_seen) VALUES (?,1,?,?)"
                " ON CONFLICT(token) DO UPDATE SET count=count+1, last_seen=excluded.last_seen", (tok, now, now))
        await db.commit()
        return new
    try:
        new = await db_exec(_do)
    except Exception as e:
        logger.warning("[spamlib] learn failed: %s", e)
        return (False, set())
    if new:
        _cache["t"] = 0.0  # 让硬判缓存下次刷新
    return (new, contacts)


# ---------------------------------------------------------------- 容灾硬判
async def _load_cache():
    if time.time() - _cache["t"] < CACHE_TTL:
        return
    await ensure_tables()

    async def _do(db):
        cur = await db.execute("SELECT hash, norm FROM spam_lib WHERE count>=?", (MIN_COUNT,))
        rows = await cur.fetchall()
        cur = await db.execute("SELECT token FROM spam_contacts WHERE count>=?", (MIN_COUNT,))
        toks = {r[0] for r in await cur.fetchall()}
        return rows, toks
    try:
        rows, toks = await db_exec(_do)
    except Exception as e:
        logger.warning("[spamlib] cache load failed: %s", e)
        return
    _cache["entries"] = [(h, n, _trigrams(n)) for h, n in rows]
    _cache["contacts"] = toks
    _cache["t"] = time.time()


async def hard_judge(text):
    """返回 True(spam) / False(没命中)。只用本地库，不调任何接口。"""
    norm = normalize(text)
    if len(norm) < MIN_LEN:
        return False
    await _load_cache()
    for tok in extract_contacts(norm):
        if tok in _cache["contacts"]:
            logger.info("[spamlib] hard hit: contact %s", tok)
            return True
    # 库里已知的联系方式只要出现在文本里就算（不要求这次也带「微信」前缀）：spam 号换个说法照样抓
    for tok in _cache["contacts"]:
        if len(tok) >= 6 and tok in norm:
            logger.info("[spamlib] hard hit: known contact %s", tok)
            return True
    h = _hash(norm)
    tg = _trigrams(norm)
    n_len = len(norm)
    for eh, en, etg in _cache["entries"]:
        if eh == h:
            logger.info("[spamlib] hard hit: exact")
            return True
        # 长度差一半以上的不用算相似度
        if not (n_len * 0.5 <= len(en) <= n_len * 2.0):
            continue
        sim = _jaccard(tg, etg)
        if sim >= SIM_THRESHOLD:
            logger.info("[spamlib] hard hit: similar %.2f", sim)
            return True
    return False


# ---------------------------------------------------------------- 每周维护 + 导出
async def stats():
    await ensure_tables()

    async def _do(db):
        cur = await db.execute("SELECT COUNT(*), COALESCE(SUM(count),0), SUM(CASE WHEN count>=? THEN 1 ELSE 0 END) FROM spam_lib", (MIN_COUNT,))
        a = await cur.fetchone()
        cur = await db.execute("SELECT COUNT(*), SUM(CASE WHEN count>=? THEN 1 ELSE 0 END) FROM spam_contacts", (MIN_COUNT,))
        b = await cur.fetchone()
        return {"entries": a[0], "hits": a[1], "active": a[2] or 0, "contacts": b[0], "contacts_active": b[1] or 0}
    return await db_exec(_do)


async def weekly_maintain():
    await ensure_tables()
    cutoff = datetime.now(timezone.utc)
    cutoff_s = (cutoff.replace(microsecond=0)).strftime("%Y-%m-%d %H:%M:%S")

    async def _do(db):
        cur = await db.execute(
            "DELETE FROM spam_lib WHERE count<? AND last_seen < datetime(?, ?)",
            (MIN_COUNT, cutoff_s, "-%d days" % STALE_DAYS))
        n1 = cur.rowcount
        cur = await db.execute(
            "DELETE FROM spam_contacts WHERE count<? AND last_seen < datetime(?, ?)",
            (MIN_COUNT, cutoff_s, "-%d days" % STALE_DAYS))
        n2 = cur.rowcount
        await db.commit()
        await db.execute("VACUUM")
        return n1, n2
    n1, n2 = await db_exec(_do)
    _cache["t"] = 0.0
    st = await stats()
    path = await export_ilang()
    logger.info("[spamlib] weekly: pruned %d entries + %d contacts; now %d entries (%d active), %d contacts (%d active); exported %s",
                n1, n2, st["entries"], st["active"], st["contacts"], st["contacts_active"], path)
    return {"pruned": n1 + n2, "stats": st, "export": path}


def _export_dir():
    d = os.path.join(os.path.dirname(os.path.abspath(getattr(config, "DB_PATH", "data/bot.db"))), "spamlib")
    os.makedirs(d, exist_ok=True)
    return d


def _esc(s):
    # I-Lang 的 T: 行是单行，换行和竖线换掉
    return s.replace("\n", " ").replace("|", "¦")


async def export_ilang(path=None):
    """导出 I-Lang v5.0 文件：只含 count ≥ MIN_COUNT 的条目。文件名带版号（日期）。"""
    await ensure_tables()

    async def _do(db):
        cur = await db.execute("SELECT norm, count, first_seen, last_seen FROM spam_lib WHERE count>=? ORDER BY count DESC, last_seen DESC", (MIN_COUNT,))
        rows = await cur.fetchall()
        cur = await db.execute("SELECT token, count, last_seen FROM spam_contacts WHERE count>=? ORDER BY count DESC", (MIN_COUNT,))
        toks = await cur.fetchall()
        return rows, toks
    rows, toks = await db_exec(_do)
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    ver = datetime.now(timezone.utc).strftime("%Y.%m.%d")
    if path is None:
        path = os.path.join(_export_dir(), "spamlib-%s-v%s.ilang.md" % (BOT_NAME.replace(".", "-"), ver))
    L = []
    L.append("::ILANG::v5.0::RULES")
    L.append("[TYPE:spam_library]")
    L.append("[ID:SPAMLIB-%s-%s]" % (BOT_NAME.upper().replace(".", "-"), today.replace("-", "")))
    L.append("[DATE:%s]" % today)
    L.append("[OWNER:%s]" % BOT_NAME)
    L.append("[SCOPE:TELEGRAM_GROUP_SPAM]")
    L.append("[LANG:zh]")
    L.append("[VERSION:%s]" % ver)
    L.append("")
    L.append("::FACT{source|conf:confirmed}")
    L.append("  T:本库由 %s 在 Telegram 群里的 AI 判定自动收敛而来，不经人工编辑" % BOT_NAME)
    L.append("  T:只收 AI 判为 spam 且独立出现 ≥ %d 次的归一化文本和联系方式；不含任何正常消息" % MIN_COUNT)
    L.append("  T:归一化＝全角转半角、去零宽字符、同形字还原、转小写、空白折叠")
    L.append("  T:%d 天没再出现且只见过一次的条目每周日自动清掉；本文件每周生成一次" % STALE_DAYS)
    L.append("  T:条目格式 文本 ¦ count=出现次数 ¦ first=首次 ¦ last=最近（UTC）")
    L.append("")
    L.append("::RULE{hard_judge|conf:confirmed}")
    L.append("  T:联系方式命中本库 contacts 任一条 ⇒ spam")
    L.append("  T:归一化文本与本库 patterns 任一条完全相同 ⇒ spam")
    L.append("  T:归一化文本与本库 patterns 任一条的字符三元组 Jaccard 相似度 ≥ %.2f ⇒ spam" % SIM_THRESHOLD)
    L.append("  T:以上全不命中 ⇒ 不由本库判定，交给下一层")
    L.append("  T:本库是 AI 判定不可用时的容灾层，不替代 AI 判定")
    L.append("")
    L.append("::FACT{contacts|conf:confirmed}")
    if toks:
        for tok, c, last in toks:
            L.append("  T:%s ¦ count=%d ¦ last=%s" % (_esc(tok), c, (last or "")[:10]))
    else:
        L.append("  T:（空）")
    L.append("")
    L.append("::FACT{patterns|conf:confirmed}")
    if rows:
        for norm, c, first, last in rows:
            L.append("  T:%s ¦ count=%d ¦ first=%s ¦ last=%s" % (_esc(norm[:300]), c, (first or "")[:10], (last or "")[:10]))
    else:
        L.append("  T:（空）")
    L.append("")
    L.append("::ILANG::COMPLETE::")
    L.append("")
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write("\n".join(L))
    os.replace(tmp, path)
    # 只留最近 KEEP_EXPORTS 份
    d = os.path.dirname(path)
    olds = sorted(f for f in os.listdir(d) if f.startswith("spamlib-") and f.endswith(".ilang.md"))
    for f in olds[:-KEEP_EXPORTS]:
        try:
            os.remove(os.path.join(d, f))
        except Exception:
            pass
    return path


async def weekly_job(context=None):
    """给 PTB JobQueue 的入口。"""
    try:
        await weekly_maintain()
    except Exception as e:
        logger.warning("[spamlib] weekly job failed: %s", e)
