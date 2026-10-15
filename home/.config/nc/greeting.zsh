# Chargé par ~/.zshrc (noctalia-config). Ne rien mettre d'autre ici.
# Accueil du terminal (nc-greeting : logo aux couleurs du thème + infos système), une seule fois par fenêtre.
# Tant qu'aucune commande n'a été tapée, il est redessiné à la nouvelle taille quand la fenêtre change de taille.
autoload -Uz add-zsh-hook
typeset -gi _nc_greet_fresh=0
function _nc_greet() {
    add-zsh-hook -d precmd _nc_greet
    [[ -n "$FASTFETCH_SHOWN" ]] && return
    export FASTFETCH_SHOWN=1
    nc-greeting $COLUMNS $LINES
    _nc_greet_fresh=1
}
function _nc_greet_used() { _nc_greet_fresh=0 }
# _nc_greet_fresh : 0 = des commandes ont été tapées (on ne touche plus à l'écran),
#                       1 = terminal neuf (redessin en effaçant aussi l'historique, qui ne contient que l'accueil),
#                       2 = après Ctrl+L (redessin sans effacer l'historique des commandes précédentes)
function TRAPWINCH() {
    (( _nc_greet_fresh )) || return 0
    zle && zle -I
    if (( _nc_greet_fresh == 1 )); then print -n '\e[H\e[2J\e[3J'; else print -n '\e[H\e[2J'; fi
    nc-greeting $COLUMNS $LINES
}
# Ctrl+L : efface l'écran et réaffiche l'accueil à la taille actuelle de la fenêtre
function _nc_clear_screen() {
    zle -I
    print -n '\e[H\e[2J'
    nc-greeting $COLUMNS $LINES
    _nc_greet_fresh=2
}
zle -N clear-screen _nc_clear_screen
if [[ -x ~/.local/bin/nc-greeting ]]; then
    add-zsh-hook precmd _nc_greet
    add-zsh-hook preexec _nc_greet_used
fi
