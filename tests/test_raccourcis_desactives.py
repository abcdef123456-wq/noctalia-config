"""Un raccourci de la config désactivé (« aucun » de raccourcis.conf) reste, grisé, dans sa section d'origine de la fiche
(Super + /), pas sous « Mes raccourcis » ; seul un raccourci inconnu y va. Le format du fichier ne change pas : la section est
retrouvée par le nom dans nc/raccourcis.lua. HOME temporaire, faux hyprctl (aucun vrai rechargement)."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[1]
BIN = REPO / "home/.local/bin"

# « hyprctl binds » : les raccourcis actifs, moins ceux que raccourcis.conf désactive (comme le fait le Lua)
FAUX_HYPRCTL = r'''#!/usr/bin/env python3
import os, sys
if sys.argv[1:2] == ["binds"]:
    off = set()
    try:
        for l in open(os.path.expanduser("~/.config/nc/raccourcis.conf"), encoding="utf-8"):
            c = l.rstrip("\n").split("\t")
            if c[0] == "aucun":
                off.add(c[1])
    except OSError:
        pass
    for mask, key, desc in (("64", "code:36", "Applis et barre|Terminal"), ("64", "code:55", "Fenêtres|%(float)s"),
                            ("64", "mouse:272", "Souris|%(move)s"), ("65", "code:44", "Fenêtres|%(move)s")):
        if mask + ":" + key not in off:
            print("bind\n\tmodmask: %%s\n\tsubmap: \n\tkey: %%s\n\tdescription: %%s" %% (mask, key, desc))
elif sys.argv[1:2] == ["configerrors"]:
    print("ok")
'''


class Desactives(unittest.TestCase):
    def prep(self, langue, conf):
        d = tempfile.TemporaryDirectory(prefix="nc-desactives-")
        self.addCleanup(d.cleanup)
        self.home = Path(d.name)
        (self.home / ".config/nc").mkdir(parents=True)
        (self.home / ".config/hypr/nc").mkdir(parents=True)
        shutil.copy(REPO / "home/.config/hypr/nc/raccourcis.lua", self.home / ".config/hypr/nc/raccourcis.lua")
        b = self.home / ".local/bin"; b.mkdir(parents=True)
        for nom in ("nc-reglages", "nc-raccourci", "nc-keys"):
            (b / nom).symlink_to(BIN / nom)
        faux = self.home / "faux"; faux.mkdir()
        noms = ("Floating ↔ tiled window", "Move the window") if langue == "en" else ("Fenêtre libre ↔ rangée", "Déplacer la fenêtre")
        (faux / "hyprctl").write_text(FAUX_HYPRCTL % {"float": noms[0], "move": noms[1]}); (faux / "hyprctl").chmod(0o755)
        (self.home / ".config/nc/raccourcis.conf").write_text("".join("\t".join(l) + "\n" for l in conf))
        self.env = dict(os.environ, HOME=str(self.home), PATH=f"{faux}:/usr/bin:/bin", NC_LANGUE=langue,
                        XDG_CONFIG_HOME=str(self.home / ".config"))

    def lancer(self, *args):
        r = subprocess.run([str(self.home / ".local/bin/nc-reglages"), *args], env=self.env, capture_output=True, text=True, timeout=30)
        self.assertEqual(r.returncode, 0, r.stderr)
        return r.stdout

    def lignes(self):
        return {tuple(l["ids"]): l for l in json.loads(self.lancer("catalogue")) if l["genre"] == "raccourci"}

    def test_ancien_format_dans_la_section_d_origine(self):
        self.prep("fr", [["aucun", "64:code:55", "Fenêtre libre ↔ rangée"], ["aucun", "64:mouse:272", "Déplacer la fenêtre"],
                         ["aucun", "65:code:44", "Déplacer la fenêtre"], ["aucun", "4:code:99", "Truc inconnu"]])
        l = self.lignes()
        for ids, sec in ((("64:code:55",), "Fenêtres"), (("64:mouse:272",), "Souris"), (("65:code:44",), "Fenêtres"),
                         (("4:code:99",), "Mes raccourcis")):
            with self.subTest(ids=ids):
                self.assertEqual(l[ids]["aide"], sec)
                self.assertTrue(l[ids]["desactive"])
        self.assertEqual(l[("64:code:55",)]["nom"], "Fenêtre libre ↔ rangée")

    def test_en_anglais_et_nom_ecrit_dans_l_autre_langue(self):
        self.prep("en", [["aucun", "64:code:55", "Floating ↔ tiled window"], ["aucun", "64:mouse:272", "Déplacer la fenêtre"],
                         ["aucun", "4:code:99", "Unknown thing"]])
        l = self.lignes()
        self.assertEqual(l[("64:code:55",)]["aide"], "Windows")
        self.assertEqual(l[("64:mouse:272",)]["aide"], "Mouse", "nom écrit en français, fiche en anglais")
        self.assertEqual(l[("4:code:99",)]["aide"], "My Shortcuts")
        self.assertTrue(all(l[k]["desactive"] for k in (("64:code:55",), ("64:mouse:272",), ("4:code:99",))))

    def test_aller_retour_desactiver_reactiver(self):
        self.prep("fr", [])
        avant = self.lignes()[("64:code:36",)]
        self.assertEqual((avant["aide"], avant["desactive"]), ("Applis et barre", False))
        self.lancer("raccourci", json.dumps({"action": "desactiver", "ids": ["64:code:36"], "nom": "Terminal"}))
        conf = (self.home / ".config/nc/raccourcis.conf").read_text()
        self.assertIn("aucun\t64:code:36\tTerminal\n", conf, "format du fichier inchangé : pas de préfixe de section")
        l = self.lignes()[("64:code:36",)]
        self.assertEqual((l["aide"], l["desactive"]), ("Applis et barre", True))
        self.lancer("raccourci", json.dumps({"action": "reactiver", "ids": ["64:code:36"]}))
        apres = self.lignes()
        self.assertEqual((apres[("64:code:36",)]["aide"], apres[("64:code:36",)]["desactive"]), ("Applis et barre", False))
        self.assertEqual([x for x in apres.values() if x["aide"] == "Mes raccourcis"], [], "aucun doublon dans Mes raccourcis")
        self.assertEqual(len(apres), 4)

    def test_nc_raccourci_liste_sans_prefixe(self):
        self.prep("fr", [["aucun", "64:code:55", "Fenêtre libre ↔ rangée"]])
        r = subprocess.run([str(self.home / ".local/bin/nc-raccourci"), "liste"], env=self.env, capture_output=True, text=True, timeout=30)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertNotIn("|", r.stdout)
        self.assertIn("Terminal", r.stdout)


if __name__ == "__main__":
    unittest.main()
