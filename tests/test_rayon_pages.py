"""Rayon des cartes des pages de l'île : elles suivent ILE_RAYON via Couleurs.rayon, comme les composants communs.

- Source : plus aucun « radius: <nombre> » en dur dans les pages, sauf les cercles listés ci-dessous.
- Rendu : au réglage par défaut (100 %), le rendu hors écran est identique à l'octet à celui des mêmes pages
  où chaque Couleurs.rayon(N, width, height) est remis en « radius: N » (donc au rendu d'avant le changement)."""
from tests import _isolation  # noqa: F401  (HOME, XDG_*, langue : avant tout le reste)
import importlib.util
import re
import shutil
import tempfile
import unittest
from pathlib import Path
import subprocess
from unittest.mock import patch

from tests import _ile_hors_ecran as H
from tests.test_ile_demarrage import lignes_en_erreur

DEPOT = Path(__file__).resolve().parents[1]
QML = DEPOT / "home/.config/quickshell/nc-ile"
LITTERAL = re.compile(r"radius: *[0-9]+(?:\.[0-9]+)?(?![0-9.]|\s*[/*+\-?])")

# Cercles et pastilles rondes (largeur = hauteur = 2 x rayon) : volontairement laissés en dur, ils doivent rester ronds
# quel que soit le réglage. fichier : nombre de cercles.
CERCLES = {
    "Assistant.qml": 3, "AssistantOrbe.qml": 1, "Calendrier.qml": 3, "Centre.qml": 3, "Charge.qml": 1, "ChoixTheme.qml": 1,
    "Claude.qml": 2, "CodeApercu.qml": 1, "CodeProjet.qml": 1, "Compact.qml": 2, "Fenetres.qml": 1, "Fiche.qml": 2,
    "FormeIle.qml": 2, "GarminTiroir.qml": 2, "Ile.qml": 2, "Jarvis.qml": 1, "Jeu.qml": 1, "PageAppel.qml": 1, "PageListe.qml": 2,
    "PageNotifs.qml": 2, "PageResume.qml": 1, "PageTerminal.qml": 1, "PresseAction.qml": 1,
    "Projection.qml": 2, "Recherche.qml": 1, "Son.qml": 2, "Systeme.qml": 3, "VpnCarte.qml": 1, "VpnPastille.qml": 1,
    "Vue.qml": 2,
}


class Source(unittest.TestCase):
    def test_plus_de_rayon_en_dur(self):
        reste = {}
        for f in sorted(QML.glob("*.qml")):
            n = sum(len(LITTERAL.findall(l)) for l in f.read_text().split("\n"))
            if n:
                reste[f.name] = n
        self.assertEqual(reste, CERCLES)


@unittest.skipUnless(shutil.which("qs"), "Quickshell requis")
class Rendu(unittest.TestCase):
    def test_defaut_identique(self):
        spec = importlib.util.spec_from_file_location("rendu_ile", DEPOT / "outils/rendu-ile.py")
        outil = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(outil)
        with tempfile.TemporaryDirectory(prefix="nc-rpages-") as d:
            avant = Path(d) / "avant-qml"
            shutil.copytree(str(QML), str(avant))
            for f in avant.glob("*.qml"):
                f.write_text(re.sub(r"Couleurs\.rayon\(([0-9.]+), width, height\)", r"\1", f.read_text()))
            for etat in ("page", "recherche", "bureau"):
                for essai in range(2):
                    png = {}
                    for nom, qml in (("apres", QML), ("avant", avant)):
                        outil.QML = qml
                        sortie = Path(d) / nom
                        sortie.mkdir(exist_ok=True)
                        p, journal = outil.rendre(etat, str(sortie), None, None)
                        self.assertTrue(p, journal)
                        png[nom] = Path(p).read_bytes()
                    if png["avant"] == png["apres"] or essai == 1:
                        self.assertEqual(png["avant"], png["apres"], etat)
                        break
    def test_cible_reglages_dans_le_coin_rond_et_section_de_la_page(self):
        spec = importlib.util.spec_from_file_location("rendu_coins", DEPOT / "outils/rendu-ile.py")
        outil = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(outil)
        pilote = H.OUTILS + """
    Timer { interval: 1500; running: true; onTriggered: {
        var nom = vs.instances[0].modelData.name || "ecran-rendu"
        Etat.basculer(nom, true); Etat.aller("systeme"); controle.start()
    } }
    Timer { id: controle; interval: 2000; onTriggered: {
        var fen = vs.instances[0], fond = fen.ilot
        var bouton = trouver(fond, "nc-ile-reglages")
        verifier(fen.ouverte && fen.points && bouton && bouton.visible, "page Système avec navigation")
        verifier(fond.radius > 50 && fond.radius <= 16 / (1 - Math.SQRT1_2), "rayon rond borné")
        var p = bouton.mapToItem(fond, bouton.width, bouton.height), r = fond.radius
        var dx = Math.max(0, p.x - (fond.width - r)), dy = Math.max(0, p.y - (fond.height - r))
        verifier(p.x <= fond.width && p.y <= fond.height && dx * dx + dy * dy <= r * r,
                 "coin extérieur de la cible dans le fond : " + p)
        verifier(bouton.vue === "systeme" && bouton.section === "Mises à jour", "section choisie par nom de page")
        trouver(bouton, "bouton-reglages-zone").clicked(null)
        verifier(!fen.ouverte, "clic ferme la page"); fin.start()
    } }
    Timer { id: fin; interval: 300; onTriggered: { console.log("FINI"); Qt.quit() } }
"""
        for forme in ("pilule", "encoche"):
            with self.subTest(forme=forme), tempfile.TemporaryDirectory(prefix="nc-coins-") as d:
                root = Path(d)
                conf = root / "reglages.conf"
                conf.write_text("ILE_RAYON=rond\nILE_FORME=" + forme
                                + "\nILE_PAGE_SYSTEME=oui\nILE_PAGE_SON=oui\nILE_PAGE_RESEAU=oui\nILE_PAGE_BLUETOOTH=oui\n")
                with patch.object(outil, "PILOTE", pilote):
                    ile = outil.preparer(root, "page", conf, None)
                # Remplacer le lien de la copie, jamais le script réel de nc-reglages.
                faux = root / "home/.local/bin/nc-reglages"
                faux.unlink()
                faux.write_text('#!/bin/sh\nprintf "%s\\n" "$*" >> "' + str(root / "journal") + '"\n')
                faux.chmod(0o755)
                # Même option que rendu-ile.py : sans elle, certains qs (0.3.2 du COPR Fedora) filtrent console.log.
                resultat = subprocess.run(["qs", "--no-color", "--log-rules", "qml.debug=true", "-p", str(ile / "shell.qml")],
                                          env=outil.environnement(root, root / "inutile.png"),
                                          capture_output=True, text=True, timeout=15)
                sortie = resultat.stdout + resultat.stderr
                self.assertEqual(resultat.returncode, 0, sortie)
                self.assertEqual(lignes_en_erreur(sortie), [], sortie)
                self.assertIn("FINI", sortie)
                self.assertEqual([l for l in H.journal(root).splitlines() if l.startswith("fenetre ")],
                                 ["fenetre Mises à jour"])


if __name__ == "__main__":
    unittest.main()
