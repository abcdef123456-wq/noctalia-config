"""A7 : les thèmes se reconnaissent sans regarder les couleurs. Cinq choix par thème (barre, bureaux, disposition,
dock, coins/bordure), calculés avec les défauts de nc-reglages et de config.toml quand le thème ne dit rien."""
import itertools
import json
from pathlib import Path
import unittest

REPO = Path(__file__).resolve().parents[1]
THEMES = REPO / "home/.local/share/nc/themes"


def cinq_choix(t):
    n = t.get("noctalia", {})
    r = t.get("reglages", {})
    bar = n.get("bar.default", {})
    ws = n.get("widget.workspaces", {})
    # Défauts de config.toml : barre en haut, flottante (margin_edge 6, épaisseur 36), capsules, bureaux « regular »
    barre = (bar.get("position", "top"), bar.get("margin_edge", 6) == 0, bar.get("capsule", True),
             bar.get("thickness", 36))
    # labels_only_when_occupied : tous les numéros, ou seulement ceux des bureaux occupés (config.toml : occupés seulement)
    bureaux = (ws.get("style", "regular"), ws.get("show_labels", True), ws.get("label_source", "id"),
               ws.get("labels_only_when_occupied", True))
    # l'espace entre les fenêtres en fait partie : une spirale sans espaces (dracula) ne ressemble pas à celle de base
    dispo = (r.get("FENETRES_DISPOSITION", "dwindle"), r.get("FENETRES_MAITRE_ORIENTATION", "auto"), r.get("FENETRES_ESPACE", "4"))
    dock = (r.get("DOCK", "oui") == "oui", r.get("DOCK_POSITION", "bottom"),
            r.get("DOCK_AUTO", "oui") == "oui")
    coins = (r.get("FENETRES_ARRONDI", "14"), r.get("FENETRES_BORDURE", "2"))
    return (barre, bureaux, dispo, dock, coins)


class CinqChoix(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.t = {f.stem: cinq_choix(json.loads(f.read_text(encoding="utf-8"))) for f in sorted(THEMES.glob("*.json"))}

    def test_chaque_theme_differe_de_noctalia(self):
        base = self.t["noctalia"]
        for nom, c in self.t.items():
            if nom == "noctalia":
                continue
            diff = sum(a != b for a, b in zip(c, base))
            with self.subTest(theme=nom):
                self.assertGreaterEqual(diff, 4, f"{nom} ne diffère de noctalia que sur {diff} choix sur 5")

    def test_aucun_couple_identique(self):
        for a, b in itertools.combinations(sorted(self.t), 2):
            with self.subTest(a=a, b=b):
                self.assertNotEqual(self.t[a], self.t[b], f"{a} et {b} ont les mêmes 5 choix")

    def test_barres_en_bas(self):
        # Barre de côté permise si elle est bien intégrée (pilule flottante centrée : test_barres_recettes), sans quota
        pos = [c[0][0] for c in self.t.values()]
        self.assertGreaterEqual(pos.count("bottom"), 2)


if __name__ == "__main__":
    unittest.main()
