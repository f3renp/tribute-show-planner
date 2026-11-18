-- 001: the catalogue tables, ported from the SQLite schema.sql to T-SQL.
-- Applied once by app/migrate.py and recorded in schema_migrations.
-- Never edit this file once it has been applied: add 002_... instead.
--
-- SQLite -> SQL Server:
--   INTEGER PRIMARY KEY  -> INT IDENTITY(1,1) PRIMARY KEY (SQL Server numbers rows)
--   TEXT                 -> NVARCHAR(n) (Unicode; a UNIQUE column needs a size)
-- Constraints have names, so a later migration can drop or change them.

CREATE TABLE outfits (
    id             INT IDENTITY(1,1) NOT NULL PRIMARY KEY,
    name           NVARCHAR(100)     NOT NULL,
    change_seconds INT               NOT NULL,
    CONSTRAINT uq_outfits_name UNIQUE (name),
    CONSTRAINT ck_outfits_change_seconds CHECK (change_seconds >= 0)
);

CREATE TABLE songs (
    id               INT IDENTITY(1,1) NOT NULL PRIMARY KEY,
    title            NVARCHAR(200)     NOT NULL,
    album            NVARCHAR(200)     NOT NULL,
    year             INT               NOT NULL,
    duration_seconds INT               NOT NULL,
    energy           INT               NOT NULL,
    kind             NVARCHAR(10)      NOT NULL,
    outfit_id        INT               NOT NULL,
    -- 1 = active, 0 = retired. INT rather than BIT, so the JSON API keeps
    -- sending 1/0 as it did with SQLite.
    active           INT               NOT NULL CONSTRAINT df_songs_active DEFAULT 1,
    CONSTRAINT fk_songs_outfit FOREIGN KEY (outfit_id) REFERENCES outfits (id),
    CONSTRAINT uq_songs_title_album UNIQUE (title, album),
    CONSTRAINT ck_songs_duration CHECK (duration_seconds > 0),
    CONSTRAINT ck_songs_energy CHECK (energy BETWEEN 1 AND 5),
    CONSTRAINT ck_songs_kind CHECK (kind IN (N'dance', N'ballad')),
    CONSTRAINT ck_songs_active CHECK (active IN (0, 1))
);
