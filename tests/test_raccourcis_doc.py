"""RACCOURCIS.md dit tout ce que home/.config/hypr/nc/raccourcis.lua déclare avec une description.

Un raccourci ajouté avec une description (« Section|Texte ») apparaît tout seul dans la fiche Super + /, mais pas dans
RACCOURCIS.md : ce test attrape l'oubli. On compare les TOUCHES (modificateurs + touche), pas les textes, que la doc
reformule. Rien n'est lancé : le Lua est lu comme du texte (les commentaires et les chaînes longues sont écartés, les
appels touche(...) sont découpés), et les noms de touches viennent de nc-keys (KEYCODES), comme la fiche.

Les écritures de la doc sont normalisées : Super/SUPER, Maj/SHIFT, Ctrl/CTRL, Alt/ALT ; « 1…4 » et « F1…F12 » sont
dépliés ; « A ou B » et « A / B » sont des variantes ; une parenthèse est ignorée.

Écartés exprès (liste ci-dessous, vérifiée par un test) :
- les raccourcis SANS description (« Super + Alt + Tab », « Maj + Impr. écran », le relâchement de la dictée, le bouton
  d'arrêt, la sortie du mode capture…) : ce sont des doublons ou des liens internes, la fiche ne les montre pas non plus ;
- « Super seule » : la description est construite à l'exécution et la touche est un réglage, pas un raccourci fixe."""
import importlib.machinery
import importlib.util
import os
from pathlib import Path
import re
import unittest

REPO = Path(__file__).resolve().parents[1]
LUA = REPO / "home/.config/hypr/nc/raccourcis.lua"
DOC = REPO / "RACCOURCIS.md"

# Description construite à l'exécution (elle contient une concaténation) : exclue, et c'est la seule
DESCRIPTIONS_DYNAMIQUES = ["Super seule"]

MODS_LUA = {"SUPER": "super", "SHIFT": "maj", "CTRL": "ctrl", "CONTROL": "ctrl", "ALT": "alt"}
MODS_DOC = {"super": "super", "maj": "maj", "shift": "maj", "ctrl": "ctrl", "alt": "alt"}
SOURIS = {"mouse:272": "glisser", "mouse:273": "clic droit", "mouse:274": "clic molette", "mouse:275": "bouton latéral arrière",
          "mouse:276": "bouton latéral avant", "mouse_up": "molette", "mouse_down": "molette"}
FLECHES = {111, 113, 114, 116}


def charger_nc_keys():
    env = os.environ.get("NC_LANGUE")
    os.environ["NC_LANGUE"] = "fr"                  # les noms de touches en français, comme la doc
    try:
        chemin = str(REPO / "home/.local/bin/nc-keys")
        spec = importlib.util.spec_from_loader("nc_keys_doc", importlib.machinery.SourceFileLoader("nc_keys_doc", chemin))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod
    finally:
        if env is None:
            os.environ.pop("NC_LANGUE", None)
        else:
            os.environ["NC_LANGUE"] = env


NC_KEYS = charger_nc_keys()


def nettoyer_lua(src):
    """Sans commentaires ; chaînes longues [[...]] remplacées par "" ; les chaînes "..." et '...' sont gardées."""
    sortie, i, n = [], 0, len(src)
    while i < n:
        c = src[i]
        if src.startswith("--", i):
            while i < n and src[i] != "\n":
                i += 1
        elif src.startswith("[[", i):
            fin = src.index("]]", i)
            sortie.append('""')
            i = fin + 2
        elif c in "\"'":
            j = i + 1
            while src[j] != c:
                j += 2 if src[j] == "\\" else 1
            sortie.append(src[i:j + 1])
            i = j + 1
        else:
            sortie.append(c)
            i += 1
    return "".join(sortie)


def fin_parenthese(src, debut):
    """Position de la parenthèse fermante qui répond à celle ouverte en `debut`."""
    prof, i = 0, debut
    while i < len(src):
        c = src[i]
        if c in "\"'":
            i += 1
            while src[i] != c:
                i += 2 if src[i] == "\\" else 1
        elif c == "(":
            prof += 1
        elif c == ")":
            prof -= 1
            if prof == 0:
                return i
        i += 1
    raise ValueError("parenthèse non fermée")


def premier_argument(texte):
    """Le premier argument d'un appel (texte après la parenthèse ouvrante) : jusqu'à la première virgule hors chaîne."""
    i = 0
    while i < len(texte):
        c = texte[i]
        if c in "\"'":
            i += 1
            while texte[i] != c:
                i += 2 if texte[i] == "\\" else 1
        elif c == ",":
            return texte[:i]
        i += 1
    return texte


def codes_de_la_boucle(src, pos):
    """Codes de touche de la boucle `for` qui précède l'appel (les `code` des raccourcis écrits en boucle)."""
    debut = src.rindex("for ", 0, pos)
    lignes = src[:debut].splitlines()[-3:]                      # la table `pas` est écrite juste au-dessus de sa boucle
    entete = " ".join(lignes) + " " + src[debut:src.index("do", debut) + 2]
    codes = [int(x) for x in re.findall(r"\[(\d+)\]", entete)]
    if codes:
        return codes
    m = re.search(r"for i = (\d+), (\d+) do\s+local code = (\d+) \+ i", src[debut:debut + 200])
    if m:
        return [int(m[3]) + i for i in range(int(m[1]), int(m[2]) + 1)]
    raise ValueError("boucle inconnue : " + entete)


def nom_touche(code):
    if code in FLECHES:
        return "flèches"
    return str(NC_KEYS.KEYCODES[code]).lower()


def touches_de_expression(expr, src, pos):
    """[(mods, touche)] d'un premier argument de touche(), ou None si elle dépend d'une variable inconnue."""
    morceaux = []
    for m in re.finditer(r'"([^"]*)"|\'([^\']*)\'|(\w+)', expr):
        chaine = m[1] if m[1] is not None else m[2]
        if chaine is not None:
            morceaux.append(chaine)
        elif m[3] == "SUPER":
            morceaux.append("SUPER")
        elif m[3] == "code":
            morceaux.append("\0CODE")
        else:
            return None
    brut = "".join(morceaux)
    if "\0CODE" in brut:
        variantes = [brut.replace("\0CODE", str(c)) for c in codes_de_la_boucle(src, pos)]
    else:
        variantes = [brut]
    res = []
    for v in variantes:
        parts = [p.strip() for p in v.split("+") if p.strip()]
        mods = frozenset(MODS_LUA[p.upper()] for p in parts[:-1])
        derniere = parts[-1]
        if re.fullmatch(r"code:\d+", derniere):
            touche = nom_touche(int(derniere[5:]))
        elif derniere in SOURIS:
            touche = SOURIS[derniere]
        elif derniere == "Print":
            touche = "impr. écran"
        elif derniere.startswith("XF86Audio") or derniere.startswith("XF86MonBrightness"):
            touche = "touches média"
        else:
            touche = derniere.lower()
        res.append((mods, touche))
    return res


def raccourcis_decrits():
    """([(mods, touche)...], description ou None) pour chaque appel touche(...) du Lua, plus les descriptions dynamiques."""
    src = nettoyer_lua(LUA.read_text(encoding="utf-8"))
    variables = dict(re.findall(r'local (\w+) = trad\("([^"]*)"', src))
    trouves, dynamiques = [], []
    for m in re.finditer(r"(?<![\w.])touche\(", src):
        debut = m.end() - 1
        if src[max(0, m.start() - 18):m.start()].endswith("local function "):
            continue
        appel = src[debut + 1:fin_parenthese(src, debut)]
        touches = touches_de_expression(premier_argument(appel), src, m.start())
        if touches is None:
            continue                                            # `touches` en variable : le relais de si_compris, sans description
        t = re.search(r'\btrad\("([^"]*)"', appel)
        v = re.search(r",\s*(\w+)\s*(?:,\s*\{[^}]*\})?\s*$", appel)
        if t:
            desc = t[1]
        elif v and v[1] in variables:
            desc = variables[v[1]]
        elif re.search(r',\s*"[^"]*\|"\s*\.\.', appel):
            dynamiques.append(re.search(r'\.\.\s*nc\.t\("([^"]*)"', appel)[1].strip(" :"))
            continue
        else:
            desc = None
        trouves.append((touches, desc))
    return trouves, dynamiques


def lignes_de_la_doc():
    """[(mods, {mots})] pour chaque variante d'une première cellule de tableau de RACCOURCIS.md."""
    res = []
    for ligne in DOC.read_text(encoding="utf-8").splitlines():
        if not ligne.startswith("|") or ligne.startswith("|---"):
            continue
        cellule = ligne.split("|")[1]
        cellule = cellule.replace("`` ` ``", "‹BT›").replace("`", "")
        cellule = re.sub(r"\([^)]*\)", "", cellule)
        for variante in re.split(r"\s+ou\s+|\s*·\s*", cellule):
            parts = [p.strip() for p in variante.split("+") if p.strip()]
            mods, mots = set(), set()
            for p in parts:
                bas = p.lower()
                if bas in MODS_DOC:
                    mods.add(MODS_DOC[bas])
                    continue
                for alt in re.split(r"\s+/\s+|,\s+", p):
                    alt = alt.strip().replace("‹BT›", "`").lower()
                    m = re.fullmatch(r"(f?)(\d+)…f?(\d+)", alt)
                    if m:
                        a, b = int(m[2]), int(m[3])
                        suite = [str(x % 10) if not m[1] else "f%d" % x for x in range(a, (10 if b == 0 else b) + 1)]
                        if b == 0:
                            suite.append("0")
                        mots.update(suite)
                    else:
                        mots.add(alt)
            if mots:
                res.append((frozenset(mods), mots))
    return res


def dans_la_doc(mods, touche, doc):
    for m, mots in doc:
        if m != mods:
            continue
        if touche in mots or (" " in touche and any(touche in x for x in mots)):
            return True
    return False


def ecriture(mods, touche):
    noms = {"super": "Super", "ctrl": "Ctrl", "alt": "Alt", "maj": "Maj"}
    return " + ".join([noms[m] for m in ("super", "ctrl", "alt", "maj") if m in mods] + [touche])


class RaccourcisEtDoc(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.trouves, cls.dynamiques = raccourcis_decrits()
        cls.doc = lignes_de_la_doc()

    def test_le_lua_est_bien_lu(self):
        """Garde-fou du test lui-même : assez de raccourcis décrits, et des cas connus bien compris."""
        decrits = [(t, d) for t, d in self.trouves if d]
        self.assertGreater(len(decrits), 100)
        touches = {x for t, d in decrits for x in t}
        self.assertIn((frozenset({"super"}), "entrée"), touches)
        self.assertIn((frozenset({"super", "maj"}), "r"), touches)                 # code:27
        self.assertIn((frozenset({"super", "ctrl"}), "flèches"), touches)          # boucle sur les 4 flèches
        self.assertIn((frozenset({"super", "maj"}), "0"), touches)                 # boucle des bureaux 1…10
        self.assertIn((frozenset(), "f5"), touches)
        self.assertIn((frozenset(), "xf86kbdbrightnessup"), touches)
        self.assertIn((frozenset({"super", "ctrl"}), "molette"), touches)

    def test_descriptions_dynamiques_connues(self):
        self.assertEqual(self.dynamiques, DESCRIPTIONS_DYNAMIQUES)

    def test_chaque_raccourci_decrit_est_dans_la_doc(self):
        manquants = []
        for touches, desc in self.trouves:
            if not desc:
                continue
            for mods, touche in touches:
                if not dans_la_doc(mods, touche, self.doc):
                    manquants.append("%s  (%s)" % (ecriture(mods, touche), desc))
        self.maxDiff = None
        self.assertEqual(sorted(set(manquants)), [], "à ajouter dans RACCOURCIS.md")

    def test_la_normalisation_de_la_doc(self):
        """Quelques écritures de la doc, pour que le test ne devienne pas trop gentil."""
        self.assertTrue(dans_la_doc(frozenset({"super", "maj"}), "q", self.doc))
        self.assertTrue(dans_la_doc(frozenset({"super"}), "`", self.doc))
        self.assertTrue(dans_la_doc(frozenset({"super"}), "m", self.doc))              # « Super + H ou Super + M »
        self.assertTrue(dans_la_doc(frozenset({"super"}), "=", self.doc))              # « Super + = / - »
        self.assertFalse(dans_la_doc(frozenset({"super", "maj"}), "z", self.doc))      # une touche qui n'existe pas


if __name__ == "__main__":
    unittest.main()
