# Diagrams

Written in Mermaid, so GitHub draws them when this file is opened. Each
one is kept small so it stays readable at full page width in the report.
They describe the system as deployed on 22 Nov 2026 (commit e6c8bc2 and
later), except the first one, which is Assignment 1.

## 1. Architecture before: the Assignment 1 monolith

One Flask app in one container, with server-rendered pages and one SQLite
file. The thick arrow is the seam: the only place where the show builder
used the catalogue, through two Python functions.

```mermaid
flowchart TD
    browser["Browser"] -->|"HTML pages"| app["Flask app (waitress)<br/>app.py"]

    subgraph catalogue["catalogue/ package"]
        croutes["routes.py<br/>song and outfit pages"] --> cservice["service.py<br/>validation, retire"]
        cservice --> crepo["repository.py"]
    end

    subgraph shows["shows/ package"]
        sroutes["routes.py<br/>show pages"] --> sservice["service.py<br/>setlist edits"]
        sroutes --> rules["rules.py<br/>six checks"]
        sservice --> srepo["repository.py"]
    end

    app --> croutes
    app --> sroutes
    sservice ==>|"seam: get_songs_by_ids()<br/>list_active_songs()"| cservice
    crepo --> sqlite[("SQLite: tribute.db<br/>all 4 tables")]
    srepo --> sqlite
```

## 2. Architecture after: two services, one database each

The UI is static files; the browser calls both services' JSON APIs, at
the URLs in `config.js`, and each service accepts browser calls only from
the UI's origin (`CORS_ORIGINS`). The thick arrow is the seam, now an HTTP
call from shows to the catalogue at `CATALOGUE_URL`, with a 5 s timeout.
No service reads the other's database.

```mermaid
flowchart TD
    browser["Browser"] -->|"loads pages + config.js"| ui["Static UI: ui/<br/>Azure: Storage static website<br/>local: nginx"]
    browser -->|"/api/songs, /api/outfits"| catalogue["catalogue service<br/>Flask, own container"]
    browser -->|"/api/shows"| shows["shows service<br/>Flask, own container"]

    shows ==>|"CATALOGUE_URL<br/>GET /api/songs?ids=<br/>GET /api/songs/active"| catalogue

    catalogue -->|"login catalogue_app"| catdb[("catalogue database<br/>outfits, songs")]
    shows -->|"login shows_app"| showsdb[("shows database<br/>shows, setlist_items")]
```

If the catalogue does not answer within 5 s, shows still serves the
overview from its own database, without song details and with the checks
skipped, and refuses to add songs (503).

## 3. Deployment

Every change goes through a pull request. A merge to `main` runs `cd.yml`,
which calls `ci.yml` again on that commit; on `main` its images job also
pushes the SHA-tagged images, and only then does `cd.yml` deploy them. The
pipeline signs in with OIDC as the managed identity: no password exists.
Everything on Azure is in `rg-fmedina-ieu2024` (swedencentral).

```mermaid
flowchart TD
    repo["GitHub: f3renp/tribute-show-planner"] -->|"push, pull request"| ci["ci.yml<br/>lint, tests 70%, validate,<br/>integration, build images"]
    repo -->|"merge to main"| cd["cd.yml<br/>CI, then deploy"]
    cd -->|"calls on main"| ci
    ci -->|"on main only:<br/>push :SHA"| ghcr["GHCR (the apps pull from here)<br/>ghcr.io/f3renp/tribute-catalogue<br/>ghcr.io/f3renp/tribute-shows"]
    cd -->|"OIDC sign-in"| mi

    subgraph rg["rg-fmedina-ieu2024"]
        mi["managed identity<br/>fmedina-ieu2024-github"]
        web["Storage fmedinaieu2024ui<br/>static website $web"]
        subgraph env["fmedina-ieu2024-env"]
            capp["fmedina-ieu2024-catalogue"]
            sapp["fmedina-ieu2024-shows"]
        end
        subgraph sql["fmedina-ieu2024-sql"]
            catdb[("fmedina-ieu2024-catalogue-db")]
            showsdb[("fmedina-ieu2024-shows-db")]
        end
        logs["Log Analytics workspace"]
    end

    mi -->|"ui/ + config.js"| web
    mi -->|"new image + secret"| env
    cd -.->|"GET /health until<br/>version = SHA"| env
    ghcr --> env
    capp --> catdb
    sapp --> showsdb
    env -->|"console logs"| logs
```

Each Container App runs 0 to 1 replicas; each database is serverless on
the free offer and pauses after 60 minutes without connections (ADR-8).

## 4. Databases, one per service

These match the migrations: catalogue `001_init.sql`; shows `001_init.sql`
and `002_add_show_status.sql`. `schema_migrations` is created by
`app/migrate.py` and records each applied file.

### Catalogue database

```mermaid
erDiagram
    outfits ||--o{ songs : "outfit_id (FK)"

    outfits {
        INT id PK
        NVARCHAR(100) name UK
        INT change_seconds "0 or more"
    }

    songs {
        INT id PK
        NVARCHAR(200) title UK "unique with album"
        NVARCHAR(200) album UK
        INT year
        INT duration_seconds "more than 0"
        INT energy "1 to 5"
        NVARCHAR(10) kind "dance or ballad"
        INT outfit_id FK
        INT active "1 active, 0 retired"
    }

    schema_migrations {
        NVARCHAR(100) version PK "001_init"
        DATETIME2 applied_at
    }
```

### Shows database

`setlist_items.song_id` is a plain ID with no foreign key: the songs are in
the catalogue's database, so shows checks the song over HTTP when it is
added (ADR-3, ADR-7). A break item has no `song_id`.

```mermaid
erDiagram
    shows ||--o{ setlist_items : "show_id (FK, ON DELETE CASCADE)"

    shows {
        INT id PK
        NVARCHAR(200) name
        NVARCHAR(200) venue
        DATE show_date
        INT max_minutes "more than 0"
        NVARCHAR(10) status "planned, confirmed or cancelled; default planned (002)"
    }

    setlist_items {
        INT id PK
        INT show_id FK
        INT position "unique with show_id"
        NVARCHAR(10) item_type "song or break"
        INT song_id "catalogue song ID, no FK; empty for a break"
        NVARCHAR(100) break_label
        INT break_seconds
    }

    schema_migrations {
        NVARCHAR(100) version PK "001_init, 002_add_show_status"
        DATETIME2 applied_at
    }
```
