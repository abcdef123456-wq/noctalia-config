#!/usr/bin/env bash
# export.sh : met à jour le dépôt avec la config actuelle de ce PC.
# Les chemins propres au compte (/home/<toi>) deviennent @HOME@ et le nom de l'écran interne @MONITOR@ ;
# install.sh fait l'inverse sur la machine cible. Aucun secret n'est copié (liste blanche de fichiers,
# clé Wallhaven vidée, historique du lanceur vidé).
# Usage : ./export.sh   puis   git add -A && git commit -m "…" && git push
set -euo pipefail
REPO="$(cd "$(dirname "$0")" && pwd)"
cd "$REPO"

HOME_FILES=(
  .config/hypr/hyprland.conf
  .config/hypr/conf.d
  .config/hypr/hypridle.conf
  .config/hypr/noctalia/noctalia-colors.conf
  .config/uwsm/env-hyprland
  .config/uwsm/env
  .config/kitty/kitty.conf
  .config/kitty/themes
  .config/qt6ct/qt6ct.conf
  .config/kdeglobals
  .config/noctalia/settings.json
  .config/noctalia/colors.json
  .config/noctalia/colorschemes
  .config/noctalia/plugins.json
  .config/noctalia/plugins/wallpaperCarousel
  .config/noctalia/plugins/legionLauncher
  .config/autostart/nm-applet.desktop
  .local/share/applications/discord.desktop
  .local/bin/legion-profile
  .local/bin/legion-profile-sync
  .local/bin/legion-theme-sync
  .local/bin/legion-wallpaper-colors
  .local/bin/legion-power-measure
  .local/bin/legion-launch
  .local/bin/legion-boot-wallpaper
  .local/bin/legion-carousel-thumbs
  .local/bin/nvidia-run
  .local/bin/firefox
  .config/systemd/user/legion-theme-sync.path
  .config/systemd/user/legion-theme-sync.service
  .config/systemd/user/legion-profile-sync.service
  .config/systemd/user/legion-carousel-thumbs.path
  .config/systemd/user/legion-carousel-thumbs.service
  .face
  Pictures/Wallpapers
)

# Fichiers système : copie en place si lisible, sinon on garde la version du dépôt.
SYSTEM_FILES=(
  "/etc/tlp.d/10-legion-pro5.conf:system/tlp.d/10-legion-pro5.conf"
  "/boot/grub/themes/legion:system/grub-theme/legion"
  "/usr/share/sddm/themes/sddm-astronaut-theme/Themes/legion.conf:system/sddm/legion.conf"
  "/usr/share/sddm/themes/sddm-astronaut-theme/Backgrounds/legion.jpg:system/sddm/legion.jpg"
)

rm -rf home
for rel in "${HOME_FILES[@]}"; do
  [ -e "$HOME/$rel" ] || { echo "absent, ignoré : ~/$rel"; continue; }
  mkdir -p "home/$(dirname "$rel")"
  cp -a "$HOME/$rel" "home/$rel"
done

# Nettoyage : sauvegardes temporaires, caches Python, historique du lanceur
find home \( -name '*.bak' -o -name '*.tmp' -o -name '*~' -o -name '__pycache__' \) -prune -exec rm -rf {} +
printf '{\n  "lastUsed": {}\n}\n' > home/.config/noctalia/plugins/legionLauncher/settings.json
# Fichier régénéré par legion-profile-sync à chaque session (il contient le mode exact de l'écran de ce PC)
printf '# Généré par legion-profile-sync à l%souverture de session. Ne pas éditer.\n' "'" > home/.config/hypr/conf.d/90-profile.conf

# Noctalia : écran interne générique, clé d'API vidée
mon=$(jq -r '.colorSchemes.monitorForColors // empty' "$HOME/.config/noctalia/settings.json")
jq '.wallpaper.wallhavenApiKey = ""
    | .colorSchemes.monitorForColors = "@MONITOR@"
    | .desktopWidgets.monitorWidgets |= map(.name = "@MONITOR@")' \
  home/.config/noctalia/settings.json > home/settings.tmp && mv home/settings.tmp home/.config/noctalia/settings.json

# Chemins du compte -> @HOME@ (fichiers texte seulement)
while IFS= read -r -d '' f; do
  if grep -Iq . "$f" && grep -q -- "$HOME" "$f"; then
    sed -i "s|$HOME|@HOME@|g" "$f"
  fi
  if [ -n "$mon" ] && grep -Iq . "$f" && [ "$f" != home/.config/noctalia/settings.json ] \
     && grep -qE "\"$mon\"" "$f" 2>/dev/null; then
    sed -i "s|\"$mon\"|\"@MONITOR@\"|g" "$f"
  fi
done < <(find home -type f -print0)

for pair in "${SYSTEM_FILES[@]}"; do
  src="${pair%%:*}"; dst="${pair#*:}"
  if [ -r "$src" ]; then
    rm -rf "$dst"; mkdir -p "$(dirname "$dst")"; cp -a "$src" "$dst"
  else
    echo "illisible, version du dépôt conservée : $src"
  fi
done

# Contrôle final : rien qui ressemble à un secret ou au nom du compte
user=$(id -un)
if grep -rIlE "$HOME|/home/$user\b|([0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}|ghp_[A-Za-z0-9]{20,}|BEGIN [A-Z ]*PRIVATE KEY" home system tools 2>/dev/null; then
  echo "ATTENTION : fichiers ci-dessus à vérifier avant de publier." >&2
  exit 1
fi
echo "Dépôt mis à jour depuis ce PC."
