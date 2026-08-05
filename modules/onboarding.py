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

"Couldn't find out" is not "no rights" — that is the central rule here. A
getChatMember timeout, a Telegram 5xx or a flood-wait all raise, and treating
every raise as a negative means one network blip can make the bot leave a fully
authorised group and blocklist it, irreversibly. So probe_rights is tri-state:
True / False / None, and only a confirmed False may trigger a leave.

Blocklist entries expire after BLOCK_DAYS. An attacker has to redo the whole
setup every week for a payoff of five messages, while an honest mistake heals
itself without anyone editing the database by hand. A super-admin can also clear
one instantly with /groups unblock <chat_id>.
"""

import logging
import time

from telegram.error import BadRequest, Forbidden

from modules.db import shared_db

logger = logging.getLogger(__name__)

# Nag schedule in seconds. The last entry leaves the group.
REMIND_AT = (60, 120, 180, 300, 600)
GIVE_UP_AFTER = REMIND_AT[-1]

# When the rights lookup itself fails: how long to wait, how many times to retry.
# No leaving happens while retrying — an unknown answer is not evidence.
RETRY_AFTER = 60
MAX_RETRIES = 3

# How long a blocklist entry stays in force.
BLOCK_DAYS = 7

# Do we hold enforcement rights in this chat: chat_id -> (has_rights, checked_at, ttl)
# Calling getChatMember per message is expensive, and rights changes arrive via
# my_chat_member anyway; the cache only covers the case where that event is
# missed, so the TTL can be generous.
# A False derived from a failed lookup is cached only briefly (_UNKNOWN_TTL) —
# otherwise one blip silences the whole group for five minutes, during which every
# message skips judging and nothing ever arrives to clear the cache.
_RIGHTS_TTL = 300
_UNKNOWN_TTL = 20
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
            cur = await db.execute(
                "SELECT 1 FROM group_blocklist WHERE chat_id=? "
                "AND blocked_at > datetime('now', ?)",
                (chat_id, "-" + str(BLOCK_DAYS) + " days")
            )
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


def note_rights(chat_id, has_rights, ttl=_RIGHTS_TTL):
    _rights_cache[chat_id] = (bool(has_rights), time.time(), ttl)


async def probe_rights(context, chat_id):
    """Tri-state: True (have them) / False (confirmed not) / None (couldn't tell).

    None must never collapse into False. Anything irreversible — leaving,
    blocklisting — may only act on a confirmed False. Writes no cache; the caller
    decides how to record the answer.
    """
    try:
        me = await context.bot.get_chat_member(chat_id, context.bot.id)
    except Exception as e:
        logger.warning("own-rights lookup failed chat=" + str(chat_id) + ": " + str(e))
        return None
    return (me.status == "administrator"
            and bool(getattr(me, "can_delete_messages", False))
            and bool(getattr(me, "can_restrict_members", False)))


async def has_rights(context, chat_id, use_cache=True):
    """Can we delete messages AND ban users here. Both, not either.

    For the message path: an unknown answer counts as False (better to judge
    nothing than to burn calls in a chat we were never authorised in), but it is
    cached only briefly. Use probe_rights for anything that leads to a leave.
    """
    if use_cache:
        hit = _rights_cache.get(chat_id)
        if hit and (time.time() - hit[1]) < hit[2]:
            return hit[0]
    ok = await probe_rights(context, chat_id)
    if ok is None:
        note_rights(chat_id, False, _UNKNOWN_TTL)
        return False
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


def _requeue(context, chat_id, title, at, tries):
    """Couldn't read rights for this slot — redo it in a minute, advance nothing."""
    jq = getattr(context, "job_queue", None)
    if not jq:
        return False
    jq.run_once(
        _nag,
        RETRY_AFTER,
        data={"chat_id": chat_id, "title": title, "at": at, "tries": tries},
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
GENERIC = ("I don't have admin rights yet (Delete Messages + Ban Users), so I "
           "can't do anything here.\nTap the group name -> Administrators -> "
           "Add Admin -> pick me -> enable both.")
GOODBYE = ("No admin rights after 10 minutes, so I'm leaving.\n"
           "Without Delete Messages and Ban Users I can't do anything here, and "
           "staying would just waste resources.\n\n"
           "Grant the rights first, then invite me again whenever you like.")


def _is_fatal_send_error(e):
    """Is this "we can never speak here" or "the network hiccuped"?

    Only the former may lead to a leave. Forbidden means kicked/muted/blocked and
    is definitive; among BadRequests only the chat-is-gone family is. Everything
    else (timeouts, 5xx, flood-wait) is treated as transient so the remaining
    nags still get their chance.
    """
    if isinstance(e, Forbidden):
        return True
    if isinstance(e, BadRequest):
        t = str(e).lower()
        return ("chat not found" in t or "chat_id is empty" in t
                or "group chat was deactivated" in t or "chat was upgraded" in t)
    return False


async def _nag(context):
    d = context.job.data
    chat_id, title, at = d["chat_id"], d.get("title", ""), d["at"]
    tries = d.get("tries", 0)

    ok = await probe_rights(context, chat_id)

    if ok is None:
        # Unknown is not a negative. Never leave on this — retry the same slot.
        if tries < MAX_RETRIES:
            logger.warning("rights lookup failed, retrying in " + str(RETRY_AFTER)
                           + "s chat=" + str(chat_id) + " at=" + str(at)
                           + " tries=" + str(tries + 1))
            _requeue(context, chat_id, title, at, tries + 1)
        else:
            # Repeatedly unanswerable: either a long outage or the chat is gone.
            # Bow out quietly — no leave, no blocklist. A rights-less chat costs
            # nothing on the message path anyway.
            logger.warning("rights lookup failed " + str(MAX_RETRIES)
                           + "x, giving up on nags (not leaving) chat=" + str(chat_id))
            cancel(context, chat_id)
        return

    if ok:
        note_rights(chat_id, True)
        cancel(context, chat_id)
        logger.info("rights granted, stopping nags for chat=" + str(chat_id))
        return

    note_rights(chat_id, False)

    if at < GIVE_UP_AFTER:
        text = TEXTS.get(at, GENERIC)
        try:
            await context.bot.send_message(chat_id, text)
        except Exception as e:
            if _is_fatal_send_error(e):
                # We genuinely cannot speak here (kicked/muted) — nagging is moot.
                logger.warning("nag undeliverable chat=" + str(chat_id) + ": "
                               + str(e) + ", leaving")
                cancel(context, chat_id)
                await _leave(context, chat_id, title, "cannot_send", blocklist=False)
            else:
                # Transient — do nothing, the later slots still run.
                logger.warning("nag send failed (transient) chat=" + str(chat_id)
                               + ": " + str(e))
        return

    # Final slot: confirmed no rights, so leave and blocklist.
    try:
        await context.bot.send_message(chat_id, GOODBYE)
    except Exception:
        pass
    cancel(context, chat_id)
    await _leave(context, chat_id, title, "no_admin_rights")


async def _leave(context, chat_id, title, reason, blocklist=True):
    """Leave. blocklist=False is for "they kicked or muted us" — that was their
    call, and holding it against the chat would block a re-invite they are
    perfectly entitled to make."""
    if blocklist:
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
