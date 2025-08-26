import aiosqlite

DB_PATH = "bot.db"

CREATE_SQL = """
CREATE TABLE IF NOT EXISTS credits (
  user_id INTEGER PRIMARY KEY,
  balance INTEGER NOT NULL DEFAULT 0
);
"""

async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(CREATE_SQL)
        await db.commit()

async def get_balance(user_id: int) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT balance FROM credits WHERE user_id=?", (user_id,)) as cur:
            row = await cur.fetchone()
            return row[0] if row else 0

async def add_credit(user_id: int, amount: int = 1):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT INTO credits(user_id, balance) VALUES(?, ?) ON CONFLICT(user_id) DO UPDATE SET balance=balance+excluded.balance", (user_id, amount))
        await db.commit()

async def consume_credit(user_id: int) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT balance FROM credits WHERE user_id=?", (user_id,)) as cur:
            row = await cur.fetchone()
            bal = row[0] if row else 0
            if bal <= 0:
                return False
        await db.execute("UPDATE credits SET balance=balance-1 WHERE user_id=?", (user_id,))
        await db.commit()
        return True
