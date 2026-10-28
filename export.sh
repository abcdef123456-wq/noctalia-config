#!/usr/bin/env bash
# export.sh : met à jour le dépôt avec la config actuelle de ce PC (à lancer sur la machine de référence).
# Ce qui est propre à la machine devient un repère que install.sh remplit sur chaque PC :
#   @HOME@  dossier personnel      @MONITOR@  écran principal      @KB_LAYOUT@ / @KB_VARIANT@ / @KB_OPTIONS@  clavier
#   @BROWSER@  navigateur par défaut      @LCX@ @LCY1@..@LCY4@  position des éléments de l'écran de verrouillage
#   @DISTRO_LOGO@  logo de la barre       @POLKIT@  agent des demandes de mot de passe
# Aucun secret n'est copié (liste blanche de fichiers). Contrôle final : rien qui ressemble à un secret.
# Dans un dossier de la liste, seuls les fichiers déjà suivis par git sont publiés ; un nouveau fichier est seulement
# signalé (NC_EXPORT_NOUVEAUX=oui le publie, sauf liste noire : jetons, clés, historiques, fichiers privés…).
# Rien n'est supprimé du dépôt : un fichier absent de ~ y reste. Pour le retirer : git rm home/<chemin>.
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
# Clone partiel (get.sh clone en --depth 1) : sans l'historique, la garde « ancienne version du dépôt » (plus bas) ne
# reconnaît rien et une installation en retard effacerait les derniers changements. Aperçu compris.
if [ "$(git -C "$REPO" rev-parse --is-shallow-repository 2>/dev/null || true)" = true ]; then
  echo "$(t "Export refusé : ce dépôt est un clone partiel (sans son historique), les anciennes versions ne peuvent pas être reconnues. Lance git fetch --unshallow dans $REPO, puis relance l'export." "Export refused: this repository is a shallow clone (without its history), old versions cannot be recognised. Run git fetch --unshallow in $REPO, then export again.")" >&2
  exit 1
fi
have() { command -v "$1" >/dev/null 2>&1; }

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
  .local/share/noctalia/plugins/nc-sessions
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
  .local/bin/nc-claude-ligne
  .local/bin/nc-micro-bluetooth
  .local/bin/nc-code
  .local/bin/nc-vpn
  .local/bin/nc-assistant
  .local/bin/nc-noeud
  .local/bin/nc-bac
  .local/bin/nc-jarvis
  .local/bin/nc-dictee
  .local/bin/nc-ia
  .local/bin/nc-session
  .local/bin/nc-dock
  .local/bin/nc-panne
  .local/share/nc-jarvis/actions.json
  .local/share/nc-jarvis/deployer.py
  .local/share/nc-jarvis/verifier.py
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
  .local/bin/nc-chromium
  .local/bin/nc-navigateurs
  .local/bin/nc-logiciels
  .local/bin/nc-aide-config
  .local/bin/nc-qs-capture
  .local/bin/nc-langue
  .local/bin/nc-pid
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
  .local/bin/nc-ecran
  .local/bin/nc-ecran-externe
  .local/bin/nc-ecrans
  .local/bin/nc-couvercle
  .local/bin/nc-bt-appel
  .local/bin/nc-verrou-place
  .local/bin/nc-raccourci
  .local/bin/nc-shell
  .local/bin/nc-shell-msg
  .local/bin/nc-sysinfo
  .local/bin/nc-conso
  .local/bin/nc-term-logo
  .local/bin/nc-theme-sync
  .local/bin/nc-wallpaper-colors
  .local/bin/nc-gpu-regle
  .local/bin/nvidia-run
  .local/bin/nc-gpu-mode
  .local/bin/nc-rtx-veille
  .local/bin/nc-energie
  .local/bin/nc-energie-liste
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
  .config/nc/outils.zsh
  .config/nc/terminal.zsh
  .config/nc/lazygit.yml
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
  .config/systemd/user/nc-bt-appel.service
  .config/systemd/user/nc-maj-verif.service
  .config/systemd/user/nc-maj-verif.timer
  .config/systemd/user/nc-paquets.service
  .config/systemd/user/nc-paquets.timer
  .config/systemd/user/nc-alertes.service
  .config/systemd/user/nc-alertes.timer
  .config/systemd/user/nc-noeud.service
  .config/systemd/user/nc-panne@.service
  .config/systemd/user/nc-panne@.service.d/sans-boucle.conf
  .config/systemd/user/service.d/nc-panne.conf
  .config/systemd/user/plasma-polkit-agent.service.d/nc-apres-session.conf
  .zshrc
  .p10k.zsh
  .config/nvim
  Pictures/Wallpapers
)
# Suivis par git mais jamais pris dans ~ : le dépôt garde sa version (install.sh ne la pose que si ~ n'en a pas).
# ~/.face est ta photo de profil : jamais publiée (le dépôt a un avatar par défaut).
DEPOT_SEUL=(
  .face
)

# Le dossier personnel devient @HOME@. Échappé pour sed (un « . » ou un « + » dans le chemin n'est pas un joker), et
# borné : seulement suivi d'un « / », d'un guillemet, d'une espace ou de la fin de ligne (un HOME « …/al » ne touche pas
# « …/alice »). Un chemin resté tel quel est arrêté par le contrôle final (/home/<nom>).
home_re="$(printf '%s' "${HOME%/}" | sed 's/[][\\.*^$+?(){}|#]/\\&/g')"
normaliser_home() { # normaliser_home [options de sed] FICHIER...
  if [ -z "$home_re" ]; then sed -e '' "$@"; return; fi  # HOME=/ : rien à remplacer
  sed -E -e "s#${home_re}([/\"' ]|\$)#@HOME@\\1#g" "$@"
}

# Fichiers de démarrage du shell : des installateurs tiers y ajoutent leurs lignes (export PATH="/home/<nom>/…").
# L'export publie toujours la version du dépôt, montre l'écart et ne touche jamais au fichier de ~.
# Les variables de la session uwsm aussi : on y met ANTHROPIC_API_KEY ou OPENAI_API_KEY (seuls les noms sont montrés).
SHELL_GARDES=" .zshrc .zshenv .zprofile .zlogin .bashrc .bash_profile .profile .config/uwsm/env .config/uwsm/env-hyprland "
comparer_shell() { # comparer_shell REL BASE INSTALLE
  local rel="$1" base="$2" installe="$3" norm="$stage/shell-normalise.tmp" ecart lignes n
  if [ ! -f "$base" ]; then
    echo "$(t "non publié : ~/$rel (le dépôt n'en a pas de version gérée)" "not published: ~/$rel (no managed version in the repository)")" >&2
    return 0
  fi
  [ -f "$installe" ] || return 0
  normaliser_home -- "$installe" > "$norm"               # la normalisation habituelle des repères
  ecart="$(git --no-pager diff --no-index --no-color -U0 -- "$base" "$norm" \
           | sed -n '/^@@/,$ { /^@@/d; /^\\/d; p }' || true)"
  rm -f -- "$norm"
  [ -n "$ecart" ] || return 0
  # Jamais une valeur à l'écran (export.sh est aussi lancé par des assistants, qui gardent tout : un mot de passe ou
  # un jeton se cache n'importe où dans une ligne) : seulement le premier mot de chaque ligne, et le nom affecté.
  ecart="$(printf '%s\n' "$ecart" | python3 -I -c '
import re, sys
import shutil
MOT = re.compile(r"[A-Za-z0-9_.-]{1,40}")
CLES = {"export", "alias", "unalias", "source", ".", "if", "then", "else", "elif", "fi", "for", "while", "until",
        "do", "done", "case", "esac", "function", "local", "typeset", "declare", "readonly", "integer", "unset",
        "setopt", "unsetopt", "autoload", "bindkey", "zstyle", "zmodload", "compdef", "eval", "exec", "test", "[",
        "[[", "]]", "{", "}", "(", ")", "#", "echo", "print", "printf", "cd", "return", "path", "fpath", "PATH",
        "zle", "emulate", "builtin", "command", "hash", "trap", "umask", "ulimit", "set", "shift", "read"}
NOM = re.compile(r"(?:^|\s)([A-Za-z_][A-Za-z0-9_]*)\+?=")
for l in sys.stdin.read().splitlines():
    signe, reste = l[:1], l[1:].strip()
    mots = reste.split()
    if not mots:
        print(signe)
        continue
    nom = NOM.search(reste)
    premier = mots[0]
    if nom and nom.start(1) == reste.index(premier):
        print(f"{signe}{nom[1]}=…")
        continue
    connu = premier in CLES or (MOT.fullmatch(premier) and shutil.which(premier))
    affiche = premier if connu else "…"
    print(f"{signe}{affiche} {nom[1]}=…" if nom else f"{signe}{affiche}" + (" …" if len(mots) > 1 else ""))
')"
  mapfile -t lignes <<< "$ecart"
  n=${#lignes[@]}
  # shellcheck disable=SC2088  # « ~/ » est du texte affiché, pas un chemin à développer
  echo "$(t "~/$rel diffère du dépôt ($n lignes) : la version du dépôt est gardée, ces lignes ne sont pas publiées (~/$rel n'est pas modifié ; valeurs cachées) :" "~/$rel differs from the repository ($n lines): the repository version is kept, these lines are not published (~/$rel is not changed; values hidden):")" >&2
  printf '  %s\n' "${lignes[@]:0:12}" >&2
  [ "$n" -le 12 ] || echo "  … ($n $(t "lignes en tout" "lines in total"))" >&2
  if [ "$rel" = .zshrc ]; then
    echo "$(t "Tes ajouts vont dans ~/.zshrc.perso : le .zshrc du dépôt le charge à la fin." "Put your additions in ~/.zshrc.perso: the repository .zshrc loads it at the end.")" >&2
  else
    echo "$(t "Garde tes ajouts dans un fichier à toi, hors du dépôt." "Keep your additions in a file of your own, outside the repository.")" >&2
  fi
}

refuser() { echo "$(t "Export refusé : $1" "Export refused: $2")" >&2; }

# Un dossier installé qui est un lien vers ~, / ou un parent ferait entrer tout le dossier personnel (clés .ssh,
# jetons) dans le dépôt.
# shellcheck disable=SC2088  # « ~/ » est du texte affiché
cible_sure() { # cible_sure REL INSTALLE
  local cible c h r
  cible="$(realpath -e -- "$2")" || { refuser "$2 introuvable." "$2 not found."; return 1; }
  h="$(realpath -e -- "$HOME")" && r="$(realpath -e -- "$REPO")" || { refuser "dossier introuvable." "folder not found."; return 1; }
  c="${cible%/}"                                         # « / » devient « » : tout est dessous
  case "$h/" in "$c"/*) refuser "~/$1 mène à ton dossier personnel ou au-dessus ($cible)." "~/$1 leads to your home folder or above ($cible)."; return 1 ;; esac
  case "$r/" in "$c"/*) refuser "~/$1 mène au dépôt ou au-dessus ($cible)." "~/$1 leads to the repository or above ($cible)."; return 1 ;; esac
  # Ailleurs dans ~ : seulement un dossier du même nom (~/.config/nvim -> ~/dotfiles/nvim). ~/Pictures/Wallpapers ->
  # ~/Images ferait passer tout ~/Images pour des fonds d'écran.
  case "$c/" in
    "$h"/*) [ "${c##*/}" = "${1##*/}" ] || {
      refuser "~/$1 mène ailleurs dans ton dossier personnel ($cible), pas à un dossier « ${1##*/} ». Fais-le pointer vers un dossier « ${1##*/} », ou remplace le lien par le dossier lui-même." "~/$1 leads elsewhere in your home folder ($cible), not to a “${1##*/}” folder. Point it to a “${1##*/}” folder, or replace the link with the folder itself."
      return 1; } ;;
  esac
  return 0
}

# Fichiers suivis par git sous home/ (chemins relatifs à home/) : d'un dossier de la liste, seuls ceux-là sont publiés.
declare -A SUIVIS=()
while IFS= read -r -d '' f; do SUIVIS["${f#home/}"]=1; done < <(git -C "$REPO" ls-files -z -- home 2>/dev/null || true)
nouveaux_ecartes=0

# Pourquoi un nouveau fichier (pas encore suivi par git) n'est pas publié ; rien s'il peut l'être. La liste noire
# l'emporte sur NC_EXPORT_NOUVEAUX : jetons, clés, historiques, bases de données, fichiers lisibles par toi seul.
raison_nouveau() { # raison_nouveau FICHIER CHEMIN_DANS_~
  local f="$1" nom gps
  nom="${2##*/}"; nom="${nom,,}"
  case "/${2,,}/" in */spell/*) t "liste noire" "blocklist"; return ;; esac
  case "$nom" in
    auth.json|*.env|.netrwhist|*token*|*secret*|*.pem|*.key|id_*|*history*|*.sqlite|*.sqlite3)
      t "liste noire" "blocklist"; return ;;
  esac
  [ -e "$f" ] || { t "lien cassé" "broken link"; return; }
  # 0600 ou plus fermé : ni le groupe ni les autres n'y ont droit (un lien : son fichier)
  if [ -z "$(find -L "$f" -maxdepth 0 -perm /077 2>/dev/null)" ]; then
    t "fichier privé, lisible par toi seul" "private file, readable only by you"; return
  fi
  case "${NC_EXPORT_NOUVEAUX:-}" in
    oui|1) ;;
    *) t "pas encore dans le dépôt" "not in the repository yet"; return ;;
  esac
  # Images : la position GPS (EXIF, XMP) ne se voit pas dans le diff. Vérifiée par exiftool ; sans lui, refusée.
  case "$nom" in
    *.jpg|*.jpeg|*.png|*.webp|*.gif|*.heic|*.heif|*.avif|*.tif|*.tiff|*.bmp|*.jxl|*.dng)
      if ! have exiftool; then
        t "image : exiftool absent, la position GPS ne peut pas être vérifiée" "image: exiftool missing, the GPS position cannot be checked"; return
      fi
      gps="$(exiftool -q -q -n -s3 -GPSLatitude -GPSLongitude -GPSPosition -- "$f" 2>/dev/null)" ||
        { t "image illisible par exiftool" "image exiftool cannot read"; return; }
      [ -z "$gps" ] || { t "image avec une position GPS" "image with a GPS position"; return; } ;;
  esac
}

# Un dossier de la liste, fichier par fichier, superposé à celui du dépôt : les fichiers déjà suivis par git sont
# publiés ; un nouveau ne l'est qu'avec NC_EXPORT_NOUVEAUX=oui et hors liste noire. Un fichier suivi absent de ~
# reste tel quel dans le dépôt (rien n'est supprimé, comme pour les fichiers de la liste).
# shellcheck disable=SC2088  # « ~/ » est du texte affiché
copier_dossier() { # copier_dossier REL INSTALLE DESTINATION
  local rel="$1" installe="$2" dest="$3" f p raison
  mkdir -p -- "$dest" || return 1
  while IFS= read -r -d '' f; do
    p="${f#"$installe"/}"
    case "/$p" in */__pycache__/*|*.bak|*.tmp|*~) continue ;; esac   # jamais publiés (nettoyage, plus bas)
    if [ -z "${SUIVIS["$rel/$p"]:-}" ]; then
      raison="$(raison_nouveau "$f" "$rel/$p")"
      if [ -n "$raison" ]; then
        echo "$(t "nouveau, pas publié : ~/$rel/$p ($raison)" "new, not published: ~/$rel/$p ($raison)")" >&2
        nouveaux_ecartes=$((nouveaux_ecartes + 1))
        continue
      fi
      echo "$(t "nouveau, publié (NC_EXPORT_NOUVEAUX) : ~/$rel/$p" "new, published (NC_EXPORT_NOUVEAUX): ~/$rel/$p")" >&2
    fi
    { mkdir -p -- "$(dirname -- "$dest/$p")" && cp -a --remove-destination -- "$f" "$dest/$p"; } ||
      { refuser "copie impossible de ~/$rel/$p." "cannot copy ~/$rel/$p."; return 1; }
  done < <(find -H "$installe" -mindepth 1 ! -type d -print0)
}

# Les liens à l'intérieur d'un dossier exporté : copiés comme fichiers s'ils mènent dans ce même dossier, sinon
# refusés (Pictures/Wallpapers/perso.jpg -> /home/<nom>/… publierait le chemin, et un lien n'a rien à faire ici).
# shellcheck disable=SC2088
liens_internes() { # liens_internes REL INSTALLE DESTINATION
  local rel="$1" installe="$2" dest="$3" racine l src cible
  # Appelée avec « || return 1 » : set -e ne joue plus ici, chaque échec est donc traité à la main.
  racine="$(realpath -e -- "$installe")" || { refuser "~/$rel introuvable." "~/$rel not found."; return 1; }
  while IFS= read -r -d '' l; do
    src="$installe/${l#"$dest"/}"
    [ -L "$src" ] || continue                       # un lien venu du dépôt : vu par le contrôle final
    cible="$(realpath -e -- "$src" 2>/dev/null)" || { refuser "lien cassé ~/$rel/${l#"$dest"/}." "broken link ~/$rel/${l#"$dest"/}."; return 1; }
    if [ -d "$cible" ]; then                         # même sans boucle, il dupliquerait tout un dossier
      refuser "~/$rel/${l#"$dest"/} est un lien vers un dossier ($cible). Remplace-le par les fichiers eux-mêmes." "~/$rel/${l#"$dest"/} links to a folder ($cible). Replace it with the files themselves."
      return 1
    fi
    case "$cible/" in
      "$racine"/*)
        { rm -f -- "$l" && cp -aL -- "$src" "$l"; } || { refuser "copie impossible de ~/$rel/${l#"$dest"/}." "cannot copy ~/$rel/${l#"$dest"/}."; return 1; } ;;
      *) refuser "~/$rel/${l#"$dest"/} est un lien vers l'extérieur du dossier ($cible). Remplace-le par le fichier." "~/$rel/${l#"$dest"/} links outside the folder ($cible). Replace it with the file."; return 1 ;;
    esac
  done < <(find "$dest" -type l -print0)
}

copy_list() { # copy_list DEST_PREFIX fichier...
  local dest="$1" rel base installe; shift
  for rel in "$@"; do
    base="$REPO/home/$rel"
    installe="$HOME/$rel"
    # La base est le home/ du dépôt entier, déjà copié (composants pas encore installés sur ce PC, fichiers hors
    # de la liste) : une absence dans ~ n'est pas une demande de supprimer un fichier du dépôt.
    if [ ! -e "$installe" ]; then          # absent, ou lien cassé
      if [ -e "$base" ] || [ -L "$base" ]; then
        echo "$(t "gardé depuis le dépôt (absent de ~) : $rel" "kept from the repository (missing from ~): $rel")"
      else
        echo "$(t "absent, ignoré : ~/$rel" "missing, skipped: ~/$rel")"
      fi
      continue
    fi
    case "$SHELL_GARDES" in
      *" $rel "*) comparer_shell "$rel" "$base" "$installe"; continue ;;
    esac
    mkdir -p "$dest/$(dirname "$rel")"
    [ -L "$dest/$rel" ] && rm -f -- "$dest/$rel"   # un lien du dépôt est remplacé par ce qu'il y a dans ~
    if [ -d "$installe" ]; then
      # Un dossier, ou un lien vers un dossier (~/.config/nvim → ailleurs) : son contenu, jamais le lien lui-même
      # (sa cible contiendrait /home/<nom>). Superposé au dossier du dépôt : les fichiers ajoutés au dépôt et pas
      # encore installés (nouvelle page de l'île, par exemple) restent. Seuls les fichiers suivis par git sont pris.
      if [ -e "$dest/$rel" ] && [ ! -d "$dest/$rel" ]; then
        refuser "type incompatible pour $rel (fichier dans le dépôt, dossier dans ~)." "incompatible type for $rel (file in the repository, directory in ~)."
        return 1
      fi
      cible_sure "$rel" "$installe" || return 1
      copier_dossier "$rel" "$installe" "$dest/$rel" || return 1
      liens_internes "$rel" "$installe" "$dest/$rel" || return 1
    else
      if [ -d "$dest/$rel" ]; then
        refuser "type incompatible pour $rel (dossier dans le dépôt, fichier dans ~)." "incompatible type for $rel (directory in the repository, file in ~)."
        return 1
      fi
      cp -aL --remove-destination "$installe" "$dest/$rel"   # un lien vers un fichier : le fichier, pas le lien
    fi
  done
}

cp -a "$REPO/home" home
copy_list home "${HOME_FILES[@]}"
if [ "$nouveaux_ecartes" -gt 0 ]; then
  echo "$(t "$nouveaux_ecartes nouveau(x) fichier(s) pas publié(s). Pour publier ceux qui ne sont pas en liste noire : vérifie-les, puis relance avec NC_EXPORT_NOUVEAUX=oui." "$nouveaux_ecartes new file(s) not published. To publish those not on the blocklist: check them, then run again with NC_EXPORT_NOUVEAUX=oui.")" >&2
fi
for rel in "${DEPOT_SEUL[@]}"; do
  # shellcheck disable=SC2088  # « ~/ » est du texte affiché
  [ ! -e "$HOME/$rel" ] || echo "$(t "jamais publié : ~/$rel (le dépôt garde sa version)" "never published: ~/$rel (the repository keeps its version)")"
done

# Réglages KDE : les dialogues de fichiers y écrivent les derniers dossiers ouverts ([KFileDialog Settings], Recent
# URLs). Ces groupes, et toute clé d'historique, ne sont jamais publiés.
if [ -f home/.config/kdeglobals ] && [ ! -L home/.config/kdeglobals ]; then
  python3 -I - home/.config/kdeglobals <<'EOF'
import os, re, sys
p = sys.argv[1]
en = os.environ.get("NC_LANGUE") == "en"
HISTORIQUE = re.compile(r"recent|histor|kfiledialog", re.I)
lignes = open(p, encoding="utf-8", errors="surrogateescape").read().splitlines(keepends=True)
garde, sortie, retire = True, [], 0
for l in lignes:
    s = l.strip()
    if s.startswith("[") and s.endswith("]"):
        garde = not HISTORIQUE.search(s)
    elif garde and HISTORIQUE.match(s.split("=", 1)[0].strip()):
        retire += 1                                     # « Recent URLs[$e]=… » hors d'un groupe d'historique
        continue
    if garde:
        sortie.append(l)
    else:
        retire += 1
if retire:
    while sortie and not sortie[-1].strip():
        sortie.pop()                                    # pas de lignes vides laissées par un groupe retiré à la fin
    if sortie and not sortie[-1].endswith("\n"):
        sortie[-1] += "\n"
    open(p, "w", encoding="utf-8", errors="surrogateescape").write("".join(sortie))
    print("kdeglobals: file dialog history removed (not published)" if en
          else "kdeglobals : historique des dialogues de fichiers retiré (pas publié)", file=sys.stderr)
EOF
fi

# Nettoyage : sauvegardes temporaires, caches Python, réglages personnels (jamais publiés)
find home \( -name '*.bak' -o -name '*.tmp' -o -name '*~' -o -name '__pycache__' \) -prune -exec rm -rf {} +
rm -f home/.config/hypr/perso.lua home/.config/hypr/nc/*.tmp
# Généré par nc-profile-sync à chaque session : valeur neutre dans le dépôt
printf '%s\n' "-- Généré par nc-profile-sync à chaque changement de profil énergétique. Ne pas éditer." \
  'return { profil = "balanced", batterie = false, hz = "max" }' > home/.config/hypr/nc/profil.lua

mon=""
# Écrans : seulement dans une session Hyprland. Ailleurs hyprctl répond par un message, pas du JSON : ni lui ni jq
# ne sont utilisés (les repères des écrans sont reposés par alignement avec le dépôt, plus bas).
mons=""
if have hyprctl && have jq; then
  mons="$(hyprctl monitors -j 2>/dev/null)" || mons=""
  case "${mons#"${mons%%[![:space:]]*}"}" in "["*) ;; *) mons="" ;; esac
fi
if [ -n "$mons" ]; then
  mon="$(jq -r '([.[] | select(.name | startswith("eDP"))][0] // .[0]).name // empty' <<<"$mons" 2>/dev/null)" || mon=""
fi

while IFS= read -r -d '' f; do
  grep -Iq . "$f" || continue
  normaliser_home -i -- "$f"
done < <(find home -type f -print0)

# Repères par alignement avec le dépôt, sans rien demander à ce PC (écran, échelle, navigateur peuvent avoir changé
# depuis l'installation) : chaque ligne du dépôt à repères devient un motif où chaque repère ne vaut que les valeurs
# qu'install.sh peut lui donner (JOKERS, ci-dessous). Une ligne installée qui y correspond, à la même place,
# redevient la ligne du dépôt. Une ligne que tu as changée (plugin ajouté, appli épinglée, widget en plus) ne
# correspond plus : elle est gardée, et les sed ci-dessous y reposent les repères, comme avant.
# Le nom de l'écran (de hyprctl, ou lu dans les lignes alignées) devient @MONITOR@, et le navigateur lu de la même
# façon @BROWSER@, seulement dans les lignes qui ne sont pas déjà celles du dépôt : un exemple du dépôt (« HDMI-A-1 »
# dans un commentaire) reste tel quel quand c'est justement l'écran branché.
python3 -I - "$REPO/home" home "$mon" <<'EOF'
import difflib, re, sys
from pathlib import Path
REPERES = re.compile(r"@(MONITOR|KB_LAYOUT|KB_VARIANT|KB_OPTIONS|BROWSER|LCX|LCY[1-5]|DISTRO_LOGO|POLKIT|QT_STYLE|ICON_THEME"
                     r"|ILE_CENTRE|NOTIF_NOCTALIA|NOTIF_WIDGET|PLUGIN_ILE)@")
NOMBRE = r"[0-9]+(?:\.[0-9]+)?"                         # awk « %.1f » dans install.sh
DISPOSITION = r"[A-Za-z0-9_()-]+"
# Les valeurs exactes qu'install.sh donne à chaque repère (voir le sed de son étape de copie)
JOKERS = {
    "MONITOR": r"[A-Za-z0-9._-]+",                     # eDP-1, HDMI-A-1, DP-2…
    "KB_LAYOUT": DISPOSITION + r"(?:," + DISPOSITION + r")*",   # fr, us,fr
    "KB_VARIANT": r"[A-Za-z0-9_,-]*",                  # bepo, intl, ,bepo, ou rien
    "KB_OPTIONS": r"[A-Za-z0-9_:,-]*",                 # ctrl:nocaps,grp:win_space_toggle, ou rien
    "BROWSER": r"[A-Za-z0-9._-]+",                     # identifiant d'appli, sans « .desktop »
    "LCX": NOMBRE, "LCY1": NOMBRE, "LCY2": NOMBRE, "LCY3": NOMBRE, "LCY4": NOMBRE, "LCY5": NOMBRE,
    "DISTRO_LOGO": r"[^\",\[\]]*",                     # un chemin, ou rien
    "POLKIT": r"(?:true|false)",
    "QT_STYLE": r"(?:Breeze|Fusion)",
    "ICON_THEME": r"[A-Za-z0-9._+-]+",                 # NC
    "ILE_CENTRE": r'(?:|"nc/ile:pilule")',
    "NOTIF_NOCTALIA": r"(?:true|false)",
    "NOTIF_WIDGET": r'(?:|, "notifications")',
    "PLUGIN_ILE": r'(?:|, "nc/ile")',
}
depot, export, mon = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3]


def texte(f):
    if f.is_symlink() or not f.is_file():
        return None
    try:
        b = f.read_bytes()
    except OSError:
        return None
    if b"\0" in b[:8192]:
        return None
    try:
        return b.decode("utf-8")
    except UnicodeDecodeError:
        return None


def motif(ligne):
    morceaux = REPERES.split(ligne)                    # texte, repère, texte, repère…
    return re.compile("".join(re.escape(m) if i % 2 == 0 else f"({JOKERS[m]})" for i, m in enumerate(morceaux)))


appris = {"MONITOR": {mon} - {""}, "BROWSER": set()}  # valeurs de ce PC lues dans les lignes alignées
fichiers = []
for cible in sorted(export.rglob("*")):
    t = texte(cible)
    if t is None:
        continue
    x = t.splitlines(keepends=True)
    r = texte(depot / cible.relative_to(export))
    a = r.splitlines(keepends=True) if r is not None else []
    sortie = list(x)
    if r is not None and REPERES.search(r):
        motifs = [motif(l.rstrip("\n")) if REPERES.search(l) else None for l in a]
        for op, i1, i2, j1, j2 in difflib.SequenceMatcher(None, a, x, autojunk=False).get_opcodes():
            if op != "replace":
                continue
            i = i1
            for j in range(j1, j2):
                for k in range(i, i2):
                    m = motifs[k] and motifs[k].fullmatch(x[j].rstrip("\n"))
                    if m:
                        for nom, valeur in zip(REPERES.findall(a[k]), m.groups()):
                            if nom in appris and valeur:
                                appris[nom].add(valeur)
                        sortie[j] = a[k].rstrip("\n") + ("\n" if x[j].endswith("\n") else "")
                        i = k + 1
                        break
    fichiers.append((cible, x, a, sortie))

for cible, x, a, sortie in fichiers:
    du_depot = {l.rstrip("\n") for l in a}
    # Le navigateur, seulement dans une ligne qui commence comme une ligne du dépôt qui l'a (« pinned = [ »…)
    debuts = {l.split("@BROWSER@")[0].split('"')[0] for l in a if "@BROWSER@" in l}
    resultat = []
    for l in sortie:
        if l.rstrip("\n") not in du_depot:
            for e in sorted(appris["MONITOR"]):
                l = l.replace(f'"{e}"', '"@MONITOR@"').replace(f'@{e}"', '@@MONITOR@"')
            if any(d and l.startswith(d) for d in debuts):
                for n in sorted(appris["BROWSER"]):
                    l = l.replace(f'"{n}"', '"@BROWSER@"')
        resultat.append(l)
    if resultat != x:
        cible.write_text("".join(resultat), encoding="utf-8")
EOF

# Clavier (s'il est publié : un clavier.lua nouveau dans ~ ne l'est pas, voir copier_dossier)
[ ! -f home/.config/hypr/nc/clavier.lua ] || sed -i -E 's/^(\s*kb_layout\s*=\s*)"[^"]*"/\1"@KB_LAYOUT@"/; s/^(\s*kb_options\s*=\s*)"[^"]*"/\1"@KB_OPTIONS@"/
  s/^(\s*local disposition = nc\.reglage\("CLAVIER_DISPOSITION", )"[^"]*"\)/\1"@KB_LAYOUT@")/
  s/^(\s*if disposition == "systeme" then disposition = )"[^"]*"/\1"@KB_LAYOUT@"/
  s/^(\s*local options = )"[^"]*"/\1"@KB_OPTIONS@"/
  s/^(\s*if variante == "systeme" then variante = )"[^"]*"/\1"@KB_VARIANT@"/' home/.config/hypr/nc/clavier.lua

# Navigateur : le navigateur de ce PC devient celui de la machine cible (les favoris du dépôt sont reposés par
# l'alignement ci-dessus) ; applis personnelles retirées des favoris
sed -i -E 's/^(pinned = \[|local PINNED = \{ )"firefox-developer-edition"/\1"@BROWSER@"/; s/, "discord"//g' \
  home/.config/noctalia/config.toml home/.local/share/noctalia/plugins/nc-launcher/panel.luau

# Style Qt (Breeze s'il est installé, sinon Fusion) : choisi par install.sh
sed -i -E 's/^style=(Breeze|Fusion)$/style=@QT_STYLE@/; s/^icon_theme=.*/icon_theme=@ICON_THEME@/' home/.config/qt6ct/qt6ct.conf

# Centre de la barre : île Quickshell (vide) ou plugin nc/ile, choisi par install.sh
sed -i -E 's/^center = \[("nc\/ile:pilule")?\]/center = [@ILE_CENTRE@]/' home/.config/noctalia/config.toml
sed -i -E 's/^enable_daemon = (true|false)/enable_daemon = @NOTIF_NOCTALIA@/; s/"group:status"(, "notifications")?([],])/"group:status"@NOTIF_WIDGET@\2/; /^enabled = \[/{s/"nc\/ile", //; s/, "nc\/ile"//; s/(@PLUGIN_ILE@)?\]/@PLUGIN_ILE@]/}' home/.config/noctalia/config.toml

# Barre : logo de la distribution et agent polkit, choisis par install.sh
sed -i -E 's|^custom_image = "[^"]*"|custom_image = "@DISTRO_LOGO@"|; s|^polkit_agent = [a-z]+|polkit_agent = @POLKIT@|' home/.config/noctalia/config.toml

# Écran de verrouillage : positions de cet écran (en points) -> proportions de l'écran de la machine cible
taille=""
if [ -n "$mons" ]; then
  taille="$(jq -r --arg m "$mon" '.[] | select(.name == $m) | "\(.width / .scale) \(.height / .scale)"' <<<"$mons" 2>/dev/null)" || taille=""
fi
python3 -I - "$taille" <<'EOF'
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

# Anciennes versions : un fichier de ~ qui n'a pas reçu les derniers changements du dépôt (installation en retard)
# effacerait ces changements. Fichier par fichier, après toutes les normalisations (le dépôt garde les repères) : un
# contenu qui diffère de HEAD mais qui a déjà existé à ce chemin dans l'historique est une ancienne version du
# dépôt. Il n'est pas publié (le fichier du dépôt reste), aperçu compris ; NC_EXPORT_MALGRE_TOUT=1 le publie quand
# même (retour en arrière voulu). Juste après ton propre export, ~ et HEAD sont pareils : rien n'est bloqué.
python3 -I - "$REPO" home "${NC_EXPORT_MALGRE_TOUT:-}" <<'EOF'
import hashlib, os, shutil, subprocess, sys
from pathlib import Path
depot, export, malgre = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3] == "1"
en = os.environ.get("NC_LANGUE") == "en"


def git(*a):
    return subprocess.run(["git", "-C", str(depot), *a], capture_output=True, text=True)


r = git("ls-tree", "-r", "-z", "HEAD", "--", "home")
if r.returncode != 0:
    sys.exit(0)                                         # pas un dépôt git : rien à comparer
tete = {}
for e in filter(None, r.stdout.split("\0")):
    meta, chemin = e.split("\t", 1)
    if meta.split()[1] == "blob":
        tete[chemin] = meta.split()[2]
anciens = 0
for f in sorted(export.rglob("*")):
    if f.is_symlink() or not f.is_file():
        continue
    rel = "home/" + f.relative_to(export).as_posix()
    b = f.read_bytes()
    blob = hashlib.sha1(b"blob %d\0" % len(b) + b).hexdigest()
    if tete.get(rel) == blob:
        continue
    commits = git("log", "--format=%h", f"--find-object={blob}", "HEAD", "--", rel).stdout.split()
    if not commits:
        continue                                        # contenu nouveau : publié
    anciens += 1
    c, nom = commits[-1], rel[5:]
    if malgre:
        print(f"~/{nom} is an old repository version (commit {c}): published anyway (NC_EXPORT_MALGRE_TOUT=1)" if en
              else f"~/{nom} est une ancienne version du dépôt (commit {c}) : publié quand même (NC_EXPORT_MALGRE_TOUT=1)",
              file=sys.stderr)
        continue
    if (depot / rel).is_file():
        shutil.copy2(depot / rel, f)                    # le fichier du dépôt reste
    else:
        f.unlink()                                      # retiré du dépôt depuis : pas republié
    print(f"~/{nom} is an old repository version (commit {c}): not published; run nc-update to update" if en
          else f"~/{nom} est une ancienne version du dépôt (commit {c}) : pas publié ; nc-maj pour te mettre à jour",
          file=sys.stderr)
if anciens and not malgre:
    print("If going back is intended, run again with NC_EXPORT_MALGRE_TOUT=1." if en
          else "Si ce retour en arrière est voulu, relance avec NC_EXPORT_MALGRE_TOUT=1.", file=sys.stderr)
EOF

# Repères : chaque repère d'install.sh d'un fichier du dépôt y reste, autant de fois. Sinon un sed ne correspond plus
# au fichier (clavier.lua, réécrit avec nc.reglage) et l'export publierait la valeur de ce PC à la place du repère.
python3 -I - "$REPO/home" home <<'EOF'
import os, re, sys
from collections import Counter
from pathlib import Path
en = os.environ.get("NC_LANGUE") == "en"
REPERES = re.compile(r"@(?:MONITOR|KB_LAYOUT|KB_VARIANT|KB_OPTIONS|BROWSER|LCX|LCY[1-5]|DISTRO_LOGO|POLKIT|QT_STYLE|ICON_THEME"
                     r"|ILE_CENTRE|NOTIF_NOCTALIA|NOTIF_WIDGET|PLUGIN_ILE)@")
depot, export = Path(sys.argv[1]), Path(sys.argv[2])
def reperes(f):
    try:
        b = f.read_bytes()
    except OSError:
        return Counter()
    return Counter() if b"\0" in b[:8192] else Counter(REPERES.findall(b.decode("utf-8", "replace")))
manque = []
for f in sorted(depot.rglob("*")):
    if f.is_symlink() or not f.is_file():
        continue
    avant = reperes(f)
    if not avant:
        continue
    rel = f.relative_to(depot)
    apres = reperes(export / rel)
    perdus = {m for m, n in avant.items() if apres[m] < n}
    if not perdus:
        continue
    try:
        exportees = set((export / rel).read_text(encoding="utf-8", errors="replace").splitlines())
    except OSError:
        exportees = set()
    lignes = [(i, l) for i, l in enumerate(f.read_text(encoding="utf-8", errors="replace").splitlines(), 1)
              if perdus & set(REPERES.findall(l)) and l not in exportees]
    manque.append((rel, sorted(perdus), lignes))
if manque:
    for rel, perdus, lignes in manque:
        print((f"Export refused: home/{rel} would lose {', '.join(perdus)}: on this PC these lines changed beyond "
               f"their value, so the repository line can no longer be found:" if en else
               f"Export refusé : home/{rel} perdrait {', '.join(perdus)}. Sur ce PC, ces lignes ont changé au-delà de "
               f"leur valeur : l'export ne retrouve plus la ligne du dépôt :"), file=sys.stderr)
        for i, l in lignes:
            print(f"  {'line' if en else 'ligne'} {i} : {l.strip()}", file=sys.stderr)
        print((f"  What to do: in ~/{rel}, write these lines again as in the repository (with your value), or first "
               f"change them in the repository, then export again." if en else
               f"  Que faire : dans ~/{rel}, remets ces lignes comme dans le dépôt (avec ta valeur), ou modifie-les "
               f"d'abord dans le dépôt, puis relance l'export."), file=sys.stderr)
    sys.exit(1)
EOF

# Rien de perdu : chaque fichier suivi sous home/ est encore là (la liste HOME_FILES ne couvre pas tout)
perdus=""
while IFS= read -r -d '' f; do
  [ -e "$f" ] || [ -L "$f" ] || perdus="$perdus  $f"$'\n'
done < <(git -C "$REPO" ls-files -z -- home 2>/dev/null || true)
if [ -n "$perdus" ]; then
  echo "$(t "Export refusé : ces fichiers du dépôt disparaîtraient :" "Export refused: these repository files would disappear:")" >&2
  printf '%s' "$perdus" >&2
  exit 1
fi

# Contrôle final : rien qui ressemble à un secret, au nom du compte ou à l'écran de cette machine
user=$(id -un)
bad=$(grep -rIlE "/home/$user\b|([0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}|gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|sk-ant-[A-Za-z0-9_-]{30,}|BEGIN [A-Z ]*PRIVATE KEY" home "$REPO/system" 2>/dev/null || true)
# Le nom de l'écran de ce PC, hors des lignes déjà dans le dépôt (un exemple « HDMI-A-1 » du dépôt n'est pas un écran)
if [ -n "$mon" ]; then
  while IFS= read -r f; do
    nouvelles="$(grep -F "\"$mon\"" "$f" | grep -vxFf <(grep -F "\"$mon\"" "$REPO/$f" 2>/dev/null || true) || true)"
    [ -z "$nouvelles" ] || bad="$bad"$'\n'"$f"
  done < <(grep -rIlF "\"$mon\"" home 2>/dev/null || true)
fi
# Clés d'API, jetons et adresses e-mail : seulement dans une ligne NOUVELLE, absente de la version du fichier dans git
# (HEAD). nc-ia, nc-noeud et nc_google.py en contiennent exprès (motifs de masquage, noms de champs). Jamais la valeur
# à l'écran : le fichier, la ligne et le genre de motif.
secrets="$(python3 -I - "$REPO" home <<'EOF'
import os, re, subprocess, sys
from pathlib import Path
depot, export = Path(sys.argv[1]), Path(sys.argv[2])
en = os.environ.get("NC_LANGUE") == "en"
MOTIFS = [
    ("clé d'API (sk-…)", "API key (sk-…)", r"sk-[A-Za-z0-9_-]{20,}"),
    ("clé Google (AIza…)", "Google key (AIza…)", r"AIza[0-9A-Za-z_-]{35}"),
    ("clé Groq (gsk_…)", "Groq key (gsk_…)", r"gsk_[A-Za-z0-9]{40,}"),
    ("clé AWS (AKIA…)", "AWS key (AKIA…)", r"AKIA[0-9A-Z]{16}"),
    ("jeton de bot Telegram", "Telegram bot token", r"(?<![0-9])[0-9]{8,10}:AA[A-Za-z0-9_-]{30,}"),
    ("jeton Slack (xox…-)", "Slack token (xox…-)", r"xox[abprs]-"),
    ("jeton Google (ya29.)", "Google token (ya29.)", r"ya29\."),
    ("refresh_token rempli", "filled refresh_token",
     r"""(?i)refresh_token["']?\s*[:=]\s*(?:["'][^"'\s]+|[A-Za-z0-9._/+=-]{16,})"""),
]
MOTIFS = [(fr, an, re.compile(m)) for fr, an, m in MOTIFS]
EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@([A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.([A-Za-z]{2,}))(?![A-Za-z0-9-])")
# Pas des adresses : unités systemd (nom@instance.service), images @2x, extensions de fichiers
PAS_UNE_ADRESSE = {"service", "socket", "target", "timer", "path", "mount", "automount", "slice", "scope", "device",
                   "swap", "desktop", "png", "jpg", "jpeg", "svg", "webp", "gif", "qml", "lua", "luau", "json", "js"}


def git(*a, texte=True):
    return subprocess.run(["git", "-C", str(depot), *a], capture_output=True, text=texte)


tete = {}
r = git("ls-tree", "-r", "-z", "HEAD", "--", "home", "system")
for e in filter(None, r.stdout.split("\0") if r.returncode == 0 else []):
    meta, chemin = e.split("\t", 1)
    if meta.split()[1] == "blob":
        tete[chemin] = meta.split()[2]
# Les adresses déjà dans un fichier suivi par git sont permises partout
r = git("grep", "-h", "-o", "-I", "-E", r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", "HEAD", "--", ".")
suivies = {m.group(0).lower() for l in (r.stdout.splitlines() if r.returncode == 0 else []) for m in EMAIL.finditer(l)}


def adresse_permise(m):
    adresse, domaine, fin = m.group(0).lower(), m.group(1).lower(), m.group(2).lower()
    local = adresse.split("@", 1)[0]
    return (domaine.split(".")[0] == "example" or "noreply" in local or "no-reply" in local or fin in PAS_UNE_ADRESSE
            or re.fullmatch(r"[0-9]+x", domaine.split(".")[0]) is not None or adresse in suivies)


def lignes(f):
    try:
        with open(f, "rb") as h:
            b = h.read(8192)
            if b"\0" in b:
                return None                             # binaire (fond d'écran…), comme grep -I
            b += h.read()
    except OSError:
        return None
    return b.decode("utf-8", "replace").splitlines()


def lignes_de_git(rel):
    blob = tete.get(rel)
    if not blob:
        return set()
    r = git("cat-file", "blob", blob, texte=False)
    return set(r.stdout.decode("utf-8", "replace").splitlines()) if r.returncode == 0 else set()


for racine, prefixe in ((export, "home"), (depot / "system", "system")):
    if not racine.is_dir():
        continue
    for f in sorted(racine.rglob("*")):
        if f.is_symlink() or not f.is_file():
            continue
        contenu = lignes(f)
        if not contenu:
            continue
        rel = prefixe + "/" + f.relative_to(racine).as_posix()
        connues = None
        for i, l in enumerate(contenu, 1):
            genres = [an if en else fr for fr, an, m in MOTIFS if m.search(l)]
            if any(not adresse_permise(m) for m in EMAIL.finditer(l)):
                genres.append("e-mail address" if en else "adresse e-mail")
            if not genres:
                continue
            if connues is None:
                connues = lignes_de_git(rel)
            if l not in connues:
                print(f"{rel}, {'line' if en else 'ligne'} {i} : {', '.join(genres)}")
EOF
)" || secrets="$(t "contrôle des clés impossible (python3)" "key check failed (python3)")"
if [ -n "$secrets" ]; then
  bad="$bad"$'\n'"$secrets"$'\n'"$(t "  (ressemble à une clé, un jeton ou une adresse : retire-le de ~, ou, si ce n'est pas un secret, commite d'abord la ligne dans le dépôt)" "  (looks like a key, a token or an address: remove it from ~, or, if it is not a secret, commit the line to the repository first)")"
fi
# Un lien sous home/ ne mène jamais hors du dépôt : ni chemin absolu, ni « .. », ni nom du compte
while IFS= read -r -d '' l; do
  c="$(readlink -- "$l")"
  case "$c" in /*|*..*|*"$user"*) bad="$bad"$'\n'"$l -> $c" ;; esac
done < <(find home -type l -print0)
if [ -n "$bad" ]; then echo "$(t "ATTENTION : à vérifier avant de publier :" "WARNING: check before publishing:")" >&2; echo "$bad" >&2; exit 1; fi
if [ "$preview" = 1 ]; then
  git --no-pager diff --no-index -- "$REPO/home" home && exit 0
  code=$?; [ "$code" = 1 ] && exit 0; exit "$code"
fi
verifier_propre || exit 1
mv "$REPO/home" "$stage/previous-home"
mv home "$REPO/home"
echo "$(t "Dépôt mis à jour depuis ce PC." "Repository updated from this PC.")"
