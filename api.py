"""
API FastAPI — expose les statistiques collectées.

Endpoints :
  GET /repos                          → liste des repos suivis
  GET /repos/{owner}/{repo}/stats     → stats agrégées d'un repo
  GET /repos/{owner}/{repo}/commits   → commits paginés
  GET /repos/{owner}/{repo}/issues    → issues avec filtre par state
"""

from fastapi import FastAPI, HTTPException, Query
from database import get_connection, init_db

app = FastAPI(title="GitHub Activity Tracker")


@app.on_event("startup")
def startup():
    init_db()


# ---------- Liste des repos suivis ----------

@app.get("/repos")
def list_repos():
    conn = get_connection()
    rows = conn.execute("SELECT * FROM repos ORDER BY stars_count DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ---------- Stats agrégées ----------

@app.get("/repos/{owner}/{repo}/stats")
def repo_stats(owner: str, repo: str):
    full_name = f"{owner}/{repo}"
    conn = get_connection()

    r = conn.execute("SELECT * FROM repos WHERE full_name = ?", (full_name,)).fetchone()
    if not r:
        conn.close()
        raise HTTPException(404, "Repo non trouvé. Lance d'abord une sync.")

    repo_id = r["id"]

    total_commits = conn.execute(
        "SELECT COUNT(*) as cnt FROM commits WHERE repo_id = ?", (repo_id,)
    ).fetchone()["cnt"]

    open_issues = conn.execute(
        "SELECT COUNT(*) as cnt FROM issues WHERE repo_id = ? AND state = 'open'",
        (repo_id,),
    ).fetchone()["cnt"]

    closed_issues = conn.execute(
        "SELECT COUNT(*) as cnt FROM issues WHERE repo_id = ? AND state = 'closed'",
        (repo_id,),
    ).fetchone()["cnt"]

    top_authors = conn.execute(
        """SELECT author, COUNT(*) as commit_count
           FROM commits WHERE repo_id = ?
           GROUP BY author ORDER BY commit_count DESC LIMIT 5""",
        (repo_id,),
    ).fetchall()

    last_sync = conn.execute(
        "SELECT sync_type, last_sync FROM sync_history WHERE repo_id = ?",
        (repo_id,),
    ).fetchall()

    conn.close()

    return {
        "repo": full_name,
        "stars": r["stars_count"],
        "forks": r["forks_count"],
        "language": r["language"],
        "total_commits": total_commits,
        "open_issues": open_issues,
        "closed_issues": closed_issues,
        "top_authors": [dict(a) for a in top_authors],
        "last_syncs": {s["sync_type"]: s["last_sync"] for s in last_sync},
    }


# ---------- Commits paginés ----------

@app.get("/repos/{owner}/{repo}/commits")
def list_commits(
    owner: str,
    repo: str,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
):
    full_name = f"{owner}/{repo}"
    conn = get_connection()

    r = conn.execute("SELECT id FROM repos WHERE full_name = ?", (full_name,)).fetchone()
    if not r:
        conn.close()
        raise HTTPException(404, "Repo non trouvé.")

    offset = (page - 1) * per_page
    rows = conn.execute(
        """SELECT sha, message, author, date FROM commits
           WHERE repo_id = ? ORDER BY date DESC LIMIT ? OFFSET ?""",
        (r["id"], per_page, offset),
    ).fetchall()
    conn.close()

    return {"page": page, "per_page": per_page, "commits": [dict(c) for c in rows]}


# ---------- Issues avec filtre ----------

@app.get("/repos/{owner}/{repo}/issues")
def list_issues(
    owner: str,
    repo: str,
    state: str = Query("all", regex="^(open|closed|all)$"),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
):
    full_name = f"{owner}/{repo}"
    conn = get_connection()

    r = conn.execute("SELECT id FROM repos WHERE full_name = ?", (full_name,)).fetchone()
    if not r:
        conn.close()
        raise HTTPException(404, "Repo non trouvé.")

    offset = (page - 1) * per_page
    if state == "all":
        rows = conn.execute(
            """SELECT number, title, state, author, created_at, closed_at
               FROM issues WHERE repo_id = ?
               ORDER BY created_at DESC LIMIT ? OFFSET ?""",
            (r["id"], per_page, offset),
        ).fetchall()
    else:
        rows = conn.execute(
            """SELECT number, title, state, author, created_at, closed_at
               FROM issues WHERE repo_id = ? AND state = ?
               ORDER BY created_at DESC LIMIT ? OFFSET ?""",
            (r["id"], state, per_page, offset),
        ).fetchall()

    conn.close()
    return {"page": page, "per_page": per_page, "state": state, "issues": [dict(i) for i in rows]}
