# Azure setup, step 7 (README, "Azure setup"): one contained user per
# service database, with a new random password that goes straight into a
# GitHub Actions secret. No password is printed or written to a file.
#
# Run from any folder, in Windows PowerShell, signed in with az and gh, with
# Docker running (sqlcmd comes from the SQL Server image). Safe to run again:
# db/azure_user.sql sets the password of an existing user, and the GitHub
# secret is only replaced once the new password works.
#
# Every step checks $LASTEXITCODE itself and throws on failure; the finally
# block always closes the firewall again.
$Rg = "rg-fmedina-ieu2024"
$Server = "fmedina-ieu2024-sql"
$Admin = "fmedinaadmin"
$Repo = "f3renp/tribute-show-planner"
$DbDir = $PSScriptRoot
$Image = "mcr.microsoft.com/mssql/server:2022-latest"

# 32 random letters and digits, with at least one upper case letter, one
# lower case letter and one digit (Azure SQL's complexity rule). Letters and
# digits only, so the password needs no escaping in DATABASE_URL.
function New-RandomPassword {
  $chars = [char[]]'ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz23456789'
  $rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
  do {
    $bytes = New-Object byte[] 32; $rng.GetBytes($bytes)
    $p = -join ($bytes | ForEach-Object { $chars[$_ % $chars.Length] })
  } until ($p -cmatch '[A-Z]' -and $p -cmatch '[a-z]' -and $p -match '[0-9]')
  $p
}

# Runs sqlcmd from the SQL Server image against one database. Passwords
# reach it only through environment variables: -e NAME with no value makes
# Docker copy NAME from this shell, so no password is on a command line.
# sqlcmd reads SQLCMDPASSWORD as the password, and fills in $(APP_USER)
# and $(APP_PASSWORD) in azure_user.sql from the environment.
function Invoke-Sqlcmd18($Database, $User, [string[]]$SqlArgs) {
  docker run --rm -e SQLCMDPASSWORD -e APP_USER -e APP_PASSWORD -v "${DbDir}:/db:ro" `
    --entrypoint /opt/mssql-tools18/bin/sqlcmd $Image `
    -S "tcp:$Server.database.windows.net,1433" -d $Database -U $User -b -l 30 @SqlArgs 2>&1 |
    ForEach-Object { "$_" } | Tee-Object -Variable script:lastSqlOutput | Out-Host
  return $LASTEXITCODE
}

# Sign in as admin every 20 s until the database answers, for up to 5
# minutes: a new firewall rule can take minutes to apply, and a paused
# serverless database takes about a minute to resume. Stop at once if Azure
# sees a different IP from the one the firewall rule opens (a network with
# several public IPs: use one with a single IP, such as a phone hotspot).
function Wait-Database($Database) {
  for ($try = 1; $try -le 15; $try++) {
    if ((Invoke-Sqlcmd18 $Database $Admin @("-Q", "SELECT 1 AS reached")) -eq 0) { return }
    $text = $script:lastSqlOutput | Out-String
    if ($text -match "Client with IP address '([0-9.]+)'" -and $Matches[1] -ne $myIp) {
      throw "Azure sees $($Matches[1]) but the rule opens $myIp"
    }
    "$Database attempt $try failed, waiting 20 s"
    Start-Sleep -Seconds 20
  }
  throw "$Database not reachable after 5 minutes"
}

$myIp = (Invoke-RestMethod https://api.ipify.org).Trim()
try {
  # 1. A fresh admin password, known only to this run. The admin password
  # is never kept: whenever it is needed, it is reset (Contributor may).
  $env:SQLCMDPASSWORD = New-RandomPassword
  az sql server update --resource-group $Rg --name $Server --admin-password $env:SQLCMDPASSWORD --only-show-errors --query state -o tsv
  if ($LASTEXITCODE -ne 0) { throw "admin password reset failed" }

  # 2. Open the firewall to this machine only while we need it.
  az sql server firewall-rule create --resource-group $Rg --server $Server --name setup-my-ip --start-ip-address $myIp --end-ip-address $myIp --only-show-errors --query name -o tsv
  if ($LASTEXITCODE -ne 0) { throw "firewall rule failed" }
  "firewall opened to $myIp"

  foreach ($svc in "catalogue", "shows") {
    $db = "fmedina-ieu2024-$svc-db"
    $env:APP_USER = "${svc}_app"
    $env:APP_PASSWORD = New-RandomPassword
    Wait-Database $db

    # 3. Create the user (or set its new password) as admin.
    $adminPassword = $env:SQLCMDPASSWORD
    if ((Invoke-Sqlcmd18 $db $Admin @("-i", "/db/azure_user.sql")) -ne 0) { throw "creating $($env:APP_USER) failed" }

    # 4. Check it: the user can sign in to its own database, with its roles.
    $env:SQLCMDPASSWORD = $env:APP_PASSWORD
    $ok = Invoke-Sqlcmd18 $db $env:APP_USER @("-Q", "SET NOCOUNT ON; SELECT DB_NAME() AS db, USER_NAME() AS app_user, IS_ROLEMEMBER('db_ddladmin') AS ddladmin")
    $env:SQLCMDPASSWORD = $adminPassword
    if ($ok -ne 0) { throw "$($env:APP_USER) cannot sign in to $db" }

    # 5. Into GitHub Actions only after the user works. The CD workflow
    # builds DATABASE_URL from this secret on every deploy.
    $secretName = "$($svc.ToUpper())_DB_PASSWORD"
    gh secret set $secretName --repo $Repo --body $env:APP_PASSWORD
    if ($LASTEXITCODE -ne 0) { throw "gh secret set $secretName failed" }
    "secret $secretName set"
    if ($svc -eq "catalogue") { $catalogueAppPassword = $env:APP_PASSWORD }
  }

  # 6. Isolation: catalogue_app with its REAL password must not get into
  # the shows database, because its contained user exists only in catalogue.
  $env:SQLCMDPASSWORD = $catalogueAppPassword
  Remove-Variable catalogueAppPassword
  if ((Invoke-Sqlcmd18 "fmedina-ieu2024-shows-db" "catalogue_app" @("-Q", "SELECT 1")) -eq 0) {
    throw "catalogue_app could sign in to the shows database"
  }
  "catalogue_app is refused by the shows database, as it should be"
}
finally {
  az sql server firewall-rule delete --resource-group $Rg --server $Server --name setup-my-ip --only-show-errors
  "firewall rule setup-my-ip removed"
  Remove-Item Env:SQLCMDPASSWORD, Env:APP_USER, Env:APP_PASSWORD -ErrorAction SilentlyContinue
}
