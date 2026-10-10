#!/usr/bin/env bash
# export.sh : met à jour le dépôt avec la config actuelle de ce PC (à lancer sur la machine de référence).
# Ce qui est propre à la machine devient un repère que install.sh remplit sur chaque PC :
#   @HOME@  dossier personnel      @MONITOR@  écran interne        @KB_LAYOUT@ / @KB_OPTIONS@  clavier
#   @BROWSER@  navigateur par défaut      @LCX@ @LCY1@..@LCY4@  position des éléments de l'écran de verrouillage
# Aucun secret n'est copié (liste blanche de fichiers). Contrôle final : rien qui ressemble à un secret.
# Usage : ./export.sh   puis   git add -A && git commit -m "…" && git push
set -euo pipefail
REPO="$(cd "$(dirname "$0")" && pwd)"
cd "$REPO"

# Pour tout le monde
HOME_FILES=(
  .config/hypr/hyprland.conf
  .config/hypr/conf.d
  .config/hypr/hypridle.conf
  .config/hypr/noctalia/noctalia-colors.conf
  .config/uwsm/env
  .config/kitty/kitty.conf
  .config/kitty/themes
  .config/qt6ct/qt6ct.conf
  .config/kdeglobals
  .config/noctalia/config.toml
  .config/noctalia/templates
  .config/noctalia/colors.json
  .config/noctalia/arch-logo.png
  .local/share/noctalia/plugins/legion-launcher
  .local/share/noctalia/plugins/legion-carousel
  .local/share/noctalia/plugins/legion-keys
  .local/bin/legion-apps
  .local/bin/legion-keys
  .local/bin/legion-shell
  .local/bin/legion-shell-msg
  .local/bin/legion-brightness
  .local/bin/legion-pin
  .local/bin/legion-launch
  .local/bin/nvidia-run
  .local/bin/legion-theme-sync
  .local/bin/legion-wallpaper-colors
  .local/bin/legion-boot-wallpaper
  .local/bin/legion-carousel-thumbs
  .local/bin/legion-greeting
  .local/bin/legion-sysinfo
  .local/bin/legion-term-logo
  .config/fastfetch/legion.jsonc
  .config/legion/greeting.zsh
  .config/systemd/user/noctalia.service
  .config/systemd/user/legion-theme-sync.path
  .config/systemd/user/legion-theme-sync.service
  .config/systemd/user/legion-carousel-thumbs.path
  .config/systemd/user/legion-carousel-thumbs.service
  .face
  Pictures/Wallpapers
)
# Seulement sur un Lenovo Legion (profils énergétiques ; détection automatique de l'écran et du clavier)
LEGION_FILES=(
  .local/bin/legion-profile-sync
  .config/systemd/user/legion-profile-sync.service
)

copy_list() { # copy_list DEST_PREFIX fichier...
  local dest="$1"; shift
  for rel in "$@"; do
    [ -e "$HOME/$rel" ] || { echo "absent, ignoré : ~/$rel"; continue; }
    mkdir -p "$dest/$(dirname "$rel")"
    cp -a "$HOME/$rel" "$dest/$rel"
  done
}

rm -rf home legion/home
copy_list home "${HOME_FILES[@]}"
copy_list legion/home "${LEGION_FILES[@]}"

# Nettoyage : sauvegardes temporaires, caches Python
find home legion/home \( -name '*.bak' -o -name '*.tmp' -o -name '*~' -o -name '__pycache__' \) -prune -exec rm -rf {} +
# Généré par legion-profile-sync à chaque session (il contient le mode exact de l'écran de ce PC)
printf '# Généré par legion-profile-sync à l%souverture de session. Ne pas éditer.\n' "'" > home/.config/hypr/conf.d/90-profile.conf

mon=""
have() { command -v "$1" >/dev/null 2>&1; }
have hyprctl && mon=$(hyprctl monitors -j 2>/dev/null | jq -r '[.[] | select(.name | startswith("eDP"))][0].name // empty')

while IFS= read -r -d '' f; do
  grep -Iq . "$f" || continue
  sed -i "s|$HOME|@HOME@|g" "$f"
  [ -n "$mon" ] && sed -i "s|$mon|@MONITOR@|g" "$f"
done < <(find home legion/home -type f -print0)

# Clavier
sed -i -E 's/^(\s*kb_layout\s*=).*/\1 @KB_LAYOUT@/; s/^(\s*kb_options\s*=).*/\1 @KB_OPTIONS@/' home/.config/hypr/conf.d/40-input.conf

# Navigateur : le navigateur de ce PC devient celui de la machine cible ; applis personnelles retirées des favoris
sed -i -E 's/"firefox-developer-edition"/"@BROWSER@"/g; s/, "discord"//g' \
  home/.config/noctalia/config.toml home/.local/share/noctalia/plugins/legion-launcher/panel.luau

# Écran de verrouillage : positions de cet écran (800 x 1000 logiques) -> proportions de l'écran de la machine cible
python3 - <<'EOF'
import re
p = "home/.config/noctalia/config.toml"
s = open(p).read()
head, sep, tail = s.partition("[lockscreen_widgets]")
assert sep, "section [lockscreen_widgets] introuvable"
sec, sep2, rest = tail.partition("\n[plugins]")
ys = {"300.0": "@LCY1@", "405.0": "@LCY2@", "640.0": "@LCY3@", "860.0": "@LCY4@"}
sec = re.sub(r"^cx = 800\.0$", "cx = @LCX@", sec, flags=re.M)
sec = re.sub(r"^cy = ([0-9.]+)$", lambda m: "cy = " + ys.get(m.group(1), m.group(1)), sec, flags=re.M)
open(p, "w").write(head + sep + sec + sep2 + rest)
EOF

# Contrôle final : rien qui ressemble à un secret, au nom du compte ou à l'écran de cette machine
user=$(id -un)
bad=$(grep -rIlE "/home/$user\b|([0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}|ghp_[A-Za-z0-9]{20,}|BEGIN [A-Z ]*PRIVATE KEY" home legion system 2>/dev/null || true)
if [ -n "$bad" ]; then echo "ATTENTION : à vérifier avant de publier :" >&2; echo "$bad" >&2; exit 1; fi
if grep -rIl "storage.key" home | grep -v config.toml >/dev/null 2>&1; then :; fi
echo "Dépôt mis à jour depuis ce PC."
