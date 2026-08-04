"""Chase the group for admin rights, or leave.

Anyone can add this bot to any group. Without delete+ban rights it can neither
remove nor restrict anything — yet the old code still sent every single group
message through the AI judge, only to discover afterwards that it had no way to
act. A real incident: one unknown group produced 447 "detected spam but no
permission" lines in 24 hours, every one of them a wasted AI call. That is a
free quota-drain: add the bot to a busy group, withhold rights, watch it burn.

Three layers:
  1. No rights -> no AI judging at all (has_rights, cached) — kills the cost
  2. After being added, nag at 1/2/3/5/10 minutes, escalating in tone
  3. Still nothing at 10 minutes: explain, leave, and blocklist the chat, so a
     re-invite is refused instantly instead of restarting the whole cycle

The blocklist is per chat_id; an owner who wants the bot back can have the
super-admin clear it.
"""

import logging
import time

from modules.db import shared_db

logger = logging.getLogger(__name__)

# Nag schedule in seconds. The last entry leaves the group.
REMIND_AT = (60, 120, 180, 300, 600)
GIVE_UP_AFTER = REMIND_AT[-1]

# Do we hold enforcement rights in this chat: chat_id -> (has_rights, checked_at)
# Calling getChatMember per message is expensive, and rights changes arrive via
# my_chat_member anyway; the cache only covers the case where that event is
# missed, so the TTL can be generous.
_RIGHTS_TTL = 300
_rights_cache = {}


async def ensure_tables():
    async with shared_db() as db:
        await db.execute(
            "CREATE TABLE IF NOT EXISTS group_blocklist ("
            "chat_id INTEGER PRIMARY KEY, title TEXT, reason TEXT, "
            "blocked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)"
        )
        await db.commit()


async def is_blocked(chat_id):
    try:
        async with shared_db() as db:
            cur = await db.execute("SELECT 1 FROM group_blocklist WHERE chat_id=?", (chat_id,))
            return await cur.fetchone() is not None
    except Exception as e:
        logger.warning("blocklist lookup failed (allowing): " + str(e))
        return False


async def block(chat_id, title="", reason="no_admin_rights"):
    async with shared_db() as db:
        await db.execute(
            "INSERT OR REPLACE INTO group_blocklist (chat_id, title, reason) VALUES (?,?,?)",
            (chat_id, title or "", reason)
        )
        await db.commit()


async def unblock(chat_id):
    async with shared_db() as db:
        await db.execute("DELETE FROM group_blocklist WHERE chat_id=?", (chat_id,))
        await db.commit()
    _rights_cache.pop(chat_id, None)


def forget_rights(chat_id):
    """Invalidate the cache when rights may have changed."""
    _rights_cache.pop(chat_id, None)


def note_rights(chat_id, has_rights):
    _rights_cache[chat_id] = (bool(has_rights), time.time())


async def has_rights(context, chat_id, use_cache=True):
    """Can we delete messages AND ban users here. Both, not either."""
    if use_cache:
        hit = _rights_cache.get(chat_id)
        if hit and (time.time() - hit[1]) < _RIGHTS_TTL:
            return hit[0]
    try:
        me = await context.bot.get_chat_member(chat_id, context.bot.id)
        ok = (me.status == "administrator"
              and bool(getattr(me, "can_delete_messages", False))
              and bool(getattr(me, "can_restrict_members", False)))
    except Exception as e:
        # Treat an unknown answer as "no rights": better to judge nothing than
        # to burn calls in a chat we were never authorised in.
        logger.warning("own-rights lookup failed chat=" + str(chat_id) + ": " + str(e))
        ok = False
    note_rights(chat_id, ok)
    return ok


def _job_name(chat_id):
    return "perm_nag_" + str(chat_id)


def cancel(context, chat_id):
    """Drop any pending nags for this chat (rights granted, or we left)."""
    jq = getattr(context, "job_queue", None)
    if not jq:
        return 0
    jobs = jq.get_jobs_by_name(_job_name(chat_id))
    for j in jobs:
        j.schedule_removal()
    return len(jobs)


def schedule(context, chat_id, title=""):
    """Queue the 1/2/3/5/10 minute nags after being added to a group."""
    jq = getattr(context, "job_queue", None)
    if not jq:
        logger.warning("no job_queue, skipping rights nag for chat=" + str(chat_id))
        return False
    cancel(context, chat_id)
    for sec in REMIND_AT:
        jq.run_once(
            _nag,
            sec,
            data={"chat_id": chat_id, "title": title, "at": sec},
            name=_job_name(chat_id),
        )
    return True


TEXTS = {
    60:  "I don't have admin rights yet, so I can't delete ads or ban anyone.\n"
         "Tap the group name -> Administrators -> Add Admin -> pick me -> "
         "enable Delete Messages and Ban Users.",
    120: "Still no rights. Without them I can only watch — I can't help.",
    180: "Third reminder: still not authorised.",
    300: "⚠️ Without rights I will leave this group in 5 minutes.",
}
GOODBYE = ("No admin rights after 10 minutes, so I'm leaving.\n"
           "Without Delete Messages and Ban Users I can't do anything here, and "
           "staying would just waste resources.\n\n"
           "Grant the rights first, then invite me again whenever you like.")


async def _nag(context):
    d = context.job.data
    chat_id, title, at = d["chat_id"], d.get("title", ""), d["at"]

    if await has_rights(context, chat_id, use_cache=False):
        cancel(context, chat_id)
        logger.info("rights granted, stopping nags for chat=" + str(chat_id))
        return

    if at < GIVE_UP_AFTER:
        try:
            await context.bot.send_message(chat_id, TEXTS[at])
        except Exception as e:
            # Can't even speak here (muted/removed) — no point continuing.
            logger.warning("nag failed chat=" + str(chat_id) + ": " + str(e) + ", giving up")
            cancel(context, chat_id)
            await _leave(context, chat_id, title, "cannot_send")
        return

    # Final slot: leave and blocklist.
    try:
        await context.bot.send_message(chat_id, GOODBYE)
    except Exception:
        pass
    cancel(context, chat_id)
    await _leave(context, chat_id, title, "no_admin_rights")


async def _leave(context, chat_id, title, reason):
    try:
        await block(chat_id, title, reason)
    except Exception as e:
        logger.warning("blocklist write failed chat=" + str(chat_id) + ": " + str(e))
    try:
        await context.bot.leave_chat(chat_id)
        logger.info("left unauthorised chat=" + str(chat_id) + " reason=" + reason)
    except Exception as e:
        logger.warning("leave failed chat=" + str(chat_id) + ": " + str(e))
    _rights_cache.pop(chat_id, None)
