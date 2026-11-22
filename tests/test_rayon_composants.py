"""Rayon des composants communs de l'île (Module, Ligne, boutons...) : ils suivent ILE_RAYON via Couleurs.rayon.

- Hors écran : le vrai Couleurs.qml ; à 100 % (défaut) chaque rayon d'aujourd'hui reste exact, carre = 0, rond = demi-taille.
- Source : chaque composant touché appelle Couleurs.rayon (un rayon remis en dur fait échouer)."""
import json
import re
import tempfile
import unittest

from tests import _ile_hors_ecran as H

# fichier : (rayon d'aujourd'hui, largeur, hauteur) d'un usage réel du composant
COMPOSANTS = {
    "Module.qml": (24, 300, 120),
    "JarvisBouton.qml": (16, 90, 32),
    "Ligne.qml": (12, 300, 42),
    "PastilleChoix.qml": (14, 80, 28),
    "BoutonEnergie.qml": (16, 120, 32),
    "VpnPastille.qml": (16, 120, 32),
    "JarvisChamp.qml": (19, 300, 38),
    "AssistantCommande.qml": (10, 90, 30),
}

SHELL = """
    Timer { interval: 300; running: true; onTriggered: parent.fin() }
    function fin() {
        var cas = %s
        for (var i = 0; i < cas.length; i++) {
            Reglages.valeurs = cas[i]
            var t = %s
            console.log("R:" + JSON.stringify(t.map(function (c) { return Couleurs.rayon(c[0], c[1], c[2]) })))
        }
        console.log("FINI"); Qt.exit(0)
    }
"""


def lancer(cas, tailles):
    with tempfile.TemporaryDirectory(prefix="nc-rayon-") as d:
        root = H.preparer(d, ("Couleurs",))
        (root / "shell.qml").write_text(H.ENTETE + "ShellRoot {\n" + H.OUTILS + SHELL % (json.dumps(cas), json.dumps(tailles)) + "\n}\n")
        _, sortie = H.lancer(root, delai=60)
    for e in H.ERREURS:
        if e in sortie:
            raise AssertionError(sortie)
    assert "FINI" in sortie, sortie
    return [json.loads(m) for m in re.findall(r"R:(\[.*\])", sortie)]


class HorsEcran(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tailles = [list(v) for v in COMPOSANTS.values()]
        cls.r = lancer([{}, {"ILE_RAYON": "carre"}, {"ILE_RAYON": "rond"}], cls.tailles)

    def test_defaut_inchange(self):
        self.assertEqual(self.r[0], [t[0] for t in self.tailles])

    def test_carre(self):
        self.assertEqual(self.r[1], [0] * len(self.tailles))

    def test_rond_plafonne_a_la_demi_taille(self):
        self.assertEqual(self.r[2], [min(t[0] * 2, min(t[1], t[2]) / 2) for t in self.tailles])


class Source(unittest.TestCase):
    def test_composants_appellent_couleurs_rayon(self):
        for f, (base, _, _) in COMPOSANTS.items():
            src = (H.QML / f).read_text()
            self.assertRegex(src, r"radius: [^\n]*Couleurs\.rayon\(%d, width, height\)" % base, f)

    def test_aucun_rayon_en_dur(self):
        for f in COMPOSANTS:
            for ligne in (H.QML / f).read_text().splitlines():
                if re.search(r"\bradius: \d", ligne):
                    # seul le point de 8 px (VpnPastille) reste rond en dur
                    self.assertIn("width: 8; height: 8", ligne, f"{f}: {ligne}")


if __name__ == "__main__":
    unittest.main()
