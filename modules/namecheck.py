"""名字就是广告的账号：进群直接拒绝，发言直接判 spam。

2026-11-23 机主：「很多人名字就是 spam 这个我觉得加的时候就直接拒绝」。

全是确定性规则，零 AI 调用：
1. 名字/用户名里带联系方式（t.me 链接、@别人的号、微信号、QQ、手机号）
2. 名字里带网址
3. 名字里出现自学习硬库里已知的 spam 联系方式（spamlib，count ≥ 2）
4. 名字过黑话词库硬阈值（lexicon.score ≥ LEXICON_HARD_THRESHOLD）
命中任一条 ⇒ (True, 原因)。自己的 @用户名不算联系方式；普通名字（哪怕带 emoji）不命中。
"""
import re

import config
from modules import spamlib

try:
    from modules import lexicon as _lex
except Exception:  # pragma: no cover
    _lex = None

_URL_RE = re.compile(r"(https?://|www\.)[^\s]+|[a-z0-9-]+\.(com|cn|net|org|top|xyz|vip|club|shop|site|io|me|cc|tv|app|link|info)(/|\b)")
_HARD = int(getattr(config, "LEXICON_HARD_THRESHOLD", 6))


def display_name(user):
    parts = [getattr(user, "first_name", None) or "", getattr(user, "last_name", None) or ""]
    return " ".join(p for p in parts if p).strip()


def name_is_spam(user, known_contacts=None):
    """user: telegram.User。known_contacts: spamlib 缓存里的已知联系方式集合（可不传）。返回 (bool, reason)。"""
    name = display_name(user)
    uname = (getattr(user, "username", None) or "").lower()
    if not name and not uname:
        return (False, "")
    norm = spamlib.normalize(name)
    # 1) 联系方式（自己的 @用户名不算）
    contacts = spamlib.extract_contacts(norm + (" @" + uname if uname else ""))
    contacts.discard("@" + uname)
    if contacts:
        return (True, "contact:" + ",".join(sorted(contacts))[:60])
    # 2) 网址
    if _URL_RE.search(norm) or (uname and _URL_RE.search(uname)):
        return (True, "url")
    # 3) 已知 spam 联系方式出现在名字里
    if known_contacts is None:
        known_contacts = spamlib._cache.get("contacts") or set()
    hay = norm + " " + uname
    for tok in known_contacts:
        if len(tok) >= 6 and tok in hay:
            return (True, "known:" + tok[:40])
    # 4) 黑话词库硬阈值
    if _lex is not None and norm:
        try:
            sc, terms = _lex.score(norm)
            if sc >= _HARD:
                return (True, "lexicon:%d:%s" % (sc, ",".join(terms)[:60]))
        except Exception:
            pass
    return (False, "")


async def name_is_spam_async(user):
    """带硬库缓存刷新的版本（进群时用）。"""
    try:
        await spamlib._load_cache()
    except Exception:
        pass
    return name_is_spam(user)
