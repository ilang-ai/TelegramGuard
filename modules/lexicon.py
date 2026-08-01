"""
Chinese slang / evasion lexicon layer.

General-purpose models do not recognise livestream-style slang like 收米 / 上车 /
日结, so this layer scores it with a plain word table. Three steps:

1. normalize() folds the text — fullwidth to halfwidth, zero-width characters
   stripped, homoglyphs restored (Cyrillic / Greek / lookalike Han characters),
   traditional to simplified, lowercased.
2. strip_separators() additionally removes in-word separators, which breaks the
   "split the word up" trick (叚*币 / 假-币 / 假 币).
3. score() matches the table on all three tracks and adds two bonuses:
   - combo bonus: a money/scam term AND a contact-evasion term in one message
   - evasion bonus: the term only matches AFTER normalizing / de-separating

Usage (called before the judge in bot.py):
    s, terms = lexicon.score(text)
    if s >= config.LEXICON_HARD_THRESHOLD:   # hard hit — spam, no AI call needed
        ...
    else:                                     # soft hit — feed terms to the AI
        ...

The table is extensible through config.LEXICON_EXTRA, so an operator can add
terms without touching code.

Why the evasion bonus exists
----------------------------
**Deliberate obfuscation is itself evidence of intent.** Somebody discussing or
complaining about counterfeit money has no reason to write 假 as 叚. Making that
substitution means the sender knows the word gets blocked — which is an
admission that what they are posting is the thing that gets blocked.

So the same word carries a completely different risk depending on how it was
written:
    "假币"    → could be news, a complaint, a question → weight 4, under the
                hard threshold, goes to the AI for context
    "叚*币"   → 4 + evasion bonus 3 = 7 → over the threshold, deleted at once

This does not depend on enumerating every lookalike character: swap in any rare
character or insert any separator and, as long as the folded text spells the
term, the bonus applies automatically.
"""

import re
import unicodedata

import config

# Zero-width / directional control characters (spam inserts these mid-word to
# break keyword matching).
_ZERO_WIDTH = dict.fromkeys(
    map(ord, "​‌‍‎‏‪‫‬⁠﻿"), None
)

# Common homoglyphs: Cyrillic / Greek → Latin (letters disguised as English).
_HOMOGLYPH = {
    "а": "a", "е": "e", "о": "o", "р": "p", "с": "c", "х": "x", "у": "y",
    "ѕ": "s", "і": "i", "ј": "j", "к": "k", "н": "h", "в": "b", "м": "m", "т": "t",
    "ο": "o", "ρ": "p", "α": "a", "ν": "v", "τ": "t", "ϲ": "c",
}

# Lookalike Han characters / traditional / Japanese shinjitai → simplified.
# NFKC does **nothing** for these: it handles fullwidth and compatibility forms,
# not distinct characters that merely look alike, and it does no traditional →
# simplified conversion. 叚 (U+53DA) and 假 (U+5047) are two separate characters.
_CJK_HOMOGLYPH = {
    # Lookalike substitutions actually observed in spam
    "叚": "假", "仮": "假", "葭": "假",
    "帀": "币", "巿": "币",
    # Traditional / variant → simplified (outside NFKC's remit)
    "幣": "币", "鈔": "钞", "偽": "伪", "僞": "伪", "貨": "货", "錢": "钱",
    "髙": "高", "證": "证", "護": "护",
    "銀": "银", "帳": "账", "號": "号", "軟": "软", "體": "体",
    "電": "电", "報": "报", "聯": "联", "係": "系", "繫": "系",
    "點": "点", "擊": "击", "賣": "卖", "買": "买", "貸": "贷",
}

# Characters commonly pushed into the middle of a word as separators (the * in
# 叚*币). Stripping zero-width characters is not enough — these are visible
# characters and NFKC leaves them alone.
_SEPARATORS = re.compile(r"[\*\-_\.·・~｜|/\\\s、，,。:：;；'\"“”‘’()（）\[\]【】<>《》!！?？#＃]+")


def normalize(text):
    """Fullwidth → halfwidth, drop zero-width, restore homoglyphs, lowercase."""
    if not text:
        return ""
    t = unicodedata.normalize("NFKC", text)              # fullwidth → halfwidth
    t = t.translate(_ZERO_WIDTH)                          # drop zero-width/marks
    t = "".join(_HOMOGLYPH.get(ch, ch) for ch in t)      # Cyrillic/Greek → Latin
    t = "".join(_CJK_HOMOGLYPH.get(ch, ch) for ch in t)  # lookalike Han → simplified
    return t.lower()


def strip_separators(text):
    """Remove in-word separators, defeating 叚*币 / 假-币 / 假 币 style splitting.

    This crosses legitimate punctuation boundaries ("美国。币安" → "美国币安"), so
    it is used **only as an auxiliary match track and every hit on it carries the
    evasion bonus** — it is never a verdict on its own.
    """
    return _SEPARATORS.sub("", text or "")


# Table: term -> (meaning, weight, category)
# Categories: money=earning/recruiting  contact=contact-detail evasion
#             pay=payment/crypto  scam=fraud scheme
#             fake=counterfeit currency/documents (serious, and the ad format is
#                  "the account itself is the contact detail")
# Higher weight = more suspicious. A single term is usually not enough to call
# something spam on its own (see LEXICON_HARD_THRESHOLD) — combinations and the
# threshold keep false positives down (收米, for example, is an ordinary word in a
# livestream-tipping context).
SLANG = {
    # ---- Earning / recruiting ----
    "收米": ("收钱", 3, "money"),
    "上车": ("入局/加入项目", 2, "money"),
    "车头": ("项目发起人", 2, "money"),
    "带单": ("带人下注/投资", 3, "money"),
    "日结": ("日结工资(刷单诈骗常见)", 2, "money"),
    "日入": ("日收入(夸张收益诱导)", 2, "money"),
    "刷单": ("刷单兼职诈骗", 3, "money"),
    "兼职": ("兼职引流", 1, "money"),
    "口子": ("放贷/诈骗渠道", 3, "money"),
    "洗码": ("赌场洗码", 3, "money"),
    "跑分": ("跑分洗钱", 3, "money"),
    "卡商": ("贩卖银行卡/账号", 3, "money"),
    "杀猪盘": ("杀猪盘诈骗", 3, "scam"),
    "反水": ("赌博返利", 3, "money"),
    "包赢": ("赌博诱导", 3, "scam"),
    "稳赚": ("虚假收益", 2, "scam"),
    "躺赚": ("虚假收益", 2, "scam"),
    "内部消息": ("荐股诈骗", 2, "scam"),
    "带你飞": ("带单诱导", 2, "money"),
    # ---- Counterfeit currency ----
    # Serious offence, but the plain spelling gets weight 4 (under the hard
    # threshold) so context still goes to the AI; obfuscated it picks up the
    # evasion bonus and hard-hits on its own.
    # Note 冥币 (joss paper, a funeral good) is deliberately NOT in this table.
    "假币": ("伪造货币", 4, "fake"),
    "假钞": ("伪造钞票", 4, "fake"),
    "伪钞": ("伪造钞票", 4, "fake"),
    "假钱": ("伪造货币", 3, "fake"),
    # These are pure trade jargon — they do not turn up in ordinary conversation,
    # so one occurrence is enough. Weight 6 clears the threshold by itself.
    "高仿钞": ("高仿伪钞", 6, "fake"),
    "仿真钞": ("仿真伪钞", 6, "fake"),
    "1:1真钞": ("伪钞话术", 6, "fake"),
    # 练功券 is a bank note-counting practice pad — a legal product — so it only
    # gets 4 and the AI decides from context.
    "练功券": ("点钞练习券(常被用作伪钞幌子)", 4, "fake"),
    # ---- Contact-detail evasion ----
    "薇": ("微信", 2, "contact"),
    "威": ("微信", 2, "contact"),
    "维": ("微信", 2, "contact"),
    "魏": ("微信", 2, "contact"),
    "vx": ("微信", 2, "contact"),
    "vxin": ("微信", 2, "contact"),
    "威信": ("微信", 2, "contact"),
    "扣扣": ("QQ", 2, "contact"),
    "企鹅": ("QQ", 2, "contact"),
    "扣v": ("加QQ/微信", 2, "contact"),
    "纸飞机": ("Telegram", 2, "contact"),
    "电报": ("Telegram", 1, "contact"),
    # A bare 飞机 cannot go in — "我坐飞机去北京" would be a false positive. Only
    # the multi-character forms that unambiguously mean a contact handle.
    "飞机号": ("Telegram 账号", 2, "contact"),
    "联系飞机": ("Telegram 联系", 2, "contact"),
    "飞机搜": ("Telegram 搜索", 2, "contact"),
    "tg号": ("Telegram 账号", 2, "contact"),
    "电报号": ("Telegram 账号", 2, "contact"),
    "蝙蝠": ("BatChat 加密聊天", 2, "contact"),
    "皮皮虾": ("加密聊天软件", 2, "contact"),
    "私我": ("私聊引流", 1, "contact"),
    "详聊": ("私下详谈引流", 1, "contact"),
    "加我": ("引流加好友", 1, "contact"),
    # ---- Payment / crypto ----
    "usdt": ("USDT 加密货币支付", 2, "pay"),
    "泰达": ("USDT", 2, "pay"),
    "承兑": ("加密货币承兑洗钱", 3, "pay"),
    "代收": ("第三方代收款", 2, "pay"),
    "四方": ("四方支付(灰产收款)", 3, "pay"),
}

# Evasion bonus: added when a term only matches after normalizing / removing
# separators. 3 is chosen so a single obfuscated fake-currency term (weight 4)
# clears the default hard threshold of 6, while the same term spelled plainly
# stays at 4 and still goes to the AI.
_EVASION_BONUS = 3


def score(text):
    """Return (total, ['term=meaning', ...]). Each term scores at most once.

    Three match tracks:
      raw    the original text, lowercased only  — direct hit, no bonus
      norm   after normalize()                   — needed folding = evasion
      strip  after normalize() + strip_separators() — same
    """
    if not text:
        return 0, []
    raw = text.lower()
    norm = normalize(text)
    strip = strip_separators(norm)
    if not norm:
        return 0, []

    table = dict(SLANG)
    extra = getattr(config, "LEXICON_EXTRA", None) or {}
    table.update(extra)

    total = 0
    matched = []
    cats = set()
    for term, meta in table.items():
        meaning, weight, cat = meta
        hit_raw = term in raw
        if not (hit_raw or term in norm or term in strip):
            continue
        total += weight
        cats.add(cat)
        if hit_raw:
            matched.append(term + "=" + meaning)
        else:
            # Only matched after folding → the sender obfuscated it on purpose,
            # which is evidence of intent in itself.
            total += _EVASION_BONUS
            matched.append(term + "=" + meaning + " (obfuscated)")

    # Combo bonus: an earning/scam/counterfeit term together with a
    # contact-evasion term is strongly suspicious.
    if cats & {"money", "scam", "pay", "fake"} and "contact" in cats:
        total += 3

    return total, matched


def is_hard_spam(text):
    """Normalized score >= the hard threshold (config.LEXICON_HARD_THRESHOLD,
    default 6) → spam outright. Used by the prefilter: a hard slang hit saves an
    AI call and defeats fullwidth / lookalike / zero-width / split-word evasion."""
    s, _ = score(text)
    return s >= getattr(config, "LEXICON_HARD_THRESHOLD", 6)
