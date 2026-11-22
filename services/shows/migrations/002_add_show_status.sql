-- 002: every show gets a status, so the manager can tell a booked gig
-- (confirmed) from one only pencilled in (planned), and keep a cancelled
-- show with its setlist instead of deleting it.
-- Never edit this file once it has been applied: add 003_... instead.
--
-- This changes a table that already holds data. It is additive (ADR-7):
-- one new column, nothing renamed or dropped.
--   - NOT NULL with a DEFAULT: SQL Server writes 'planned' into every
--     existing row in this same statement, so no row is left without a
--     status and every row is kept as it was.
--   - The previous image keeps working while the new one deploys: its
--     INSERT does not name status, so the default fills it in; its UPDATE
--     does not name status, so the value stays as it was; its SELECT *
--     gets one extra field it ignores.
-- The constraints have names, so a later migration can change them.

ALTER TABLE shows ADD
    status NVARCHAR(10) NOT NULL
        CONSTRAINT df_shows_status DEFAULT N'planned'
        CONSTRAINT ck_shows_status CHECK (status IN (N'planned', N'confirmed', N'cancelled'));
