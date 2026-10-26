"""Durcissement de l'île (lot D10) : tests statiques sur les .qml.
- Le mot de passe Wi-Fi n'entre pas dans la liste des commandes de Voulu (Etat.faire) et sa commande est oubliée.
- Le texte venu de l'extérieur (notifications, sessions d'agents) est affiché en texte brut.
- Les mouvements à 30 images/s s'arrêtent écran éteint ; les commandes qui peuvent ne jamais finir ont une garde."""
from pathlib import Path
import re
import unittest

QML = Path(__file__).resolve().parents[1] / "home/.config/quickshell/nc-ile"


def lire(nom):
    return (QML / nom).read_text()


class PageListe(unittest.TestCase):
    def setUp(self):
        self.src = lire("PageListe.qml")

    def test_mot_de_passe_hors_de_voulu(self):
        fonction = self.src[self.src.index("function connecterAvec"):self.src.index("function basculerBt")]
        self.assertNotIn("Etat.faire", fonction, "Etat.faire garde la commande (et son mot de passe) dans le modèle de Voulu")
        # « nmcli --ask » sur un stdin qui n'est pas un terminal : non fiable, et il peut rester bloqué malgré timeout
        self.assertNotIn("--ask", fonction)
        self.assertIn('["timeout", "30", "sh", "-c", "nmcli dev wifi connect', fonction)
        self.assertRegex(self.src, r"id: connexion\s*\n\s*onExited: \{ command = \[\]")

    def test_oubli_limite_au_wifi(self):
        self.assertIn("802-11-wireless", self.src)

    def test_bluetooth_par_argument_positionnel(self):
        self.assertNotRegex(self.src, r'"bluetoothctl pair "\s*\+')
        self.assertIn('bluetoothctl pair \\"$1\\"', self.src)
        self.assertRegex(self.src, r'\["timeout", "30", "sh", "-c", "bluetoothctl pair')

    def test_recherche_remise_a_zero(self):
        self.assertRegex(self.src, r"onVisibleChanged:[^\n]*recherche = false")


class TextePlat(unittest.TestCase):
    def test_banniere(self):
        src = lire("Banniere.qml")
        self.assertGreaterEqual(src.count("textFormat: Text.PlainText"), 3)
        for entite in ("&lt;", "&gt;", "&quot;", "&#39;", "&amp;"):
            self.assertIn(entite, src)
        self.assertLess(src.index("/&lt;/g"), src.index("/&amp;/g"), "&amp; se décode en dernier")

    def test_claude(self):
        src = lire("Claude.qml")
        self.assertIn("carte.s.projet || Agents.nom(carte.s); textFormat: Text.PlainText", src)
        self.assertIn("parent.modelData.texte; textFormat: Text.PlainText", src)

    def test_jarvis_unit_en_chaine(self):
        self.assertNotIn("unit:carte.item.unit}", lire("JarvisResultat.qml"))


class Energie(unittest.TestCase):
    def test_pas_arretes_ecran_eteint(self):
        for nom, motif in (("Etincelle.qml", r"running: e\.bouge[^\n]*Etat\.ecranVu"),
                           ("Compact.qml", r"Pas \{ running: [^\n]*Etat\.ecranVu")):
            src = lire(nom)
            for ligne in re.findall(r"^\s*(?:Pas \{ )?running: [^\n]*(?:bouge|clignote)[^\n]*$", src, re.M):
                self.assertIn("Etat.ecranVu", ligne, nom + " : " + ligne.strip())

    def test_minuterie_systeme(self):
        self.assertRegex(lire("Etat.qml"), r"etat\.pageSys && etat\.ecranVu; onTriggered")


class Gardes(unittest.TestCase):
    def test_memo(self):
        src = lire("Memo.qml")
        self.assertRegex(src, r"id: lecture\s*\n\s*onExited: memo\.suivant\(\)")
        self.assertIn("running: memo.courant !== null", src)

    def test_jarvis_90_secondes(self):
        self.assertRegex(lire("JarvisEtat.qml"), r"id: garde; interval: 90000; running: j\.enCours")

    def test_diagnostic_15_secondes(self):
        src = lire("Diagnostic.qml")
        self.assertIn("interval: 15000; running: d.etape === \"verif\"", src)


if __name__ == "__main__":
    unittest.main()


class DicteeLimite(unittest.TestCase):
    def test_fin_de_dictee_par_marque_surveillee_sans_minuterie(self):
        """La limite de 10 min de nc-dictee écrit nc-dictee-auto.txt : l'île le suit par inotify, jamais par sondage."""
        src = lire("Assistant.qml")
        bloc = src[src.index("id: dicteeAuto"):src.index("id: dictee\n")]
        self.assertIn('"/nc-dictee-auto.txt"', bloc)
        self.assertIn("watchChanges: true", bloc)
        self.assertIn("page.ecouteVocale = false", bloc)
        self.assertIn("!page.ecouteVocale", bloc, "un vieux fichier au démarrage ne dit rien")
        self.assertNotIn("Timer", bloc)
        self.assertNotRegex(src, r'"nc-dictee",\s*"status"', "l'île n'interroge pas nc-dictee status")
