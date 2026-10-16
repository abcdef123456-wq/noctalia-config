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
choisir() { # choisir "question" "choix 1" "choix 2"…  -> numéro choisi dans $CHOIX (1 par défaut)
  local q="$1" i=1 r=""
  shift
  info "$q"
  for o in "$@"; do info "  $i) $o"; i=$((i + 1)); done
  if { true </dev/tty; } 2>/dev/null; then read -r -p "   Ton choix [1] : " r </dev/tty || r=""; else info "-> réponse par défaut (1)"; fi
  [[ "$r" =~ ^[0-9]+$ ]] && [ "$r" -ge 1 ] && [ "$r" -le $# ] || r=1
  CHOIX=$r
}
# Longue étape sans sudo (compilation, téléchargement) : tourne en arrière-plan pendant qu'une ligne s'actualise
# (roue, temps écoulé ; pour une compilation, avancement en %). avec_progres "Message" journal commande… -> son code
avec_progres() {
  local msg="$1" log="$2" pid t0=$SECONDS i=0 roue='|/-\' pc=""
  shift 2
  "$@" >"$log" 2>&1 &
  pid=$!
  while kill -0 "$pid" 2>/dev/null; do
    pc="$(grep -ao '\[[0-9]*/[0-9]*\]' "$log" 2>/dev/null | tail -1 | awk -F'[][/]' '$3 > 0 { printf " · %d %%", 100 * $2 / $3 }' || true)"
    [ -t 1 ] && printf '\r   %s %s (%d min %02d s)%s   ' "${roue:$((i++ % 4)):1}" "$msg" $(((SECONDS - t0) / 60)) $(((SECONDS - t0) % 60)) "$pc"
    sleep 1
  done
  [ -t 1 ] && printf '\r\033[K'
  wait "$pid"
}

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
OSID=""; OSLIKE=""; OSCODE=""; OSNAME=""; OSLOGO=""; OSVER=0
if [ -r /etc/os-release ]; then
  OSID="$(. /etc/os-release; echo "${ID:-}")"; OSLIKE="$(. /etc/os-release; echo "${ID_LIKE:-}")"
  OSCODE="$(. /etc/os-release; echo "${VERSION_CODENAME:-}")"; OSNAME="$(. /etc/os-release; echo "${NAME:-Linux}")"
  OSLOGO="$(. /etc/os-release; echo "${LOGO:-}")"
  OSVER="$(. /etc/os-release; echo "${VERSION_ID:-0}")"
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
# apt 3 (Debian 13) : un téléchargement raté est « mis en attente » pour un nouvel essai, et apt peut alors boucler sans
# fin (« Tried to start delayed item … but failed »). Nouveaux essais immédiats à la place.
APT_OPT="-o Acquire::Retries=3 -o Acquire::Retries::Delay=false"
BPO=""
bpo_on() {
  [ "$OSID" = debian ] && [ "$OSCODE" = trixie ] || return 1
  if ! apt-cache policy 2>/dev/null | grep -qE 'o=Debian Backports.*n=trixie-backports'; then
    info "Hyprland 0.55 ou plus, TLP 1.9 ou plus : seulement dans « trixie-backports », la source officielle de Debian pour les"
    info "versions récentes (https://backports.debian.org). Seuls les paquets demandés en viennent, le reste du système ne change pas."
    ask "Activer trixie-backports ?" o || return 1
    printf 'Types: deb\nURIs: http://deb.debian.org/debian\nSuites: trixie-backports\nComponents: main\nEnabled: yes\nSigned-By: /usr/share/keyrings/debian-archive-keyring.gpg\n' |
      sudo tee /etc/apt/sources.list.d/debian-backports.sources >/dev/null
    sudo apt-get $APT_OPT update -q || return 1
  fi
}
bpo_actif() { [ "$OSID" = debian ] && [ "$OSCODE" = trixie ] && apt-cache policy 2>/dev/null | grep -qE 'o=Debian Backports.*n=trixie-backports'; }
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
    # Debian 13 avec backports (Hyprland) : leurs bibliothèques (libxkbcommon…) sont plus récentes que celles de
    # trixie ; si un paquet ne s'installe pas pour cette raison, nouvel essai en acceptant les backports
    debian) sudo apt-get $APT_OPT install -y $BPO "$@" || { [ -z "$BPO" ] && bpo_actif && sudo apt-get $APT_OPT install -y -t trixie-backports "$@"; } ;;
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
    sushi:debian) echo gnome-sushi ;;   # aperçu rapide dans Fichiers (Espace sur un fichier), comme Quick Look
    libnotify:suse) echo libnotify-tools ;;
    python:arch) echo python ;;
    python:*) echo python3 ;;
    qalc:arch) echo libqalculate ;;
    qalc:fedora) echo qalculate ;;       # /usr/bin/qalc (libqalculate n'a que la bibliothèque)
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
    quickshell:arch|quickshell:fedora) echo quickshell ;;
    quickshell:*) ;;   # pas dans les dépôts officiels : l'île du plugin Noctalia est utilisée
    breeze:fedora) echo plasma-breeze-qt6 ;;   # le style Qt 6 seul, sans les modules de réglage de KDE
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
# Outils de base du script : installés s'ils manquent (Debian neuf : jq et diffutils absents)
manque=(); for t in jq sed find cmp awk; do have "$t" || manque+=("$t"); done
if [ ${#manque[@]} -gt 0 ] && [ "$FAMILY" != other ]; then
  info "Outils nécessaires au script : ${manque[*]}"
  paquets=(); for t in "${manque[@]}"; do case "$t" in cmp) paquets+=(diffutils) ;; find) paquets+=(findutils) ;; awk) paquets+=(gawk) ;; *) paquets+=("$t") ;; esac; done
  [ "$FAMILY" = debian ] && sudo apt-get $APT_OPT update -q >/dev/null 2>&1
  pkg_install "${paquets[@]}" >/dev/null 2>&1 || true
fi
for t in jq sed find cmp awk; do have "$t" || die "commande manquante : $t (installe-la avec le gestionnaire de paquets de ta distribution)"; done
info "Distribution : ${OSNAME:-inconnue} (famille : $FAMILY)"

LAPTOP=0; ls -d /sys/class/power_supply/BAT* >/dev/null 2>&1 && LAPTOP=1
# Première installation sur ce PC : quelques choix au début (assistant, étape 4)
PREMIERE=0; [ -e "$HOME/.config/nc/depot" ] || [ -e "$HOME/.config/nc/reglages.conf" ] || PREMIERE=1
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
  local b="${1:-}" v=""
  [ -n "$b" ] || b="$(hypr_bin)"
  # Numéro qui suit « Hyprland » (ou « Tag: v… ») : la suite de --version liste aussi les bibliothèques (0.5.1…)
  [ -n "$b" ] && v="$("$b" --version 2>/dev/null | grep -oE '^Hyprland v?[0-9]+\.[0-9]+\.[0-9]+|^Tag: v[0-9]+\.[0-9]+\.[0-9]+' |
    head -1 | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' || true)"
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
  # Fedora : Noctalia v5 n'est dans les dépôts qu'à partir de Fedora 44 ; vérifié avant de toucher à quoi que ce soit
  if [ "$FAMILY" = fedora ] && ! have noctalia; then
    if [ "$OSID" != fedora ] && [ "$OSID" != nobara ]; then
      die "$OSNAME n'a pas Noctalia v5 dans ses dépôts : installe-le toi-même ($NOCT_DOCS) puis relance."
    elif [ "${OSVER%%.*}" -lt 44 ] 2>/dev/null; then
      die "Fedora $OSVER n'a pas Noctalia v5 : il faut Fedora 44 ou plus (sudo dnf system-upgrade download --releasever=44)."
    fi
  fi
  [ "$FAMILY" != other ] || have Hyprland || die "distribution non gérée par l'installateur. Installe Hyprland (0.55 ou plus) et Noctalia v5 ($NOCT_DOCS), puis relance."

  # Hyprland (Debian 13 : depuis trixie-backports, avec sa veille, son portail et uwsm)
  hv="$(hypr_version)"
  if [ -z "$(hypr_bin)" ] || { [ -n "$hv" ] && ! ver_ge "$hv" "$HYPR_MIN"; }; then
    if [ -z "$(hypr_bin)" ]; then info "Hyprland n'est pas installé."; else info "Hyprland $hv est trop ancien (0.55 ou plus)."; fi
    ask "L'installer maintenant ?" o || die "Hyprland 0.55 ou plus est nécessaire."
    if [ "$OSID" = debian ] && [ "$OSCODE" = trixie ]; then
      bpo_on || die "sans trixie-backports, Debian 13 n'a pas Hyprland 0.55 : relance et réponds oui, ou installe-le toi-même."
      bpo_install hyprland hypridle xdg-desktop-portal-hyprland uwsm || die "installation de Hyprland impossible depuis trixie-backports."
    elif [ "$FAMILY" = fedora ] && { dv="$(dnf -q repoquery --latest-limit=1 --qf '%{version}\n' hyprland 2>/dev/null | tail -1)"
                                     [ -z "$dv" ] || ! ver_ge "$dv" "$HYPR_MIN"; }; then
      # Fedora : pas de Hyprland récent dans les dépôts officiels (ni dans l'ancien COPR solopasha, abandonné) ;
      # dépôt communautaire (COPR) le plus suivi, à jour
      info "Pas de Hyprland 0.55 ou plus dans les dépôts de Fedora : dépôt communautaire COPR sdegler/hyprland"
      info "  https://copr.fedorainfracloud.org/coprs/sdegler/hyprland/"
      ask "Activer ce dépôt et installer Hyprland ?" o || die "Hyprland 0.55 ou plus est nécessaire."
      if have dnf5; then pkg_try dnf5-plugins; else pkg_try dnf-plugins-core; fi   # commande « dnf copr »
      sudo dnf -y copr disable solopasha/hyprland >/dev/null 2>&1 || true
      sudo dnf -y copr enable sdegler/hyprland || die "activation du dépôt sdegler/hyprland impossible (paquet dnf5-plugins ?)."
      sudo dnf install -y --refresh hyprland hypridle xdg-desktop-portal-hyprland uwsm ||
        die "installation de Hyprland impossible depuis sdegler/hyprland."
    else
      pkg_install hyprland || die "installation de Hyprland impossible : installe-le toi-même puis relance."
    fi
  fi
  if [ "$OSID" = debian ] && [ "$OSCODE" = trixie ]; then
    bpo_need=(); for p in hypridle xdg-desktop-portal-hyprland uwsm; do pkg_installed "$p" || bpo_need+=("$p"); done
    [ ${#bpo_need[@]} -eq 0 ] || { bpo_on && bpo_install "${bpo_need[@]}"; } || warn "Non installés depuis trixie-backports : ${bpo_need[*]}"
  fi
  # Plusieurs Hyprland installés (paquet, compilation à la main, mise à jour faite à la main…) : c'est le premier du
  # PATH qui démarre. S'il est trop ancien alors qu'un autre est assez récent, les anciens qui passent devant sont mis
  # de côté (déplacés dans /usr/local/nc-ancien-hyprland, rien n'est supprimé ; jamais un fichier d'un paquet)
  hypr_tous() {
    { type -aP Hyprland hyprland 2>/dev/null; for d in /usr/local/bin /usr/bin "$HOME/.local/bin" /opt/hyprland/bin; do
        for n in Hyprland hyprland; do [ -x "$d/$n" ] && echo "$d/$n"; done; done; } | awk '!vu[$0]++'
  }
  du_paquet() {
    case "$FAMILY" in
      debian) dpkg -S "$(readlink -f "$1")" >/dev/null 2>&1 || dpkg -S "$1" >/dev/null 2>&1 ;;
      arch) pacman -Qo "$1" >/dev/null 2>&1 ;; fedora|suse) rpm -qf "$1" >/dev/null 2>&1 ;; *) false ;;
    esac
  }
  hb="$(hypr_bin)"; hv="$(hypr_version)"
  if [ -n "$hb" ] && ! ver_ge "${hv:-0}" "$HYPR_MIN"; then
    meilleur=""; mv_=""
    while read -r b; do
      v="$(hypr_version "$b")"
      [ -n "$v" ] && ver_ge "$v" "$HYPR_MIN" && { [ -z "$mv_" ] || ! ver_ge "$mv_" "$v"; } && { meilleur="$b"; mv_="$v"; }
    done < <(hypr_tous)
    if [ -n "$meilleur" ]; then
      info "Plusieurs Hyprland sont installés : $hb ($hv) démarre, alors que $meilleur ($mv_) est assez récent."
      gener=(); while read -r b; do
        [ "$b" = "$meilleur" ] && break
        if du_paquet "$b"; then warn "$b vient d'un paquet de ta distribution : désinstalle ce paquet ou mets-le à jour."
        else gener+=("$b"); fi
      done < <(type -aP Hyprland hyprland 2>/dev/null | awk '!vu[$0]++')
      if [ ${#gener[@]} -gt 0 ] && ask "Mettre de côté les anciens (${gener[*]}) dans /usr/local/nc-ancien-hyprland (rien n'est supprimé) ?" o; then
        cote=/usr/local/nc-ancien-hyprland
        for b in "${gener[@]}"; do
          d="$(dirname "$b")"
          for f in "$d"/Hyprland "$d"/hyprland "$d"/hyprctl "$d"/hyprpm; do
            [ -e "$f" ] || continue
            sudo mkdir -p "$cote$d" && sudo mv "$f" "$cote$f" && info "  $f → $cote$f"
          done
          case "$d" in
            /usr/local/*) for f in /usr/local/share/wayland-sessions/hyprland*.desktop; do
                [ -e "$f" ] && sudo mkdir -p "$cote$(dirname "$f")" && sudo mv "$f" "$cote$f" && info "  $f → $cote$f"; done ;;
          esac
        done
        hash -r
        ok "Anciens Hyprland mis de côté : $meilleur ($mv_) sera utilisé. Pour les remettre : sudo cp -a $cote/. / "
      fi
    fi
  fi
  hv="$(hypr_version)"
  [ -n "$hv" ] || die "version de Hyprland introuvable."
  if ! ver_ge "$hv" "$HYPR_MIN"; then
    # Diagnostic : d'où vient ce Hyprland, et que faire selon la distribution
    warn "Hyprland $hv ($(hypr_bin)) est trop ancien : cette config utilise le format Lua de Hyprland 0.55 ou plus."
    case "$FAMILY:$OSID:$OSCODE" in
      debian:debian:trixie)
        info "Versions disponibles :"; apt-cache policy hyprland 2>/dev/null | sed -n '1,12p' | sed 's/^/     /'
        info "Mise à jour à la main : sudo apt install -t trixie-backports hyprland hypridle xdg-desktop-portal-hyprland uwsm" ;;
      debian:debian:*) info "Debian $OSCODE n'a pas Hyprland 0.55 : il faut Debian 13 (trixie) ou plus récent." ;;
      debian:*) info "$OSNAME n'a pas encore Hyprland 0.55 dans ses dépôts : installe-le autrement (https://wiki.hypr.land/Getting-Started/Installation/)." ;;
      fedora:*) info "Mise à jour à la main : sudo dnf copr enable sdegler/hyprland && sudo dnf upgrade --refresh hyprland" ;;
    esac
    case "$(hypr_bin)" in /usr/local/*|"$HOME"/*) info "Ce Hyprland a été installé à la main ($(hypr_bin)) et passe avant celui de ta distribution : supprime-le ou mets-le à jour." ;; esac
    die "Hyprland 0.55 ou plus est nécessaire."
  fi

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
        have wget || sudo apt-get $APT_OPT install -y wget
        kd="$(mktemp -d)"; wget -q -O "$kd/keyring.deb" https://pkg.noctalia.dev/deb/nickh-archive-keyring.deb && sudo dpkg -i "$kd/keyring.deb"; rm -rf "$kd"
        sudo wget -q -O "/etc/apt/sources.list.d/$src" "https://pkg.noctalia.dev/deb/$src"
        sudo apt-get $APT_OPT update -q || true
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
LCY5="$(awk -v h="$LH" 'BEGIN{printf "%.1f", h*0.93}')"
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
# Fedora : l'île dynamique demande Quickshell 0.3 ; Fedora 44 n'a qu'un instantané plus ancien (0.2), Fedora 43 rien.
# Dépôt communautaire (COPR) errornointernet/quickshell, tenu à jour (0.3.x)
qs_ver() { qs --version 2>/dev/null | grep -oE '[0-9]+\.[0-9]+(\.[0-9]+)?' | head -1; }
if [ "$MODE" != files ] && [ "$FAMILY" = fedora ] && ! ver_ge "$(qs_ver || true)" 0.3; then
  info "L'île dynamique utilise Quickshell 0.3, absent des dépôts de Fedora : dépôt communautaire COPR errornointernet/quickshell"
  if ask "Activer ce dépôt pour l'île dynamique ?" o; then
    if have dnf5; then pkg_try dnf5-plugins; else pkg_try dnf-plugins-core; fi
    sudo dnf -y copr enable errornointernet/quickshell >/dev/null 2>&1 &&
      { if have qs; then sudo dnf upgrade -y --refresh quickshell; else sudo dnf install -y --refresh quickshell; fi; } >/dev/null 2>&1 &&
      hash -r && ver_ge "$(qs_ver)" 0.3 && ok "Quickshell $(qs_ver) installé." ||
      warn "Quickshell non installé depuis le COPR : l'île du plugin Noctalia sera utilisée."
    hash -r
  fi
fi
GENERIC=(uwsm hypridle xdg-desktop-portal-hyprland xdg-desktop-portal-gtk kitty nautilus qt6ct papirus-icon-theme cava swaybg imagemagick
         jq grim slurp swappy wl-clipboard brightnessctl libnotify python qalc playerctl fastfetch bluez-utils gdbus
         zsh git curl unzip nerdfont adwaita-fonts noto-fonts breeze quickshell sushi wf-recorder)
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
  case " ${manual[*]} " in
    *" nerdfont "*) fc-list : family 2>/dev/null | grep -i "CaskaydiaCove Nerd Font" >/dev/null ||
                      info "La police du terminal (CaskaydiaCove Nerd Font) t'est proposée en téléchargement à l'étape 3." ;;
  esac
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
# Écran de verrouillage : Noctalia garde sa propre disposition (settings.toml), qui passe avant config.toml ; celle
# des anciennes versions (lecteur nc-media de Noctalia) est retirée pour que la capsule de musique s'applique
if [ -f "$NSET" ] && grep -qF 'lockscreen_widgets.widget.nc-media]' "$NSET"; then
  backup .local/state/noctalia/settings.toml
  python3 -I - "$NSET" <<'PYEOF'
import re, sys
p = sys.argv[1]; out, saute = [], False
for l in open(p).read().splitlines():
    if re.match(r'^\s*\[', l):
        saute = bool(re.match(r'^\s*\[lockscreen_widgets', l))
    if not saute:
        out.append(l)
open(p, "w").write("\n".join(out) + "\n")
PYEOF
  migrated=1
fi
if [ -f "$HOME/.zshrc" ] && grep -qF '.config/legion/greeting.zsh' "$HOME/.zshrc"; then
  backup .zshrc
  sed -i 's#\.config/legion/greeting\.zsh#.config/nc/greeting.zsh#g' "$HOME/.zshrc"; migrated=1
fi
[ "$migrated" = 1 ] && ok "Ancienne version (« legion ») convertie ; ses fichiers sont dans la sauvegarde."

# Icônes : thème « NC » dessiné par nc-icones aux couleurs du fond d'écran (dossiers, corbeille, Terminal,
# Fichiers), le reste vient de Papirus
ICON_THEME=NC

# Île dynamique : version Quickshell (dessinée par-dessus la barre, au plus près de l'iPhone) si Quickshell est là,
# sinon celle du plugin Noctalia. La version Quickshell utilise la police d'icônes Material Symbols Rounded (Google,
# licence Apache 2.0), téléchargée une fois dans ~/.local/share/fonts.
ILE=noctalia
# Debian / Ubuntu : Quickshell n'est pas dans les dépôts : compilé depuis ses sources officielles (version 0.3.2),
# seulement les modules utiles à l'île, installé dans /usr/local. Testé sur Debian 13 (protocoles Wayland des backports).
compiler_quickshell() {
  local wd prefixe="/usr/local"
  info "Quickshell (l'île dynamique : centre de contrôle, notifications, Spotlight) n'est pas dans les dépôts de ta distribution."
  info "Il peut être compilé depuis ses sources officielles (https://quickshell.org) : environ 5 minutes, ~400 Mo d'outils."
  ask "Le compiler et l'installer (dans $prefixe) ?" o || return 1
  pkg_try build-essential cmake ninja-build pkg-config git ca-certificates qt6-base-dev qt6-base-private-dev \
    qt6-declarative-dev qt6-declarative-private-dev qt6-wayland-dev qt6-wayland-private-dev qt6-shadertools-dev qt6-svg-dev \
    libwayland-dev libpipewire-0.3-dev libdrm-dev libgbm-dev libcli11-dev spirv-tools libvulkan-dev wayland-protocols
  # Debian 13 : protocoles Wayland trop anciens dans trixie (il faut 1.45 ou plus) : version des backports
  if [ "$OSCODE" = trixie ]; then bpo_on && bpo_install wayland-protocols >/dev/null 2>&1; fi
  wd="$(mktemp -d)"
  info "Compilation de Quickshell (5 à 15 minutes selon le processeur) :"
  if { avec_progres "Téléchargement des sources" "$wd/clone.log" git clone -q --depth 1 --branch v0.3.2 https://git.outfoxxed.me/quickshell/quickshell.git "$wd/qs" ||
       avec_progres "Téléchargement des sources" "$wd/clone.log" git clone -q --depth 1 --branch v0.3.2 https://github.com/quickshell-mirror/quickshell.git "$wd/qs"; } &&
     avec_progres "Préparation" "$wd/cmake.log" cmake -S "$wd/qs" -B "$wd/build" -GNinja -DCMAKE_BUILD_TYPE=RelWithDebInfo -DCMAKE_INSTALL_PREFIX="$prefixe" \
       -DDISTRIBUTOR="noctalia-config" -DCRASH_HANDLER=OFF -DUSE_JEMALLOC=OFF -DX11=OFF -DI3=OFF -DSCREENCOPY=OFF \
       -DSERVICE_PAM=OFF -DSERVICE_POLKIT=OFF -DSERVICE_GREETD=OFF -DSERVICE_STATUS_NOTIFIER=OFF \
       -DNETWORK=OFF -DBLUETOOTH=OFF -DWAYLAND_SESSION_LOCK=OFF -DHYPRLAND_GLOBAL_SHORTCUTS=OFF \
       -DHYPRLAND_SURFACE_EXTENSIONS=OFF &&
     avec_progres "Compilation" "$wd/build.log" cmake --build "$wd/build" &&
     sudo cmake --install "$wd/build" >/dev/null 2>&1; then
    ok "Quickshell installé ($(qs --version 2>/dev/null | head -1))."
    rm -rf "$wd"
    return 0
  fi
  warn "Compilation de Quickshell impossible (journal : $wd) : l'île du plugin Noctalia est utilisée."
  return 1
}
# L'île Quickshell pour tout le monde : paquet sur Arch et Fedora, compilée sur Debian / Ubuntu
if ! have qs && [ "$FAMILY" = debian ] && [ "$MODE" != files ]; then compiler_quickshell || true; hash -r; fi
if have qs && ver_ge "$(qs_ver || true)" 0.3; then      # l'île demande Quickshell 0.3
  ILE=quickshell
  POLICE_ICONES="$HOME/.local/share/fonts/MaterialSymbolsRounded.ttf"
  if [ ! -s "$POLICE_ICONES" ] && [ "$MODE" != files ] && have curl; then
    info "Icônes de l'île : police Material Symbols Rounded (Google), https://github.com/google/material-design-icons"
    if ask "La télécharger (15 Mo) ?" o; then
      mkdir -p "$(dirname "$POLICE_ICONES")"
      if curl -fsSL -o "$POLICE_ICONES.tmp" 'https://github.com/google/material-design-icons/raw/master/variablefont/MaterialSymbolsRounded%5BFILL,GRAD,opsz,wght%5D.ttf'; then
        mv "$POLICE_ICONES.tmp" "$POLICE_ICONES"; fc-cache -f "$(dirname "$POLICE_ICONES")" >/dev/null 2>&1 || true; ok "Police d'icônes installée."
      else
        rm -f "$POLICE_ICONES.tmp"; warn "Téléchargement impossible : l'île du plugin Noctalia est utilisée."; ILE=noctalia
      fi
    else
      ILE=noctalia
    fi
  fi
  [ -s "$POLICE_ICONES" ] || ILE=noctalia
fi
if [ "$ILE" = quickshell ]; then ILE_CENTRE=""; else ILE_CENTRE='"nc/ile:pilule"'; fi
# Notifications : affichées par l'île Quickshell (bannière qui sort de la pilule, historique dans l'île) ; sinon par
# Noctalia, avec son icône dans la barre
if [ "$ILE" = quickshell ]; then NOTIF_NOCTALIA=false; NOTIF_WIDGET=""; else NOTIF_NOCTALIA=true; NOTIF_WIDGET=', "notifications"'; fi
# Ancienne île (plugin Noctalia nc/ile) : seulement sans l'île Quickshell
if [ "$ILE" = quickshell ]; then PLUGIN_ILE=""; else PLUGIN_ILE=', "nc/ile"'; fi

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
        -e "s|@LCY3@|$LCY3|g" -e "s|@LCY4@|$LCY4|g" -e "s|@LCY5@|$LCY5|g" -e "s|@DISTRO_LOGO@|$DISTRO_LOGO|g" -e "s|@POLKIT@|$POLKIT|g" -e "s|@QT_STYLE@|$QT_STYLE|g" -e "s|@ICON_THEME@|$ICON_THEME|g" -e "s|@ILE_CENTRE@|$ILE_CENTRE|g" -e "s|@NOTIF_NOCTALIA@|$NOTIF_NOCTALIA|g" -e "s|@NOTIF_WIDGET@|$NOTIF_WIDGET|g" -e "s|@PLUGIN_ILE@|$PLUGIN_ILE|g" "$src" > "$tmp"
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
# Dossiers utilisateur : si xdg-user-dirs a créé des dossiers vides en français alors que les tiens existent en
# anglais (Downloads, Pictures…), on garde les tiens ; Bureau, Modèles et Public vides (inutiles sous Hyprland) sont
# désactivés. Seuls des dossiers vides sont supprimés.
python3 -I - <<'PYEOF' 2>/dev/null || true
import os, re
maison = os.path.expanduser("~")
fichier = os.path.join(maison, ".config/user-dirs.dirs")
if os.path.exists(fichier):
    anglais = {"DOWNLOAD": "Downloads", "DOCUMENTS": "Documents", "PICTURES": "Pictures", "MUSIC": "Music",
               "VIDEOS": "Videos", "PROJECTS": "Projects"}
    inutiles = {"DESKTOP", "TEMPLATES", "PUBLICSHARE"}
    vide = lambda d: os.path.isdir(d) and not os.listdir(d)
    lignes, change = [], False
    for ligne in open(fichier).read().splitlines():
        m = re.match(r'XDG_(\w+)_DIR="\$HOME/(.*)"$', ligne)
        if m and m.group(2):
            cle, d = m.group(1), os.path.join(maison, m.group(2))
            remplace = None
            if cle in inutiles and (vide(d) or not os.path.exists(d)):
                remplace = ""
            elif cle in anglais and anglais[cle] != m.group(2) and vide(d) and os.path.isdir(os.path.join(maison, anglais[cle])):
                remplace = anglais[cle]
            if remplace is not None:
                ligne = 'XDG_%s_DIR="$HOME/%s"' % (cle, remplace)
                change = True
                try:
                    os.rmdir(d)
                except OSError:
                    pass
        lignes.append(ligne)
    if change:
        open(fichier, "w").write("\n".join(lignes) + "\n")
PYEOF
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
-- Raccourcis sans éditer de fichier : nc-raccourci (ajouter, changer ou désactiver ceux de la config).
-- Réglages courants (espaces, bordures, pavé tactile, écran…) : nc-reglages.
--
-- hl.bind("SUPER + B", hl.dsp.exec_cmd("firefox"), { description = "Mes raccourcis|Navigateur" })
-- hl.monitor({ output = "HDMI-A-1", mode = "preferred", position = "auto", scale = 1 })
-- hl.config({ general = { gaps_out = 6 }, decoration = { rounding = 10 } })
-- hl.on("hyprland.start", function() hl.exec_cmd("discord --start-minimized") end)
PERSO_EOF
  echo ".config/hypr/perso.lua" >> "$BK/.created"
fi
# Commandes nc-* (nc-maj…) trouvées aussi dans bash, sans attendre une reconnexion ni passer à zsh
if [ -f "$HOME/.bashrc" ] || [ "$(basename "${SHELL:-}")" = bash ]; then
  if ! grep -qF 'noctalia-config : commandes nc-' "$HOME/.bashrc" 2>/dev/null; then
    [ -f "$HOME/.bashrc" ] && backup .bashrc
    printf '\n# noctalia-config : commandes nc-* (nc-maj…) dans ~/.local/bin\ncase ":$PATH:" in *":$HOME/.local/bin:"*) ;; *) export PATH="$HOME/.local/bin:$PATH" ;; esac\n' >> "$HOME/.bashrc"
  fi
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
          avec_progres "Téléchargement de $(basename "$d")" /dev/null git clone -q --depth 1 "${REPOS[$d]}" "$d" && echo "${d#"$HOME/"}" >> "$BK/.created" || warn "téléchargement impossible : ${REPOS[$d]}"
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
    fedora) pkg_try neovim git ripgrep fd-find gcc make tree-sitter-cli gitui
            # Fedora 44 : nodejs24 / nodejs24-npm (plus de paquet « nodejs ») ; demandés par la commande fournie
            have node || sudo dnf install -y /usr/bin/node /usr/bin/npm >/dev/null 2>&1 || true ;;
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
UNITS=(noctalia.service nc-carousel-thumbs.service nc-profile-sync.service nc-pouls.service nc-ecran-externe.service nc-couvercle.service)
[ "$ILE" = quickshell ] && UNITS+=(nc-ile.service)
[ "$KDE_POLKIT" = 1 ] && UNITS+=(plasma-polkit-agent.service)
if systemctl --user daemon-reload >/dev/null 2>&1; then
  systemctl --user enable "${UNITS[@]}" >/dev/null 2>&1 || true
  [ "$ILE" = quickshell ] || systemctl --user disable --now nc-ile.service >/dev/null 2>&1 || true
  # Anciennes barres / shells (config d'avant : Waybar, HyprPanel, AGS, eww…) qui démarreraient avec la session par
  # un service ou un lancement automatique : désactivés après une question (rien n'est désinstallé)
  barres=(); demarrages=()
  for b in waybar hyprpanel ags eww polybar; do
    systemctl --user is-enabled "$b.service" >/dev/null 2>&1 && barres+=("$b")
  done
  for f in "$HOME"/.config/autostart/*.desktop /etc/xdg/autostart/*.desktop; do
    [ -f "$f" ] || continue
    grep -qiE '^Hidden=true' "$f" && continue
    grep -qE '^Exec=.*\b(waybar|hyprpanel|ags|eww|polybar|swaync|dunst|mako)\b' "$f" && demarrages+=("$f")
  done
  if [ ${#barres[@]} -gt 0 ] || [ ${#demarrages[@]} -gt 0 ]; then
    info "Ton ancienne config démarre encore : ${barres[*]} ${demarrages[*]##*/}"
    if ask "Les désactiver (la barre de Noctalia et l'île les remplacent ; rien n'est désinstallé) ?" o; then
      # mask, pas disable : sur Debian, waybar.service est activé pour tous les utilisateurs et reviendrait
      for b in "${barres[@]}"; do systemctl --user stop "$b.service" >/dev/null 2>&1; systemctl --user mask "$b.service" >/dev/null 2>&1 || true; done
      mkdir -p "$HOME/.config/autostart"
      for f in "${demarrages[@]}"; do
        n="$HOME/.config/autostart/$(basename "$f")"
        if [ "$f" = "$n" ]; then backup ".config/autostart/$(basename "$f")"; else cp "$f" "$n"; echo ".config/autostart/$(basename "$f")" >> "$BK/.created"; fi
        printf '\nHidden=true\n' >> "$n"
      done
      for b in waybar hyprpanel eww polybar; do pkill -x "$b" 2>/dev/null || true; done
      ok "Ancienne barre désactivée."
    fi
  fi
  # Démons de notifications lancés à la demande (dunst, mako, swaync) : ils prendraient la place de l'île ou de Noctalia
  for d in dunst mako swaync; do
    if [ -n "$(systemctl --user list-unit-files "$d.service" --no-legend 2>/dev/null)" ] && ! systemctl --user is-enabled "$d.service" 2>/dev/null | grep -x masked >/dev/null; then
      systemctl --user mask --now "$d.service" >/dev/null 2>&1 && info "$d (notifications) désactivé : les notifications passent par $([ "$ILE" = quickshell ] && echo "l'île" || echo "Noctalia")."
    fi
  done
  systemctl --user enable --now nc-theme-sync.path nc-carousel-thumbs.path nc-maj-verif.timer hypridle.service >/dev/null 2>&1 ||
    warn "Certains services n'ont pas pu démarrer maintenant : ils démarreront à la prochaine session."
  "$HOME/.local/bin/nc-theme-sync" >/dev/null 2>&1 || true
  # Première installation : quelques choix, tout de suite (tout se change ensuite avec nc-reglages)
  if [ "$PREMIERE" = 1 ]; then
    R="$HOME/.local/bin/nc-reglages"
    say "Quelques choix pour commencer (modifiables ensuite : nc-reglages)"
    choisir "Style du bureau :" "noctalia-config : les couleurs de ton fond d'écran" "Apple : façon macOS et iPhone" \
      "Noir pur (écran OLED)" "Nord" "Catppuccin"
    case "$CHOIX" in 2) "$R" set STYLE apple ;; 3) "$R" set STYLE oled ;; 4) "$R" set STYLE nord ;; 5) "$R" set STYLE catppuccin ;; esac >/dev/null 2>&1
    ask "Thème sombre ?" o || "$R" set THEME_MODE light >/dev/null 2>&1
    ask "Changer de fond d'écran tout seul toutes les 10 minutes ?" o || "$R" set FONDS_ROTATION non >/dev/null 2>&1
    ask "Couper les notifications la nuit (22 h à 7 h) ?" n && "$R" set NPD_NUIT oui >/dev/null 2>&1
    if [ "$LAPTOP" = 1 ]; then
      choisir "Couvercle fermé :" "Mise en veille" "L'écran s'éteint, le PC continue (téléchargements, musique…)"
      [ "$CHOIX" = 2 ] && "$R" set COUVERCLE ecran >/dev/null 2>&1
    fi
    choisir "Un appui sur le bouton d'arrêt :" "Une petite surprise (des doigts partout)" "Des confettis" \
      "Le menu Éteindre / Redémarrer / Veille" "Éteindre, comme d'habitude"
    case "$CHOIX" in 2) "$R" set BOUTON_ARRET confettis ;; 3) "$R" set BOUTON_ARRET menu ;; 4) "$R" set BOUTON_ARRET eteindre ;; esac >/dev/null 2>&1
    ok "C'est noté."
  fi
  # Tes réglages (nc-reglages) : ~/.config/nc/reglages.conf n'est jamais touché ; ce qui en est tiré (veille, terminal)
  # est refait d'après la nouvelle version de la config
  "$HOME/.local/bin/nc-reglages" appliquer >/dev/null 2>&1 || true
  "$HOME/.local/bin/nc-verrou-place" >/dev/null 2>&1 || true     # écran de verrouillage centré sur l'écran réel
  # Claude Code dans l'île (comme l'appli coucou) : ses étapes, sa fin, ses demandes ; hooks dans ~/.claude/settings.json
  if [ "$ILE" = quickshell ] && { have claude || [ -d "$HOME/.claude" ]; } &&
     ! grep -q "nc-claude hook" "$HOME/.claude/settings.json" 2>/dev/null &&
     ! grep -qx 'CLAUDE_ILE=non' "$HOME/.config/nc/reglages.conf" 2>/dev/null; then
    info "Claude Code est installé : l'île peut montrer ce qu'il fait et répondre à ses demandes (comme l'appli coucou)."
    if ask "L'afficher dans l'île ?" o; then "$HOME/.local/bin/nc-claude" installer | head -1
    else printf 'CLAUDE_ILE=non\n' >> "$HOME/.config/nc/reglages.conf"; fi
  fi
  # Antigravity (Google) aussi : ce que fait son agent et quand il a fini ; hooks dans ~/.gemini/config/hooks.json
  if [ "$ILE" = quickshell ] && { have antigravity || have agy || [ -d "$HOME/.gemini" ]; } &&
     ! grep -q "nc-claude.* agy " "$HOME/.gemini/config/hooks.json" 2>/dev/null &&
     ! grep -qx 'ANTIGRAVITY_ILE=non' "$HOME/.config/nc/reglages.conf" 2>/dev/null; then
    info "Antigravity est installé : l'île peut montrer ce que fait son agent et quand il a fini."
    if ask "L'afficher dans l'île ?" o; then "$HOME/.local/bin/nc-claude" installer antigravity | head -1
    else printf 'ANTIGRAVITY_ILE=non\n' >> "$HOME/.config/nc/reglages.conf"; fi
  fi
  systemctl --user start nc-carousel-thumbs.service >/dev/null 2>&1 || true
  if [ "$NOCT_WAS_ACTIVE" = 1 ] || systemctl --user is-active --quiet graphical-session.target 2>/dev/null; then
    if [ "$copied" -gt 0 ] || [ "$migrated" = 1 ]; then
      # Session ouverte et fichiers changés : services relancés avec leur nouvelle config
      systemctl --user restart noctalia.service nc-profile-sync.service nc-pouls.service nc-ecran-externe.service nc-couvercle.service hypridle.service 2>/dev/null || true
      [ "$ILE" = quickshell ] && { systemctl --user restart nc-ile.service 2>/dev/null || true; }
    else
      systemctl --user start noctalia.service nc-pouls.service 2>/dev/null || true   # rien n'a changé : simplement relancés
      [ "$ILE" = quickshell ] && { systemctl --user start nc-ile.service 2>/dev/null || true; }
    fi
    [ "$KDE_POLKIT" = 1 ] && { systemctl --user start plasma-polkit-agent.service 2>/dev/null || true; }
  fi
  ok "Services activés."
  if ! systemctl --user is-active --quiet graphical-session.target 2>/dev/null; then
    info "Pour que la barre démarre à l'ouverture de session, choisis la session « Hyprland (uwsm-managed) » sur l'écran de connexion."
  fi
else
  warn "Pas de session utilisateur active (installation depuis un terminal de connexion ou SSH ?) : services non activés."
  info "Dans ta session Hyprland, lance : systemctl --user enable --now noctalia.service nc-theme-sync.path nc-carousel-thumbs.path nc-profile-sync.service nc-pouls.service nc-ecran-externe.service nc-couvercle.service hypridle.service$([ "$ILE" = quickshell ] && echo " nc-ile.service")"
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
  TLP_PERSO="$(ls /etc/tlp.d/*.conf 2>/dev/null | grep -vE '/(00-template|10-nc|10-legion|11-nc-frequence|20-battery-limit)\.conf$' || true)"
  tlp_regle() {   # réglages du dépôt dans /etc/tlp.d (et la limite de charge si choisie) ; vrai si quelque chose a changé
    local ch=1
    if [ -n "$TLP_PERSO" ] && [ ! -f /etc/tlp.d/10-nc.conf ] && [ ! -f /etc/tlp.d/10-legion.conf ]; then
      return 1
    fi
    [ -f /etc/tlp.d/10-legion.conf ] && { sbackup /etc/tlp.d/10-legion.conf; sudo rm -f /etc/tlp.d/10-legion.conf; ch=0; }
    cmp -s "$REPO/system/tlp.d/10-nc.conf" /etc/tlp.d/10-nc.conf || { sudo install -Dm0644 "$REPO/system/tlp.d/10-nc.conf" /etc/tlp.d/10-nc.conf; ch=0; }
    # Fréquence maximale rendue en Équilibré et Performance : sans ça, le plafond de 2 GHz du profil Économie restait
    # jusqu'au redémarrage (TLP ne touche pas à un réglage absent). Valeur de ce processeur, d'où un fichier à part.
    fmax="$(cat /sys/devices/system/cpu/cpu0/cpufreq/cpuinfo_max_freq 2>/dev/null)"
    if [ -n "$fmax" ]; then
      freq="$(printf '# /etc/tlp.d/11-nc-frequence.conf : fréquence maximale du processeur en Performance et Équilibré\n# (noctalia-config ; le profil Économie la plafonne à 2 GHz, voir 10-nc.conf).\nCPU_SCALING_MAX_FREQ_ON_AC=%s\nCPU_SCALING_MAX_FREQ_ON_BAT=%s\n' "$fmax" "$fmax")"
      [ "$(cat /etc/tlp.d/11-nc-frequence.conf 2>/dev/null)" = "$freq" ] || { printf '%s\n' "$freq" | sudo install -Dm0644 /dev/stdin /etc/tlp.d/11-nc-frequence.conf; ch=0; }
    fi
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
      for u in auto-cpufreq tuned tuned-ppd power-profiles-daemon; do
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
        if [ "$ppd" = tuned-ppd ]; then sudo systemctl enable --now tuned.service >/dev/null 2>&1 || true; fi   # tuned-ppd s'appuie sur tuned
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

  # Interrupteur « Protéger la batterie » de l'île : petit utilitaire root qui ne fait que limiter la charge, lancé
  # sans mot de passe grâce à une règle sudo limitée à lui seul (vérifiée par visudo avant d'être mise en place)
  if [ "$LAPTOP" = 1 ] && [ "$("$REPO/system/nc-limite-charge" etat 2>/dev/null)" != absent ]; then
    regle=/etc/sudoers.d/nc-limite-charge
    ligne="$(id -un) ALL=(root) NOPASSWD: /usr/local/bin/nc-limite-charge"
    if cmp -s "$REPO/system/nc-limite-charge" /usr/local/bin/nc-limite-charge && sudo grep -qxF "$ligne" "$regle" 2>/dev/null; then
      ok "Interrupteur de protection de la batterie (île) : déjà en place."
    else
      info "Interrupteur « Protéger la batterie » dans la page Système de l'île (charge arrêtée vers 80 %) : un petit"
      info "utilitaire qui ne fait que ça (/usr/local/bin/nc-limite-charge), lancé depuis l'île sans mot de passe."
      if ask "L'installer ?" o; then
        t="$(mktemp)"; printf '# noctalia-config : interrupteur « Protéger la batterie » de l'"'"'île\n%s\n' "$ligne" > "$t"
        if sudo install -Dm0755 -o root -g root "$REPO/system/nc-limite-charge" /usr/local/bin/nc-limite-charge &&
           sudo visudo -cf "$t" >/dev/null && sudo install -m0440 -o root -g root "$t" "$regle"; then
          ok "Interrupteur de protection de la batterie installé."
        else
          warn "Installation de l'interrupteur de batterie impossible (règle sudo refusée par visudo)."
        fi
        rm -f "$t"
      fi
    fi
  fi

  # Bouton d'arrêt : un appui fait une petite animation (nc-anim bouton, raccourci XF86PowerOff ; laquelle : nc-reglages) au lieu
  # d'éteindre ; logind doit donc laisser la touche à Hyprland. Le garder appuyé éteint toujours proprement, et
  # Super + F4 éteint aussi. 50-legion-powerkey.conf : ancien nom de ce réglage, remplacé.
  bouton=/etc/systemd/logind.conf.d/50-nc-bouton.conf
  contenu=$'# noctalia-config : un appui sur le bouton d\'arrêt fait apparaître les doigts (nc-finger) au lieu d\'éteindre.\n# Le garder appuyé éteint ; Super + F4 aussi. Pour revenir à l\'arrêt normal : sudo rm '"$bouton"$'\n[Login]\nHandlePowerKey=ignore\nHandlePowerKeyLongPress=poweroff'
  if [ "$(cat "$bouton" 2>/dev/null)" = "$contenu" ] && [ ! -f /etc/systemd/logind.conf.d/50-legion-powerkey.conf ]; then
    ok "Bouton d'arrêt (les doigts) : déjà en place."
  elif ask "Bouton d'arrêt : un appui fait apparaître des doigts au lieu d'éteindre (le garder appuyé éteint) ?" o; then
    if printf '%s\n' "$contenu" | sudo install -Dm0644 /dev/stdin "$bouton"; then
      sudo rm -f /etc/systemd/logind.conf.d/50-legion-powerkey.conf
      # Relecture de la config par logind sans le redémarrer (un redémarrage fermerait la session)
      sudo systemctl kill -s HUP systemd-logind >/dev/null 2>&1 || true
      ok "Bouton d'arrêt : les doigts à chaque appui."
    else
      warn "Réglage du bouton d'arrêt impossible."
    fi
  fi

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
    # Fedora : sortie texte par défaut (GRUB_TERMINAL_OUTPUT="console"), qui ignore le thème : sortie graphique
    if grep -qE '^GRUB_TERMINAL_OUTPUT="?console"?\s*$' /etc/default/grub; then
      sudo sed -i -E 's/^GRUB_TERMINAL_OUTPUT=.*/GRUB_TERMINAL_OUTPUT="gfxterm"/' /etc/default/grub
    fi
    sudo "$GRUBMK" -o "$GRUBDIR/grub.cfg" && ok "Thème GRUB installé (visible au prochain redémarrage)."
    if have restorecon; then sudo restorecon -RF "$GRUBDIR/themes/nc" >/dev/null 2>&1 || true; fi   # SELinux (Fedora)
    if grep -qE '^GRUB_TIMEOUT_STYLE=hidden' /etc/default/grub ||
       { have grub2-editenv && sudo grub2-editenv - list 2>/dev/null | grep -q '^menu_auto_hide=1'; }; then
      info "Le menu GRUB est masqué sur ta distribution : maintiens Maj (ou Échap, F8) au démarrage pour le voir."
    fi
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
      diff -rq --exclude=theme.txt "$REPO/system/grub-theme/nc" "$GRUBDIR/themes/nc" >/dev/null 2>&1 &&
      ! grep -qE '^GRUB_TERMINAL_OUTPUT="?console"?\s*$' /etc/default/grub || grub_done=0
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
        grep -q '^ConfigFile=Themes/nc.conf' "$T/metadata.desktop" 2>/dev/null && ! grep -q 'Screen\.ScreenWidth' "$T/Main.qml" &&
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
      # Erreur du thème : sans taille dans la config, la largeur de l'écran n'était pas lue (Screen.ScreenWidth)
      sudo sed -i 's/Screen\.ScreenWidth/Screen.width/' "$T/Main.qml"
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
info "Tes réglages (écran, fenêtres, île, veille, clavier, terminal…) : nc-reglages (gardés à chaque mise à jour)"
info "Un souci ? nc-diag vérifie tout et dit quoi faire (nc-diag rapport : le bilan, prêt à envoyer). Les commandes : nc-aide"
