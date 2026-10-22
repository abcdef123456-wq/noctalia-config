#!/usr/bin/env bash
# install.sh : installe le bureau noctalia-config (Hyprland + Noctalia v5) sur ton PC.
#
#   ./install.sh               installation complète, avec une question avant chaque étape système
#   ./install.sh --no-system   seulement ta session (paquets, fichiers, terminal, services utilisateur), rien d'autre en root
#   ./install.sh --files-only  seulement la copie des fichiers (aucun paquet, service ni sudo)
#   ./install.sh --restore     remet les fichiers tels qu'avant la dernière installation
#   ./install.sh --en | --fr   force la langue : anglais ou français (sinon le réglage LANGUE, puis celle du système)
#
# Distributions : Arch (et dérivées), Fedora, Debian/Ubuntu, openSUSE : Hyprland et Noctalia v5 sont installés
# s'ils manquent. Autres distributions : installe Hyprland (0.55 ou plus) et Noctalia v5 toi-même
# (docs.noctalia.dev), puis relance.
# Tout fichier remplacé est d'abord sauvegardé dans ~/.local/state/noctalia-config/backup-<date>/.
# Le script ne lance jamais de mise à jour système et ne touche au démarrage (Plymouth, GRUB, initramfs)
# que si tu réponds oui à la question correspondante.
set -euo pipefail

REPO="$(cd "$(dirname "$0")" && pwd)"
# Langue des messages : --en / --fr, sinon NC_LANGUE=en|fr, le réglage LANGUE, puis la langue du système (nc-langue)
for a in "$@"; do case "$a" in --en) NC_LANGUE=en ;; --fr) NC_LANGUE=fr ;; esac; done
if ! . "$REPO/home/.local/bin/nc-langue" 2>/dev/null; then
  NC_LANGUE=fr; NOMS_ANGLAIS=""; t() { printf '%s' "$1"; }
fi
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
die()  { printf '\033[31m%s%s\033[0m\n' "$(t 'Erreur : ' 'Error: ')" "$*" >&2; exit 1; }
ask() { # ask "question" [o|n]  -> vrai si oui (o, oui, y, yes ; en anglais, [Y/n] au lieu de [O/n])
  local d="${2:-n}" r hint
  hint="$(t "[o/N]" "[y/N]")"
  [ "$d" = o ] && hint="$(t "[O/n]" "[Y/n]")"
  r=""
  if { true </dev/tty; } 2>/dev/null; then read -r -p "   $1 $hint " r </dev/tty || r=""; else info "$1 -> $(t "réponse par défaut ($d)" "default answer ($([ "$d" = o ] && echo y || echo n))")"; fi
  r="${r:-$d}"
  [[ "$r" =~ ^[oOyY] ]]
}
have() { command -v "$1" >/dev/null 2>&1; }
# Une sonde en lecture seule ne doit pas bloquer toute l'installation. Les installations
# de paquets gardent leurs propres délais et une sortie visible.
sonder() { # sonder DURÉE LIBELLÉ COMMANDE…
  local delai="$1" libelle="$2" code
  shift 2
  if timeout --kill-after=2s "$delai" "$@" 2>/dev/null; then return 0; else code=$?; fi
  if [ "$code" = 124 ] || [ "$code" = 137 ]; then
    warn "$(t "$libelle : délai de $delai dépassé." "$libelle: timed out after $delai.")" >&2
  fi
  return "$code"
}
choisir() { # choisir "question" "choix 1" "choix 2"…  -> numéro choisi dans $CHOIX (1 par défaut)
  local q="$1" i=1 r=""
  shift
  info "$q"
  for o in "$@"; do info "  $i) $o"; i=$((i + 1)); done
  if { true </dev/tty; } 2>/dev/null; then read -r -p "   $(t "Ton choix [1] : " "Your choice [1]: ")" r </dev/tty || r=""; else info "$(t "-> réponse par défaut (1)" "-> default answer (1)")"; fi
  [[ "$r" =~ ^[0-9]+$ ]] && [ "$r" -ge 1 ] && [ "$r" -le $# ] || r=1
  CHOIX=$r
}
# Longue étape sans sudo (compilation, téléchargement) : tourne en arrière-plan pendant qu'une ligne s'actualise
# (roue, temps écoulé ; pour une compilation, avancement en %). avec_progres "Message" journal commande… -> son code
avec_progres() {
  local msg="$1" log="$2" pid t0=$SECONDS i=0 roue='|/-\' pc="" fpc
  fpc="$(t ' · %d %%' ' · %d%%')"
  shift 2
  "$@" >"$log" 2>&1 &
  pid=$!
  while kill -0 "$pid" 2>/dev/null; do
    pc="$(grep -ao '\[[0-9]*/[0-9]*\]' "$log" 2>/dev/null | tail -1 | awk -F'[][/]' -v f="$fpc" '$3 > 0 { printf f, 100 * $2 / $3 }' || true)"
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
    --en|--fr) ;;   # langue : prise en compte plus haut
    --legion|--no-legion) info "$(t "Option $a ignorée : les profils d'énergie sont maintenant proposés sur tous les PC." "Option $a ignored: power profiles are now offered on every PC.")" ;;
    -h|--help)
      if [ "$NC_LANGUE" = en ]; then
        cat <<'AIDE_EN'
install.sh: installs the noctalia-config desktop (Hyprland + Noctalia v5) on your PC.

  ./install.sh               full install, with a question before each system step
  ./install.sh --no-system   only your session (packages, files, terminal, user services), nothing else as root
  ./install.sh --files-only  only copy the files (no packages, services or sudo)
  ./install.sh --restore     put the files back as they were before the last install
  ./install.sh --en | --fr   force the language: English or French (otherwise the LANGUE setting, then the system's)

Distributions: Arch (and derivatives), Fedora, Debian/Ubuntu, openSUSE: Hyprland and Noctalia v5 are installed
if missing. Other distributions: install Hyprland (0.55 or later) and Noctalia v5 yourself
(docs.noctalia.dev), then run it again.
Every replaced file is first backed up to ~/.local/state/noctalia-config/backup-<date>/.
The script never runs a system update, and only touches the boot (Plymouth, GRUB, initramfs)
if you answer yes to the matching question.
AIDE_EN
      else
        sed -n '2,15p' "$0"
      fi
      exit 0 ;;
    *) die "$(t "option inconnue : $a (voir ./install.sh --help)" "unknown option: $a (see ./install.sh --help)")" ;;
  esac
done
[ "$(id -u)" != 0 ] || die "$(t "lance ce script sans sudo : il demandera ton mot de passe quand il en aura besoin." "run this script without sudo: it will ask for your password when it needs it.")"

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
    info "$(t "Hyprland 0.55 ou plus, TLP 1.9 ou plus : seulement dans « trixie-backports », la source officielle de Debian pour les" "Hyprland 0.55 or later, TLP 1.9 or later: only in “trixie-backports”, Debian's official source for")"
    info "$(t "versions récentes (https://backports.debian.org). Seuls les paquets demandés en viennent, le reste du système ne change pas." "recent versions (https://backports.debian.org). Only the requested packages come from it; the rest of the system doesn't change.")"
    ask "$(t "Activer trixie-backports ?" "Enable trixie-backports?")" o || return 1
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
    info "$(t "installation : $p" "installing: $p")"
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
    checkupdates:arch) echo pacman-contrib ;;                      # compter les mises à jour (nc-paquets)
    checkupdates:*) ;;
    tesseract:debian|tesseract:suse) echo tesseract-ocr ;;        # lire le texte d'une capture (nc-capture texte)
    tesseract-fra:arch) echo tesseract-data-fra ;;
    tesseract-fra:fedora) echo tesseract-langpack-fra ;;
    tesseract-fra:debian) echo tesseract-ocr-fra ;;
    tesseract-fra:suse) echo tesseract-ocr-traineddata-french ;;
    tesseract-eng:arch) echo tesseract-data-eng ;;
    tesseract-eng:debian|tesseract-eng:suse) echo tesseract-ocr ;;   # l'anglais vient avec
    tesseract-eng:*) echo tesseract ;;
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
    # Dictée (nc-dictee) : pw-record, seulement s'il n'y a ni pw-record, ni parec, ni arecord (noms vérifiés dans chaque dépôt)
    enregistreur:arch) echo pipewire-audio ;;
    enregistreur:fedora) echo pipewire-utils ;;
    enregistreur:debian) echo pipewire-bin ;;
    enregistreur:suse) echo pipewire-tools ;;
    enregistreur:*) ;;
    *) echo "$1" ;;
  esac
}

# ── Retour arrière ───────────────────────────────────────────────────────────
if [ "$MODE" = restore ]; then
  last="$(ls -1d "$STATE"/backup-* "$OLD_STATE"/backup-* 2>/dev/null | awk -F/ '{ print $NF "\t" $0 }' | sort | tail -1 | cut -f2- || true)"
  [ -n "$last" ] || die "$(t "aucune sauvegarde trouvée dans $STATE" "no backup found in $STATE")"
  say "$(t "Restauration de $last" "Restoring $last")"
  ask "$(t "Remettre tes anciens fichiers et supprimer ceux ajoutés par l'installation ?" "Put your old files back and delete the ones added by the install?")" n || exit 0
  have systemctl && systemctl --user stop noctalia.service 2>/dev/null || true
  if [ -f "$last/.created" ]; then
    while IFS= read -r rel; do [ -n "$rel" ] && rm -rf "${HOME:?}/$rel"; done < "$last/.created"
  fi
  (cd "$last" && find . -path ./system -prune -o \( -type f -o -type l \) ! -name .created -print0 |
    while IFS= read -r -d '' f; do mkdir -p "$HOME/$(dirname "$f")"; cp -a "$last/$f" "$HOME/$f"; done)
  [ -d "$last/system" ] && warn "$(t "Fichiers système sauvegardés dans $last/system : à remettre à la main avec sudo si besoin." "System files backed up in $last/system: put them back by hand with sudo if needed.")"
  if have systemctl; then
    systemctl --user daemon-reload 2>/dev/null || true
    systemctl --user start noctalia.service 2>/dev/null || true
  fi
  ok "$(t "Fichiers restaurés. Ferme puis rouvre ta session." "Files restored. Log out and back in.")"
  exit 0
fi

# ── Vérifications ────────────────────────────────────────────────────────────
say "$(t "Vérifications" "Checks")"
# Outils de base du script : installés s'ils manquent (Debian neuf : jq et diffutils absents)
manque=(); for t in jq sed find cmp awk timeout; do have "$t" || manque+=("$t"); done
if [ ${#manque[@]} -gt 0 ] && [ "$FAMILY" != other ] && [ "$MODE" != files ]; then
  info "$(t "Outils nécessaires au script : ${manque[*]}" "Tools the script needs: ${manque[*]}")"
  paquets=(); for t in "${manque[@]}"; do case "$t" in cmp) paquets+=(diffutils) ;; find) paquets+=(findutils) ;; awk) paquets+=(gawk) ;; timeout) paquets+=(coreutils) ;; *) paquets+=("$t") ;; esac; done
  sudo -v || die "$(t "authentification sudo impossible." "sudo authentication failed.")"
  if [ "$FAMILY" = debian ]; then sudo apt-get $APT_OPT update -q; fi
  pkg_install "${paquets[@]}" || die "$(t "installation des outils de vérification impossible." "could not install the checking tools.")"
fi
for t in jq sed find cmp awk timeout; do have "$t" || die "$(t "commande manquante : $t (installe-la avec le gestionnaire de paquets de ta distribution)" "missing command: $t (install it with your distribution's package manager)")"; done
info "$(t "Distribution : ${OSNAME:-inconnue} (famille : $FAMILY)" "Distribution: ${OSNAME:-unknown} (family: $FAMILY)")"

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
info "$(t "Portable : $([ $LAPTOP = 1 ] && echo oui || echo non) · Carte NVIDIA : $([ $NVIDIA = 1 ] && { [ $HYBRID = 1 ] && echo "oui (hybride)" || echo oui; } || echo non)" "Laptop: $([ $LAPTOP = 1 ] && echo yes || echo no) · NVIDIA card: $([ $NVIDIA = 1 ] && { [ $HYBRID = 1 ] && echo "yes (hybrid)" || echo yes; } || echo no)")"

hypr_bin() { command -v Hyprland 2>/dev/null || command -v hyprland 2>/dev/null || true; }
hypr_version() {
  local b="${1:-}" v=""
  [ -n "$b" ] || b="$(hypr_bin)"
  # Numéro qui suit « Hyprland » (ou « Tag: v… ») : la suite de --version liste aussi les bibliothèques (0.5.1…)
  [ -n "$b" ] && v="$(sonder 5s 'Hyprland --version' "$b" --version | grep -oE '^Hyprland v?[0-9]+\.[0-9]+\.[0-9]+|^Tag: v[0-9]+\.[0-9]+\.[0-9]+' |
    head -1 | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' || true)"
  if [ -z "$v" ]; then   # repli : version du paquet (la commande peut échouer sans écran)
    case "$FAMILY" in
      arch) v="$(sonder 5s 'pacman -Q hyprland' pacman -Q hyprland | awk '{print $2}' || true)" ;;
      fedora|suse) v="$(sonder 5s 'rpm -q hyprland' rpm -q --qf '%{VERSION}' hyprland || true)" ;;
      debian) v="$(sonder 5s 'dpkg-query hyprland' dpkg-query -W -f='${Version}' hyprland || true)" ;;
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
      die "$(t "$OSNAME n'a pas Noctalia v5 dans ses dépôts : installe-le toi-même ($NOCT_DOCS) puis relance." "$OSNAME doesn't have Noctalia v5 in its repositories: install it yourself ($NOCT_DOCS), then run this again.")"
    elif [ "${OSVER%%.*}" -lt 44 ] 2>/dev/null; then
      if [ "$OSID" = nobara ]; then
        die "$(t "Nobara $OSVER n'a pas Noctalia v5 : il faut Nobara 44 ou plus (basé sur Fedora 44)." "Nobara $OSVER doesn't have Noctalia v5: Nobara 44 or later is required (based on Fedora 44).")"
      fi
      die "$(t "Fedora $OSVER n'a pas Noctalia v5 : il faut Fedora 44 ou plus (sudo dnf system-upgrade download --releasever=44)." "Fedora $OSVER doesn't have Noctalia v5: Fedora 44 or later is required (sudo dnf system-upgrade download --releasever=44).")"
    fi
  fi
  [ "$FAMILY" != other ] || have Hyprland || die "$(t "distribution non gérée par l'installateur. Installe Hyprland (0.55 ou plus) et Noctalia v5 ($NOCT_DOCS), puis relance." "distribution not supported by the installer. Install Hyprland (0.55 or later) and Noctalia v5 ($NOCT_DOCS), then run this again.")"

  # Hyprland (Debian 13 : depuis trixie-backports, avec sa veille, son portail et uwsm)
  info "$(t "Vérification de la version de Hyprland…" "Checking the Hyprland version…")"
  hv="$(hypr_version)"
  if [ -z "$(hypr_bin)" ] || { [ -n "$hv" ] && ! ver_ge "$hv" "$HYPR_MIN"; }; then
    if [ -z "$(hypr_bin)" ]; then info "$(t "Hyprland n'est pas installé." "Hyprland is not installed.")"; else info "$(t "Hyprland $hv est trop ancien (0.55 ou plus)." "Hyprland $hv is too old (0.55 or later needed).")"; fi
    ask "$(t "L'installer maintenant ?" "Install it now?")" o || die "$(t "Hyprland 0.55 ou plus est nécessaire." "Hyprland 0.55 or later is required.")"
    dv=""
    if [ "$FAMILY" = fedora ]; then
      info "$(t "Recherche de Hyprland dans DNF (30 s maximum)…" "Checking Hyprland in DNF (30 s maximum)…")"
      dv="$(sonder 30s 'DNF repoquery hyprland' dnf -q repoquery --latest-limit=1 --qf '%{version}\n' hyprland | tail -1)" ||
        die "$(t "DNF n'a pas pu consulter les dépôts. Vérifie le réseau et les dépôts, puis relance ; aucun COPR ajouté." "DNF could not query repositories. Check the network and repositories, then retry; no COPR was added.")"
    fi
    if [ "$OSID" = debian ] && [ "$OSCODE" = trixie ]; then
      bpo_on || die "$(t "sans trixie-backports, Debian 13 n'a pas Hyprland 0.55 : relance et réponds oui, ou installe-le toi-même." "without trixie-backports, Debian 13 doesn't have Hyprland 0.55: run this again and answer yes, or install it yourself.")"
      bpo_install hyprland hypridle xdg-desktop-portal-hyprland uwsm || die "$(t "installation de Hyprland impossible depuis trixie-backports." "couldn't install Hyprland from trixie-backports.")"
    elif [ "$FAMILY" = fedora ] && { [ -z "$dv" ] || ! ver_ge "$dv" "$HYPR_MIN"; }; then
      # Fedora : pas de Hyprland récent dans les dépôts officiels (ni dans l'ancien COPR solopasha, abandonné) ;
      # dépôt communautaire (COPR) le plus suivi, à jour
      info "$(t "Pas de Hyprland 0.55 ou plus dans les dépôts de Fedora : dépôt communautaire COPR sdegler/hyprland" "No Hyprland 0.55 or later in Fedora's repositories: community COPR repository sdegler/hyprland")"
      info "  https://copr.fedorainfracloud.org/coprs/sdegler/hyprland/"
      ask "$(t "Activer ce dépôt et installer Hyprland ?" "Enable this repository and install Hyprland?")" o || die "$(t "Hyprland 0.55 ou plus est nécessaire." "Hyprland 0.55 or later is required.")"
      if have dnf5; then pkg_try dnf5-plugins; else pkg_try dnf-plugins-core; fi   # commande « dnf copr »
      sudo dnf -y copr disable solopasha/hyprland >/dev/null 2>&1 || true
      sudo dnf -y copr enable sdegler/hyprland || die "$(t "activation du dépôt sdegler/hyprland impossible (paquet dnf5-plugins ?)." "couldn't enable the sdegler/hyprland repository (dnf5-plugins package?).")"
      sudo dnf install -y --refresh hyprland hypridle xdg-desktop-portal-hyprland uwsm ||
        die "$(t "installation de Hyprland impossible depuis sdegler/hyprland." "couldn't install Hyprland from sdegler/hyprland.")"
    else
      pkg_install hyprland || die "$(t "installation de Hyprland impossible : installe-le toi-même puis relance." "couldn't install Hyprland: install it yourself, then run this again.")"
    fi
  fi
  if [ "$OSID" = debian ] && [ "$OSCODE" = trixie ]; then
    bpo_need=(); for p in hypridle xdg-desktop-portal-hyprland uwsm; do pkg_installed "$p" || bpo_need+=("$p"); done
    [ ${#bpo_need[@]} -eq 0 ] || { bpo_on && bpo_install "${bpo_need[@]}"; } || warn "$(t "Non installés depuis trixie-backports : ${bpo_need[*]}" "Not installed from trixie-backports: ${bpo_need[*]}")"
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
      info "$(t "Plusieurs Hyprland sont installés : $hb ($hv) démarre, alors que $meilleur ($mv_) est assez récent." "Several Hyprland builds are installed: $hb ($hv) starts, while $meilleur ($mv_) is recent enough.")"
      gener=(); while read -r b; do
        [ "$b" = "$meilleur" ] && break
        if du_paquet "$b"; then warn "$(t "$b vient d'un paquet de ta distribution : désinstalle ce paquet ou mets-le à jour." "$b comes from one of your distribution's packages: uninstall that package or update it.")"
        else gener+=("$b"); fi
      done < <(type -aP Hyprland hyprland 2>/dev/null | awk '!vu[$0]++')
      if [ ${#gener[@]} -gt 0 ] && ask "$(t "Mettre de côté les anciens (${gener[*]}) dans /usr/local/nc-ancien-hyprland (rien n'est supprimé) ?" "Move the old ones (${gener[*]}) aside to /usr/local/nc-ancien-hyprland (nothing is deleted)?")" o; then
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
        ok "$(t "Anciens Hyprland mis de côté : $meilleur ($mv_) sera utilisé. Pour les remettre : sudo cp -a $cote/. / " "Old Hyprland builds moved aside: $meilleur ($mv_) will be used. To put them back: sudo cp -a $cote/. / ")"
      fi
    fi
  fi
  hv="$(hypr_version)"
  [ -n "$hv" ] || die "$(t "version de Hyprland introuvable." "Hyprland version not found.")"
  if ! ver_ge "$hv" "$HYPR_MIN"; then
    # Diagnostic : d'où vient ce Hyprland, et que faire selon la distribution
    warn "$(t "Hyprland $hv ($(hypr_bin)) est trop ancien : cette config utilise le format Lua de Hyprland 0.55 ou plus." "Hyprland $hv ($(hypr_bin)) is too old: this config uses the Lua format of Hyprland 0.55 or later.")"
    case "$FAMILY:$OSID:$OSCODE" in
      debian:debian:trixie)
        info "$(t "Versions disponibles :" "Available versions:")"; apt-cache policy hyprland 2>/dev/null | sed -n '1,12p' | sed 's/^/     /'
        info "$(t "Mise à jour à la main : sudo apt install -t trixie-backports hyprland hypridle xdg-desktop-portal-hyprland uwsm" "Update by hand: sudo apt install -t trixie-backports hyprland hypridle xdg-desktop-portal-hyprland uwsm")" ;;
      debian:debian:*) info "$(t "Debian $OSCODE n'a pas Hyprland 0.55 : il faut Debian 13 (trixie) ou plus récent." "Debian $OSCODE doesn't have Hyprland 0.55: Debian 13 (trixie) or newer is required.")" ;;
      debian:*) info "$(t "$OSNAME n'a pas encore Hyprland 0.55 dans ses dépôts : installe-le autrement (https://wiki.hypr.land/Getting-Started/Installation/)." "$OSNAME doesn't have Hyprland 0.55 in its repositories yet: install it another way (https://wiki.hypr.land/Getting-Started/Installation/).")" ;;
      fedora:*) info "$(t "Mise à jour à la main : sudo dnf copr enable sdegler/hyprland && sudo dnf upgrade --refresh hyprland" "Update by hand: sudo dnf copr enable sdegler/hyprland && sudo dnf upgrade --refresh hyprland")" ;;
    esac
    case "$(hypr_bin)" in /usr/local/*|"$HOME"/*) info "$(t "Ce Hyprland a été installé à la main ($(hypr_bin)) et passe avant celui de ta distribution : supprime-le ou mets-le à jour." "This Hyprland was installed by hand ($(hypr_bin)) and takes precedence over your distribution's: remove it or update it.")" ;; esac
    die "$(t "Hyprland 0.55 ou plus est nécessaire." "Hyprland 0.55 or later is required.")"
  fi

  # Noctalia v5
  if ! have noctalia; then
    say "$(t "Installation de Noctalia v5" "Installing Noctalia v5")"
    case "$FAMILY" in
      arch) sudo pacman -S --needed noctalia ;;
      fedora) sudo dnf install -y noctalia ;;
      suse)
        case "$OSID" in
          opensuse-tumbleweed) rp=openSUSE_Tumbleweed ;;
          opensuse-slowroll) rp=openSUSE_Slowroll ;;
          *) rp="" ;;
        esac
        [ -n "$rp" ] || die "$(t "version d'openSUSE non gérée : suis $NOCT_DOCS puis relance." "unsupported openSUSE version: follow $NOCT_DOCS, then run this again.")"
        url="https://download.opensuse.org/repositories/home:neifua:Noctalia/$rp/home:neifua:Noctalia.repo"
        info "$(t "Noctalia n'est pas dans les dépôts d'openSUSE : dépôt tiers indiqué par la documentation officielle :" "Noctalia isn't in openSUSE's repositories: third-party repository given by the official documentation:")"
        info "$url"
        ask "$(t "Ajouter ce dépôt et installer Noctalia ?" "Add this repository and install Noctalia?")" o || die "$(t "Noctalia v5 est nécessaire : $NOCT_DOCS" "Noctalia v5 is required: $NOCT_DOCS")"
        sudo zypper addrepo --refresh --name noctalia-v5 "$url" && sudo zypper --gpg-auto-import-keys refresh && sudo zypper install noctalia ;;
      debian)
        case "$OSCODE" in
          trixie) src=noctalia-trixie.sources ;;
          resolute) src=noctalia-resolute.sources ;;
          sid|"") [ "$OSID" = debian ] && src=noctalia-unstable.sources || src="" ;;
          *) src="" ;;
        esac
        [ -n "$src" ] || die "$(t "version de ${OSID:-Debian} non gérée par l'installateur (Debian 13, Debian Sid, Ubuntu 26.04) : suis $NOCT_DOCS puis relance." "${OSID:-Debian} version not supported by the installer (Debian 13, Debian Sid, Ubuntu 26.04): follow $NOCT_DOCS, then run this again.")"
        info "$(t "Noctalia n'est pas dans les dépôts de ta distribution : dépôt officiel indiqué par la documentation :" "Noctalia isn't in your distribution's repositories: official repository given by the documentation:")"
        info "$(t "  clé : https://pkg.noctalia.dev/deb/nickh-archive-keyring.deb" "  key: https://pkg.noctalia.dev/deb/nickh-archive-keyring.deb")"
        info "$(t "  dépôt : https://pkg.noctalia.dev/deb/$src" "  repository: https://pkg.noctalia.dev/deb/$src")"
        ask "$(t "Ajouter ce dépôt et installer Noctalia ?" "Add this repository and install Noctalia?")" o || die "$(t "Noctalia v5 est nécessaire : $NOCT_DOCS" "Noctalia v5 is required: $NOCT_DOCS")"
        have wget || sudo apt-get $APT_OPT install -y wget
        kd="$(mktemp -d)"; wget -q -O "$kd/keyring.deb" https://pkg.noctalia.dev/deb/nickh-archive-keyring.deb && sudo dpkg -i "$kd/keyring.deb"; rm -rf "$kd"
        sudo wget -q -O "/etc/apt/sources.list.d/$src" "https://pkg.noctalia.dev/deb/$src"
        sudo apt-get $APT_OPT update -q || true
        # Debian 13 : ce dépôt est construit pour trixie-backports (comme Hyprland 0.55) : mêmes versions des bibliothèques
        if [ "$OSCODE" = trixie ]; then { bpo_on && bpo_install noctalia; } || true; else pkg_install noctalia || true; fi ;;
    esac
    have noctalia || die "$(t "Noctalia v5 n'a pas pu être installé : $NOCT_DOCS" "Noctalia v5 couldn't be installed: $NOCT_DOCS")"
  fi
  if [ "$FAMILY" = arch ] && pkg_installed noctalia-shell; then
    warn "$(t "L'ancienne Noctalia v4 (noctalia-shell) est installée. Cette config utilise la v5 : le service « noctalia » de ta session lancera la v5." "The old Noctalia v4 (noctalia-shell) is installed. This config uses v5: your session's “noctalia” service will start v5.")"
    warn "$(t "Tu pourras désinstaller la v4 ensuite : sudo pacman -Rns noctalia-shell" "You can uninstall v4 afterwards: sudo pacman -Rns noctalia-shell")"
  fi
  info "$(t "Vérification de la version de Noctalia (5 s maximum)…" "Checking the Noctalia version (5 s maximum)…")"
  nv="$(sonder 5s 'noctalia --version' noctalia --version | head -1 || true)"
  [ -n "$nv" ] || warn "$(t "Noctalia est présent mais sa version ne répond pas ; poursuite des autres vérifications." "Noctalia is present but its version is unavailable; continuing the other checks.")"
  ok "Hyprland $hv · Noctalia (${nv:-$(t 'version inconnue' 'unknown version')})"
fi

# ── Écran ────────────────────────────────────────────────────────────────────
# Écran principal : l'écran interne d'un portable (eDP), sinon le premier branché.
# Sa définition (pixels), sa taille physique (mm), puis l'échelle que choisira la config (nc/ecrans.lua : mêmes
# seuils que Hyprland, sans descendre sous 1600 x 900 points) et donc sa taille « logique » en points.
info "$(t "Détection des écrans…" "Detecting displays…")"
MON=""; PXW=0; PXH=0; MMW=0; MMH=0
if have hyprctl && mj="$(sonder 5s 'hyprctl monitors' hyprctl monitors all -j)"; then
  mj="$(jq -c '([.[] | select(.name | startswith("eDP"))][0]) // .[0] // empty' <<<"$mj" 2>/dev/null || true)"
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
ok "$(t "Écran principal : $MON, ${PXW}x${PXH} pixels, échelle $SCALE (${LW}x${LH} points)" "Main display: $MON, ${PXW}x${PXH} pixels, scale $SCALE (${LW}x${LH} points)")"

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
info "$(t "Détection du clavier…" "Detecting keyboard…")"
lc_etat="$(sonder 5s 'localectl status' localectl status || true)"
for kb in \
  "$(sed -n 's/.*X11 Layout: *//p' <<<"$lc_etat" | head -1)" \
  "$(sed -n 's/^XKBLAYOUT="\{0,1\}\([^"]*\)"\{0,1\}/\1/p' /etc/default/keyboard 2>/dev/null | head -1 || true)" \
  "$(sed -n 's/.*VC Keymap: *//p' <<<"$lc_etat" | head -1 | sed -E 's/[-_].*//')" \
  "$(echo "${LANG:-}" | sed -nE 's/^[a-z]+_([A-Z]{2}).*/\1/p' | tr '[:upper:]' '[:lower:]')"; do
  kb="$(echo "$kb" | tr -d ' ')"
  if kb_valide "$kb"; then KBL="$kb"; break; fi
done
KBL="${KBL:-us}"
KBO=""; case "$KBL" in *,*) KBO="grp:win_space_toggle" ;; esac
ok "$(t "Clavier : $KBL" "Keyboard: $KBL")"
# Navigateur par défaut (épinglé dans la recherche et le dock)
info "$(t "Détection du navigateur par défaut…" "Detecting default browser…")"
BROWSER="$(sonder 5s 'xdg-settings' xdg-settings get default-web-browser | sed 's/\.desktop$//' | head -1 || true)"
BROWSER="${BROWSER:-firefox}"
ok "$(t "Navigateur : $BROWSER" "Browser: $BROWSER")"
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
ok "$(t "Logo de la barre : ${DISTRO_LOGO:-icône de Noctalia}" "Bar logo: ${DISTRO_LOGO:-Noctalia icon}")"
# Demandes de mot de passe (polkit) : l'agent de KDE s'il est installé, sinon celui de Noctalia
POLKIT=true; KDE_POLKIT=0
info "$(t "Vérification de l’agent polkit…" "Checking the polkit agent…")"
if sonder 5s 'systemctl polkit' systemctl --user cat plasma-polkit-agent.service >/dev/null; then POLKIT=false; KDE_POLKIT=1; fi
# Nom affiché au démarrage (GRUB) : modèle du PC s'il est lisible, sinon nom de la distribution
BOOT_TITLE="$( { [ "$(dmi sys_vendor)" = LENOVO ] && dmi product_version || dmi product_name; } | tr -cd 'A-Za-z0-9 ._-' | sed -E 's/ +/ /g; s/^ //; s/ $//')"
w_last="${BOOT_TITLE##* }"
[[ "$w_last" =~ [0-9] && "$w_last" =~ [A-Za-z] && ${#w_last} -ge 5 && "$BOOT_TITLE" == *" "* ]] && BOOT_TITLE="${BOOT_TITLE% *}"
if [ -z "$BOOT_TITLE" ] || [ ${#BOOT_TITLE} -gt 24 ] || echo "$BOOT_TITLE" | grep -qiE 'o\.?e\.?m|system product|default string|to be filled|not specified|not applicable|^[0-9. -]+$'; then
  BOOT_TITLE="$(echo "$OSNAME" | tr -cd 'A-Za-z0-9 ._-')"
fi

# Écran verrouillé : Noctalia (qui dessine l'écran de verrouillage) ne doit pas être relancée, sinon Hyprland affiche
# « l'écran de verrouillage a planté ». L'installation attend que tu sois là.
if [ "$MODE" != files ] && have noctalia; then
  info "$(t "Vérification du verrouillage Noctalia (5 s maximum)…" "Checking the Noctalia lock status (5 s maximum)…")"
  statut_code=0
  statut="$(sonder 5s 'noctalia msg status' noctalia msg status)" || statut_code=$?
  if [ "$statut_code" = 124 ] || [ "$statut_code" = 137 ]; then
    die "$(t "Noctalia ne répond pas : impossible de vérifier le verrouillage. Installation arrêtée avant la copie ; vérifie Noctalia puis relance." "Noctalia is unresponsive: cannot check the lock status. Installation stopped before copying; check Noctalia and retry.")"
  fi
  if [ "$statut_code" = 0 ] && grep -qE '"locked": *true' <<<"$statut"; then
    die "$(t "l'écran est verrouillé : relance l'installation une fois la session déverrouillée." "the screen is locked: run the install again once the session is unlocked.")"
  fi
fi

echo
info "$(t "Ce script va :" "This script will:")"
info "$(t "  Tout ce qui est déjà en place est sauté : seul ce qui manque ou a changé est fait." "  Anything already in place is skipped: only what's missing or has changed is done.")"
info "$(t "  1. installer les paquets manquants (sans mise à jour système) ;" "  1. install the missing packages (no system update);")"
info "$(t "  2. sauvegarder puis remplacer ta config Hyprland, Noctalia, kitty, Qt/KDE ;" "  2. back up, then replace your Hyprland, Noctalia, kitty and Qt/KDE config;")"
info "$(t "  3. te proposer la config du terminal (zsh, oh-my-zsh, powerlevel10k) et de Neovim (LazyVim) ;" "  3. offer you the terminal config (zsh, oh-my-zsh, powerlevel10k) and the Neovim config (LazyVim);")"
info "$(t "  4. activer les services de ta session (barre, couleurs, miniatures, profils d'énergie, veille) ;" "  4. enable your session's services (bar, colors, thumbnails, power profiles, sleep);")"
[ "$MODE" = full ] && info "$(t "  5. te proposer, une par une, les étapes système pas encore faites (énergie, Wi-Fi, démarrage, écran de connexion, pilote NVIDIA)." "  5. offer you, one by one, the system steps not done yet (power, Wi-Fi, boot, login screen, NVIDIA driver).")"
ask "$(t "On y va ?" "Ready to go?")" o || exit 0

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
  info "$(t "L'île dynamique utilise Quickshell 0.3, absent des dépôts de Fedora : dépôt communautaire COPR errornointernet/quickshell" "The dynamic island uses Quickshell 0.3, which isn't in Fedora's repositories: community COPR repository errornointernet/quickshell")"
  if ask "$(t "Activer ce dépôt pour l'île dynamique ?" "Enable this repository for the dynamic island?")" o; then
    if have dnf5; then pkg_try dnf5-plugins; else pkg_try dnf-plugins-core; fi
    sudo dnf -y copr enable errornointernet/quickshell >/dev/null 2>&1 &&
      { if have qs; then sudo dnf upgrade -y --refresh quickshell; else sudo dnf install -y --refresh quickshell; fi; } >/dev/null 2>&1 &&
      hash -r && ver_ge "$(qs_ver)" 0.3 && ok "$(t "Quickshell $(qs_ver) installé." "Quickshell $(qs_ver) installed.")" ||
      warn "$(t "Quickshell non installé depuis le COPR : l'île du plugin Noctalia sera utilisée." "Quickshell not installed from the COPR: the Noctalia plugin island will be used.")"
    hash -r
  fi
fi
GENERIC=(uwsm hypridle xdg-desktop-portal-hyprland xdg-desktop-portal-gtk kitty nautilus qt6ct papirus-icon-theme cava swaybg imagemagick
         jq grim slurp swappy wl-clipboard wtype brightnessctl libnotify python qalc playerctl fastfetch bluez-utils gdbus
         zsh git curl unzip nerdfont adwaita-fonts noto-fonts breeze quickshell sushi wf-recorder tesseract tesseract-fra tesseract-eng checkupdates
         enregistreur)
if [ "$MODE" != files ]; then
  say "$(t "1. Paquets" "1. Packages")"
  missing=(); manual=()
  for g in "${GENERIC[@]}"; do
    p="$(pname "$g")"
    if [ -z "$p" ]; then manual+=("$g"); continue; fi
    pkg_installed "$p" && continue
    [ "$g" = enregistreur ] && { have pw-record || have parec || have arecord; } && continue
    [ "$g" = nerdfont ] && [ -n "$(fc-list : family 2>/dev/null | grep -i "CaskaydiaCove Nerd Font")" ] && continue
    missing+=("$p")
  done
  if [ ${#missing[@]} -eq 0 ]; then
    ok "$(t "Tout est déjà installé." "Everything is already installed.")"
  elif [ "$FAMILY" = arch ]; then
    unknown=()
    for p in "${missing[@]}"; do pacman -Si "$p" >/dev/null 2>&1 || unknown+=("$p"); done
    if [ ${#unknown[@]} -gt 0 ]; then
      warn "$(t "Introuvables dans ta base de paquets : ${unknown[*]}" "Not found in your package database: ${unknown[*]}")"
      die "$(t "ta base de paquets est sans doute ancienne. Lance « sudo pacman -Syu », redémarre si besoin, puis relance ce script." "your package database is probably out of date. Run “sudo pacman -Syu”, reboot if needed, then run this script again.")"
    fi
    info "$(t "À installer : ${missing[*]}" "To install: ${missing[*]}")"
    if pkg_install "${missing[@]}"; then ok "$(t "Paquets installés." "Packages installed.")"; else warn "$(t "Paquets non installés : ${missing[*]} (à installer toi-même)." "Packages not installed: ${missing[*]} (install them yourself).")"; fi
  else
    failed=()
    for p in "${missing[@]}"; do pkg_install "$p" >/dev/null 2>&1 && info "$(t "installé : $p" "installed: $p")" || failed+=("$p"); done
    [ ${#failed[@]} -eq 0 ] && ok "$(t "Paquets installés." "Packages installed.")" || warn "$(t "Non installés (nom différent ou absent sur ta distribution) : ${failed[*]}" "Not installed (different name, or missing on your distribution): ${failed[*]}")"
  fi
  case " ${manual[*]} " in
    *" nerdfont "*) fc-list : family 2>/dev/null | grep -i "CaskaydiaCove Nerd Font" >/dev/null ||
                      info "$(t "La police du terminal (CaskaydiaCove Nerd Font) t'est proposée en téléchargement à l'étape 3." "The terminal font (CaskaydiaCove Nerd Font) will be offered for download in step 3.")" ;;
  esac
fi

# ── 2. Fichiers ──────────────────────────────────────────────────────────────
say "$(t "2. Fichiers de configuration" "2. Configuration files")"
NOCT_WAS_ACTIVE=0
if [ "$MODE" != files ] && systemctl --user is-active --quiet noctalia.service 2>/dev/null; then
  NOCT_WAS_ACTIVE=1
  systemctl --user stop noctalia.service   # Noctalia réécrit ses réglages : on l'arrête pendant la copie
fi

# Ancien cockpit QML orphelin : remplacé par Jarvis.qml, sauvegardé avant retrait.
rel=.config/quickshell/nc-ile/JarvisDashboard.qml
if [ -f "$HOME/$rel" ] || [ -L "$HOME/$rel" ]; then
  backup "$rel"
  rm -f -- "$HOME/$rel"
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
[ "$migrated" = 1 ] && ok "$(t "Ancienne version (« legion ») convertie ; ses fichiers sont dans la sauvegarde." "Old version (“legion”) converted; its files are in the backup.")"

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
  info "$(t "Quickshell (l'île dynamique : centre de contrôle, notifications, Spotlight) n'est pas dans les dépôts de ta distribution." "Quickshell (the dynamic island: Control Center, notifications, Spotlight) isn't in your distribution's repositories.")"
  info "$(t "Il peut être compilé depuis ses sources officielles (https://quickshell.org) : environ 5 minutes, ~400 Mo d'outils." "It can be built from its official sources (https://quickshell.org): about 5 minutes, ~400 MB of tools.")"
  ask "$(t "Le compiler et l'installer (dans $prefixe) ?" "Build and install it (in $prefixe)?")" o || return 1
  pkg_try build-essential cmake ninja-build pkg-config git ca-certificates qt6-base-dev qt6-base-private-dev \
    qt6-declarative-dev qt6-declarative-private-dev qt6-wayland-dev qt6-wayland-private-dev qt6-shadertools-dev qt6-svg-dev \
    libwayland-dev libpipewire-0.3-dev libdrm-dev libgbm-dev libcli11-dev spirv-tools libvulkan-dev wayland-protocols \
    qml6-module-qtquick qml6-module-qtquick-window qml6-module-qtquick-shapes qml6-module-qtquick-effects \
    qml6-module-qtqml qml6-module-qtqml-workerscript qml6-module-qtqml-models
  # Debian 13 : protocoles Wayland trop anciens dans trixie (il faut 1.45 ou plus) : version des backports
  if [ "$OSCODE" = trixie ]; then bpo_on && bpo_install wayland-protocols >/dev/null 2>&1; fi
  wd="$(mktemp -d)"
  info "$(t "Compilation de Quickshell (5 à 15 minutes selon le processeur) :" "Building Quickshell (5 to 15 minutes depending on the processor):")"
  if { avec_progres "$(t "Téléchargement des sources" "Downloading the sources")" "$wd/clone.log" git clone -q --depth 1 --branch v0.3.2 https://git.outfoxxed.me/quickshell/quickshell.git "$wd/qs" ||
       avec_progres "$(t "Téléchargement des sources" "Downloading the sources")" "$wd/clone.log" git clone -q --depth 1 --branch v0.3.2 https://github.com/quickshell-mirror/quickshell.git "$wd/qs"; } &&
     avec_progres "$(t "Préparation" "Configuring")" "$wd/cmake.log" cmake -S "$wd/qs" -B "$wd/build" -GNinja -DCMAKE_BUILD_TYPE=RelWithDebInfo -DCMAKE_INSTALL_PREFIX="$prefixe" \
       -DDISTRIBUTOR="noctalia-config" -DCRASH_HANDLER=OFF -DUSE_JEMALLOC=OFF -DX11=OFF -DI3=OFF \
       -DSCREENCOPY=ON -DSCREENCOPY_HYPRLAND_TOPLEVEL=ON \
       -DSERVICE_PAM=OFF -DSERVICE_POLKIT=OFF -DSERVICE_GREETD=OFF -DSERVICE_STATUS_NOTIFIER=OFF \
       -DNETWORK=OFF -DBLUETOOTH=OFF -DWAYLAND_SESSION_LOCK=OFF -DHYPRLAND_GLOBAL_SHORTCUTS=OFF \
       -DHYPRLAND_SURFACE_EXTENSIONS=OFF &&
     avec_progres "$(t "Compilation" "Building")" "$wd/build.log" cmake --build "$wd/build" &&
     sudo cmake --install "$wd/build" >/dev/null 2>&1; then
    ok "$(t "Quickshell installé ($(qs --version 2>/dev/null | head -1))." "Quickshell installed ($(qs --version 2>/dev/null | head -1)).")"
    rm -rf "$wd"
    return 0
  fi
  warn "$(t "Compilation de Quickshell impossible (journal : $wd) : l'île du plugin Noctalia est utilisée." "Couldn't build Quickshell (log: $wd): the Noctalia plugin island is used.")"
  return 1
}
# L'île Quickshell pour tout le monde : paquet sur Arch et Fedora, compilée sur Debian / Ubuntu
if [ "$FAMILY" = debian ] && [ "$MODE" != files ]; then
  # Les anciennes installations étaient compilées sans capture : leur numéro de version ne suffit pas.
  if ! have qs || ! ver_ge "$(qs_ver || true)" 0.3 || ! bash "$REPO/home/.local/bin/nc-qs-capture"; then
    if have qs; then
      warn "$(t "Quickshell doit être recompilé avec la capture pour la vue des fenêtres (Super + A)." "Quickshell must be rebuilt with capture support for the window overview (Super + A).")"
    fi
    compiler_quickshell || true
    hash -r
  fi
fi
# La capture ne sert qu'aux aperçus de la vue des fenêtres (Super + A) : sans elle, l'île Quickshell reste (avant, un
# Quickshell compilé sans capture faisait perdre toute l'île et ses réglages à la mise à jour, sur Debian)
if have qs && ver_ge "$(qs_ver || true)" 0.3 && bash "$REPO/home/.local/bin/nc-qs-capture" --modules; then
  ILE=quickshell
  bash "$REPO/home/.local/bin/nc-qs-capture" ||
    warn "$(t "Quickshell sans capture : la vue des fenêtres (Super + A) est indisponible ; relance nc-maj et accepte sa recompilation." "Quickshell without capture: the window overview (Super + A) is unavailable; run nc-update again and accept rebuilding it.")"
  POLICE_ICONES="$HOME/.local/share/fonts/MaterialSymbolsRounded.ttf"
  if [ ! -s "$POLICE_ICONES" ] && [ "$MODE" != files ] && have curl; then
    info "$(t "Icônes de l'île : police Material Symbols Rounded (Google), https://github.com/google/material-design-icons" "Island icons: Material Symbols Rounded font (Google), https://github.com/google/material-design-icons")"
    if ask "$(t "La télécharger (15 Mo) ?" "Download it (15 MB)?")" o; then
      mkdir -p "$(dirname "$POLICE_ICONES")"
      if curl -fsSL -o "$POLICE_ICONES.tmp" 'https://github.com/google/material-design-icons/raw/master/variablefont/MaterialSymbolsRounded%5BFILL,GRAD,opsz,wght%5D.ttf'; then
        mv "$POLICE_ICONES.tmp" "$POLICE_ICONES"; fc-cache -f "$(dirname "$POLICE_ICONES")" >/dev/null 2>&1 || true; ok "$(t "Police d'icônes installée." "Icon font installed.")"
      else
        rm -f "$POLICE_ICONES.tmp"; warn "$(t "Téléchargement impossible : l'île du plugin Noctalia est utilisée." "Download failed: the Noctalia plugin island is used.")"; ILE=noctalia
      fi
    else
      ILE=noctalia
    fi
  fi
  [ -s "$POLICE_ICONES" ] || ILE=noctalia
elif have qs; then
  warn "$(t "Quickshell est incompatible ou ses modules sont incomplets : l'île du plugin Noctalia est utilisée." "Quickshell is incompatible or its modules are incomplete: the Noctalia plugin island is used.")"
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
  # assistant.conf contient la clé privée : aucun modèle du dépôt ne doit remplacer ce fichier personnel.
  case "$rel" in .zshrc|.p10k.zsh|.config/nvim/*|.config/nc/assistant.conf) continue ;; esac   # étapes 3 et 3b
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
ok "$(t "$copied fichier(s) installé(s), $same déjà à jour." "$copied file(s) installed, $same already up to date.")$([ "$copied" -gt 0 ] && echo " $(t "Sauvegarde : $BK" "Backup: $BK")")"
# Noms anglais des commandes (nc-settings = nc-reglages…) : liens, quelle que soit la langue choisie
# (NOMS_ANGLAIS : défini par nc-langue, lu en haut du script)
for paire in $NOMS_ANGLAIS; do
  [ -x "$HOME/.local/bin/${paire#*:}" ] || continue
  [ -e "$HOME/.local/bin/${paire%%:*}" ] && [ ! -L "$HOME/.local/bin/${paire%%:*}" ] && continue   # jamais un vrai fichier
  ln -sfn "${paire#*:}" "$HOME/.local/bin/${paire%%:*}"
done

# Session Hyprland ouverte avec l'ancien format : bascule à chaud vers hyprland.lua, avant de retirer l'ancienne config
# (Hyprland recharge sa config dès qu'un fichier change : la retirer avant la bascule laisserait la session sans réglages).
if have hyprctl && hyprctl systeminfo 2>/dev/null | grep 'configProvider: hyprlang' >/dev/null; then
  hyprctl reload full-reset >/dev/null 2>&1 && ok "$(t "Session Hyprland passée au format Lua." "Hyprland session switched to the Lua format.")"
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
  ok "$(t "Ancienne config Hyprland (hyprland.conf) remplacée par hyprland.lua ; elle est dans la sauvegarde." "Old Hyprland config (hyprland.conf) replaced by hyprland.lua; it's in the backup.")"
  [ -d "$HC/conf.d" ] && info "$(t "Le dossier ~/.config/hypr/conf.d contient encore tes propres fichiers : à reporter dans ~/.config/hypr/perso.lua si tu en as besoin." "The ~/.config/hypr/conf.d folder still has your own files: move them to ~/.config/hypr/perso.lua if you need them.")"
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
  if [ "$NC_LANGUE" = en ]; then
    cat > "$PERSO" <<'PERSO_EN'
-- Your personal Hyprland settings: loaded last, never replaced by install.sh or nc-update.
-- Hyprland 0.55+ Lua format (https://wiki.hypr.land). Remove "--" at the start of a line to enable it.
--
-- Shortcuts without editing a file: nc-shortcut (add, change or disable the config's shortcuts).
-- Common settings (gaps, borders, touchpad, display…): nc-settings.
--
-- hl.bind("SUPER + B", hl.dsp.exec_cmd("firefox"), { description = "My shortcuts|Browser" })
-- hl.monitor({ output = "HDMI-A-1", mode = "preferred", position = "auto", scale = 1 })
-- hl.config({ general = { gaps_out = 6 }, decoration = { rounding = 10 } })
-- hl.on("hyprland.start", function() hl.exec_cmd("discord --start-minimized") end)
PERSO_EN
  else
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
  fi
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
    chmod 600 "$KEY"; ok "$(t "Clé de l'historique du presse-papiers créée." "Clipboard history key created.")"
  else
    rm -f "$KEY"; warn "$(t "Clé du presse-papiers non créée : l'historique du presse-papiers ne fonctionnera pas." "Clipboard key not created: clipboard history won't work.")"
  fi
fi

[ "$MODE" = files ] && { say "$(t "Terminé (fichiers seulement)." "Done (files only).")"; info "$(t "Les configs du terminal (zsh) et de Neovim n'ont pas été touchées : relance sans --files-only pour les installer." "The terminal (zsh) and Neovim configs weren't touched: run again without --files-only to install them.")"; info "$(t "Assistant distant facultatif : nc-assistant configurer (URL et clé du serveur)." "Optional remote assistant: nc-assistant configurer (server URL and key).")"; exit 0; }

# ── 3. Terminal : zsh + oh-my-zsh + powerlevel10k ─────────────────────────────
say "$(t "3. Terminal : zsh, oh-my-zsh, powerlevel10k (invite sur deux lignes, suggestions, couleurs)" "3. Terminal: zsh, oh-my-zsh, powerlevel10k (two-line prompt, suggestions, colors)")"
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
  ok "$(t "Déjà en place (zsh par défaut, oh-my-zsh, powerlevel10k, police)." "Already set up (zsh as default shell, oh-my-zsh, powerlevel10k, font).")"
elif ask "$(t "Installer la config du terminal (seulement ce qui manque) ?" "Install the terminal config (only what's missing)?")" o; then
  have zsh || pkg_try zsh
  have git || pkg_try git
  if ! have zsh || ! have git; then
    warn "$(t "zsh ou git manquant : étape ignorée (installe-les puis relance)." "zsh or git missing: step skipped (install them, then run this again).")"
  else
    if [ ${#need[@]} -gt 0 ]; then
      info "$(t "Téléchargements depuis GitHub (dépôts officiels) :" "Downloads from GitHub (official repositories):")"
      for d in "${need[@]}"; do info "  ${REPOS[$d]}"; done
      if ask "$(t "Les télécharger ?" "Download them?")" o; then
        for d in "${need[@]}"; do
          avec_progres "$(t "Téléchargement de $(basename "$d")" "Downloading $(basename "$d")")" /dev/null git clone -q --depth 1 "${REPOS[$d]}" "$d" && echo "${d#"$HOME/"}" >> "$BK/.created" || warn "$(t "téléchargement impossible : ${REPOS[$d]}" "download failed: ${REPOS[$d]}")"
        done
      fi
    fi
    for f in .zshrc .p10k.zsh; do
      [ -f "$HOME/$f" ] && cmp -s "$REPO/home/$f" "$HOME/$f" && continue
      if [ -f "$HOME/$f" ]; then
        ask "$(t "Remplacer ton ~/$f (il sera sauvegardé) ?" "Replace your ~/$f (it will be backed up)?")" o || continue
        backup "$f"
      else
        echo "$f" >> "$BK/.created"
      fi
      cp "$REPO/home/$f" "$HOME/$f"
    done
    ok "$(t "Config du terminal installée. Tes alias et réglages personnels : ~/.zshrc.perso" "Terminal config installed. Your own aliases and settings: ~/.zshrc.perso")"
    if [ "$(basename "$(getent passwd "$(id -un)" | cut -d: -f7)")" != zsh ]; then
      ask "$(t "Faire de zsh ton shell par défaut (il te demandera ton mot de passe) ?" "Make zsh your default shell (it will ask for your password)?")" o && chsh -s "$(command -v zsh)" && ok "$(t "zsh est ton shell par défaut (à la prochaine connexion)." "zsh is your default shell (from your next login).")"
    fi
  fi
  # Police du terminal (icônes de l'invite) : paquet sur Arch, sinon téléchargement depuis la page officielle de Nerd Fonts
  if ! has_font; then
    url=https://github.com/ryanoasis/nerd-fonts/releases/latest/download/CascadiaCode.zip
    info "$(t "Police du terminal (CaskaydiaCove Nerd Font) absente : $url" "Terminal font (CaskaydiaCove Nerd Font) missing: $url")"
    if have curl && have unzip && ask "$(t "La télécharger dans ~/.local/share/fonts ?" "Download it to ~/.local/share/fonts?")" o; then
      fd="$HOME/.local/share/fonts/CaskaydiaCove"; zd="$(mktemp -d)"
      if curl -fsSL -o "$zd/f.zip" "$url" && mkdir -p "$fd" && unzip -qo "$zd/f.zip" '*.ttf' -d "$fd"; then
        fc-cache -f "$fd" >/dev/null 2>&1 || true; ok "$(t "Police installée." "Font installed.")"
      else
        warn "$(t "Téléchargement de la police impossible." "Couldn't download the font.")"
      fi
      rm -rf "$zd"
    fi
  fi
fi

# ── 3b. Neovim (LazyVim) ──────────────────────────────────────────────────────
say "$(t "3b. Neovim : LazyVim avec ses extras (C/C++, JavaScript, formatage, Git…)" "3b. Neovim: LazyVim with its extras (C/C++, JavaScript, formatting, Git…)")"
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
  nv_q="$(t "Config déjà à jour ; installer les outils manquants (${nv_tools[*]}) ?" "Config already up to date; install the missing tools (${nv_tools[*]})?")"
else
  nv_q="$(t "Installer la config Neovim (seulement ce qui manque) ?" "Install the Neovim config (only what's missing)?")"
fi
if [ "$nv_same" = 1 ] && [ "$nv_plugins" = 1 ] && [ ${#nv_tools[@]} -eq 0 ]; then
  ok "$(t "Déjà en place (config, plugins et outils)." "Already set up (config, plugins and tools).")"
elif ask "$nv_q" o; then
  # Outils dont LazyVim et ses extras ont besoin (noms selon la distribution ; déjà installés ou absents : ignorés)
  case "$FAMILY" in
    arch)   pkg_try neovim git ripgrep fd gcc make nodejs npm tree-sitter-cli gitui ;;
    fedora) pkg_try neovim git ripgrep fd-find gcc make tree-sitter-cli gitui
            # Fedora 44 : nodejs24 / nodejs24-npm (plus de paquet « nodejs ») ; demandés par la commande fournie
            have node || sudo dnf install -y /usr/bin/node /usr/bin/npm >/dev/null 2>&1 || true ;;
    # python3-venv : Mason installe ruff et le serveur Python (extra Python) dans un environnement virtuel, que Debian
    # et Ubuntu séparent de python3
    debian) pkg_try neovim git ripgrep fd-find gcc make nodejs npm tree-sitter-cli gitui python3-venv ;;
    suse)   pkg_try neovim git ripgrep fd gcc make nodejs-default npm-default tree-sitter gitui ;;
  esac
  nv="$(nv_ver)"
  # Neovim trop ancien dans la distribution (Debian 13 : 0.10) : version officielle de neovim.io dans ~/.local
  if [ -z "$nv" ] || ! ver_ge "$nv" 0.11.2; then
    case "$(uname -m)" in x86_64) na=nvim-linux-x86_64 ;; aarch64) na=nvim-linux-arm64 ;; *) na="" ;; esac
    url="https://github.com/neovim/neovim/releases/latest/download/$na.tar.gz"
    info "$(t "Neovim ${nv:-absent}$([ -n "$nv" ] && echo " (trop ancien)") : LazyVim demande la 0.11.2 ou plus." "Neovim ${nv:-missing}$([ -n "$nv" ] && echo " (too old)"): LazyVim needs 0.11.2 or later.")"
    if [ -n "$na" ] && have curl && ask "$(t "Installer la version officielle de Neovim dans ~/.local (depuis $url) ?" "Install the official Neovim release in ~/.local (from $url)?")" o; then
      zd="$(mktemp -d)"
      if curl -fsSL -o "$zd/nvim.tar.gz" "$url" && mkdir -p "$HOME/.local/opt" "$HOME/.local/bin" &&
         rm -rf "$HOME/.local/opt/$na" && tar -xzf "$zd/nvim.tar.gz" -C "$HOME/.local/opt"; then
        ln -sfn "$HOME/.local/opt/$na/bin/nvim" "$HOME/.local/bin/nvim"
        nv="$(nv_ver)"; ok "$(t "Neovim $nv installé (~/.local/bin/nvim)." "Neovim $nv installed (~/.local/bin/nvim).")"
      else
        warn "$(t "Téléchargement de Neovim impossible." "Couldn't download Neovim.")"
      fi
      rm -rf "$zd"
    fi
    if [ -z "$nv" ] || ! ver_ge "$nv" 0.11.2; then
      warn "$(t "Neovim 0.11.2 ou plus manquant : config copiée quand même, elle servira dès qu'il sera installé." "Neovim 0.11.2 or later missing: config copied anyway; it will be used once Neovim is installed.")"
    fi
  fi
  if [ "$nv_same" = 1 ]; then
    ok "$(t "Config Neovim déjà à jour." "Neovim config already up to date.")"
  elif [ ! -e "$NV" ] || ask "$(t "Remplacer ta config ~/.config/nvim (elle sera sauvegardée) ?" "Replace your ~/.config/nvim config (it will be backed up)?")" o; then
    if [ -e "$NV" ]; then backup .config/nvim; rm -rf "$NV"; else echo ".config/nvim" >> "$BK/.created"; fi
    mkdir -p "$HOME/.config" && cp -a "$REPO/home/.config/nvim" "$NV"
    mkdir -p "$STATE"; echo "$NV_SUM" > "$NV_STAMP"
    ok "$(t "Config Neovim installée." "Neovim config installed.")"
    nv_plugins=0
  fi
  # Plugins aux versions exactes de lazy-lock.json (sinon ils s'installent au premier lancement)
  if [ "$nv_plugins" = 0 ] && [ -n "$nv" ] && ver_ge "$nv" 0.11.2 && diff -rq "$REPO/home/.config/nvim" "$NV" >/dev/null 2>&1; then
    # Téléchargement en arrière-plan, avec l'avancement affiché (plugins présents / plugins du lock) ;
    # abandon au bout de 10 minutes (connexion lente) : ils s'installeront alors au premier lancement de nvim.
    nv_total="$(grep -c '"branch"' "$NV/lazy-lock.json" 2>/dev/null || echo '?')"
    nv_lazy="${XDG_DATA_HOME:-$HOME/.local/share}/nvim/lazy"
    info "$(t "Téléchargement des plugins Neovim ($nv_total, une à cinq minutes selon la connexion)…" "Downloading Neovim plugins ($nv_total, one to five minutes depending on the connection)…")"
    timeout 600 "$(nv_bin)" --headless "+Lazy! restore" +qa >/dev/null 2>&1 &
    nv_pid=$!
    while kill -0 "$nv_pid" 2>/dev/null; do
      printf '\r   %s / %s plugins' "$(find "$nv_lazy" -mindepth 1 -maxdepth 1 -type d 2>/dev/null | wc -l)" "$nv_total"
      sleep 2
    done
    printf '\r%60s\r' ''
    if wait "$nv_pid"; then ok "$(t "Plugins Neovim installés." "Neovim plugins installed.")"
    else warn "$(t "Plugins non installés maintenant : ils s'installeront au premier lancement de nvim." "Plugins not installed now: they'll install the first time you start nvim.")"; fi
  fi
fi

# ── 3c. Firefox ──────────────────────────────────────────────────────────────
# Préférences (user.js) et style de l'île (chrome/userChrome.css) dans le profil Firefox par défaut : facultatif,
# proposé seulement si Firefox a un profil ici ; « nc-firefox desinstaller » pour revenir en arrière
if "$HOME/.local/bin/nc-firefox" profil >/dev/null 2>&1; then
  say "$(t "3c. Firefox : préférences et style de l'île dans ton profil (facultatif)" "3c. Firefox: preferences and island style in your profile (optional)")"
  if "$HOME/.local/bin/nc-firefox" etat >/dev/null 2>&1; then
    ok "$(t "Déjà en place." "Already set up.")"
  elif ask "$(t "Installer la config Firefox (user.js, userChrome.css ; Firefox à relancer ; nc-firefox desinstaller l'enlève) ?" "Install the Firefox config (user.js, userChrome.css; restart Firefox; nc-firefox uninstall removes it)?")" n; then
    "$HOME/.local/bin/nc-firefox" installer || warn "$(t "Config Firefox non installée." "Firefox config not installed.")"
  fi
fi

# ── 4. Services de la session ────────────────────────────────────────────────
say "$(t "4. Services de ta session" "4. Your session's services")"
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
    info "$(t "Ton ancienne config démarre encore : ${barres[*]} ${demarrages[*]##*/}" "Your old config still starts: ${barres[*]} ${demarrages[*]##*/}")"
    if ask "$(t "Les désactiver (la barre de Noctalia et l'île les remplacent ; rien n'est désinstallé) ?" "Disable them (Noctalia's bar and the island replace them; nothing is uninstalled)?")" o; then
      # mask, pas disable : sur Debian, waybar.service est activé pour tous les utilisateurs et reviendrait
      for b in "${barres[@]}"; do systemctl --user stop "$b.service" >/dev/null 2>&1; systemctl --user mask "$b.service" >/dev/null 2>&1 || true; done
      mkdir -p "$HOME/.config/autostart"
      for f in "${demarrages[@]}"; do
        n="$HOME/.config/autostart/$(basename "$f")"
        if [ "$f" = "$n" ]; then backup ".config/autostart/$(basename "$f")"; else cp "$f" "$n"; echo ".config/autostart/$(basename "$f")" >> "$BK/.created"; fi
        printf '\nHidden=true\n' >> "$n"
      done
      for b in waybar hyprpanel eww polybar; do pkill -x "$b" 2>/dev/null || true; done
      ok "$(t "Ancienne barre désactivée." "Old bar disabled.")"
    fi
  fi
  # Démons de notifications lancés à la demande (dunst, mako, swaync) : ils prendraient la place de l'île ou de Noctalia
  for d in dunst mako swaync; do
    if [ -n "$(systemctl --user list-unit-files "$d.service" --no-legend 2>/dev/null)" ] && ! systemctl --user is-enabled "$d.service" 2>/dev/null | grep -x masked >/dev/null; then
      systemctl --user mask --now "$d.service" >/dev/null 2>&1 && info "$(t "$d (notifications) désactivé : les notifications passent par $([ "$ILE" = quickshell ] && echo "l'île" || echo "Noctalia")." "$d (notifications) disabled: notifications go through $([ "$ILE" = quickshell ] && echo "the island" || echo "Noctalia").")"
    fi
  done
  systemctl --user enable --now nc-theme-sync.path nc-carousel-thumbs.path nc-maj-verif.timer nc-paquets.timer nc-alertes.timer hypridle.service >/dev/null 2>&1 ||
    warn "$(t "Certains services n'ont pas pu démarrer maintenant : ils démarreront à la prochaine session." "Some services couldn't start now: they'll start in your next session.")"
  "$HOME/.local/bin/nc-theme-sync" >/dev/null 2>&1 || true
  # Première installation : quelques choix, tout de suite (tout se change ensuite avec nc-reglages)
  if [ "$PREMIERE" = 1 ]; then
    R="$HOME/.local/bin/nc-reglages"
    say "$(t "Quelques choix pour commencer (modifiables ensuite : nc-reglages)" "A few choices to start with (you can change them later: nc-settings)")"
    choisir "$(t "Style du bureau :" "Desktop style:")" "$(t "noctalia-config : les couleurs de ton fond d'écran" "noctalia-config: your wallpaper's colors")" "$(t "Apple : façon macOS et iPhone" "Apple: macOS and iPhone style")" \
      "$(t "Noir pur (écran OLED)" "Pure black (OLED display)")" "Nord" "Catppuccin"
    case "$CHOIX" in 2) "$R" set STYLE apple ;; 3) "$R" set STYLE oled ;; 4) "$R" set STYLE nord ;; 5) "$R" set STYLE catppuccin ;; esac >/dev/null 2>&1
    ask "$(t "Thème sombre ?" "Dark theme?")" o || "$R" set THEME_MODE light >/dev/null 2>&1
    ask "$(t "Changer de fond d'écran tout seul toutes les 10 minutes ?" "Change the wallpaper automatically every 10 minutes?")" o || "$R" set FONDS_ROTATION non >/dev/null 2>&1
    ask "$(t "Couper les notifications la nuit (22 h à 7 h) ?" "Silence notifications at night (10 PM to 7 AM)?")" n && "$R" set NPD_NUIT oui >/dev/null 2>&1
    if [ "$LAPTOP" = 1 ]; then
      choisir "$(t "Couvercle fermé :" "Lid closed:")" "$(t "Mise en veille" "Sleep")" "$(t "L'écran s'éteint, le PC continue (téléchargements, musique…)" "The screen turns off, the PC keeps running (downloads, music…)")"
      [ "$CHOIX" = 2 ] && "$R" set COUVERCLE ecran >/dev/null 2>&1
    fi
    choisir "$(t "Un appui sur le bouton d'arrêt :" "Pressing the power button:")" "$(t "Une petite surprise (des doigts partout)" "A little surprise (fingers everywhere)")" "$(t "Des confettis" "Confetti")" \
      "$(t "Le menu Éteindre / Redémarrer / Veille" "The Shut Down / Restart / Sleep menu")" "$(t "Éteindre, comme d'habitude" "Shut down, as usual")"
    case "$CHOIX" in 2) "$R" set BOUTON_ARRET confettis ;; 3) "$R" set BOUTON_ARRET menu ;; 4) "$R" set BOUTON_ARRET eteindre ;; esac >/dev/null 2>&1
    ok "$(t "C'est noté." "Got it.")"
  fi
  # Tes réglages (nc-reglages) : ~/.config/nc/reglages.conf n'est jamais touché ; ce qui en est tiré (veille, terminal)
  # est refait d'après la nouvelle version de la config
  "$HOME/.local/bin/nc-reglages" appliquer >/dev/null 2>&1 || true
  "$HOME/.local/bin/nc-verrou-place" >/dev/null 2>&1 || true     # écran de verrouillage centré sur l'écran réel
  # Portails choisis pour Hyprland (~/.config/xdg-desktop-portal) : pris en compte tout de suite
  systemctl --user try-restart xdg-desktop-portal.service >/dev/null 2>&1 || true
  # Claude Code dans l'île (comme l'appli coucou) : ses étapes, sa fin, ses demandes ; hooks dans ~/.claude/settings.json
  if [ "$ILE" = quickshell ] && { have claude || [ -d "$HOME/.claude" ]; } &&
     ! grep -q "nc-claude hook" "$HOME/.claude/settings.json" 2>/dev/null &&
     ! grep -qx 'CLAUDE_ILE=non' "$HOME/.config/nc/reglages.conf" 2>/dev/null; then
    info "$(t "Claude Code est installé : l'île peut montrer ce qu'il fait et répondre à ses demandes (comme l'appli coucou)." "Claude Code is installed: the island can show what it's doing and answer its requests (like the coucou app).")"
    if ask "$(t "L'afficher dans l'île ?" "Show it in the island?")" o; then "$HOME/.local/bin/nc-claude" installer | head -1
    else printf 'CLAUDE_ILE=non\n' >> "$HOME/.config/nc/reglages.conf"; fi
  fi
  # Les autres IA (Antigravity, opencode, Codex, Gemini CLI, Cursor, Copilot, Qwen, Kiro, Amp) : déjà branchées, remises
  # au format du jour sans rien demander ; nouvelles (installées, pas refusées), une seule question pour toutes
  if [ "$ILE" = quickshell ]; then
    "$HOME/.local/bin/nc-claude" actualiser >/dev/null 2>&1 || true
    ias="$("$HOME/.local/bin/nc-claude" detecter 2>/dev/null || true)"
    if [ -n "$ias" ]; then
      info "$(t "IA installées : $ias. L'île peut montrer ce qu'elles font, quand elles ont fini, et te laisser leur écrire." "AI tools installed: $ias. The island can show what they're doing and when they're done, and let you write to them.")"
      if ask "$(t "Les afficher dans l'île ?" "Show them in the island?")" o; then
        for ia in $ias; do "$HOME/.local/bin/nc-claude" installer "$ia" | head -1; done
        case " $ias " in *" codex "*) info "$(t "Codex : ouvre-le et tape /hooks une fois pour approuver ses nouveaux hooks." "Codex: open it and type /hooks once to approve its new hooks.")" ;; esac
      else
        for ia in $ias; do printf '%s_ILE=non\n' "$(printf %s "$ia" | tr a-z A-Z)" >> "$HOME/.config/nc/reglages.conf"; done
      fi
    fi
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
  ok "$(t "Services activés." "Services enabled.")"
  if ! systemctl --user is-active --quiet graphical-session.target 2>/dev/null; then
    info "$(t "Pour que la barre démarre à l'ouverture de session, choisis la session « Hyprland (uwsm-managed) » sur l'écran de connexion." "For the bar to start when you log in, pick the “Hyprland (uwsm-managed)” session on the login screen.")"
  fi
else
  warn "$(t "Pas de session utilisateur active (installation depuis un terminal de connexion ou SSH ?) : services non activés." "No active user session (installing from a login console or over SSH?): services not enabled.")"
  info "$(t "Dans ta session Hyprland, lance :" "In your Hyprland session, run:") systemctl --user enable --now noctalia.service nc-theme-sync.path nc-carousel-thumbs.path nc-profile-sync.service nc-pouls.service nc-ecran-externe.service nc-couvercle.service hypridle.service$([ "$ILE" = quickshell ] && echo " nc-ile.service")"
fi

# Assistant distant : mêmes fichiers et dépendances sur toutes les distributions, même sans Quickshell/systemd.
# Pas de configuration automatique sans terminal, ni de remplacement d'une connexion existante lors de nc-maj.
if [ -e "$HOME/.config/nc/assistant.conf" ]; then
  ok "$(t "Configuration de l'assistant distant préservée." "Remote assistant configuration preserved.")"
elif { true </dev/tty; } 2>/dev/null && ask "$(t "Connecter un assistant distant (serveur déjà installé) ?" "Connect a remote assistant (server already installed)?")" n; then
  if "$HOME/.local/bin/nc-assistant" configurer </dev/tty; then
    if ask "$(t "L'utiliser pour les questions du Spotlight ?" "Use it for Spotlight questions?")" n; then
      "$HOME/.local/bin/nc-reglages" set SPOTLIGHT_IA assistant
    fi
  else
    warn "$(t "Connexion non configurée ; tu pourras lancer nc-assistant configurer plus tard." "Connection not configured; run nc-assistant configurer later.")"
  fi
fi

# ── 5. Étapes système (une question par étape) ───────────────────────────────
info "$(t "JARVIS facultatif : nc-jarvis tableau ; déploiement local/serveur dans le cockpit ou nc-settings → Agents IA." "Optional JARVIS: nc-jarvis tableau; local/server deployment in the dashboard or nc-settings → AI agents.")"
if [ "$MODE" = full ]; then
  SBK="$BK/system"
  sbackup() { sudo mkdir -p "$SBK"; local f; for f in "$@"; do [ -e "$f" ] && sudo cp -a --parents "$f" "$SBK/"; done; sudo chown -R "$(id -u):$(id -g)" "$SBK"; }

  # 5a. Énergie : 3 profils pour tous les PC, via un service compatible power-profiles-daemon (barre, Super + Alt + P).
  # Portable : TLP + tlp-pd avec les réglages du dépôt (mêmes profils partout) quand la distribution les propose
  # (Arch, Fedora 44+, Debian 13 via trixie-backports, openSUSE Tumbleweed) ; sinon le service de la distribution.
  say "$(t "5a. Énergie : 3 profils (Performance / Équilibré / Économie)" "5a. Power: 3 profiles (Performance / Balanced / Power Saver)")"
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
      info "$(t "Ta batterie accepte une limite de charge (environ 80 %), qui la préserve si le PC reste souvent branché." "Your battery supports a charge limit (about 80%), which preserves it if the PC is often plugged in.")"
      if ask "$(t "Activer cette limite de charge ?" "Enable this charge limit?")" o; then
        printf '%s\n' "$BATLIM" | sudo install -Dm0644 /dev/stdin /etc/tlp.d/20-battery-limit.conf; ch=0
      fi
    fi
    return $ch
  }
  if [ "$ppd" = tlp-pd ]; then
    if tlp_regle; then sudo tlp start >/dev/null && ok "$(t "Réglages TLP mis à jour (/etc/tlp.d/10-nc.conf)." "TLP settings updated (/etc/tlp.d/10-nc.conf).")"
    elif [ -n "$TLP_PERSO" ] && [ ! -f /etc/tlp.d/10-nc.conf ]; then ok "$(t "Déjà en place (TLP avec tes propres réglages : $(echo $TLP_PERSO | xargs -n1 basename | paste -sd' '), gardés)." "Already set up (TLP with your own settings: $(echo $TLP_PERSO | xargs -n1 basename | paste -sd' '), kept).")"
    else ok "$(t "Déjà en place (TLP et tlp-pd)." "Already set up (TLP and tlp-pd).")"; fi
  elif [ "$LAPTOP" = 1 ] && tlp_dispo; then
    info "$(t "Portable : TLP et tlp-pd, avec des réglages valables pour tout portable (processeur, turbo, carte PCIe, plateforme)." "Laptop: TLP and tlp-pd, with settings that suit any laptop (processor, turbo, PCIe card, platform).")"
    [ -n "$ppd" ] && info "$(t "Ils remplacent $ppd (même fonctionnement depuis la barre)." "They replace $ppd (works the same from the bar).")"
    if ask "$(t "Installer ces profils énergétiques ?" "Install these power profiles?")" o; then
      sbackup /etc/tlp.conf /etc/tlp.d
      for u in auto-cpufreq tuned tuned-ppd power-profiles-daemon; do
        if systemctl is-enabled --quiet "$u.service" 2>/dev/null; then
          info "$(t "$u entre en conflit avec TLP : il est désactivé (le paquet reste installé, sauf conflit de paquets)." "$u conflicts with TLP: it's disabled (the package stays installed, unless the packages conflict).")"
          sudo systemctl disable --now "$u.service" >/dev/null 2>&1 || true
        fi
      done
      inst=1
      case "$FAMILY" in
        arch)
          pkg_installed power-profiles-daemon && info "$(t "pacman va proposer de remplacer power-profiles-daemon : réponds oui." "pacman will offer to replace power-profiles-daemon: answer yes.")"
          sudo pacman -S --needed tlp tlp-pd || inst=0 ;;
        fedora) sudo dnf install -y --allowerasing tlp tlp-pd || inst=0 ;;
        debian) if [ "$OSCODE" = trixie ]; then bpo_install tlp tlp-pd || inst=0; else pkg_install tlp tlp-pd || inst=0; fi ;;
        suse) sudo zypper --non-interactive install --force-resolution tlp tlp-pd || inst=0 ;;
      esac
      if [ "$inst" = 1 ]; then
        tlp_regle || true
        sudo systemctl enable --now tlp.service tlp-pd.service >/dev/null
        sudo tlp start >/dev/null && ok "$(t "TLP actif (profil Équilibré par défaut)." "TLP active (Balanced profile by default).")"
      else
        warn "$(t "Installation de TLP impossible : $([ -n "$ppd" ] && echo "$ppd reste en place" || echo "profils non disponibles")." "Couldn't install TLP: $([ -n "$ppd" ] && echo "$ppd stays in place" || echo "profiles unavailable").")"
        if [ "$ppd" = tuned-ppd ]; then sudo systemctl enable --now tuned.service >/dev/null 2>&1 || true; fi   # tuned-ppd s'appuie sur tuned
        [ -n "$ppd" ] && sudo systemctl enable --now "$ppd.service" >/dev/null 2>&1
      fi
    fi
  elif [ -n "$ppd" ]; then
    ok "$(t "Déjà en place (service $ppd)." "Already set up ($ppd service).")"
  else
    svc=power-profiles-daemon
    [ "$FAMILY" = fedora ] && svc=tuned-ppd   # service de profils par défaut de Fedora
    info "$(t "Installe $svc (profils fournis par ta distribution)." "Will install $svc (profiles provided by your distribution).")"
    if ask "$(t "Installer les profils énergétiques ?" "Install the power profiles?")" o; then
      if pkg_install "$svc" && { [ "$svc" != tuned-ppd ] || sudo systemctl enable --now tuned.service; } && sudo systemctl enable --now "$svc.service"; then
        ok "$(t "Profils actifs." "Profiles active.")"
      else
        warn "$(t "Installation de $svc impossible : les profils ne seront pas disponibles." "Couldn't install $svc: profiles won't be available.")"
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
      ok "$(t "Interrupteur de protection de la batterie (île) : déjà en place." "Battery protection switch (island): already set up.")"
    else
      info "$(t "Interrupteur « Protéger la batterie » dans la page Système de l'île (charge arrêtée vers 80 %) : un petit" "“Protect Battery” switch on the island's System page (charging stops around 80%): a small")"
      info "$(t "utilitaire qui ne fait que ça (/usr/local/bin/nc-limite-charge), lancé depuis l'île sans mot de passe." "tool that does only that (/usr/local/bin/nc-limite-charge), run from the island without a password.")"
      if ask "$(t "L'installer ?" "Install it?")" o; then
        t="$(mktemp)"; printf '# noctalia-config : interrupteur « Protéger la batterie » de l'"'"'île\n%s\n' "$ligne" > "$t"
        if sudo install -Dm0755 -o root -g root "$REPO/system/nc-limite-charge" /usr/local/bin/nc-limite-charge &&
           sudo visudo -cf "$t" >/dev/null && sudo install -m0440 -o root -g root "$t" "$regle"; then
          ok "$(t "Interrupteur de protection de la batterie installé." "Battery protection switch installed.")"
        else
          warn "$(t "Installation de l'interrupteur de batterie impossible (règle sudo refusée par visudo)." "Couldn't install the battery switch (sudo rule rejected by visudo).")"
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
    ok "$(t "Bouton d'arrêt (les doigts) : déjà en place." "Power button (the fingers): already set up.")"
  elif ask "$(t "Bouton d'arrêt : un appui fait apparaître des doigts au lieu d'éteindre (le garder appuyé éteint) ?" "Power button: a press shows fingers instead of shutting down (holding it still shuts down)?")" o; then
    if printf '%s\n' "$contenu" | sudo install -Dm0644 /dev/stdin "$bouton"; then
      sudo rm -f /etc/systemd/logind.conf.d/50-legion-powerkey.conf
      # Relecture de la config par logind sans le redémarrer (un redémarrage fermerait la session)
      sudo systemctl kill -s HUP systemd-logind >/dev/null 2>&1 || true
      ok "$(t "Bouton d'arrêt : les doigts à chaque appui." "Power button: fingers on every press.")"
    else
      warn "$(t "Réglage du bouton d'arrêt impossible." "Couldn't set up the power button.")"
    fi
  fi

  if [ "$FAMILY" = arch ] && [ -f /etc/conf.d/wireless-regdom ]; then
    say "$(t "5b. Wi-Fi : pays de réglementation" "5b. Wi-Fi: regulatory country")"
    cc="$(sed -nE 's/^WIRELESS_REGDOM="?([A-Z]{2})"?.*/\1/p' /etc/conf.d/wireless-regdom | tail -1)"
  fi
  if [ "$FAMILY" = arch ] && [ -n "${cc:-}" ]; then
    ok "$(t "Déjà réglé (pays : $cc)." "Already set (country: $cc).")"
  elif [ "$FAMILY" = arch ] && [ -f /etc/conf.d/wireless-regdom ]; then
    info "$(t "Sans pays, le Wi-Fi reste bridé (canaux et puissance au minimum mondial)." "Without a country, Wi-Fi stays restricted (channels and power at the worldwide minimum).")"
    if ask "$(t "Régler le pays du Wi-Fi ?" "Set the Wi-Fi country?")" o; then
      dflt="$(echo "${LANG:-fr_FR}" | sed -nE 's/^[a-z]+_([A-Z]{2}).*/\1/p')"; dflt="${dflt:-FR}"
      cc=""
      { true </dev/tty; } 2>/dev/null && { read -r -p "$(t "   Code du pays (2 lettres) [$dflt] " "   Country code (2 letters) [$dflt] ")" cc </dev/tty || cc=""; }
      cc="$(echo "${cc:-$dflt}" | tr '[:lower:]' '[:upper:]')"
      if [[ "$cc" =~ ^[A-Z]{2}$ ]]; then
        sbackup /etc/conf.d/wireless-regdom
        sudo pacman -S --needed wireless-regdb
        sudo sed -i -E 's/^WIRELESS_REGDOM=/#&/' /etc/conf.d/wireless-regdom
        echo "WIRELESS_REGDOM=\"$cc\"" | sudo tee -a /etc/conf.d/wireless-regdom >/dev/null
        have iw && sudo iw reg set "$cc" || true
        ok "$(t "Pays du Wi-Fi : $cc" "Wi-Fi country: $cc")"
      else
        warn "$(t "Code invalide : étape ignorée." "Invalid code: step skipped.")"
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
    # Attente du menu : 5 s ou plus par défaut, raccourcie (3 s avec un autre système à côté pour avoir le temps de
    # choisir, 1 s sinon) ; une attente que tu as déjà réglée plus courte n'est pas touchée
    if grep -qE '^GRUB_TIMEOUT=([5-9]|[1-9][0-9]+)\s*$' /etc/default/grub; then
      if grep -qiE "menuentry '[^']*(windows|\((on|sur) /dev)" "$GRUBDIR/grub.cfg" 2>/dev/null ||
         { have os-prober && sudo os-prober 2>/dev/null | grep -q .; }; then t=3; else t=1; fi
      sudo sed -i -E "s/^GRUB_TIMEOUT=.*/GRUB_TIMEOUT=$t/" /etc/default/grub
    fi
    # Fedora : sortie texte par défaut (GRUB_TERMINAL_OUTPUT="console"), qui ignore le thème : sortie graphique
    if grep -qE '^GRUB_TERMINAL_OUTPUT="?console"?\s*$' /etc/default/grub; then
      sudo sed -i -E 's/^GRUB_TERMINAL_OUTPUT=.*/GRUB_TERMINAL_OUTPUT="gfxterm"/' /etc/default/grub
    fi
    sudo "$GRUBMK" -o "$GRUBDIR/grub.cfg" && ok "$(t "Thème GRUB installé (visible au prochain redémarrage)." "GRUB theme installed (visible at the next restart).")"
    if have restorecon; then sudo restorecon -RF "$GRUBDIR/themes/nc" >/dev/null 2>&1 || true; fi   # SELinux (Fedora)
    if grep -qE '^GRUB_TIMEOUT_STYLE=hidden' /etc/default/grub ||
       { have grub2-editenv && sudo grub2-editenv - list 2>/dev/null | grep -q '^menu_auto_hide=1'; }; then
      info "$(t "Le menu GRUB est masqué sur ta distribution : maintiens Maj (ou Échap, F8) au démarrage pour le voir." "The GRUB menu is hidden on your distribution: hold Shift (or Esc, F8) at boot to see it.")"
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
      ! grep -qE '^GRUB_TERMINAL_OUTPUT="?console"?\s*$' /etc/default/grub &&
      ! grep -qE '^GRUB_TIMEOUT=([5-9]|[1-9][0-9]+)\s*$' /etc/default/grub || grub_done=0
  fi
  if [ "$plym_done" = 1 ] && [ "$grub_done" = 1 ]; then
    say "$(t "5c. Démarrage" "5c. Boot")"
    ok "$(t "Déjà en place (logo animé$([ -n "$GRUBDIR" ] && echo ", thème GRUB « nc »"))." "Already set up (animated logo$([ -n "$GRUBDIR" ] && echo ", “nc” GRUB theme")).")"
  elif [ "$plym_done" = 1 ]; then
    say "$(t "5c. Démarrage : thème GRUB « nc » (« $BOOT_TITLE »)" "5c. Boot: “nc” GRUB theme (“$BOOT_TITLE”)")"
    info "$(t "Le logo animé est déjà en place ; seul le thème GRUB est à installer ou à mettre à jour." "The animated logo is already set up; only the GRUB theme needs installing or updating.")"
    if ask "$(t "Mettre à jour le thème GRUB ?" "Update the GRUB theme?")" o; then
      sbackup /etc/default/grub
      grub_nc
    fi
  elif [ -n "$INITRD" ]; then
    say "$(t "5c. Démarrage : logo animé (Plymouth)$([ -n "$GRUBDIR" ] && echo " + thème GRUB « nc » (« $BOOT_TITLE »)")" "5c. Boot: animated logo (Plymouth)$([ -n "$GRUBDIR" ] && echo " + “nc” GRUB theme (“$BOOT_TITLE”)")")"
    warn "$(t "Cette étape modifie le démarrage (initramfs$([ -n "$GRUBDIR" ] && echo ", GRUB")). Tout est sauvegardé avant." "This step changes the boot (initramfs$([ -n "$GRUBDIR" ] && echo ", GRUB")). Everything is backed up first.")"
    info "$(t "Secours si l'écran reste noir au démarrage : dans GRUB, touche « e », retirer « splash », Ctrl+X." "If the screen stays black at boot: in GRUB, press “e”, remove “splash”, then Ctrl+X.")"
    if ask "$(t "Installer l'écran de démarrage ?" "Install the boot screen?")" n; then
      sbackup /etc/default/grub /etc/mkinitcpio.conf /etc/plymouth /etc/kernel/cmdline
      pkg_installed plymouth || pkg_install plymouth || warn "$(t "Plymouth n'a pas pu être installé." "Plymouth couldn't be installed.")"
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
          ok "$(t "Plymouth installé (thème $theme)." "Plymouth installed ($theme theme).")"
          # Option « splash » du noyau (Fedora utilise « rhgb », déjà présente)
          if [ -n "$GRUBDIR" ]; then
            grub_nc
          elif [ -f /etc/kernel/cmdline ]; then
            grep -qwE 'splash|rhgb' /etc/kernel/cmdline || sudo sed -i '1 s/$/ splash/' /etc/kernel/cmdline
            info "$(t "Option « splash » ajoutée à /etc/kernel/cmdline : elle s'appliquera à la prochaine mise à jour du noyau." "“splash” option added to /etc/kernel/cmdline: it will apply at the next kernel update.")"
          else
            info "$(t "Ajoute « quiet splash » aux options du noyau de ton chargeur de démarrage pour voir le logo animé." "Add “quiet splash” to your boot loader's kernel options to see the animated logo.")"
          fi
        else
          warn "$(t "La régénération de l'initramfs a échoué : le démarrage n'a pas été modifié davantage. Sauvegarde : $SBK" "Rebuilding the initramfs failed: the boot wasn't changed any further. Backup: $SBK")"
        fi
      fi
    fi
  fi

  # 5d. Écran de connexion SDDM (thème de base : sddm-astronaut-theme)
  if have sddm; then
    say "$(t "5d. Écran de connexion SDDM « nc »" "5d. “nc” SDDM login screen")"
    T=/usr/share/sddm/themes/sddm-astronaut-theme
    sed -e "s|@SCREEN_W@|$PXW|g" -e "s|@SCREEN_H@|$PXH|g" -e "s|@LOCALE@|$LOCALE|g" "$REPO/system/sddm/nc.conf" > "$tmp"
    sddm_done() {
      [ -d "$T" ] && cmp -s "$tmp" "$T/Themes/nc.conf" && cmp -s "$REPO/system/sddm/nc.jpg" "$T/Backgrounds/nc.jpg" &&
        grep -q '^ConfigFile=Themes/nc.conf' "$T/metadata.desktop" 2>/dev/null && ! grep -q 'Screen\.ScreenWidth' "$T/Main.qml" &&
        grep -q '^Current=sddm-astronaut-theme' /etc/sddm.conf.d/theme.conf 2>/dev/null
    }
    if sddm_done; then
      ok "$(t "Déjà en place." "Already set up.")"
    elif [ ! -d "$T" ]; then
      info "$(t "Il s'appuie sur le thème libre sddm-astronaut-theme, absent : https://github.com/Keyitdev/sddm-astronaut-theme" "It builds on the free sddm-astronaut-theme, which is missing: https://github.com/Keyitdev/sddm-astronaut-theme")"
      if ask "$(t "Le télécharger (et ses modules Qt) ?" "Download it (and its Qt modules)?")" o; then
        case "$FAMILY" in
          arch) pkg_try qt6-svg qt6-virtualkeyboard qt6-multimedia-ffmpeg ;;
          fedora) pkg_try qt6-qtsvg qt6-qtvirtualkeyboard qt6-qtmultimedia ;;
          debian) pkg_try qml6-module-qtquick-virtualkeyboard qml6-module-qtmultimedia libqt6svg6 ;;
          suse) pkg_try qt6-svg-imports qt6-virtualkeyboard-imports qt6-multimedia-imports ;;
        esac
        sudo git clone -q --depth 1 https://github.com/Keyitdev/sddm-astronaut-theme.git "$T" || warn "$(t "Téléchargement impossible." "Download failed.")"
      fi
    fi
    if [ -d "$T" ] && ! sddm_done && ask "$(t "Installer l'écran de connexion ?" "Install the login screen?")" o; then
      sbackup "$T/metadata.desktop" /etc/sddm.conf.d/theme.conf
      sudo install -Dm0644 "$tmp" "$T/Themes/nc.conf"
      sudo install -Dm0644 "$REPO/system/sddm/nc.jpg" "$T/Backgrounds/nc.jpg"
      sudo rm -f "$T/Themes/legion.conf" "$T/Backgrounds/legion.jpg"
      sudo sed -i 's#^ConfigFile=.*#ConfigFile=Themes/nc.conf#' "$T/metadata.desktop"
      # Erreur du thème : sans taille dans la config, la largeur de l'écran n'était pas lue (Screen.ScreenWidth)
      sudo sed -i 's/Screen\.ScreenWidth/Screen.width/' "$T/Main.qml"
      printf '[Theme]\nCurrent=sddm-astronaut-theme\n' | sudo install -Dm0644 /dev/stdin /etc/sddm.conf.d/theme.conf
      ok "$(t "Écran de connexion installé." "Login screen installed.")"
      systemctl is-enabled --quiet sddm.service 2>/dev/null ||
        info "$(t "SDDM n'est pas ton écran de connexion actif : pour l'utiliser, « sudo systemctl enable sddm » (désactive l'autre avant)." "SDDM isn't your active login screen: to use it, “sudo systemctl enable sddm” (disable the other one first).")"
    fi
  fi

  # 5d bis. Wi-Fi sans mise en veille entre deux paquets (NetworkManager ; TLP le fait aussi, 10-nc.conf) : sinon,
  # sur beaucoup de cartes, ce qui arrive est retardé (messages en retard, voix des autres coupée en appel)
  if have nmcli && [ -d /etc/NetworkManager ] && ! cmp -s "$REPO/system/networkmanager/nc-wifi-sans-veille.conf" \
       /etc/NetworkManager/conf.d/nc-wifi-sans-veille.conf; then
    say "$(t "5d bis. Wi-Fi réactif" "5d bis. Responsive Wi-Fi")"
    sudo install -Dm0644 "$REPO/system/networkmanager/nc-wifi-sans-veille.conf" /etc/NetworkManager/conf.d/nc-wifi-sans-veille.conf &&
      sudo nmcli general reload conf >/dev/null 2>&1 || true
    if have iw; then
      for i in /sys/class/net/wl*; do
        [ -e "$i" ] || continue
        sudo iw dev "${i##*/}" set power_save off 2>/dev/null || true
      done
    fi
    ok "$(t "Wi-Fi sans mise en veille entre deux paquets (pris en compte tout de suite)." "Wi-Fi no longer dozes between packets (applied right away).")"
  fi

  # 5e. Pilote NVIDIA : sans lui, la carte tourne avec « nouveau » (pas d'accélération correcte, pas de mise en veille fine).
  # Cartes récentes (RTX 50, « Blackwell ») : pilote 570.169 ou plus, en version « open » (modules ouverts de NVIDIA).
  if [ "$NVIDIA" = 1 ]; then
    say "$(t "5e. Carte NVIDIA" "5e. NVIDIA card")"
    nvdev="$(for d in /sys/bus/pci/devices/*; do [ "$(cat "$d/vendor" 2>/dev/null)" = 0x10de ] && [[ $(cat "$d/class" 2>/dev/null) == 0x03* ]] && cat "$d/device"; done | head -1 || true)"
    BLACKWELL=0; [ -n "$nvdev" ] && [ $((nvdev)) -ge $((0x2b00)) ] && BLACKWELL=1
    drv="$(modinfo -F version nvidia 2>/dev/null || true)"
    if [ -n "$drv" ] && { [ "$BLACKWELL" = 0 ] || ver_ge "$drv" 570.169; }; then
      ok "$(t "Pilote NVIDIA $drv installé." "NVIDIA driver $drv installed.")"
    elif [ "$FAMILY" = arch ]; then
      if [ -n "$drv" ]; then info "$(t "Pilote NVIDIA $drv trop ancien pour cette carte (570.169 ou plus)." "NVIDIA driver $drv is too old for this card (570.169 or later needed).")"; else info "$(t "Pilote NVIDIA absent : la carte tourne sans accélération correcte." "NVIDIA driver missing: the card runs without proper acceleration.")"; fi
      mapfile -t kernels < <(cat /usr/lib/modules/*/pkgbase 2>/dev/null | sort -u)
      pk=(nvidia-utils)
      if [ "${kernels[*]}" = linux ]; then pk+=(nvidia-open); else pk+=(nvidia-open-dkms); for k in "${kernels[@]}"; do pk+=("$k-headers"); done; fi
      pacman -Sl multilib >/dev/null 2>&1 && pk+=(lib32-nvidia-utils)   # jeux 32 bits (Steam)
      if ask "$(t "Installer le pilote officiel de NVIDIA (${pk[*]}) ?" "Install NVIDIA's official driver (${pk[*]})?")" o; then
        if sudo pacman -S --needed "${pk[@]}"; then ok "$(t "Pilote NVIDIA installé : redémarre le PC pour l'utiliser." "NVIDIA driver installed: restart the PC to use it.")"; else warn "$(t "Installation du pilote NVIDIA impossible." "Couldn't install the NVIDIA driver.")"; fi
      fi
    elif [ "$FAMILY" = debian ] && [ "$BLACKWELL" = 1 ]; then
      warn "$(t "Ta carte NVIDIA (série RTX 50) demande le pilote 570.169 ou plus ; Debian ne fournit que le 550, qui ne la gère pas." "Your NVIDIA card (RTX 50 series) needs driver 570.169 or later; Debian only provides 550, which doesn't support it.")"
      info "$(t "Pilote de NVIDIA pour Debian (dépôt officiel de NVIDIA, paquet nvidia-open) :" "NVIDIA driver for Debian (NVIDIA's official repository, nvidia-open package):")"
      info "  https://docs.nvidia.com/datacenter/tesla/driver-installation-guide/debian.html"
      info "$(t "En attendant, l'écran interne fonctionne avec la carte intégrée." "Meanwhile, the built-in display works with the integrated graphics.")"
    else
      info "$(t "Pilote NVIDIA ${drv:+$drv }à installer avec la méthode de ta distribution :" "NVIDIA driver ${drv:+$drv }to install with your distribution's method:")"
      case "$FAMILY" in
        fedora) if [ "$OSID" = nobara ]; then info "$(t "  Nobara : appli « Nobara Driver Manager » (pilote déjà fourni par Nobara)" "  Nobara: “Nobara Driver Manager” app (driver already provided by Nobara)")"
                else info "$(t "  RPM Fusion : https://rpmfusion.org/Howto/NVIDIA (sudo dnf install akmod-nvidia)" "  RPM Fusion: https://rpmfusion.org/Howto/NVIDIA (sudo dnf install akmod-nvidia)")"; fi ;;
        debian) info "  https://wiki.debian.org/NvidiaGraphicsDrivers" ;;
        suse) info "  https://en.opensuse.org/SDB:NVIDIA_drivers" ;;
        *) info "$(t "  documentation de ta distribution (pilote « nvidia-open » pour les cartes récentes)" "  your distribution's documentation (“nvidia-open” driver for recent cards)")" ;;
      esac
    fi
  fi

  if [ "$FAMILY" = arch ]; then
    say "$(t "5f. Entretien : nettoyage automatique du cache des paquets" "5f. Maintenance: automatic package cache cleanup")"
    if systemctl is-enabled --quiet paccache.timer 2>/dev/null; then
      ok "$(t "Déjà en place (paccache.timer)." "Already set up (paccache.timer).")"
    elif ask "$(t "Garder seulement les 2 dernières versions de chaque paquet en cache (chaque semaine) ?" "Keep only the last 2 versions of each package in the cache (weekly)?")" o; then
      pkg_installed pacman-contrib || sudo pacman -S --needed pacman-contrib
      sudo systemctl enable --now paccache.timer >/dev/null && ok "$(t "paccache.timer actif." "paccache.timer active.")"
    fi
  fi
fi

say "$(t "Terminé" "Done")"
info "$(t "Ferme puis rouvre ta session pour que tout s'applique (choisis « Hyprland (uwsm-managed) » sur l'écran de connexion)." "Log out and back in for everything to apply (pick “Hyprland (uwsm-managed)” on the login screen).")"
info "$(t "Raccourcis : Super+/ affiche la fiche · Super+R recherche · Super+W fonds d'écran · Super+Entrée terminal (liste complète : RACCOURCIS.md)." "Shortcuts: Super+/ shows the cheat sheet · Super+R search · Super+W wallpapers · Super+Enter terminal (full list: RACCOURCIS.md).")"
[ "$HYBRID" = 1 ] && info "$(t "PC hybride : lancer une appli sur la carte NVIDIA avec « nvidia-run <commande> » (Steam : nvidia-run %command%)." "Hybrid PC: run an app on the NVIDIA card with “nvidia-run <command>” (Steam: nvidia-run %command%).")"
[ -n "$(ls -A "$BK" 2>/dev/null)" ] && info "$(t "Retour arrière : ./install.sh --restore   (sauvegarde : $BK)" "Undo: ./install.sh --restore   (backup: $BK)")"
info "$(t "Mise à jour plus tard, en une commande : nc-maj" "Update later with one command: nc-update")"
info "$(t "Tes réglages (écran, fenêtres, île, veille, clavier, terminal…) : nc-reglages (gardés à chaque mise à jour)" "Your settings (display, windows, island, sleep, keyboard, terminal…): nc-settings (kept on every update)")"
info "$(t "Un souci ? nc-diag vérifie tout et dit quoi faire (nc-diag rapport : le bilan, prêt à envoyer). Les commandes : nc-aide" "A problem? nc-diag checks everything and tells you what to do (nc-diag report: the summary, ready to send). The commands: nc-help")"
