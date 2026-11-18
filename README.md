# Tribute Show Planner

A playlist checker for live concerts. A tribute act keeps a catalogue of
songs and outfits, puts songs in order for a show, and the app reports what
is wrong with that order: running time over the limit, outfit changes
without a long enough break, poor energy pacing, and retired or repeated
songs.

It runs as two services, each a Flask app served by waitress with its own
SQLite database (ADR-6 in `ADR.md`):

- **Catalogue** (`services/catalogue/`): songs and outfits, as a JSON API
  at http://localhost:8001/api/. Owns the `outfits` and `songs` tables.
- **Shows** (`services/shows/`): shows, ordered setlists and the setlist
  checks (`shows/rules.py`), as a JSON API at http://localhost:8002/api/.
  Owns the `shows` and `setlist_items` tables.

The shows service gets song details only from the catalogue's JSON API,
over HTTP:

| Endpoint | Returns |
|----------|---------|
| `GET /api/songs?ids=3,7` | The songs with these ids (unknown ids are left out) |
| `GET /api/songs/active` | The songs that can be added to a setlist |
| `GET /health` (both services) | `{"status": "ok"}` |

The rest of the catalogue API is for the browser. Errors are
`{"errors": ["message", ...]}`: 400 for invalid values (every field error
at once), 404 for an unknown id, 409 for removing an outfit songs use.

| Endpoint | Returns |
|----------|---------|
| `GET /api/songs/all` | Every song, active first, with `duration` as `"4:54"` |
| `GET /api/songs/{id}` | One song (404 if unknown) |
| `POST /api/songs` | 201 and the new song, or 400 |
| `PUT /api/songs/{id}` | The saved song, 400 or 404 |
| `POST /api/songs/{id}/retire`, `/reactivate` | The song, or 404 |
| `GET /api/outfits` | Every outfit, with `song_count` |
| `POST /api/outfits` | 201 and the new outfit, or 400 |
| `PUT /api/outfits/{id}` | The saved outfit, 400 or 404 |
| `DELETE /api/outfits/{id}` | 204, 404, or 409 if songs (also retired ones) use it |

The shows API, also for the browser, with the same error shape. Every
change to a setlist answers with the show's new **overview**: the show,
its setlist with song details, the running time and the check results.
If the catalogue is down, the overview is still 200, with
`catalogue_available: false`, song details `null` and the checks skipped
(`problems: null`); adding a song is then refused with 503.

| Endpoint | Returns |
|----------|---------|
| `GET /api/shows` | Every show, soonest first |
| `POST /api/shows` | 201 and the new show, or 400 |
| `GET /api/shows/{id}` | The overview, or 404 |
| `PUT /api/shows/{id}` | The new overview, 400 or 404 |
| `DELETE /api/shows/{id}` | 204 (its setlist is deleted too) or 404 |
| `POST /api/shows/{id}/songs` | 201 and the overview, 400, 404, or 503 if the catalogue is down |
| `POST /api/shows/{id}/breaks` | 201 and the overview, 400 or 404 |
| `POST /api/shows/{id}/items/{item_id}/move` | `{"direction": "up"}` or `"down"`: the overview, 400 or 404 |
| `DELETE /api/shows/{id}/items/{item_id}` | The overview, or 404 |

## Run locally

You need Docker with Docker Compose. From the repository root:

```
docker compose up --build
```

The JSON APIs are then at http://localhost:8001/api/ (catalogue) and
http://localhost:8002/api/ (shows), e.g. http://localhost:8001/api/songs/all.
Stop with Ctrl+C. `docker compose down` removes the containers;
the data stays in the `sqlserver-data` volume until you run
`docker compose down -v`.

There is no other setup step and no `.env` file is needed. Compose starts
SQL Server, `db-init` runs `db/init.sql` (databases and logins), then each
service applies its pending migrations (`services/<name>/migrations/`). If the catalogue is empty,
it also adds a demo catalogue (`seed.py`): 7 outfits and 20 songs, with one
song already retired. A catalogue that already has data is never changed.

### Without Docker (for development)

Each service runs on its own with Python 3.10 or newer (developed with
3.14). In two terminals, with a virtual environment active:

```
cd services/catalogue
pip install -r requirements.txt
$env:PORT = "8001"; python app/main.py      # macOS/Linux: PORT=8001 python app/main.py
```

```
cd services/shows
pip install -r requirements.txt
$env:PORT = "8002"; python app/main.py      # macOS/Linux: PORT=8002 python app/main.py
```

## Configuration

Everything is set through environment variables with defaults.
`docker-compose.yml` sets the ones the containers need; `.env.example`
lists the ones you may want to change.

| Variable | Service | Default | What it does |
|----------|---------|---------|--------------|
| `PORT` | both | `8000` | Port the server listens on. It always binds to `0.0.0.0`. |
| `DATABASE_URL` | both | none (required, holds a password) | `mssql://user:password@host:1433/database`. Compose sets it with a local-only password. |
| `DB_CONNECT_ATTEMPTS` | both | `8` | Connection attempts, with waits of 1, 2, 4, 8, 15... s between them (about a minute). |
| `DB_LOGIN_TIMEOUT_SECONDS` | both | `10` | Seconds one connection attempt may take. |
| `CATALOGUE_URL` | shows | `http://localhost:8001` | Where shows calls the catalogue API. Compose sets `http://catalogue:8000`. |
| `CATALOGUE_TIMEOUT` | shows | `5` | Seconds to wait for the catalogue. |
| `CORS_ORIGINS` | both | `http://localhost:8080` | Comma-separated origins whose pages may call the API from the browser. Empty allows none. |

## Tests and coverage

Each service has its own tests in its `tests/` folder. The database tests
run on that service's `_test` database (`catalogue_test`, `shows_test`) in
the compose SQL Server, emptied before every test; start it first with
`docker compose up -d sqlserver db-init`. The shows tests never call the
real catalogue: they use a fake one (the `catalogue` fixture in
`services/shows/tests/conftest.py`).

The test tools are in each service's `requirements-dev.txt`, which also
installs `requirements.txt`. The images only install `requirements.txt`.

```
cd services/catalogue
pip install -r requirements-dev.txt
python -m pytest --cov=app --cov-report=term-missing
cd ../shows
pip install -r requirements-dev.txt
python -m pytest --cov=app --cov-report=term-missing
```

Result on 2026-11-18:

| Service | Tests | Coverage |
|---------|-------|----------|
| catalogue | 149 passed | 99% |
| shows | 150 passed | 99% |

Since the pages became JSON APIs (18 Nov), each service's `tests/test_api.py`
tests every endpoint and status code through Flask's test client, so
`api.py` is covered too, not only the rules and services (ADR-4).

## Assignment 1 container contract check (§7)

This is the evidence for the single-container version of the app from
Assignment 1, before the split. Output of the provided `run.sh`, run on
2026-10-12:

```
=== SDD Assignment 1 contract check ===
Repository: /c/Users/Fernando/SoftwareandDevops/tribute-show-planner

==> Repository shape
  PASS  one Dockerfile, one manifest (requirements.txt)

==> Build from a clean context, no build args
  PASS  image built
  PASS  image size 220 MB

==> Start on PORT=8000 and reach it from the host
  PASS  HTTP 302 from http://localhost:8000/

==> SQLite file under DATA_DIR
  PASS  found in /data: tribute.db

==> Data persists, and a second boot does not re-seed
  PASS  volume at /data persists
  PASS  row counts unchanged across restart: outfits=7 setlist_items=0 shows=0 songs=20

==> PORT override is honoured (not hardcoded)
  PASS  HTTP 302 from http://localhost:9123/

=== ALL CHECKS PASSED ===
Paste this output into your README as the §7 evidence.
```

Notes:

- In the original output the row-counts line was garbled by Windows line
  endings. The line above shows the real counts: `outfits=7
  setlist_items=0 shows=0 songs=20`.
- I ran it in Git Bash on Windows. The script calls `mktemp -t sdd-check`,
  and GNU `mktemp` (the one in Git Bash) needs X's in the template to
  replace with random characters. So I defined a `mktemp` shell function
  that adds `XXXXXX` to the template, then ran the script unchanged.

## Project files

- `docker-compose.yml`: starts both services, one volume each.
- `.env.example`: the optional settings for compose.
- `services/<name>/Dockerfile`, `.dockerignore`, `requirements.txt`: how
  each image is built. Only `app/` is copied into the image.
- `services/<name>/requirements-dev.txt`: pytest and pytest-cov, for the
  tests only.
- `services/<name>/app/main.py`: builds the Flask app and starts waitress.
- `services/<name>/app/config.py`: reads that service's settings.
- `services/<name>/app/db.py` and `schema.sql`: SQLite connections and the
  tables that service owns.
- `services/catalogue/app/seed.py`: the demo catalogue.
- `services/catalogue/app/catalogue/`: `api.py` (the JSON API, for the
  browser and the shows service), `service.py` (rules and validation),
  `repository.py` (SQL).
- `services/shows/app/shows/`: `api.py` (the JSON API), `service.py`,
  `repository.py`, `rules.py` (the six setlist checks) and
  `catalogue_client.py` (the HTTP calls to the catalogue).
- `services/<name>/app/cors.py`: the CORS headers for `CORS_ORIGINS`
  (the same file in both services).
- `docs/diagrams.md`: architecture and database diagrams (still show the
  single-app version).
- `ADR.md`: architecture decisions. `AI_USAGE.md`: AI usage log.
