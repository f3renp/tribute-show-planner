-- Local setup for docker compose: one database per service, and one login
-- per service that can only use its own databases.
--
-- Idempotent: every step checks first, so running it again changes nothing.
-- Passwords are not written here. $(CATALOGUE_DB_PASSWORD) and
-- $(SHOWS_DB_PASSWORD) are sqlcmd variables filled in from db-init's
-- environment. A changed password is NOT applied to an existing login.
--
-- Each service also gets a *_test database for its tests (tests/conftest.py
-- empties it before every test), so the tests never touch the real data.
--
-- GO ends a batch: SQL Server runs everything up to each GO on its own.

-- 1. Databases
IF DB_ID(N'catalogue') IS NULL
    CREATE DATABASE catalogue;
GO
IF DB_ID(N'catalogue_test') IS NULL
    CREATE DATABASE catalogue_test;
GO
IF DB_ID(N'shows') IS NULL
    CREATE DATABASE shows;
GO
IF DB_ID(N'shows_test') IS NULL
    CREATE DATABASE shows_test;
GO

-- 2. Logins (server level: who may connect)
IF SUSER_ID(N'catalogue_app') IS NULL
    CREATE LOGIN catalogue_app
        WITH PASSWORD = N'$(CATALOGUE_DB_PASSWORD)',
        DEFAULT_DATABASE = catalogue;
GO
IF SUSER_ID(N'shows_app') IS NULL
    CREATE LOGIN shows_app
        WITH PASSWORD = N'$(SHOWS_DB_PASSWORD)',
        DEFAULT_DATABASE = shows;
GO

-- 3. Users (database level: what a login may do inside one database).
-- A login gets a user only in its own service's databases, so it cannot
-- open the other service's. Roles: read rows, write rows, and create/alter
-- tables (needed by the migrations that run when the service starts).
USE catalogue;
GO
IF USER_ID(N'catalogue_app') IS NULL
    CREATE USER catalogue_app FOR LOGIN catalogue_app;
GO
IF IS_ROLEMEMBER(N'db_datareader', N'catalogue_app') = 0
    ALTER ROLE db_datareader ADD MEMBER catalogue_app;
IF IS_ROLEMEMBER(N'db_datawriter', N'catalogue_app') = 0
    ALTER ROLE db_datawriter ADD MEMBER catalogue_app;
IF IS_ROLEMEMBER(N'db_ddladmin', N'catalogue_app') = 0
    ALTER ROLE db_ddladmin ADD MEMBER catalogue_app;
GO

USE catalogue_test;
GO
IF USER_ID(N'catalogue_app') IS NULL
    CREATE USER catalogue_app FOR LOGIN catalogue_app;
GO
IF IS_ROLEMEMBER(N'db_datareader', N'catalogue_app') = 0
    ALTER ROLE db_datareader ADD MEMBER catalogue_app;
IF IS_ROLEMEMBER(N'db_datawriter', N'catalogue_app') = 0
    ALTER ROLE db_datawriter ADD MEMBER catalogue_app;
IF IS_ROLEMEMBER(N'db_ddladmin', N'catalogue_app') = 0
    ALTER ROLE db_ddladmin ADD MEMBER catalogue_app;
GO

USE shows;
GO
IF USER_ID(N'shows_app') IS NULL
    CREATE USER shows_app FOR LOGIN shows_app;
GO
IF IS_ROLEMEMBER(N'db_datareader', N'shows_app') = 0
    ALTER ROLE db_datareader ADD MEMBER shows_app;
IF IS_ROLEMEMBER(N'db_datawriter', N'shows_app') = 0
    ALTER ROLE db_datawriter ADD MEMBER shows_app;
IF IS_ROLEMEMBER(N'db_ddladmin', N'shows_app') = 0
    ALTER ROLE db_ddladmin ADD MEMBER shows_app;
GO

USE shows_test;
GO
IF USER_ID(N'shows_app') IS NULL
    CREATE USER shows_app FOR LOGIN shows_app;
GO
IF IS_ROLEMEMBER(N'db_datareader', N'shows_app') = 0
    ALTER ROLE db_datareader ADD MEMBER shows_app;
IF IS_ROLEMEMBER(N'db_datawriter', N'shows_app') = 0
    ALTER ROLE db_datawriter ADD MEMBER shows_app;
IF IS_ROLEMEMBER(N'db_ddladmin', N'shows_app') = 0
    ALTER ROLE db_ddladmin ADD MEMBER shows_app;
GO

PRINT 'db-init: databases and logins are in place.';
GO
