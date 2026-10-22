"""nc-reglages fenetre (l'appli Réglages, Super + Alt + ,) : la fenêtre graphique vit dans l'île Quickshell.
Si l'île ne répond pas (arrêtée, ou encore sur l'ancienne config après une mise à jour : Quickshell répond alors
« Function not found. » avec le code 0), un seul redémarrage de nc-ile.service et un second essai ; sinon une
notification, puis l'écran des réglages dans le terminal. HOME temporaire ; faux qs, systemctl, kitty et
notify-send seuls dans le PATH (aucun vrai redémarrage, aucune vraie fenêtre)."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest

REPO = Path(__file__).resolve().parents[1]
BIN = REPO / "home/.local/bin"

# Faux qs : l'état de l'île est dans $HOME/qs-mode (ok, ancienne, arretee, cassee) ; « ancienne » et « arretee » sont
# réparées par un redémarrage (fichier $HOME/redemarre, posé par le faux systemctl). Rien que des commandes internes
# du shell : le PATH ne contient que les faux.
FAUX_QS = r'''#!/bin/sh
echo "qs $*" >> "$HOME/appels"
mode=ok
[ -e "$HOME/qs-mode" ] && read mode < "$HOME/qs-mode"
etat=$mode
if [ -e "$HOME/redemarre" ] && { [ "$mode" = ancienne ] || [ "$mode" = arretee ]; }; then etat=ok; fi
case "$*" in
  *"ipc show"*)
    [ "$etat" = arretee ] && { echo "No running instances for nc-ile"; exit 255; }
    echo "target ile"
    [ "$etat" = ok ] && echo "  function reglages(): void"
    echo "  function ouvrir(): void"
    exit 0 ;;
esac
case "$etat" in
  ok) exit 0 ;;
  arretee) echo "No running instances for nc-ile"; exit 255 ;;
  *) echo "Function not found."; exit 0 ;;
esac
'''
FAUX_SYSTEMCTL = '''#!/bin/sh
echo "systemctl $*" >> "$HOME/appels"
case "$*" in
  *restart*) : > "$HOME/redemarre" ;;
esac
exit 0
'''
FAUX_JOURNAL = '#!/bin/sh\necho "{nom} $*" >> "$HOME/appels"\n'


class Fenetre(unittest.TestCase):
    def setUp(self):
        d = tempfile.TemporaryDirectory(prefix="nc-reglages-fenetre-")
        self.addCleanup(d.cleanup)
        self.home = Path(d.name)
        (self.home / ".config/nc").mkdir(parents=True)
        b = self.home / ".local/bin"; b.mkdir(parents=True)
        (b / "nc-reglages").symlink_to(BIN / "nc-reglages")
        self.faux = self.home / "faux"; self.faux.mkdir()
        (self.faux / "python3").symlink_to(sys.executable)          # pour « #!/usr/bin/env python3 »
        for nom, texte in (("qs", FAUX_QS), ("systemctl", FAUX_SYSTEMCTL), ("kitty", FAUX_JOURNAL.format(nom="kitty")),
                           ("notify-send", FAUX_JOURNAL.format(nom="notify-send"))):
            (self.faux / nom).write_text(texte); (self.faux / nom).chmod(0o755)
        # Seuls les faux : le vrai qs (/usr/bin/qs) ne doit jamais être joint
        self.env = dict(os.environ, HOME=str(self.home), PATH=str(self.faux), NC_LANGUE="fr",
                        XDG_CONFIG_HOME=str(self.home / ".config"))

    def lancer(self, mode=None, *args, code=0):
        if mode:
            (self.home / "qs-mode").write_text(mode + "\n")
        r = subprocess.run([str(self.home / ".local/bin/nc-reglages"), "fenetre", *args], env=self.env,
                           capture_output=True, text=True, timeout=30)
        self.assertEqual(r.returncode, code, r.stderr)
        return r

    def appels(self, attendre=None):
        """Les appels notés ; avec `attendre`, patiente (kitty est lancé détaché) jusqu'à voir ce début de ligne."""
        f = self.home / "appels"
        fin = time.monotonic() + 5
        while True:
            lignes = f.read_text().splitlines() if f.exists() else []
            if not attendre or any(l.startswith(attendre) for l in lignes) or time.monotonic() > fin:
                return lignes
            time.sleep(0.05)

    def test_a_appel_reussi(self):
        self.lancer("ok")
        time.sleep(0.3)                                               # laisse le temps à un éventuel kitty détaché
        a = self.appels()
        self.assertEqual(a, ["qs -c nc-ile ipc call ile reglages"])

    def test_b_ancienne_ile_redemarree(self):
        self.lancer("ancienne")
        time.sleep(0.3)
        a = self.appels()
        self.assertIn("systemctl --user restart nc-ile.service", a)
        self.assertEqual(sum(l == "systemctl --user restart nc-ile.service" for l in a), 1)
        self.assertEqual(a.count("qs -c nc-ile ipc call ile reglages"), 2)
        self.assertIn("qs -c nc-ile ipc show", a)
        self.assertFalse(any(l.startswith(("kitty", "notify-send")) for l in a), a)

    def test_b_ile_arretee_redemarree(self):
        self.lancer("arretee")
        time.sleep(0.3)
        a = self.appels()
        self.assertEqual(sum(l == "systemctl --user restart nc-ile.service" for l in a), 1)
        self.assertEqual(a.count("qs -c nc-ile ipc call ile reglages"), 2)
        self.assertFalse(any(l.startswith(("kitty", "notify-send")) for l in a), a)

    def test_c_echec_persistant(self):
        debut = time.monotonic()
        self.lancer("cassee")
        self.assertLess(time.monotonic() - debut, 12)                # 5 s au plus, puis 4 s d'attente, puis 2 s
        a = self.appels(attendre="kitty")
        self.assertEqual(sum(l == "systemctl --user restart nc-ile.service" for l in a), 1)
        self.assertEqual(a.count("qs -c nc-ile ipc call ile reglages"), 2)
        notif = [i for i, l in enumerate(a) if l.startswith("notify-send")]
        term = [i for i, l in enumerate(a) if l.startswith("kitty")]
        self.assertEqual(len(notif), 1, a); self.assertEqual(len(term), 1, a)
        self.assertLess(notif[0], term[0])
        self.assertIn("-a noctalia-config", a[notif[0]])
        self.assertIn("L'île ne répond pas : réglages ouverts dans le terminal. Diagnostic : nc-diag", a[notif[0]])
        self.assertIn("--class nc-reglages -e", a[term[0]])

    def test_d_sans_qs(self):
        (self.faux / "qs").unlink()
        self.lancer()
        a = self.appels(attendre="kitty")
        self.assertFalse(any(l.startswith(("systemctl", "qs")) for l in a), a)
        self.assertEqual([l.split(" ", 1)[0] for l in a], ["notify-send", "kitty"])

    def test_e_section(self):
        # Nom français ou anglais, sans accent : l'île reçoit le nom affiché de la section
        self.lancer("ok", "nouveautes")
        self.lancer("ok", "Shortcuts")
        time.sleep(0.3)
        self.assertEqual(self.appels(), ["qs -c nc-ile ipc call ile reglagesSection Nouveautés",
                                         "qs -c nc-ile ipc call ile reglagesSection Raccourcis"])

    def test_e_section_en_anglais(self):
        self.env["NC_LANGUE"] = "en"
        self.lancer("ok", "Nouveautés")
        time.sleep(0.3)
        self.assertEqual(self.appels(), ["qs -c nc-ile ipc call ile reglagesSection What's New"])

    def test_e_section_inconnue(self):
        r = self.lancer("ok", "Nulle part", code=1)
        self.assertIn("section inconnue : Nulle part", r.stderr)
        self.assertFalse((self.home / "appels").exists())

    def test_f_repli_sur_la_meme_section(self):
        # Sans l'île : l'écran du terminal, sur les raccourcis ou les nouveautés (comme avant « Tout voir »)
        (self.faux / "qs").unlink()
        self.lancer(None, "Raccourcis")
        a = self.appels(attendre="kitty")
        self.assertTrue(a[-1].startswith("kitty --class nc-reglages -e ") and a[-1].endswith("/nc-reglages raccourcis"), a)
        (self.home / "appels").unlink()
        self.lancer(None, "Nouveautés")
        a = self.appels(attendre="kitty")
        self.assertIn("-e sh -c \"$0\" nouveautes | less -R ", a[-1])

    def test_notification_en_anglais(self):
        self.env["NC_LANGUE"] = "en"
        (self.faux / "qs").unlink()
        self.lancer()
        a = self.appels(attendre="kitty")
        self.assertIn("The island is not responding: settings opened in the terminal. Diagnosis: nc-diag", a[0])


if __name__ == "__main__":
    unittest.main()
