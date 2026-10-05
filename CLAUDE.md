# Tribute Show Planner

Individual Assignment 1 for Software and DevOps (IE University). The full brief is in `assignment_1.md`. Read it completely before doing anything. When this file and the brief disagree, the brief wins.

- Student: Fer (GitHub user `f3renp`)
- Deadline: 2026-10-12 23:59 (extended; the brief still shows the old date)
- Repo: `f3renp/tribute-show-planner`
- Local folder: `C:\Users\Fernando\SoftwareandDevops\tribute-show-planner`

## How to work with me

A closed-book written check multiplies my grade: I have to explain my own code on paper, with no notes. Code I don't understand costs me marks, so understanding matters more than speed.

- Go one small step at a time and wait for my confirmation before the next one.
- Before writing code, say in plain language what it will do and why.
- Write at most about 40 new lines per step, then stop and walk me through them.
- Keep the code plain: small functions, clear names, no clever abstractions, no classes unless they remove real duplication.
- After each piece, ask me two or three questions about it (for example: "what does `check_outfit_changes` return when there is no problem?"). Correct my answers. Do not continue until I can answer.
- I have not used Flask before. Teach each Flask concept the first time it appears.
- Only do the current day's scope. If I ask to jump ahead, remind me of the commit rules first.
- Point out anything that breaks a constraint from the brief before I move on.

## Things only I write

- `AI_USAGE.md`, column "In my own words, how this works": I write it. You check it against the code and tell me what is vague or wrong. Never draft it for me.
- `ADR.md`: I draft Decision, Alternatives considered and Consequences. You check the format and challenge weak reasoning. Each entry is written on its planned day, never several at once.
- Every session with you is an AI interaction. Remind me to add its rows to `AI_USAGE.md` before the day's last commit.

## Git rules

- Do not run `git commit` or `git push`. Give me the command and I run it.
- Never backdate, change commit dates, rewrite history or fabricate commits. The brief treats that as an academic integrity violation.
- Commit messages describe what changed and why. Never "Initial commit", "WIP", "update" or "fix".
- I push at the end of every working day, because push timestamps are what gets checked.
- Targets: 12+ commits, 6+ distinct calendar days, no day above 40% of all commits, ADR entries spread over 3+ commit dates.

## Environment

- Windows, PowerShell, VS Code, `uv`.
- Setup: `uv venv`, then `uv pip install -r requirements.txt`.
- Run Python as `uv run python ...` (bare `python` may not resolve on this machine).
- Tests: `uv run python -m pytest`.
- Never run `uv init` or `uv add`: they create `pyproject.toml`, which would be a second manifest.
- PowerShell treats `<` and `>` as operators, so never put placeholder brackets in commands.
- `assignment_1.md` stays out of git: list it in `.gitignore`.

## Hard constraints from the brief

- Single process, single container, started by one documented command.
- SQLite only, at one documented path under `DATA_DIR`.
- Exactly one dependency manifest: `requirements.txt` at the repo root.
- No Dockerfile, `docker-compose.yml`, `.github/workflows/`, Terraform, Bicep or ARM.
- No public deployment, external database, cache, message broker or background job runner.
- Bind to `0.0.0.0`. Port from `PORT` with a default. All configuration through environment variables, with no required `.env` file.
- No interactive setup: tables are created automatically at startup.
- About 12 third-party packages at most, and 15 to 50 files.
- Unit tests on core business logic at 70% coverage or more, with the coverage command and result in the README.
- `ADR.md` has exactly 5 entries in the brief's format.

## The app

A playlist checker for live concerts. A Michael Jackson tribute act plans a show by putting songs in order, and the app reports what is wrong with that order.

Stakeholders (invented): the musical director, who maintains the catalogue, and the manager, who plans the shows.

**Domain 1, catalogue** (`catalogue/`): songs and outfits.

- `outfits`: id, name, change_seconds
- `songs`: id, title, album, year, duration_seconds, energy (1 to 5), kind (dance or ballad), outfit_id, active
- Logic: validation (energy range, sane duration, no duplicate title and album), duration parsing ("4:54" to seconds and back), retire and reactivate.

**Domain 2, show builder** (`shows/`): shows and ordered setlists.

- `shows`: id, name, venue, show_date, max_minutes
- `setlist_items`: id, show_id, position, item_type (song or break), song_id, break_label, break_seconds
- Logic: add, remove and reorder items, plus the checks below.

**The checks**, one small pure function each, in `shows/rules.py`:

1. Running time over the show's limit.
2. Outfit change between two songs without a long enough break.
3. More than two high-energy songs (energy 4 or 5) in a row.
4. Two ballads in a row.
5. Opener or closer that is not high energy.
6. A retired song, or the same song twice.

**The seam:** `setlist_items` stores only `song_id`. The show builder gets song details through one catalogue function (for example `get_songs_by_ids`) and never queries `songs` or `outfits` itself. No SQL joins across the two domains.

## Decisions already taken

These came out of an AI brainstorming session in claude.ai on 2026-10-05. They belong in `AI_USAGE.md`, and I can still change any of them.

- Stack (proposed, confirm with me first): Flask, built-in `sqlite3`, `waitress` as the server, `pytest`, `pytest-cov`.
- Songs are retired, never deleted, so the catalogue does not need to know about shows.
- Server-rendered templates with plain HTML and CSS. Reordering uses up and down buttons.
- No login (planned as ADR-5, the thing deliberately not built).
- Metadata only: no lyrics, audio or cover art in the repo.

## Target layout

```
app.py  config.py  db.py  schema.sql  seed.py
catalogue/   __init__.py  repository.py  service.py  routes.py
shows/       __init__.py  repository.py  service.py  rules.py  routes.py
templates/   static/style.css   tests/
requirements.txt  pytest.ini  README.md  ADR.md  AI_USAGE.md  .gitignore  CLAUDE.md
```

## Plan

Three commits per day. If a day is missed, shift the work, keep every day at 40% of commits or less, and still reach 6 distinct days by 12 Oct.

**Day 1, Mon 5 Oct: pitch and setup.** No feature code before the professor approves the idea.
- I send the pitch below. `git init`, create the empty GitHub repo, add the remote.
- Add project skeleton with README, gitignore and Flask requirements
- Record ADR-1: choose Flask and built-in sqlite3 over FastAPI and Django
- Start AI usage log with the idea brainstorming entries

**Day 2, Tue 6 Oct: app skeleton and database.**
- Add config module reading PORT and DATA_DIR from the environment
- Create SQLite schema and initialise the database on startup
- Record ADR-2: keep catalogue and show builder as separate packages

**Day 3, Wed 7 Oct: catalogue.**
- Implement song and outfit validation with duration parsing
- Add catalogue pages to list, add, edit and retire songs
- Add unit tests for catalogue validation and duration parsing

**Day 4, Thu 8 Oct: shows and setlists.**
- Add shows and ordered setlist items with reordering
- Add show pages to build a setlist from the catalogue
- Record ADR-3: setlist items reference songs by ID only

**Day 5, Fri 9 Oct: the checks.**
- Implement setlist checks for running time and outfit changes (with tests)
- Add energy pacing, opener and closer, and retired song checks (with tests)
- Display check results on the show page

**Day 6, Sat 10 Oct: testing and coverage.**
- Add service tests using a temporary SQLite database
- Seed the demo catalogue when the database is empty
- Record ADR-4: test rules and services first, keep routes thin

**Day 7, Sun 11 Oct: documentation and report.**
- Record ADR-5: no login in this version
- Document setup, environment variables and coverage result in README
- Add architecture and database diagrams matching the code

**Day 8, Mon 12 Oct: buffer and submission.**
- Clone into a fresh folder and run from zero to prove the README works.
- Finish the 4-5 page report (SDLC model, both diagrams, AI disclosure statement).
- Check `ADR.md` has exactly 5 entries, then submit.

## Pitch for the professor

> Tribute Show Planner: a tool for tribute acts to plan live shows. Domain 1 is a song catalogue (songs, outfits, validation). Domain 2 is a show builder that stores ordered setlists and checks them against rules: running time, costume-change breaks, energy pacing. Both persist in SQLite. The show builder reads the catalogue through a single function, which is where the future service split would go. Stack: Python and Flask.

## Status

Update this section at the end of every session.

- Idea approved by the professor: no, pitch not sent yet
- Stack confirmed by Fer: no
- Last finished: nothing, Day 1 not started
- Commits so far: 0
