"""Barres des thèmes composées d'après les recettes : règles tirées de ce qui a été vu à l'écran.
- une barre collée en haut qui porte l'île (sans bande) fait au moins 40 px, sinon l'île dépasse du bandeau ;
- une barre sans pastilles a un fond, sauf sur un thème noir pur (texte sans fond illisible sur un fond d'écran clair) ;
- une barre du haut sans bande ne montre pas l'heure : l'île fermée la montre déjà (la date, oui) ;
- un thème a au plus une seconde barre, sur un autre bord que la première.
Règles sur les fichiers des thèmes : pas de session, pas de Noctalia."""
from tests import _isolation  # noqa: F401  (HOME, XDG_*, langue : avant tout le reste)
import json
from pathlib import Path
import re
import unittest

THEMES = Path(__file__).resolve().parents[1] / "home/.local/share/nc/themes"


def themes():
    return {p.stem: json.loads(p.read_text(encoding="utf-8")) for p in sorted(THEMES.glob("*.json"))}


def barre(d):
    b = d.get("noctalia", {}).get("bar.default", {})
    return {"position": b.get("position", "top"), "thickness": b.get("thickness", 36), "margin_edge": b.get("margin_edge", 6),
            "capsule": b.get("capsule", True), "fond": b.get("background_opacity", 0.0),
            "listes": b.get("start", []) + b.get("center", []) + b.get("end", [])}


def montre_l_heure(d, nom_widget):
    """Vrai si l'instance (ou l'horloge de config.toml, « clock ») affiche l'heure."""
    if nom_widget == "clock":
        return True
    w = d.get("noctalia", {}).get("widget." + nom_widget, {})
    return w.get("type") == "clock" and bool(re.search(r"%[HIklRrTX]", w.get("format", "")))


class Regles(unittest.TestCase):
    def test_bandeau_du_haut_assez_haut_pour_l_ile(self):
        for nom, d in themes().items():
            b = barre(d)
            if b["position"] == "top" and b["margin_edge"] == 0 and d["reglages"].get("ILE_BANDE") != "oui":
                with self.subTest(theme=nom):
                    self.assertGreaterEqual(b["thickness"], 40)

    def test_barre_sans_pastilles_a_un_fond(self):
        for nom, d in themes().items():
            b = barre(d)
            if b["capsule"] is False and not d.get("noctalia", {}).get("theme", {}).get("pure_black_dark"):
                with self.subTest(theme=nom):
                    self.assertGreater(b["fond"], 0, "texte sans fond ni pastille : illisible sur un fond clair")

    def test_pas_d_heure_en_double_avec_l_ile(self):
        for nom, d in themes().items():
            b = barre(d)
            if b["position"] == "top" and d["reglages"].get("ILE_BANDE") != "oui":
                with self.subTest(theme=nom):
                    self.assertFalse([w for w in b["listes"] if montre_l_heure(d, w)], "l'île fermée montre déjà l'heure")

    def test_une_seule_seconde_barre_sur_un_autre_bord(self):
        for nom, d in themes().items():
            autres = [t for t in d.get("noctalia", {}) if t.startswith("bar.") and t != "bar.default"]
            with self.subTest(theme=nom):
                self.assertLessEqual(len(autres), 1)
                for t in autres:
                    self.assertNotEqual(d["noctalia"][t].get("position"), barre(d)["position"])

    def test_controle_du_controle(self):
        """Les règles attrapent bien les défauts vus : bandeau de 36, texte sans fond, heure en double."""
        d = {"reglages": {}, "noctalia": {"bar.default": {"position": "top", "margin_edge": 0, "thickness": 36,
                                                          "capsule": False, "background_opacity": 0.0, "end": ["t-h"]},
                                          "widget.t-h": {"type": "clock", "format": "{:%H:%M}"}}}
        b = barre(d)
        self.assertLess(b["thickness"], 40)
        self.assertEqual(b["fond"], 0)
        self.assertTrue(montre_l_heure(d, "t-h"))
        self.assertFalse(montre_l_heure({"noctalia": {"widget.t-d": {"type": "clock", "format": "{:%a %d %b}"}}}, "t-d"))


if __name__ == "__main__":
    unittest.main()
