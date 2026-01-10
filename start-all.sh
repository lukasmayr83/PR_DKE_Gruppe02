#!/usr/bin/env bash
# start-all.sh
# Linux: Setup + Start aller Flask-Services
# - optional: venv neu (löschen & neu erstellen)
# - pip install -r requirements.txt
# - flask db upgrade
# - flask run auf fixen Ports (je Service eigener Terminal-Tab/Window, wenn möglich)

set -euo pipefail

BASE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# >>> HIER EINSTELLEN <<<
# name   = Anzeigename
# folder = Ordnername
# port   = Port pro Service
# app    = was du bei "flask --app <app>" nutzt (z.B. strecken / fahrplan / app / app:create_app)
services=(
  "strecken|Strecken|5001|strecken"
  "flotten|Flotten|5003|flotten"
  "fahrplan|Fahrplan|5002|fahrplan"
  "ticket|Ticket|5004|ticket"
)

# Clean start: venv löschen & neu erstellen?
# true  = jedes Mal komplett neu (langsam, aber sicher)
# false = venv behalten, nur deps/db upgrade/run (schneller)
RECREATE_VENV=true

# Python Kommando (python3 ist Standard auf Linux)
PYTHON_BIN="${PYTHON_BIN:-python3}"

ensure_venv_and_deps() {
  local name="$1" folder="$2"
  local dir="$BASE/$folder"

  [[ -d "$dir" ]] || { echo "Ordner nicht gefunden: $dir"; exit 1; }

  pushd "$dir" >/dev/null

  if [[ "$RECREATE_VENV" == "true" && -d "venv" ]]; then
    echo "[$name] Lösche venv..."
    rm -rf venv
  fi

  if [[ ! -d "venv" ]]; then
    echo "[$name] Erstelle venv..."
    "$PYTHON_BIN" -m venv venv
  fi

  local py="./venv/bin/python"
  local pip="./venv/bin/pip"

  echo "[$name] Upgrade pip..."
  "$py" -m pip install --upgrade pip >/dev/null

  if [[ -f "requirements.txt" ]]; then
    echo "[$name] Install requirements..."
    "$pip" install -r requirements.txt >/dev/null
  else
    echo "[$name] WARN: requirements.txt nicht gefunden"
  fi

  popd >/dev/null
}

db_upgrade() {
  local name="$1" folder="$2" app="$3"
  local dir="$BASE/$folder"

  pushd "$dir" >/dev/null
  local py="./venv/bin/python"

  echo "[$name] flask db upgrade..."
  "$py" -m flask --app "$app" db upgrade

  popd >/dev/null
}

start_service() {
  local name="$1" folder="$2" port="$3" app="$4"
  local dir="$BASE/$folder"

  echo "[$name] Starte auf Port $port..."

  # Kommando, das im Service-Terminal laufen soll
  local cmd="cd \"$dir\" && source venv/bin/activate && flask --app \"$app\" run --port \"$port\""

  # Bevorzugt: gnome-terminal (Ubuntu Standard)
  if command -v gnome-terminal >/dev/null 2>&1; then
    gnome-terminal -- bash -lc "$cmd; exec bash" >/dev/null 2>&1 &
    return
  fi

  # Alternative: xterm
  if command -v xterm >/dev/null 2>&1; then
    xterm -T "$name" -e bash -lc "$cmd" >/dev/null 2>&1 &
    return
  fi

  # Fallback: läuft im Hintergrund ohne eigenes Fenster, Logs je Service in Datei
  (bash -lc "$cmd") >"$BASE/${name}.log" 2>&1 &
  echo "[$name] Kein Terminal gefunden -> läuft im Hintergrund, Logs: ${name}.log"
}

# -----------------------
# 1) SETUP + DB UPGRADE
# -----------------------
for entry in "${services[@]}"; do
  IFS="|" read -r name folder port app <<<"$entry"
  echo
  echo "=== Setup: $name ($folder) ==="
  ensure_venv_and_deps "$name" "$folder"
  db_upgrade "$name" "$folder" "$app"
done

# -----------------------
# 2) START
# -----------------------
echo
echo "=== Starte alle Services ==="
for entry in "${services[@]}"; do
  IFS="|" read -r name folder port app <<<"$entry"
  start_service "$name" "$folder" "$port" "$app"
done

echo
echo "Fertig."
