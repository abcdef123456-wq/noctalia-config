"""Plugins Noctalia : aucun champ qui exige une plugin_api plus récente que celle déclarée. Sinon Noctalia ignore TOUT
le plugin (vu en 5.3.0 : « widget entry 'titre': hover_highlight requires plugin_api >= 34 », et le titre des fenêtres
avait disparu de la barre). Les plugins restent à l'API 32, celle des Noctalia v5 les plus anciennes visées.

Une prop qu'un élément ui.* ne connaît pas est ignorée, avec seulement une ligne au journal (« ui tree: 'image' has no
prop 'onRightClick', ignored ») : le clic droit d'une tranche du carrousel des sessions n'ouvrait rien. Table des props
refusées par type d'élément (docs/user/plugins/development/declarative-ui.mdx de Noctalia v5.3.0 : onRightClick n'existe
que sur ui.button), vérifiée dans tous les .luau des plugins (panneaux et widgets)."""
from pathlib import Path
import re
import tomllib
import unittest

PLUGINS = Path(__file__).resolve().parents[1] / "home/.local/share/noctalia/plugins"
API_MAX = 32
# Champ (de plugin.toml, ou d'une entrée [[widget]] / [[panel]]) → plugin_api minimale qui l'accepte
EXIGE = {"hover_highlight": 34}

# Élément ui.* → props qu'il refuse (Noctalia v5.3.0). À compléter au besoin.
_SANS_CLIC_DROIT = ("image", "box", "row", "column", "scroll", "label", "markdown", "glyph", "separator", "spacer",
                    "progress", "graph", "toggle", "slider", "select", "input", "dragSource", "dropZone")
REFUSEES = {t: {"onRightClick"} for t in _SANS_CLIC_DROIT}


def sans_chaines_ni_commentaires(src):
    """Le source Luau, chaînes et commentaires remplacés par des espaces : les accolades qu'ils contiennent ne comptent
    pas, et les numéros de ligne restent justes (les fins de ligne des blocs longs sont gardées)."""
    out, i, n = [], 0, len(src)

    def blanc(t):
        return re.sub(r"[^\n]", " ", t)

    while i < n:
        long_ = re.match(r"(--)?\[(=*)\[", src[i:i + 40])
        if long_:   # commentaire --[[ ]] ou chaîne [[ ]], avec ou sans =
            fin = src.find("]" + long_.group(2) + "]", i + long_.end())
            fin = n if fin < 0 else fin + len(long_.group(2)) + 2
        elif src.startswith("--", i):
            fin = src.find("\n", i)
            fin = n if fin < 0 else fin
        elif src[i] in "\"'":
            j = i + 1
            while j < n and src[j] not in (src[i], "\n"):
                j += 2 if src[j] == "\\" else 1
            fin = min(j + 1, n)
        else:
            out.append(src[i])
            i += 1
            continue
        out.append(blanc(src[i:fin]))
        i = fin
    return "".join(out)


def props_des_elements(src):
    """(type, prop, ligne) pour chaque clé du premier argument littéral { … } d'un appel ui.type(…). Une table passée
    par une variable (ui.column(props, …)) n'est pas lue."""
    s = sans_chaines_ni_commentaires(src)
    for m in re.finditer(r"\bui\.(\w+)\s*\(\s*\{", s):
        prof, prec, i = 0, "", m.end() - 1
        while i < len(s):
            c = s[i]
            if c in "{(":
                prof += 1
            elif c in "})":
                prof -= 1
                if prof == 0:
                    break
            elif prof == 1 and prec in ("{", ",") and not c.isspace():
                k = re.match(r"([A-Za-z_]\w*)\s*=(?!=)", s[i:])
                if k:
                    yield m.group(1), k.group(1), s.count("\n", 0, i) + 1
            if not c.isspace():
                prec = c
            i += 1


class ApiDesPlugins(unittest.TestCase):
    def test_champs_compatibles(self):
        for f in sorted(PLUGINS.glob("*/plugin.toml")):
            with self.subTest(plugin=f.parent.name):
                d = tomllib.loads(f.read_text())
                api = d.get("plugin_api", 0)
                self.assertLessEqual(api, API_MAX, "plugin_api trop récente pour les Noctalia v5 visées")
                entrees = [d] + d.get("widget", []) + d.get("panel", [])
                for e in entrees:
                    for champ, mini in EXIGE.items():
                        self.assertNotIn(champ, e, f"{champ} exige plugin_api >= {mini} (déclarée : {api})")

    def test_props_refusees(self):
        trouvees = 0
        for f in sorted(PLUGINS.glob("*/*.luau")):
            for typ, prop, ligne in props_des_elements(f.read_text()):
                trouvees += 1
                with self.subTest(fichier=f"{f.parent.name}/{f.name}:{ligne}"):
                    self.assertNotIn(prop, REFUSEES.get(typ, ()),
                                     f"ui.{typ} n'a pas de prop {prop} : Noctalia l'ignore")
        self.assertGreater(trouvees, 300, "lecteur des props cassé : presque rien trouvé")

    def test_lecteur_des_props(self):
        src = ('ui.image({ path = "a{b", onClick = function() x = 1; f(y) end, --[[ } ]] onRightClick = g })\n'
               '-- ui.box({ onRightClick = h })\n'
               'ui.button({ text = [[}]], onRightClick = h, n = a == b })')
        self.assertEqual([(t, p, l) for t, p, l in props_des_elements(src)],
                         [("image", "path", 1), ("image", "onClick", 1), ("image", "onRightClick", 1),
                          ("button", "text", 3), ("button", "onRightClick", 3), ("button", "n", 3)])


if __name__ == "__main__":
    unittest.main()
