"""Choix proposés par JARVIS (issue #7) : des boutons à cliquer plutôt qu'une réponse à retaper.

Une seule fonction, partagée par le gateway (/api/ask, nc_gateway) et le client (nc-assistant la charge depuis ce
fichier, installé à côté : ~/.local/share/nc-jarvis/server/nc_choix.py). Sans dépendance : bibliothèque standard seule.

D'où viennent les choix, dans cet ordre :
  a) le marqueur que l'agent écrit en dernière ligne, [[choix: Option A | Option B]] ; il est retiré du texte ;
  b) sinon, une liste en fin de réponse (2 à 5 lignes « 1. … », « 1) … » ou « - … » de 60 caractères au plus), juste
     après une phrase qui finit par « ? », et rien après ; le texte reste tel quel ;
  c) sinon, aucun.
Au plus 5 choix de 80 caractères au plus, sinon aucun.
"""
import re

MAX_CHOIX = 5
MAX_LONGUEUR = 80
MAX_LIGNE_LISTE = 60

# Dernière ligne seulement : un marqueur au milieu du texte n'est pas une demande de choix
_MARQUEUR = re.compile(r"(?:^|\n)[ \t]*\[\[[ \t]*choix[ \t]*:([^\n\]]*)\]\][ \t]*\Z", re.I)
_NUMERO = re.compile(r"^[ \t]*\d{1,2}[.)][ \t]+(\S.*?)[ \t]*$")
_TIRET = re.compile(r"^[ \t]*[-*•][ \t]+(\S.*?)[ \t]*$")
_CONTROLE = re.compile(r"[\x00-\x1f\x7f-\x9f​-‏ -‮⁦-⁩]")


def _libelle(texte):
    """Libellé d'un bouton : sans gras ni code Markdown, ni caractère de contrôle, espaces simples."""
    texte = _CONTROLE.sub(" ", texte).replace("**", "").replace("__", "").replace("`", "")
    return re.sub(r"\s+", " ", texte).strip()


def verifier_choix(choix):
    """Liste de libellés valides, ou [] : 1 à 5 textes non vides de 80 caractères au plus, sans doublon."""
    if not isinstance(choix, list) or not 1 <= len(choix) <= MAX_CHOIX:
        return []
    propres = []
    for c in choix:
        if not isinstance(c, str):
            return []
        c = _libelle(c)
        if not c or len(c) > MAX_LONGUEUR:
            return []
        if c not in propres:
            propres.append(c)
    return propres


def _liste_finale(texte):
    """Repli (b) : les éléments de la liste qui termine le texte, après une question ; sinon []."""
    lignes = texte.rstrip().split("\n")
    elements, motif = [], None
    while lignes:
        ligne = lignes[-1]
        for m in (_NUMERO, _TIRET):
            r = m.match(ligne)
            if r and motif in (None, m):
                motif = m
                break
        else:
            break
        elements.insert(0, r.group(1))
        lignes.pop()
    if not 2 <= len(elements) <= MAX_CHOIX or any(len(_libelle(e)) > MAX_LIGNE_LISTE for e in elements):
        return []
    while lignes and not lignes[-1].strip():
        lignes.pop()                                   # une ligne vide entre la question et la liste
    question = lignes[-1].strip().rstrip("*_ ").rstrip() if lignes else ""
    return verifier_choix(elements) if question.endswith("?") else []


def extraire_choix(texte):
    """(texte sans marqueur, liste de choix) ; la liste est vide quand rien n'est proposé."""
    if not isinstance(texte, str):
        return texte, []
    m = _MARQUEUR.search(texte.rstrip())
    if m:
        reste = texte.rstrip()[:m.start()].rstrip()
        if not reste:
            return texte, []                           # rien d'autre que le marqueur : on n'efface pas toute la réponse
        return reste, verifier_choix([c for c in m.group(1).split("|") if c.strip()])
    return texte, _liste_finale(texte)
