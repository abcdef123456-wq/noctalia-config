# Outils modernes du terminal (nc-reglages → Terminal → Outils modernes), chargé par ~/.zshrc.
# Chaque bloc n'existe que si l'outil est installé : rien n'est affiché sinon. Tous suivent les couleurs du terminal
# (les 16 couleurs ANSI que nc-theme-sync règle sur le fond d'écran), donc le fond d'écran, sans rien régénérer.
#   fzf     Ctrl+R historique · Ctrl+T fichiers · Alt+C dossiers · Tab (avec fzf-tab) en liste filtrable
#   zoxide  z DOSSIER (saute vers un dossier déjà visité) · zi (choix) ; cd reste cd
#   eza     ls ll la lt (icônes, dossiers d'abord, git) sauf si tu as déjà tes propres alias
#   bat     coloré, thème ansi (man aussi) · delta : git diff / log lisibles, sauf si tu as déjà un pager git
#   lazygit lg · yazi y (change de dossier en sortant) · nc-outils : ce qui est actif
# Tes propres alias (~/.zshrc.perso, chargé après) l'emportent toujours.
# Pas de fonction autour : fzf --zsh et zoxide déclarent leurs variables avec typeset, qui serait local.

_nc_reglage() { # _nc_reglage CLE -> la valeur du réglage, sans sous-processus
  local f=~/.config/nc/reglages.conf l v
  [[ -r $f ]] || return 1
  for l in "${(@f)"$(<$f)"}"; do
    [[ $l == $1=* ]] && v=${l#*=}
  done
  v=${v//[\" ]/}
  [[ -n $v ]] && print -r -- $v
}

if [[ "$(_nc_reglage TERMINAL_OUTILS)" != non ]]; then

  # Debian : bat s'appelle batcat et fd fdfind
  typeset _nc_bat= _nc_fd= _nc_eza=0
  if (( $+commands[bat] )); then _nc_bat=bat; elif (( $+commands[batcat] )); then _nc_bat=batcat; fi
  if (( $+commands[fd] )); then _nc_fd=fd; elif (( $+commands[fdfind] )); then _nc_fd=fdfind; fi
  (( $+commands[eza] )) && _nc_eza=1
  [[ $_nc_bat == batcat ]] && (( ! $+aliases[bat] )) && alias bat=batcat
  [[ $_nc_fd == fdfind ]] && (( ! $+aliases[fd] )) && alias fd=fdfind

  # ── fzf ──
  if (( $+commands[fzf] )); then
    # Couleurs 0-15 du terminal : fond transparent (-1), accents bleu (4) et magenta (5)
    typeset _o="--layout=reverse --height=60% --border=rounded --info=inline-right --prompt='❯ ' --pointer='▶' --marker='✓' --color=fg:-1,bg:-1,hl:4,fg+:-1,bg+:8,hl+:12,info:5,prompt:4,pointer:5,marker:2,spinner:5,header:6,border:4,gutter:-1,label:4"
    FZF_DEFAULT_OPTS="$_o $FZF_DEFAULT_OPTS"   # tes propres options viennent après : elles gagnent
    if [[ -n $_nc_fd && -z $FZF_DEFAULT_COMMAND ]]; then
      export FZF_DEFAULT_COMMAND="$_nc_fd --hidden --follow --exclude .git"
      export FZF_CTRL_T_COMMAND="$FZF_DEFAULT_COMMAND"
      export FZF_ALT_C_COMMAND="$_nc_fd --type d --hidden --follow --exclude .git"
    fi
    typeset _pf _pd
    [[ -n $_nc_bat ]] && _pf="$_nc_bat --color=always --style=plain --line-range=:200 {}" || _pf="head -n 200 {}"
    (( _nc_eza )) && _pd="eza --tree --level=2 --color=always --icons=auto {}" || _pd="ls -A {}"
    : ${FZF_CTRL_T_OPTS:="--preview '[[ -d {} ]] && $_pd || $_pf'"}
    : ${FZF_ALT_C_OPTS:="--preview '$_pd'"}
    export FZF_DEFAULT_OPTS FZF_CTRL_T_OPTS FZF_ALT_C_OPTS
    # fzf --zsh (0.48 ou plus) : Ctrl+R, Ctrl+T, Alt+C. zsh-autosuggestions n'y gêne pas : il s'accroche aux touches
    # au premier affichage de l'invite, après celles-ci.
    source <(fzf --zsh 2>/dev/null)
    unset _o _pf _pd
  fi

  # ── fzf-tab : Tab ouvre la liste filtrable (chargé ici si .zshrc ne l'a pas déjà fait via plugins=) ──
  if (( $+commands[fzf] && ! $+functions[enable-fzf-tab] && $+functions[compdef] )) \
     && [[ -r ${ZSH_CUSTOM:-$HOME/.oh-my-zsh/custom}/plugins/fzf-tab/fzf-tab.plugin.zsh ]]; then
    source ${ZSH_CUSTOM:-$HOME/.oh-my-zsh/custom}/plugins/fzf-tab/fzf-tab.plugin.zsh
  fi
  if (( $+functions[enable-fzf-tab] )); then
    zstyle ':completion:*' menu no
    zstyle ':completion:*:descriptions' format '[%d]'
    zstyle ':fzf-tab:*' use-fzf-default-opts yes
    zstyle ':fzf-tab:*' switch-group '<' '>'
    if (( _nc_eza )); then
      zstyle ':fzf-tab:complete:(cd|z|zi):*' fzf-preview 'eza -1 --color=always --icons=auto $realpath'
    fi
    if [[ -n $_nc_bat ]]; then
      zstyle ':fzf-tab:complete:*:*' fzf-preview "[[ -d \$realpath ]] && ls -A \$realpath || { [[ -f \$realpath ]] && $_nc_bat --color=always --style=plain --line-range=:100 \$realpath; }"
    fi
  fi

  # ── zoxide : z et zi (cd reste cd) ──
  (( $+commands[zoxide] )) && eval "$(zoxide init zsh)"

  # ── eza : à la place des alias par défaut d'oh-my-zsh seulement, jamais d'un alias ou d'une fonction à toi ──
  if (( _nc_eza )); then
    _nc_alias_libre() { # vrai si le nom n'a ni fonction ni alias, ou seulement celui qu'oh-my-zsh pose
      (( $+functions[$1] )) && return 1
      (( $+aliases[$1] )) || return 0
      case "$1=$aliases[$1]" in
        ls=ls\ --color=*|ls=ls\ -G|l=ls\ -lah|la=ls\ -lAh|ll=ls\ -lh|lsa=ls\ -lah) return 0 ;;
      esac
      return 1
    }
    typeset _ic=auto _e
    [[ "$(_nc_reglage TERMINAL_LS_ICONES)" == non ]] && _ic=never
    _e="eza --group-directories-first --icons=$_ic"
    if _nc_alias_libre ls; then
      alias ls="$_e"
      _nc_alias_libre ll && alias ll="$_e -l --git --header"
      _nc_alias_libre la && alias la="$_e -la --git --header"
      _nc_alias_libre l && alias l="$_e -la --git --header"
      (( $+aliases[lt] || $+functions[lt] )) || alias lt="$_e --tree --level=2"
    fi
    unfunction _nc_alias_libre
    unset _ic _e
  fi

  # ── bat : thème ansi (suit le terminal) ; pas d'alias cat, pour ne pas surprendre les habitudes ──
  if [[ -n $_nc_bat ]]; then
    : ${BAT_THEME:=ansi}
    export BAT_THEME
    # man en couleurs (la recette de bat) ; sed est GNU partout où tourne le bureau
    [[ -z $MANPAGER ]] && export MANPAGER="sh -c 'sed -u -e \"s/\\x1B\[[0-9;]*m//g; s/.\\x08//g\" | $_nc_bat -p -lman'"
  fi

  # ── delta : seulement sans pager git à toi (une lecture de config, une fois) ──
  if (( $+commands[delta] && $+commands[git] )) && [[ -z $GIT_PAGER ]] \
     && [[ -z "$(git config --global --get core.pager 2>/dev/null)" ]]; then
    typeset _n=${GIT_CONFIG_COUNT:-0} _k _v _i _deja=" "
    typeset -a _cfg=(
      core.pager delta
      interactive.diffFilter "delta --color-only"
      delta.navigate true
      delta.syntax-theme ansi
      delta.line-numbers true
    )
    # ce que d'autres ont déjà posé (GIT_CONFIG_KEY_n) reste, et n'est pas reposé
    for (( _i = 0; _i < _n; _i++ )); do _deja+="${(P)${:-GIT_CONFIG_KEY_$_i}} "; done
    if [[ $_deja != *" core.pager "* ]]; then
      for _k _v in "${_cfg[@]}"; do
        [[ $_deja == *" $_k "* ]] && continue
        export "GIT_CONFIG_KEY_$_n=$_k" "GIT_CONFIG_VALUE_$_n=$_v"
        (( _n++ ))
      done
      export GIT_CONFIG_COUNT=$_n
    fi
    unset _n _k _v _i _deja _cfg
  fi

  # ── lazygit : lg, avec notre thème d'abord, ta config ensuite (la dernière gagne) ──
  if (( $+commands[lazygit] )); then
    [[ $aliases[lg] == *lazygit* ]] && unalias lg   # l'alias lg=lazygit d'oh-my-zsh ou à toi : remplacé par la fonction
    if (( ! $+aliases[lg] && ! $+functions[lg] )); then
      lg() {
        local f=~/.config/nc/lazygit.yml u=${XDG_CONFIG_HOME:-$HOME/.config}/lazygit/config.yml
        if [[ -n $LG_CONFIG_FILE || ! -r $f ]]; then command lazygit "$@"; return; fi
        [[ -r $u ]] && f+=",$u"   # lazygit lit les fichiers dans l'ordre et le dernier gagne
        LG_CONFIG_FILE=$f command lazygit "$@"
      }
    fi
  fi

  # ── yazi : y ouvre yazi et te laisse dans le dossier où tu l'as quitté ──
  if (( $+commands[yazi] && ! $+aliases[y] && ! $+functions[y] )); then
    y() {
      local tmp cwd
      tmp=$(mktemp -t yazi-cwd.XXXXXX) || return
      command yazi "$@" --cwd-file="$tmp"
      cwd=$(<"$tmp")
      [[ -n $cwd && $cwd != $PWD && -d $cwd ]] && builtin cd -- "$cwd"
      rm -f -- "$tmp"
    }
  fi

  # ── nc-outils : ce qui est actif ──
  nc-outils() {
    local fr=0 o c m
    [[ "${NC_LANGUE:-$LANG}" == fr* ]] && fr=1
    (( fr )) && print "Outils modernes du terminal (nc-reglages → Terminal pour les couper) :" \
             || print "Modern terminal tools (nc-settings → Terminal to turn off):"
    for o in "fzf:Ctrl+R Ctrl+T Alt+C" "zoxide:z zi" "eza:ls ll la lt" "bat:bat, man" "delta:git diff" "lazygit:lg" "yazi:y"; do
      c=${o%%:*}; m="·"
      (( $+commands[$c] )) && m="✓"
      [[ $c == bat ]] && (( $+commands[batcat] )) && m="✓"
      print -r -- "  $m $c  ${o#*:}"
    done
    (( fr )) && print "  · = non installé (paquet du même nom ; yazi et lazygit selon la distribution)." \
             || print "  · = not installed (package of the same name; yazi and lazygit depend on the distribution)."
  }
  unset _nc_bat _nc_fd _nc_eza
fi
unfunction _nc_reglage
