"""qmllint sur l'île (nc-ile) : seulement les vraies fautes, pas le bruit.

qmllint ne connaît pas les types de Quickshell : il signale des milliers de « missing-property » et
« unqualified » sans intérêt. Ce test ne retient que deux catégories :
- id-shadows-member : un id qui masque une propriété du parent (ex. `MouseArea { id: z }` cache `z`) ;
- equality-type-coercion : `==` ou `!=` qui convertissent les types en douce.
qmllint est lancé une seule fois sur tous les fichiers ; le test est sauté s'il est absent."""
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[1]
QML = REPO / "home/.config/quickshell/nc-ile"
CATEGORIES = {"id-shadows-member", "equality-type-coercion"}


def trouver_qmllint():
    for chemin in ("/usr/lib/qt6/bin/qmllint", "/usr/lib64/qt6/bin/qmllint", "/usr/lib/x86_64-linux-gnu/qt6/bin/qmllint"):
        if Path(chemin).is_file():
            return chemin
    return shutil.which("qmllint6") or shutil.which("qmllint")


QMLLINT = trouver_qmllint()


@unittest.skipUnless(QMLLINT, "qmllint absent")
class QmllintIle(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fichiers = sorted(str(p) for p in QML.glob("*.qml"))
        cls.fautes = []
        aide = subprocess.run([QMLLINT, "--help"], capture_output=True, text=True, timeout=30).stdout
        if "--json" in aide:
            with tempfile.TemporaryDirectory() as dossier:
                sortie = Path(dossier) / "lint.json"
                # Code de sortie non nul à cause du bruit : seul le JSON compte
                subprocess.run([QMLLINT, "--json", str(sortie), *fichiers], cwd=QML, capture_output=True, timeout=120)
                donnees = json.loads(sortie.read_text(encoding="utf-8"))
            for f in donnees.get("files", []):
                for w in f.get("warnings", []):
                    if w.get("id") in CATEGORIES:
                        cls.fautes.append(f"{Path(f.get('filename', '?')).name}:{w.get('line')} [{w.get('id')}] {w.get('message', '').strip()}")
        else:
            # Ancien qmllint sans JSON : le texte porte la catégorie entre crochets
            res = subprocess.run([QMLLINT, *fichiers], cwd=QML, capture_output=True, text=True, timeout=120)
            for ligne in (res.stdout + res.stderr).splitlines():
                if any(f"[{c}]" in ligne for c in CATEGORIES):
                    cls.fautes.append(ligne.strip())

    def test_aucun_id_ne_masque_une_propriete(self):
        fautes = [f for f in self.fautes if "id-shadows-member" in f]
        self.assertEqual(fautes, [], "\n".join(fautes))

    def test_aucune_egalite_avec_conversion(self):
        fautes = [f for f in self.fautes if "equality-type-coercion" in f]
        self.assertEqual(fautes, [], "\n".join(fautes))


if __name__ == "__main__":
    unittest.main()
