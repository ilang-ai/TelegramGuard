import logging
import sys
import os
import time as _time
import hashlib as _hashlib
import asyncio

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, ChatMemberHandler, filters, ContextTypes
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

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

TOS_TEXT = (
    "I-Lang Guard 服务条款\n\n"
    "为保障群组安全, 本Bot提供以下服务:\n"
    "- 自动识别并清理垃圾广告\n"
    "- 通过消息分析持续优化AI反spam能力\n\n"
    "使用说明:\n"
    "- Bot会分析群内消息用于反垃圾和AI模型优化\n"
    "- 不存储个人身份信息\n"
    "- 管理员可随时移除Bot终止服务\n\n"
    "群管理员点击下方按钮即表示同意以上条款"
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
        parts.append("NEW_SESSION:新对话开始,主动问好,问用户今天需要什么帮助")
    return " | ".join(parts)


async def _handle_ai_result(intent, device, reply, msg, user_id, context):
    history = context.user_data.setdefault("history", [])
    await msg.reply_text(reply)
    history.append({"role": "assistant", "text": reply})
    if len(history) > 20:
        history[:] = history[-20:]


# ==================== Commands ====================

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not config.ADMIN_USER_ID:
        config.ADMIN_USER_ID = update.effective_user.id
    if update.effective_chat.type == "private":
        context.user_data["history"] = []
        intent, device, reply = await ai_text(
            "/start",
            history=None,
            context_info="NEW_SESSION:用户刚打开对话,简短问好,介绍你能做什么"
        )
        await update.message.reply_text(reply)
        context.user_data.setdefault("history", []).append({"role": "assistant", "text": reply})
    else:
        chat_id = update.effective_chat.id
        await register_group(chat_id, update.effective_chat.title)
        if not await check_tos(chat_id):
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("同意并启用", callback_data="tos_accept_" + str(chat_id))],
                [InlineKeyboardButton("不同意", callback_data="tos_decline_" + str(chat_id))]
            ])
            await update.message.reply_text(TOS_TEXT, reply_markup=keyboard)
        else:
            await update.message.reply_text(GROUP_WELCOME)


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type == "private":
        await update.message.reply_text(
            "直接跟我说话就行, 不用命令\n\n"
            "群管理 → 拉我进群, 给管理员权限\n"
            "其他 → 随便聊"
        )
    else:
        await update.message.reply_text(
            "我在群里自动工作, 不用配置\n\n管理员命令:\n/ban — 回复消息踢人"
        )


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

async def handle_group_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg:
        return
    chat_id = msg.chat.id
    user = msg.from_user
    if not user:
        return
    text = msg.text or msg.caption or ""

    await register_group(chat_id, msg.chat.title)

    tos_ok = await check_tos(chat_id)

    # @mention or reply to bot
    is_mention = text and context.bot.username and ("@" + context.bot.username) in text
    is_reply_to_bot = msg.reply_to_message and msg.reply_to_message.from_user and msg.reply_to_message.from_user.id == context.bot.id
    has_media = bool(msg.photo or msg.video or msg.document)
    if (text or has_media) and (is_mention or is_reply_to_bot):
        clean = text.replace("@" + context.bot.username, "").strip() if (text and is_mention) else (text.strip() if text else "")
        if not tos_ok:
            reply = "我还没被启用哦, 请管理员点一下上面的「同意并启用」按钮"
        else:
            g_history = context.chat_data.setdefault("group_history", [])
            if msg.photo:
                try:
                    f = await context.bot.get_file(msg.photo[-1].file_id)
                    img_data = bytes(await f.download_as_bytearray())
                    reply = await ai_group_vision(img_data, caption=clean, history=g_history)
                except Exception:
                    reply = "图片没看清, 再发一张?"
            elif msg.video:
                if msg.video.thumbnail:
                    try:
                        vf = await context.bot.get_file(msg.video.thumbnail.file_id)
                        vimg = bytes(await vf.download_as_bytearray())
                        reply = await ai_group_vision(vimg, caption=clean, history=g_history)
                    except Exception:
                        if clean:
                            g_history.append({"role": "user", "text": "[视频] " + clean})
                            reply = await ai_group_reply("[视频] " + clean, g_history)
                        else:
                            reply = "视频封面没看清, 说说是什么内容?"
                elif clean:
                    g_history.append({"role": "user", "text": "[视频] " + clean})
                    reply = await ai_group_reply("[视频] " + clean, g_history)
                else:
                    reply = "视频我看不了, 说说是什么内容?"
            else:
                g_history.append({"role": "user", "text": clean})
                reply = await ai_group_reply(clean, g_history)
            g_history.append({"role": "assistant", "text": reply})
            if len(g_history) > 20:
                g_history[:] = g_history[-20:]
        await msg.reply_text(reply)
        return

    if not tos_ok:
        return

    # Admin check
    is_admin_user = False
    try:
        member = await context.bot.get_chat_member(chat_id, user.id)
        if member.status in ("administrator", "creator"):
            is_admin_user = True
    except Exception:
        pass

    # Track recent messages: (msg_id, content_hash, timestamp)
    user_msgs = context.chat_data.setdefault("user_recent_msgs", {})
    uid = user.id
    if uid not in user_msgs:
        user_msgs[uid] = []
    content_hash = _hashlib.md5(text.encode()).hexdigest() if text else ""
    now = _time.time()
    user_msgs[uid].append((msg.message_id, content_hash, now))
    if len(user_msgs[uid]) > 20:
        user_msgs[uid] = user_msgs[uid][-20:]

    # Admin bypass
    if is_admin_user:
        return

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

    # AI spam check (skip if already caught)
    if not spam:
        if msg.photo:
            try:
                f = await context.bot.get_file(msg.photo[-1].file_id)
                data = bytes(await f.download_as_bytearray())
                spam = await ai_judge_group_image(data, text)
            except Exception:
                if text:
                    spam = await ai_judge_group_message(text)
        elif msg.video:
            if msg.video.thumbnail:
                try:
                    vf = await context.bot.get_file(msg.video.thumbnail.file_id)
                    vdata = bytes(await vf.download_as_bytearray())
                    spam = await ai_judge_group_image(vdata, text)
                except Exception:
                    if text:
                        spam = await ai_judge_group_message(text)
            elif text:
                spam = await ai_judge_group_message(text)
            elif msg.forward_date:
                spam = True
        elif msg.document or msg.sticker:
            if text:
                spam = await ai_judge_group_message(text)
            elif msg.forward_date:
                spam = True
        elif text:
            spam = await ai_judge_group_message(text)

    if spam:
        try:
            tasks = []
            for entry in user_msgs.get(uid, []):
                mid = entry[0] if isinstance(entry, tuple) else entry
                tasks.append(context.bot.delete_message(chat_id, mid))
            tasks.append(context.bot.ban_chat_member(chat_id, uid))
            results = await asyncio.gather(*tasks, return_exceptions=True)
            user_msgs.pop(uid, None)
            logger.info("SPAM nuked: user=" + str(uid) + " chat=" + str(chat_id) + " tasks=" + str(len(tasks)))
        except Exception as e:
            logger.warning("Anti-spam action failed: " + str(e))
            last_remind = context.bot_data.get("perm_remind_" + str(chat_id), 0)
            if _time.time() - last_remind > 3600:
                context.bot_data["perm_remind_" + str(chat_id)] = _time.time()
                try:
                    await msg.reply_text(
                        "\u26a0\ufe0f 发现垃圾消息但我没权限处理\n\n"
                        "点群名字 → 管理员 → 添加管理员 → 找到我 → 打开「删除消息」和「封禁用户」→ 完成"
                    )
                except Exception:
                    pass
        return


# ==================== Private ====================

async def handle_private_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg or not msg.text:
        return
    user_id = msg.from_user.id
    history = context.user_data.setdefault("history", [])
    history.append({"role": "user", "text": msg.text})
    intent, device, reply = await ai_text(msg.text, history, _ctx_info(context))
    await _handle_ai_result(intent, device, reply, msg, user_id, context)


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
        await msg.reply_text("图片没收到, 再发一次?")
        return
    intent, device, reply = await ai_vision(img_bytes, caption, history, _ctx_info(context))
    await _handle_ai_result(intent, device, reply, msg, user_id, context)


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
        await msg.reply_text("语音没收到, 再说一次或者打字也行")
        return
    intent, device, reply = await ai_voice(audio_bytes, mime, history, _ctx_info(context))
    await _handle_ai_result(intent, device, reply, msg, user_id, context)


# ==================== Events ====================

async def handle_my_chat_member(update: Update, context: ContextTypes.DEFAULT_TYPE):
    result = update.my_chat_member
    if not result:
        return
    chat_id = result.chat.id
    old = result.old_chat_member.status if result.old_chat_member else "left"
    new = result.new_chat_member.status if result.new_chat_member else "left"

    if old in ("left", "kicked") and new in ("member", "administrator"):
        await delete_tos(chat_id)
        await register_group(chat_id, result.chat.title)
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("同意并启用", callback_data="tos_accept_" + str(chat_id))],
            [InlineKeyboardButton("不同意", callback_data="tos_decline_" + str(chat_id))]
        ])
        await context.bot.send_message(chat_id, TOS_TEXT, reply_markup=keyboard)
    elif old in ("member", "administrator") and new in ("left", "kicked"):
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
            await query.answer("只有管理员可以操作", show_alert=True)
            return
    except Exception:
        pass

    if is_accept:
        await record_tos(chat_id, user_id)
        await query.answer("已启用")
        has_perms = False
        try:
            bot_member = await context.bot.get_chat_member(chat_id, context.bot.id)
            if hasattr(bot_member, 'can_delete_messages') and bot_member.can_delete_messages and hasattr(bot_member, 'can_restrict_members') and bot_member.can_restrict_members:
                has_perms = True
        except Exception:
            pass

        if has_perms:
            await query.edit_message_text("I-Lang Guard 已启用 ✅\n\n垃圾广告我来清理, 全自动")
        else:
            await query.edit_message_text(
                "I-Lang Guard 已启用\n\n"
                "⚠️ 我还需要管理员权限才能干活:\n\n"
                "1. 点群名字进入群资料\n"
                "2. 点「管理员」\n"
                "3. 点「添加管理员」\n"
                "4. 找到 I-Lang Guard 点它\n"
                "5. 打开「删除消息」和「封禁用户」\n"
                "6. 点右上角「完成」"
            )
    else:
        await query.answer("好的, 再见")
        await query.edit_message_text("已退出群组")
        await context.bot.leave_chat(chat_id)


# ==================== Main ====================

def main():
    # Ensure data directory exists
    os.makedirs(os.path.dirname(config.DB_PATH) or "data", exist_ok=True)

    app = Application.builder().token(config.BOT_TOKEN).build()

    for cmd, fn in [
        ("start", cmd_start), ("help", cmd_help), ("ban", cmd_ban),
    ]:
        app.add_handler(CommandHandler(cmd, fn))

    app.add_handler(ChatMemberHandler(handle_my_chat_member, ChatMemberHandler.MY_CHAT_MEMBER))
    app.add_handler(CallbackQueryHandler(handle_tos_callback, pattern="^tos_"))

    # Group
    app.add_handler(MessageHandler(
        (filters.TEXT | filters.PHOTO | filters.VIDEO | filters.Document.ALL | filters.Sticker.ALL) & filters.ChatType.GROUPS & ~filters.COMMAND,
        handle_group_message
    ))

    # Private
    app.add_handler(MessageHandler(filters.TEXT & filters.ChatType.PRIVATE & ~filters.COMMAND, handle_private_text))
    app.add_handler(MessageHandler(filters.PHOTO & filters.ChatType.PRIVATE, handle_private_photo))
    app.add_handler(MessageHandler(filters.VOICE & filters.ChatType.PRIVATE, handle_private_voice))

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(init_db())

    logger.info("I-Lang Guard starting...")
    app.run_polling(
        drop_pending_updates=True,
        allowed_updates=["message", "callback_query", "my_chat_member"]
    )


if __name__ == "__main__":
    main()
