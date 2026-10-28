"""EnergieProfils.qml et BoutonEnergie.qml (carte « Profils d'énergie poussés » de la page Santé), chargés hors écran avec le
vrai qs (qs -p) et un faux nc-energie qui note ses arguments : la carte n'existe pas sans capacité, les profils sont
listés en texte brut, l'aperçu s'ouvre sur un clic, Appliquer ne passe que l'identifiant (et --oui-hz seulement quand
l'aperçu le demande), Revenir, le bouton de l'IA caché quand l'IA est coupée. Aucune erreur QML."""
import json
from pathlib import Path
import shutil
import tempfile
import textwrap
import unittest

from tests.test_conso_pourquoi import ENTETE_QML, OUTILS_QML, lancer_qs
from tests.test_sante import QML, bouchons, faux

PROFILS = [
    {"id": "cours-bureautique", "nom": "Cours <b>bureautique</b>", "description": "Sobre.", "film_batterie": False, "source": "regles",
     "reglages": 5, "materiel": True, "valide": True, "raison": ""},
    {"id": "film-sur-batterie", "nom": "Film sur batterie", "description": "Autonomie.", "film_batterie": True, "source": "ia",
     "reglages": 3, "materiel": False, "valide": True, "raison": ""},
    {"id": "vieux", "nom": "Vieux", "description": "", "film_batterie": False, "source": "ia", "reglages": 0, "materiel": False,
     "valide": False, "raison": "clé inconnue : truc"}]


def apercu(film):
    return {"id": "film-sur-batterie" if film else "cours-bureautique", "nom": "N", "description": "d", "film_batterie": film,
            "changements": [{"cle": "profil", "libelle": "Profil d'énergie", "avant": "Équilibré", "apres": "Économie", "niveau": 1}],
            "inchanges": 0, "avertissements": [], "applicable": True, "raison": "", "demande_hz": film, "hz_max": 165,
            "texte_hz": "L'écran passera à 60 Hz au lieu de 165 Hz." if film else ""}


@unittest.skipUnless(shutil.which("qs"), "Quickshell requis")
class Carte(unittest.TestCase):
    def executer(self, liste, scenario):
        with tempfile.TemporaryDirectory(prefix="nc-energie-qml-") as d:
            root = Path(d)
            bouchons(root, d)
            for nom in ("EnergieProfils", "BoutonEnergie", "Texte", "Ico", "Module", "Couleurs"):
                shutil.copy2(QML / (nom + ".qml"), root)
            (root / "qmldir").write_text("\n".join(("singleton " if n in ("Couleurs", "Reglages", "Etat") else "") + n + " 1.0 " + n + ".qml"
                                                   for n in ("EnergieProfils", "BoutonEnergie", "Texte", "Ico", "Module", "Couleurs", "Reglages", "Etat")))
            (root / "liste.json").write_text(json.dumps(liste))
            (root / "apercu-cours.json").write_text(json.dumps(apercu(False)))
            (root / "apercu-film.json").write_text(json.dumps(apercu(True)))
            faux(root / "bin", "nc-energie", textwrap.dedent(f'''\
                echo "nc-energie $*" >> "{root}/appels"
                case "$1" in
                  liste) cat "{root}/liste.json" ;;
                  apercu) case "$2" in film-sur-batterie) cat "{root}/apercu-film.json" ;; *) cat "{root}/apercu-cours.json" ;; esac ;;
                  appliquer|revenir) echo '{{"ok": true, "message": "Fait."}}' ;;
                  proposer) echo '{{"source": "regles", "raison": "", "profils": [], "rejets": []}}' ;;
                esac
                '''))
            (root / "shell.qml").write_text(ENTETE_QML + textwrap.dedent('''\
                ShellRoot {
                    id: racine
                    property int etape: 0
                    property real marque: 0
                ''') + OUTILS_QML + textwrap.dedent('''\
                    function attendre(ms) { if (marque === 0) marque = Date.now(); if (Date.now() - marque < ms) return true; marque = 0; return false }
                    Window { id: w; visible: true; width: 400; height: 700; EnergieProfils { id: page; objectName: "page"; width: 378; affichee: true } }
                    Timer { interval: 50; running: true; repeat: true; onTriggered: {
                ''') + scenario + "\n} }\nTimer { interval: 10000; running: true; onTriggered: Qt.exit(9) }\n}")
            r, sortie = lancer_qs(root, d, delai=25)
            self.assertEqual(r.returncode, 0, sortie)
            return (root / "appels").read_text().splitlines()

    def test_parcours(self):
        appels = self.executer({"profils": PROFILS, "ia": True, "disponible": True, "actif": "cours-bureautique", "assistant_root": True}, '''
if (etape === 0) { if (attendre(900)) return
  verifier(page.visible, "carte cachée alors que le PC a des capacités")
  var p = tous(page, "profilPousse"); verifier(p.length === 3, "profils : " + p.length)
  verifier(p[0].modelData.nom === "Cours <b>bureautique</b>", "nom brut")
  verifier(trouver(page, "boutonIaEnergie").visible, "bouton IA caché alors que l'IA est permise")
  verifier(!trouver(page, "apercuEnergie").visible, "aperçu ouvert d'avance")
  verifier(cliquer(page, "profilPousse"), "clic sur un profil")
  marque = Date.now(); etape++ }
else if (etape === 1) { if (attendre(700)) return
  verifier(trouver(page, "apercuEnergie").visible, "aperçu absent après le clic")
  verifier(page.choisi === "cours-bureautique", "profil choisi : " + page.choisi)
  verifier(cliquer(page, "boutonAppliquerEnergie"), "bouton Appliquer")
  marque = Date.now(); etape++ }
else if (etape === 2) { if (attendre(900)) return
  verifier(page.message === "Fait.", "message : " + page.message)
  verifier(cliquer(page, "boutonRevenirEnergie"), "bouton Revenir")
  marque = Date.now(); etape++ }
else if (etape === 3) { if (attendre(700)) return
  verifier(cliquer(page, "boutonReglesEnergie"), "bouton des règles")
  marque = Date.now(); etape++ }
else if (etape === 4) { if (attendre(700)) return; Qt.quit() }
''')
        self.assertIn("nc-energie liste --json", appels)
        self.assertIn("nc-energie apercu cours-bureautique --json", appels)
        self.assertIn("nc-energie appliquer cours-bureautique --oui --json", appels, "pas de --oui-hz sans baisse de fréquence")
        self.assertIn("nc-energie revenir --json", appels)
        self.assertIn("nc-energie proposer --regles --json", appels)
        self.assertFalse(any("--oui-hz" in l for l in appels))
        self.assertFalse(any(l.startswith("nc-energie proposer --ia") for l in appels), "l'IA n'est appelée que sur un clic")

    def test_film_confirme_le_60_hz(self):
        appels = self.executer({"profils": PROFILS, "ia": False, "disponible": True, "actif": None, "assistant_root": True}, '''
if (etape === 0) { if (attendre(900)) return
  verifier(!trouver(page, "boutonIaEnergie").visible, "bouton IA visible alors que l'IA est coupée")
  page.ouvrir("film-sur-batterie"); marque = Date.now(); etape++ }
else if (etape === 1) { if (attendre(700)) return
  var b = trouver(page, "boutonAppliquerEnergie")
  verifier(b.texte.indexOf("60 Hz") >= 0, "le bouton ne dit pas 60 Hz : " + b.texte)
  verifier(page.apercu.texte_hz.indexOf("60 Hz au lieu de 165 Hz") >= 0, "phrase de confirmation")
  verifier(cliquer(page, "boutonAppliquerEnergie"), "bouton Appliquer")
  marque = Date.now(); etape++ }
else if (etape === 2) { if (attendre(700)) return; Qt.quit() }
''')
        self.assertIn("nc-energie appliquer film-sur-batterie --oui --oui-hz --json", appels)

    def test_identifiant_douteux_refuse(self):
        appels = self.executer({"profils": PROFILS, "ia": False, "disponible": True, "actif": None, "assistant_root": False}, '''
if (etape === 0) { if (attendre(900)) return
  page.ouvrir("a; rm -rf ~"); page.ouvrir("../x"); page.ouvrir("")
  verifier(page.choisi === "", "identifiant douteux accepté : " + page.choisi)
  marque = Date.now(); etape++ }
else if (etape === 1) { if (attendre(500)) return; Qt.quit() }
''')
        self.assertEqual([l for l in appels if "apercu" in l], [])

    def test_carte_cachee_sans_capacite(self):
        self.executer({"profils": [], "ia": False, "disponible": False, "actif": None, "assistant_root": False}, '''
if (etape === 0) { if (attendre(900)) return
  verifier(!page.visible, "carte visible sans capacité")
  Qt.quit() }
''')


if __name__ == "__main__":
    unittest.main()
