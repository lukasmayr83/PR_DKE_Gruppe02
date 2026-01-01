# start-all.ps1
# Windows: Setup + Start aller Flask-Services
# - optional: venv neu (löschen & neu erstellen)
# - pip install -r requirements.txt
# - flask db upgrade
# - flask run auf fixen Ports in eigenen Fenstern

$ErrorActionPreference = "Stop"
$BASE = Split-Path -Parent $MyInvocation.MyCommand.Path

# >>> HIER EINSTELLEN <<<
# folder = Ordnername
# app    = was du bei "flask --app <app>" nutzt (z.B. strecken / fahrplan / app / app:create_app)
# port   = Port pro Service
$services = @(
  @{ name="strecken"; folder="Strecken"; port=5001; app="strecken" },
  @{ name="flotten";  folder="Flotten";  port=5003; app="flotten"  },
  @{ name="fahrplan"; folder="Fahrplan"; port=5002; app="fahrplan" },
  @{ name="ticket";   folder="Ticket";   port=5004; app="ticket"   }
)

# Clean start: venv löschen & neu erstellen?
# $true  = jedes Mal komplett neu (langsam, aber sicher)
# $false = venv behalten, nur deps/db upgrade/run (schneller)
$RECREATE_VENV = $false                                           # DS 30.12.2025

function Invoke-InDir($dir, [scriptblock]$block) {
  if (!(Test-Path $dir)) { throw "Ordner nicht gefunden: $dir" }
  Push-Location $dir
  try { & $block }
  finally { Pop-Location }
}

function Ensure-VenvAndDeps($svc) {
  $dir = Join-Path $BASE $svc.folder

  Invoke-InDir $dir {
    if ($RECREATE_VENV -and (Test-Path "venv")) {
      Write-Host "[$($svc.name)] Lösche venv..."
      Remove-Item -Recurse -Force "venv"
    }

    if (!(Test-Path "venv")) {
      Write-Host "[$($svc.name)] Erstelle venv..."
      py -m venv venv
    }

    $py  = ".\venv\Scripts\python.exe"
    $pip = ".\venv\Scripts\pip.exe"

    Write-Host "[$($svc.name)] Upgrade pip..."
    & $py -m pip install --upgrade pip | Out-Host

    if (Test-Path "requirements.txt") {
      Write-Host "[$($svc.name)] Install requirements..."
      & $pip install -r requirements.txt | Out-Host
    } else {
      Write-Host "[$($svc.name)] WARN: requirements.txt nicht gefunden"
    }
  }
}

function Db-Upgrade($svc) {
  $dir = Join-Path $BASE $svc.folder
  $app = $svc.app

  Invoke-InDir $dir {
    $py = ".\venv\Scripts\python.exe"
    Write-Host "[$($svc.name)] flask db upgrade..."
    & $py -m flask --app $app db upgrade | Out-Host
  }
}

function Start-Service($svc) {
  $dir  = Join-Path $BASE $svc.folder
  $app  = $svc.app
  $port = $svc.port
  $name = $svc.name

  Write-Host "[$name] Starte auf Port $port..."

  Start-Process powershell -ArgumentList "-NoExit", "-Command", @"
cd '$dir'
.\venv\Scripts\activate
flask --app $app run --port $port
"@ | Out-Null
}

# -----------------------
# 1) SETUP + DB UPGRADE
# -----------------------
foreach ($svc in $services) {
  Write-Host "`n=== Setup: $($svc.name) ($($svc.folder)) ==="
  Ensure-VenvAndDeps $svc
  Db-Upgrade $svc
}

# -----------------------
# 2) START
# -----------------------
Write-Host "`n=== Starte alle Services ==="
foreach ($svc in $services) {
  Start-Service $svc
}

Write-Host "`nFertig. (Je Service sollte ein eigenes Fenster offen sein.)"
