# Diagrams

Both diagrams are written in Mermaid, so GitHub draws them when this file
is opened. They describe the code as it is in the repository.

## Architecture

One process: `python app.py` starts waitress, which serves the Flask app
built by `create_app()`. Arrows point from the file that calls to the file
it calls. The thick arrow is the seam, the only place where the show
builder uses the catalogue.

```mermaid
flowchart TD
    browser["Browser"] -->|"HTTP on PORT (0.0.0.0)"| waitress["waitress server"]
    waitress --> app["app.py<br/>create_app()"]
    app -->|"1. init_db()"| db
    app -->|"2. seed_demo_catalogue()"| seed["seed.py<br/>demo outfits and songs"]
    app -->|"registers blueprint"| croutes
    app -->|"registers blueprint"| sroutes

    subgraph catalogue["catalogue/ (domain 1: songs and outfits)"]
        croutes["routes.py<br/>song and outfit pages"] --> cservice["service.py<br/>validation, duration parsing,<br/>retire and reactivate"]
        croutes -->|"reads lists for pages"| crepo["repository.py<br/>SQL for songs and outfits"]
        cservice --> crepo
    end

    subgraph shows["shows/ (domain 2: shows and setlists)"]
        sroutes["routes.py<br/>show pages"] --> sservice["service.py<br/>add, remove, reorder items"]
        sroutes -->|"reads lists for pages"| srepo["repository.py<br/>SQL for shows and setlist_items"]
        sroutes -->|"check_setlist(), setlist_seconds(),<br/>is_over_limit()"| rules["rules.py<br/>six pure checks"]
        sservice --> srepo
        sservice -->|"format_duration()"| rules
    end

    sservice ==>|"the seam:<br/>get_songs_by_ids()<br/>list_active_songs()"| cservice
    seed -->|"writes: add_outfit(), add_song(), retire_song()"| cservice
    seed -->|"reads: is the catalogue empty, look up IDs"| crepo

    crepo --> db["db.py<br/>connections, init_db()"]
    srepo --> db
    db --> sqlite[("SQLite file<br/>DATA_DIR/tribute.db")]
    db -.->|"DATABASE_PATH"| config["config.py<br/>PORT, DATA_DIR<br/>from environment variables"]
    app -.->|"PORT"| config
```

## Database

Four tables in one SQLite file. Solid lines are real foreign keys. The
dashed line is not a foreign key: `setlist_items.song_id` stores only the
song's ID, and the show builder gets the song details through the
catalogue service (ADR-3). A break item has no `song_id`.

```mermaid
erDiagram
    outfits ||--o{ songs : "outfit_id (FK)"
    shows ||--o{ setlist_items : "show_id (FK, ON DELETE CASCADE)"
    songs |o..o{ setlist_items : "ID only, no FK"

    outfits {
        INTEGER id PK
        TEXT name UK
        INTEGER change_seconds "0 or more"
    }

    songs {
        INTEGER id PK
        TEXT title UK "unique together with album"
        TEXT album UK
        INTEGER year
        INTEGER duration_seconds "more than 0"
        INTEGER energy "1 to 5"
        TEXT kind "dance or ballad"
        INTEGER outfit_id FK
        INTEGER active "1 active, 0 retired"
    }

    shows {
        INTEGER id PK
        TEXT name
        TEXT venue
        TEXT show_date
        INTEGER max_minutes "more than 0"
    }

    setlist_items {
        INTEGER id PK
        INTEGER show_id FK
        INTEGER position "unique together with show_id"
        TEXT item_type "song or break"
        INTEGER song_id "ID only, no FK, empty for a break"
        TEXT break_label
        INTEGER break_seconds
    }
```
