# IA dans le terminal (nc-ia ; nc-reglages → Intelligence artificielle → IA dans le terminal), chargé par ~/.zshrc.
#   Alt + I              la description tapée (« trouver les fichiers de plus de 1 Go ») devient une commande,
#                        laissée dans l'invite pour être relue : jamais lancée toute seule
#   ia QUESTION          une réponse courte, avec la commande utile en dernière ligne
#   … | ia CONSIGNE      sur la sortie d'une commande (journalctl -b -p err | ia résume)
#   gcia                 commit du diff indexé avec un message écrit par l'IA : tu le relis toujours dans ton éditeur
# L'IA est celle du bureau (automatique, choisie ou aucune) ; coupée, rien n'est envoyé.

_nc_ia_permise() {
  [[ "$(sed -n 's/^IA_TERMINAL=//p' ~/.config/nc/reglages.conf 2>/dev/null | tail -1 | tr -d '" ')" != non ]] \
    && ~/.local/bin/nc-ia actif
}

_nc_ia_msg() { [[ "${NC_LANGUE:-$LANG}" == fr* ]] && print -r -- "$1" || print -r -- "$2" }

# « ia » : seulement si aucune commande ne porte déjà ce nom (le client d'Internet Archive s'appelle aussi ia)
if (( ! $+commands[ia] )); then
  ia() {
    if ! _nc_ia_permise; then
      _nc_ia_msg "IA désactivée (nc-reglages → Intelligence artificielle)." "AI is turned off (nc-settings → Artificial intelligence)." >&2
      return 1
    fi
    if [[ ! -t 0 && ( -p /dev/stdin || -f /dev/stdin ) ]]; then
      { print -r -- "${*:-$(_nc_ia_msg 'Explique cette sortie de commande.' 'Explain this command output.')}"
        print -r -- ""; print -r -- "---"; head -c 200000; print -r -- ""; print -r -- "---"; } \
        | ~/.local/bin/nc-ia demander --usage texte -
    else
      [[ -n "$*" ]] || { _nc_ia_msg "ia QUESTION, ou commande | ia CONSIGNE" "ia QUESTION, or command | ia INSTRUCTION" >&2; return 2 }
      ~/.local/bin/nc-ia demander -- "$*"
    fi
  }
fi

_nc_ia_commande() {
  [[ -n "${BUFFER// }" ]] || return 0
  if ! _nc_ia_permise; then
    zle -M "$(_nc_ia_msg 'IA désactivée (nc-reglages → Intelligence artificielle)' 'AI is turned off (nc-settings → Artificial intelligence)')"
    return 0
  fi
  zle -M "$(_nc_ia_msg 'IA : une commande pour « ' 'AI: a command for “')$BUFFER$(_nc_ia_msg ' »…' '”…')"
  zle -R
  local c
  c="$(~/.local/bin/nc-ia commande -- "$BUFFER" 2>/dev/null </dev/null)"
  if [[ -n "$c" ]]; then
    BUFFER="$c"; CURSOR=${#BUFFER}
    zle -M "$(_nc_ia_msg 'Relis la commande, puis Entrée.' 'Check the command, then Enter.')"
  else
    zle -M "$(_nc_ia_msg 'Pas de commande proposée (nc-ia etat).' 'No command suggested (nc-ai status).')"
  fi
}
zle -N _nc_ia_commande
bindkey '^[i' _nc_ia_commande

# gcia : « git commit avec message de l'IA ». Le message vient du diff indexé et du style des derniers commits ;
# l'éditeur s'ouvre toujours dessus (tu le changes, ou tu quittes sans enregistrer pour annuler). Un secret dans le
# diff : rien n'est envoyé à l'IA.
gcia() {
  _nc_ia_permise || { _nc_ia_msg "IA désactivée (nc-reglages → Intelligence artificielle)." "AI is turned off (nc-settings → Artificial intelligence)." >&2; return 1 }
  local f c; f="$(mktemp "${TMPDIR:-/tmp}/gcia.XXXXXX")" || return 1
  _nc_ia_msg "IA : un message de commit…" "AI: a commit message…" >&2
  if ~/.local/bin/nc-ia commit >"$f" </dev/null; then
    command git commit --edit --file "$f" "$@"; c=$?
  else
    c=$?
  fi
  command rm -f "$f"
  return $c
}
