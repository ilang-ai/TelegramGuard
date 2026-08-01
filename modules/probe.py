"""
Probe ("check-in") detection.

Spam bots warm a group up with harmless filler — 签到 / 打卡 / 冒泡 — to see whether
anyone is moderating and to build a bit of message history before dropping the
actual ad. This layer is deliberately the gentlest one in the stack:

  * every non-admin member is subject to it (not just new joiners)
  * it NEVER bans — the worst it does is silently delete
  * and it only starts deleting after the same member has been flagged
    config.PROBE_FLAG_DELETE times inside a rolling PROBE_WINDOW_HOURS window

Everything else keeps going through the lexicon + AI path.
"""

import logging
import re

import config
from modules.db import shared_db

logger = logging.getLogger(__name__)

# Deliberately narrow — only the check-in family of phrases.
# A wider pattern (哈+ / 好+的? / 收到 / 顶, plus "pure emoji" and "pure punctuation")
# was measured against real Chinese group chat: it hit 59% of ordinary short
# messages. Since this layer applies to every member, that means silently
# deleting real people's "哈哈" and "👍" — worse than missing a probe.
PROBE_PATTERNS = re.compile(
    r"^(签到|打卡|报到|新人报道|前来报道|冒泡|水一下|沙发|路过)\s*$"
)


def looks_like_probe(text):
    """Pure check-in filler. Single-message check, no history involved."""
    if not text:
        return False
    t = text.strip()
    return len(t) <= 8 and bool(PROBE_PATTERNS.match(t))


# A bare "/start@SomeOtherBot" posted in a group is the classic way to drive
# traffic to another bot — you start a bot in private, not by announcing it in a
# group. The AI judge cannot flag it (there is nothing to judge but a command),
# so it belongs here. Only /start: "/menu@ShopBot" is somebody legitimately
# using another bot in the group and must not be touched.
FOREIGN_START = re.compile(r"^/start@([A-Za-z0-9_]{4,32})\s*$", re.I)


def looks_like_foreign_start(text, my_username=""):
    """True for a bare /start aimed at a bot that is not us."""
    if not text:
        return False
    m = FOREIGN_START.match(text.strip())
    if not m:
        return False
    return m.group(1).lower() != (my_username or "").lower().lstrip("@")


def _window_hours():
    try:
        return max(1, int(getattr(config, "PROBE_WINDOW_HOURS", 24)))
    except (TypeError, ValueError):
        return 24


async def add_flag(chat_id, user_id):
    """Add one probe flag for this member and return the running count.

    UPSERT, not a bare UPDATE: members have no row until their first probe, and
    an UPDATE that matches nothing affects 0 rows and keeps returning 0 — the
    delete threshold would never be reached and this whole layer would be dead.

    window_start records the START of the current window and is NOT refreshed on
    a hit, so the window genuinely expires. Refreshing it every time would let
    the count of someone who posts one such message a day ratchet up forever
    until they are permanently silenced.
    """
    window = "-%d hours" % _window_hours()
    async with shared_db() as db:
        await db.execute(
            "INSERT INTO probe_flags (chat_id, user_id, flags, window_start) "
            "VALUES (?, ?, 1, CURRENT_TIMESTAMP) "
            "ON CONFLICT(chat_id, user_id) DO UPDATE SET "
            "flags = CASE WHEN window_start IS NULL OR window_start < datetime('now', ?) "
            "             THEN 1 ELSE flags + 1 END, "
            "window_start = CASE WHEN window_start IS NULL OR window_start < datetime('now', ?) "
            "                    THEN CURRENT_TIMESTAMP ELSE window_start END",
            (chat_id, user_id, window, window)
        )
        await db.commit()
        cur = await db.execute(
            "SELECT flags FROM probe_flags WHERE chat_id=? AND user_id=?",
            (chat_id, user_id)
        )
        row = await cur.fetchone()
        return row[0] if row else 0


async def check(msg, chat_id, user_id, my_username=""):
    """Flag a probe message. Returns True if this message was one (caller stops).

    Judges msg.text only, never captions: a caption hit would delete the photo
    along with it, which is a visible accident. Admins never reach this — the
    caller returns for them before calling in.
    """
    if not msg.text:
        return False
    if not (looks_like_probe(msg.text) or looks_like_foreign_start(msg.text, my_username)):
        return False
    flags = await add_flag(chat_id, user_id)
    logger.info("PROBE flag: user=" + str(user_id) + " chat=" + str(chat_id) +
                " flags=" + str(flags) + " text=" + msg.text[:20])
    if flags >= getattr(config, "PROBE_FLAG_DELETE", 2):
        # Mark-only layer: delete quietly, never ban, never warn.
        try:
            await msg.delete()
        except Exception as e:
            logger.warning("PROBE delete failed: " + str(e))
    return True
