"""nc-qr et l'action « QR » du presse-papiers (PresseQr.qml, Presse.qml, PresseAnalyse.qml).

nc-qr : texte seulement sur l'entrée standard (aucun argument), 2000 caractères au plus, PNG 0600 dans un dossier 0700 de
XDG_RUNTIME_DIR, anciens PNG retirés, qrencode absent ou XDG_RUNTIME_DIR absent : refus. Faux qrencode : il note ses
arguments et son entrée, et écrit un petit PNG ; le vrai n'est jamais lancé. Île : lecture du source (pas d'écran)."""
from pathlib import Path
import re
import shutil
import stat
import subprocess
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[1]
NC_QR = REPO / "home/.local/bin/nc-qr"
QML = REPO / "home/.config/quickshell/nc-ile"
FAUX = """#!/bin/sh
printf '%s\\n' "$@" > "$FAUX_ARGS"
cat > "$FAUX_STDIN"
while [ "$1" ]; do [ "$1" = -o ] && sortie="$2"; shift; done
printf 'PNG' > "$sortie"
"""


class NcQr(unittest.TestCase):
    def setUp(self):
        self.d = Path(tempfile.mkdtemp(prefix="qr"))
        self.addCleanup(shutil.rmtree, self.d, True)
        self.run_dir = self.d / "run"
        self.run_dir.mkdir(mode=0o700)
        self.bin = self.d / "bin"
        self.bin.mkdir()
        faux = self.bin / "qrencode"
        faux.write_text(FAUX)
        faux.chmod(0o755)

    def lancer(self, texte, avec_qrencode=True, avec_run=True, args=()):
        env = {"PATH": f"{self.bin if avec_qrencode else self.d}:/usr/bin:/bin", "HOME": str(self.d),
               "FAUX_ARGS": str(self.d / "args"), "FAUX_STDIN": str(self.d / "stdin")}
        if avec_run:
            env["XDG_RUNTIME_DIR"] = str(self.run_dir)
        return subprocess.run(["python3", "-B", str(NC_QR), *args], input=texte.encode(), env=env, capture_output=True)

    def test_texte_sur_stdin_jamais_en_argument(self):
        secret = "motdepasse-secret é"
        r = self.lancer(secret)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertNotIn("secret", (self.d / "args").read_text())
        self.assertEqual((self.d / "stdin").read_text(), secret)
        png = Path(r.stdout.decode().strip())
        self.assertEqual(png.parent, self.run_dir / "nc-qr")
        self.assertEqual(stat.S_IMODE(png.stat().st_mode), 0o600)
        self.assertEqual(stat.S_IMODE(png.parent.stat().st_mode), 0o700)

    def test_un_argument_est_refuse(self):
        r = self.lancer("x", args=("secret",))
        self.assertEqual(r.returncode, 2)
        self.assertFalse((self.run_dir / "nc-qr").exists())

    def test_2000_passent_2001_refuses(self):
        self.assertEqual(self.lancer("a" * 2000).returncode, 0)
        r = self.lancer("a" * 2001)
        self.assertEqual(r.returncode, 4)
        self.assertEqual(r.stdout, b"")

    def test_anciens_png_retires(self):
        d = self.run_dir / "nc-qr"
        d.mkdir(mode=0o700)
        (d / "vieux.png").write_text("x")
        png = Path(self.lancer("bonjour").stdout.decode().strip())
        self.assertEqual(list(d.glob("*.png")), [png])

    def test_qrencode_absent_nomme_le_paquet(self):
        r = self.lancer("x", avec_qrencode=False)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn(b"paquet qrencode", r.stderr)

    def test_sans_xdg_runtime_dir_refus(self):
        r = self.lancer("x", avec_run=False)
        self.assertNotEqual(r.returncode, 0)
        self.assertEqual(r.stdout, b"")


class Ile(unittest.TestCase):
    def setUp(self):
        self.presse = (QML / "Presse.qml").read_text()
        self.qr = (QML / "PresseQr.qml").read_text()
        self.analyse = (QML / "PresseAnalyse.qml").read_text()

    def test_action_seulement_texte_et_si_qrencode(self):
        m = re.search(r'\{ id: "qr",.*?\}', self.presse)
        self.assertIn("visible: !el.image && PresseAnalyse.qrDispo === 1", m.group(0))
        self.assertIn("command -v qrencode", self.analyse)

    def test_texte_par_stdin_et_partage_ecran(self):
        self.assertIn("write(q.texte)", self.qr)
        self.assertNotRegex(self.qr, r"command: \[[^\]]*q\.texte")
        self.assertIn("running: q.visible && !q.masque", self.qr)
        self.assertIn("masque: p.masque", self.presse)

    def test_png_retire_a_la_sortie_et_retour(self):
        self.assertIn('"rm", "-f", "--", png', self.qr)
        self.assertIn("onVisibleChanged: if (!visible) { effacer()", self.qr)
        self.assertIn('if (!visible) qrTexte = ""', self.presse)
        self.assertIn("Qt.Key_Escape) qrTexte", self.presse)
        self.assertIn("onClicked: q.fermer()", self.qr)

    def test_pas_de_nouveau_component_ni_minuteur(self):
        for t in (self.qr,):
            self.assertNotRegex(t, r"\bcomponent\b|Timer|repeat: true")


if __name__ == "__main__":
    unittest.main()
