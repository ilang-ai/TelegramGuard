"""
中文黑话/擦边词库层（功能4）。

解决通用模型判不出"收米""上车""日结"这类抖音直播式规避话术的问题。
两步：
1. normalize() 先把文本归一化 —— 全角转半角、去零宽字符、同形字（西里尔/希腊字母伪装）还原、转小写，
   破掉 spam 常用的 Unicode 花招。
2. score() 在归一化后的文本上匹配词库打分，并对"搞钱词 + 联系方式规避词"同时出现做组合加成。

用法（在 bot.py 判定前调用）：
    s, terms = lexicon.score(text)
    if s >= config.LEXICON_HARD_THRESHOLD:   # 硬命中，直接判 spam，省一次 AI 调用
        ...
    else:                                     # 软命中，把 terms 作为线索喂给 AI
        ...

词库可通过 config.LEXICON_EXTRA 扩展，群主不用改代码就能加词。
"""

import unicodedata

import config

# 零宽字符 / 方向控制符（spam 常插进词里破坏关键词匹配）
_ZERO_WIDTH = dict.fromkeys(
    map(ord, "​‌‍‎‏‪‫‬⁠﻿"), None
)

# 常见同形字：西里尔 / 希腊字母 → 拉丁（伪装成英文字母的花招）
_HOMOGLYPH = {
    "а": "a", "е": "e", "о": "o", "р": "p", "с": "c", "х": "x", "у": "y",
    "ѕ": "s", "і": "i", "ј": "j", "к": "k", "н": "h", "в": "b", "м": "m", "т": "t",
    "ο": "o", "ρ": "p", "α": "a", "ν": "v", "τ": "t", "ϲ": "c",
}


def normalize(text):
    if not text:
        return ""
    t = unicodedata.normalize("NFKC", text)          # 全角 → 半角
    t = t.translate(_ZERO_WIDTH)                      # 去零宽/方向符
    t = "".join(_HOMOGLYPH.get(ch, ch) for ch in t)  # 同形字还原
    return t.lower()


# 词库：term -> (含义, 权重, 类别)
# 类别 money=搞钱/招募  contact=联系方式规避  pay=支付/加密货币  scam=诈骗盘
# 权重越高越可疑；单个词一般不足以直接判 spam（见 LEXICON_HARD_THRESHOLD），
# 靠组合 + 阈值控制误伤（例如"收米"在直播打赏语境是正常词）。
SLANG = {
    # ---- 搞钱 / 招募 ----
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
    # ---- 联系方式规避 ----
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
    "蝙蝠": ("BatChat 加密聊天", 2, "contact"),
    "皮皮虾": ("加密聊天软件", 2, "contact"),
    "私我": ("私聊引流", 1, "contact"),
    "详聊": ("私下详谈引流", 1, "contact"),
    "加我": ("引流加好友", 1, "contact"),
    # ---- 支付 / 加密货币 ----
    "usdt": ("USDT 加密货币支付", 2, "pay"),
    "泰达": ("USDT", 2, "pay"),
    "承兑": ("加密货币承兑洗钱", 3, "pay"),
    "代收": ("第三方代收款", 2, "pay"),
    "四方": ("四方支付(灰产收款)", 3, "pay"),
}


def score(text):
    """返回 (总分, 命中词列表'词=含义')。文本先归一化再匹配。"""
    t = normalize(text)
    if not t:
        return 0, []
    table = dict(SLANG)
    extra = getattr(config, "LEXICON_EXTRA", None) or {}
    table.update(extra)

    total = 0
    matched = []
    cats = set()
    for term, meta in table.items():
        meaning, weight, cat = meta
        if term in t:
            total += weight
            cats.add(cat)
            matched.append(term + "=" + meaning)

    # 组合加成：搞钱/诈骗词 + 联系方式规避词 同时出现 → 强烈可疑
    if cats & {"money", "scam", "pay"} and "contact" in cats:
        total += 3

    return total, matched


def is_hard_spam(text):
    """归一化打分 >= 硬阈值(config.LEXICON_HARD_THRESHOLD, 默认6) → 直接判 spam。
    给 prefilter 用：黑话硬命中直接判、省一次 AI 调用，且破全角/同形字/零宽规避。"""
    s, _ = score(text)
    return s >= getattr(config, "LEXICON_HARD_THRESHOLD", 6)
