-- 001: the shows tables, ported from the SQLite schema.sql to T-SQL.
-- Applied once by app/migrate.py and recorded in schema_migrations.
-- Never edit this file once it has been applied: add 002_... instead.
--
-- SQLite -> SQL Server:
--   INTEGER PRIMARY KEY  -> INT IDENTITY(1,1) PRIMARY KEY (SQL Server numbers rows)
--   TEXT                 -> NVARCHAR(n) (Unicode, with a size)
--   show_date TEXT       -> DATE (the form sends YYYY-MM-DD, which SQL Server
--                           always reads the same way for a DATE)
-- Constraints have names, so a later migration can drop or change them.

CREATE TABLE shows (
    id          INT IDENTITY(1,1) NOT NULL PRIMARY KEY,
    name        NVARCHAR(200)     NOT NULL,
    venue       NVARCHAR(200)     NOT NULL,
    show_date   DATE              NOT NULL,
    max_minutes INT               NOT NULL,
    CONSTRAINT ck_shows_max_minutes CHECK (max_minutes > 0)
);

-- song_id has no FOREIGN KEY: songs live in the catalogue's database, and
-- SQL Server cannot check a key in another database. The show builder only
-- stores the id; shows/service.py asks the catalogue API whether the song
-- exists and is active before adding it (ADR-3, ADR-6).
CREATE TABLE setlist_items (
    id            INT IDENTITY(1,1) NOT NULL PRIMARY KEY,
    show_id       INT               NOT NULL,
    position      INT               NOT NULL,
    item_type     NVARCHAR(10)      NOT NULL,
    song_id       INT               NULL,
    break_label   NVARCHAR(100)     NULL,
    break_seconds INT               NULL,
    -- Deleting a show deletes its setlist with it.
    CONSTRAINT fk_setlist_items_show FOREIGN KEY (show_id)
        REFERENCES shows (id) ON DELETE CASCADE,
    CONSTRAINT uq_setlist_items_show_position UNIQUE (show_id, position),
    CONSTRAINT ck_setlist_items_type CHECK (item_type IN (N'song', N'break'))
);
