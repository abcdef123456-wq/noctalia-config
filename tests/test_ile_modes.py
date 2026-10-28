"""Modes Concentration dans l'île, hors écran (Modes.qml, PageConcentration.qml, EditeurMode.qml, ChoixMode.qml).

Le vrai qs (« qs -p », jamais « qs -c nc-ile ») charge les vrais .qml avec des Etat, Reglages, Notifs et Partage de
remplacement, la vraie commande nc-modes et de faux nc-energie, nc-fond-jour-nuit et nc-reglages qui notent leurs arguments (jamais les
vrais). Cas : aucun mode par défaut = rien ne change, pas de pastille ; activer applique et pose la pastille ; le nom est caché en
partage d'écran ; désactiver remet l'état d'avant ; Ne pas déranger changé à la main est gardé ; le mode actif survit au
redémarrage sans rien réappliquer ; ILE_CONCENTRATION=non = rien ; noms en texte brut ; rien sans clic.
HOME, XDG_* et TMPDIR sont ceux d'un dossier temporaire court."""
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import textwrap
import unittest

from tests import _ile_hors_ecran as H
from tests.test_modes import FAUX_ENERGIE, FAUX_FOND, FAUX_REGLAGES

NOTIFS = "pragma Singleton\nimport QtQuick\nQtObject { property bool concentration: false }\n"
PARTAGE = "pragma Singleton\nimport QtQuick\nQtObject { property bool silence: false }\n"
ETAT = """
  property string ecranOuvert: ""
  property var appels: []
  function aller(n) { appels = appels.concat(["aller:" + n]) }
"""
SHELL = """
    property int i: 0
    property int essais: 0
    property bool lance: false
    property var etapes: [%s]
    Timer {
        interval: 200; running: true; repeat: true
        onTriggered: {
            if (racine.i >= racine.etapes.length) { console.log("FINI"); Qt.exit(0); return }
            var e = racine.etapes[racine.i]
            if (!racine.lance) { if (e.f) e.f(); racine.lance = true; racine.essais = 0; return }
            if (e.c()) { racine.i++; racine.lance = false; return }
            if (++racine.essais > 60) { console.error("ECHEC: " + e.m); Qt.exit(2) }
        }
    }
"""


def pause(n=6):
    return "{ f: null, n: 0, c: function() { return ++racine.etapes[racine.i].n > %d }, m: \"pause\" }" % n


def etape(c, m, f="null"):
    return "{ f: %s, c: function() { return %s }, m: %s }" % (f if f == "null" else "function() { %s }" % f, c, json.dumps(m))


@unittest.skipUnless(shutil.which("qs"), "Quickshell requis")
class HorsEcran(unittest.TestCase):
    def lancer(self, etapes, valeurs=None, avant=None, page=False, delai=90):
        os.makedirs("/tmp/claude-1000", exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="nq-", dir="/tmp/claude-1000") as d:
            noms = ["Modes", "Couleurs"] + (["PageConcentration", "EditeurMode", "ChoixMode", "BoutonEnergie", "Texte", "Ico"] if page else [])
            root = H.preparer(d, noms, etat=ETAT, extra={"Notifs.qml": NOTIFS, "Partage.qml": PARTAGE},
                              singletons=("Modes", "Notifs", "Partage"))
            reglages = (root / "Reglages.qml").read_text()
            (root / "Reglages.qml").write_text(reglages.replace("property var valeurs: ({})", "property var valeurs: (" + json.dumps(valeurs or {}) + ")"))
            (root / "faux").mkdir()
            for nom, texte in (("nc-energie", FAUX_ENERGIE), ("nc-fond-jour-nuit", FAUX_FOND), ("nc-reglages", FAUX_REGLAGES)):
                (root / "bin" / nom).write_text(texte)
                (root / "bin" / nom).chmod(0o755)
            shutil.copy2(H.REPO / "home/.local/bin/nc-modes", root / "bin/nc-modes")
            (root / "config/nc").mkdir(parents=True, exist_ok=True)
            if valeurs:
                (root / "config/nc/reglages.conf").write_text("".join("%s=%s\n" % kv for kv in valeurs.items()))
            if avant:
                avant(root)
            contenu = "Item { id: contenu; width: 400; height: 500; PageConcentration { anchors.fill: parent } }\n" if page else ""
            (root / "shell.qml").write_text(H.ENTETE + "ShellRoot {\n    id: racine\n" + H.OUTILS + SHELL % ",\n".join(etapes) + contenu + "\n}\n")
            env = dict(NC_MODES_OUTILS=str(root / "bin"), FAUX_ETAT=str(root / "faux"), NC_LANGUE="fr")
            code, sortie = H.lancer(root, delai=delai, **env)
            for e in H.ERREURS:
                self.assertNotIn(e, sortie, sortie)
            self.assertIn("FINI", sortie, sortie)
            journal = (root / "faux/journal").read_text().splitlines() if (root / "faux/journal").exists() else []
            return sortie, journal, root

    @staticmethod
    def ecrire_modes(root, modes, etat=None):
        (root / "config/nc").mkdir(parents=True, exist_ok=True)
        (root / "config/nc/modes.json").write_text(json.dumps({"version": 1, "modes": modes}))
        if etat is not None:
            (root / "state/nc").mkdir(parents=True, exist_ok=True)
            (root / "state/nc/modes-etat.json").write_text(json.dumps(etat))

    TRAVAIL = {"id": "travail", "nom": "Travail", "icone": "work", "dnd": "oui", "energie": "", "fond": "garder", "notifs_ia": "garder"}
    PRET = etape("Modes.restaure", "Modes jamais lu")

    def test_aucun_mode_rien_ne_change(self):
        _, journal, root = self.lancer([self.PRET,
            pause(),
            etape("Modes.modes.length === 0 && !Modes.pastille && !Modes.pagePossible && !Modes.aModes && Notifs.concentration === false",
                  "un mode ou une pastille sans mode créé")])
        self.assertEqual(journal, [])
        self.assertFalse((root / "config/nc/modes.json").exists() or (root / "state/nc/modes-etat.json").exists())

    def test_activer_pastille_partage_et_desactiver(self):
        _, journal, root = self.lancer([self.PRET,
            etape("Modes.modes.length === 1 && !Modes.pastille && Notifs.concentration === false", "mode non lu ou pastille sans clic"),
            etape("Modes.actif === 'travail' && Notifs.concentration === true && Modes.pastille && Modes.nomVisible === 'Travail'",
                  "activation", "Modes.activer('travail')"),
            etape("Modes.pastille && Modes.nomVisible === ''", "nom visible en partage d'écran", "Partage.silence = true"),
            etape("Modes.nomVisible === 'Travail'", "nom absent après le partage", "Partage.silence = false"),
            etape("Modes.actif === '' && !Modes.pastille && Notifs.concentration === false", "désactivation", "Modes.sortir()")],
            avant=lambda r: self.ecrire_modes(r, [self.TRAVAIL]))
        self.assertEqual(journal, [])                                      # ce mode ne règle que Ne pas déranger
        self.assertFalse((root / "state/nc/modes-etat.json").exists())

    def test_dnd_change_a_la_main_pendant_le_mode(self):
        calme = dict(self.TRAVAIL, id="calme", nom="Calme", dnd="non")
        self.lancer([self.PRET,
            etape("true", "dnd", "Notifs.concentration = true"),
            etape("Modes.actif === 'calme' && Notifs.concentration === false", "activation", "Modes.activer('calme')"),
            etape("Notifs.concentration === true", "main", "Notifs.concentration = true"),
            etape("Modes.actif === '' && Notifs.concentration === true", "ancien réglage remis par-dessus le choix", "Modes.sortir()")],
            avant=lambda r: self.ecrire_modes(r, [calme]))

    def test_redemarrage_remet_le_mode_sans_rien_reappliquer(self):
        etat = {"version": 1, "actif": "travail", "nom": "Travail", "icone": "work", "dnd": {"avant": False, "pose": True},
                "energie": {"pose": "calme", "avant_actif": None}}
        _, journal, _ = self.lancer([self.PRET,
            etape("Modes.actif === 'travail' && Modes.pastille && Notifs.concentration === true && Modes.actifNom === 'Travail'",
                  "mode actif non relu au démarrage")],
            avant=lambda r: self.ecrire_modes(r, [self.TRAVAIL], etat))
        self.assertEqual(journal, [])                                      # rien n'est relancé : ni énergie, ni fond, ni réglage

    def test_reglage_coupe_rien(self):
        _, journal, root = self.lancer([etape("true", "départ", "Modes.activer('travail'); Modes.ouvrirPage()"), pause(),
            etape("Modes.modes.length === 0 && Modes.actif === '' && !Modes.pastille && !Modes.pagePossible && Notifs.concentration === false",
                  "mode actif malgré ILE_CONCENTRATION=non")],
            valeurs={"ILE_CONCENTRATION": "non"}, avant=lambda r: self.ecrire_modes(r, [self.TRAVAIL]))
        self.assertEqual(journal, [])
        self.assertFalse((root / "state/nc/modes-etat.json").exists())

    def test_page_exemples_clic_et_texte_brut(self):
        _, journal, root = self.lancer([self.PRET,
            etape("tous(contenu, 'creerExemple').length === 3 && tous(contenu, 'ligneMode').length === 0", "trois propositions au départ"),
            etape("tous(contenu, 'ligneMode').length === 1 && Modes.modes[0].nom === 'Travail' && Modes.modes[0].dnd === 'oui'",
                  "exemple Travail non créé par le clic", "tous(contenu, 'creerExemple')[0].clic()"),
            etape("tous(contenu, 'ligneMode').length === 2 && tous(contenu, 'creerExemple').length === 2", "nom libre non créé",
                  "Modes.creer('<b>x</b> & <i>y</i>', '')"),
            etape("Modes.actif !== '' && Modes.pastille && Notifs.concentration === false", "clic sur le mode", "tous(contenu, 'activerMode')[1].clicked(null)"),
            etape("verifier(Modes.modes[1].nom === '<b>x</b> & <i>y</i>', 'nom altéré'); true", "nom"),
            etape("tous(contenu, 'nomMode').length === 0", "éditeur ouvert tout seul")],
            page=True)
        self.assertEqual(journal, [])

    def test_aucun_minuteur_ni_lancement_sans_clic(self):
        src = (H.QML / "Modes.qml").read_text()
        self.assertNotIn("Timer", src)


if __name__ == "__main__":
    unittest.main()
