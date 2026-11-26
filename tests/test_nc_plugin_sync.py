"""nc-plugin-sync : compile le plugin nc-gestes pour l'Hyprland en cours et le charge, sans jamais bloquer la session.
Faux hyprctl, pkg-config, make, g++ et qs dans un HOME jetable : jamais le vrai Hyprland ni le vrai compilateur.
Vérifié : sortie 0 en silence sans session, sans en-têtes ou avec les en-têtes d'un autre commit ; une compilation par
commit et par version des sources (fichier .abi) ; .so remplacé d'un bloc, jamais abîmé par un échec de compilation ;
chargé une seule fois, rechargé après une recompilation ; puis nc.gestes_sync et la pilule de l'île redemandées."""
import os
from pathlib import Path
import shutil
import stat
import subprocess
import tempfile
import unittest

from tests import _isolation

REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "home/.local/bin/nc-plugin-sync"
COMMIT = "11cbc6c577b84ffb1edf4df3fc5b6128c3ae6947"

FAUX = {
    # version -j : le commit en cours ; plugin list -j / load / unload : l'état « chargé » est un fichier
    "hyprctl": r'''echo "hyprctl $*" >> "$J"
case "$1 $2" in
  "version -j") printf '{"commit": "%s"}\n' "$(cat "$E/commit")" ;;
  "plugin list") if [ -e "$E/charge" ]; then echo '[{"name": "nc-gestes"}]'; else echo '[]'; fi ;;
  "plugin load") touch "$E/charge"; echo ok ;;
  "plugin unload") rm -f "$E/charge"; echo ok ;;
  *) echo ok ;;
esac''',
    "pkg-config": r'''case "$1" in
  --exists) [ -e "$E/entetes" ] ;;
  --cflags-only-I) echo "-I$E/inc/hyprland/protocols -I$E/inc/hyprland/src" ;;
esac''',
    "make": r'''echo "make $*" >> "$J"
[ -e "$E/echec" ] && { echo "erreur de compilation" >&2; exit 1; }
for a in "$@"; do case "$a" in SORTIE=*) printf 'so %s' "$(cat "$E/commit")" > "${a#SORTIE=}" ;; esac; done''',
    "g++": "exit 0",
    "qs": 'echo "qs $*" >> "$J"',
}


@unittest.skipUnless(shutil.which("jq") and shutil.which("bash"), "jq ou bash absent")
class PluginSync(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(prefix="nc-plugin-", dir=_isolation.dossier_court())
        self.addCleanup(tmp.cleanup)
        r = Path(tmp.name)
        self.home, self.etat, self.journal = r / "home", r / "etat", r / "journal"
        self.etat.mkdir()
        (self.etat / "inc/hyprland/src").mkdir(parents=True)
        self.entetes(COMMIT)
        (self.etat / "commit").write_text(COMMIT)
        (self.etat / "entetes").touch()
        src = self.home / ".local/share/nc/plugins/nc-gestes"
        (src / "src").mkdir(parents=True)
        (src / "Makefile").write_text("all:\n")
        (src / "src/main.cpp").write_text("// v1\n")
        self.src = src
        faux = r / "bin"
        faux.mkdir()
        for nom, corps in FAUX.items():
            f = faux / nom
            f.write_text("#!/bin/sh\n" + corps + "\n")
            f.chmod(f.stat().st_mode | stat.S_IEXEC)
        self.lib = self.home / ".local/lib/noctalia-config"
        self.env = dict(os.environ, HOME=str(self.home), PATH=f"{faux}:{os.environ['PATH']}", J=str(self.journal),
                        E=str(self.etat), HYPRLAND_INSTANCE_SIGNATURE="test", NC_LANGUE="fr")
        self.env.pop("CXX", None)

    def entetes(self, commit):
        (self.etat / "inc/hyprland/src/version.h").write_text(f'#pragma once\n#define GIT_COMMIT_HASH    "{commit}"\n')

    def lancer(self, env=None):
        self.journal.unlink(missing_ok=True)
        r = subprocess.run(["bash", str(SCRIPT)], env=env or self.env, capture_output=True, text=True, timeout=30)
        self.assertEqual(r.returncode, 0, r.stderr)
        return r, self.journal.read_text().splitlines() if self.journal.exists() else []

    def compte(self, lignes, debut):
        return sum(1 for l in lignes if l.startswith(debut))

    def test_sans_entetes_rien(self):
        (self.etat / "entetes").unlink()
        r, j = self.lancer()
        self.assertEqual((r.stdout, r.stderr, j), ("", "", []))
        self.assertFalse(self.lib.exists())

    def test_sans_session_rien(self):
        env = dict(self.env)
        del env["HYPRLAND_INSTANCE_SIGNATURE"]
        r, j = self.lancer(env)
        self.assertEqual((r.stdout, r.stderr, j), ("", "", []))
        self.assertFalse(self.lib.exists())

    def test_entetes_d_un_autre_commit_rien(self):
        self.entetes("0" * 40)                                   # Hyprland mis à jour, pas encore relancé
        r, j = self.lancer()
        self.assertEqual(r.stderr, "")
        self.assertEqual(self.compte(j, "make"), 0)
        self.assertEqual(self.compte(j, "hyprctl plugin load"), 0)
        self.assertFalse((self.lib / "nc-gestes.so").exists())

    def test_compile_charge_puis_ne_refait_rien(self):
        r, j = self.lancer()
        self.assertEqual((r.stdout, r.stderr), ("", ""))
        self.assertEqual(self.compte(j, "make"), 1)
        so = self.lib / "nc-gestes.so"
        self.assertEqual(so.read_text(), "so " + COMMIT)
        self.assertTrue((self.lib / "nc-gestes.abi").read_text().startswith(COMMIT + " "))
        self.assertIn(f"hyprctl plugin load {so}", j)
        self.assertEqual(self.compte(j, "hyprctl eval"), 1)
        self.assertIn("qs -c nc-ile ipc call ile gestesAncre", j)
        self.assertEqual(sorted(p.name for p in self.lib.iterdir()), [".verrou", "nc-gestes.abi", "nc-gestes.log", "nc-gestes.so"])
        # Même commit, mêmes sources, déjà chargé : ni compilation ni chargement ; le geste est quand même redonné
        _, j = self.lancer()
        self.assertEqual(self.compte(j, "make"), 0)
        self.assertEqual(self.compte(j, "hyprctl plugin"), 1)     # seulement « plugin list »
        self.assertEqual(self.compte(j, "hyprctl eval"), 1)
        # Hyprland relancé (même commit) : plus chargé, rechargé sans recompiler
        (self.etat / "charge").unlink()
        _, j = self.lancer()
        self.assertEqual(self.compte(j, "make"), 0)
        self.assertIn(f"hyprctl plugin load {so}", j)

    def test_sources_changees_recompile_et_recharge(self):
        self.lancer()
        (self.src / "src/main.cpp").write_text("// v2\n")
        _, j = self.lancer()
        self.assertEqual(self.compte(j, "make"), 1)
        so = self.lib / "nc-gestes.so"
        self.assertLess(j.index(f"hyprctl plugin unload {so}"), j.index(f"hyprctl plugin load {so}"))

    def test_nouvel_hyprland_recompile(self):
        self.lancer()
        nouveau = "f" * 40
        (self.etat / "commit").write_text(nouveau)
        self.entetes(nouveau)
        (self.etat / "charge").unlink()
        _, j = self.lancer()
        self.assertEqual(self.compte(j, "make"), 1)
        self.assertEqual((self.lib / "nc-gestes.so").read_text(), "so " + nouveau)

    def test_echec_de_compilation_garde_l_ancien(self):
        self.lancer()
        so = self.lib / "nc-gestes.so"
        nouveau = "e" * 40
        (self.etat / "commit").write_text(nouveau)
        self.entetes(nouveau)
        (self.etat / "charge").unlink()
        (self.etat / "echec").touch()
        r, j = self.lancer()
        self.assertIn("nc-gestes.log", r.stderr)
        self.assertEqual(so.read_text(), "so " + COMMIT)          # l'ancien .so n'est pas abîmé
        self.assertEqual(self.compte(j, "hyprctl plugin load"), 0)
        self.assertEqual([p.name for p in self.lib.iterdir() if p.name.startswith(".nc-gestes")], [])   # pas de reste


if __name__ == "__main__":
    unittest.main()
