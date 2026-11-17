"""Tests de installeur/nc-installeur : logique pure, session contre un FAUX install.sh, fenêtre hors écran si GTK."""
import importlib.machinery
import importlib.util
import os
import pathlib
import shutil
import stat
import sys
import tempfile
import textwrap
import unittest
from unittest import mock

BIN = pathlib.Path(__file__).resolve().parent.parent / "installeur"
_TMP = tempfile.mkdtemp(prefix="nc-ig-test-")
# HOME, XDG_* et TMPDIR isolés pour ce fichier seulement, rendus à la fin (les autres tests du même processus n'en héritent pas)
_ISOLE = mock.patch.dict(os.environ, dict({k: _TMP for k in ("HOME", "XDG_CACHE_HOME", "XDG_CONFIG_HOME", "XDG_DATA_HOME",
                                                             "XDG_STATE_HOME", "XDG_RUNTIME_DIR", "TMPDIR")}, NC_LANGUE="fr"))
_ISOLE.start()


def tearDownModule():
    _ISOLE.stop()
    shutil.rmtree(_TMP, ignore_errors=True)


_l = importlib.machinery.SourceFileLoader("nc_installeur", str(BIN / "nc-installeur"))
M = importlib.util.module_from_spec(importlib.util.spec_from_loader("nc_installeur", _l))
_l.exec_module(M)


def os_release(texte):
    d = tempfile.mkdtemp(dir=_TMP)
    p = os.path.join(d, "os-release")
    pathlib.Path(p).write_text(textwrap.dedent(texte))
    return M.lire_os_release({"NC_OS_RELEASE": p})


class Pur(unittest.TestCase):
    def test_distributions(self):
        cas = [('NAME="Arch Linux"\nPRETTY_NAME="Arch Linux"\nID=arch\nLOGO=archlinux-logo\n', "#1793d1"),
               ('PRETTY_NAME="Debian GNU/Linux 13 (trixie)"\nID=debian\n', "#d70a53"),
               ('NAME=Fedora\nPRETTY_NAME="Fedora Linux 42"\nID=fedora\n', "#3c6eb4"),
               ('PRETTY_NAME="openSUSE Tumbleweed"\nID="opensuse-tumbleweed"\nID_LIKE="opensuse suse"\n', "#73ba25")]
        for texte, couleur in cas:
            o = os_release(texte)
            self.assertEqual(M.couleur_accent(o), couleur, texte)
            self.assertTrue(M.nom_distribution(o))
        self.assertEqual(M.nom_distribution(os_release('PRETTY_NAME="Arch Linux"\nID=arch\n')), "Arch Linux")

    def test_ansi_color(self):
        self.assertEqual(M.couleur_accent({"ANSI_COLOR": "38;2;23;147;209"}), "#1793d1")
        self.assertEqual(M.couleur_accent({"ANSI_COLOR": "0;34", "ID": "debian"}), "#3465a4")
        self.assertEqual(M.couleur_accent({"ANSI_COLOR": "n'importe quoi", "ID_LIKE": "arch"}), "#1793d1")
        self.assertEqual(M.couleur_accent({}), M.DEFAUT_ACCENT)
        self.assertEqual(M.lire_os_release({"NC_OS_RELEASE": "/nulle/part"}) is not None, True)

    def test_json_hostile(self):
        p = M.parse_evenement
        e = p('{"type":"info","texte":"<b>gras</b> \\u202e\\n"}')
        self.assertEqual(e["texte"], "<b>gras</b>")  # gardé tel quel : c'est la fenêtre qui n'interprète pas
        for mauvais in ('{"type":"info","texte":"x', "", "pas du json", "[1]", '{"type":"inconnu"}',
                        '{"type":"question","id":"a","question":"?"}', '{"type":"question","id":true,"question":"?"}',
                        '{"type":"choix","id":1,"question":"?","options":[]}', '{"type":"progres","x":1,"y":0}',
                        '{"type":"fin","code":"0"}', "[" * 100000):
            self.assertIsNone(p(mauvais), mauvais[:30])
        self.assertEqual(p('{"type":"question","id":3,"question":"Go ?","defaut":"n","sensible":true}'),
                         {"type": "question", "id": 3, "question": "Go ?", "defaut": "n", "sensible": True})
        self.assertEqual(p('{"type":"choix","id":4,"question":"?","options":["a","b"],"defaut":9}')["defaut"], 1)

    def test_reponse(self):
        self.assertEqual(M.formater_reponse(2, True), "2 o\n")
        self.assertEqual(M.formater_reponse(2, 3), "2 3\n")
        self.assertEqual(M.formater_reponse(5, "a\nb\x1b[31m\r6 o"), "5 a b 6 o\n".replace("b 6", "b 6"))
        self.assertEqual(M.formater_reponse(5, "x\ny").count("\n"), 1)
        with self.assertRaises(ValueError):
            M.formater_reponse("1; rm", "o")

    def test_ansi_journal(self):
        self.assertEqual(M.retirer_ansi("\x1b[1;32mok\x1b[0m fini"), "ok fini")
        self.assertEqual(M.retirer_ansi("10%\r50%\r100%"), "100%")

    def test_commande(self):
        argv, env = M.construire_commande(["--no-system", "--fr", "a b;rm"], "/s", "/e",
                                          {"NC_INSTALLEUR_SCRIPT": "/x/install.sh", "PATH": "/bin"})
        self.assertEqual(argv, ["/x/install.sh", "--no-system", "--fr", "a b;rm"])
        self.assertEqual((env["NC_UI"], env["NC_UI_SORTIE"], env["NC_UI_ENTREE"]), ("1", "/s", "/e"))
        self.assertTrue(M.chemin_script({}).endswith("install.sh"))
        self.assertEqual(M.analyser_args(["--files-only", "--en", "--autre"], {}), ("files-only", "en", ["--autre"]))
        self.assertEqual(M.options_install("complet", "fr", ["--x"]), ["--fr", "--x"])

    def test_fin(self):
        self.assertEqual(M.message_fin(0), (True, "Installation terminée"))
        self.assertIn("annulée", M.message_fin(130)[1])
        self.assertIn("annulée", M.message_fin(10)[1])
        self.assertIn("7", M.message_fin(7)[1])
        self.assertFalse(M.message_fin(0, inattendu=True)[0])


FAUX = r'''#!/bin/sh
printf '%s\n' "$*" > "$NC_FAUX_DIR/args"
env | grep '^NC_UI' | sort > "$NC_FAUX_DIR/env"
e() { printf '%s\n' "$1" > "$NC_UI_SORTIE"; }
a() { read -r l < "$NC_UI_ENTREE"; printf '%s\n' "$l" >> "$NC_FAUX_DIR/reponses"; }
case "$NC_FAUX_MODE" in
 normal)
  e '{"type":"etape","n":1,"titre":"Paquets"}'
  printf 'texte \033[31mrouge\033[0m\n'; echo "erreur" >&2
  e 'bruit pas json'
  e '{"type":"progres","x":1,"y":4}'
  e '{"type":"question","id":1,"question":"On y va ?","defaut":"o","sensible":false}'; a
  e '{"type":"choix","id":2,"question":"Quoi ?","options":["a","b"],"defaut":1}'; a
  e '{"type":"saisie","id":3,"question":"Nom ?","defaut":""}'; a
  e '{"type":"fin","code":0}'; exit 0;;
 lent) trap 'exit 130' INT; e '{"type":"etape","n":1,"titre":"Long"}'; while :; do sleep 0.1; done;;
 commande) trap 'exit 130' INT; e '{"type":"etape","n":1,"titre":"Compilation"}'; sleep 60; exit 0;;
 sans_fin) e '{"type":"info","texte":"salut"}'; exit 3;;
esac
'''


class Bout(unittest.TestCase):
    def lancer(self, mode, repondre=None, options=()):
        d = tempfile.mkdtemp(dir=_TMP)
        script = os.path.join(d, "install.sh")
        pathlib.Path(script).write_text(FAUX)
        os.chmod(script, stat.S_IRWXU)
        env = dict(os.environ, NC_INSTALLEUR_SCRIPT=script, NC_FAUX_DIR=d, NC_FAUX_MODE=mode)
        evs, jour, fin = [], [], []
        s = M.Session(options, lambda e: (evs.append(e), repondre and repondre(s, e)),
                      jour.append, lambda c, i: fin.append((c, i)), env)
        s.demarrer()
        return s, d, evs, jour, fin

    def test_normal(self):
        rep = {"question": True, "choix": 2, "saisie": "Zoé\nx"}
        s, d, evs, jour, fin = self.lancer("normal", lambda s, e: e["type"] in rep and s.repondre(e["id"], rep[e["type"]]),
                                           ["--no-system", "--fr"])
        self.assertTrue(s.termine.wait(15))
        self.assertEqual(fin, [(0, False)])
        self.assertEqual([e["type"] for e in evs], ["etape", "progres", "question", "choix", "saisie", "fin"])
        self.assertEqual(pathlib.Path(d, "reponses").read_text().split("\n")[:3], ["1 o", "2 2", "3 Zoé x"])
        self.assertEqual(pathlib.Path(d, "args").read_text().strip(), "--no-system --fr")
        self.assertIn("NC_UI=1", pathlib.Path(d, "env").read_text())
        self.assertIn("texte rouge", jour)
        self.assertIn("erreur", jour)
        self.assertFalse(os.path.isdir(s._dossier))

    def test_annulation(self):
        s, d, evs, jour, fin = self.lancer("lent")
        for _ in range(100):
            if evs:
                break
            import time
            time.sleep(0.1)
        s.annuler()
        self.assertTrue(s.termine.wait(15))
        self.assertEqual(fin[0][0], 130)
        self.assertIn("annulée", M.message_fin(*fin[0][:1])[1])

    def test_annulation_pendant_une_commande_longue(self):
        # SIGINT au seul bash attendrait la fin de « sleep 60 » ; au groupe, la commande s'arrête tout de suite
        import time
        s, d, evs, jour, fin = self.lancer("commande")
        for _ in range(100):
            if evs:
                break
            time.sleep(0.1)
        time.sleep(0.2)
        s.annuler()
        self.assertTrue(s.termine.wait(5), "Annuler attend la fin de la commande en cours")
        self.assertEqual(fin[0][0], 130)

    def test_fin_inattendue(self):
        s, d, evs, jour, fin = self.lancer("sans_fin")
        self.assertTrue(s.termine.wait(15))
        self.assertEqual(fin, [(3, True)])
        self.assertEqual(evs[0]["texte"], "salut")


def _gtk_ok():
    try:
        import gi
        gi.require_version("Gtk", "4.0")
        gi.require_version("Adw", "1")
        from gi.repository import Adw, Gtk  # noqa: F401
        return bool(os.environ.get("WAYLAND_DISPLAY") or os.environ.get("DISPLAY"))
    except Exception:
        return False


@unittest.skipUnless(_gtk_ok(), "GTK 4, libadwaita ou écran absents")
class Fenetre(unittest.TestCase):
    def test_construction(self):
        M.charger_gtk()
        if not M.Gtk.init_check():
            self.skipTest("pas d'écran")
        M.Adw.init()
        app = M.Adw.Application(application_id="org.noctalia.config.installeur.test")
        ui = M.Interface(app, ["--files-only", "--en"], {"NC_OS_RELEASE": "/nulle/part", "LANG": "fr_FR.UTF-8"})
        self.assertEqual((ui.mode, ui.langue), ("files-only", "en"))
        ui._evenement({"type": "etape", "n": 1, "titre": "<b>x</b>"})
        ui._evenement({"type": "progres", "x": 1, "y": 2})
        self.assertEqual(len(ui.lignes_etapes), 1)
        ui._terminer(130, False)
        self.assertEqual(ui.fin_page.get_title(), M.T["en"]["annulee"])


if __name__ == "__main__":
    unittest.main()
