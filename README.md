# GitHub Activity Tracker

Pipeline de données qui collecte l'activité de repos GitHub publics (commits, stars, issues) et expose les stats via une API FastAPI.

## Stack

Python, requests, FastAPI, SQLite, uvicorn

## Installation

```bash
pip install -r requirements.txt
```

## Utilisation

### 1. Collecter les données d'un repo

```bash
python main.py sync fastapi/fastapi
# Avec un token GitHub (recommandé, limite de 5000 req/h au lieu de 60) :
python main.py sync fastapi/fastapi --token ghp_xxx
```

### 2. Lancer l'API

```bash
python main.py serve
# ou sur un port custom :
python main.py serve --port 3000
```

### 3. Endpoints disponibles

| Endpoint | Description |
|---|---|
| `GET /repos` | Liste des repos suivis |
| `GET /repos/{owner}/{repo}/stats` | Stats agrégées (commits, issues, top auteurs) |
| `GET /repos/{owner}/{repo}/commits?page=1&per_page=20` | Commits paginés |
| `GET /repos/{owner}/{repo}/issues?state=open&page=1` | Issues avec filtre par état |

## Architecture

```
main.py            → Point d'entrée (CLI)
github_client.py   → Ingestion GitHub (pagination + incrémental)
database.py        → Modèle SQLite (tables normalisées)
api.py             → API FastAPI (endpoints REST)
```

## Concepts clés

- **Ingestion incrémentale** : le paramètre `since` évite de re-télécharger les données déjà collectées
- **Pagination** : GitHub limite à 100 résultats par page, on boucle jusqu'à réponse vide
- **Tables normalisées** : repos, commits, issues et stargazers dans des tables séparées avec clés étrangères
- **Batch vs temps réel** : ici c'est du batch (on lance `sync` manuellement), un système temps réel utiliserait les webhooks GitHub
