import config
from modules.db import db_exec

async def is_admin(update, context):
    try:
        chat_id = update.effective_chat.id
        user_id = update.effective_user.id
        member = await context.bot.get_chat_member(chat_id, user_id)
        return member.status in ("administrator", "creator")
    except Exception:
        return False

def is_bot_admin(user_id):
    return config.ADMIN_USER_ID and user_id == config.ADMIN_USER_ID

async def register_group(chat_id, title):
    async def _do(db):
        await db.execute(
            "INSERT INTO groups (chat_id, title) VALUES (?, ?) "
            "ON CONFLICT(chat_id) DO UPDATE SET title=?",
            (chat_id, title, title)
        )
        await db.commit()
    await db_exec(_do)
