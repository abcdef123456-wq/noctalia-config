"""Quickshell 0.3 refuse un composant interne (« component X: … ») utilisé dans un AUTRE composant interne du même
fichier quand ce fichier est chargé comme type par shell.qml : « X is not a type », et toute l'île refuse de se
charger (vu avec Fiche.qml, alors que les tests, qui la chargent par Qt.createComponent, passaient). Un tel composant
va dans son propre fichier (GroupeTouches.qml)."""
from pathlib import Path
import re
import unittest

QML = Path(__file__).resolve().parents[1] / "home/.config/quickshell/nc-ile"


def composants(texte):
    """{nom: corps} des composants internes d'un fichier (corps : jusqu'à l'accolade fermante correspondante)."""
    res = {}
    for m in re.finditer(r"(?m)^\s*component\s+(\w+)\s*:\s*[\w.]+\s*\{", texte):
        i, prof = m.end(), 1
        while prof and i < len(texte):
            prof += {"{": 1, "}": -1}.get(texte[i], 0)
            i += 1
        res[m.group(1)] = texte[m.end():i]
    return res


class ComposantsInternes(unittest.TestCase):
    def test_pas_de_composant_interne_dans_un_autre(self):
        for f in sorted(QML.glob("*.qml")):
            c = composants(f.read_text())
            for nom, corps in c.items():
                for autre in c:
                    if autre != nom:
                        with self.subTest(fichier=f.name, composant=nom):
                            self.assertNotRegex(corps, r"\b" + autre + r"\s*\{",
                                                f"{f.name} : {nom} utilise {autre}, un autre composant interne : "
                                                "mets-le dans son propre fichier")


if __name__ == "__main__":
    unittest.main()
