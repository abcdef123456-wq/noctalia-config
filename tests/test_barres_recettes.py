"""Barres des thèmes composées d'après les recettes : règles tirées de ce qui a été vu à l'écran.
- une barre collée en haut qui porte l'île (sans bande) fait au moins 40 px, sinon l'île dépasse du bandeau ;
- une barre sans pastilles a un fond, sauf sur un thème noir pur (texte sans fond illisible sur un fond d'écran clair) ;
- une barre du haut sans bande ne montre pas l'heure : l'île fermée la montre déjà (la date, oui) ;
- un thème a au plus une seconde barre, sur un autre bord que la première ;
- les bureaux posés dans une barre montrent leur chiffre (minimal sans chiffres = pastille vide, vu sur oled et papier ;
  l'utilisateur ne voyait pas les numéros) ; en pilules pleines, jamais focused_color=on_surface (chiffre on_surface sur
  une pilule on_surface : invisible, vu sur oled). En minimal, focused_color colore le chiffre lui-même : permis ;
- une barre de côté est une pilule flottante centrée sur le bord (vue sur matrice), jamais une barre pleine hauteur
  collée au bord (ancien nord, que l'utilisateur n'aimait pas) : sans fond, à 6 px du bord au moins, tout dans des
  groupes posés au centre, start et end vides ;
- une barre collée au bord avec un fond le pose jusqu'aux coins de l'écran (radius 0, margin_ends 0 : vu sur
  brutaliste, coins arrondis qui laissent voir le fond) ; l'air des pastilles passe par padding (12 au moins).
Règles sur les fichiers des thèmes : pas de session, pas de Noctalia."""
from tests import _isolation  # noqa: F401  (HOME, XDG_*, langue : avant tout le reste)
import contextlib
import json
from pathlib import Path
import re
import unittest
from unittest.mock import patch

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

    def test_bureaux_avec_chiffres(self):
        for nom, d in themes().items():
            if nom == "noctalia":           # la base, identique à config.toml
                continue
            b = d.get("noctalia", {}).get("bar.default", {})
            membres = [m for g in b.get("capsule_group", []) for m in g.get("members", [])]
            # sans listes, celles de config.toml (qui posent les bureaux) restent
            pose = "workspaces" in barre(d)["listes"] + membres or not any(k in b for k in ("start", "center", "end"))
            w = d.get("noctalia", {}).get("widget.workspaces", {})
            if pose:
                with self.subTest(theme=nom):
                    self.assertIs(w.get("show_labels"), True, "les numéros des bureaux ne sont pas visibles")
                    if w.get("style", "regular") != "minimal":
                        self.assertNotEqual(w.get("focused_color"), "on_surface", "chiffre invisible sur la pilule active")

    def test_barre_de_cote_bien_integree(self):
        for nom, d in themes().items():
            for t, b in d.get("noctalia", {}).items():
                if t.startswith("bar.") and b.get("position") in ("left", "right"):
                    with self.subTest(theme=nom, barre=t):
                        self.assertEqual(b.get("background_opacity", 0.0), 0.0, "pas de bande pleine hauteur")
                        self.assertGreaterEqual(b.get("margin_edge", 6), 6, "flottante, pas collée au bord")
                        self.assertEqual((b.get("start"), b.get("end")), ([], []), "rien aux extrémités")
                        self.assertTrue(b.get("center") and all(w.startswith("group:") for w in b["center"]),
                                        "tout dans des groupes au centre")

    def test_pilule_de_cote_exclusive(self):
        """La pilule de côté est la signature de matrice (« laisse-la exclusive à ce modèle ») : un seul thème au plus."""
        cote = [n for n, d in themes().items()
                if any(t.startswith("bar.") and b.get("position") in ("left", "right") for t, b in d.get("noctalia", {}).items())]
        self.assertLessEqual(len(cote), 1, cote)

    def test_barre_collee_remplit_les_coins(self):
        for nom, d in themes().items():
            for t, b in d.get("noctalia", {}).items():
                if t.startswith("bar.") and b.get("margin_edge", 6) == 0 and b.get("background_opacity", 0.0) > 0:
                    with self.subTest(theme=nom, barre=t):
                        self.assertEqual((b.get("radius"), b.get("margin_ends")), (0, 0), "coins de l'écran mal remplis")
                        self.assertGreaterEqual(b.get("padding", 0), 12, "rien plaqué contre le bord")

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
        # l'ancienne barre de brutaliste (collée, pleine, bouts arrondis par défaut) est attrapée
        with patch(__name__ + ".themes", lambda: {"brutaliste": {"noctalia": {"bar.default": {
                "position": "top", "margin_edge": 0, "margin_ends": 0, "background_opacity": 1.0}}}}):
            with self.assertRaises(AssertionError):
                with patch.object(self, "subTest", lambda **k: contextlib.nullcontext()):
                    self.test_barre_collee_remplit_les_coins()
        # l'ancienne barre de nord (pleine hauteur collée au bord, listes aux extrémités) est attrapée
        with patch(__name__ + ".themes", lambda: {"nord": {"noctalia": {"bar.default": {
                "position": "left", "margin_edge": 0, "thickness": 52, "background_opacity": 0.9,
                "start": ["logo", "workspaces"], "center": [], "end": ["tray", "group:status", "t-heure"]}}}}):
            with self.assertRaises(AssertionError):
                with patch.object(self, "subTest", lambda **k: contextlib.nullcontext()):
                    self.test_barre_de_cote_bien_integree()
        # l'ancienne table de papier (minimal sans chiffres, bureaux dans un groupe) est attrapée
        with patch(__name__ + ".themes", lambda: {"papier": {"noctalia": {
                "bar.default": {"capsule_group": [{"id": "b", "members": ["workspaces"]}], "start": ["group:b"]},
                "widget.workspaces": {"style": "minimal", "show_labels": False}}}}):
            with self.assertRaises(AssertionError):
                with patch.object(self, "subTest", lambda **k: contextlib.nullcontext()):
                    self.test_bureaux_avec_chiffres()
        # et l'ancienne table d'oled (chiffres posés, pilule active on_surface)
        with patch(__name__ + ".themes", lambda: {"oled": {"noctalia": {
                "bar.default": {"start": ["workspaces"]},
                "widget.workspaces": {"style": "regular", "show_labels": True, "focused_color": "on_surface"}}}}):
            with self.assertRaises(AssertionError):
                with patch.object(self, "subTest", lambda **k: contextlib.nullcontext()):
                    self.test_bureaux_avec_chiffres()


if __name__ == "__main__":
    unittest.main()
