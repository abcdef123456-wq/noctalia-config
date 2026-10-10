# Chargé par ~/.zshrc (legion-dotfiles). Ne rien mettre d'autre ici.
# Accueil du terminal (legion-greeting : logo aux couleurs du thème + infos système), une seule fois par fenêtre.
# Tant qu'aucune commande n'a été tapée, il est redessiné à la nouvelle taille quand la fenêtre change de taille.
autoload -Uz add-zsh-hook
typeset -gi _legion_greet_fresh=0
function _legion_greet() {
    add-zsh-hook -d precmd _legion_greet
    [[ -n "$FASTFETCH_SHOWN" ]] && return
    export FASTFETCH_SHOWN=1
    legion-greeting $COLUMNS $LINES
    _legion_greet_fresh=1
}
function _legion_greet_used() { _legion_greet_fresh=0 }
# _legion_greet_fresh : 0 = des commandes ont été tapées (on ne touche plus à l'écran),
#                       1 = terminal neuf (redessin en effaçant aussi l'historique, qui ne contient que l'accueil),
#                       2 = après Ctrl+L (redessin sans effacer l'historique des commandes précédentes)
function TRAPWINCH() {
    (( _legion_greet_fresh )) || return 0
    zle && zle -I
    if (( _legion_greet_fresh == 1 )); then print -n '\e[H\e[2J\e[3J'; else print -n '\e[H\e[2J'; fi
    legion-greeting $COLUMNS $LINES
}
# Ctrl+L : efface l'écran et réaffiche l'accueil à la taille actuelle de la fenêtre
function _legion_clear_screen() {
    zle -I
    print -n '\e[H\e[2J'
    legion-greeting $COLUMNS $LINES
    _legion_greet_fresh=2
}
zle -N clear-screen _legion_clear_screen
if [[ -x ~/.local/bin/legion-greeting ]]; then
    add-zsh-hook precmd _legion_greet
    add-zsh-hook preexec _legion_greet_used
fi
