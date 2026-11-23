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


async def close_db():
    """Close the shared connection on shutdown.

    aiosqlite runs each connection on a NON-daemon worker thread. Left open, the
    interpreter cannot exit after Application.stop(): the process sat there until
    systemd SIGKILLed it at TimeoutStopSec (90 s) on every single restart.
    """
    global _db
    if _db is not None:
        try:
            await _db.close()
        except Exception:
            pass
        _db = None
