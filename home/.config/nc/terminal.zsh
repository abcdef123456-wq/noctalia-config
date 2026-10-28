# Commandes longues du terminal dans l'île (nc-reglages → Île → « Commandes longues du terminal »), chargé par ~/.zshrc.
# Une commande qui dure 10 s ou plus : l'île montre le nom du programme et sa durée (pilule, page Terminal), puis
# « Terminée » ou « Échec », avec un clic pour revenir au terminal. Deux fichiers dans le dossier privé de la session (0700) :
#   $XDG_RUNTIME_DIR/nc-terminal        pendant une commande : pid du terminal, début (s), pid du shell, programme
#   $XDG_RUNTIME_DIR/nc-terminal-fini   après une commande de 10 s ou plus : code, durée (s), fin (s), pid du terminal, programme
# Vie privée : SEUL le nom du programme est écrit (le premier mot après les VAR=…, sudo, env, nohup, time…), jamais ses
# arguments (mots de passe, jetons, chemins) ; une ligne qui commence par une espace (hors historique) n'est pas notée ;
# les programmes interactifs (éditeurs, ssh, pagers, consoles…) non plus. Écriture atomique (fichier temporaire puis
# zf_mv), seulement des commandes internes de zsh (print, zf_mv, zf_rm) : aucun processus lancé à chaque commande.
# Plusieurs terminaux : la dernière commande lancée est celle qui s'affiche ; un shell n'efface que sa propre ligne.
# Le pid du terminal est $PPID : juste si le terminal lance zsh lui-même (kitty, foot, alacritty…) ; sous tmux ou dans
# une instance unique de kitty, la fenêtre ramenée peut ne pas être la bonne (alors rien, ou la fenêtre principale).
# L'île (Terminal.qml) surveille les fichiers : rien ne sonde. Rien hors d'une session graphique (SSH, console), ni si
# le réglage est « non ».
[[ -n $XDG_RUNTIME_DIR && -d $XDG_RUNTIME_DIR && ( -n $WAYLAND_DISPLAY || -n $HYPRLAND_INSTANCE_SIGNATURE ) ]] || return 0
() {
  local f=~/.config/nc/reglages.conf l v
  [[ -r $f ]] || return 0
  for l in "${(@f)"$(<$f)"}"; do [[ $l == ILE_TERMINAL=* ]] && v=${l#*=}; done
  [[ ${v//[\" ]/} != non ]]
} || return 0
zmodload zsh/datetime 2>/dev/null || return 0                    # EPOCHSECONDS, sans sous-processus
zmodload -F zsh/files b:zf_rm b:zf_mv 2>/dev/null || return 0    # rm et mv internes
autoload -Uz add-zsh-hook

typeset -g _nc_terminal_debut=0 _nc_terminal_cmd=
# Mots sautés avant le programme (préfixes), et programmes interactifs (jamais « longs » : on y travaille)
typeset -ga _nc_terminal_prefixes=(sudo doas env nohup time command builtin exec noglob nocorrect)
typeset -ga _nc_terminal_interactifs=(vim nvim vi nano emacs micro helix hx ssh mosh telnet htop btop top less more man
  mysql psql sqlite3 tmux screen lazygit lg yazi ranger mc nnn claude codex gemini opencode ia python python3 ipython
  node irb bash zsh fish sh fzf journalctl watch tail gdb bluetoothctl nmtui wpa_cli nc-reglages nc-settings nc-raccourci
  nc-jarvis sudoedit visudo crontab ncdu glances cmatrix unimatrix ssh-add gpg passwd su)
# Le nom du programme d'une ligne de commande dans REPLY (pas de $(…) : une sous-coquille serait un processus), ou 1
_nc_terminal_programme() {
  local -a mots; local m suivant=0
  REPLY=
  mots=(${(z)1})
  for m in $mots; do
    (( suivant )) && { suivant=0; continue }                   # l'argument d'une option (env -u VAR, sudo -u NOM…)
    [[ $m == [A-Za-z_][A-Za-z0-9_]*=* ]] && continue           # VAR=valeur
    if [[ $m == -* ]]; then                                    # option d'un préfixe (sudo -i, env -u…)
      [[ $m == -[ugUCDphrTfSE] ]] && suivant=1
      continue
    fi
    (( ${_nc_terminal_prefixes[(Ie)$m]} )) && continue
    m=${m:t}                                                   # /usr/bin/make → make
    (( ${_nc_terminal_interactifs[(Ie)$m]} )) && return 1
    [[ -n $m && $m != *[^A-Za-z0-9._+-]* ]] || return 1         # pas un nom de programme (guillemets, parenthèses…)
    REPLY=${m[1,40]}
    return 0
  done
  return 1
}
_nc_terminal_ecrire() { # _nc_terminal_ecrire FICHIER LIGNES… : atomique, sans suivre un lien ni heurter noclobber
  local f=$1; shift
  print -rl -- "$@" >| "$f.$$" && zf_mv -f -- "$f.$$" "$f"
}
_nc_terminal_preexec() {
  _nc_terminal_cmd=
  [[ $1 == [[:space:]]* ]] && return 0                          # espace en tête : hors historique, hors île
  local REPLY
  _nc_terminal_programme "$1" || return 0
  _nc_terminal_debut=$EPOCHSECONDS
  _nc_terminal_cmd=$REPLY
  _nc_terminal_ecrire "$XDG_RUNTIME_DIR/nc-terminal" "$PPID" "$_nc_terminal_debut" "$$" "$_nc_terminal_cmd"
}
# Le fichier en cours est-il le mien (ligne 3 = pid de ce shell) ? Un autre terminal garde le sien.
_nc_terminal_mien() {
  local -a l
  [[ -r $XDG_RUNTIME_DIR/nc-terminal ]] || return 1
  l=("${(@f)"$(<$XDG_RUNTIME_DIR/nc-terminal)"}")
  [[ ${l[3]:-} == $$ ]]
}
_nc_terminal_precmd() {
  local code=$?
  [[ -n $_nc_terminal_cmd ]] || return 0
  local duree=$(( EPOCHSECONDS - _nc_terminal_debut ))
  if (( duree >= 10 )); then
    _nc_terminal_ecrire "$XDG_RUNTIME_DIR/nc-terminal-fini" "$code" "$duree" "$EPOCHSECONDS" "$PPID" "$_nc_terminal_cmd"
  fi
  _nc_terminal_cmd=
  _nc_terminal_mien && zf_rm -f -- "$XDG_RUNTIME_DIR/nc-terminal"
  return 0
}
# Shell fermé en pleine commande : son fichier ne reste pas
_nc_terminal_zshexit() { [[ -n $_nc_terminal_cmd ]] && _nc_terminal_mien && zf_rm -f -- "$XDG_RUNTIME_DIR/nc-terminal"; return 0 }
add-zsh-hook preexec _nc_terminal_preexec
add-zsh-hook precmd _nc_terminal_precmd
add-zsh-hook zshexit _nc_terminal_zshexit
