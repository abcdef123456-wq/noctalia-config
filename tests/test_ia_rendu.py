"""Rendu des réponses de l'IA dans l'île (NotifIA, PourquoiChaleur, ExpliquerMaj, DemandeIA) : tout est en texte brut
(Texte.qml, PlainText), jamais de Markdown ni de rich text, aucun lien ni image distante, et DemandeIA passe toujours
--sans-outils (le texte vient de n'importe qui : jamais JARVIS ni un moteur à outils)."""
from pathlib import Path
import re
import unittest

QML = Path(__file__).resolve().parents[1] / "home/.config/quickshell/nc-ile"
FICHIERS = ("NotifIA.qml", "PourquoiChaleur.qml", "ExpliquerMaj.qml", "DemandeIA.qml", "IaPrete.qml")


class Rendu(unittest.TestCase):
    def code(self, nom):
        return re.sub(r"//.*", "", (QML / nom).read_text())

    def test_texte_brut_partout(self):
        self.assertIn("textFormat: Text.PlainText", (QML / "Texte.qml").read_text())
        for nom in FICHIERS:
            c = self.code(nom)
            self.assertNotRegex(c, r"MarkdownText|RichText|StyledText|AutoText|textFormat", nom)
            self.assertNotRegex(c, r"(?m)^\s*(Text|TextEdit|TextArea|Label)\s*\{", nom + " : seulement Texte.qml (PlainText)")

    def test_ni_lien_ni_image_distante(self):
        for nom in FICHIERS:
            c = self.code(nom)
            self.assertNotRegex(c, r"onLinkActivated|onLinkHovered|openUrlExternally|\bImage\s*\{|AnimatedImage|https?://|<a |<img", nom)

    def test_toute_reponse_dans_un_texte(self):
        for nom, objets in (("NotifIA.qml", ("nc-notif-ia-resume", "nc-notif-ia-erreur", "nc-notif-ia-suggestion-")),
                            ("PourquoiChaleur.qml", ("pourquoiChaleurReponse", "pourquoiChaleurErreur")),
                            ("ExpliquerMaj.qml", ("expliquerMajReponse", "expliquerMajErreur"))):
            src = (QML / nom).read_text()
            for o in objets:
                self.assertIn('objectName: "' + o, src, nom + " " + o)
        # les suggestions : Texte à l'intérieur de leur rectangle
        self.assertRegex((QML / "NotifIA.qml").read_text(), r"Texte \{ id: lsg;")

    def test_demande_ia_passe_toujours_sans_outils(self):
        c = self.code("DemandeIA.qml")
        m = re.search(r"command: (\[.+)", c)
        self.assertIn('"--sans-outils"', m[1])
        self.assertNotRegex(m[1], r"d\.sans|\? \[\]|if ")           # inconditionnel : aucune option pour le retirer
        self.assertNotIn("sans-outils", re.sub(r'"--sans-outils"', "", m[1]))
        for nom in ("PourquoiChaleur.qml", "ExpliquerMaj.qml", "NotifIA.qml"):
            self.assertIn("local: true", self.code(nom), nom + " : l'IA de ce PC en préférence")


if __name__ == "__main__":
    unittest.main()
