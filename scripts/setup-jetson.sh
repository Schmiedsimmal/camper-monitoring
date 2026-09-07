#!/usr/bin/env bash
# =============================================================================
# Einrichtungsskript für den Jetson Nano (Host).
#
# Installiert/prüft:
#   - Docker + Docker Compose
#   - NVIDIA Container Runtime (nvidia-docker2) für GPU-Zugriff in Containern
#   - GPIO-Berechtigungen (User in Gruppe 'gpio')
#
# Idempotent: kann gefahrlos mehrfach ausgeführt werden.
# =============================================================================
set -euo pipefail

log()  { printf '\033[1;34m[setup]\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m[warn]\033[0m %s\n' "$*" >&2; }
die()  { printf '\033[1;31m[err ]\033[0m %s\n' "$*" >&2; exit 1; }

[[ "$(uname -m)" == "aarch64" ]] || warn "Kein aarch64-Host (kein Jetson?). Skript läuft trotzdem."

# --- Docker -------------------------------------------------------------------
if ! command -v docker >/dev/null 2>&1; then
    log "Docker nicht gefunden. Installiere via offiziellem Convenience-Skript."
    curl -fsSL https://get.docker.com | sh
    sudo usermod -aG docker "$USER"
    warn "Ab- und wieder anmelden, damit die docker-Gruppe greift."
else
    log "Docker vorhanden: $(docker --version)"
fi

if ! docker compose version >/dev/null 2>&1; then
    die "Docker Compose v2 fehlt. Bitte 'docker compose plugin' installieren."
fi
log "Docker Compose: $(docker compose version --short)"

# --- NVIDIA Container Runtime -------------------------------------------------
# JetPack 4.x liefert nvidia-docker2 über das L4T-Repo. Falls nicht vorhanden,
# Hinweis ausgeben (Installation erfordert ggf. manuelle Repo-Einbindung).
if docker info 2>/dev/null | grep -q nvidia; then
    log "NVIDIA Container Runtime aktiv."
else
    warn "NVIDIA Container Runtime nicht erkannt."
    warn "Auf JetPack 4.x installieren:"
    warn "  sudo apt-get update"
    warn "  sudo apt-get install -y nvidia-docker2"
    warn "  sudo systemctl restart docker"
    warn "Danach dieses Skript erneut ausführen."
fi

# --- GPIO-Berechtigungen ------------------------------------------------------
if ! getent group gpio >/dev/null 2>&1; then
    log "Lege Gruppe 'gpio' an."
    sudo groupadd -f gpio
fi

# /dev/gpiomem ggf. auf Gruppe gpio setzen (über udev-Regel persistent).
UDEV_RULE=/etc/udev/rules.d/99-gpiomem.rules
if [[ ! -f "$UDEV_RULE" ]]; then
    log "Lege udev-Regel für /dev/gpiomem an ($UDEV_RULE)."
    echo 'SUBSYSTEM=="gpio*", KERNEL=="gpiomem", GROUP="gpio", MODE="0660"' \
        | sudo tee "$UDEV_RULE" >/dev/null
    sudo udevadm control --reload-rules
    sudo udevadm trigger
fi

if ! id -nG "$USER" | grep -qw gpio; then
    log "Füge User '$USER' zur Gruppe 'gpio' hinzu."
    sudo usermod -aG gpio "$USER"
    warn "Ab- und wieder anmelden, damit die gpio-Gruppe greift."
else
    log "User '$USER' ist bereits in Gruppe 'gpio'."
fi

log "Fertig. Siehe README.md für den nächsten Schritt (docker compose up)."
