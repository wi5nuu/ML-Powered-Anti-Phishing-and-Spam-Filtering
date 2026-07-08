param(
    [ValidateSet("local", "production")]
    [string]$Profile = "local",
    [switch]$Build,
    [switch]$StartDockerDesktop
)

$ErrorActionPreference = "Stop"
$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $Root

if (-not (Test-Path ".env")) {
    throw ".env tidak ditemukan. Buat .env terlebih dahulu sebelum menjalankan stack."
}

function Test-DockerReady {
    try {
        $output = & docker version --format '{{.Server.Version}}' 2>$null
        return ($LASTEXITCODE -eq 0 -and -not [string]::IsNullOrWhiteSpace($output))
    } catch {
        return $false
    }
}

if ((-not (Test-DockerReady)) -and $StartDockerDesktop) {
    $dockerDesktop = @(
        "$env:ProgramFiles\Docker\Docker\Docker Desktop.exe",
        "$env:LOCALAPPDATA\Docker\Docker Desktop.exe"
    ) | Where-Object { Test-Path $_ } | Select-Object -First 1

    if ($dockerDesktop) {
        Write-Host "Starting Docker Desktop..."
        Start-Process -FilePath $dockerDesktop | Out-Null
    } else {
        throw "Docker belum berjalan atau Docker Desktop tidak ditemukan."
    }
}

if (-not (Test-DockerReady)) {
    throw "Docker daemon belum aktif. Aktifkan Docker Engine dari command line/WSL/service Anda, lalu jalankan script ini lagi. Jika di Windows ingin pakai Docker Desktop otomatis, tambahkan -StartDockerDesktop."
}

Write-Host "Waiting for Docker daemon..."
for ($i = 0; $i -lt 90; $i++) {
    if (Test-DockerReady) {
        Write-Host "Docker is ready."
        break
    }
    Start-Sleep -Seconds 2
}

if (-not (Test-DockerReady)) {
    throw "Docker daemon belum siap. Cek Docker Desktop/WSL/virtualization."
}

$compose = @("--env-file", ".env")
$env:ENV = $Profile

if ($Profile -eq "production") {
    $env:SMTP_PUBLIC_PORT = "25"
} else {
    $env:SMTP_PUBLIC_PORT = "2525"
    $env:REDIS_PORT = "6470"
}

function Invoke-DockerCompose {
    & docker compose @args
    if ($LASTEXITCODE -ne 0) {
        throw "docker compose command failed with exit code $LASTEXITCODE"
    }
}

if ($Build) {
    Invoke-DockerCompose @compose --profile $Profile build
}

Invoke-DockerCompose @compose --profile $Profile up -d
Invoke-DockerCompose @compose --profile $Profile ps

Write-Host ""
Write-Host "Mode: $Profile"
Write-Host "Dashboard   http://localhost:8080"
Write-Host "Classifier  http://localhost:8001/health"
Write-Host "Grafana     http://localhost:3000"
Write-Host "Prometheus  http://localhost:9090"
if ($Profile -eq "local") {
    Write-Host "Mailpit     http://localhost:8025"
    Write-Host "SMTP local  localhost:2525"
}
