"""nc-sauvegarde avec des dossiers de Noctalia déplacés (XDG_CONFIG_HOME, XDG_STATE_HOME, NOCTALIA_*_HOME) : les
fichiers de Noctalia sont pris là où il les lit, gardés dans l'archive sous leur chemin habituel (~/.config/noctalia,
~/.local/state/noctalia : une sauvegarde passe d'un PC à l'autre), et remis là où Noctalia les lit sur le PC qui
restaure. Faux HOME, faux nc-reglages ; jamais le vrai HOME."""
import os
from pathlib import Path
import subprocess
import tarfile
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[1]
NC_SAUVEGARDE = REPO / "home/.local/bin/nc-sauvegarde"


class DossiersDeNoctalia(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(prefix="nc-sauvegarde-")
        self.addCleanup(self._tmp.cleanup)
        self.r = Path(self._tmp.name)

    def maison(self, nom, **dossiers):
        """Un faux HOME, son faux nc-reglages, et l'environnement (dossiers XDG ou NOCTALIA_* donnés, relatifs à r)."""
        home = self.r / nom
        (home / ".local/bin").mkdir(parents=True)
        (home / ".local/bin/nc-reglages").write_text("#!/bin/sh\nexit 0\n")
        (home / ".local/bin/nc-reglages").chmod(0o755)
        env = {k: v for k, v in os.environ.items() if not k.startswith(("NOCTALIA_", "XDG_CONFIG", "XDG_STATE"))}
        env.pop("HYPRLAND_INSTANCE_SIGNATURE", None)
        env.update(HOME=str(home), NC_LANGUE="fr", XDG_CACHE_HOME=str(home / ".cache"))
        env.update({k: str(self.r / v) for k, v in dossiers.items()})
        return home, env

    def lancer(self, env, *args):
        return subprocess.run([str(NC_SAUVEGARDE), *args], env=env, cwd=env["HOME"], capture_output=True, text=True,
                              timeout=30)

    def test_xdg_state_home_et_xdg_config_home(self):
        home, env = self.maison("a", XDG_STATE_HOME="a-etat", XDG_CONFIG_HOME="a-config")
        (home / ".config/nc").mkdir(parents=True)
        (home / ".config/nc/reglages.conf").write_text("LANGUE=fr\n")
        (self.r / "a-etat/noctalia").mkdir(parents=True)
        (self.r / "a-etat/noctalia/settings.toml").write_text('[dock]\npinned = ["gimp"]\n')
        (self.r / "a-config/noctalia/palettes").mkdir(parents=True)
        (self.r / "a-config/noctalia/palettes/nuit.json").write_text("{}")
        # Ceux de ~/.local/state et ~/.config/noctalia ne sont pas lus par Noctalia ici : jamais pris
        (home / ".local/state/noctalia").mkdir(parents=True)
        (home / ".local/state/noctalia/settings.toml").write_text("ancien\n")
        r = self.lancer(env)
        self.assertEqual(r.returncode, 0, r.stderr)
        archive = next(home.glob("nc-sauvegarde-*.tar.gz"))
        with tarfile.open(archive) as t:
            noms = t.getnames()
            self.assertEqual(t.extractfile(".local/state/noctalia/settings.toml").read(), b'[dock]\npinned = ["gimp"]\n')
        self.assertIn(".config/noctalia/palettes/nuit.json", noms)
        self.assertIn(".config/nc/reglages.conf", noms)
        # Restaurée sur un PC où l'état de Noctalia est ailleurs (NOCTALIA_STATE_HOME passe avant XDG_STATE_HOME)
        home_b, env_b = self.maison("b", NOCTALIA_STATE_HOME="b-noctalia", XDG_STATE_HOME="b-etat",
                                    XDG_CONFIG_HOME="b-config")
        (self.r / "b-noctalia/noctalia").mkdir(parents=True)
        (self.r / "b-noctalia/noctalia/settings.toml").write_text("avant\n")
        r = self.lancer(env_b, "restaurer", str(archive))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual((self.r / "b-noctalia/noctalia/settings.toml").read_text(), '[dock]\npinned = ["gimp"]\n')
        self.assertEqual((self.r / "b-config/noctalia/palettes/nuit.json").read_text(), "{}")
        self.assertEqual((home_b / ".config/nc/reglages.conf").read_text(), "LANGUE=fr\n")
        self.assertFalse((home_b / ".local/state/noctalia").exists())
        self.assertFalse((self.r / "b-etat").exists())
        self.assertFalse((home_b / ".config/noctalia").exists())
        # L'ancien settings.toml est mis de côté, sous son chemin dans la sauvegarde
        avant = list((home_b / ".cache/nc/avant-restauration").glob("*/.local/state/noctalia/settings.toml"))
        self.assertEqual([p.read_text() for p in avant], ["avant\n"])

    def test_sans_xdg_comme_avant(self):
        home, env = self.maison("c")
        (home / ".local/state/noctalia").mkdir(parents=True)
        (home / ".local/state/noctalia/settings.toml").write_text("x = 1\n")
        r = self.lancer(env)
        self.assertEqual(r.returncode, 0, r.stderr)
        archive = next(home.glob("nc-sauvegarde-*.tar.gz"))
        (home / ".local/state/noctalia/settings.toml").write_text("change\n")
        r = self.lancer(env, "restaurer", str(archive))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual((home / ".local/state/noctalia/settings.toml").read_text(), "x = 1\n")


if __name__ == "__main__":
    unittest.main()
