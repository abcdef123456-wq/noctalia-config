#!/usr/bin/env python3
"""emoji-generer : fabrique home/.local/share/nc/emoji/emoji.tsv, la liste d'emoji du Spotlight de l'île (« : coeur »).

Aucun téléchargement ici : les fichiers sources sont donnés en arguments (chemins locaux, données non fiables lues
seulement comme du texte et du XML, jamais exécutées).

  python3 -I outils/emoji-generer.py -o emoji.tsv --unicode 17.0 --cldr 48.2 \\
      --emoji-test emoji-test.txt --fr annotations/fr.xml --en annotations/en.xml \\
      [--fr-derive annotationsDerived/fr.xml --en-derive annotationsDerived/en.xml]

Sources : emoji-test.txt (Unicode, https://unicode.org/Public/<version>/emoji/) et les annotations CLDR
(common/annotations et common/annotationsDerived du dépôt unicode-org/cldr, à une étiquette de version précise).
Licence Unicode : home/.local/share/nc/emoji/LICENSE-UNICODE.txt.

Sortie (TSV, UTF-8, une ligne d'en-tête commençant par « # ») : emoji, nom français, nom anglais, mots-clés fr + en
séparés par « | ». Seuls les emoji « fully-qualified » sont gardés ; les variantes de couleur de peau sont écartées
(le fichier reste petit, et l'emoji de base se copie puis se nuance dans l'appli) sauf avec --avec-peau.
"""
import argparse
import os
import re
import sys
import unicodedata
import xml.etree.ElementTree as ET

PEAU = {chr(c) for c in range(0x1F3FB, 0x1F400)}
VS16 = "️"


def lire_emoji_test(chemin, avec_peau=False):
    """[(emoji, nom anglais)] dans l'ordre du fichier, « fully-qualified » seulement."""
    sortie = []
    with open(chemin, encoding="utf-8") as f:
        for ligne in f:
            if ligne.startswith("#") or ";" not in ligne:
                continue
            avant, _, apres = ligne.partition("#")
            codes, _, etat = avant.partition(";")
            if etat.strip() != "fully-qualified":
                continue
            try:
                emoji = "".join(chr(int(c, 16)) for c in codes.split())
            except ValueError:
                continue
            if not avec_peau and any(c in PEAU for c in emoji):
                continue
            # « 😀 E1.0 grinning face » : le nom suit la version
            m = re.match(r"\s*\S+\s+E\d+(?:\.\d+)?\s+(.*)", apres)
            sortie.append((emoji, m.group(1).strip() if m else ""))
    return sortie


def lire_annotations(chemin):
    """{emoji: (nom, [mots])} d'un fichier d'annotations CLDR (clé sans U+FE0F)."""
    noms, mots = {}, {}
    if not chemin:
        return noms, mots
    for a in ET.parse(chemin).getroot().iter("annotation"):
        cp = (a.get("cp") or "").replace(VS16, "")
        texte = (a.text or "").strip()
        if not cp or not texte:
            continue
        if a.get("type") == "tts":
            noms[cp] = texte
        else:
            mots[cp] = [m.strip() for m in texte.split("|") if m.strip()]
    return noms, mots


def fusion(*sources):
    """Les sources dans l'ordre de priorité : la première qui connaît l'emoji gagne."""
    sortie = {}
    for s in sources:
        for k, v in s.items():
            sortie.setdefault(k, v)
    return sortie


def plat(t):
    """Minuscules sans accents : la forme sur laquelle la recherche compare."""
    return "".join(c for c in unicodedata.normalize("NFD", t.lower()) if not unicodedata.combining(c))


def nettoyer(t):
    """Pas de tabulation ni de saut de ligne dans un champ."""
    return re.sub(r"[\t\r\n]+", " ", t).strip()


def generer(args):
    emojis = lire_emoji_test(args.emoji_test, args.avec_peau)
    nom_fr, mots_fr = (fusion(a, b) for a, b in zip(lire_annotations(args.fr), lire_annotations(args.fr_derive)))
    nom_en, mots_en = (fusion(a, b) for a, b in zip(lire_annotations(args.en), lire_annotations(args.en_derive)))
    lignes = ["# Unicode %s, CLDR %s : emoji, nom fr, nom en, mots-clés fr | en (licence : LICENSE-UNICODE.txt). "
              "Fichier généré par outils/emoji-generer.py, à ne pas modifier à la main." % (args.unicode, args.cldr)]
    vus = set()
    for emoji, nom_test in emojis:
        if emoji in vus:
            continue
        vus.add(emoji)
        cle = emoji.replace(VS16, "")
        fr = nom_fr.get(cle, "")
        en = nom_en.get(cle, "") or nom_test
        if not fr and not en:
            continue
        # Un mot-clé déjà dans un des noms (ou déjà vu) ne sert à rien : la recherche regarde aussi les noms
        noms_plats = plat(fr) + "|" + plat(en)
        mots, vu = [], set()
        for m in mots_fr.get(cle, []) + mots_en.get(cle, []):
            k = plat(m)
            if k in noms_plats or k in vu:
                continue
            vu.add(k)
            mots.append(m)
        lignes.append("\t".join((emoji, nettoyer(fr or en), nettoyer(en or fr), nettoyer("|".join(mots)))))
    # Écriture atomique : un fichier à moitié écrit ne remplace jamais le bon
    tmp = args.sortie + ".nouveau"
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lignes) + "\n")
    os.replace(tmp, args.sortie)
    return len(lignes) - 1


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("-o", "--sortie", required=True, help="fichier TSV à écrire")
    p.add_argument("--unicode", required=True, help="version d'Unicode des sources (pour l'en-tête)")
    p.add_argument("--cldr", required=True, help="version de CLDR des sources (pour l'en-tête)")
    p.add_argument("--emoji-test", required=True)
    p.add_argument("--fr", required=True)
    p.add_argument("--en", required=True)
    p.add_argument("--fr-derive")
    p.add_argument("--en-derive")
    p.add_argument("--avec-peau", action="store_true", help="garder les variantes de couleur de peau")
    args = p.parse_args(argv)
    n = generer(args)
    print("%d emoji écrits dans %s" % (n, args.sortie))
    return 0


if __name__ == "__main__":
    sys.exit(main())
