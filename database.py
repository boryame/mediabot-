import sqlite3
import datetime
from config import DB_NAME


def get_conn():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_conn()
    c = conn.cursor()

    c.execute("""CREATE TABLE IF NOT EXISTS users (
        id          INTEGER PRIMARY KEY,
        full_name   TEXT,
        username    TEXT,
        lang        TEXT DEFAULT '',
        is_admin    INTEGER DEFAULT 0,
        vip_until   TEXT,
        views       INTEGER DEFAULT 0,
        joined_at   TEXT DEFAULT CURRENT_TIMESTAMP
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS admins (
        user_id  INTEGER PRIMARY KEY,
        added_by INTEGER,
        added_at TEXT DEFAULT CURRENT_TIMESTAMP
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS subscriptions (
        id           INTEGER PRIMARY KEY AUTOINCREMENT,
        channel_id   TEXT NOT NULL,
        channel_name TEXT,
        channel_url  TEXT,
        sub_type     TEXT DEFAULT 'public',
        is_active    INTEGER DEFAULT 1
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS movies (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        title       TEXT NOT NULL,
        category    TEXT NOT NULL,
        year        INTEGER,
        country     TEXT,
        genre       TEXT,
        rating      REAL DEFAULT 0,
        description TEXT,
        poster_id   TEXT,
        is_vip      INTEGER DEFAULT 0,
        is_active   INTEGER DEFAULT 1,
        views       INTEGER DEFAULT 0,
        added_by    INTEGER,
        added_at    TEXT DEFAULT CURRENT_TIMESTAMP
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS seasons (
        id         INTEGER PRIMARY KEY AUTOINCREMENT,
        movie_id   INTEGER NOT NULL,
        season_num INTEGER NOT NULL
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS episodes (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        movie_id    INTEGER NOT NULL,
        season_id   INTEGER,
        episode_num INTEGER DEFAULT 1,
        file_id     TEXT NOT NULL
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS views (
        id        INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id   INTEGER,
        movie_id  INTEGER,
        viewed_at TEXT DEFAULT CURRENT_TIMESTAMP
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS ratings (
        user_id  INTEGER,
        movie_id INTEGER,
        rating   INTEGER,
        PRIMARY KEY (user_id, movie_id)
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS messages (
        id         INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id    INTEGER,
        full_name  TEXT,
        message    TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS settings (
        key   TEXT PRIMARY KEY,
        value TEXT
    )""")

    c.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('forward_enabled', '0')")

    conn.commit()
    conn.close()
    print("✅ Database tayyor!")


# ── FOYDALANUVCHI ──────────────────────────────────────

def add_user(uid, full_name, username):
    conn = get_conn()
    conn.execute("INSERT OR IGNORE INTO users (id, full_name, username) VALUES (?,?,?)",
                 (uid, full_name, username))
    conn.execute("UPDATE users SET full_name=?, username=? WHERE id=?",
                 (full_name, username, uid))
    conn.commit()
    conn.close()


def get_user(uid):
    conn = get_conn()
    row = conn.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()
    conn.close()
    return row


def get_user_lang(uid):
    conn = get_conn()
    row = conn.execute("SELECT lang FROM users WHERE id=?", (uid,)).fetchone()
    conn.close()
    return (row["lang"] or "uz") if row else "uz"


def set_user_lang(uid, lang):
    conn = get_conn()
    conn.execute("UPDATE users SET lang=? WHERE id=?", (lang, uid))
    conn.commit()
    conn.close()


def get_all_user_ids():
    conn = get_conn()
    rows = conn.execute("SELECT id FROM users").fetchall()
    conn.close()
    return [r["id"] for r in rows]


# ── ADMIN ──────────────────────────────────────────────

def is_admin(uid):
    conn = get_conn()
    row = conn.execute("SELECT is_admin FROM users WHERE id=?", (uid,)).fetchone()
    conn.close()
    return bool(row and row["is_admin"])


def add_admin(uid, added_by):
    conn = get_conn()
    conn.execute("UPDATE users SET is_admin=1 WHERE id=?", (uid,))
    conn.execute("INSERT OR IGNORE INTO admins (user_id, added_by) VALUES (?,?)", (uid, added_by))
    conn.commit()
    conn.close()


# ── OBUNA ──────────────────────────────────────────────

def get_subscriptions():
    conn = get_conn()
    rows = conn.execute("SELECT * FROM subscriptions WHERE is_active=1").fetchall()
    conn.close()
    return rows


def add_subscription(channel_id, channel_name, channel_url, sub_type):
    conn = get_conn()
    conn.execute(
        "INSERT INTO subscriptions (channel_id, channel_name, channel_url, sub_type) VALUES (?,?,?,?)",
        (channel_id, channel_name, channel_url, sub_type)
    )
    conn.commit()
    conn.close()


def remove_subscription(sub_id):
    conn = get_conn()
    conn.execute("DELETE FROM subscriptions WHERE id=?", (sub_id,))
    conn.commit()
    conn.close()


# ── KINO ───────────────────────────────────────────────

def add_movie(data):
    conn = get_conn()
    cur = conn.execute(
        """INSERT INTO movies (title, category, year, country, genre, description, poster_id, is_vip, added_by)
           VALUES (?,?,?,?,?,?,?,?,?)""",
        (data["title"], data["category"], data.get("year"), data.get("country"),
         data.get("genre"), data.get("description"), data.get("poster_id"),
         data.get("is_vip", 0), data.get("added_by"))
    )
    movie_id = cur.lastrowid
    conn.commit()
    conn.close()
    return movie_id


def get_movie(movie_id):
    conn = get_conn()
    row = conn.execute("SELECT * FROM movies WHERE id=? AND is_active=1", (movie_id,)).fetchone()
    conn.close()
    return row


def delete_movie(movie_id):
    conn = get_conn()
    conn.execute("UPDATE movies SET is_active=0 WHERE id=?", (movie_id,))
    conn.execute("DELETE FROM episodes WHERE movie_id=?", (movie_id,))
    conn.execute("DELETE FROM seasons WHERE movie_id=?", (movie_id,))
    conn.commit()
    conn.close()


def get_movies_by_category(category, limit=12, offset=0):
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM movies WHERE category=? AND is_active=1 ORDER BY id DESC LIMIT ? OFFSET ?",
        (category, limit, offset)
    ).fetchall()
    conn.close()
    return rows


def count_movies_by_category(category):
    conn = get_conn()
    n = conn.execute(
        "SELECT COUNT(*) as c FROM movies WHERE category=? AND is_active=1", (category,)
    ).fetchone()["c"]
    conn.close()
    return n


def search_movies(query):
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM movies WHERE is_active=1 AND (title LIKE ? OR id=?) LIMIT 20",
        (f"%{query}%", query if query.isdigit() else -1)
    ).fetchall()
    conn.close()
    return rows


def get_random_movie():
    conn = get_conn()
    row = conn.execute("SELECT * FROM movies WHERE is_active=1 ORDER BY RANDOM() LIMIT 1").fetchone()
    conn.close()
    return row


def add_view(uid, movie_id):
    conn = get_conn()
    conn.execute("INSERT INTO views (user_id, movie_id) VALUES (?,?)", (uid, movie_id))
    conn.execute("UPDATE movies SET views=views+1 WHERE id=?", (movie_id,))
    conn.execute("UPDATE users SET views=views+1 WHERE id=?", (uid,))
    conn.commit()
    conn.close()


def set_rating(uid, movie_id, rating):
    conn = get_conn()
    conn.execute("INSERT OR REPLACE INTO ratings (user_id, movie_id, rating) VALUES (?,?,?)",
                 (uid, movie_id, rating))
    avg = conn.execute("SELECT AVG(rating) as a FROM ratings WHERE movie_id=?",
                       (movie_id,)).fetchone()["a"]
    conn.execute("UPDATE movies SET rating=? WHERE id=?", (round(avg, 1), movie_id))
    conn.commit()
    conn.close()


# ── FASL / QISM ────────────────────────────────────────

def add_season(movie_id, season_num):
    conn = get_conn()
    cur = conn.execute("INSERT INTO seasons (movie_id, season_num) VALUES (?,?)",
                       (movie_id, season_num))
    sid = cur.lastrowid
    conn.commit()
    conn.close()
    return sid


def get_seasons(movie_id):
    conn = get_conn()
    rows = conn.execute("SELECT * FROM seasons WHERE movie_id=? ORDER BY season_num",
                        (movie_id,)).fetchall()
    conn.close()
    return rows


def add_episode(movie_id, file_id, season_id=None, episode_num=1):
    conn = get_conn()
    conn.execute(
        "INSERT INTO episodes (movie_id, season_id, episode_num, file_id) VALUES (?,?,?,?)",
        (movie_id, season_id, episode_num, file_id)
    )
    conn.commit()
    conn.close()


def get_episodes(movie_id, season_id=None):
    conn = get_conn()
    if season_id:
        rows = conn.execute(
            "SELECT * FROM episodes WHERE movie_id=? AND season_id=? ORDER BY episode_num",
            (movie_id, season_id)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM episodes WHERE movie_id=? ORDER BY episode_num",
            (movie_id,)
        ).fetchall()
    conn.close()
    return rows


# ── VIP ────────────────────────────────────────────────

def is_vip(uid):
    conn = get_conn()
    row = conn.execute("SELECT vip_until FROM users WHERE id=?", (uid,)).fetchone()
    conn.close()
    if not row or not row["vip_until"]:
        return False
    try:
        return datetime.datetime.strptime(row["vip_until"], "%Y-%m-%d") >= datetime.datetime.now()
    except:
        return False


def set_vip(uid, days):
    until = (datetime.datetime.now() + datetime.timedelta(days=days)).strftime("%Y-%m-%d")
    conn = get_conn()
    conn.execute("UPDATE users SET vip_until=? WHERE id=?", (until, uid))
    conn.commit()
    conn.close()
    return until


# ── STATISTIKA ─────────────────────────────────────────

def get_stats():
    conn = get_conn()
    today = datetime.date.today().isoformat()
    stats = {
        "users":       conn.execute("SELECT COUNT(*) as c FROM users").fetchone()["c"],
        "movies":      conn.execute("SELECT COUNT(*) as c FROM movies WHERE is_active=1").fetchone()["c"],
        "today_views": conn.execute("SELECT COUNT(*) as c FROM views WHERE viewed_at LIKE ?",
                                    (f"{today}%",)).fetchone()["c"],
        "total_views": conn.execute("SELECT COUNT(*) as c FROM views").fetchone()["c"],
    }
    conn.close()
    return stats


# ── SOZLAMA ────────────────────────────────────────────

def get_setting(key):
    conn = get_conn()
    row = conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    conn.close()
    return row["value"] if row else None


def set_setting(key, value):
    conn = get_conn()
    conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?,?)", (key, value))
    conn.commit()
    conn.close()


# ── XABARLAR (INBOX) ───────────────────────────────────

def save_message(uid, full_name, message):
    conn = get_conn()
    conn.execute("INSERT INTO messages (user_id, full_name, message) VALUES (?,?,?)",
                 (uid, full_name, message))
    conn.commit()
    conn.close()


def get_messages(limit=30):
    conn = get_conn()
    rows = conn.execute("SELECT * FROM messages ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    conn.close()
    return rows
