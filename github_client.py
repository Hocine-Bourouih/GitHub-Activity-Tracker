"""
Client GitHub — ingestion incrémentale avec pagination.

Points clés pour l'entretien :
- Pagination : GitHub renvoie max 100 résultats par page,
  on suit le header "Link" ou on incrémente ?page jusqu'à réponse vide.
- Ingestion incrémentale : on passe "since" pour ne récupérer
  que les données nouvelles depuis la dernière sync.
- Rate limiting : 60 req/h sans token, 5000 avec token.
"""

import requests
from database import get_connection, get_last_sync, update_last_sync

BASE_URL = "https://api.github.com"


def _headers(token: str | None = None) -> dict:
    h = {"Accept": "application/vnd.github.v3+json"}
    if token:
        h["Authorization"] = f"token {token}"
    return h


def _paginate(url: str, params: dict, token: str | None = None) -> list[dict]:
    """
    Récupère toutes les pages d'un endpoint GitHub.
    GitHub pagine à 100 résultats max par page.
    """
    params["per_page"] = 100
    params["page"] = 1
    all_results = []

    while True:
        resp = requests.get(url, headers=_headers(token), params=params)
        resp.raise_for_status()
        data = resp.json()
        if not data:
            break
        all_results.extend(data)
        params["page"] += 1

    return all_results


def sync_repo(full_name: str, token: str | None = None) -> int:
    """
    Ajoute ou met à jour les infos de base d'un repo.
    Retourne le repo_id en base.
    """
    resp = requests.get(f"{BASE_URL}/repos/{full_name}", headers=_headers(token))
    resp.raise_for_status()
    data = resp.json()

    conn = get_connection()
    conn.execute(
        """INSERT INTO repos (id, full_name, description, stars_count, forks_count, language, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?)
           ON CONFLICT(id) DO UPDATE SET
               description = excluded.description,
               stars_count = excluded.stars_count,
               forks_count = excluded.forks_count,
               language    = excluded.language,
               updated_at  = excluded.updated_at""",
        (
            data["id"],
            data["full_name"],
            data.get("description"),
            data["stargazers_count"],
            data["forks_count"],
            data.get("language"),
            data["updated_at"],
        ),
    )
    conn.commit()
    conn.close()
    return data["id"]


def sync_commits(repo_id: int, full_name: str, token: str | None = None):
    """Récupère les commits de manière incrémentale (paramètre since)."""
    params = {}
    last_sync = get_last_sync(repo_id, "commits")
    if last_sync:
        params["since"] = last_sync  # ingestion incrémentale

    commits = _paginate(f"{BASE_URL}/repos/{full_name}/commits", params, token)

    conn = get_connection()
    for c in commits:
        commit_data = c.get("commit", {})
        conn.execute(
            """INSERT OR IGNORE INTO commits (sha, repo_id, message, author, date)
               VALUES (?, ?, ?, ?, ?)""",
            (
                c["sha"],
                repo_id,
                commit_data.get("message", ""),
                commit_data.get("author", {}).get("name", "unknown"),
                commit_data.get("author", {}).get("date"),
            ),
        )
    conn.commit()
    conn.close()
    update_last_sync(repo_id, "commits")
    return len(commits)


def sync_issues(repo_id: int, full_name: str, token: str | None = None):
    """Récupère les issues (incrémental via since, state=all)."""
    params = {"state": "all"}
    last_sync = get_last_sync(repo_id, "issues")
    if last_sync:
        params["since"] = last_sync

    issues = _paginate(f"{BASE_URL}/repos/{full_name}/issues", params, token)

    conn = get_connection()
    for issue in issues:
        # L'API GitHub mélange issues et pull requests, on filtre les PRs
        if "pull_request" in issue:
            continue
        conn.execute(
            """INSERT INTO issues (id, repo_id, number, title, state, author, created_at, closed_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(id) DO UPDATE SET
                   state     = excluded.state,
                   closed_at = excluded.closed_at""",
            (
                issue["id"],
                repo_id,
                issue["number"],
                issue["title"],
                issue["state"],
                issue["user"]["login"],
                issue["created_at"],
                issue.get("closed_at"),
            ),
        )
    conn.commit()
    conn.close()
    update_last_sync(repo_id, "issues")
    return len(issues)


def sync_stargazers(repo_id: int, full_name: str, token: str | None = None):
    """Récupère les stargazers avec leur date de star."""
    headers = _headers(token)
    headers["Accept"] = "application/vnd.github.v3.star+json"

    params = {"per_page": 100, "page": 1}
    all_stars = []
    while True:
        resp = requests.get(
            f"{BASE_URL}/repos/{full_name}/stargazers",
            headers=headers,
            params=params,
        )
        resp.raise_for_status()
        data = resp.json()
        if not data:
            break
        all_stars.extend(data)
        params["page"] += 1

    conn = get_connection()
    for star in all_stars:
        conn.execute(
            """INSERT OR IGNORE INTO stargazers (repo_id, username, starred_at)
               VALUES (?, ?, ?)""",
            (repo_id, star["user"]["login"], star.get("starred_at")),
        )
    conn.commit()
    conn.close()
    update_last_sync(repo_id, "stargazers")
    return len(all_stars)
