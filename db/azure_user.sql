-- Azure setup (run once per service database, as the server admin): the
-- service's own user, which can only use this one database.
--
-- On Azure SQL each user is a contained user: it lives inside its database
-- with its own password, and there is no server login. So the catalogue's
-- user does not exist in the shows database and cannot open it.
--
-- Passwords are not written here. $(APP_USER) and $(APP_PASSWORD) are sqlcmd
-- variables filled in from the environment of the sqlcmd run (README, Azure
-- setup). Idempotent: running it again creates nothing new, but it does set
-- the password, so the user always matches the current GitHub secret.

IF USER_ID(N'$(APP_USER)') IS NULL
    CREATE USER [$(APP_USER)] WITH PASSWORD = N'$(APP_PASSWORD)';
ELSE
    ALTER USER [$(APP_USER)] WITH PASSWORD = N'$(APP_PASSWORD)';
GO

-- Read rows, write rows, and create/alter tables (needed by the migrations
-- that run when the service starts). The same roles as db/init.sql locally.
IF IS_ROLEMEMBER(N'db_datareader', N'$(APP_USER)') = 0
    ALTER ROLE db_datareader ADD MEMBER [$(APP_USER)];
IF IS_ROLEMEMBER(N'db_datawriter', N'$(APP_USER)') = 0
    ALTER ROLE db_datawriter ADD MEMBER [$(APP_USER)];
IF IS_ROLEMEMBER(N'db_ddladmin', N'$(APP_USER)') = 0
    ALTER ROLE db_ddladmin ADD MEMBER [$(APP_USER)];
GO

PRINT 'azure_user: $(APP_USER) is in place.';
GO
