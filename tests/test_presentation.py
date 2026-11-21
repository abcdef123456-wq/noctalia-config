"""Mode Présentation : nc-presentation lit café et « ne pas déranger » par l'IPC de l'île, les met en route,
puis les remet comme avant. Faux qs, faux notify-send, tout dans un dossier temporaire."""
import itertools
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

RACINE = Path(__file__).resolve().parents[1]
SCRIPT = RACINE / "home/.local/bin/nc-presentation"

# faux qs : états dans $D/cafe et $D/dnd ; QS_MUET=1 : l'île ne répond pas
FAUX_QS = '''#!/bin/sh
echo "$*" >> "$D/journal"
[ -n "$QS_MUET" ] && exit 1
case "$*" in
  *cafeEtat*) cat "$D/cafe" ;;
  *concentrationEtat*) cat "$D/dnd" ;;
  *"cafeRegler true"*) echo oui > "$D/cafe" ;;
  *"cafeRegler false"*) echo non > "$D/cafe" ;;
  *"concentrationRegler true"*) echo oui > "$D/dnd" ;;
  *"concentrationRegler false"*) echo non > "$D/dnd" ;;
esac
'''


@unittest.skipUnless(shutil.which("bash") and shutil.which("timeout"), "bash et timeout requis")
class Presentation(unittest.TestCase):
    def setUp(self):
        self._t = tempfile.TemporaryDirectory(prefix="ncp-", dir=os.environ.get("TMPDIR"))
        self.addCleanup(self._t.cleanup)
        self.d = Path(self._t.name)
        (self.d / "bin").mkdir()
        (self.d / "home/.local/bin").mkdir(parents=True)
        (self.d / "run").mkdir()
        for nom, corps in (("qs", FAUX_QS), ("notify-send", '#!/bin/sh\necho "$*" >> "$D/notifs"\n')):
            p = self.d / "bin" / nom
            p.write_text(corps)
            p.chmod(0o755)
        self.fichier = self.d / "run/nc-presentation"

    def etats(self, cafe, dnd):
        (self.d / "cafe").write_text(cafe + "\n")
        (self.d / "dnd").write_text(dnd + "\n")

    def lire(self):
        return (self.d / "cafe").read_text().strip(), (self.d / "dnd").read_text().strip()

    def lance(self, *args, muet=False, sans_session=False):
        env = {"PATH": f"{self.d}/bin:/usr/bin:/bin", "HOME": str(self.d / "home"), "XDG_CONFIG_HOME": str(self.d / "cfg"),
               "XDG_STATE_HOME": str(self.d / "state"), "XDG_RUNTIME_DIR": str(self.d / "run"), "D": str(self.d),
               "NC_LANGUE": "fr"}
        if muet:
            env["QS_MUET"] = "1"
        if sans_session:
            del env["XDG_RUNTIME_DIR"]
        return subprocess.run(["bash", str(SCRIPT), *args], env=env, capture_output=True, text=True, timeout=20)

    def test_activer_puis_couper_restaure_les_quatre_combinaisons(self):
        for cafe, dnd in itertools.product(("oui", "non"), repeat=2):
            with self.subTest(cafe=cafe, dnd=dnd):
                self.etats(cafe, dnd)
                self.assertEqual(self.lance("activer").returncode, 0)
                self.assertEqual(self.lire(), ("oui", "oui"))
                self.assertEqual(self.lance("etat").stdout.strip(), "oui")
                self.assertEqual(self.lance("couper").returncode, 0)
                self.assertEqual(self.lire(), (cafe, dnd))
                self.assertFalse(self.fichier.exists())
                self.assertEqual(self.lance("etat").stdout.strip(), "non")

    def test_double_activation_garde_l_etat_d_avant(self):
        self.etats("non", "oui")
        self.lance("activer")
        self.lance("activer")
        self.lance("couper")
        self.assertEqual(self.lire(), ("non", "oui"))

    def test_sans_dossier_de_session_refuse(self):
        """Sans XDG_RUNTIME_DIR : refus, l'île n'est pas appelée et rien n'est écrit dans /tmp."""
        self.etats("non", "non")
        r = self.lance("activer", sans_session=True)
        self.assertEqual(r.returncode, 1)
        self.assertIn("XDG_RUNTIME_DIR", r.stderr)
        self.assertFalse((self.d / "journal").exists())
        self.assertEqual(self.lire(), ("non", "non"))

    def test_couper_sans_activation_ne_fait_rien(self):
        self.etats("oui", "non")
        self.assertEqual(self.lance("couper").returncode, 0)
        self.assertEqual(self.lire(), ("oui", "non"))
        self.assertFalse((self.d / "journal").exists())

    def test_ile_muette_refuse_sans_rien_ecrire(self):
        self.etats("non", "non")
        r = self.lance("activer", muet=True)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("île", r.stderr)
        self.assertFalse(self.fichier.exists())

    def test_mode_jeu_actif_refuse(self):
        self.etats("non", "non")
        (self.d / "run/nc-mode-jeu").write_text("")
        r = self.lance("activer")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("mode jeu", r.stderr)
        self.assertFalse(self.fichier.exists())
        self.assertEqual(self.lire(), ("non", "non"))

    def test_basculer(self):
        self.etats("non", "non")
        self.lance("basculer")
        self.assertEqual(self.lire(), ("oui", "oui"))
        self.lance("basculer")
        self.assertEqual(self.lire(), ("non", "non"))

    def test_notification_dite(self):
        self.etats("non", "non")
        self.lance("activer")
        self.assertIn("activé", (self.d / "notifs").read_text())

    def test_ipc_de_l_ile_a_les_fonctions(self):
        src = (RACINE / "home/.config/quickshell/nc-ile/shell.qml").read_text()
        self.assertIn("function cafeEtat(): string", src)
        self.assertIn("function cafeRegler(actif: bool): void", src)
        etat = (RACINE / "home/.config/quickshell/nc-ile/Etat.qml").read_text()
        self.assertIn("function cafeRegler(actif)", etat)


if __name__ == "__main__":
    unittest.main()
