#!/usr/bin/env bash
# Installation en une ligne de noctalia-config (Arch, Fedora, Debian 13, Ubuntu) :
#   bash <(curl -fsSL https://raw.githubusercontent.com/abcdef123456-wq/noctalia-config/main/get.sh)
# Installe git s'il manque, télécharge le dépôt dans ~/noctalia-config (ou le met à jour s'il y est déjà),
# puis lance ./install.sh (mêmes options : --no-system, --files-only, --restore).
set -euo pipefail

DEPOT="https://github.com/abcdef123456-wq/noctalia-config.git"
DOSSIER="$HOME/noctalia-config"

if ! command -v git >/dev/null 2>&1; then
  echo "==> Installation de git"
  if command -v pacman >/dev/null 2>&1; then sudo pacman -S --needed --noconfirm git
  elif command -v apt-get >/dev/null 2>&1; then sudo apt-get update -q && sudo apt-get install -y git
  elif command -v dnf >/dev/null 2>&1; then sudo dnf install -y git
  elif command -v zypper >/dev/null 2>&1; then sudo zypper --non-interactive install git
  else echo "Installe git, puis relance cette commande." >&2; exit 1
  fi
fi

if [ -d "$DOSSIER/.git" ]; then
  echo "==> Mise à jour de $DOSSIER"
  git -C "$DOSSIER" pull --ff-only || { echo "Mise à jour impossible (fichiers modifiés dans $DOSSIER ?) : la version présente est utilisée." >&2; }
else
  echo "==> Téléchargement dans $DOSSIER"
  git clone --depth 1 "$DEPOT" "$DOSSIER"
fi

cd "$DOSSIER"
exec ./install.sh "$@"
