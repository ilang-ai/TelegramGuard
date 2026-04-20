import aiosqlite
import asyncio
import config

_db = None
_db_lock = asyncio.Lock()

async def get_db():
    global _db
    if _db is None:
        _db = await aiosqlite.connect(config.DB_PATH)
        await _db.execute("PRAGMA journal_mode=WAL")
        await _db.execute("PRAGMA busy_timeout=10000")
        await _db.commit()
    return _db

async def db_exec(func):
    async with _db_lock:
        return await func(await get_db())

class SharedDB:
    async def __aenter__(self):
        await _db_lock.acquire()
        return await get_db()
    async def __aexit__(self, *args):
        _db_lock.release()

def shared_db():
    return SharedDB()
