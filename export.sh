#!/usr/bin/env bash
# export.sh : met à jour le dépôt avec la config actuelle de ce PC (à lancer sur la machine de référence).
# Ce qui est propre à la machine devient un repère que install.sh remplit sur chaque PC :
#   @HOME@  dossier personnel      @MONITOR@  écran principal      @KB_LAYOUT@ / @KB_OPTIONS@  clavier
#   @BROWSER@  navigateur par défaut      @LCX@ @LCY1@..@LCY4@  position des éléments de l'écran de verrouillage
#   @DISTRO_LOGO@  logo de la barre       @POLKIT@  agent des demandes de mot de passe
# Aucun secret n'est copié (liste blanche de fichiers). Contrôle final : rien qui ressemble à un secret.
# Usage : ./export.sh [--preview]   puis vérifier le diff avant de publier
set -euo pipefail
REPO="$(cd "$(dirname "$0")" && pwd)"
cd "$REPO"
. "$HOME/.local/bin/nc-langue" 2>/dev/null || t() { printf '%s' "$1"; }

preview=0
case "${1:-}" in
  --preview) preview=1 ;;
  "") ;;
  *) echo "Usage: $0 [--preview]" >&2; exit 2 ;;
esac
# Ne jamais remplacer du travail local par une version installée plus ancienne.
verifier_propre() {
  local etat
  etat="$(git -C "$REPO" --no-optional-locks status --porcelain --untracked-files=all -- home)" || return 1
  if [ -n "$etat" ]; then
    echo "$(t "Export annulé : home/ contient des modifications locales. Utilise --preview pour comparer sans les remplacer." "Export cancelled: home/ has local changes. Use --preview to compare without replacing them.")" >&2
    return 1
  fi
}
if [ "$preview" = 0 ]; then verifier_propre || exit 1; fi

# Toutes les substitutions et vérifications se font à côté du dépôt existant.
stage="$(mktemp -d "$REPO/.nc-export.XXXXXX")"
nettoyer() {
  if [ ! -e "$REPO/home" ] && [ -d "$stage/previous-home" ]; then
    mv "$stage/previous-home" "$REPO/home"
  fi
  rm -rf -- "$stage"
}
trap nettoyer EXIT
cd "$stage"

HOME_FILES=(
  .config/hypr/hyprland.lua
  .config/hypr/nc
  .config/hypr/hypridle.conf
  .config/uwsm/env
  .config/uwsm/env-hyprland
  .config/kitty/kitty.conf
  .config/kitty/themes/noctalia-dynamic.conf
  .config/qt6ct/qt6ct.conf
  .config/kdeglobals
  .config/noctalia/config.toml
  .config/noctalia/templates
  .config/noctalia/colors.json
  .config/noctalia/arch-logo.png
  .local/share/noctalia/plugins/nc-launcher
  .local/share/noctalia/plugins/nc-carousel
  .local/share/noctalia/plugins/nc-verrou
  .local/share/noctalia/plugins/nc-keys
  .local/share/noctalia/plugins/nc-ile
  .local/share/noctalia/plugins/nc-fenetres
  .local/share/noctalia/plugins/nc-batterie
  .config/quickshell/nc-ile
  .local/share/nc/firefox
  .local/share/nc/finger.png
  .local/share/nc/logos
  .local/bin/nc-apps
  .local/bin/nc-boot-wallpaper
  .local/bin/nc-brightness
  .local/bin/nc-carousel-thumbs
  .local/bin/nc-finger
  .local/bin/nc-anim
  .local/bin/nc-aide
  .local/bin/nc-diag
  .local/bin/nc-sauvegarde
  .local/bin/nc-claude
  .local/bin/nc-assistant
  .local/bin/nc-jarvis
  .local/bin/nc-dictee
  .local/bin/nc-ia
  .local/bin/nc-session
  .local/bin/nc-panne
  .local/share/nc-jarvis/actions.json
  .local/share/nc-jarvis/deployer.py
  .local/share/nc-jarvis/server/nc_gateway.py
  .local/share/nc-jarvis/server/nc_management.py
  .local/share/nc-jarvis/server/nc_runner.py
  .local/share/nc-jarvis/server/nc_engines.py
  .local/share/nc-jarvis/server/nc_telegram.py
  .local/share/nc-jarvis/server/nc_noctalia.py
  .local/share/nc-jarvis/server/nc_google.py
  .local/share/nc-jarvis/server/nc_choix.py
  .local/bin/nc-demander
  .local/bin/nc-paquets
  .local/bin/nc-alertes
  .local/bin/nc-fenetre
  .local/bin/nc-firefox
  .local/bin/nc-logiciels
  .local/bin/nc-aide-config
  .local/bin/nc-qs-capture
  .local/bin/nc-langue
  .local/bin/nc-meteo
  .local/bin/nc-video
  .local/bin/nc-fermer
  .local/bin/nc-greeting
  .local/bin/nc-capture
  .local/bin/nc-session-propre
  .local/bin/nc-noctalia-avant
  .local/bin/nc-keys
  .local/bin/nc-icones
  .local/bin/nc-ile-etat
  .local/bin/nc-ile-memo
  .local/bin/nc-presse-capture
  .local/bin/nc-verrou-media
  .local/bin/nc-media
  .local/bin/nc-touches
  .local/bin/nc-memoire
  .local/bin/nc-reglages
  .local/bin/nc-launch
  .local/bin/nc-maj
  .local/bin/nc-profile-sync
  .local/bin/nc-pouls
  .local/bin/nc-ecran-externe
  .local/bin/nc-ecrans
  .local/bin/nc-couvercle
  .local/bin/nc-verrou-place
  .local/bin/nc-raccourci
  .local/bin/nc-shell
  .local/bin/nc-shell-msg
  .local/bin/nc-sysinfo
  .local/bin/nc-term-logo
  .local/bin/nc-theme-sync
  .local/bin/nc-wallpaper-colors
  .local/bin/nc-gpu-regle
  .local/bin/nvidia-run
  .local/bin/nc-gpu-mode
  .local/bin/nc-rtx-veille
  .local/bin/cmatrix
  .local/bin/unimatrix
  .local/share/applications/nc-assistant.desktop
  .local/share/applications/nc-jarvis.desktop
  .local/share/applications/nc-jarvis-chat.desktop
  .local/share/applications/nc-reglages.desktop
  .local/share/applications/dropterm.desktop
  .local/share/kio/servicemenus/nc-ia.desktop
  .local/share/nautilus/scripts/IA
  .local/share/nemo/actions/nc-ia-expliquer.nemo_action
  .local/share/nemo/actions/nc-ia-resumer.nemo_action
  .config/xdg-desktop-portal/hyprland-portals.conf
  .config/noctalia/palettes/Apple.json
  .config/fastfetch/nc.jsonc
  .config/nc/greeting.zsh
  .config/nc/ia.zsh
  .config/systemd/user/noctalia.service
  .config/systemd/user/nc-theme-sync.path
  .config/systemd/user/nc-theme-sync.service
  .config/systemd/user/nc-carousel-thumbs.path
  .config/systemd/user/nc-carousel-thumbs.service
  .config/systemd/user/nc-profile-sync.service
  .config/systemd/user/nc-pouls.service
  .config/systemd/user/nc-ile.service
  .config/systemd/user/nc-ecran-externe.service
  .config/systemd/user/nc-couvercle.service
  .config/systemd/user/nc-maj-verif.service
  .config/systemd/user/nc-maj-verif.timer
  .config/systemd/user/nc-paquets.service
  .config/systemd/user/nc-paquets.timer
  .config/systemd/user/nc-alertes.service
  .config/systemd/user/nc-alertes.timer
  .config/systemd/user/nc-panne@.service
  .config/systemd/user/nc-panne@.service.d/sans-boucle.conf
  .config/systemd/user/service.d/nc-panne.conf
  .config/systemd/user/plasma-polkit-agent.service.d/nc-apres-session.conf
  .zshrc
  .p10k.zsh
  .config/nvim
  .face
  Pictures/Wallpapers
)

copy_list() { # copy_list DEST_PREFIX fichier...
  local dest="$1"; shift
  for rel in "$@"; do
    [ -e "$HOME/$rel" ] || { echo "$(t "absent, ignoré : ~/$rel" "missing, skipped: ~/$rel")"; continue; }
    mkdir -p "$dest/$(dirname "$rel")"
    cp -a "$HOME/$rel" "$dest/$rel"
  done
}

copy_list home "${HOME_FILES[@]}"

# Nettoyage : sauvegardes temporaires, caches Python, réglages personnels (jamais publiés)
find home \( -name '*.bak' -o -name '*.tmp' -o -name '*~' -o -name '__pycache__' \) -prune -exec rm -rf {} +
rm -f home/.config/hypr/perso.lua home/.config/hypr/nc/*.tmp
# Généré par nc-profile-sync à chaque session : valeur neutre dans le dépôt
printf '%s\n' "-- Généré par nc-profile-sync à chaque changement de profil énergétique. Ne pas éditer." \
  'return { profil = "balanced", batterie = false, hz = "max" }' > home/.config/hypr/nc/profil.lua

mon=""
have() { command -v "$1" >/dev/null 2>&1; }
have hyprctl && mon=$(hyprctl monitors -j 2>/dev/null | jq -r '([.[] | select(.name | startswith("eDP"))][0] // .[0]).name // empty')

while IFS= read -r -d '' f; do
  grep -Iq . "$f" || continue
  sed -i "s|$HOME|@HOME@|g" "$f"
  [ -n "$mon" ] && sed -i "s|\"$mon\"|\"@MONITOR@\"|g; s|@$mon\"|@@MONITOR@\"|g" "$f"
done < <(find home -type f -print0)

# Clavier
sed -i -E 's/^(\s*kb_layout\s*=\s*)"[^"]*"/\1"@KB_LAYOUT@"/; s/^(\s*kb_options\s*=\s*)"[^"]*"/\1"@KB_OPTIONS@"/' home/.config/hypr/nc/clavier.lua

# Navigateur : le navigateur de ce PC devient celui de la machine cible ; applis personnelles retirées des favoris
sed -i -E 's/"firefox-developer-edition"/"@BROWSER@"/g; s/, "discord"//g' \
  home/.config/noctalia/config.toml home/.local/share/noctalia/plugins/nc-launcher/panel.luau

# Style Qt (Breeze s'il est installé, sinon Fusion) : choisi par install.sh
sed -i -E 's/^style=(Breeze|Fusion)$/style=@QT_STYLE@/; s/^icon_theme=.*/icon_theme=@ICON_THEME@/' home/.config/qt6ct/qt6ct.conf

# Centre de la barre : île Quickshell (vide) ou plugin nc/ile, choisi par install.sh
sed -i -E 's/^center = \[("nc\/ile:pilule")?\]/center = [@ILE_CENTRE@]/' home/.config/noctalia/config.toml
sed -i -E 's/^enable_daemon = (true|false)/enable_daemon = @NOTIF_NOCTALIA@/; s/"group:status"(, "notifications")?\]/"group:status"@NOTIF_WIDGET@]/; /^enabled = \[/s/(, "nc\/ile")?\]/@PLUGIN_ILE@]/' home/.config/noctalia/config.toml

# Barre : logo de la distribution et agent polkit, choisis par install.sh
sed -i -E 's|^custom_image = "[^"]*"|custom_image = "@DISTRO_LOGO@"|; s|^polkit_agent = [a-z]+|polkit_agent = @POLKIT@|' home/.config/noctalia/config.toml

# Écran de verrouillage : positions de cet écran (en points) -> proportions de l'écran de la machine cible
python3 -I - "$(hyprctl monitors -j 2>/dev/null | jq -r --arg m "$mon" '.[] | select(.name == $m) | "\(.width / .scale) \(.height / .scale)"')" <<'EOF'
import os, re, sys
p = "home/.config/noctalia/config.toml"
s = open(p).read()
size = sys.argv[1].split() if len(sys.argv) > 1 else []
lw, lh = (float(size[0]), float(size[1])) if len(size) == 2 else (1600.0, 1000.0)
head, sep, tail = s.partition("[lockscreen_widgets]")
assert sep, "section [lockscreen_widgets] not found" if os.environ.get("NC_LANGUE") == "en" else "section [lockscreen_widgets] introuvable"
sec, sep2, rest = tail.partition("\n[plugins]")
marks = {0.30: "@LCY1@", 0.405: "@LCY2@", 0.64: "@LCY3@", 0.86: "@LCY4@", 0.93: "@LCY5@"}
def y(m):
    v = float(m.group(1)) / lh
    best = min(marks, key=lambda k: abs(k - v))
    return "cy = " + (marks[best] if abs(best - v) < 0.02 else m.group(1))
sec = re.sub(r"^cx = ([0-9.]+)$", lambda m: "cx = @LCX@" if abs(float(m.group(1)) - lw / 2) < 2 else m.group(0), sec, flags=re.M)
sec = re.sub(r"^cy = ([0-9.]+)$", y, sec, flags=re.M)
open(p, "w").write(head + sep + sec + sep2 + rest)
EOF

# Contrôle final : rien qui ressemble à un secret, au nom du compte ou à l'écran de cette machine
user=$(id -un)
bad=$(grep -rIlE "/home/$user\b|([0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}|ghp_[A-Za-z0-9]{20,}|BEGIN [A-Z ]*PRIVATE KEY" home "$REPO/system" 2>/dev/null || true)
[ -n "$mon" ] && bad="$bad$(grep -rIl "\"$mon\"" home 2>/dev/null || true)"
if [ -n "$bad" ]; then echo "$(t "ATTENTION : à vérifier avant de publier :" "WARNING: check before publishing:")" >&2; echo "$bad" >&2; exit 1; fi
if [ "$preview" = 1 ]; then
  git --no-pager diff --no-index -- "$REPO/home" home && exit 0
  code=$?; [ "$code" = 1 ] && exit 0; exit "$code"
fi
verifier_propre || exit 1
mv "$REPO/home" "$stage/previous-home"
mv home "$REPO/home"
echo "$(t "Dépôt mis à jour depuis ce PC." "Repository updated from this PC.")"
