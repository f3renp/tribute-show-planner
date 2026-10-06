-- Tables for both domains. IF NOT EXISTS makes this safe to run on
-- every startup: existing tables and their data are left alone.

-- Catalogue domain ------------------------------------------------------

CREATE TABLE IF NOT EXISTS outfits (
    id             INTEGER PRIMARY KEY,
    name           TEXT    NOT NULL UNIQUE,
    change_seconds INTEGER NOT NULL CHECK (change_seconds >= 0)
);

CREATE TABLE IF NOT EXISTS songs (
    id               INTEGER PRIMARY KEY,
    title            TEXT    NOT NULL,
    album            TEXT    NOT NULL,
    year             INTEGER NOT NULL,
    duration_seconds INTEGER NOT NULL CHECK (duration_seconds > 0),
    energy           INTEGER NOT NULL CHECK (energy BETWEEN 1 AND 5),
    kind             TEXT    NOT NULL CHECK (kind IN ('dance', 'ballad')),
    outfit_id        INTEGER NOT NULL REFERENCES outfits (id),
    active           INTEGER NOT NULL DEFAULT 1,
    UNIQUE (title, album)
);

-- Show builder domain ---------------------------------------------------

CREATE TABLE IF NOT EXISTS shows (
    id          INTEGER PRIMARY KEY,
    name        TEXT    NOT NULL,
    venue       TEXT    NOT NULL,
    show_date   TEXT    NOT NULL,
    max_minutes INTEGER NOT NULL CHECK (max_minutes > 0)
);

-- song_id has no REFERENCES to songs on purpose: the show builder only
-- stores the ID and asks the catalogue for song details, so the two
-- domains share no foreign key.
CREATE TABLE IF NOT EXISTS setlist_items (
    id            INTEGER PRIMARY KEY,
    show_id       INTEGER NOT NULL REFERENCES shows (id) ON DELETE CASCADE,
    position      INTEGER NOT NULL,
    item_type     TEXT    NOT NULL CHECK (item_type IN ('song', 'break')),
    song_id       INTEGER,
    break_label   TEXT,
    break_seconds INTEGER,
    UNIQUE (show_id, position)
);
