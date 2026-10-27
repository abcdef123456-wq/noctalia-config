# Commandes longues du terminal dans l'île (nc-reglages → Île → « Commandes longues du terminal »), chargé par ~/.zshrc.
# Une commande qui dure 10 s ou plus : l'île montre son nom et sa durée (pilule, page Terminal), puis « Terminée » ou
# « Échec », avec un clic pour revenir au terminal. Deux fichiers dans le dossier privé de la session (0700) :
#   $XDG_RUNTIME_DIR/nc-terminal        pendant une commande : pid du terminal, début (s), pid du shell, commande
#   $XDG_RUNTIME_DIR/nc-terminal-fini   après une commande de 10 s ou plus : code, durée (s), fin (s), pid du terminal, commande
# L'île (Terminal.qml) les surveille : rien ne sonde. Ici, seulement des commandes internes de zsh (print, zf_rm) :
# aucun processus lancé à chaque commande. Rien hors d'une session graphique (SSH, console), ni si le réglage est « non ».
[[ -n $XDG_RUNTIME_DIR && -d $XDG_RUNTIME_DIR && ( -n $WAYLAND_DISPLAY || -n $HYPRLAND_INSTANCE_SIGNATURE ) ]] || return 0
() {
  local f=~/.config/nc/reglages.conf l v
  [[ -r $f ]] || return 0
  for l in "${(@f)"$(<$f)"}"; do [[ $l == ILE_TERMINAL=* ]] && v=${l#*=}; done
  [[ ${v//[\" ]/} != non ]]
} || return 0
zmodload zsh/datetime 2>/dev/null || return 0            # EPOCHSECONDS, sans sous-processus
zmodload -F zsh/files b:zf_rm 2>/dev/null || return 0    # rm interne
autoload -Uz add-zsh-hook

typeset -g _nc_terminal_debut=0 _nc_terminal_cmd=
_nc_terminal_preexec() {
  _nc_terminal_debut=$EPOCHSECONDS
  _nc_terminal_cmd=${${1//$'\n'/ }[1,200]}
  print -rl -- "$PPID" "$_nc_terminal_debut" "$$" "$_nc_terminal_cmd" > "$XDG_RUNTIME_DIR/nc-terminal"
}
_nc_terminal_precmd() {
  local code=$?
  [[ -n $_nc_terminal_cmd ]] || return 0
  local duree=$(( EPOCHSECONDS - _nc_terminal_debut ))
  if (( duree >= 10 )); then
    print -rl -- "$code" "$duree" "$EPOCHSECONDS" "$PPID" "$_nc_terminal_cmd" > "$XDG_RUNTIME_DIR/nc-terminal-fini"
  fi
  _nc_terminal_cmd=
  zf_rm -f -- "$XDG_RUNTIME_DIR/nc-terminal"
}
# Shell fermé en pleine commande : le fichier ne reste pas
_nc_terminal_zshexit() { [[ -n $_nc_terminal_cmd ]] && zf_rm -f -- "$XDG_RUNTIME_DIR/nc-terminal"; return 0 }
add-zsh-hook preexec _nc_terminal_preexec
add-zsh-hook precmd _nc_terminal_precmd
add-zsh-hook zshexit _nc_terminal_zshexit
