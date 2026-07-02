param(
    [ValidateSet("local", "production")]
    [string]$Profile = "local"
)

$ErrorActionPreference = "Stop"
$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $Root

$env:ENV = $Profile
if ($Profile -eq "production") {
    $env:SMTP_PUBLIC_PORT = "25"
} else {
    $env:SMTP_PUBLIC_PORT = "2525"
}

& docker compose --env-file .env --profile $Profile down
if ($LASTEXITCODE -ne 0) {
    throw "docker compose down gagal dengan exit code $LASTEXITCODE"
}
