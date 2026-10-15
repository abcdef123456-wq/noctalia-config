# ~/.zshrc (noctalia-config) : zsh + oh-my-zsh + powerlevel10k, accueil du terminal.
# Tes alias et réglages personnels : ~/.zshrc.perso (chargé à la fin, jamais remplacé par install.sh).

# Invite instantanée de powerlevel10k désactivée : l'accueil du terminal s'affiche avant la première invite.
typeset -g POWERLEVEL9K_INSTANT_PROMPT=off

export ZSH="$HOME/.oh-my-zsh"
ZSH_THEME="powerlevel10k/powerlevel10k"
plugins=(
  git
  zsh-autosuggestions
  zsh-syntax-highlighting
)
[[ -r "$ZSH/oh-my-zsh.sh" ]] && source "$ZSH/oh-my-zsh.sh"
[[ -r ~/.p10k.zsh ]] && source ~/.p10k.zsh

export PATH="$HOME/.local/bin:$PATH"

# Accueil du terminal (logo aux couleurs du fond d'écran + infos système)
[[ -r ~/.config/nc/greeting.zsh ]] && source ~/.config/nc/greeting.zsh

[[ -r ~/.zshrc.perso ]] && source ~/.zshrc.perso
