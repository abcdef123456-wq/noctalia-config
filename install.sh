#!/usr/bin/env bash
# install.sh : installe le bureau noctalia-config (Hyprland + Noctalia v5) sur ton PC.
#
#   ./install.sh               installation complète, avec une question avant chaque étape système
#   ./install.sh --no-system   seulement ta session (paquets, fichiers, terminal, services utilisateur), rien d'autre en root
#   ./install.sh --files-only  seulement la copie des fichiers (aucun paquet, service ni sudo)
#   ./install.sh --restore     remet les fichiers tels qu'avant la dernière installation
#
# Distributions : Arch (et dérivées), Fedora, Debian/Ubuntu, openSUSE : Hyprland et Noctalia v5 sont installés
# s'ils manquent. Autres distributions : installe Hyprland (0.55 ou plus) et Noctalia v5 toi-même
# (docs.noctalia.dev), puis relance.
# Tout fichier remplacé est d'abord sauvegardé dans ~/.local/state/noctalia-config/backup-<date>/.
# Le script ne lance jamais de mise à jour système et ne touche au démarrage (Plymouth, GRUB, initramfs)
# que si tu réponds oui à la question correspondante.
set -euo pipefail

REPO="$(cd "$(dirname "$0")" && pwd)"
STATE="$HOME/.local/state/noctalia-config"
OLD_STATE="$HOME/.local/state/legion-dotfiles"   # sauvegardes des versions « legion » de ce dépôt
BK="$STATE/backup-$(date +%Y%m%d-%H%M%S)"
MODE=full
HYPR_MIN=0.55.0
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
    --legion|--no-legion) info "Option $a ignorée : les profils d'énergie sont maintenant proposés sur tous les PC." ;;
    -h|--help) sed -n '2,15p' "$0"; exit 0 ;;
    *) die "option inconnue : $a (voir ./install.sh --help)" ;;
  esac
done
[ "$(id -u)" != 0 ] || die "lance ce script sans sudo : il demandera ton mot de passe quand il en aura besoin."

# ── Distribution ─────────────────────────────────────────────────────────────
OSID=""; OSLIKE=""; OSCODE=""; OSNAME=""; OSLOGO=""
if [ -r /etc/os-release ]; then
  OSID="$(. /etc/os-release; echo "${ID:-}")"; OSLIKE="$(. /etc/os-release; echo "${ID_LIKE:-}")"
  OSCODE="$(. /etc/os-release; echo "${VERSION_CODENAME:-}")"; OSNAME="$(. /etc/os-release; echo "${NAME:-Linux}")"
  OSLOGO="$(. /etc/os-release; echo "${LOGO:-}")"
fi
FAMILY=other
case " $OSID $OSLIKE " in
  *" arch "*) FAMILY=arch ;;
  *" fedora "*) FAMILY=fedora ;;
  *" debian "*|*" ubuntu "*) FAMILY=debian ;;
  *suse*) FAMILY=suse ;;
esac

# Debian 13 (trixie) : Hyprland 0.55+ n'existe que dans les « backports » officiels de Debian (paquets plus récents
# publiés par Debian elle-même, https://backports.debian.org). bpo_on : vrai si la source est (ou vient d'être) activée ;
# bpo_install : installe des paquets précis depuis les backports (les autres paquets viennent toujours de trixie).
BPO=""
bpo_on() {
  [ "$OSID" = debian ] && [ "$OSCODE" = trixie ] || return 1
  if ! apt-cache policy 2>/dev/null | grep -qE 'o=Debian Backports.*n=trixie-backports'; then
    info "Hyprland 0.55 ou plus, TLP 1.9 ou plus : seulement dans « trixie-backports », la source officielle de Debian pour les"
    info "versions récentes (https://backports.debian.org). Seuls les paquets demandés en viennent, le reste du système ne change pas."
    ask "Activer trixie-backports ?" o || return 1
    printf 'Types: deb\nURIs: http://deb.debian.org/debian\nSuites: trixie-backports\nComponents: main\nEnabled: yes\nSigned-By: /usr/share/keyrings/debian-archive-keyring.gpg\n' |
      sudo tee /etc/apt/sources.list.d/debian-backports.sources >/dev/null
    sudo apt-get update -q || return 1
  fi
}
bpo_install() { local r=0; BPO="-t trixie-backports"; pkg_install "$@" || r=$?; BPO=""; return $r; }

pkg_installed() {
  case "$FAMILY" in
    arch) pacman -Q "$1" ;; fedora|suse) rpm -q "$1" ;; debian) dpkg -s "$1" ;; *) false ;;
  esac >/dev/null 2>&1
}
pkg_install() {
  case "$FAMILY" in
    arch) sudo pacman -S --needed "$@" ;;
    fedora) sudo dnf install -y "$@" ;;
    debian) sudo apt-get install -y $BPO "$@" ;;
    suse) sudo zypper --non-interactive install "$@" ;;
    *) return 1 ;;
  esac
}
# Un paquet à la fois, sans arrêter le script s'il n'existe pas sur cette distribution. Sortie masquée : aucune
# question ne doit attendre de réponse invisible (pacman demanderait de confirmer ou de choisir un fournisseur).
pkg_try() {
  local p
  for p in "$@"; do
    pkg_installed "$p" && continue
    info "installation : $p"
    if [ "$FAMILY" = arch ]; then sudo pacman -S --needed --noconfirm "$p" >/dev/null 2>&1 || true
    else pkg_install "$p" >/dev/null 2>&1 || true; fi
  done
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
    gdbus:debian) echo libglib2.0-bin ;;
    gdbus:suse) echo glib2-tools ;;
    gdbus:*) echo glib2 ;;
    nerdfont:arch) echo ttf-cascadia-code-nerd ;;
    nerdfont:*) ;;   # proposée en téléchargement à l'étape 3
    adwaita-fonts:debian) ;;   # pas de paquet dans Debian 13 : la barre utilise une police de remplacement
    adwaita-fonts:fedora) echo adwaita-sans-fonts ;;
    noto-fonts:debian) echo fonts-noto-core ;;
    noto-fonts:fedora) echo google-noto-sans-fonts ;;
    noto-fonts:suse) echo noto-sans-fonts ;;
    breeze:fedora) echo plasma-breeze ;;
    breeze:suse) echo breeze6-style ;;
    *) echo "$1" ;;
  esac
}

# ── Retour arrière ───────────────────────────────────────────────────────────
if [ "$MODE" = restore ]; then
  last="$(ls -1d "$STATE"/backup-* "$OLD_STATE"/backup-* 2>/dev/null | awk -F/ '{ print $NF "\t" $0 }' | sort | tail -1 | cut -f2- || true)"
  [ -n "$last" ] || die "aucune sauvegarde trouvée dans $STATE"
  say "Restauration de $last"
  ask "Remettre tes anciens fichiers et supprimer ceux ajoutés par l'installation ?" n || exit 0
  have systemctl && systemctl --user stop noctalia.service 2>/dev/null || true
  if [ -f "$last/.created" ]; then
    while IFS= read -r rel; do [ -n "$rel" ] && rm -rf "${HOME:?}/$rel"; done < "$last/.created"
  fi
  (cd "$last" && find . -path ./system -prune -o \( -type f -o -type l \) ! -name .created -print0 |
    while IFS= read -r -d '' f; do mkdir -p "$HOME/$(dirname "$f")"; cp -a "$last/$f" "$HOME/$f"; done)
  [ -d "$last/system" ] && warn "Fichiers système sauvegardés dans $last/system : à remettre à la main avec sudo si besoin."
  if have systemctl; then
    systemctl --user daemon-reload 2>/dev/null || true
    systemctl --user start noctalia.service 2>/dev/null || true
  fi
  ok "Fichiers restaurés. Ferme puis rouvre ta session."
  exit 0
fi

# ── Vérifications ────────────────────────────────────────────────────────────
say "Vérifications"
for t in jq sed find cmp awk; do have "$t" || die "commande manquante : $t (installe-la avec le gestionnaire de paquets de ta distribution)"; done
info "Distribution : ${OSNAME:-inconnue} (famille : $FAMILY)"

LAPTOP=0; ls -d /sys/class/power_supply/BAT* >/dev/null 2>&1 && LAPTOP=1
NVIDIA=0; OTHER_GPU=0
for d in /sys/bus/pci/devices/*; do
  [[ $(cat "$d/class" 2>/dev/null) == 0x03* ]] || continue
  if [ "$(cat "$d/vendor" 2>/dev/null)" = 0x10de ]; then NVIDIA=1; else OTHER_GPU=1; fi
done
HYBRID=$((NVIDIA && OTHER_GPU))
dmi() { cat "/sys/class/dmi/id/$1" 2>/dev/null || true; }
info "Portable : $([ $LAPTOP = 1 ] && echo oui || echo non) · Carte NVIDIA : $([ $NVIDIA = 1 ] && { [ $HYBRID = 1 ] && echo "oui (hybride)" || echo oui; } || echo non)"

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
  [ "$FAMILY" != other ] || have Hyprland || die "distribution non gérée par l'installateur. Installe Hyprland (0.55 ou plus) et Noctalia v5 ($NOCT_DOCS), puis relance."

  # Hyprland (Debian 13 : depuis trixie-backports, avec sa veille, son portail et uwsm)
  hv="$(hypr_version)"
  if [ -z "$(hypr_bin)" ] || { [ -n "$hv" ] && ! ver_ge "$hv" "$HYPR_MIN"; }; then
    if [ -z "$(hypr_bin)" ]; then info "Hyprland n'est pas installé."; else info "Hyprland $hv est trop ancien (0.55 ou plus)."; fi
    ask "L'installer maintenant ?" o || die "Hyprland 0.55 ou plus est nécessaire."
    if [ "$OSID" = debian ] && [ "$OSCODE" = trixie ]; then
      bpo_on || die "sans trixie-backports, Debian 13 n'a pas Hyprland 0.55 : relance et réponds oui, ou installe-le toi-même."
      bpo_install hyprland hypridle xdg-desktop-portal-hyprland uwsm || die "installation de Hyprland impossible depuis trixie-backports."
    else
      pkg_install hyprland || die "installation de Hyprland impossible : installe-le toi-même puis relance."
    fi
  fi
  if [ "$OSID" = debian ] && [ "$OSCODE" = trixie ]; then
    bpo_need=(); for p in hypridle xdg-desktop-portal-hyprland uwsm; do pkg_installed "$p" || bpo_need+=("$p"); done
    [ ${#bpo_need[@]} -eq 0 ] || { bpo_on && bpo_install "${bpo_need[@]}"; } || warn "Non installés depuis trixie-backports : ${bpo_need[*]}"
  fi
  hv="$(hypr_version)"
  [ -n "$hv" ] || die "version de Hyprland introuvable."
  ver_ge "$hv" "$HYPR_MIN" || die "Hyprland $hv est trop ancien : cette config utilise le format Lua de Hyprland 0.55 ou plus. Mets-le à jour (sur Debian 13 : dépôt « trixie-backports »), puis relance."

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
        ask "Ajouter ce dépôt et installer Noctalia ?" o || die "Noctalia v5 est nécessaire : $NOCT_DOCS"
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
        ask "Ajouter ce dépôt et installer Noctalia ?" o || die "Noctalia v5 est nécessaire : $NOCT_DOCS"
        have wget || sudo apt-get install -y wget
        kd="$(mktemp -d)"; wget -q -O "$kd/keyring.deb" https://pkg.noctalia.dev/deb/nickh-archive-keyring.deb && sudo dpkg -i "$kd/keyring.deb"; rm -rf "$kd"
        sudo wget -q -O "/etc/apt/sources.list.d/$src" "https://pkg.noctalia.dev/deb/$src"
        sudo apt-get update -q || true
        # Debian 13 : ce dépôt est construit pour trixie-backports (comme Hyprland 0.55) : mêmes versions des bibliothèques
        if [ "$OSCODE" = trixie ]; then { bpo_on && bpo_install noctalia; } || true; else pkg_install noctalia || true; fi ;;
    esac
    have noctalia || die "Noctalia v5 n'a pas pu être installé : $NOCT_DOCS"
  fi
  if [ "$FAMILY" = arch ] && pkg_installed noctalia-shell; then
    warn "L'ancienne Noctalia v4 (noctalia-shell) est installée. Cette config utilise la v5 : le service « noctalia » de ta session lancera la v5."
    warn "Tu pourras désinstaller la v4 ensuite : sudo pacman -Rns noctalia-shell"
  fi
  ok "Hyprland $hv · Noctalia v5 ($(noctalia --version 2>/dev/null | head -1))"
fi

# ── Écran ────────────────────────────────────────────────────────────────────
# Écran principal : l'écran interne d'un portable (eDP), sinon le premier branché.
# Sa définition (pixels), sa taille physique (mm), puis l'échelle que choisira la config (nc/ecrans.lua : mêmes
# seuils que Hyprland, sans descendre sous 1600 x 900 points) et donc sa taille « logique » en points.
MON=""; PXW=0; PXH=0; MMW=0; MMH=0
if have hyprctl && hyprctl monitors -j >/dev/null 2>&1; then
  mj="$(hyprctl monitors all -j | jq -c '([.[] | select(.name | startswith("eDP"))][0]) // .[0] // empty')"
  if [ -n "$mj" ]; then
    MON="$(jq -r .name <<<"$mj")"
    read -r PXW PXH < <(jq -r '[.availableModes[]? | capture("^(?<w>[0-9]+)x(?<h>[0-9]+)@") | {w: (.w|tonumber), h: (.h|tonumber)}]
      + [{w: .width, h: .height}] | max_by(.w * .h) | "\(.w) \(.h)"' <<<"$mj")
    MMW="$(jq -r '.physicalWidth // 0' <<<"$mj")"; MMH="$(jq -r '.physicalHeight // 0' <<<"$mj")"
  fi
fi
if [ -z "$MON" ]; then   # pas de session Hyprland : lecture directe des écrans branchés
  for s in /sys/class/drm/card*-*/status; do
    [ -r "$s" ] && [ "$(cat "$s")" = connected ] || continue
    c="$(dirname "$s")"; n="$(basename "$c")"; n="${n#card*-}"
    case "$n" in eDP*) ;; *) [ -n "$MON" ] && continue ;; esac
    MON="$n"
    read -r PXW PXH < <(awk -Fx '{ if ($1 * $2 > w * h) { w = $1; h = $2 } } END { print w + 0, h + 0 }' "$c/modes" 2>/dev/null)
    # Taille physique : octets 21 et 22 de l'EDID (en cm)
    if [ -r "$c/edid" ] && [ "$(stat -c %s "$c/edid")" -ge 23 ]; then
      read -r MMW MMH < <(od -An -tu1 -j21 -N2 "$c/edid" | awk '{ print $1 * 10, $2 * 10 }')
    fi
    case "$n" in eDP*) break ;; esac
  done
fi
MON="${MON:-eDP-1}"; [ "${PXW:-0}" -gt 0 ] || { PXW=1920; PXH=1080; }
read -r SCALE LW LH < <(awk -v w="$PXW" -v h="$PXH" -v pw="${MMW:-0}" -v ph="${MMH:-0}" 'BEGIN {
  voulu = 1
  if (pw > 0 && ph > 0) { ppp = sqrt(w*w + h*h) / (sqrt(pw*pw + ph*ph) / 25.4); if (ppp > 200) voulu = 2; else if (ppp > 140) voulu = 1.5 }
  plafond = w / 1600; if (h / 900 < plafond) plafond = h / 900; if (plafond < 1) plafond = 1
  if (voulu > plafond) voulu = plafond; if (voulu < 1) voulu = 1
  base = int(voulu * 120 + 0.5); best = 120; found = 0
  for (i = 0; i <= 120 && !found; i++) for (j = 0; j < 2 && !found; j++) {
    k = (j == 0) ? base + i : base - i
    if (k >= 120 && k / 120 <= plafond + 1e-9 && (w * 120) % k == 0 && (h * 120) % k == 0) { best = k; found = 1 }
  }
  printf "%.4g %d %d\n", best / 120, w * 120 / best, h * 120 / best }')
LCX="$(awk -v w="$LW" 'BEGIN{printf "%.1f", w/2}')"
LCY1="$(awk -v h="$LH" 'BEGIN{printf "%.1f", h*0.30}')"; LCY2="$(awk -v h="$LH" 'BEGIN{printf "%.1f", h*0.405}')"
LCY3="$(awk -v h="$LH" 'BEGIN{printf "%.1f", h*0.64}')";  LCY4="$(awk -v h="$LH" 'BEGIN{printf "%.1f", h*0.86}')"
ok "Écran principal : $MON, ${PXW}x${PXH} pixels, échelle $SCALE (${LW}x${LH} points)"

# Clavier : disposition du système ; bascule Super+Espace seulement s'il y en a plusieurs.
# Sources, dans l'ordre : localectl (X11), /etc/default/keyboard (Debian), clavier de la console (« fr-latin1 » -> fr),
# pays de la langue (fr_FR -> fr). Chaque nom est vérifié dans la liste officielle des dispositions (xkb) :
# « n/a » ou un nom inconnu donnerait « invalid keyboard layout » dans Hyprland.
XKB_LST=/usr/share/X11/xkb/rules/evdev.lst
kb_valide() { # kb_valide "fr,us" : vrai si chaque disposition existe
  local l
  [ -n "$1" ] || return 1
  [ -r "$XKB_LST" ] || { [[ "$1" =~ ^[a-z]{2,3}(,[a-z]{2,3})*$ ]]; return; }
  for l in ${1//,/ }; do
    awk -v l="$l" '/^! layout/{f=1;next} /^!/{f=0} f && $1==l {t=1} END{exit !t}' "$XKB_LST" || return 1
  done
}
KBL=""
for kb in \
  "$(localectl status 2>/dev/null | sed -n 's/.*X11 Layout: *//p' | head -1 || true)" \
  "$(sed -n 's/^XKBLAYOUT="\{0,1\}\([^"]*\)"\{0,1\}/\1/p' /etc/default/keyboard 2>/dev/null | head -1 || true)" \
  "$(localectl status 2>/dev/null | sed -n 's/.*VC Keymap: *//p' | head -1 | sed -E 's/[-_].*//' || true)" \
  "$(echo "${LANG:-}" | sed -nE 's/^[a-z]+_([A-Z]{2}).*/\1/p' | tr '[:upper:]' '[:lower:]')"; do
  kb="$(echo "$kb" | tr -d ' ')"
  if kb_valide "$kb"; then KBL="$kb"; break; fi
done
KBL="${KBL:-us}"
KBO=""; case "$KBL" in *,*) KBO="grp:win_space_toggle" ;; esac
ok "Clavier : $KBL"
# Navigateur par défaut (épinglé dans la recherche et le dock)
BROWSER="$(xdg-settings get default-web-browser 2>/dev/null | sed 's/\.desktop$//' | head -1 || true)"
BROWSER="${BROWSER:-firefox}"
ok "Navigateur : $BROWSER"
# Langue (écran de connexion)
LOCALE="$(echo "${LANG:-en_US.UTF-8}" | sed -E 's/[.@].*$//')"; [ -n "$LOCALE" ] || LOCALE=en_US
# Logo de la distribution dans la barre (coloré aux couleurs du thème) ; vide = icône de Noctalia
DISTRO_LOGO=""
if [ "$OSID" = arch ]; then
  DISTRO_LOGO="$HOME/.config/noctalia/arch-logo.png"
else
  for n in ${OSLOGO:+"$OSLOGO"} "${OSID}-logo" "${OSID}-logo-icon" "distributor-logo-${OSID}" "${OSID}"; do
    for f in "/usr/share/pixmaps/$n.svg" "/usr/share/pixmaps/$n.png" "/usr/share/icons/hicolor/scalable/apps/$n.svg" \
             "/usr/share/icons/hicolor/256x256/apps/$n.png" "/usr/share/icons/hicolor/128x128/apps/$n.png"; do
      [ -r "$f" ] && { DISTRO_LOGO="$f"; break 2; }
    done
  done
fi
ok "Logo de la barre : ${DISTRO_LOGO:-icône de Noctalia}"
# Demandes de mot de passe (polkit) : l'agent de KDE s'il est installé, sinon celui de Noctalia
POLKIT=true; KDE_POLKIT=0
if systemctl --user cat plasma-polkit-agent.service >/dev/null 2>&1; then POLKIT=false; KDE_POLKIT=1; fi
# Nom affiché au démarrage (GRUB) : modèle du PC s'il est lisible, sinon nom de la distribution
BOOT_TITLE="$( { [ "$(dmi sys_vendor)" = LENOVO ] && dmi product_version || dmi product_name; } | tr -cd 'A-Za-z0-9 ._-' | sed -E 's/ +/ /g; s/^ //; s/ $//')"
w_last="${BOOT_TITLE##* }"
[[ "$w_last" =~ [0-9] && "$w_last" =~ [A-Za-z] && ${#w_last} -ge 5 && "$BOOT_TITLE" == *" "* ]] && BOOT_TITLE="${BOOT_TITLE% *}"
if [ -z "$BOOT_TITLE" ] || [ ${#BOOT_TITLE} -gt 24 ] || echo "$BOOT_TITLE" | grep -qiE 'o\.?e\.?m|system product|default string|to be filled|not specified|not applicable|^[0-9. -]+$'; then
  BOOT_TITLE="$(echo "$OSNAME" | tr -cd 'A-Za-z0-9 ._-')"
fi

# Écran verrouillé : Noctalia (qui dessine l'écran de verrouillage) ne doit pas être relancée, sinon Hyprland affiche
# « l'écran de verrouillage a planté ». L'installation attend que tu sois là.
if [ "$MODE" != files ] && have noctalia && noctalia msg status 2>/dev/null | grep -qE '"locked": *true'; then
  die "l'écran est verrouillé : relance l'installation une fois la session déverrouillée."
fi

echo
info "Ce script va :"
info "  Tout ce qui est déjà en place est sauté : seul ce qui manque ou a changé est fait."
info "  1. installer les paquets manquants (sans mise à jour système) ;"
info "  2. sauvegarder puis remplacer ta config Hyprland, Noctalia, kitty, Qt/KDE ;"
info "  3. te proposer la config du terminal (zsh, oh-my-zsh, powerlevel10k) et de Neovim (LazyVim) ;"
info "  4. activer les services de ta session (barre, couleurs, miniatures, profils d'énergie, veille) ;"
[ "$MODE" = full ] && info "  5. te proposer, une par une, les étapes système pas encore faites (énergie, Wi-Fi, démarrage, écran de connexion, pilote NVIDIA)."
ask "On y va ?" o || exit 0

mkdir -p "$BK"
tmp="$(mktemp)"
trap 'rm -f "$tmp"; rmdir "$BK" 2>/dev/null || true' EXIT   # pas de sauvegarde vide

# Sauvegarde d'un fichier ou dossier de ta session avant de le remplacer ou de le supprimer
backup() { # backup CHEMIN_RELATIF_À_HOME
  local rel="$1"
  [ -e "$HOME/$rel" ] || [ -L "$HOME/$rel" ] || return 0
  mkdir -p "$BK/$(dirname "$rel")"
  cp -a "$HOME/$rel" "$BK/$rel" 2>/dev/null || cp -aL "$HOME/$rel" "$BK/$rel"
}

# ── 1. Paquets ───────────────────────────────────────────────────────────────
GENERIC=(uwsm hypridle xdg-desktop-portal-hyprland xdg-desktop-portal-gtk kitty nautilus qt6ct papirus-icon-theme cava swaybg imagemagick
         jq grim slurp swappy wl-clipboard brightnessctl libnotify python qalc playerctl fastfetch bluez-utils gdbus
         zsh git curl unzip nerdfont adwaita-fonts noto-fonts breeze)
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
    if pkg_install "${missing[@]}"; then ok "Paquets installés."; else warn "Paquets non installés : ${missing[*]} (à installer toi-même)."; fi
  else
    failed=()
    for p in "${missing[@]}"; do pkg_install "$p" >/dev/null 2>&1 && info "installé : $p" || failed+=("$p"); done
    [ ${#failed[@]} -eq 0 ] && ok "Paquets installés." || warn "Non installés (nom différent ou absent sur ta distribution) : ${failed[*]}"
  fi
  if [ ${#manual[@]} -gt 0 ]; then info "La police du terminal (CaskaydiaCove Nerd Font) t'est proposée en téléchargement à l'étape 3."; fi
fi

# ── 2. Fichiers ──────────────────────────────────────────────────────────────
say "2. Fichiers de configuration"
NOCT_WAS_ACTIVE=0
if [ "$MODE" != files ] && systemctl --user is-active --quiet noctalia.service 2>/dev/null; then
  NOCT_WAS_ACTIVE=1
  systemctl --user stop noctalia.service   # Noctalia réécrit ses réglages : on l'arrête pendant la copie
fi

# Ancienne version de ce dépôt (noms « legion ») : fichiers retirés après sauvegarde, réglages renommés
migrated=0
OLD_UNITS=(legion-theme-sync.path legion-theme-sync.service legion-carousel-thumbs.path legion-carousel-thumbs.service legion-profile-sync.service)
for u in "${OLD_UNITS[@]}"; do
  if [ -e "$HOME/.config/systemd/user/$u" ]; then
    systemctl --user disable --now "$u" >/dev/null 2>&1 || true
    backup ".config/systemd/user/$u"; rm -f "$HOME/.config/systemd/user/$u"; migrated=1
  fi
done
for rel in .local/bin/legion-{apps,boot-wallpaper,brightness,carousel-thumbs,finger,greeting,keys,kill,launch,pin,profile,profile-sync,shell,shell-msg,size,sysinfo,term-logo,theme-sync,tosp,wallpaper-colors} \
           .local/share/noctalia/plugins/legion-{launcher,carousel,keys} .config/legion .local/share/legion \
           .config/fastfetch/legion.jsonc .config/kitty/themes/legion-midnight.conf; do
  if [ -e "$HOME/$rel" ]; then backup "$rel"; rm -rf "${HOME:?}/$rel"; migrated=1; fi
done
rm -rf "$HOME/.cache/legion"
PDATA="$HOME/.local/state/noctalia/plugins/data"
if [ -d "$PDATA/legion" ] && [ ! -e "$PDATA/nc" ]; then mv "$PDATA/legion" "$PDATA/nc"; migrated=1; fi
[ -f "$HOME/.config/legion-profile.conf" ] && [ ! -e "$HOME/.config/nc-profile.conf" ] && mv "$HOME/.config/legion-profile.conf" "$HOME/.config/nc-profile.conf"
NSET="$HOME/.local/state/noctalia/settings.toml"
if [ -f "$NSET" ] && grep -qE 'legion-(time|date|media)' "$NSET"; then
  backup .local/state/noctalia/settings.toml
  sed -i -E 's/legion-(time|date|media)/nc-\1/g' "$NSET"; migrated=1
fi
if [ -f "$HOME/.zshrc" ] && grep -qF '.config/legion/greeting.zsh' "$HOME/.zshrc"; then
  backup .zshrc
  sed -i 's#\.config/legion/greeting\.zsh#.config/nc/greeting.zsh#g' "$HOME/.zshrc"; migrated=1
fi
[ "$migrated" = 1 ] && ok "Ancienne version (« legion ») convertie ; ses fichiers sont dans la sauvegarde."

# Icônes façon macOS : thème WhiteSur (github.com/vinceliuice/WhiteSur-icon-theme), installé pour toi seul dans
# ~/.local/share/icons s'il manque (une question) ; sinon Papirus
ICON_THEME=Papirus-Dark
WS="$HOME/.local/share/icons/WhiteSur-dark"
if [ ! -d "$WS" ] && [ "$MODE" != files ] && have git; then
  info "Icônes façon macOS (dossiers, applis) : thème libre WhiteSur, https://github.com/vinceliuice/WhiteSur-icon-theme"
  if ask "Le télécharger (environ 80 Mo) et l'installer pour toi ?" o; then
    wd="$(mktemp -d)"
    if git clone -q --depth 1 https://github.com/vinceliuice/WhiteSur-icon-theme.git "$wd/ws" && bash "$wd/ws/install.sh" -d "$HOME/.local/share/icons" -t default >/dev/null 2>&1; then
      ok "Icônes WhiteSur installées."
    else
      warn "Téléchargement des icônes WhiteSur impossible : Papirus est gardé."
    fi
    rm -rf "$wd"
  fi
fi
[ -d "$WS" ] && ICON_THEME=WhiteSur-dark

# Style des applis Qt / KDE (Dolphin…) : Breeze, le style moderne de KDE, s'il est installé ; sinon Fusion
QT_STYLE=Fusion
[ -n "$(find /usr/lib /usr/lib64 -path '*qt6/plugins/styles/breeze*.so' -print -quit 2>/dev/null || true)" ] && QT_STYLE=Breeze

copied=0; same=0; hypr_changed=0
root="$REPO/home"
while IFS= read -r -d '' src; do
  rel="${src#"$root/"}"
  dst="$HOME/$rel"
  case "$rel" in .zshrc|.p10k.zsh|.config/nvim/*) continue ;; esac   # étapes 3 (terminal) et 3b (Neovim)
  if grep -Iq . "$src" 2>/dev/null; then
    sed -e "s|@HOME@|$HOME|g" -e "s|@MONITOR@|$MON|g" -e "s|@KB_LAYOUT@|$KBL|g" -e "s|@KB_OPTIONS@|$KBO|g" \
        -e "s|@BROWSER@|$BROWSER|g" -e "s|@LCX@|$LCX|g" -e "s|@LCY1@|$LCY1|g" -e "s|@LCY2@|$LCY2|g" \
        -e "s|@LCY3@|$LCY3|g" -e "s|@LCY4@|$LCY4|g" -e "s|@DISTRO_LOGO@|$DISTRO_LOGO|g" -e "s|@POLKIT@|$POLKIT|g" -e "s|@QT_STYLE@|$QT_STYLE|g" -e "s|@ICON_THEME@|$ICON_THEME|g" "$src" > "$tmp"
  else
    cp "$src" "$tmp"
  fi
  if [ -f "$dst" ] && cmp -s "$tmp" "$dst"; then same=$((same + 1)); continue; fi
  case "$rel" in
    # Jamais écrasés : tes images (fonds d'écran, photo de profil) et les fichiers régénérés automatiquement sur ce PC
    Pictures/Wallpapers/* | .face | .config/hypr/nc/couleurs.lua | .config/hypr/nc/profil.lua | .config/kdeglobals \
    | .config/noctalia/colors.json | .config/kitty/themes/noctalia-dynamic.conf)
      [ -e "$dst" ] && { same=$((same + 1)); continue; } ;;
  esac
  if [ -e "$dst" ] || [ -L "$dst" ]; then
    backup "$rel"
  else
    echo "$rel" >> "$BK/.created"
  fi
  # Remplacement d'un seul coup (renommage) : le fichier n'est jamais absent ni à moitié écrit, même pour
  # Hyprland qui recharge sa config dès qu'un fichier change
  mkdir -p "$(dirname "$dst")"
  cp "$tmp" "$dst.nc-new"
  chmod --reference="$src" "$dst.nc-new"
  mv -f "$dst.nc-new" "$dst"
  copied=$((copied + 1))
  case "$rel" in .config/hypr/*) hypr_changed=1 ;; esac
done < <(find "$root" -type f -print0)
ok "$copied fichier(s) installé(s), $same déjà à jour.$([ "$copied" -gt 0 ] && echo " Sauvegarde : $BK")"

# Session Hyprland ouverte avec l'ancien format : bascule à chaud vers hyprland.lua, avant de retirer l'ancienne config
# (Hyprland recharge sa config dès qu'un fichier change : la retirer avant la bascule laisserait la session sans réglages).
if have hyprctl && hyprctl systeminfo 2>/dev/null | grep 'configProvider: hyprlang' >/dev/null; then
  hyprctl reload full-reset >/dev/null 2>&1 && ok "Session Hyprland passée au format Lua."
fi
# Config Hyprland changée : un seul rechargement, une fois tous les fichiers en place
[ "$hypr_changed" = 1 ] && have hyprctl && hyprctl systeminfo 2>/dev/null | grep 'configProvider: lua' >/dev/null && hyprctl reload >/dev/null 2>&1
# Ancienne config Hyprland (format hyprlang) : remplacée par hyprland.lua, donc retirée après sauvegarde.
# hypridle.conf reste : hypridle ne lit que ce format.
HC="$HOME/.config/hypr"
if [ -f "$HC/hyprland.conf" ]; then
  for rel in hyprland.conf conf.d/{00-monitors,10-env,20-autostart,30-look,35-colors,40-input,50-binds,60-rules,90-profile}.conf noctalia/noctalia-colors.conf; do
    [ -e "$HC/$rel" ] && { backup ".config/hypr/$rel"; rm -f "$HC/$rel"; }
  done
  rmdir "$HC/conf.d" "$HC/noctalia" 2>/dev/null || true
  ok "Ancienne config Hyprland (hyprland.conf) remplacée par hyprland.lua ; elle est dans la sauvegarde."
  [ -d "$HC/conf.d" ] && info "Le dossier ~/.config/hypr/conf.d contient encore tes propres fichiers : à reporter dans ~/.config/hypr/perso.lua si tu en as besoin."
fi

# Fichiers (Nautilus, style Apple) : appli par défaut pour les dossiers ; applis GTK en sombre avec les mêmes icônes
# que le reste ; couleurs GTK générées par Noctalia (fond d'écran) ; vignettes moyennes, dossiers en premier
if have gsettings; then
  gsettings set org.gnome.desktop.interface color-scheme prefer-dark 2>/dev/null || true
  gsettings set org.gnome.desktop.interface icon-theme "$ICON_THEME" 2>/dev/null || true
  gsettings set org.gnome.nautilus.preferences default-folder-viewer icon-view 2>/dev/null || true
  gsettings set org.gnome.nautilus.icon-view default-zoom-level medium 2>/dev/null || true
  gsettings set org.gtk.gtk4.Settings.FileChooser sort-directories-first true 2>/dev/null || true
fi
have xdg-mime && [ -n "$(find /usr/share/applications -name org.gnome.Nautilus.desktop -print -quit 2>/dev/null || true)" ] &&
  xdg-mime default org.gnome.Nautilus.desktop inode/directory 2>/dev/null

# Barre latérale de Nautilus, comme les Favoris du Finder : Téléchargements, Documents, Images, Musique, Vidéos
# (dossiers de ta langue, ajoutés seulement s'ils existent et n'y sont pas déjà)
python3 -I - "$HOME/.config/gtk-3.0/bookmarks" <<'PYEOF' 2>/dev/null || true
import os, subprocess, sys, urllib.parse
fichier = sys.argv[1]
os.makedirs(os.path.dirname(fichier), exist_ok=True)
lignes = open(fichier).read().splitlines() if os.path.exists(fichier) else []
deja = {l.split(" ")[0] for l in lignes}
maison = os.path.expanduser("~")
noms = {"DOWNLOAD": ("Downloads", "Téléchargements"), "DOCUMENTS": ("Documents",), "PICTURES": ("Pictures", "Images"),
        "MUSIC": ("Music", "Musique"), "VIDEOS": ("Videos", "Vidéos")}
for nom, secours in noms.items():
    try:
        d = subprocess.run(["xdg-user-dir", nom], capture_output=True, text=True).stdout.strip()
    except OSError:
        d = ""
    if not d or d == maison:            # dossiers utilisateur non configurés : noms courants
        d = next((os.path.join(maison, n) for n in secours if os.path.isdir(os.path.join(maison, n))), "")
    uri = "file://" + urllib.parse.quote(d)
    if d and os.path.isdir(d) and d != os.path.expanduser("~") and uri not in deja:
        lignes.append(uri)
open(fichier, "w").write("\n".join(lignes) + ("\n" if lignes else ""))
PYEOF

# Icônes sobres du terminal et des fichiers, aux couleurs du thème (remplacent le chat de kitty et le dauphin de Dolphin)
"$HOME/.local/bin/nc-icones" >/dev/null 2>&1 || true

# Tes réglages Hyprland personnels : fichier créé une seule fois avec des exemples, jamais remplacé ensuite
PERSO="$HOME/.config/hypr/perso.lua"
if [ ! -e "$PERSO" ]; then
  cat > "$PERSO" <<'PERSO_EOF'
-- Tes réglages Hyprland personnels : chargés en dernier, jamais remplacés par install.sh ni nc-maj.
-- Format Lua de Hyprland 0.55+ (https://wiki.hypr.land). Enlève « -- » devant une ligne pour l'activer.
--
-- Ajouter un raccourci sans éditer ce fichier :   nc-raccourci ajoute "Super+B" "firefox" "Navigateur"
-- (liste : nc-raccourci ; retirer : nc-raccourci retire "Super+B")
--
-- hl.bind("SUPER + B", hl.dsp.exec_cmd("firefox"), { description = "Mes raccourcis|Navigateur" })
-- hl.monitor({ output = "HDMI-A-1", mode = "preferred", position = "auto", scale = 1 })
-- hl.config({ general = { gaps_out = 6 }, decoration = { rounding = 10 } })
-- hl.on("hyprland.start", function() hl.exec_cmd("discord --start-minimized") end)
PERSO_EOF
  echo ".config/hypr/perso.lua" >> "$BK/.created"
fi
# Emplacement de ce dépôt, pour nc-maj (mise à jour en une commande)
if [ -d "$REPO/.git" ]; then mkdir -p "$HOME/.config/nc"; printf '%s\n' "$REPO" > "$HOME/.config/nc/depot"; fi

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

[ "$MODE" = files ] && { say "Terminé (fichiers seulement)."; info "Les configs du terminal (zsh) et de Neovim n'ont pas été touchées : relance sans --files-only pour les installer."; exit 0; }

# ── 3. Terminal : zsh + oh-my-zsh + powerlevel10k ─────────────────────────────
say "3. Terminal : zsh, oh-my-zsh, powerlevel10k (invite sur deux lignes, suggestions, couleurs)"
ZSH_DIR="$HOME/.oh-my-zsh"; ZC="$ZSH_DIR/custom"
declare -A REPOS=(
  ["$ZSH_DIR"]=https://github.com/ohmyzsh/ohmyzsh.git
  ["$ZC/themes/powerlevel10k"]=https://github.com/romkatv/powerlevel10k.git
  ["$ZC/plugins/zsh-autosuggestions"]=https://github.com/zsh-users/zsh-autosuggestions.git
  ["$ZC/plugins/zsh-syntax-highlighting"]=https://github.com/zsh-users/zsh-syntax-highlighting.git
)
need=()
for d in "$ZSH_DIR" "$ZC/themes/powerlevel10k" "$ZC/plugins/zsh-autosuggestions" "$ZC/plugins/zsh-syntax-highlighting"; do
  [ -e "$d" ] || need+=("$d")
done
has_font() { fc-list : family 2>/dev/null | grep -i "CaskaydiaCove Nerd Font" >/dev/null; }
term_done=1
have zsh && have git && [ ${#need[@]} -eq 0 ] && has_font || term_done=0
for f in .zshrc .p10k.zsh; do cmp -s "$REPO/home/$f" "$HOME/$f" || term_done=0; done
[ "$(basename "$(getent passwd "$(id -un)" | cut -d: -f7)")" = zsh ] || term_done=0
if [ "$term_done" = 1 ]; then
  ok "Déjà en place (zsh par défaut, oh-my-zsh, powerlevel10k, police)."
elif ask "Installer la config du terminal (seulement ce qui manque) ?" o; then
  have zsh || pkg_try zsh
  have git || pkg_try git
  if ! have zsh || ! have git; then
    warn "zsh ou git manquant : étape ignorée (installe-les puis relance)."
  else
    if [ ${#need[@]} -gt 0 ]; then
      info "Téléchargements depuis GitHub (dépôts officiels) :"
      for d in "${need[@]}"; do info "  ${REPOS[$d]}"; done
      if ask "Les télécharger ?" o; then
        for d in "${need[@]}"; do
          git clone -q --depth 1 "${REPOS[$d]}" "$d" && echo "${d#"$HOME/"}" >> "$BK/.created" || warn "téléchargement impossible : ${REPOS[$d]}"
        done
      fi
    fi
    for f in .zshrc .p10k.zsh; do
      [ -f "$HOME/$f" ] && cmp -s "$REPO/home/$f" "$HOME/$f" && continue
      if [ -f "$HOME/$f" ]; then
        ask "Remplacer ton ~/$f (il sera sauvegardé) ?" o || continue
        backup "$f"
      else
        echo "$f" >> "$BK/.created"
      fi
      cp "$REPO/home/$f" "$HOME/$f"
    done
    ok "Config du terminal installée. Tes alias et réglages personnels : ~/.zshrc.perso"
    if [ "$(basename "$(getent passwd "$(id -un)" | cut -d: -f7)")" != zsh ]; then
      ask "Faire de zsh ton shell par défaut (il te demandera ton mot de passe) ?" o && chsh -s "$(command -v zsh)" && ok "zsh est ton shell par défaut (à la prochaine connexion)."
    fi
  fi
  # Police du terminal (icônes de l'invite) : paquet sur Arch, sinon téléchargement depuis la page officielle de Nerd Fonts
  if ! has_font; then
    url=https://github.com/ryanoasis/nerd-fonts/releases/latest/download/CascadiaCode.zip
    info "Police du terminal (CaskaydiaCove Nerd Font) absente : $url"
    if have curl && have unzip && ask "La télécharger dans ~/.local/share/fonts ?" o; then
      fd="$HOME/.local/share/fonts/CaskaydiaCove"; zd="$(mktemp -d)"
      if curl -fsSL -o "$zd/f.zip" "$url" && mkdir -p "$fd" && unzip -qo "$zd/f.zip" '*.ttf' -d "$fd"; then
        fc-cache -f "$fd" >/dev/null 2>&1 || true; ok "Police installée."
      else
        warn "Téléchargement de la police impossible."
      fi
      rm -rf "$zd"
    fi
  fi
fi

# ── 3b. Neovim (LazyVim) ──────────────────────────────────────────────────────
say "3b. Neovim : LazyVim avec ses extras (C/C++, JavaScript, formatage, Git…)"
NV="$HOME/.config/nvim"
# Déjà fait : même config que le dépôt, plugins téléchargés, Neovim assez récent et outils essentiels présents
# (gitui et tree-sitter sont facultatifs : absents de certaines distributions, ils ne bloquent rien)
nv_bin() { if [ -x "$HOME/.local/bin/nvim" ]; then echo "$HOME/.local/bin/nvim"; else command -v nvim || true; fi; }   # celui du terminal
nv_ver() { local b; b="$(nv_bin)"; [ -n "$b" ] && "$b" --version 2>/dev/null | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -1 || true; }
nv_tools=()
for c in git rg gcc make node npm; do have "$c" || nv_tools+=("$c"); done
have fd || have fdfind || nv_tools+=(fd)
nv="$(nv_ver)"; { [ -n "$nv" ] && ver_ge "$nv" 0.11.2; } || nv_tools+=("neovim 0.11.2+")
# « À jour » : identique au dépôt, ou déjà installée depuis cette version du dépôt (LazyVim retouche ensuite ses
# fichiers, et tes propres modifications sont gardées tant que la config du dépôt ne change pas)
NV_STAMP="$STATE/nvim-installe"
NV_SUM="$(cd "$REPO/home/.config/nvim" && find . -type f -print0 | sort -z | xargs -0 sha256sum | sha256sum | cut -c1-16)"
nv_same=0
if [ -d "$NV" ] && { diff -rq "$REPO/home/.config/nvim" "$NV" >/dev/null 2>&1 || [ "$(cat "$NV_STAMP" 2>/dev/null)" = "$NV_SUM" ]; }; then
  nv_same=1; mkdir -p "$STATE"; echo "$NV_SUM" > "$NV_STAMP"
fi
nv_plugins=0; [ -d "${XDG_DATA_HOME:-$HOME/.local/share}/nvim/lazy/LazyVim" ] && nv_plugins=1
if [ "$nv_same" = 1 ] && [ "$nv_plugins" = 1 ]; then
  nv_q="Config déjà à jour ; installer les outils manquants (${nv_tools[*]}) ?"
else
  nv_q="Installer la config Neovim (seulement ce qui manque) ?"
fi
if [ "$nv_same" = 1 ] && [ "$nv_plugins" = 1 ] && [ ${#nv_tools[@]} -eq 0 ]; then
  ok "Déjà en place (config, plugins et outils)."
elif ask "$nv_q" o; then
  # Outils dont LazyVim et ses extras ont besoin (noms selon la distribution ; déjà installés ou absents : ignorés)
  case "$FAMILY" in
    arch)   pkg_try neovim git ripgrep fd gcc make nodejs npm tree-sitter-cli gitui ;;
    fedora) pkg_try neovim git ripgrep fd-find gcc make nodejs npm tree-sitter-cli gitui ;;
    debian) pkg_try neovim git ripgrep fd-find gcc make nodejs npm tree-sitter-cli gitui ;;
    suse)   pkg_try neovim git ripgrep fd gcc make nodejs-default npm-default tree-sitter gitui ;;
  esac
  nv="$(nv_ver)"
  # Neovim trop ancien dans la distribution (Debian 13 : 0.10) : version officielle de neovim.io dans ~/.local
  if [ -z "$nv" ] || ! ver_ge "$nv" 0.11.2; then
    case "$(uname -m)" in x86_64) na=nvim-linux-x86_64 ;; aarch64) na=nvim-linux-arm64 ;; *) na="" ;; esac
    url="https://github.com/neovim/neovim/releases/latest/download/$na.tar.gz"
    info "Neovim ${nv:-absent}$([ -n "$nv" ] && echo " (trop ancien)") : LazyVim demande la 0.11.2 ou plus."
    if [ -n "$na" ] && have curl && ask "Installer la version officielle de Neovim dans ~/.local (depuis $url) ?" o; then
      zd="$(mktemp -d)"
      if curl -fsSL -o "$zd/nvim.tar.gz" "$url" && mkdir -p "$HOME/.local/opt" "$HOME/.local/bin" &&
         rm -rf "$HOME/.local/opt/$na" && tar -xzf "$zd/nvim.tar.gz" -C "$HOME/.local/opt"; then
        ln -sfn "$HOME/.local/opt/$na/bin/nvim" "$HOME/.local/bin/nvim"
        nv="$(nv_ver)"; ok "Neovim $nv installé (~/.local/bin/nvim)."
      else
        warn "Téléchargement de Neovim impossible."
      fi
      rm -rf "$zd"
    fi
    if [ -z "$nv" ] || ! ver_ge "$nv" 0.11.2; then
      warn "Neovim 0.11.2 ou plus manquant : config copiée quand même, elle servira dès qu'il sera installé."
    fi
  fi
  if [ "$nv_same" = 1 ]; then
    ok "Config Neovim déjà à jour."
  elif [ ! -e "$NV" ] || ask "Remplacer ta config ~/.config/nvim (elle sera sauvegardée) ?" o; then
    if [ -e "$NV" ]; then backup .config/nvim; rm -rf "$NV"; else echo ".config/nvim" >> "$BK/.created"; fi
    mkdir -p "$HOME/.config" && cp -a "$REPO/home/.config/nvim" "$NV"
    mkdir -p "$STATE"; echo "$NV_SUM" > "$NV_STAMP"
    ok "Config Neovim installée."
    nv_plugins=0
  fi
  # Plugins aux versions exactes de lazy-lock.json (sinon ils s'installent au premier lancement)
  if [ "$nv_plugins" = 0 ] && [ -n "$nv" ] && ver_ge "$nv" 0.11.2 && diff -rq "$REPO/home/.config/nvim" "$NV" >/dev/null 2>&1; then
    # Téléchargement en arrière-plan, avec l'avancement affiché (plugins présents / plugins du lock) ;
    # abandon au bout de 10 minutes (connexion lente) : ils s'installeront alors au premier lancement de nvim.
    nv_total="$(grep -c '"branch"' "$NV/lazy-lock.json" 2>/dev/null || echo '?')"
    nv_lazy="${XDG_DATA_HOME:-$HOME/.local/share}/nvim/lazy"
    info "Téléchargement des plugins Neovim ($nv_total, une à cinq minutes selon la connexion)…"
    timeout 600 "$(nv_bin)" --headless "+Lazy! restore" +qa >/dev/null 2>&1 &
    nv_pid=$!
    while kill -0 "$nv_pid" 2>/dev/null; do
      printf '\r   %s / %s plugins' "$(find "$nv_lazy" -mindepth 1 -maxdepth 1 -type d 2>/dev/null | wc -l)" "$nv_total"
      sleep 2
    done
    printf '\r%60s\r' ''
    if wait "$nv_pid"; then ok "Plugins Neovim installés."
    else warn "Plugins non installés maintenant : ils s'installeront au premier lancement de nvim."; fi
  fi
fi

# ── 4. Services de la session ────────────────────────────────────────────────
say "4. Services de ta session"
UNITS=(noctalia.service nc-carousel-thumbs.service nc-profile-sync.service nc-pouls.service nc-ecran-externe.service)
[ "$KDE_POLKIT" = 1 ] && UNITS+=(plasma-polkit-agent.service)
if systemctl --user daemon-reload >/dev/null 2>&1; then
  systemctl --user enable "${UNITS[@]}" >/dev/null 2>&1 || true
  systemctl --user enable --now nc-theme-sync.path nc-carousel-thumbs.path hypridle.service >/dev/null 2>&1 ||
    warn "Certains services n'ont pas pu démarrer maintenant : ils démarreront à la prochaine session."
  "$HOME/.local/bin/nc-theme-sync" >/dev/null 2>&1 || true
  systemctl --user start nc-carousel-thumbs.service >/dev/null 2>&1 || true
  if [ "$NOCT_WAS_ACTIVE" = 1 ] || systemctl --user is-active --quiet graphical-session.target 2>/dev/null; then
    if [ "$copied" -gt 0 ] || [ "$migrated" = 1 ]; then
      # Session ouverte et fichiers changés : services relancés avec leur nouvelle config
      systemctl --user restart noctalia.service nc-profile-sync.service nc-pouls.service nc-ecran-externe.service hypridle.service 2>/dev/null || true
    else
      systemctl --user start noctalia.service nc-pouls.service 2>/dev/null || true   # rien n'a changé : simplement relancés
    fi
    [ "$KDE_POLKIT" = 1 ] && { systemctl --user start plasma-polkit-agent.service 2>/dev/null || true; }
  fi
  ok "Services activés."
  if ! systemctl --user is-active --quiet graphical-session.target 2>/dev/null; then
    info "Pour que la barre démarre à l'ouverture de session, choisis la session « Hyprland (uwsm-managed) » sur l'écran de connexion."
  fi
else
  warn "Pas de session utilisateur active (installation depuis un terminal de connexion ou SSH ?) : services non activés."
  info "Dans ta session Hyprland, lance : systemctl --user enable --now noctalia.service nc-theme-sync.path nc-carousel-thumbs.path nc-profile-sync.service nc-pouls.service hypridle.service"
fi

# ── 5. Étapes système (une question par étape) ───────────────────────────────
if [ "$MODE" = full ]; then
  SBK="$BK/system"
  sbackup() { sudo mkdir -p "$SBK"; local f; for f in "$@"; do [ -e "$f" ] && sudo cp -a --parents "$f" "$SBK/"; done; sudo chown -R "$(id -u):$(id -g)" "$SBK"; }

  # 5a. Énergie : 3 profils pour tous les PC, via un service compatible power-profiles-daemon (barre, Super + Alt + P).
  # Portable : TLP + tlp-pd avec les réglages du dépôt (mêmes profils partout) quand la distribution les propose
  # (Arch, Fedora 44+, Debian 13 via trixie-backports, openSUSE Tumbleweed) ; sinon le service de la distribution.
  say "5a. Énergie : 3 profils (Performance / Équilibré / Économie)"
  ppd=""
  for u in tlp-pd power-profiles-daemon tuned-ppd; do systemctl is-active --quiet "$u.service" 2>/dev/null && { ppd=$u; break; }; done
  tlp_dispo() {
    case "$FAMILY" in
      arch) pacman -Si tlp-pd >/dev/null 2>&1 ;;
      fedora) dnf -q list --available tlp-pd >/dev/null 2>&1 || rpm -q tlp-pd >/dev/null 2>&1 ;;
      debian) { [ "$OSCODE" != trixie ] || apt-cache policy 2>/dev/null | grep -qE 'o=Debian Backports.*n=trixie-backports' || bpo_on; } &&
              [ -n "$(apt-cache madison tlp-pd 2>/dev/null)" ] ;;
      suse) zypper -q info tlp-pd 2>/dev/null | grep -q '^Name' ;;
      *) false ;;
    esac
  }
  # Limite de charge (préserve la batterie si le PC reste souvent branché) : selon ce que le portable sait faire
  BATLIM=""
  if grep -q '\[Long_Life\]' /sys/class/power_supply/BAT*/charge_types 2>/dev/null ||
     [ "$(cat /sys/class/power_supply/BAT*/charge_control_end_threshold 2>/dev/null | head -1)" -lt 100 ] 2>/dev/null; then
    :   # limite déjà active (réglée ailleurs) : rien à proposer
  elif grep -q Long_Life /sys/class/power_supply/BAT*/charge_types 2>/dev/null; then
    BATLIM="$(cat "$REPO/system/tlp.d/20-battery-limit.conf")"   # mode « Long_Life » (Lenovo et autres)
  elif ls /sys/class/power_supply/BAT*/charge_control_end_threshold >/dev/null 2>&1; then
    BATLIM=$'# /etc/tlp.d/20-battery-limit.conf : limite de charge (noctalia-config). Recharge sous 75 %, arrêt à 80 %.\n# Charge complète ponctuelle : sudo tlp fullcharge   ·   Pour l\'enlever : sudo rm /etc/tlp.d/20-battery-limit.conf\nSTART_CHARGE_THRESH_BAT0=75\nSTOP_CHARGE_THRESH_BAT0=80'
  fi
  # Réglages TLP faits par toi (autres fichiers de /etc/tlp.d que ceux du dépôt) : gardés tels quels, rien n'est ajouté
  TLP_PERSO="$(ls /etc/tlp.d/*.conf 2>/dev/null | grep -vE '/(00-template|10-nc|10-legion|20-battery-limit)\.conf$' || true)"
  tlp_regle() {   # réglages du dépôt dans /etc/tlp.d (et la limite de charge si choisie) ; vrai si quelque chose a changé
    local ch=1
    if [ -n "$TLP_PERSO" ] && [ ! -f /etc/tlp.d/10-nc.conf ] && [ ! -f /etc/tlp.d/10-legion.conf ]; then
      return 1
    fi
    [ -f /etc/tlp.d/10-legion.conf ] && { sbackup /etc/tlp.d/10-legion.conf; sudo rm -f /etc/tlp.d/10-legion.conf; ch=0; }
    cmp -s "$REPO/system/tlp.d/10-nc.conf" /etc/tlp.d/10-nc.conf || { sudo install -Dm0644 "$REPO/system/tlp.d/10-nc.conf" /etc/tlp.d/10-nc.conf; ch=0; }
    if [ -n "$BATLIM" ] && [ ! -f /etc/tlp.d/20-battery-limit.conf ]; then
      info "Ta batterie accepte une limite de charge (environ 80 %), qui la préserve si le PC reste souvent branché."
      if ask "Activer cette limite de charge ?" o; then
        printf '%s\n' "$BATLIM" | sudo install -Dm0644 /dev/stdin /etc/tlp.d/20-battery-limit.conf; ch=0
      fi
    fi
    return $ch
  }
  if [ "$ppd" = tlp-pd ]; then
    if tlp_regle; then sudo tlp start >/dev/null && ok "Réglages TLP mis à jour (/etc/tlp.d/10-nc.conf)."
    elif [ -n "$TLP_PERSO" ] && [ ! -f /etc/tlp.d/10-nc.conf ]; then ok "Déjà en place (TLP avec tes propres réglages : $(echo $TLP_PERSO | xargs -n1 basename | paste -sd' '), gardés)."
    else ok "Déjà en place (TLP et tlp-pd)."; fi
  elif [ "$LAPTOP" = 1 ] && tlp_dispo; then
    info "Portable : TLP et tlp-pd, avec des réglages valables pour tout portable (processeur, turbo, carte PCIe, plateforme)."
    [ -n "$ppd" ] && info "Ils remplacent $ppd (même fonctionnement depuis la barre)."
    if ask "Installer ces profils énergétiques ?" o; then
      sbackup /etc/tlp.conf /etc/tlp.d
      for u in auto-cpufreq tuned power-profiles-daemon; do
        if systemctl is-enabled --quiet "$u.service" 2>/dev/null; then
          info "$u entre en conflit avec TLP : il est désactivé (le paquet reste installé, sauf conflit de paquets)."
          sudo systemctl disable --now "$u.service" >/dev/null 2>&1 || true
        fi
      done
      inst=1
      case "$FAMILY" in
        arch)
          pkg_installed power-profiles-daemon && info "pacman va proposer de remplacer power-profiles-daemon : réponds oui."
          sudo pacman -S --needed tlp tlp-pd || inst=0 ;;
        fedora) sudo dnf install -y --allowerasing tlp tlp-pd || inst=0 ;;
        debian) if [ "$OSCODE" = trixie ]; then bpo_install tlp tlp-pd || inst=0; else pkg_install tlp tlp-pd || inst=0; fi ;;
        suse) sudo zypper --non-interactive install --force-resolution tlp tlp-pd || inst=0 ;;
      esac
      if [ "$inst" = 1 ]; then
        tlp_regle || true
        sudo systemctl enable --now tlp.service tlp-pd.service >/dev/null
        sudo tlp start >/dev/null && ok "TLP actif (profil Équilibré par défaut)."
      else
        warn "Installation de TLP impossible : $([ -n "$ppd" ] && echo "$ppd reste en place" || echo "profils non disponibles")."
        [ -n "$ppd" ] && sudo systemctl enable --now "$ppd.service" >/dev/null 2>&1
      fi
    fi
  elif [ -n "$ppd" ]; then
    ok "Déjà en place (service $ppd)."
  else
    svc=power-profiles-daemon
    [ "$FAMILY" = fedora ] && svc=tuned-ppd   # service de profils par défaut de Fedora
    info "Installe $svc (profils fournis par ta distribution)."
    if ask "Installer les profils énergétiques ?" o; then
      if pkg_install "$svc" && { [ "$svc" != tuned-ppd ] || sudo systemctl enable --now tuned.service; } && sudo systemctl enable --now "$svc.service"; then
        ok "Profils actifs."
      else
        warn "Installation de $svc impossible : les profils ne seront pas disponibles."
      fi
    fi
  fi
  systemctl --user restart nc-profile-sync.service >/dev/null 2>&1 || true

  if [ "$FAMILY" = arch ] && [ -f /etc/conf.d/wireless-regdom ]; then
    say "5b. Wi-Fi : pays de réglementation"
    cc="$(sed -nE 's/^WIRELESS_REGDOM="?([A-Z]{2})"?.*/\1/p' /etc/conf.d/wireless-regdom | tail -1)"
  fi
  if [ "$FAMILY" = arch ] && [ -n "${cc:-}" ]; then
    ok "Déjà réglé (pays : $cc)."
  elif [ "$FAMILY" = arch ] && [ -f /etc/conf.d/wireless-regdom ]; then
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

  # 5c. Démarrage : logo animé (Plymouth) pour tous ; thème « nc » si le chargeur de démarrage est GRUB
  INITRD=""
  if have mkinitcpio && [ -f /etc/mkinitcpio.conf ]; then INITRD=mkinitcpio
  elif have dracut; then INITRD=dracut
  elif have update-initramfs; then INITRD=initramfs-tools
  fi
  GRUBDIR=""; GRUBMK=""
  if [ -f /etc/default/grub ]; then
    for d in /boot/grub2 /boot/grub; do [ -d "$d" ] && { GRUBDIR=$d; break; }; done
    GRUBMK="$(command -v grub-mkconfig || command -v grub2-mkconfig || true)"
    [ -n "$GRUBDIR" ] && [ -n "$GRUBMK" ] || GRUBDIR=""
  fi
  grub_nc() {   # option « splash » du noyau et thème GRUB « nc » (nom du PC dans le titre)
    if ! grep -qE '^GRUB_CMDLINE_LINUX(_DEFAULT)?=.*\b(splash|rhgb)\b' /etc/default/grub; then
      if grep -qE '^GRUB_CMDLINE_LINUX_DEFAULT=' /etc/default/grub; then
        sudo sed -i -E 's/^(GRUB_CMDLINE_LINUX_DEFAULT="[^"]*)"/\1 splash"/' /etc/default/grub
      else
        echo 'GRUB_CMDLINE_LINUX_DEFAULT="quiet splash"' | sudo tee -a /etc/default/grub >/dev/null
      fi
    fi
    # Thème GRUB : nom du PC dans le titre ; l'ancien thème « legion » de ce dépôt est retiré
    sudo rm -rf "$GRUBDIR/themes/legion" "$GRUBDIR/themes/nc"
    sudo mkdir -p "$GRUBDIR/themes"
    sudo cp -r "$REPO/system/grub-theme/nc" "$GRUBDIR/themes/nc"
    sudo sed -i "s|@BOOT_TITLE@|$BOOT_TITLE|" "$GRUBDIR/themes/nc/theme.txt"
    if grep -qE '^#?GRUB_THEME=' /etc/default/grub; then
      sudo sed -i -E "s|^#?GRUB_THEME=.*|GRUB_THEME=\"$GRUBDIR/themes/nc/theme.txt\"|" /etc/default/grub
    else
      echo "GRUB_THEME=\"$GRUBDIR/themes/nc/theme.txt\"" | sudo tee -a /etc/default/grub >/dev/null
    fi
    sudo "$GRUBMK" -o "$GRUBDIR/grub.cfg" && ok "Thème GRUB installé (visible au prochain redémarrage)."
    grep -qE '^GRUB_TIMEOUT_STYLE=hidden' /etc/default/grub &&
      info "Le menu GRUB est masqué sur ta distribution : maintiens Maj (ou Échap) au démarrage pour le voir."
    return 0
  }
  # Déjà fait : Plymouth dans l'initramfs ; avec GRUB, option splash et thème « nc » identique à celui du dépôt
  plym_done=0; grub_done=1
  if [ -n "$INITRD" ] && [ -f /etc/plymouth/plymouthd.conf ] && { have plymouth || [ -x /usr/sbin/plymouthd ]; }; then
    plym_done=1
    [ "$INITRD" = mkinitcpio ] && ! grep -qE '^HOOKS=.*\bplymouth\b' /etc/mkinitcpio.conf && plym_done=0
  fi
  if [ -n "$GRUBDIR" ]; then
    sed "s|@BOOT_TITLE@|$BOOT_TITLE|" "$REPO/system/grub-theme/nc/theme.txt" > "$tmp"
    grep -qE '^GRUB_CMDLINE_LINUX(_DEFAULT)?=.*\b(splash|rhgb)\b' /etc/default/grub &&
      grep -qF "GRUB_THEME=\"$GRUBDIR/themes/nc/theme.txt\"" /etc/default/grub &&
      cmp -s "$tmp" "$GRUBDIR/themes/nc/theme.txt" &&
      diff -rq --exclude=theme.txt "$REPO/system/grub-theme/nc" "$GRUBDIR/themes/nc" >/dev/null 2>&1 || grub_done=0
  fi
  if [ "$plym_done" = 1 ] && [ "$grub_done" = 1 ]; then
    say "5c. Démarrage"
    ok "Déjà en place (logo animé$([ -n "$GRUBDIR" ] && echo ", thème GRUB « nc »"))."
  elif [ "$plym_done" = 1 ]; then
    say "5c. Démarrage : thème GRUB « nc » (« $BOOT_TITLE »)"
    info "Le logo animé est déjà en place ; seul le thème GRUB est à installer ou à mettre à jour."
    if ask "Mettre à jour le thème GRUB ?" o; then
      sbackup /etc/default/grub
      grub_nc
    fi
  elif [ -n "$INITRD" ]; then
    say "5c. Démarrage : logo animé (Plymouth)$([ -n "$GRUBDIR" ] && echo " + thème GRUB « nc » (« $BOOT_TITLE »)")"
    warn "Cette étape modifie le démarrage (initramfs$([ -n "$GRUBDIR" ] && echo ", GRUB")). Tout est sauvegardé avant."
    info "Secours si l'écran reste noir au démarrage : dans GRUB, touche « e », retirer « splash », Ctrl+X."
    if ask "Installer l'écran de démarrage ?" n; then
      sbackup /etc/default/grub /etc/mkinitcpio.conf /etc/plymouth /etc/kernel/cmdline
      pkg_installed plymouth || pkg_install plymouth || warn "Plymouth n'a pas pu être installé."
      if have plymouth || [ -x /usr/sbin/plymouthd ]; then
        theme=bgrt; [ -d /usr/share/plymouth/themes/bgrt ] || theme=spinner
        scale=1; awk -v s="$SCALE" 'BEGIN{exit !(s >= 1.5)}' && scale=2
        sudo mkdir -p /etc/plymouth
        printf '[Daemon]\nTheme=%s\nDeviceScale=%s\nUseFirmwareBackground=true\n' "$theme" "$scale" | sudo tee /etc/plymouth/plymouthd.conf >/dev/null
        rebuilt=0
        case "$INITRD" in
          mkinitcpio)
            if ! grep -qE '^HOOKS=.*\bplymouth\b' /etc/mkinitcpio.conf; then
              if grep -qE '^HOOKS=.*\bkms\b' /etc/mkinitcpio.conf; then
                sudo sed -i -E '/^HOOKS=/ s/\bkms\b/kms plymouth/' /etc/mkinitcpio.conf
              else
                sudo sed -i -E '/^HOOKS=/ s/\budev\b/udev plymouth/; /^HOOKS=/ s/\bsystemd\b/systemd plymouth/' /etc/mkinitcpio.conf
              fi
            fi
            sudo mkinitcpio -P && rebuilt=1 ;;
          dracut) sudo dracut --regenerate-all --force && rebuilt=1 ;;
          initramfs-tools) sudo update-initramfs -u -k all && rebuilt=1 ;;
        esac
        if [ "$rebuilt" = 1 ]; then
          ok "Plymouth installé (thème $theme)."
          # Option « splash » du noyau (Fedora utilise « rhgb », déjà présente)
          if [ -n "$GRUBDIR" ]; then
            grub_nc
          elif [ -f /etc/kernel/cmdline ]; then
            grep -qwE 'splash|rhgb' /etc/kernel/cmdline || sudo sed -i '1 s/$/ splash/' /etc/kernel/cmdline
            info "Option « splash » ajoutée à /etc/kernel/cmdline : elle s'appliquera à la prochaine mise à jour du noyau."
          else
            info "Ajoute « quiet splash » aux options du noyau de ton chargeur de démarrage pour voir le logo animé."
          fi
        else
          warn "La régénération de l'initramfs a échoué : le démarrage n'a pas été modifié davantage. Sauvegarde : $SBK"
        fi
      fi
    fi
  fi

  # 5d. Écran de connexion SDDM (thème de base : sddm-astronaut-theme)
  if have sddm; then
    say "5d. Écran de connexion SDDM « nc »"
    T=/usr/share/sddm/themes/sddm-astronaut-theme
    sed -e "s|@SCREEN_W@|$PXW|g" -e "s|@SCREEN_H@|$PXH|g" -e "s|@LOCALE@|$LOCALE|g" "$REPO/system/sddm/nc.conf" > "$tmp"
    sddm_done() {
      [ -d "$T" ] && cmp -s "$tmp" "$T/Themes/nc.conf" && cmp -s "$REPO/system/sddm/nc.jpg" "$T/Backgrounds/nc.jpg" &&
        grep -q '^ConfigFile=Themes/nc.conf' "$T/metadata.desktop" 2>/dev/null &&
        grep -q '^Current=sddm-astronaut-theme' /etc/sddm.conf.d/theme.conf 2>/dev/null
    }
    if sddm_done; then
      ok "Déjà en place."
    elif [ ! -d "$T" ]; then
      info "Il s'appuie sur le thème libre sddm-astronaut-theme, absent : https://github.com/Keyitdev/sddm-astronaut-theme"
      if ask "Le télécharger (et ses modules Qt) ?" o; then
        case "$FAMILY" in
          arch) pkg_try qt6-svg qt6-virtualkeyboard qt6-multimedia-ffmpeg ;;
          fedora) pkg_try qt6-qtsvg qt6-qtvirtualkeyboard qt6-qtmultimedia ;;
          debian) pkg_try qml6-module-qtquick-virtualkeyboard qml6-module-qtmultimedia libqt6svg6 ;;
          suse) pkg_try qt6-svg-imports qt6-virtualkeyboard-imports qt6-multimedia-imports ;;
        esac
        sudo git clone -q --depth 1 https://github.com/Keyitdev/sddm-astronaut-theme.git "$T" || warn "Téléchargement impossible."
      fi
    fi
    if [ -d "$T" ] && ! sddm_done && ask "Installer l'écran de connexion ?" o; then
      sbackup "$T/metadata.desktop" /etc/sddm.conf.d/theme.conf
      sudo install -Dm0644 "$tmp" "$T/Themes/nc.conf"
      sudo install -Dm0644 "$REPO/system/sddm/nc.jpg" "$T/Backgrounds/nc.jpg"
      sudo rm -f "$T/Themes/legion.conf" "$T/Backgrounds/legion.jpg"
      sudo sed -i 's#^ConfigFile=.*#ConfigFile=Themes/nc.conf#' "$T/metadata.desktop"
      printf '[Theme]\nCurrent=sddm-astronaut-theme\n' | sudo install -Dm0644 /dev/stdin /etc/sddm.conf.d/theme.conf
      ok "Écran de connexion installé."
      systemctl is-enabled --quiet sddm.service 2>/dev/null ||
        info "SDDM n'est pas ton écran de connexion actif : pour l'utiliser, « sudo systemctl enable sddm » (désactive l'autre avant)."
    fi
  fi

  # 5e. Pilote NVIDIA : sans lui, la carte tourne avec « nouveau » (pas d'accélération correcte, pas de mise en veille fine).
  # Cartes récentes (RTX 50, « Blackwell ») : pilote 570.169 ou plus, en version « open » (modules ouverts de NVIDIA).
  if [ "$NVIDIA" = 1 ]; then
    say "5e. Carte NVIDIA"
    nvdev="$(for d in /sys/bus/pci/devices/*; do [ "$(cat "$d/vendor" 2>/dev/null)" = 0x10de ] && [[ $(cat "$d/class" 2>/dev/null) == 0x03* ]] && cat "$d/device"; done | head -1 || true)"
    BLACKWELL=0; [ -n "$nvdev" ] && [ $((nvdev)) -ge $((0x2b00)) ] && BLACKWELL=1
    drv="$(modinfo -F version nvidia 2>/dev/null || true)"
    if [ -n "$drv" ] && { [ "$BLACKWELL" = 0 ] || ver_ge "$drv" 570.169; }; then
      ok "Pilote NVIDIA $drv installé."
    elif [ "$FAMILY" = arch ]; then
      if [ -n "$drv" ]; then info "Pilote NVIDIA $drv trop ancien pour cette carte (570.169 ou plus)."; else info "Pilote NVIDIA absent : la carte tourne sans accélération correcte."; fi
      mapfile -t kernels < <(cat /usr/lib/modules/*/pkgbase 2>/dev/null | sort -u)
      pk=(nvidia-utils)
      if [ "${kernels[*]}" = linux ]; then pk+=(nvidia-open); else pk+=(nvidia-open-dkms); for k in "${kernels[@]}"; do pk+=("$k-headers"); done; fi
      pacman -Sl multilib >/dev/null 2>&1 && pk+=(lib32-nvidia-utils)   # jeux 32 bits (Steam)
      if ask "Installer le pilote officiel de NVIDIA (${pk[*]}) ?" o; then
        if sudo pacman -S --needed "${pk[@]}"; then ok "Pilote NVIDIA installé : redémarre le PC pour l'utiliser."; else warn "Installation du pilote NVIDIA impossible."; fi
      fi
    elif [ "$FAMILY" = debian ] && [ "$BLACKWELL" = 1 ]; then
      warn "Ta carte NVIDIA (série RTX 50) demande le pilote 570.169 ou plus ; Debian ne fournit que le 550, qui ne la gère pas."
      info "Pilote de NVIDIA pour Debian (dépôt officiel de NVIDIA, paquet nvidia-open) :"
      info "  https://docs.nvidia.com/datacenter/tesla/driver-installation-guide/debian.html"
      info "En attendant, l'écran interne fonctionne avec la carte intégrée."
    else
      info "Pilote NVIDIA ${drv:+$drv }à installer avec la méthode de ta distribution :"
      case "$FAMILY" in
        fedora) info "  RPM Fusion : https://rpmfusion.org/Howto/NVIDIA (sudo dnf install akmod-nvidia)" ;;
        debian) info "  https://wiki.debian.org/NvidiaGraphicsDrivers" ;;
        suse) info "  https://en.opensuse.org/SDB:NVIDIA_drivers" ;;
        *) info "  documentation de ta distribution (pilote « nvidia-open » pour les cartes récentes)" ;;
      esac
    fi
  fi

  if [ "$FAMILY" = arch ]; then
    say "5f. Entretien : nettoyage automatique du cache des paquets"
    if systemctl is-enabled --quiet paccache.timer 2>/dev/null; then
      ok "Déjà en place (paccache.timer)."
    elif ask "Garder seulement les 2 dernières versions de chaque paquet en cache (chaque semaine) ?" o; then
      pkg_installed pacman-contrib || sudo pacman -S --needed pacman-contrib
      sudo systemctl enable --now paccache.timer >/dev/null && ok "paccache.timer actif."
    fi
  fi
fi

say "Terminé"
info "Ferme puis rouvre ta session pour que tout s'applique (choisis « Hyprland (uwsm-managed) » sur l'écran de connexion)."
info "Raccourcis : Super+/ affiche la fiche · Super+R recherche · Super+W fonds d'écran · Super+Entrée terminal (liste complète : RACCOURCIS.md)."
[ "$HYBRID" = 1 ] && info "PC hybride : lancer une appli sur la carte NVIDIA avec « nvidia-run <commande> » (Steam : nvidia-run %command%)."
[ -n "$(ls -A "$BK" 2>/dev/null)" ] && info "Retour arrière : ./install.sh --restore   (sauvegarde : $BK)"
info "Mise à jour plus tard, en une commande : nc-maj"
