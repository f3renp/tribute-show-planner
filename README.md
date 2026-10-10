# Tribute Show Planner

A playlist checker for live concerts. A tribute act keeps a catalogue of
songs and outfits, puts songs in order for a show, and the app reports what
is wrong with that order: running time over the limit, outfit changes
without a long enough break, poor energy pacing, and retired or repeated
songs.

It is one Flask app, served by waitress, with one SQLite database. It has
two parts that only talk through `catalogue/service.py`:

- **Catalogue** (`catalogue/`): songs and outfits, at `/catalogue/`.
- **Show builder** (`shows/`): shows, ordered setlists and the setlist
  checks (`shows/rules.py`), at `/shows/`.

## Requirements

- Python 3.10 or newer (developed with Python 3.14).
- The packages in `requirements.txt`, the only dependency manifest.

## Setup and run

Run these from the repository root. Choose one of the two ways.

### With plain Python and pip

```
python -m venv .venv
```

Activate the virtual environment:

- Windows PowerShell: `.venv\Scripts\Activate.ps1`
- macOS or Linux: `source .venv/bin/activate`

Then install and start:

```
pip install -r requirements.txt
python app.py
```

### With uv

```
uv venv
uv pip install -r requirements.txt
uv run python app.py
```

Either way, open http://localhost:8000 in a browser. Stop the app with
Ctrl+C.

There is no other setup step. At startup the app creates the data folder
and the tables if they are missing. If the catalogue is empty, it also adds
a demo catalogue (`seed.py`): 7 outfits and 20 songs, with one song
already retired. A catalogue that already has data is never changed.

## Configuration

Everything is set through environment variables. All of them are optional
and no `.env` file is needed.

| Variable   | Default | What it does |
|------------|---------|--------------|
| `PORT`     | `8000`  | Port the server listens on. It always binds to `0.0.0.0`. |
| `DATA_DIR` | `data`  | Folder for the SQLite file. The database is `DATA_DIR/tribute.db`. |

A relative `DATA_DIR` is relative to the folder the app is started from, so
start it from the repository root. The default database is
`data/tribute.db`.

Example, Windows PowerShell:

```
$env:PORT = "5000"; $env:DATA_DIR = "C:\tribute-data"; python app.py
```

Example, macOS or Linux:

```
PORT=5000 DATA_DIR=/tmp/tribute-data python app.py
```

## Tests and coverage

The tests are in `tests/`. The database tests each run on a new temporary
SQLite file, so they never touch `data/tribute.db`.

```
python -m pytest --cov=. --cov-report=term-missing
```

With uv: `uv run python -m pytest --cov=. --cov-report=term-missing`

`.coveragerc` leaves the `tests/` folder out of the measurement, so the
total is for the app code only.

Result on 2026-10-10: **144 passed, 77% total coverage.**

| File | Coverage |
|------|----------|
| `shows/rules.py` (the six setlist checks) | 100% |
| `catalogue/service.py` | 100% |
| `shows/service.py` | 99% |
| `catalogue/repository.py`, `shows/repository.py`, `db.py`, `config.py` | 100% |
| `seed.py` | 93% |
| `catalogue/routes.py`, `shows/routes.py`, `app.py` | 0% |

The routes and `app.py` are left untested on purpose: they hold no rules
and only call the services. See ADR-4 in `ADR.md`.

## Project files

- `app.py`: builds the Flask app and starts waitress.
- `config.py`: reads `PORT` and `DATA_DIR`.
- `db.py` and `schema.sql`: SQLite connections and the tables.
- `seed.py`: the demo catalogue.
- `catalogue/`, `shows/`: the two domains, each split into `routes.py`
  (pages), `service.py` (rules and validation) and `repository.py` (SQL).
- `templates/`, `static/`: HTML templates and CSS.
- `ADR.md`: architecture decisions. `AI_USAGE.md`: AI usage log.
