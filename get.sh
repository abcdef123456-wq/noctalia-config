#!/usr/bin/env bash
# Installation en une ligne de noctalia-config (Arch, Debian 13, Ubuntu, Fedora, openSUSE) :
#   bash <(curl -fsSL https://raw.githubusercontent.com/abcdef123456-wq/noctalia-config/main/get.sh)
# Installe git s'il manque, télécharge le dépôt dans ~/noctalia-config (ou le met à jour s'il y est déjà),
# puis lance ./install.sh (mêmes options : --no-system, --files-only, --restore).
# Variables facultatives : NC_VERSION (branche ou étiquette à installer), NC_GARDER=1 (continuer avec la version
# présente si la mise à jour échoue).
# Tout est dans main(), appelée à la toute dernière ligne : un téléchargement coupé n'exécute rien.
set -euo pipefail

main() {
  local DEPOT="https://github.com/abcdef123456-wq/noctalia-config.git"
  local DOSSIER="$HOME/noctalia-config"
  local VERSION="${NC_VERSION:-}"
  export GIT_TERMINAL_PROMPT=0

  if [ "$(id -u)" -eq 0 ]; then
    echo "Ne lance pas ce script en root (ni avec sudo) : il installerait tout dans le dossier de root." >&2
    echo "Lance-le avec ton utilisateur ; il demandera sudo quand il en aura besoin." >&2
    return 1
  fi

  if ! command -v git >/dev/null 2>&1; then
    local pm="" cmd=""
    if command -v pacman >/dev/null 2>&1; then pm=pacman; cmd="pacman -S --needed git"
    elif command -v apt-get >/dev/null 2>&1; then pm=apt; cmd="apt install sudo git"
    elif command -v dnf >/dev/null 2>&1; then pm=dnf; cmd="dnf install sudo git"
    elif command -v zypper >/dev/null 2>&1; then pm=zypper; cmd="zypper install sudo git"
    else echo "Installe git, puis relance cette commande." >&2; return 1
    fi
    if ! command -v sudo >/dev/null 2>&1; then
      echo "sudo est absent, git ne peut pas être installé d'ici." >&2
      echo "Installe-les en root, puis relance cette commande : su -c '$cmd'" >&2
      return 1
    fi
    echo "==> Installation de git"
    case "$pm" in
      pacman) sudo pacman -S --needed --noconfirm git || true ;;
      apt) { sudo apt-get update -q && sudo apt-get install -y git; } || true ;;
      dnf) sudo dnf install -y git || true ;;
      zypper) sudo zypper --non-interactive install git || true ;;
    esac
    if ! command -v git >/dev/null 2>&1; then
      echo "L'installation de git a échoué. Installe-le à la main (su -c '$cmd'), puis relance cette commande." >&2
      return 1
    fi
  fi

  if [ -d "$DOSSIER/.git" ]; then
    local origine propre
    origine="$(git -C "$DOSSIER" remote get-url origin 2>/dev/null || true)"
    # Le même dépôt en SSH (git@github.com:… ou ssh://git@github.com/…) est accepté
    propre="${origine%.git}"; propre="${propre%/}"
    case "$propre" in
      git@github.com:*) propre="https://github.com/${propre#git@github.com:}" ;;
      ssh://git@github.com/*) propre="https://github.com/${propre#ssh://git@github.com/}" ;;
    esac
    if [ "$propre" != "${DEPOT%.git}" ]; then
      echo "$DOSSIER vient d'un autre dépôt (${origine:-origine inconnue}) que $DEPOT." >&2
      echo "Déplace ou supprime ce dossier, puis relance cette commande." >&2
      return 1
    fi
    echo "==> Mise à jour de $DOSSIER"
    local ok=1
    if [ -n "$VERSION" ]; then
      { git -C "$DOSSIER" fetch --depth 1 origin "$VERSION" && git -C "$DOSSIER" checkout -q FETCH_HEAD; } || ok=0
    elif ! git -C "$DOSSIER" symbolic-ref -q HEAD >/dev/null; then
      # Sur une version choisie (NC_VERSION, HEAD détaché) : la dernière version, pas un « pull » impossible
      { git -C "$DOSSIER" fetch --depth 1 origin HEAD && git -C "$DOSSIER" checkout -q FETCH_HEAD; } || ok=0
    else
      git -C "$DOSSIER" pull --ff-only || ok=0
    fi
    if [ "$ok" -eq 0 ]; then
      if [ "${NC_GARDER:-0}" = 1 ]; then
        echo "Mise à jour impossible (fichiers modifiés dans $DOSSIER ?) : la version présente est utilisée (NC_GARDER=1)." >&2
      else
        echo "Mise à jour impossible (fichiers modifiés dans $DOSSIER ?). Arrêt, pour ne pas lancer une ancienne version." >&2
        echo "Règle le problème, ou relance avec NC_GARDER=1 pour garder la version présente." >&2
        return 1
      fi
    fi
  else
    echo "==> Téléchargement dans $DOSSIER"
    if [ -n "$VERSION" ]; then
      git clone --depth 1 --branch "$VERSION" "$DEPOT" "$DOSSIER"
    else
      git clone --depth 1 "$DEPOT" "$DOSSIER"
    fi
  fi

  cd "$DOSSIER"
  exec ./install.sh "$@"
}

main "$@"
