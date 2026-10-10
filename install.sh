#!/usr/bin/env bash
# install.sh : installe la config « Legion » (Hyprland + Noctalia) sur Arch Linux.
#
#   ./install.sh               installation complète, avec une question avant chaque étape système
#   ./install.sh --no-system   seulement ta session (fichiers, paquets, services utilisateur), rien en root sauf pacman
#   ./install.sh --files-only  seulement la copie des fichiers (aucun paquet, service ni sudo)
#   ./install.sh --restore     remet les fichiers tels qu'avant la dernière installation
#
# Prérequis : Arch Linux avec Hyprland et Noctalia (noctalia-shell) déjà installés.
# Tout fichier remplacé est d'abord sauvegardé dans ~/.local/state/legion-dotfiles/backup-<date>/.
# Le script ne lance jamais de mise à jour système (pacman -Syu) et ne touche au démarrage
# (GRUB, Plymouth, initramfs) que si tu réponds oui à la question correspondante.
set -euo pipefail

REPO="$(cd "$(dirname "$0")" && pwd)"
STATE="$HOME/.local/state/legion-dotfiles"
BK="$STATE/backup-$(date +%Y%m%d-%H%M%S)"
MODE=full

say()  { printf '\n\033[1;35m==\033[0m \033[1m%s\033[0m\n' "$*"; }
info() { printf '   %s\n' "$*"; }
ok()   { printf '   \033[32m✓\033[0m %s\n' "$*"; }
warn() { printf '   \033[33m! %s\033[0m\n' "$*"; }
die()  { printf '\033[31mErreur : %s\033[0m\n' "$*" >&2; exit 1; }
ask() { # ask "question" [o|n]  -> vrai si oui
  local d="${2:-n}" r hint="[o/N]"
  [ "$d" = o ] && hint="[O/n]"
  r=""
  if { true </dev/tty; } 2>/dev/null; then read -r -p "   $1 $hint " r </dev/tty || r=""; else info "$1 -> réponse par défaut ($d)"; fi
  r="${r:-$d}"
  [[ "$r" =~ ^[oOyY] ]]
}
have() { command -v "$1" >/dev/null 2>&1; }
installed() { pacman -Q "$1" >/dev/null 2>&1; }

case "${1:-}" in
  "") ;;
  --no-system) MODE=nosystem ;;
  --files-only) MODE=files ;;
  --restore) MODE=restore ;;
  -h|--help) sed -n '2,13p' "$0"; exit 0 ;;
  *) die "option inconnue : $1 (voir ./install.sh --help)" ;;
esac

[ "$(id -u)" != 0 ] || die "lance ce script sans sudo : il demandera ton mot de passe quand il en aura besoin."

# ── Retour arrière ───────────────────────────────────────────────────────────
if [ "$MODE" = restore ]; then
  last="$(ls -1d "$STATE"/backup-* 2>/dev/null | tail -1)"
  [ -n "$last" ] || die "aucune sauvegarde trouvée dans $STATE"
  say "Restauration de $last"
  ask "Remettre tes anciens fichiers et supprimer ceux ajoutés par l'installation ?" n || exit 0
  have systemctl && systemctl --user stop noctalia.service 2>/dev/null || true
  if [ -f "$last/.created" ]; then
    while IFS= read -r rel; do rm -f "$HOME/$rel"; done < "$last/.created"
  fi
  (cd "$last" && find . \( -path ./system -o -path ./noctalia-shell-copie \) -prune -o \
      \( -type f -o -type l \) ! -name .created -print0 |
    while IFS= read -r -d '' f; do mkdir -p "$HOME/$(dirname "$f")"; cp -a "$f" "$HOME/$f"; done)
  if [ -d "$last/noctalia-shell-copie" ]; then
    rm -rf "$HOME/.config/quickshell/noctalia-shell"
    cp -a "$last/noctalia-shell-copie" "$HOME/.config/quickshell/noctalia-shell"
  fi
  [ -d "$last/system" ] && warn "Fichiers système sauvegardés dans $last/system : à remettre à la main avec sudo si besoin."
  have systemctl && systemctl --user start noctalia.service 2>/dev/null || true
  ok "Fichiers restaurés. Ferme puis rouvre ta session."
  exit 0
fi

# ── Vérifications ────────────────────────────────────────────────────────────
say "Vérifications"
[ -f /etc/arch-release ] || die "ce script est fait pour Arch Linux."
for t in jq sed find cmp; do have "$t" || die "commande manquante : $t (sudo pacman -S jq)"; done
if [ "$MODE" != files ]; then
  installed hyprland || die "Hyprland n'est pas installé (sudo pacman -S hyprland)."
  installed noctalia-shell || [ -d /etc/xdg/quickshell/noctalia-shell ] ||
    die "Noctalia n'est pas installé. Installe-le d'abord depuis l'AUR : paru -S noctalia-shell"
fi
ok "Arch Linux$(installed hyprland && echo ", Hyprland $(pacman -Q hyprland | awk '{print $2}')")$(installed noctalia-shell && echo ", Noctalia $(pacman -Q noctalia-shell | awk '{print $2}')")"

# Écran interne (nom utilisé par Noctalia pour les couleurs et les widgets du bureau)
MON=""
if have hyprctl && hyprctl monitors -j >/dev/null 2>&1; then
  MON="$(hyprctl monitors -j | jq -r '([.[] | select(.name | startswith("eDP"))][0].name) // .[0].name // empty')"
fi
if [ -z "$MON" ]; then
  for s in /sys/class/drm/card*-*/status; do
    [ -r "$s" ] && [ "$(cat "$s")" = connected ] || continue
    n="$(basename "$(dirname "$s")")"; n="${n#card*-}"
    case "$n" in eDP*) MON="$n"; break ;; *) [ -z "$MON" ] && MON="$n" ;; esac
  done
fi
MON="${MON:-eDP-1}"
ok "Écran principal : $MON"

LAPTOP=0; ls /sys/class/power_supply/BAT* >/dev/null 2>&1 && LAPTOP=1
NVIDIA=0; [ -n "$(lspci 2>/dev/null | grep -i nvidia)" ] && NVIDIA=1
info "Portable : $([ $LAPTOP = 1 ] && echo oui || echo non) · Carte NVIDIA : $([ $NVIDIA = 1 ] && echo oui || echo non)"

echo
info "Ce script va :"
info "  1. installer les paquets manquants (dépôts officiels, sans mise à jour système) ;"
info "  2. sauvegarder puis remplacer ta config Hyprland, Noctalia, kitty, Qt/KDE ;"
info "  3. activer les services de ta session (couleurs, profils, veille, miniatures) ;"
[ "$MODE" = full ] && info "  4. te proposer, une par une, les étapes système (énergie, Wi-Fi, démarrage, écran de connexion)."
ask "On y va ?" o || exit 0

mkdir -p "$BK"

# ── 1. Paquets ───────────────────────────────────────────────────────────────
PKGS=(uwsm hypridle xdg-desktop-portal-hyprland kitty dolphin qt6ct papirus-icon-theme cava pacman-contrib
      swaybg imagemagick jq grim wl-clipboard brightnessctl libnotify python
      ttf-cascadia-code-nerd adwaita-fonts noto-fonts bluez-utils)
if [ "$MODE" != files ]; then
  say "1. Paquets"
  missing=()
  for p in "${PKGS[@]}"; do
    installed "$p" && continue
    # Police du terminal déjà présente autrement (par ex. installée à la main dans ~/.fonts)
    [ "$p" = ttf-cascadia-code-nerd ] && [ -n "$(fc-list : family 2>/dev/null | grep -i "CaskaydiaCove Nerd Font")" ] && continue
    missing+=("$p")
  done
  if [ ${#missing[@]} -eq 0 ]; then
    ok "Tout est déjà installé."
  else
    unknown=()
    for p in "${missing[@]}"; do pacman -Si "$p" >/dev/null 2>&1 || unknown+=("$p"); done
    if [ ${#unknown[@]} -gt 0 ]; then
      warn "Introuvables dans ta base de paquets : ${unknown[*]}"
      die "ta base de paquets est sans doute ancienne. Lance « sudo pacman -Syu », redémarre si besoin, puis relance ce script."
    fi
    info "À installer : ${missing[*]}"
    sudo pacman -S --needed "${missing[@]}"
    ok "Paquets installés."
  fi
fi

# ── 2. Fichiers ──────────────────────────────────────────────────────────────
say "2. Fichiers de configuration"
NOCT_WAS_ACTIVE=0
if [ "$MODE" != files ] && systemctl --user is-active --quiet noctalia.service 2>/dev/null; then
  NOCT_WAS_ACTIVE=1
  systemctl --user stop noctalia.service   # Noctalia réécrit ses réglages : on l'arrête pendant la copie
fi

copied=0; same=0; tmp="$(mktemp)"
trap 'rm -f "$tmp"; rmdir "$BK" 2>/dev/null || true' EXIT   # pas de sauvegarde vide
while IFS= read -r -d '' src; do
  rel="${src#"$REPO/home/"}"
  dst="$HOME/$rel"
  if grep -Iq . "$src" 2>/dev/null; then
    sed -e "s|@HOME@|$HOME|g" -e "s|@MONITOR@|$MON|g" "$src" > "$tmp"
  else
    cp "$src" "$tmp"
  fi
  if [ -f "$dst" ] && cmp -s "$tmp" "$dst"; then same=$((same + 1)); continue; fi
  case "$rel" in
    # Jamais écrasés : tes images, et l'état propre à ce PC (réglages d'écran générés, historique du lanceur)
    Pictures/Wallpapers/* | .config/hypr/conf.d/90-profile.conf | .config/noctalia/plugins/legionLauncher/settings.json)
      [ -e "$dst" ] && { same=$((same + 1)); continue; } ;;
  esac
  if [ -e "$dst" ] || [ -L "$dst" ]; then
    mkdir -p "$BK/$(dirname "$rel")"
    cp -aL "$dst" "$BK/$rel"
    rm -f "$dst"
  else
    echo "$rel" >> "$BK/.created"
  fi
  mkdir -p "$(dirname "$dst")"
  cp "$tmp" "$dst"
  chmod --reference="$src" "$dst"
  copied=$((copied + 1))
done < <(find "$REPO/home" -type f -print0)
ok "$copied fichier(s) installé(s), $same déjà à jour. Sauvegarde : $BK"

[ "$MODE" = files ] && { say "Terminé (fichiers seulement)."; exit 0; }

# Correctif Qt 6.12 pour Noctalia 4.4.x (sinon la barre et les panneaux perdent leurs couleurs)
qtv="$(pacman -Q qt6-declarative 2>/dev/null | awk '{print $2}')"
if [ -n "$qtv" ] && [ "$(vercmp "$qtv" 6.12)" -ge 0 ]; then
  info "Qt $qtv : application du correctif de compatibilité de Noctalia…"
  [ -d "$HOME/.config/quickshell/noctalia-shell" ] && cp -a "$HOME/.config/quickshell/noctalia-shell" "$BK/noctalia-shell-copie"
  if python3 "$REPO/tools/noctalia-qt612-patch.py" --force; then
    ok "Correctif Qt 6.12 appliqué."
  else
    warn "Correctif non appliqué (version de Noctalia différente de celle prévue). Si les couleurs de la barre disparaissent, signale-le."
  fi
fi

# ── 3. Services de la session ────────────────────────────────────────────────
say "3. Services de ta session"
systemctl --user daemon-reload
systemctl --user enable noctalia.service legion-profile-sync.service legion-carousel-thumbs.service >/dev/null 2>&1 || true
systemctl --user enable --now legion-theme-sync.path legion-carousel-thumbs.path hypridle.service >/dev/null 2>&1 ||
  warn "Certains services n'ont pas pu démarrer maintenant : ils démarreront à la prochaine session."
"$HOME/.local/bin/legion-theme-sync" >/dev/null 2>&1 || true
systemctl --user start legion-carousel-thumbs.service >/dev/null 2>&1 || true
if [ "$NOCT_WAS_ACTIVE" = 1 ] || systemctl --user is-active --quiet graphical-session.target 2>/dev/null; then
  systemctl --user restart noctalia.service 2>/dev/null || true
  systemctl --user restart legion-profile-sync.service 2>/dev/null || true
  have hyprctl && hyprctl reload >/dev/null 2>&1 || true
fi
ok "Services activés."

# ── 4. Étapes système (une question par étape) ───────────────────────────────
if [ "$MODE" = full ]; then
  SBK="$BK/system"
  sbackup() { sudo mkdir -p "$SBK"; for f in "$@"; do [ -e "$f" ] && sudo cp -a --parents "$f" "$SBK/"; done; sudo chown -R "$(id -u):$(id -g)" "$SBK"; }

  if [ "$LAPTOP" = 1 ]; then
    say "4a. Énergie : TLP + 3 profils (Performance / Équilibré / Économie)"
    info "Installe tlp et tlp-pd (remplace power-profiles-daemon, utilisé par Noctalia pour les profils),"
    info "avec réglages AMD + charge limitée pour préserver la batterie (portables Lenovo)."
    if ask "Installer les profils énergétiques ?" o; then
      sbackup /etc/tlp.conf /etc/tlp.d
      if systemctl is-enabled --quiet auto-cpufreq.service 2>/dev/null; then
        info "auto-cpufreq entre en conflit avec TLP : il est désactivé (le paquet reste installé)."
        sudo systemctl disable --now auto-cpufreq.service
      fi
      if pacman -Si tlp-pd >/dev/null 2>&1; then
        sudo pacman -S --needed tlp tlp-pd
        sudo install -Dm0644 "$REPO/system/tlp.d/10-legion-pro5.conf" /etc/tlp.d/10-legion-pro5.conf
        sudo systemctl enable --now tlp.service tlp-pd.service
        sudo tlp start >/dev/null && ok "TLP actif (profil Équilibré par défaut)."
      else
        warn "tlp-pd introuvable dans ta base de paquets : étape ignorée (lance « sudo pacman -Syu » puis relance)."
      fi
    fi
  fi

  say "4b. Wi-Fi : pays de réglementation"
  info "Sans pays, le Wi-Fi reste bridé (canaux et puissance au minimum mondial)."
  if ask "Régler le pays du Wi-Fi ?" o; then
    cc=""
    { true </dev/tty; } 2>/dev/null && { read -r -p "   Code du pays (2 lettres) [FR] " cc </dev/tty || cc=""; }
    cc="$(echo "${cc:-FR}" | tr '[:lower:]' '[:upper:]')"
    if [[ "$cc" =~ ^[A-Z]{2}$ ]]; then
      sbackup /etc/conf.d/wireless-regdom
      sudo pacman -S --needed wireless-regdb
      sudo sed -i -E 's/^WIRELESS_REGDOM=/#&/' /etc/conf.d/wireless-regdom
      echo "WIRELESS_REGDOM=\"$cc\"" | sudo tee -a /etc/conf.d/wireless-regdom >/dev/null
      have iw && sudo iw reg set "$cc" || true
      ok "Pays du Wi-Fi : $cc"
    else
      warn "Code invalide : étape ignorée."
    fi
  fi

  if [ -f /etc/default/grub ] && [ -d /boot/grub ] && [ -f /etc/mkinitcpio.conf ]; then
    say "4c. Démarrage : thème GRUB « legion » + logo animé (Plymouth)"
    warn "Cette étape modifie le démarrage (GRUB, initramfs). Tout est sauvegardé avant."
    info "Secours si l'écran reste noir au démarrage : dans GRUB, touche « e », retirer « splash », Ctrl+X."
    if ask "Installer le thème de démarrage ?" n; then
      sbackup /etc/default/grub /etc/mkinitcpio.conf /etc/plymouth
      sudo pacman -S --needed plymouth
      if ! grep -qE '^HOOKS=.*\bplymouth\b' /etc/mkinitcpio.conf; then
        if grep -qE '^HOOKS=.*\bkms\b' /etc/mkinitcpio.conf; then
          sudo sed -i -E '/^HOOKS=/ s/\bkms\b/kms plymouth/' /etc/mkinitcpio.conf
        else
          sudo sed -i -E '/^HOOKS=/ s/\budev\b/udev plymouth/; /^HOOKS=/ s/\bsystemd\b/systemd plymouth/' /etc/mkinitcpio.conf
        fi
      fi
      scale=1
      if have hyprctl; then
        s="$(hyprctl monitors -j 2>/dev/null | jq -r '[.[].scale] | max // 1')"
        awk -v s="$s" 'BEGIN{exit !(s >= 1.5)}' && scale=2
      fi
      sudo mkdir -p /etc/plymouth
      printf '[Daemon]\nTheme=bgrt\nDeviceScale=%s\nUseFirmwareBackground=true\n' "$scale" | sudo tee /etc/plymouth/plymouthd.conf >/dev/null
      if sudo mkinitcpio -P; then
        sudo mkdir -p /boot/grub/themes
        sudo rm -rf /boot/grub/themes/legion
        sudo cp -r "$REPO/system/grub-theme/legion" /boot/grub/themes/legion
        grep -qE '^GRUB_CMDLINE_LINUX_DEFAULT=.*\bsplash\b' /etc/default/grub ||
          sudo sed -i -E 's/^(GRUB_CMDLINE_LINUX_DEFAULT="[^"]*)"/\1 splash"/' /etc/default/grub
        if grep -qE '^#?GRUB_THEME=' /etc/default/grub; then
          sudo sed -i -E 's|^#?GRUB_THEME=.*|GRUB_THEME="/boot/grub/themes/legion/theme.txt"|' /etc/default/grub
        else
          echo 'GRUB_THEME="/boot/grub/themes/legion/theme.txt"' | sudo tee -a /etc/default/grub >/dev/null
        fi
        sudo grub-mkconfig -o /boot/grub/grub.cfg && ok "Thème de démarrage installé (visible au prochain redémarrage)."
      else
        warn "La régénération de l'initramfs a échoué : GRUB n'a pas été modifié. Sauvegarde : $SBK"
      fi
    fi
  fi

  T=/usr/share/sddm/themes/sddm-astronaut-theme
  if installed sddm; then
    say "4d. Écran de connexion SDDM « legion »"
    if [ -d "$T" ]; then
      if ask "Installer l'écran de connexion ?" o; then
        sbackup "$T/metadata.desktop" /etc/sddm.conf.d/theme.conf
        sudo install -Dm0644 "$REPO/system/sddm/legion.conf" "$T/Themes/legion.conf"
        sudo install -Dm0644 "$REPO/system/sddm/legion.jpg" "$T/Backgrounds/legion.jpg"
        sudo sed -i 's#^ConfigFile=.*#ConfigFile=Themes/legion.conf#' "$T/metadata.desktop"
        printf '[Theme]\nCurrent=sddm-astronaut-theme\n' | sudo install -Dm0644 /dev/stdin /etc/sddm.conf.d/theme.conf
        ok "Écran de connexion installé."
      fi
    else
      info "Le thème de base « sddm-astronaut-theme » n'est pas installé : étape ignorée."
      info "Pour l'avoir : paru -S sddm-astronaut-theme, puis relance ./install.sh."
    fi
  fi

  say "4e. Entretien : nettoyage automatique du cache des paquets"
  if ask "Garder seulement les 2 dernières versions de chaque paquet en cache (chaque semaine) ?" o; then
    sudo systemctl enable --now paccache.timer >/dev/null && ok "paccache.timer actif."
  fi
fi

say "Terminé"
info "Ferme puis rouvre ta session pour que tout s'applique."
[ "$NVIDIA" = 1 ] && info "Carte NVIDIA : une appli sur la RTX avec « nvidia-run <commande> » (par défaut en mode Performance)."
info "Raccourcis : Super+R applications · Super+W fonds d'écran · Super+² terminal déroulant · Super+, réglages."
info "Retour arrière : ./install.sh --restore   (sauvegarde : $BK)"
