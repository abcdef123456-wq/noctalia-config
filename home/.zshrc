# ~/.zshrc (noctalia-config) : zsh + oh-my-zsh + powerlevel10k, accueil du terminal.
# Tes alias et réglages personnels : ~/.zshrc.perso (chargé à la fin, jamais remplacé par install.sh).

# Invite instantanée de powerlevel10k désactivée : l'accueil du terminal s'affiche avant la première invite.
typeset -g POWERLEVEL9K_INSTANT_PROMPT=off

export ZSH="$HOME/.oh-my-zsh"
ZSH_THEME="powerlevel10k/powerlevel10k"
plugins=(git)
# fzf-tab (Tab en liste filtrable) seulement s'il est téléchargé, sinon oh-my-zsh affiche « plugin not found » ;
# avant les deux autres, qui enveloppent les touches
[[ -d ${ZSH_CUSTOM:-$ZSH/custom}/plugins/fzf-tab ]] && plugins+=(fzf-tab)
plugins+=(zsh-autosuggestions zsh-syntax-highlighting)
# Mises à jour d'oh-my-zsh : nc-maj ne s'en occupe pas, donc un simple rappel (pas de question « Would you like to
# update? » dans un terminal neuf). La mise à jour se fait à la main : omz update.
zstyle ':omz:update' mode reminder
[[ -r "$ZSH/oh-my-zsh.sh" ]] && source "$ZSH/oh-my-zsh.sh"
[[ -r ~/.p10k.zsh ]] && source ~/.p10k.zsh

# ~/.local/bin en tête du PATH, une seule fois (remis devant s'il y était déjà plus loin) : les commandes nc-* et le
# Neovim récent qu'install.sh y installe passent avant ceux de /usr/bin (Debian 13 : Neovim 0.10, trop ancien)
typeset -U path PATH
path=("$HOME/.local/bin" $path)
export PATH

# Accueil du terminal (logo aux couleurs du fond d'écran + infos système)
[[ -r ~/.config/nc/greeting.zsh ]] && source ~/.config/nc/greeting.zsh

# IA dans le terminal : Alt + I (description → commande), « ia question » (nc-ia)
[[ -r ~/.config/nc/ia.zsh ]] && source ~/.config/nc/ia.zsh

# Outils modernes : fzf, zoxide, eza, bat, delta, lazygit, yazi (ceux qui sont installés ; nc-outils les liste)
[[ -r ~/.config/nc/outils.zsh ]] && source ~/.config/nc/outils.zsh

[[ -r ~/.zshrc.perso ]] && source ~/.zshrc.perso
