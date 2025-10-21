"""
Point d'entrée — deux commandes :
  python main.py sync  owner/repo [--token TOKEN]   → collecte les données
  python main.py serve [--port 8000]                 → lance l'API FastAPI
"""

import argparse
import sys
import uvicorn
from database import init_db
from github_client import sync_repo, sync_commits, sync_issues, sync_stargazers


def run_sync(full_name: str, token: str | None = None):
    print(f"--- Sync du repo : {full_name} ---")

    repo_id = sync_repo(full_name, token)
    print(f"  Repo info OK (id={repo_id})")

    nb_commits = sync_commits(repo_id, full_name, token)
    print(f"  Commits : {nb_commits} récupérés")

    nb_issues = sync_issues(repo_id, full_name, token)
    print(f"  Issues  : {nb_issues} récupérées")

    nb_stars = sync_stargazers(repo_id, full_name, token)
    print(f"  Stars   : {nb_stars} récupérées")

    print("--- Sync terminée ---")


def main():
    parser = argparse.ArgumentParser(description="GitHub Activity Tracker")
    sub = parser.add_subparsers(dest="command")

    # Commande sync
    sync_parser = sub.add_parser("sync", help="Collecter les données d'un repo")
    sync_parser.add_argument("repo", help="Repo au format owner/repo")
    sync_parser.add_argument("--token", help="GitHub personal access token (optionnel)")

    # Commande serve
    serve_parser = sub.add_parser("serve", help="Lancer l'API FastAPI")
    serve_parser.add_argument("--port", type=int, default=8000)

    args = parser.parse_args()

    if args.command == "sync":
        init_db()
        run_sync(args.repo, args.token)
    elif args.command == "serve":
        uvicorn.run("api:app", host="0.0.0.0", port=args.port, reload=True)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
