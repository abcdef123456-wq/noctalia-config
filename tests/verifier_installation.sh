#!/usr/bin/env bash
# Vérifie une installation réelle (CI : .github/workflows/install.yml). À lancer APRÈS ./install.sh, sous un
# utilisateur ordinaire, dans un conteneur jetable : le script relance install.sh (2e passage) pour tester l'idempotence,
# avec les mêmes options que le 1er passage (variable NC_INSTALL_ARGS, par exemple --oui).
#   tests/verifier_installation.sh [DOSSIER_DU_DEPOT]     (par défaut : le dépôt qui contient ce script)
# Il continue après un échec, résume tout, et sort avec 1 s'il y en a au moins un. Aucun réseau, hors le 2e install.sh.
set -u

DEPOT="$(cd "${1:-$(dirname "$0")/..}" && pwd)"
export PATH="$HOME/.local/bin:$PATH"
ECHECS=0
ok()   { printf '  ok    %s\n' "$*"; }
ko()   { printf '  ECHEC %s\n' "$*"; ECHECS=$((ECHECS + 1)); }
info() { printf '  ..    %s\n' "$*"; }
titre() { printf '\n== %s\n' "$*"; }
have() { command -v "$1" >/dev/null 2>&1; }
ver_ge() { [ "$(printf '%s\n%s\n' "$2" "$1" | sort -V | head -1)" = "$2" ]; }   # A >= B
# Seuil Hyprland : celui d'install.sh (HYPR_MIN), la même règle que l'installateur ; NC_VERIF_HYPR_MIN pour le surcharger
HYPR_ATTENDU="${NC_VERIF_HYPR_MIN:-$(sed -n 's/^HYPR_MIN=\([0-9.]*\).*/\1/p' "$DEPOT/install.sh" | head -1)}"
[ -n "$HYPR_ATTENDU" ] || { echo "HYPR_MIN introuvable dans $DEPOT/install.sh" >&2; exit 2; }
[ "$(id -u)" != 0 ] || { echo "À lancer sous un utilisateur ordinaire, pas en root." >&2; exit 2; }
. /etc/os-release 2>/dev/null || true

# ── 1. Aucun @MARQUEUR@ restant ──────────────────────────────────────────────
titre "Marqueurs @NOM@ restants dans ~/.config et ~/.local"
# Ce ne sont PAS des marqueurs du dépôt, liste explicite (FICHIER:MARQUEUR, motif de grep étendu) :
#  - les cibles réservées de wpctl (@DEFAULT_AUDIO_SINK@, @DEFAULT_AUDIO_SOURCE@) et leurs formes courtes, que nc-diag
#    cite pour les reconnaître (nc-diag, ligne « if m not in (… ») ;
#  - @PY@ et @NC@ de nc-claude : modèles du plugin JavaScript, remplis par nc-claude au moment de l'écrire.
EXCEPTIONS='@DEFAULT_(AUDIO_)?(SINK|SOURCE)@|\.local/bin/nc-claude:@(PY|NC)@'
# Hors du champ : ce que les outils téléchargent eux-mêmes (modules de Mason/lazy.nvim, Neovim dans ~/.local/opt, node_modules), pas le dépôt.
restes="$(grep -rIoE '@[A-Z][A-Z0-9_]*@' "$HOME/.config" "$HOME/.local" \
  --exclude-dir='backup-*' --exclude-dir=node_modules --exclude-dir=Trash 2>/dev/null |
  grep -vE "^[^:]*/\.local/(share/nvim|opt)/" | grep -vE "($EXCEPTIONS)\$" | sort -u || true)"
if [ -z "$restes" ]; then ok "aucun marqueur (exceptions listées dans le script)"; else ko "marqueurs restants :"; printf '%s\n' "$restes" | head -20; fi

# ── 2. Commandes clés et versions ────────────────────────────────────────────
titre "Commandes clés"
for c in Hyprland hypridle noctalia nc-reglages nc-diag; do
  if have "$c"; then ok "$c : $(command -v "$c")"; else ko "$c introuvable"; fi
done
hv=""
if have Hyprland; then
  hv="$(timeout 10 Hyprland --version 2>/dev/null | grep -oE '^Hyprland v?[0-9]+\.[0-9]+\.[0-9]+|^Tag: v[0-9]+\.[0-9]+\.[0-9]+' | head -1 | grep -oE '[0-9]+\.[0-9]+\.[0-9]+')"
  if [ -z "$hv" ]; then
    case "${ID:-}" in
      arch) hv="$(pacman -Q hyprland 2>/dev/null | awk '{print $2}')" ;;
      debian|ubuntu) hv="$(dpkg-query -W -f='${Version}' hyprland 2>/dev/null)" ;;
      *) hv="$(rpm -q --qf '%{VERSION}' hyprland 2>/dev/null)" ;;
    esac
    hv="$(grep -oE '[0-9]+\.[0-9]+\.[0-9]+' <<<"$hv" | head -1)"
  fi
  if [ -n "$hv" ] && ver_ge "$hv" "$HYPR_ATTENDU"; then ok "Hyprland $hv (>= $HYPR_ATTENDU)"; else ko "Hyprland ${hv:-version inconnue} : $HYPR_ATTENDU ou plus attendu"; fi
fi
# Quickshell : sur openSUSE il n'a pas de paquet, install.sh ne le compile pas et laisse l'île du plugin Noctalia :
# son absence y est le comportement prévu (on l'écrit, sans le masquer). Partout ailleurs il doit être là, en 0.3 ou plus.
qs=""; have qs && qs=qs; [ -z "$qs" ] && have quickshell && qs=quickshell
if [ -n "$qs" ]; then
  qv="$($qs --version 2>/dev/null | grep -oE '[0-9]+\.[0-9]+(\.[0-9]+)?' | head -1)"
  if [ -n "$qv" ] && ver_ge "$qv" 0.3; then ok "Quickshell $qv (>= 0.3)"; else ko "Quickshell ${qv:-version inconnue} : 0.3 ou plus attendu"; fi
else
  case "${ID:-}" in
    opensuse*) info "Quickshell absent : prévu sur openSUSE (pas de paquet ; l'île du plugin Noctalia sert)" ;;
    *) ko "Quickshell (qs) introuvable" ;;
  esac
fi

# ── 3. nc-diag --json --rapide ───────────────────────────────────────────────
titre "nc-diag --json --rapide (hors session)"
if have nc-diag; then
  sortie="$(mktemp)"; erreurs="$(mktemp)"
  timeout 120 nc-diag --json --rapide >"$sortie" 2>"$erreurs"; code=$?
  if [ "$code" -ne 0 ]; then ko "code $code"; head -5 "$erreurs";
  elif ! python3 -c 'import json,sys; json.load(open(sys.argv[1]))' "$sortie" 2>/dev/null; then ko "JSON invalide"; head -c 300 "$sortie";
  elif grep -q Traceback "$sortie" "$erreurs"; then ko "trace Python"; head -10 "$erreurs";
  else ok "JSON valide, sans trace Python"; fi
  rm -f "$sortie" "$erreurs"
fi

# ── 4. nc-reglages appliquer ─────────────────────────────────────────────────
titre "nc-reglages appliquer (hors session)"
if have nc-reglages; then
  sortie="$(mktemp)"
  timeout 120 nc-reglages appliquer >"$sortie" 2>&1 </dev/null; code=$?
  # 0 : tout passé. 1 : un groupe en échec, annoncé par un message (normal sans session : pas de hyprctl ni de Noctalia
  # qui répond). Tout autre code, une trace Python ou un code 1 muet : plantage.
  if grep -q Traceback "$sortie"; then ko "trace Python"; head -15 "$sortie"
  elif [ "$code" -eq 0 ]; then ok "code 0"
  elif [ "$code" -eq 1 ] && [ -s "$sortie" ]; then ok "code 1 avec message (groupe en échec hors session) : $(head -c 160 "$sortie" | tr '\n' ' ')"
  else ko "code $code"; head -10 "$sortie"; fi
  rm -f "$sortie"
fi

# ── 5. Syntaxe Lua ───────────────────────────────────────────────────────────
titre "Syntaxe Lua de la config Hyprland"
if have luac; then lint() { luac -p "$1"; }
elif have lua; then lint() { lua -e 'assert(loadfile(arg[1]))' "$1"; }
elif have lua5.4; then lint() { lua5.4 -e 'assert(loadfile(arg[1]))' "$1"; }
else lint() { return 99; }; fi
lint /dev/null 2>/dev/null; if [ $? -eq 99 ]; then
  ko "ni luac ni lua installé : impossible de vérifier"
else
  n=0
  for f in "$HOME/.config/hypr/hyprland.lua" "$HOME"/.config/hypr/nc/*.lua; do
    [ -f "$f" ] || { ko "absent : $f"; continue; }
    n=$((n + 1)); lint "$f" 2>&1 || ko "syntaxe : ${f#"$HOME"/}"
  done
  [ "$n" -gt 1 ] && ok "$n fichiers .lua lus"
fi

# ── 6. 2e install.sh : code 0, rien ne change, aucune sauvegarde inutile ─────
titre "2e passage de install.sh (idempotence)"
STATE="$HOME/.local/state/noctalia-config"
instantane() { # liste + empreintes, sans ce qui change légitimement
  # Écartés, et pourquoi :
  # - backup-* : les sauvegardes ; testées à part (leur nombre)
  # - .local/state/noctalia-config/ : journaux et dates du dernier passage (révision, heure)
  # - __pycache__, Trash, recently-used.xbel : produits par les outils eux-mêmes
  ( cd "$HOME" && find .config .local -type f ! -path '*/backup-*' ! -path '.local/state/noctalia-config/*' \
      ! -path '*/__pycache__/*' ! -path '.local/share/Trash/*' ! -path '.local/share/recently-used.xbel' -print0 2>/dev/null |
    sort -z | xargs -0 -r sha256sum )
}
sauvegardes() { ls -1d "$STATE"/backup-* 2>/dev/null | wc -l; }
avant="$(mktemp)"; apres="$(mktemp)"; journal="$(mktemp)"
instantane >"$avant"; nb_avant="$(sauvegardes)"
( cd "$DEPOT" && setsid timeout 3000 ./install.sh ${NC_INSTALL_ARGS:-} </dev/null >"$journal" 2>&1 ); code=$?
if [ "$code" -eq 0 ]; then ok "2e install.sh : code 0"; else ko "2e install.sh : code $code"; tail -15 "$journal"; fi
instantane >"$apres"; nb_apres="$(sauvegardes)"
if cmp -s "$avant" "$apres"; then ok "mêmes fichiers, même contenu"
else ko "fichiers changés au 2e passage :"; diff "$avant" "$apres" | head -30; fi
if [ "$nb_avant" = "$nb_apres" ]; then ok "aucune sauvegarde ajoutée ($nb_apres dans ${STATE/#$HOME/~})"
else ko "sauvegarde inutile : $nb_avant -> $nb_apres"; ls -1d "$STATE"/backup-* | tail -2; fi
rm -f "$avant" "$apres" "$journal"

printf '\n'
if [ "$ECHECS" -eq 0 ]; then echo "Installation vérifiée : tout est bon."; exit 0; fi
echo "$ECHECS vérification(s) en échec."; exit 1
