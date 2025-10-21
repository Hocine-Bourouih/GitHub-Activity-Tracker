"""
Base de données SQLite — tables normalisées pour stocker l'activité GitHub.

Tables :
- repos          : les repos qu'on suit
- commits        : historique des commits par repo
- issues         : issues ouvertes/fermées par repo
- stargazers     : utilisateurs ayant starré un repo
- sync_history   : dernière date de sync par repo+type (pour l'ingestion incrémentale)
"""

import sqlite3
from datetime import datetime

DB_PATH = "github_activity.db"


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # résultats accessibles par nom de colonne
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db():
    """Crée les tables si elles n'existent pas."""
    conn = get_connection()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS repos (
            id          INTEGER PRIMARY KEY,
            full_name   TEXT UNIQUE NOT NULL,   -- ex: "fastapi/fastapi"
            description TEXT,
            stars_count INTEGER DEFAULT 0,
            forks_count INTEGER DEFAULT 0,
            language    TEXT,
            updated_at  TEXT
        );

        CREATE TABLE IF NOT EXISTS commits (
            sha         TEXT PRIMARY KEY,
            repo_id     INTEGER NOT NULL REFERENCES repos(id),
            message     TEXT,
            author      TEXT,
            date        TEXT
        );

        CREATE TABLE IF NOT EXISTS issues (
            id          INTEGER PRIMARY KEY,
            repo_id     INTEGER NOT NULL REFERENCES repos(id),
            number      INTEGER,
            title       TEXT,
            state       TEXT,       -- "open" ou "closed"
            author      TEXT,
            created_at  TEXT,
            closed_at   TEXT
        );

        CREATE TABLE IF NOT EXISTS stargazers (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            repo_id     INTEGER NOT NULL REFERENCES repos(id),
            username    TEXT,
            starred_at  TEXT,
            UNIQUE(repo_id, username)
        );

        CREATE TABLE IF NOT EXISTS sync_history (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            repo_id     INTEGER NOT NULL REFERENCES repos(id),
            sync_type   TEXT NOT NULL,  -- "commits", "issues", "stargazers"
            last_sync   TEXT NOT NULL,
            UNIQUE(repo_id, sync_type)
        );
    """)
    conn.close()


def get_last_sync(repo_id: int, sync_type: str) -> str | None:
    """Retourne la date ISO de la dernière sync, ou None si jamais sync."""
    conn = get_connection()
    row = conn.execute(
        "SELECT last_sync FROM sync_history WHERE repo_id = ? AND sync_type = ?",
        (repo_id, sync_type),
    ).fetchone()
    conn.close()
    return row["last_sync"] if row else None


def update_last_sync(repo_id: int, sync_type: str):
    """Met à jour la date de dernière sync à maintenant."""
    conn = get_connection()
    now = datetime.utcnow().isoformat() + "Z"
    conn.execute(
        """INSERT INTO sync_history (repo_id, sync_type, last_sync)
           VALUES (?, ?, ?)
           ON CONFLICT(repo_id, sync_type) DO UPDATE SET last_sync = ?""",
        (repo_id, sync_type, now, now),
    )
    conn.commit()
    conn.close()
