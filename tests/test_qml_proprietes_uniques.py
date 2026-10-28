"""Une même propriété (ou un même gestionnaire, Component.onCompleted…) posée deux fois sur l'objet racine d'un .qml
de l'île : Quickshell refuse tout le fichier (« Property value set multiple times ») et l'île ne démarre plus. Deux
branches correctes chacune peuvent le produire en fusionnant (shell.qml, page Santé et Super + X). qmllint ne le voit
pas : ce test lit les lignes de premier niveau de l'objet racine (indentées de 4 espaces)."""
from collections import Counter
from pathlib import Path
import re
import unittest

QML = Path(__file__).resolve().parents[1] / "home/.config/quickshell/nc-ile"
LIGNE = re.compile(r"^    ((?:[A-Za-z_][A-Za-z0-9_]*\.)*[A-Za-z_][A-Za-z0-9_]*)\s*:(?!:)")


def doublons(texte):
    """Les noms posés plusieurs fois au premier niveau de l'objet racine (hors déclarations « property … »)."""
    noms, profondeur = [], 0
    for l in texte.splitlines():
        if profondeur == 1:
            m = LIGNE.match(l)
            if m and not l.lstrip().startswith(("property ", "readonly ", "required ", "signal ", "function ", "//")):
                noms.append(m[1])
        code = re.sub(r'"(?:\\.|[^"\\])*"|//.*', "", l)
        profondeur += code.count("{") - code.count("}")
    return [n for n, k in Counter(noms).items() if k > 1]


class ProprietesUniques(unittest.TestCase):
    def test_aucune_propriete_racine_posee_deux_fois(self):
        for f in sorted(QML.glob("*.qml")):
            with self.subTest(fichier=f.name):
                self.assertEqual(doublons(f.read_text(encoding="utf-8")), [], f.name)

    def test_le_test_voit_un_doublon(self):
        self.assertEqual(doublons("Item {\n    Component.onCompleted: a()\n    width: 3\n    Component.onCompleted: b()\n}\n"),
                         ["Component.onCompleted"])
        self.assertEqual(doublons("Item {\n    Rectangle {\n        width: 1\n    }\n    Rectangle {\n        width: 2\n    }\n}\n"), [])


if __name__ == "__main__":
    unittest.main()
