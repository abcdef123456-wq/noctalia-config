#!/usr/bin/env bash
# install.sh : installe la config « Legion » (Hyprland + Noctalia v5) sur ton PC.
#
#   ./install.sh               installation complète, avec une question avant chaque étape système
#   ./install.sh --no-system   seulement ta session (paquets, fichiers, services utilisateur), rien d'autre en root
#   ./install.sh --files-only  seulement la copie des fichiers (aucun paquet, service ni sudo)
#   ./install.sh --restore     remet les fichiers tels qu'avant la dernière installation
#   Options : --legion / --no-legion   forcer ou refuser les profils énergétiques « Legion »
#
# Distributions : Arch (et dérivées), Fedora, Debian/Ubuntu, openSUSE : Hyprland et Noctalia v5 sont installés
# s'ils manquent. Autres distributions : installe Hyprland et Noctalia v5 toi-même (docs.noctalia.dev), puis relance.
# Tout fichier remplacé est d'abord sauvegardé dans ~/.local/state/legion-dotfiles/backup-<date>/.
# Le script ne lance jamais de mise à jour système et ne touche au démarrage (GRUB, Plymouth, initramfs)
# que si tu réponds oui à la question correspondante (Arch seulement).
set -euo pipefail

REPO="$(cd "$(dirname "$0")" && pwd)"
STATE="$HOME/.local/state/legion-dotfiles"
BK="$STATE/backup-$(date +%Y%m%d-%H%M%S)"
MODE=full
LEGION_OPT=auto
NOCT_DOCS=https://docs.noctalia.dev/noctalia/getting-started/installation/

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

for a in "$@"; do
  case "$a" in
    --no-system) MODE=nosystem ;;
    --files-only) MODE=files ;;
    --restore) MODE=restore ;;
    --legion) LEGION_OPT=yes ;;
    --no-legion) LEGION_OPT=no ;;
    -h|--help) sed -n '2,14p' "$0"; exit 0 ;;
    *) die "option inconnue : $a (voir ./install.sh --help)" ;;
  esac
done
[ "$(id -u)" != 0 ] || die "lance ce script sans sudo : il demandera ton mot de passe quand il en aura besoin."

# ── Distribution ─────────────────────────────────────────────────────────────
OSID=""; OSLIKE=""; OSCODE=""; OSVER=""
if [ -r /etc/os-release ]; then
  OSID="$(. /etc/os-release; echo "${ID:-}")"; OSLIKE="$(. /etc/os-release; echo "${ID_LIKE:-}")"
  OSCODE="$(. /etc/os-release; echo "${VERSION_CODENAME:-}")"; OSVER="$(. /etc/os-release; echo "${VERSION_ID:-}")"
fi
FAMILY=other
case " $OSID $OSLIKE " in
  *" arch "*) FAMILY=arch ;;
  *" fedora "*) FAMILY=fedora ;;
  *" debian "*|*" ubuntu "*) FAMILY=debian ;;
  *suse*) FAMILY=suse ;;
esac

pkg_installed() {
  case "$FAMILY" in
    arch) pacman -Q "$1" ;; fedora|suse) rpm -q "$1" ;; debian) dpkg -s "$1" ;; *) false ;;
  esac >/dev/null 2>&1
}
# Un paquet à la fois : un nom introuvable sur ta distribution n'arrête pas tout.
pkg_install() {
  case "$FAMILY" in
    arch) sudo pacman -S --needed "$@" ;;
    fedora) sudo dnf install -y "$@" ;;
    debian) sudo apt-get install -y "$@" ;;
    suse) sudo zypper --non-interactive install "$@" ;;
    *) return 1 ;;
  esac
}
# Nom générique -> nom du paquet sur cette distribution (vide = pas de paquet, à installer à la main)
pname() {
  case "$1:$FAMILY" in
    imagemagick:fedora|imagemagick:suse) echo ImageMagick ;;
    libnotify:debian) echo libnotify-bin ;;
    libnotify:suse) echo libnotify-tools ;;
    python:arch) echo python ;;
    python:*) echo python3 ;;
    qalc:arch|qalc:fedora) echo libqalculate ;;
    qalc:debian) echo qalc ;;
    qalc:suse) echo qalculate ;;
    bluez-utils:arch) echo bluez-utils ;;
    bluez-utils:*) echo bluez ;;
    nerdfont:arch) echo ttf-cascadia-code-nerd ;;
    adwaita-fonts:arch) echo adwaita-fonts ;;
    noto-fonts:arch) echo noto-fonts ;;
    nerdfont:*|adwaita-fonts:*|noto-fonts:*) ;;
    *) echo "$1" ;;
  esac
}

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
  (cd "$last" && find . -path ./system -prune -o \( -type f -o -type l \) ! -name .created -print0 |
    while IFS= read -r -d '' f; do mkdir -p "$HOME/$(dirname "$f")"; cp -a "$last/$f" "$HOME/$f"; done)
  [ -d "$last/system" ] && warn "Fichiers système sauvegardés dans $last/system : à remettre à la main avec sudo si besoin."
  have systemctl && systemctl --user start noctalia.service 2>/dev/null || true
  ok "Fichiers restaurés. Ferme puis rouvre ta session."
  exit 0
fi

# ── Vérifications ────────────────────────────────────────────────────────────
say "Vérifications"
for t in jq sed find cmp awk; do have "$t" || die "commande manquante : $t (installe-la avec le gestionnaire de paquets de ta distribution)"; done
info "Distribution : ${OSID:-inconnue} (famille : $FAMILY)"

LAPTOP=0; ls /sys/class/power_supply/BAT* >/dev/null 2>&1 && LAPTOP=1
NVIDIA=0; [ -n "$(lspci 2>/dev/null | grep -i nvidia)" ] && NVIDIA=1
dmi() { cat "/sys/class/dmi/id/$1" 2>/dev/null || true; }
LEGION=0
if [ "$LEGION_OPT" = yes ]; then LEGION=1
elif [ "$LEGION_OPT" = auto ] && [ "$(dmi sys_vendor)" = LENOVO ] && echo "$(dmi product_family) $(dmi product_name) $(dmi product_version)" | grep -qi legion; then LEGION=1; fi
info "Portable : $([ $LAPTOP = 1 ] && echo oui || echo non) · Carte NVIDIA : $([ $NVIDIA = 1 ] && echo oui || echo non) · Lenovo Legion : $([ $LEGION = 1 ] && echo "oui ($(dmi product_family))" || echo non)"

hypr_bin() { command -v Hyprland 2>/dev/null || command -v hyprland 2>/dev/null || true; }
hypr_version() {
  local b v=""
  b="$(hypr_bin)"
  [ -n "$b" ] && v="$("$b" --version 2>/dev/null | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -1 || true)"
  if [ -z "$v" ]; then   # repli : version du paquet (la commande peut échouer sans écran)
    case "$FAMILY" in
      arch) v="$(pacman -Q hyprland 2>/dev/null | awk '{print $2}')" ;;
      fedora|suse) v="$(rpm -q --qf '%{VERSION}' hyprland 2>/dev/null || true)" ;;
      debian) v="$(dpkg-query -W -f='${Version}' hyprland 2>/dev/null || true)" ;;
    esac
    v="$(echo "$v" | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -1 || true)"
  fi
  echo "$v"
}
ver_ge() { [ "$(printf '%s\n%s\n' "$2" "$1" | sort -V | head -1)" = "$2" ]; }   # ver_ge A B : A >= B

if [ "$MODE" != files ]; then
  [ "$FAMILY" != other ] || have Hyprland || die "distribution non gérée par l'installateur. Installe Hyprland (0.53 ou plus) et Noctalia v5 ($NOCT_DOCS), puis relance."

  # Hyprland
  if [ -z "$(hypr_bin)" ]; then
    info "Hyprland n'est pas installé."
    ask "L'installer maintenant ?" o || die "Hyprland est nécessaire."
    pkg_install hyprland || die "installation de Hyprland impossible : installe-le toi-même puis relance."
  fi
  hv="$(hypr_version)"
  [ -n "$hv" ] || die "version de Hyprland introuvable."
  ver_ge "$hv" 0.53.0 || die "Hyprland $hv est trop ancien : cette config demande la version 0.53 ou plus (syntaxe des règles). Mets-le à jour ou utilise une distribution qui en propose une récente (Arch, Fedora)."

  # Noctalia v5
  if ! have noctalia; then
    say "Installation de Noctalia v5"
    case "$FAMILY" in
      arch) sudo pacman -S --needed noctalia ;;
      fedora) sudo dnf install -y noctalia ;;
      suse)
        case "$OSID" in
          opensuse-tumbleweed) rp=openSUSE_Tumbleweed ;;
          opensuse-slowroll) rp=openSUSE_Slowroll ;;
          *) rp="" ;;
        esac
        [ -n "$rp" ] || die "version d'openSUSE non gérée : suis $NOCT_DOCS puis relance."
        url="https://download.opensuse.org/repositories/home:neifua:Noctalia/$rp/home:neifua:Noctalia.repo"
        info "Noctalia n'est pas dans les dépôts d'openSUSE : dépôt tiers indiqué par la documentation officielle :"
        info "$url"
        ask "Ajouter ce dépôt et installer Noctalia ?" n || die "Noctalia v5 est nécessaire : $NOCT_DOCS"
        sudo zypper addrepo --refresh --name noctalia-v5 "$url" && sudo zypper --gpg-auto-import-keys refresh && sudo zypper install noctalia ;;
      debian)
        case "$OSCODE" in
          trixie) src=noctalia-trixie.sources ;;
          resolute) src=noctalia-resolute.sources ;;
          sid|"") [ "$OSID" = debian ] && src=noctalia-unstable.sources || src="" ;;
          *) src="" ;;
        esac
        [ -n "$src" ] || die "version de ${OSID:-Debian} non gérée par l'installateur (Debian 13, Debian Sid, Ubuntu 26.04) : suis $NOCT_DOCS puis relance."
        info "Noctalia n'est pas dans les dépôts de ta distribution : dépôt officiel indiqué par la documentation :"
        info "  clé : https://pkg.noctalia.dev/deb/nickh-archive-keyring.deb"
        info "  dépôt : https://pkg.noctalia.dev/deb/$src"
        ask "Ajouter ce dépôt et installer Noctalia ?" n || die "Noctalia v5 est nécessaire : $NOCT_DOCS"
        have wget || sudo apt-get install -y wget
        kd="$(mktemp -d)"; wget -q -O "$kd/keyring.deb" https://pkg.noctalia.dev/deb/nickh-archive-keyring.deb && sudo dpkg -i "$kd/keyring.deb"; rm -rf "$kd"
        sudo wget -q -O "/etc/apt/sources.list.d/$src" "https://pkg.noctalia.dev/deb/$src"
        sudo apt-get update && sudo apt-get install -y noctalia ;;
    esac
    have noctalia || die "Noctalia v5 n'a pas pu être installé : $NOCT_DOCS"
  fi
  if [ "$FAMILY" = arch ] && pkg_installed noctalia-shell; then
    warn "L'ancienne Noctalia v4 (noctalia-shell) est installée. Cette config utilise la v5 : le service « noctalia » de ta session lancera la v5."
    warn "Tu pourras désinstaller la v4 ensuite : sudo pacman -Rns noctalia-shell"
  fi
  ok "Hyprland $hv · Noctalia v5 ($(noctalia --version 2>/dev/null | head -1))"
fi

# Écran interne (nom utilisé par Noctalia pour l'écran de verrouillage) et sa taille « logique »
MON=""; LW=1920; LH=1080
if have hyprctl && hyprctl monitors -j >/dev/null 2>&1; then
  mj="$(hyprctl monitors -j | jq -c '([.[] | select(.name | startswith("eDP"))][0]) // .[0] // empty')"
  if [ -n "$mj" ]; then
    MON="$(jq -r .name <<<"$mj")"
    LW="$(jq -r '(.width / .scale) | floor' <<<"$mj")"; LH="$(jq -r '(.height / .scale) | floor' <<<"$mj")"
  fi
fi
if [ -z "$MON" ]; then
  for s in /sys/class/drm/card*-*/status; do
    [ -r "$s" ] && [ "$(cat "$s")" = connected ] || continue
    n="$(basename "$(dirname "$s")")"; n="${n#card*-}"
    case "$n" in eDP*) MON="$n"; break ;; *) [ -z "$MON" ] && MON="$n" ;; esac
  done
fi
MON="${MON:-eDP-1}"
LCX="$(awk -v w="$LW" 'BEGIN{printf "%.1f", w/2}')"
LCY1="$(awk -v h="$LH" 'BEGIN{printf "%.1f", h*0.30}')"; LCY2="$(awk -v h="$LH" 'BEGIN{printf "%.1f", h*0.405}')"
LCY3="$(awk -v h="$LH" 'BEGIN{printf "%.1f", h*0.64}')";  LCY4="$(awk -v h="$LH" 'BEGIN{printf "%.1f", h*0.86}')"
ok "Écran principal : $MON (${LW}x${LH})"

# Clavier : disposition du système ; bascule Super+Espace seulement s'il y en a plusieurs
KBL="$(localectl status 2>/dev/null | sed -n 's/.*X11 Layout: *//p' | head -1 || true)"
KBL="${KBL:-us}"
KBO=""; case "$KBL" in *,*) KBO="grp:win_space_toggle" ;; esac
ok "Clavier : $KBL"
# Navigateur par défaut (épinglé dans le lanceur et le dock)
BROWSER="$(xdg-settings get default-web-browser 2>/dev/null | sed 's/\.desktop$//' | head -1 || true)"
BROWSER="${BROWSER:-firefox}"
ok "Navigateur : $BROWSER"

echo
info "Ce script va :"
info "  1. installer les paquets manquants (sans mise à jour système) ;"
info "  2. sauvegarder puis remplacer ta config Hyprland, Noctalia, kitty, Qt/KDE ;"
info "  3. activer les services de ta session (barre, couleurs, miniatures, veille) ;"
[ "$MODE" = full ] && info "  4. te proposer, une par une, les étapes système (énergie, Wi-Fi, démarrage, écran de connexion)."
ask "On y va ?" o || exit 0

mkdir -p "$BK"

# ── 1. Paquets ───────────────────────────────────────────────────────────────
GENERIC=(uwsm hypridle xdg-desktop-portal-hyprland kitty dolphin qt6ct papirus-icon-theme cava swaybg imagemagick
         jq grim slurp swappy wl-clipboard brightnessctl libnotify python qalc playerctl fastfetch bluez-utils
         nerdfont adwaita-fonts noto-fonts)
if [ "$MODE" != files ]; then
  say "1. Paquets"
  missing=(); manual=()
  for g in "${GENERIC[@]}"; do
    p="$(pname "$g")"
    if [ -z "$p" ]; then manual+=("$g"); continue; fi
    pkg_installed "$p" && continue
    [ "$g" = nerdfont ] && [ -n "$(fc-list : family 2>/dev/null | grep -i "CaskaydiaCove Nerd Font")" ] && continue
    missing+=("$p")
  done
  if [ ${#missing[@]} -eq 0 ]; then
    ok "Tout est déjà installé."
  elif [ "$FAMILY" = arch ]; then
    unknown=()
    for p in "${missing[@]}"; do pacman -Si "$p" >/dev/null 2>&1 || unknown+=("$p"); done
    if [ ${#unknown[@]} -gt 0 ]; then
      warn "Introuvables dans ta base de paquets : ${unknown[*]}"
      die "ta base de paquets est sans doute ancienne. Lance « sudo pacman -Syu », redémarre si besoin, puis relance ce script."
    fi
    info "À installer : ${missing[*]}"
    pkg_install "${missing[@]}" && ok "Paquets installés."
  else
    failed=()
    for p in "${missing[@]}"; do pkg_install "$p" >/dev/null 2>&1 && info "installé : $p" || failed+=("$p"); done
    [ ${#failed[@]} -eq 0 ] && ok "Paquets installés." || warn "Non installés (nom différent ou absent sur ta distribution) : ${failed[*]}"
  fi
  if [ ${#manual[@]} -gt 0 ]; then
    info "À installer à la main si tu les veux (pas de paquet sur ta distribution) : police « CaskaydiaCove Nerd Font » (terminal), « Adwaita Sans », polices Noto."
  fi
fi

# ── 2. Fichiers ──────────────────────────────────────────────────────────────
say "2. Fichiers de configuration"
NOCT_WAS_ACTIVE=0
if [ "$MODE" != files ] && systemctl --user is-active --quiet noctalia.service 2>/dev/null; then
  NOCT_WAS_ACTIVE=1
  systemctl --user stop noctalia.service   # Noctalia réécrit ses réglages : on l'arrête pendant la copie
fi

roots=("$REPO/home")
[ "$LEGION" = 1 ] && roots+=("$REPO/legion/home")
copied=0; same=0; tmp="$(mktemp)"
trap 'rm -f "$tmp"; rmdir "$BK" 2>/dev/null || true' EXIT   # pas de sauvegarde vide
for root in "${roots[@]}"; do
  while IFS= read -r -d '' src; do
    rel="${src#"$root/"}"
    dst="$HOME/$rel"
    if grep -Iq . "$src" 2>/dev/null; then
      sed -e "s|@HOME@|$HOME|g" -e "s|@MONITOR@|$MON|g" -e "s|@KB_LAYOUT@|$KBL|g" -e "s|@KB_OPTIONS@|$KBO|g" \
          -e "s|@BROWSER@|$BROWSER|g" -e "s|@LCX@|$LCX|g" -e "s|@LCY1@|$LCY1|g" -e "s|@LCY2@|$LCY2|g" \
          -e "s|@LCY3@|$LCY3|g" -e "s|@LCY4@|$LCY4|g" "$src" > "$tmp"
    else
      cp "$src" "$tmp"
    fi
    if [ -f "$dst" ] && cmp -s "$tmp" "$dst"; then same=$((same + 1)); continue; fi
    case "$rel" in
      # Jamais écrasés : tes images et les fichiers régénérés automatiquement sur ce PC
      Pictures/Wallpapers/* | .config/hypr/conf.d/90-profile.conf | .config/hypr/conf.d/35-colors.conf \
      | .config/hypr/noctalia/noctalia-colors.conf | .config/noctalia/colors.json \
      | .config/kitty/themes/current.conf | .config/kitty/themes/noctalia*.conf)
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
  done < <(find "$root" -type f -print0)
done
ok "$copied fichier(s) installé(s), $same déjà à jour. Sauvegarde : $BK"

# Message d'accueil du terminal (zsh)
if [ -f "$HOME/.zshrc" ] || [ "$(basename "${SHELL:-}")" = zsh ]; then
  if ! grep -qF 'legion/greeting.zsh' "$HOME/.zshrc" 2>/dev/null; then
    if [ -f "$HOME/.zshrc" ]; then cp -a "$HOME/.zshrc" "$BK/.zshrc"; else echo ".zshrc" >> "$BK/.created"; fi
    printf '%s\n' '[[ -r ~/.config/legion/greeting.zsh ]] && source ~/.config/legion/greeting.zsh' >> "$HOME/.zshrc"
    ok "Accueil du terminal ajouté à ~/.zshrc"
  fi
else
  info "Accueil du terminal : réservé à zsh (ton shell n'est pas zsh), ignoré."
fi

# Clé de chiffrement de l'historique du presse-papiers : Noctalia ne la crée pas elle-même (64 caractères hexadécimaux
# aléatoires, lisible par toi seul). Générée une fois sur ce PC, jamais versionnée ni écrasée.
KEY="$HOME/.local/state/noctalia/storage.key"
if [ ! -s "$KEY" ]; then
  mkdir -p "$(dirname "$KEY")"
  if ( umask 077; od -An -N32 -tx1 /dev/urandom | tr -d ' \n' > "$KEY" ) && [ "$(wc -c < "$KEY")" = 64 ]; then
    chmod 600 "$KEY"; ok "Clé de l'historique du presse-papiers créée."
  else
    rm -f "$KEY"; warn "Clé du presse-papiers non créée : l'historique du presse-papiers ne fonctionnera pas."
  fi
fi

[ "$MODE" = files ] && { say "Terminé (fichiers seulement)."; exit 0; }

# ── 3. Services de la session ────────────────────────────────────────────────
say "3. Services de ta session"
UNITS=(noctalia.service legion-carousel-thumbs.service)
[ "$LEGION" = 1 ] && UNITS+=(legion-profile-sync.service)
if systemctl --user daemon-reload >/dev/null 2>&1; then
  systemctl --user enable "${UNITS[@]}" >/dev/null 2>&1 || true
  systemctl --user enable --now legion-theme-sync.path legion-carousel-thumbs.path hypridle.service >/dev/null 2>&1 ||
    warn "Certains services n'ont pas pu démarrer maintenant : ils démarreront à la prochaine session."
  "$HOME/.local/bin/legion-theme-sync" >/dev/null 2>&1 || true
  systemctl --user start legion-carousel-thumbs.service >/dev/null 2>&1 || true
  if [ "$NOCT_WAS_ACTIVE" = 1 ] || systemctl --user is-active --quiet graphical-session.target 2>/dev/null; then
    systemctl --user restart noctalia.service 2>/dev/null || true
    if [ "$LEGION" = 1 ]; then systemctl --user restart legion-profile-sync.service 2>/dev/null || true; fi
    have hyprctl && hyprctl reload >/dev/null 2>&1 || true
  fi
  ok "Services activés."
  if ! systemctl --user is-active --quiet graphical-session.target 2>/dev/null; then
    info "Pour que la barre démarre à l'ouverture de session, choisis la session « Hyprland (uwsm-managed) » sur l'écran de connexion."
  fi
else
  warn "Pas de session utilisateur active (installation depuis un terminal de connexion ou SSH ?) : services non activés."
  info "Dans ta session Hyprland, lance : systemctl --user enable --now noctalia.service legion-theme-sync.path legion-carousel-thumbs.path hypridle.service"
fi

# ── 4. Étapes système (une question par étape) ───────────────────────────────
if [ "$MODE" = full ]; then
  SBK="$BK/system"
  sbackup() { sudo mkdir -p "$SBK"; for f in "$@"; do [ -e "$f" ] && sudo cp -a --parents "$f" "$SBK/"; done; sudo chown -R "$(id -u):$(id -g)" "$SBK"; }

  if [ "$LEGION" = 1 ] && [ "$LAPTOP" = 1 ]; then
    say "4a. Énergie : 3 profils (Performance / Équilibré / Économie)"
    if [ "$FAMILY" = arch ]; then
      info "Installe tlp et tlp-pd (remplace power-profiles-daemon) avec des réglages valables pour tous les Legion."
      if ask "Installer les profils énergétiques ?" o; then
        sbackup /etc/tlp.conf /etc/tlp.d
        if systemctl is-enabled --quiet auto-cpufreq.service 2>/dev/null; then
          info "auto-cpufreq entre en conflit avec TLP : il est désactivé (le paquet reste installé)."
          sudo systemctl disable --now auto-cpufreq.service
        fi
        if pacman -Si tlp-pd >/dev/null 2>&1; then
          sudo pacman -S --needed tlp tlp-pd
          sudo install -Dm0644 "$REPO/legion/tlp.d/10-legion.conf" /etc/tlp.d/10-legion.conf
          if grep -q Long_Life /sys/class/power_supply/BAT*/charge_types 2>/dev/null; then
            info "Ta batterie propose une charge limitée à environ 80 % (« Long_Life »), qui la préserve si le PC reste souvent branché."
            ask "Activer cette limite de charge ?" o && sudo install -Dm0644 "$REPO/legion/tlp.d/20-battery-limit.conf" /etc/tlp.d/20-battery-limit.conf
          fi
          sudo systemctl enable --now tlp.service tlp-pd.service
          sudo tlp start >/dev/null && ok "TLP actif (profil Équilibré par défaut)."
        else
          warn "tlp-pd introuvable dans ta base de paquets : étape ignorée (lance « sudo pacman -Syu » puis relance)."
        fi
      fi
    else
      info "Installe power-profiles-daemon (profils fournis par ta distribution ; sur un Legion il pilote les modes du firmware)."
      if ask "Installer les profils énergétiques ?" o; then
        pkg_install power-profiles-daemon && sudo systemctl enable --now power-profiles-daemon.service && ok "Profils actifs."
      fi
    fi
  elif [ "$LAPTOP" = 1 ]; then
    info "Portable non-Legion : profils énergétiques « Legion » non proposés (./install.sh --legion pour les forcer)."
  fi

  if [ "$FAMILY" = arch ]; then
    say "4b. Wi-Fi : pays de réglementation"
    info "Sans pays, le Wi-Fi reste bridé (canaux et puissance au minimum mondial)."
    if ask "Régler le pays du Wi-Fi ?" o; then
      dflt="$(echo "${LANG:-fr_FR}" | sed -nE 's/^[a-z]+_([A-Z]{2}).*/\1/p')"; dflt="${dflt:-FR}"
      cc=""
      { true </dev/tty; } 2>/dev/null && { read -r -p "   Code du pays (2 lettres) [$dflt] " cc </dev/tty || cc=""; }
      cc="$(echo "${cc:-$dflt}" | tr '[:lower:]' '[:upper:]')"
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
  fi

  if [ "$FAMILY" = arch ] && [ -f /etc/default/grub ] && [ -d /boot/grub ] && [ -f /etc/mkinitcpio.conf ]; then
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
  if [ -d "$T" ] && have sddm; then
    say "4d. Écran de connexion SDDM « legion »"
    if ask "Installer l'écran de connexion ?" o; then
      sbackup "$T/metadata.desktop" /etc/sddm.conf.d/theme.conf
      sudo install -Dm0644 "$REPO/system/sddm/legion.conf" "$T/Themes/legion.conf"
      sudo install -Dm0644 "$REPO/system/sddm/legion.jpg" "$T/Backgrounds/legion.jpg"
      sudo sed -i 's#^ConfigFile=.*#ConfigFile=Themes/legion.conf#' "$T/metadata.desktop"
      printf '[Theme]\nCurrent=sddm-astronaut-theme\n' | sudo install -Dm0644 /dev/stdin /etc/sddm.conf.d/theme.conf
      ok "Écran de connexion installé."
    fi
  elif have sddm; then
    info "Écran de connexion : le thème de base « sddm-astronaut-theme » n'est pas installé, étape ignorée (voir le README)."
  fi

  if [ "$FAMILY" = arch ]; then
    say "4e. Entretien : nettoyage automatique du cache des paquets"
    if ask "Garder seulement les 2 dernières versions de chaque paquet en cache (chaque semaine) ?" o; then
      pkg_installed pacman-contrib || sudo pacman -S --needed pacman-contrib
      sudo systemctl enable --now paccache.timer >/dev/null && ok "paccache.timer actif."
    fi
  fi
fi

say "Terminé"
info "Ferme puis rouvre ta session pour que tout s'applique."
info "Raccourcis : Super+/ affiche la fiche · Super+R recherche · Super+W fonds d'écran · Super+Entrée terminal (liste complète : RACCOURCIS.md)."
[ "$NVIDIA" = 1 ] && info "Carte NVIDIA : lancer une appli dessus avec « nvidia-run <commande> » (Steam : nvidia-run %command%)."
info "Retour arrière : ./install.sh --restore   (sauvegarde : $BK)"
