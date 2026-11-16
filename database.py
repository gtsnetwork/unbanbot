import aiosqlite
from pathlib import Path
from config import DATABASE_PATH, OWNER_ID

DB = DATABASE_PATH

async def connect():
    Path(DB).parent.mkdir(parents=True, exist_ok=True)
    conn = await aiosqlite.connect(DB, timeout=30)
    conn.row_factory = aiosqlite.Row
    await conn.execute("PRAGMA foreign_keys=ON")
    await conn.execute("PRAGMA journal_mode=WAL")
    return conn

async def init_db():
    async with await connect() as db:
        await db.executescript("""
        CREATE TABLE IF NOT EXISTS users(
            user_id INTEGER PRIMARY KEY, username TEXT, first_name TEXT,
            created_at TEXT NOT NULL, last_seen TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS appeals(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL, username TEXT, first_name TEXT,
            group_name TEXT NOT NULL, ban_reason TEXT NOT NULL,
            explanation TEXT NOT NULL, agreement INTEGER NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            moderator_id INTEGER, moderator_response TEXT,
            created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
            decided_at TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_appeals_user ON appeals(user_id);
        CREATE INDEX IF NOT EXISTS idx_appeals_status ON appeals(status);
        CREATE UNIQUE INDEX IF NOT EXISTS idx_one_pending_per_group
        ON appeals(user_id, group_name)
        WHERE status IN ('pending','under_review','more_info_required');
        CREATE TABLE IF NOT EXISTS moderators(
            user_id INTEGER PRIMARY KEY, approved_by INTEGER NOT NULL,
            approved_at TEXT NOT NULL, active INTEGER NOT NULL DEFAULT 1
        );
        CREATE TABLE IF NOT EXISTS moderator_requests(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL, username TEXT, full_name TEXT,
            reason TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'pending',
            created_at TEXT NOT NULL, reviewed_by INTEGER, reviewed_at TEXT,
            UNIQUE(user_id, status)
        );
        CREATE TABLE IF NOT EXISTS appeal_history(
            id INTEGER PRIMARY KEY AUTOINCREMENT, appeal_id INTEGER NOT NULL,
            actor_id INTEGER NOT NULL, action TEXT NOT NULL, details TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY(appeal_id) REFERENCES appeals(id)
        );
        CREATE TABLE IF NOT EXISTS moderator_activity(
            id INTEGER PRIMARY KEY AUTOINCREMENT, moderator_id INTEGER NOT NULL,
            action TEXT NOT NULL, target TEXT, details TEXT, created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS rate_limits(
            user_id INTEGER PRIMARY KEY, last_action REAL NOT NULL
        );
        CREATE TABLE IF NOT EXISTS bot_users(
            user_id INTEGER PRIMARY KEY, created_at TEXT NOT NULL
        );
        """)
        await db.execute("INSERT OR IGNORE INTO moderators(user_id,approved_by,approved_at,active) VALUES(?,?,datetime('now'),1)",
                         (OWNER_ID, OWNER_ID))
        await db.commit()

async def upsert_user(user_id, username, first_name, now):
    async with await connect() as db:
        await db.execute("""INSERT INTO users VALUES(?,?,?,?,?)
        ON CONFLICT(user_id) DO UPDATE SET username=excluded.username,
        first_name=excluded.first_name,last_seen=excluded.last_seen""",
        (user_id, username, first_name, now, now))
        await db.execute("INSERT OR IGNORE INTO bot_users VALUES(?,?)", (user_id, now))
        await db.commit()

async def is_moderator(user_id):
    if user_id == OWNER_ID:
        return True
    async with await connect() as db:
        cur = await db.execute("SELECT 1 FROM moderators WHERE user_id=? AND active=1", (user_id,))
        return await cur.fetchone() is not None

async def create_appeal(data, now):
    async with await connect() as db:
        try:
            cur = await db.execute("""INSERT INTO appeals
            (user_id,username,first_name,group_name,ban_reason,explanation,agreement,status,created_at,updated_at)
            VALUES(?,?,?,?,?,?,?,'pending',?,?)""",
            (data["user_id"], data["username"], data["first_name"], data["group"],
             data["ban_reason"], data["explanation"], int(data["agreement"]), now, now))
            appeal_id = cur.lastrowid
            await db.execute("INSERT INTO appeal_history(appeal_id,actor_id,action,details,created_at) VALUES(?,?,?,?,?)",
                             (appeal_id, data["user_id"], "submitted", "Appeal submitted", now))
            await db.commit()
            return appeal_id
        except aiosqlite.IntegrityError:
            return None

async def get_appeal(appeal_id):
    async with await connect() as db:
        cur = await db.execute("SELECT * FROM appeals WHERE id=?", (appeal_id,))
        return await cur.fetchone()

async def list_appeals(status=None, limit=15):
    async with await connect() as db:
        if status:
            cur = await db.execute("SELECT * FROM appeals WHERE status=? ORDER BY id DESC LIMIT ?", (status, limit))
        else:
            cur = await db.execute("SELECT * FROM appeals ORDER BY id DESC LIMIT ?", (limit,))
        return await cur.fetchall()

async def user_appeals(user_id):
    async with await connect() as db:
        cur = await db.execute("SELECT * FROM appeals WHERE user_id=? ORDER BY id DESC LIMIT 20", (user_id,))
        return await cur.fetchall()

async def transition_appeal(appeal_id, new_status, moderator_id, response, now, allowed):
    async with await connect() as db:
        placeholders = ",".join("?" for _ in allowed)
        cur = await db.execute(
            f"""UPDATE appeals SET status=?, moderator_id=?, moderator_response=?,
            updated_at=?, decided_at=? WHERE id=? AND status IN ({placeholders})""",
            (new_status, moderator_id, response, now,
             now if new_status in ("approved","rejected") else None,
             appeal_id, *allowed)
        )
        if cur.rowcount != 1:
            await db.rollback()
            return None
        await db.execute("INSERT INTO appeal_history(appeal_id,actor_id,action,details,created_at) VALUES(?,?,?,?,?)",
                         (appeal_id, moderator_id, new_status, response, now))
        await db.execute("INSERT INTO moderator_activity(moderator_id,action,target,details,created_at) VALUES(?,?,?,?,?)",
                         (moderator_id, new_status, str(appeal_id), response, now))
        await db.commit()
        cur = await db.execute("SELECT * FROM appeals WHERE id=?", (appeal_id,))
        return await cur.fetchone()

async def add_mod_request(user_id, username, full_name, reason, now):
    async with await connect() as db:
        cur = await db.execute("SELECT id FROM moderator_requests WHERE user_id=? AND status='pending'", (user_id,))
        existing = await cur.fetchone()
        if existing:
            return existing["id"]
        cur = await db.execute("""INSERT INTO moderator_requests
        (user_id,username,full_name,reason,status,created_at)
        VALUES(?,?,?,?, 'pending', ?)""", (user_id, username, full_name, reason, now))
        await db.commit()
        return cur.lastrowid

async def review_mod_request(request_id, approve, now):
    async with await connect() as db:
        cur = await db.execute("SELECT * FROM moderator_requests WHERE id=? AND status='pending'", (request_id,))
        req = await cur.fetchone()
        if not req:
            return None
        if approve:
            await db.execute("""INSERT INTO moderators(user_id,approved_by,approved_at,active)
            VALUES(?,?,?,1) ON CONFLICT(user_id) DO UPDATE SET approved_by=excluded.approved_by,
            approved_at=excluded.approved_at,active=1""", (req["user_id"], OWNER_ID, now))
            status = "approved"
        else:
            status = "rejected"
        await db.execute("UPDATE moderator_requests SET status=?,reviewed_by=?,reviewed_at=? WHERE id=? AND status='pending'",
                         (status, OWNER_ID, now, request_id))
        await db.commit()
        return dict(req) | {"status": status}

async def pending_mod_requests():
    async with await connect() as db:
        cur = await db.execute("SELECT * FROM moderator_requests WHERE status='pending' ORDER BY id")
        return await cur.fetchall()

async def remove_moderator(user_id, now):
    async with await connect() as db:
        cur = await db.execute("UPDATE moderators SET active=0 WHERE user_id=? AND user_id!=?", (user_id, OWNER_ID))
        await db.execute("INSERT INTO moderator_activity(moderator_id,action,target,details,created_at) VALUES(?,?,?,?,?)",
                         (OWNER_ID, "revoke_moderator", str(user_id), "Access revoked", now))
        await db.commit()
        return cur.rowcount

async def moderators_list():
    async with await connect() as db:
        cur = await db.execute("SELECT * FROM moderators WHERE active=1 ORDER BY approved_at")
        return await cur.fetchall()

async def stats():
    async with await connect() as db:
        result = {}
        for key, query in {
            "users":"SELECT COUNT(*) FROM bot_users",
            "appeals":"SELECT COUNT(*) FROM appeals",
            "pending":"SELECT COUNT(*) FROM appeals WHERE status IN ('pending','under_review','more_info_required')",
            "approved":"SELECT COUNT(*) FROM appeals WHERE status='approved'",
            "rejected":"SELECT COUNT(*) FROM appeals WHERE status='rejected'",
            "mods":"SELECT COUNT(*) FROM moderators WHERE active=1"
        }.items():
            cur = await db.execute(query)
            result[key] = (await cur.fetchone())[0]
        return result

async def activity_log():
    async with await connect() as db:
        cur = await db.execute("SELECT * FROM moderator_activity ORDER BY id DESC LIMIT 50")
        return await cur.fetchall()

async def rate_allowed(user_id, now_epoch, seconds):
    async with await connect() as db:
        cur = await db.execute("SELECT last_action FROM rate_limits WHERE user_id=?", (user_id,))
        row = await cur.fetchone()
        if row and now_epoch - row["last_action"] < seconds:
            return False
        await db.execute("""INSERT INTO rate_limits VALUES(?,?)
        ON CONFLICT(user_id) DO UPDATE SET last_action=excluded.last_action""", (user_id, now_epoch))
        await db.commit()
        return True
