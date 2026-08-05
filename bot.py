import logging
import sys
import os
import time as _time
import hashlib as _hashlib
import asyncio
import threading
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, ChatMemberHandler, filters, ContextTypes,
    ApplicationHandlerStop
)
import config
from modules.db import db_exec
from modules.database import init_db
from modules.chat import (
    ai_text, ai_vision, ai_voice, ai_group_reply,
    ai_judge_group_message, ai_judge_group_image, ai_group_vision,
    GROUP_WELCOME
)
from modules.admin import is_admin, is_bot_admin, register_group
from modules.prefilter import prefilter
from modules import probe, onboarding

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)
# httpx 会把完整请求 URL 打进 INFO 日志，而 Telegram 的 URL 里就带着 bot token：
#   HTTP Request: POST https://api.telegram.org/bot<TOKEN>/getUpdates "HTTP/1.1 200 OK"
# 轮询每几秒一次，实测每小时 300-400 行、一天约 8000 次明文 token 落进 journald。
logging.getLogger("httpx").setLevel(logging.WARNING)


TOS_TEXT = (
    "I-Lang Guard Terms of Service\n\n"
    "This bot provides:\n"
    "- Auto spam detection and cleanup\n"
    "- AI-powered message analysis\n\n"
    "Usage:\n"
    "- Bot analyzes group messages for spam detection\n"
    "- No personal data is stored\n"
    "- Admins can remove the bot at any time\n\n"
    "Group admins: tap the button below to accept"
)


async def check_tos(chat_id):
    async def _do(db):
        cur = await db.execute("SELECT 1 FROM tos_consent WHERE chat_id=?", (chat_id,))
        return await cur.fetchone() is not None
    return await db_exec(_do)

async def record_tos(chat_id, user_id):
    async def _do(db):
        await db.execute(
            "INSERT OR REPLACE INTO tos_consent (chat_id, accepted_by) VALUES (?, ?)",
            (chat_id, user_id)
        )
        await db.commit()
    await db_exec(_do)

async def delete_tos(chat_id):
    async def _do(db):
        await db.execute("DELETE FROM tos_consent WHERE chat_id=?", (chat_id,))
        await db.commit()
    await db_exec(_do)


def _ctx_info(context):
    parts = []
    history = context.user_data.get("history", [])
    if not history:
        parts.append("NEW_SESSION:New conversation, greet casually, ask what they need")
    return " | ".join(parts)


async def _handle_ai_result(intent, reply, msg, user_id, context):
    history = context.user_data.setdefault("history", [])
    await msg.reply_text(reply)
    history.append({"role": "assistant", "text": reply})
    if len(history) > 20:
        history[:] = history[-20:]


# ==================== Commands ====================

async def _group_cmd_allowed(update, context):
    """Rate-limit publicly callable commands inside a group.

    The bot answers with reply_text, which bumps the triggering message back to
    the top of the chat — so anyone can spam /help and have the bot repeatedly
    bump their own ad for them, and a loop of /start makes it reprint the whole
    ToS block. One call per chat per GROUP_CMD_COOLDOWN seconds for non-admins;
    admins and private chats are never limited.
    """
    if update.effective_chat.type == "private":
        return True
    try:
        if await is_admin(update, context):
            return True
    except Exception:
        pass
    key = "cmd_cd_" + str(update.effective_chat.id)
    last = context.bot_data.get(key, 0)
    if _time.time() - last < getattr(config, "GROUP_CMD_COOLDOWN", 60):
        return False
    context.bot_data[key] = _time.time()
    return True


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Deliberately no "first caller becomes super-admin" here. This bot is public,
    # so that grab went to whoever happened to /start first after each restart,
    # and it silently re-opened on every deploy. Set ADMIN_USER_ID explicitly;
    # unset means the super-admin commands are unavailable to everyone.
    if update.effective_chat.type == "private":
        context.user_data["history"] = []
        intent, reply = await ai_text(
            "/start",
            history=None,
            context_info="NEW_SESSION:User just opened chat, greet briefly, say what you can do"
        )
        await update.message.reply_text(reply)
        context.user_data.setdefault("history", []).append({"role": "assistant", "text": reply})
    else:
        chat_id = update.effective_chat.id
        await register_group(chat_id, update.effective_chat.title)
        # Rate-limited: the ToS text is a large block, and without this anyone
        # can loop /start to make the bot flood the group with it.
        if not await _group_cmd_allowed(update, context):
            return
        if not await check_tos(chat_id):
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("Accept & Enable", callback_data="tos_accept_" + str(chat_id))],
                [InlineKeyboardButton("Decline", callback_data="tos_decline_" + str(chat_id))]
            ])
            await update.message.reply_text(TOS_TEXT, reply_markup=keyboard)
        else:
            await update.message.reply_text(GROUP_WELCOME)


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type == "private":
        await update.message.reply_text(
            "Just talk to me, no commands needed\n\n"
            "Group admin → Add me to a group, give me admin permissions\n"
            "Anything else → Just chat"
        )
    else:
        if not await _group_cmd_allowed(update, context):
            return
        await update.message.reply_text(
            "I work automatically in groups. No config needed.\n\nAdmin commands:\n/ban — Reply to a message to ban the user"
        )


async def cmd_groups(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Super-admin: inspect and clear the group blocklist.

    Entries expire on their own after onboarding.BLOCK_DAYS, but a wrong one
    should not need a week or a hand-edited database to undo.
    /groups — list, /groups unblock <chat_id> — clear one.
    """
    if not update.effective_user or not is_bot_admin(update.effective_user.id):
        return
    args = context.args or []
    if args and args[0] == "unblock":
        if len(args) < 2:
            await update.message.reply_text("Usage: /groups unblock <chat_id>")
            return
        try:
            cid = int(args[1])
        except ValueError:
            await update.message.reply_text("chat_id must be a number")
            return
        await onboarding.unblock(cid)
        await update.message.reply_text("Unblocked: " + str(cid))
        return
    from modules.db import shared_db
    async with shared_db() as db:
        cur = await db.execute(
            "SELECT chat_id, title, reason, blocked_at FROM group_blocklist "
            "ORDER BY blocked_at DESC LIMIT 20")
        rows = await cur.fetchall()
    if not rows:
        await update.message.reply_text("Blocklist is empty")
        return
    lines = ["Blocked groups (" + str(len(rows)) + ", expire after "
             + str(onboarding.BLOCK_DAYS) + "d):"]
    for cid, title, reason, at in rows:
        lines.append(str(cid) + "  " + (title or "?")[:20] + "  " + str(reason)
                     + "  " + str(at)[:16])
    lines.append("")
    lines.append("Clear one: /groups unblock <chat_id>")
    await update.message.reply_text("\n".join(lines))


async def cmd_ban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type == "private" or not update.message.reply_to_message:
        return
    if not await is_admin(update, context):
        return
    try:
        t = update.message.reply_to_message.from_user
        await context.bot.ban_chat_member(update.effective_chat.id, t.id)
        await update.message.reply_text("done")
    except Exception as e:
        await update.message.reply_text(str(e))


# ==================== Group ====================

async def _ban_actor(context, chat_id, sender_chat, user_id):
    """Ban whoever is actually responsible for the message.

    A message posted under a chat's identity carries a globally shared stand-in
    user in `from` (Channel_Bot / GroupAnonymousBot); ban_chat_member on that id
    is a permanent no-op, so a spammer wearing a channel identity could post
    forever. The real identity is in sender_chat and needs ban_chat_sender_chat.
    """
    if sender_chat is not None and sender_chat.id != chat_id:
        return await context.bot.ban_chat_sender_chat(chat_id, sender_chat.id)
    return await context.bot.ban_chat_member(chat_id, user_id)


async def _remind_no_permission(msg, context, chat_id):
    """Tell admins we found spam but cannot act on it. Once per chat per hour."""
    last = context.bot_data.get("perm_remind_" + str(chat_id), 0)
    if _time.time() - last <= 3600:
        return
    context.bot_data["perm_remind_" + str(chat_id)] = _time.time()
    try:
        await msg.reply_text(
            "⚠️ Detected spam but I don't have permissions to act.\n\n"
            "Tap group name → Admins → Add Admin → Find me → Enable Delete Messages and Ban Users → Done"
        )
    except Exception:
        pass


def _poll_text(msg):
    """A poll's visible text: the question plus every option.

    A poll is prime real estate — 300 characters of question and up to 12 options
    of 100 characters each, all sender-controlled — and none of it appears in
    msg.text, so it used to be judged by nobody.
    """
    p = getattr(msg, "poll", None)
    if not p:
        return ""
    parts = [p.question or ""]
    for o in (p.options or []):
        parts.append(getattr(o, "text", "") or "")
    return " ".join(x for x in parts if x)


def _media_meta(msg):
    """Text a reader can see on a media message but that msg.text/caption lacks.

    Ads live here routinely: the file name spells out a contact handle, the audio
    title is used as ad space, the sticker set name points at a landing page, a
    shared contact card is a phone number and a display name and nothing else.
    """
    out = []
    for obj, attrs in (
        (getattr(msg, "document", None), ("file_name",)),
        (getattr(msg, "audio", None), ("title", "performer", "file_name")),
        (getattr(msg, "video", None), ("file_name",)),
        (getattr(msg, "animation", None), ("file_name",)),
        (getattr(msg, "sticker", None), ("emoji", "set_name")),
        (getattr(msg, "venue", None), ("title", "address")),
        (getattr(msg, "game", None), ("title", "description")),
        (getattr(msg, "invoice", None), ("title", "description")),
        # No dedicated contact handler exists, so contact cards come through the
        # normal pipeline and this is the only text they carry.
        (getattr(msg, "contact", None), ("first_name", "last_name", "phone_number")),
    ):
        if obj is None:
            continue
        for a in attrs:
            v = getattr(obj, a, None)
            if v:
                out.append(str(v))
    return " ".join(out)


def _hidden_text(msg, user):
    """Attack-surface text that readers can see or tap but msg.text does not hold.

    1. The URL behind a hyperlink: a text_link entity keeps its url in entities,
       never in msg.text. "[hello everyone](spam-link)" reached the judge as two
       harmless words.
    2. The forward origin's title: a spammer's own channel name IS the ad, and it
       is rendered above the message and is tappable.
    3. The sender's display name: set first_name to an ad and every innocuous
       message they post is advertising on their behalf.
    """
    out = []
    for e in list(getattr(msg, "entities", None) or []) + list(getattr(msg, "caption_entities", None) or []):
        u = getattr(e, "url", None)
        if u:
            out.append(u)
        eu = getattr(e, "user", None)  # text_mention: a user rendered as a link
        if eu is not None:
            for a in ("first_name", "last_name", "username"):
                v = getattr(eu, a, None)
                if v:
                    out.append(str(v))
    fo = getattr(msg, "forward_origin", None)
    if fo is not None:
        for holder in (getattr(fo, "chat", None), getattr(fo, "sender_chat", None), getattr(fo, "sender_user", None)):
            if holder is None:
                continue
            for a in ("title", "username", "first_name"):
                v = getattr(holder, a, None)
                if v:
                    out.append(str(v))
        v = getattr(fo, "sender_user_name", None)
        if v:
            out.append(str(v))
    vb = getattr(msg, "via_bot", None)
    if vb is not None and getattr(vb, "username", None):
        out.append(str(vb.username))
    if user is not None:
        for a in ("first_name", "last_name", "username"):
            v = getattr(user, a, None)
            if v:
                out.append(str(v))
    return " ".join(out)


async def _answer_mention(msg, context, is_mention, text):
    """Reply to someone who @mentioned the bot or replied to it.

    Called only once the message is known to be clean (or from an admin) — it
    used to run at the top of handle_group_message and return, which let any
    spammer skip the entire anti-spam pipeline just by replying to the bot.
    """
    clean = text.replace("@" + context.bot.username, "").strip() if (text and is_mention) else (text.strip() if text else "")
    g_history = context.chat_data.setdefault("group_history", [])
    if msg.photo:
        try:
            f = await context.bot.get_file(msg.photo[-1].file_id)
            img_data = bytes(await f.download_as_bytearray())
            reply = await ai_group_vision(img_data, caption=clean, history=g_history)
        except Exception:
            reply = "Couldn't read that image. Try sending another one?"
    elif msg.video:
        if msg.video.thumbnail:
            try:
                vf = await context.bot.get_file(msg.video.thumbnail.file_id)
                vimg = bytes(await vf.download_as_bytearray())
                reply = await ai_group_vision(vimg, caption=clean, history=g_history)
            except Exception:
                if clean:
                    g_history.append({"role": "user", "text": "[video] " + clean})
                    reply = await ai_group_reply("[video] " + clean, g_history)
                else:
                    reply = "Couldn't read the video thumbnail. What's it about?"
        elif clean:
            g_history.append({"role": "user", "text": "[video] " + clean})
            reply = await ai_group_reply("[video] " + clean, g_history)
        else:
            reply = "Can't process videos directly. What's it about?"
    else:
        g_history.append({"role": "user", "text": clean})
        reply = await ai_group_reply(clean, g_history)
    g_history.append({"role": "assistant", "text": reply})
    if len(g_history) > 20:
        g_history[:] = g_history[-20:]
    try:
        await msg.reply_text(reply)
    except Exception as e:
        logger.warning("group @mention reply failed: chat=" + str(msg.chat.id) + " err=" + str(e))


async def handle_group_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Edited messages come in too: this used to read update.message only, which
    # is None on an edit event, so the handler returned on its first line and
    # "post something harmless, then edit it into an ad" bypassed everything.
    is_edited = update.message is None and update.edited_message is not None
    msg = update.message or update.edited_message
    if not msg:
        return
    chat_id = msg.chat.id
    user = msg.from_user
    if not user:
        return
    text = msg.text or msg.caption or ""
    # The string the judges see = the visible body plus everything a reader can
    # see or tap that is NOT in text (link targets, forward origin, display name).
    # Only the judging layers get it; text itself stays untouched because it is
    # still used for @mention parsing, the probe layer and logging.
    _hidden = _hidden_text(msg, user)
    judge_text = (text + " " + _hidden).strip() if _hidden else text

    await register_group(chat_id, msg.chat.title)

    tos_ok = await check_tos(chat_id)

    # @mention or reply to bot — only detected here, answered at the end of the
    # function once anti-spam has cleared the message.
    is_mention = text and context.bot.username and ("@" + context.bot.username) in text
    is_reply_to_bot = msg.reply_to_message and msg.reply_to_message.from_user and msg.reply_to_message.from_user.id == context.bot.id
    has_media = bool(msg.photo or msg.video or msg.document)
    # Is this message a command? This handler now runs in group=-1, ahead of the
    # CommandHandlers, so command messages reach it too. They must be excluded:
    # "/start@ourbot" contains "@ourbotusername", so the mention check above fires
    # and the bot would answer it with AI here while cmd_start answers it again
    # in group 0 — one command, two replies.
    ents = getattr(msg, "entities", None) or ()
    is_command = bool(ents) and ents[0].type == "bot_command" and ents[0].offset == 0
    # An edited message is re-judged for spam but never re-answered, otherwise
    # the bot replies again every time the user tweaks their message.
    wants_reply = bool((text or has_media) and (is_mention or is_reply_to_bot)
                       and not is_edited and not is_command)

    # ToS not accepted: guidance only. Without admin consent we take no action.
    if not tos_ok:
        if wants_reply:
            try:
                await msg.reply_text("I haven't been enabled yet. Ask an admin to tap the Accept & Enable button above.")
            except Exception as e:
                logger.warning("group @mention reply failed: chat=" + str(chat_id) + " err=" + str(e))
        # Plain return, never ApplicationHandlerStop: the group-0 CommandHandlers
        # still have to run, otherwise /start can never be used to accept the ToS
        # and the bot could never be enabled at all.
        return

    # No admin rights means nothing we decide can be acted on, so don't decide:
    # judging here is pure wasted AI spend. This is a real quota-drain surface —
    # anyone can add the bot to a busy group and withhold rights (observed live:
    # 447 "detected spam but no permission" lines from one unknown group in 24h).
    # The rights nag runs on a timer in modules/onboarding and gives up at 10 min.
    if not await onboarding.has_rights(context, chat_id):
        # Say so once in a while so someone fixes it, but not on every mention —
        # "make the bot talk" is the same free drain in miniature, and legacy
        # rights-less groups never go through the nag flow at all.
        if wants_reply:
            k = "norights_cd_" + str(chat_id)
            if _time.time() - context.bot_data.get(k, 0) >= 600:
                context.bot_data[k] = _time.time()
                try:
                    await msg.reply_text(
                        "I don't have admin rights yet (Delete Messages + Ban Users), "
                        "so I can't do anything here. Ask an admin to grant them."
                    )
                except Exception:
                    pass
        return

    # A message posted under a chat's identity (anonymous admin, channel identity)
    # gets a globally shared stand-in user in `from` — GroupAnonymousBot
    # (1087968824) or Channel_Bot (136817688) — with the real identity in
    # sender_chat. Never reading sender_chat had two consequences:
    #   1. banning called ban_chat_member on the stand-in id, which does nothing,
    #      so a channel identity could post ads indefinitely
    #   2. the per-user message bucket was keyed on that shared id, pooling every
    #      channel-identity sender together, so a cleanup deleted other people's
    #      messages
    sender_chat = getattr(msg, "sender_chat", None)
    # sender_chat == this group means an admin posting anonymously — an admin.
    is_anon_admin = sender_chat is not None and sender_chat.id == chat_id
    # An automatic forward from the linked channel is the owner's own content.
    is_auto_forward = bool(getattr(msg, "is_automatic_forward", False))
    # The party held responsible: bookkeeping, judging and banning all key on it.
    actor_id = sender_chat.id if sender_chat is not None else user.id

    # Admin check
    is_admin_user = is_anon_admin or is_auto_forward
    if not is_admin_user:
        try:
            member = await context.bot.get_chat_member(chat_id, user.id)
            if member.status in ("administrator", "creator"):
                is_admin_user = True
        except Exception:
            pass

    # Track recent messages: (msg_id, content_hash, timestamp)
    user_msgs = context.chat_data.setdefault("user_recent_msgs", {})
    uid = actor_id
    if uid not in user_msgs:
        user_msgs[uid] = []
    content_hash = _hashlib.md5(text.encode()).hexdigest() if text else ""
    now = _time.time()
    # An edit carries the same message_id: replace the existing entry instead of
    # appending a second one, so the bulk-delete list holds no duplicates and
    # editing one message repeatedly doesn't look like flooding.
    user_msgs[uid] = [e for e in user_msgs[uid] if e[0] != msg.message_id]
    user_msgs[uid].append((msg.message_id, content_hash, now))
    if len(user_msgs[uid]) > 20:
        user_msgs[uid] = user_msgs[uid][-20:]

    # Admin bypass: no enforcement on admins, but still answer them.
    if is_admin_user:
        if wants_reply:
            await _answer_mention(msg, context, is_mention, text)
        return

    # Probe ("check-in") filler: mark only, never ban. Runs before the duplicate
    # check so repeated check-ins can't escalate into a ban.
    probe_result = None
    try:
        probe_result = await probe.check(msg, chat_id, uid, context.bot.username)
    except Exception as e:
        logger.warning("probe check failed: " + str(e))
    # ApplicationHandlerStop is raised outside the try above on purpose — it is
    # an Exception subclass, so `except Exception` would swallow it.
    if probe_result == probe.DELETED:
        raise ApplicationHandlerStop
    if probe_result:
        return

    # @mention / reply-to-bot now goes through anti-spam as well. Asking the bot
    # a question is not an offence though — without this hint the judge reads a
    # question addressed to it as promotion and bans the person for it.
    sender_ctx = ""
    if wants_reply:
        sender_ctx = (
            "This message is addressed to the bot (a question or a reply to it). "
            "Asking the bot something is not a violation on its own — only call it "
            "spam if the content really is advertising, a scam, or contact harvesting."
        )

    # Duplicate message detection
    spam = False
    if content_hash:
        recent_same = [
            e for e in user_msgs[uid]
            if e[1] == content_hash and (now - e[2]) < config.SPAM_REPEAT_WINDOW
        ]
        if len(recent_same) >= config.SPAM_REPEAT_THRESHOLD:
            spam = True
            logger.info("REPEAT SPAM: user=" + str(uid) + " chat=" + str(chat_id) + " count=" + str(len(recent_same)))

    # Pre-filter: keyword/regex/forward/new-account (zero API cost).
    # judge_text, not text: the keyword, contact and lexicon layers have to see
    # the hidden text too, otherwise a bare "hello everyone" hyperlinked to a spam
    # URL passes every one of them.
    if not spam:
        verdict = prefilter(msg, user, judge_text)
        if verdict == "spam":
            spam = True
        elif verdict == "ai":
            # Needs AI analysis (API budget available)
            if msg.photo:
                try:
                    f = await context.bot.get_file(msg.photo[-1].file_id)
                    data = bytes(await f.download_as_bytearray())
                    spam = await ai_judge_group_image(data, judge_text, sender_context=sender_ctx)
                except Exception:
                    if judge_text:
                        spam = await ai_judge_group_message(judge_text, sender_context=sender_ctx)
            elif msg.video:
                if msg.video.thumbnail:
                    try:
                        vf = await context.bot.get_file(msg.video.thumbnail.file_id)
                        vdata = bytes(await vf.download_as_bytearray())
                        spam = await ai_judge_group_image(vdata, judge_text, sender_context=sender_ctx)
                    except Exception:
                        if judge_text:
                            spam = await ai_judge_group_message(judge_text, sender_context=sender_ctx)
                elif judge_text:
                    spam = await ai_judge_group_message(judge_text, sender_context=sender_ctx)
                elif msg.forward_origin:
                    spam = True
            elif msg.document or msg.sticker or msg.animation or msg.video_note:
                # This branch used to judge the caption and nothing else, falling
                # back to msg.forward_date — an attribute PTB no longer has, so a
                # caption-less sticker/document/GIF raised AttributeError right
                # here and the message was never judged, deleted or logged.
                # And these ads are usually IN the picture, not in the caption:
                # the sticker image is the ad, "send as file" dodges the vision
                # judge, the file name spells out a contact handle.
                # Now: judge the thumbnail if there is one, otherwise at least
                # judge the metadata text.
                thumb = None
                if msg.sticker:
                    # A plain .webp sticker can go to the vision judge as-is;
                    # animated/video stickers only via their thumbnail.
                    thumb = msg.sticker.thumbnail
                    if not thumb and not msg.sticker.is_animated and not msg.sticker.is_video:
                        thumb = msg.sticker
                elif msg.animation:
                    thumb = msg.animation.thumbnail
                elif msg.video_note:
                    thumb = msg.video_note.thumbnail
                elif msg.document:
                    thumb = msg.document.thumbnail
                    if not thumb and (msg.document.mime_type or "").startswith("image/"):
                        thumb = msg.document  # an image "sent as a file": judge it directly
                # Combined, not "judge_text or metadata": judge_text is never
                # empty (it always carries the sender's display name), so an
                # `or` would silently discard the file name / sticker set name
                # on every single message.
                meta = (judge_text + " " + _media_meta(msg)).strip()
                judged = False
                if thumb is not None:
                    try:
                        tf = await context.bot.get_file(thumb.file_id)
                        tdata = bytes(await tf.download_as_bytearray())
                        spam = await ai_judge_group_image(tdata, meta, sender_context=sender_ctx)
                        judged = True
                    except Exception as e:
                        logger.warning("media thumb judge failed: " + str(e))
                if not judged:
                    if meta:
                        spam = await ai_judge_group_message(meta, sender_context=sender_ctx)
                    elif msg.forward_origin:
                        spam = True
            elif msg.poll:
                spam = await ai_judge_group_message((_poll_text(msg) + " " + _hidden).strip(), sender_context=sender_ctx)
            elif text:
                spam = await ai_judge_group_message(judge_text, sender_context=sender_ctx)
            else:
                # Everything else that carries sender-controlled text but no body:
                # a shared contact card, a venue, an audio track.
                meta = (_media_meta(msg) + " " + _hidden).strip()
                if meta:
                    spam = await ai_judge_group_message(meta, sender_context=sender_ctx)
        # verdict == "clean" → skip AI, let it through

    if spam:
        try:
            tasks = []
            for entry in user_msgs.get(uid, []):
                mid = entry[0] if isinstance(entry, tuple) else entry
                tasks.append(context.bot.delete_message(chat_id, mid))
            n_del = len(tasks)
            tasks.append(_ban_actor(context, chat_id, sender_chat, user.id))
            results = await asyncio.gather(*tasks, return_exceptions=True)
            # gather(return_exceptions=True) never raises: a permission error
            # (Forbidden) or a rate limit (RetryAfter) comes back as a VALUE in
            # results. The old code threw the results away, so a bot without the
            # rights logged "SPAM nuked" while the ad sat untouched in the group
            # and the reminder branch below was unreachable dead code.
            deleted_ok = sum(1 for r in results[:n_del]
                             if not isinstance(r, Exception) and r is not False)
            ban_ok = not isinstance(results[n_del], Exception)
            errs = [r for r in results if isinstance(r, Exception)]
            user_msgs.pop(uid, None)
            if errs and (deleted_ok == 0 or not ban_ok):
                logger.warning(
                    "SPAM action PARTIAL/FAILED: user=" + str(uid) + " chat=" + str(chat_id) +
                    " deleted=" + str(deleted_ok) + "/" + str(n_del) + " ban_ok=" + str(ban_ok) +
                    " errs=" + str([type(e).__name__ + ":" + str(e)[:60] for e in errs[:3]])
                )
                await _remind_no_permission(msg, context, chat_id)
            else:
                logger.info("SPAM nuked: user=" + str(uid) + " chat=" + str(chat_id) +
                            " deleted=" + str(deleted_ok) + "/" + str(n_del) + " (banned)")
        except Exception as e:
            logger.warning("Anti-spam action failed: " + str(e))
            await _remind_no_permission(msg, context, chat_id)
        # The message is gone: stop the chain so the group-0 CommandHandlers do
        # not reply to a deleted message. A command may carry arbitrary trailing
        # text, so "/help <ad text>" reaches this handler AND cmd_help.
        raise ApplicationHandlerStop

    # Clean message (spam was handled and returned above). Only now do we answer
    # someone who was talking to the bot.
    if wants_reply:
        await _answer_mention(msg, context, is_mention, text)


# ==================== Private ====================

async def handle_private_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg or not msg.text:
        return
    user_id = msg.from_user.id
    history = context.user_data.setdefault("history", [])
    history.append({"role": "user", "text": msg.text})
    intent, reply = await ai_text(msg.text, history, _ctx_info(context))
    await _handle_ai_result(intent, reply, msg, user_id, context)


async def handle_private_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg or not msg.photo:
        return
    user_id = msg.from_user.id
    history = context.user_data.setdefault("history", [])
    caption = msg.caption or ""
    history.append({"role": "user", "text": "[photo] " + caption if caption else "[photo]"})
    try:
        file = await context.bot.get_file(msg.photo[-1].file_id)
        img_bytes = bytes(await file.download_as_bytearray())
    except Exception:
        await msg.reply_text("Didn't receive that image. Try again?")
        return
    intent, reply = await ai_vision(img_bytes, caption, history, _ctx_info(context))
    await _handle_ai_result(intent, reply, msg, user_id, context)


async def handle_private_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg or not msg.voice:
        return
    user_id = msg.from_user.id
    history = context.user_data.setdefault("history", [])
    history.append({"role": "user", "text": "[voice]"})
    try:
        file = await context.bot.get_file(msg.voice.file_id)
        audio_bytes = bytes(await file.download_as_bytearray())
        mime = msg.voice.mime_type or "audio/ogg"
    except Exception:
        await msg.reply_text("Didn't catch that voice message. Try again or just type it out.")
        return
    intent, reply = await ai_voice(audio_bytes, mime, history, _ctx_info(context))
    await _handle_ai_result(intent, reply, msg, user_id, context)


# ==================== Events ====================

async def handle_my_chat_member(update: Update, context: ContextTypes.DEFAULT_TYPE):
    result = update.my_chat_member
    if not result:
        return
    chat_id = result.chat.id
    old = result.old_chat_member.status if result.old_chat_member else "left"
    new = result.new_chat_member.status if result.new_chat_member else "left"
    # This event also fires when our rights are edited, so drop the cache or we
    # would keep using the stale answer until the TTL expires.
    onboarding.forget_rights(chat_id)
    # Stop nagging the moment we are out, unconditionally. Not inside the branch
    # below: restricted -> kicked does not satisfy its `old` test, which would
    # orphan the nags. They would then keep posting into a chat we already left,
    # fail, and that failure would be read as "we can never speak here".
    if new in ("left", "kicked"):
        onboarding.cancel(context, chat_id)

    if old in ("left", "kicked") and new in ("member", "administrator"):
        # Channels are not supported: the anti-spam filter is ChatType.GROUPS
        # (which excludes CHANNEL) and allowed_updates does not subscribe to
        # channel_post, so structurally we can never see a single post here.
        # Running the whole ToS flow and answering with a green "enabled" tick
        # was an empty promise — the owner would think the product works. Say so
        # and leave instead.
        if result.chat.type not in ("group", "supergroup"):
            try:
                await context.bot.send_message(
                    chat_id,
                    "I only support groups and supergroups — not channels. "
                    "I can't see any content here, so keeping me around wouldn't do "
                    "anything. Leaving now."
                )
            except Exception:
                pass
            try:
                await context.bot.leave_chat(chat_id)
            except Exception as e:
                logger.warning("leave non-group chat failed: " + str(e))
            return
        # Already blocklisted (we gave this chat 10 minutes once and got nothing):
        # leave without a word. Otherwise re-inviting is a free way to make the
        # bot talk and process traffic over and over.
        if await onboarding.is_blocked(chat_id):
            logger.info("added to a blocklisted chat, leaving: " + str(chat_id))
            try:
                await context.bot.leave_chat(chat_id)
            except Exception as e:
                logger.warning("leaving blocklisted chat failed: " + str(e))
            return
        onboarding.forget_rights(chat_id)
        # Queue the 1/2/3/5/10 minute rights nags; the last one leaves + blocklists.
        onboarding.schedule(context, chat_id, result.chat.title or "")
        await delete_tos(chat_id)
        await register_group(chat_id, result.chat.title)
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("Accept & Enable", callback_data="tos_accept_" + str(chat_id))],
            [InlineKeyboardButton("Decline", callback_data="tos_decline_" + str(chat_id))]
        ])
        await context.bot.send_message(chat_id, TOS_TEXT, reply_markup=keyboard)
    elif new in ("left", "kicked"):
        onboarding.forget_rights(chat_id)
        await delete_tos(chat_id)


async def handle_tos_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query or not query.data:
        return

    is_accept = query.data.startswith("tos_accept_")
    is_decline = query.data.startswith("tos_decline_")
    if not is_accept and not is_decline:
        return

    chat_id = query.message.chat.id
    user_id = query.from_user.id

    try:
        admins = await context.bot.get_chat_administrators(chat_id)
        admin_ids = [a.user.id for a in admins]
        if user_id not in admin_ids:
            await query.answer("Only admins can do this", show_alert=True)
            return
    except Exception:
        pass

    if is_accept:
        await record_tos(chat_id, user_id)
        await query.answer("Enabled")
        has_perms = False
        try:
            bot_member = await context.bot.get_chat_member(chat_id, context.bot.id)
            if hasattr(bot_member, 'can_delete_messages') and bot_member.can_delete_messages and hasattr(bot_member, 'can_restrict_members') and bot_member.can_restrict_members:
                has_perms = True
        except Exception:
            pass

        if has_perms:
            await query.edit_message_text("I-Lang Guard enabled ✅\n\nSpam cleanup is now automatic.")
        else:
            await query.edit_message_text(
                "I-Lang Guard enabled\n\n"
                "⚠️ I need admin permissions to work:\n\n"
                "1. Tap the group name\n"
                "2. Tap Administrators\n"
                "3. Tap Add Admin\n"
                "4. Find I-Lang Guard\n"
                "5. Enable Delete Messages and Ban Users\n"
                "6. Tap Done"
            )
    else:
        await query.answer("OK, goodbye")
        await query.edit_message_text("Left the group")
        await context.bot.leave_chat(chat_id)


# ==================== Health Check (HF Space) ====================

class HealthHandler(BaseHTTPRequestHandler):
    # Without this, a client that opens a connection and never sends a request
    # line blocks handle_one_request() on rfile.readline() forever. The port is
    # public, so internet scanners do exactly that: observed in production with
    # Recv-Q=6 against a backlog of 5 — the accept queue full of connections the
    # server never got to, and the health check timing out while the bot itself
    # was perfectly healthy.
    timeout = 5

    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"OK")

    def handle_one_request(self):
        try:
            super().handle_one_request()
        except OSError:  # peer vanished / read timed out — nothing to log
            self.close_connection = True

    def log_message(self, *args):
        pass

def start_health_server():
    port = int(os.environ.get("PORT", 7860))
    # Threading, not the single-threaded HTTPServer: one stalled client must not
    # be able to wedge the whole health endpoint (see HealthHandler.timeout).
    server = ThreadingHTTPServer(("0.0.0.0", port), HealthHandler)
    server.daemon_threads = True
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    logger.info("Health check on port " + str(port))


# ==================== Main ====================

def main():
    # Ensure data directory exists
    db_dir = os.path.dirname(config.DB_PATH)
    if db_dir:
        os.makedirs(db_dir, exist_ok=True)

    app = Application.builder().token(config.BOT_TOKEN).connect_timeout(30).read_timeout(30).write_timeout(30).pool_timeout(30).build()

    async def _on_error(update, context):
        # There was no error handler at all, so an exception inside a handler
        # left nothing but a traceback in the log: a crash halfway through the
        # judging chain looked exactly like a clean message.
        logger.exception("handler error: " + str(context.error))
    app.add_error_handler(_on_error)

    # UpdateType.MESSAGE everywhere below: once edited_message is subscribed to,
    # every handler sees edit events too. Only the group handler wants them —
    # anywhere else an edit would run the command or the answer a second time.
    for cmd, fn in [
        ("start", cmd_start), ("help", cmd_help), ("ban", cmd_ban),
        ("groups", cmd_groups),
    ]:
        app.add_handler(CommandHandler(cmd, fn, filters=filters.UpdateType.MESSAGE))

    app.add_handler(ChatMemberHandler(handle_my_chat_member, ChatMemberHandler.MY_CHAT_MEMBER))
    app.add_handler(CallbackQueryHandler(handle_tos_callback, pattern="^tos_"))

    # Group — deliberately no UpdateType filter: edits must be re-judged here.
    # Also deliberately no ~filters.COMMAND. A command addressed to a DIFFERENT bot
    # ("/start@OtherBot buy followers cheap") is refused by our own CommandHandlers —
    # PTB checks the @username against this bot and returns None on a mismatch — so
    # excluding commands here left those messages handled by nothing at all.
    #
    # group=-1, and it has to be. PTB runs only the FIRST matching handler per
    # group, and CommandHandler accepts arbitrary trailing text (everything after
    # /help goes into args), so with the CommandHandlers registered first in
    # group 0 a message like "/help buy followers cheap 加V abc" was swallowed by
    # cmd_help and never judged at all. Running first fixes that; the handler
    # raises ApplicationHandlerStop once it has actually deleted something, so
    # clean messages still fall through to the group-0 command handlers.
    #
    # The type whitelist is gone too. TEXT|PHOTO|VIDEO|Document|Sticker meant
    # audio, voice, video notes, polls, stories, venues, locations and dice
    # matched no handler anywhere — an mp3 with an ad caption, or a poll whose
    # question IS the ad, was visible to the whole group and checked by nobody.
    # Everything in a group is now accepted, minus join/leave/pin system events.
    # CONTACT is deliberately NOT excluded (unlike the private bot this was
    # ported from, which has a dedicated contact handler): here nothing else
    # would pick a shared contact card up, and a contact card is a display name
    # plus a phone number, which is exactly what a contact-harvesting ad is.
    app.add_handler(MessageHandler(
        filters.ChatType.GROUPS & ~filters.StatusUpdate.ALL,
        handle_group_message
    ), group=-1)

    # Private
    app.add_handler(MessageHandler(filters.TEXT & filters.ChatType.PRIVATE & ~filters.COMMAND & filters.UpdateType.MESSAGE, handle_private_text))
    app.add_handler(MessageHandler(filters.PHOTO & filters.ChatType.PRIVATE & filters.UpdateType.MESSAGE, handle_private_photo))
    app.add_handler(MessageHandler(filters.VOICE & filters.ChatType.PRIVATE & filters.UpdateType.MESSAGE, handle_private_voice))

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(init_db())
    loop.run_until_complete(onboarding.ensure_tables())

    # Detect mode: webhook (Cloud Run / Railway) or polling (VPS)
    webhook_url = os.environ.get("WEBHOOK_URL", "")
    port = int(os.environ.get("PORT", 8080))

    if webhook_url:
        # Webhook mode: start listening IMMEDIATELY (Cloud Run health check is strict)
        logger.info("I-Lang Guard starting (webhook: " + webhook_url + ")")
        app.run_webhook(
            listen="0.0.0.0",
            port=port,
            url_path="webhook",
            webhook_url=webhook_url + "/webhook",
            drop_pending_updates=True,
            # edited_message: without subscribing, Telegram never sends edit
            # events at all and "post something harmless, then edit it into an
            # ad" walks straight past the anti-spam pipeline.
            allowed_updates=["message", "edited_message", "callback_query", "my_chat_member"],
        )
    else:
        # Polling mode: run AI test first, then start
        async def _test_ai():
            try:
                from modules import ai_provider
                text = await ai_provider.generate_text(
                    "Say hi in one word. JSON: {\"intent\":\"chat\",\"reply\":\"hi\"}",
                    max_tokens=50)
                if text:
                    logger.info("AI startup test OK: " + text[:100])
                else:
                    logger.error("AI startup test FAILED: empty response")
            except Exception as e:
                logger.error("AI startup test EXCEPTION: " + str(e))
        loop.run_until_complete(_test_ai())

        start_health_server()
        logger.info("I-Lang Guard starting (polling mode)")
        app.run_polling(
            drop_pending_updates=True,
            # See the webhook branch above — edited_message must be subscribed
            # to or edits bypass anti-spam entirely.
            allowed_updates=["message", "edited_message", "callback_query", "my_chat_member"],
            bootstrap_retries=10
        )


if __name__ == "__main__":
    main()
