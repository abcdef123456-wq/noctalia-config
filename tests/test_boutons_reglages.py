"""Boutons ⚙ des panneaux graphiques (BoutonReglages.qml, ReglagesIle.qml) : chaque outil graphique ouvre SA section dans la
fenêtre des réglages (nc-reglages fenetre SECTION, en argv). Règle permanente : tout réglage d'un outil graphique se fait
aussi dans son interface.

- Source : les panneaux VPN, Clés des IA, JARVIS, l'île (ReglagesIle) et la page Système ont leur bouton ; toutes les sections
  nommées existent dans nc-reglages.
- Hors écran, avec le vrai qs lancé par « qs -p » (jamais l'île réelle) et un faux nc-reglages qui note seulement ses
  arguments : le clic appelle « nc-reglages fenetre SECTION » ; l'île choisit la section de la page affichée.
HOME et XDG_* isolés, sans Wayland."""
import os
from pathlib import Path
import re
import runpy
import shutil
import tempfile
import textwrap
import unittest
import warnings
from unittest.mock import patch

from tests import _ile_hors_ecran as H

REPO = Path(__file__).resolve().parents[1]
QML = REPO / "home/.config/quickshell/nc-ile"


def sections_connues():
    with tempfile.TemporaryDirectory() as d, patch.dict(os.environ, HOME=d), warnings.catch_warnings():
        warnings.simplefilter("ignore", ResourceWarning)
        m = runpy.run_path(str(REPO / "home/.local/bin/nc-reglages"))
        # toutes les sections du catalogue : celles qui dépendent de l'île ne sont « visibles » que si elle tourne (elle tourne,
        # puisque le bouton est dans l'un de ses panneaux)
        toutes = {r.section for r in m["REGLAGES"]} | {"Raccourcis", "Nouveautés"}
        return lambda nom: nom in toutes


class Source(unittest.TestCase):
    def test_chaque_panneau_a_son_bouton_et_une_section_qui_existe(self):
        demandee = sections_connues()
        attendu = {"Vpn.qml": "nc-vpn-reglages", "ClesIA.qml": "nc-cles-reglages", "Jarvis.qml": "nc-jarvis-reglages"}
        for nom, objet in attendu.items():
            src = (QML / nom).read_text()
            m = re.search(r'BoutonReglages \{[^}]*objectName: "%s"[^}]*section: "([^"]+)"|BoutonReglages \{[^}]*section: "([^"]+)"[^}]*objectName: "%s"' % (objet, objet), src)
            self.assertTrue(m, nom + " : un BoutonReglages avec sa section")
            self.assertTrue(demandee(m.group(1) or m.group(2)), nom + " : section inconnue de nc-reglages")
        ile = (QML / "Ile.qml").read_text()
        self.assertIn("ReglagesIle {", ile)
        self.assertIn("vue: Etat.vue", ile)
        sections = re.search(r"sections: \(\{(.*?)\}\)", (QML / "ReglagesIle.qml").read_text(), re.S).group(1)
        for s in re.findall(r':\s*"([^"]+)"', sections) + ["Île"]:
            self.assertTrue(demandee(s), "ReglagesIle : section inconnue : " + s)
        self.assertIn('"nc-reglages", "fenetre"', (QML / "Systeme.qml").read_text())

    def test_bouton_en_argv_sans_shell_ni_composant_inline(self):
        src = (QML / "BoutonReglages.qml").read_text()
        self.assertIn('"/.local/bin/nc-reglages", "fenetre"]', src)
        self.assertIn("Quickshell.execDetached(cmd)", src)
        for nom in ("BoutonReglages", "ReglagesIle", "PastilleChoix"):
            code = (QML / (nom + ".qml")).read_text()
            self.assertNotRegex(code, r"(?m)^\s*component ", nom)
            self.assertNotRegex(code, r'"sh"|bash -c', nom)


@unittest.skipUnless(shutil.which("qs"), "Quickshell requis")
class HorsEcran(unittest.TestCase):
    def lancer(self, corps):
        with tempfile.TemporaryDirectory(prefix="nc-bouton-") as d:
            root = H.preparer(d, ("BoutonReglages", "ReglagesIle", "Texte", "Ico", "Couleurs"))
            faux = root / "home/.local/bin"
            faux.mkdir(parents=True)
            f = faux / "nc-reglages"
            f.write_text('#!/bin/sh\necho "nc-reglages $*" >> "%s/journal"\n' % root)
            f.chmod(0o755)
            (root / "shell.qml").write_text(H.ENTETE + textwrap.dedent('''\
                ShellRoot {
                    property int ouverts: 0
                    function cliquer(o) { trouver(o, "bouton-reglages-zone").clicked(null) }
                    Window { id: w; visible: true; width: 200; height: 100; color: "black" }
                ''') + H.OUTILS + textwrap.dedent(corps) + "\n}\n")
            code, sortie = H.lancer(root)
            for e in H.ERREURS:
                self.assertNotIn(e, sortie, sortie)
            self.assertIn("FINI", sortie, sortie)
            return H.journal(root).splitlines()

    def test_clic_ouvre_la_section_et_previent(self):
        j = self.lancer('''
            Timer { interval: 100; running: true; onTriggered: {
                var c = Qt.createComponent("BoutonReglages.qml"); verifier(c.status === Component.Ready, c.errorString())
                var b = c.createObject(w.contentItem, { section: "Terminal" })
                b.ouvert.connect(function () { ouverts++ })
                cliquer(b); verifier(ouverts === 1, "le signal ouvert part")
                var s = c.createObject(w.contentItem, {}); cliquer(s)
                attente.start() } }
            Timer { id: attente; interval: 800; onTriggered: { console.log("FINI"); Qt.exit(0) } }
        ''')
        self.assertEqual([l for l in j if "nc-reglages" in l], ["nc-reglages fenetre Terminal", "nc-reglages fenetre"], j)

    def test_ile_choisit_la_section_de_la_page(self):
        j = self.lancer('''
            Timer { interval: 100; running: true; onTriggered: {
                var c = Qt.createComponent("ReglagesIle.qml"); verifier(c.status === Component.Ready, c.errorString())
                var vues = ["charge", "son", "claude", "systeme", "meteo", "concentration"]
                for (var i = 0; i < vues.length; i++) cliquer(c.createObject(w.contentItem, { vue: vues[i] }))
                attente.start() } }
            Timer { id: attente; interval: 1200; onTriggered: { console.log("FINI"); Qt.exit(0) } }
        ''')
        self.assertEqual([l for l in j if "nc-reglages" in l], [
            "nc-reglages fenetre Énergie", "nc-reglages fenetre Son et luminosité", "nc-reglages fenetre Agents IA (coucou)",
            "nc-reglages fenetre Mises à jour", "nc-reglages fenetre Île", "nc-reglages fenetre Île"], j)


if __name__ == "__main__":
    unittest.main()
