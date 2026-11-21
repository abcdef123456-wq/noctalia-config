"""nc-sauvegarde avec des dossiers de Noctalia déplacés (XDG_CONFIG_HOME, XDG_STATE_HOME, NOCTALIA_*_HOME) : les
fichiers de Noctalia sont pris là où il les lit, gardés dans l'archive sous leur chemin habituel (~/.config/noctalia,
~/.local/state/noctalia : une sauvegarde passe d'un PC à l'autre), et remis là où Noctalia les lit sur le PC qui
restaure. Faux HOME, faux nc-reglages ; jamais le vrai HOME."""
import gzip
import io
import os
from pathlib import Path
import subprocess
import stat
import tarfile
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[1]
NC_SAUVEGARDE = REPO / "home/.local/bin/nc-sauvegarde"


class Base(unittest.TestCase):
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

    def reglages(self, home, **v):
        (home / ".config/nc").mkdir(parents=True, exist_ok=True)
        (home / ".config/nc/reglages.conf").write_text("".join(f'{k}="{x}"\n' for k, x in v.items()) or "LANGUE=fr\n")

    def piegee(self, membres):
        """Archive faite à la main : liste de (nom, TarInfo.type, contenu ou lien, mode)."""
        chemin = self.r / "piegee.tar.gz"
        with tarfile.open(chemin, "w:gz") as t:
            for nom, type_, contenu, mode in membres:
                ti = tarfile.TarInfo(nom)
                ti.type, ti.mode = type_, mode
                if type_ == tarfile.REGTYPE:
                    ti.size = len(contenu)
                    t.addfile(ti, io.BytesIO(contenu))
                else:
                    ti.linkname = contenu if isinstance(contenu, str) else ""
                    t.addfile(ti)
        return chemin

    def module(self):
        """Le script chargé comme module (pour appeler une fonction seule)."""
        import importlib.machinery
        import importlib.util
        spec = importlib.util.spec_from_loader("nc_sauvegarde", importlib.machinery.SourceFileLoader(
            "nc_sauvegarde", str(NC_SAUVEGARDE)))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod

    def lancer(self, env, *args):
        return subprocess.run([str(NC_SAUVEGARDE), *args], env=env, cwd=env["HOME"], capture_output=True, text=True,
                              timeout=60)


class DossiersDeNoctalia(Base):
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
        # settings.toml (hooks) est du code : pas remis sans --avec-code
        self.assertEqual((self.r / "b-noctalia/noctalia/settings.toml").read_text(), "avant\n")
        self.assertIn("--avec-code", r.stdout)
        r = self.lancer(env_b, "restaurer", str(archive), "--avec-code")
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
        r = self.lancer(env, "restaurer", str(archive), "--avec-code")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual((home / ".local/state/noctalia/settings.toml").read_text(), "x = 1\n")


class SauvegardeSure(Base):
    """Sauvegarde qui échoue sans abîmer l'ancienne, fonds hors de HOME, archive piégée, messages sans trace."""

    def test_deuxieme_sauvegarde_qui_echoue_laisse_la_premiere(self):
        home, env = self.maison("e")
        self.reglages(home)
        r = self.lancer(env)
        self.assertEqual(r.returncode, 0, r.stderr)
        archive = next(home.glob("nc-sauvegarde-*.tar.gz"))
        avant = archive.read_bytes()
        # Erreur simulée (marche aussi en root, où chmod 000 ne bloque rien) : tarfile.add échoue
        (self.r / "faux").mkdir()
        (self.r / "faux/sitecustomize.py").write_text(
            "import tarfile\n"
            "def _add(*a, **k):\n    raise PermissionError(13, 'simulé')\n"
            "tarfile.TarFile.add = _add\n")
        env2 = dict(env, PYTHONPATH=str(self.r / "faux"))
        (home / ".config/nc/reglages.conf").write_text("LANGUE=en\n")
        r = self.lancer(env2)
        self.assertNotEqual(r.returncode, 0)
        self.assertNotIn("Traceback", r.stderr)
        self.assertIn("pas été touchée", r.stderr)
        self.assertEqual(archive.read_bytes(), avant)
        self.assertEqual([p.name for p in home.glob(".nc-sauvegarde-*")], [])
        # Vrai fichier illisible (sauf en root)
        if os.geteuid() != 0:
            (home / ".config/nc/reglages.conf").chmod(0)
            r = self.lancer(env)
            self.assertNotEqual(r.returncode, 0)
            self.assertNotIn("Traceback", r.stderr)
            self.assertEqual(archive.read_bytes(), avant)
            self.assertEqual([p.name for p in home.glob(".nc-sauvegarde-*")], [])

    def test_fonds_hors_de_home_aller_retour(self):
        home, env = self.maison("f")
        ext = self.r / "ext-f/fonds"
        ext.mkdir(parents=True)
        (ext / "mer.png").write_bytes(b"\x89PNG-mer")
        self.reglages(home, FONDS_DOSSIER=ext)
        r = self.lancer(env, "--fonds")
        self.assertEqual(r.returncode, 0, r.stderr)
        archive = next(home.glob("nc-sauvegarde-*.tar.gz"))
        with tarfile.open(archive) as t:
            self.assertIn(".nc-fonds-externes/mer.png", t.getnames())
            self.assertFalse([n for n in t.getnames() if ".." in n])
        r = self.lancer(env, "voir", str(archive))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("mer.png", r.stdout)
        self.assertNotIn("ignoré", r.stdout)
        # Autre PC : ses fonds sont ailleurs, l'image y arrive
        home_b, env_b = self.maison("g")
        ext_b = home_b / "Fonds-g"
        self.reglages(home_b, FONDS_DOSSIER=ext_b)
        r = self.lancer(env_b, "restaurer", str(archive))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual((ext_b / "mer.png").read_bytes(), b"\x89PNG-mer")
        # Réglage hors de HOME sur le PC qui restaure : jamais utilisé, le dossier par défaut le remplace
        home_c, env_c = self.maison("g2")
        self.reglages(home_c, FONDS_DOSSIER=self.r / "ext-g2")
        r = self.lancer(env_c, "restaurer", str(archive))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertFalse((self.r / "ext-g2").exists())
        self.assertEqual((home_c / "Pictures/Wallpapers/mer.png").read_bytes(), b"\x89PNG-mer")

    def test_fonds_sous_home_vers_un_autre_pc(self):
        home, env = self.maison("i")
        (home / "Images/Fonds").mkdir(parents=True)
        (home / "Images/Fonds/b.png").write_bytes(b"\x89PNG-B")
        self.reglages(home, FONDS_DOSSIER=home / "Images/Fonds")
        self.assertEqual(self.lancer(env, "--fonds").returncode, 0)
        archive = next(home.glob("nc-sauvegarde-*.tar.gz"))
        with tarfile.open(archive) as t:
            self.assertIn(".nc-fonds-externes/b.png", t.getnames())
        home_b, env_b = self.maison("j")
        self.reglages(home_b, FONDS_DOSSIER=home_b / "Pictures/Wallpapers")
        r = self.lancer(env_b, "restaurer", str(archive))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual((home_b / "Pictures/Wallpapers/b.png").read_bytes(), b"\x89PNG-B")
        self.assertFalse((home_b / "Images").exists())

    def test_ancienne_archive_fonds_a_son_chemin(self):
        home, env = self.maison("k")
        self.reglages(home, FONDS_DOSSIER=home / "Images/Fonds")
        ancienne = self.piegee([("Images/Fonds/c.png", tarfile.REGTYPE, b"\x89PNG-C", 0o644),
                                ("Autre/d.png", tarfile.REGTYPE, b"D", 0o644)])
        r = self.lancer(env, "restaurer", str(ancienne))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual((home / "Images/Fonds/c.png").read_bytes(), b"\x89PNG-C")
        self.assertFalse((home / "Autre").exists())
        self.assertIn("ignoré", r.stdout)

    def test_fonds_sous_home_garde_son_chemin(self):
        home, env = self.maison("h")
        (home / "Images/fonds").mkdir(parents=True)
        (home / "Images/fonds/a.png").write_bytes(b"\x89PNG-A")
        self.reglages(home, FONDS_DOSSIER=home / "Images/fonds")
        self.assertEqual(self.lancer(env, "--fonds").returncode, 0)
        archive = next(home.glob("nc-sauvegarde-*.tar.gz"))
        (home / "Images/fonds/a.png").unlink()
        r = self.lancer(env, "restaurer", str(archive))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual((home / "Images/fonds/a.png").read_bytes(), b"\x89PNG-A")

    def test_archive_piegee_ignoree(self):
        home, env = self.maison("p")
        (home / ".bashrc").write_text("original\n")
        archive = self.piegee([
            (".bashrc", tarfile.REGTYPE, b"evil\n", 0o644),
            (".local/bin/nc-reglages", tarfile.REGTYPE, b"#!/bin/sh\ntouch pwned\n", 0o755),
            (".config/nc-autre/x", tarfile.REGTYPE, b"x", 0o644),
            ("/tmp/absolu-nc-test", tarfile.REGTYPE, b"x", 0o644),
            (".config/nc/../../.bashrc", tarfile.REGTYPE, b"evil", 0o644),
            (".config/nc/lien", tarfile.SYMTYPE, ".local/bin", 0o777),
            (".config/nc/dur", tarfile.LNKTYPE, ".bashrc", 0o644),
            (".config/nc/fifo", tarfile.FIFOTYPE, "", 0o644),
            (".config/nc/reglages.conf", tarfile.REGTYPE, b"LANGUE=fr\n", 0o4755),
        ])
        r = self.lancer(env, "voir", str(archive))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("ignoré", r.stdout)
        r = self.lancer(env, "restaurer", str(archive))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("ignoré", r.stdout)
        self.assertEqual((home / ".bashrc").read_text(), "original\n")
        self.assertEqual((home / ".local/bin/nc-reglages").read_text(), "#!/bin/sh\nexit 0\n")
        self.assertFalse((home / "pwned").exists())
        for n in (".config/nc-autre", ".config/nc/lien", ".config/nc/dur", ".config/nc/fifo"):
            self.assertFalse(os.path.lexists(home / n), n)
        # Le seul membre sûr est remis, sans setuid
        f = home / ".config/nc/reglages.conf"
        self.assertEqual(f.read_text(), "LANGUE=fr\n")
        self.assertEqual(stat.S_IMODE(f.stat().st_mode) & 0o7022, 0)

    def test_lien_a_la_destination_pas_suivi(self):
        home, env = self.maison("l")
        cible = home / ".local/bin"
        (home / ".config").mkdir()
        os.symlink(cible, home / ".config/nc")           # ~/.config/nc → ~/.local/bin
        archive = self.piegee([(".config/nc/reglages.conf", tarfile.REGTYPE, b"LANGUE=fr\n", 0o644)])
        r = self.lancer(env, "restaurer", str(archive))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("ignoré", r.stdout)
        self.assertEqual(sorted(p.name for p in cible.iterdir()), ["nc-reglages"])
        # Fichier final remplacé par un lien : pas suivi non plus
        (home / ".config/nc").unlink()
        (home / ".config/nc").mkdir()
        os.symlink(home / ".bashrc-cible", home / ".config/nc/reglages.conf")
        r = self.lancer(env, "restaurer", str(archive))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertFalse((home / ".bashrc-cible").exists())

    def test_aller_retour_normal_contenu_et_droits(self):
        home, env = self.maison("n")
        (home / ".config/nc/animations").mkdir(parents=True)
        (home / ".config/nc/animations/a.conf").write_text("a\n")
        (home / ".config/nc/animations/a.conf").chmod(0o640)
        (home / ".config/kitty").mkdir(parents=True)
        (home / ".config/kitty/perso.conf").write_text("k\n")
        (home / ".config/kitty/perso.conf").chmod(0o755)
        (home / ".zshrc.perso").write_text("z\n")
        self.assertEqual(self.lancer(env).returncode, 0)
        archive = next(home.glob("nc-sauvegarde-*.tar.gz"))
        for p in (home / ".config/nc/animations/a.conf", home / ".config/kitty/perso.conf", home / ".zshrc.perso"):
            p.unlink()
        r = self.lancer(env, "restaurer", str(archive), "--avec-code")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertNotIn("ignoré", r.stdout)
        self.assertEqual((home / ".config/nc/animations/a.conf").read_text(), "a\n")
        self.assertEqual(stat.S_IMODE((home / ".config/nc/animations/a.conf").stat().st_mode), 0o640 | 0o600)
        self.assertEqual(stat.S_IMODE((home / ".config/kitty/perso.conf").stat().st_mode), 0o755)
        self.assertEqual((home / ".zshrc.perso").read_text(), "z\n")

    def test_messages_sans_trace(self):
        home, env = self.maison("m")
        r = self.lancer(env, "voir", str(home / "absent.tar.gz"))
        self.assertNotEqual(r.returncode, 0)
        self.assertNotIn("Traceback", r.stderr)
        self.assertIn("introuvable", r.stderr)
        casse = home / "casse.tar.gz"
        casse.write_bytes(b"ceci n'est pas une archive")
        for cmd in ("voir", "restaurer"):
            r = self.lancer(env, cmd, str(casse))
            self.assertNotEqual(r.returncode, 0, cmd)
            self.assertNotIn("Traceback", r.stderr, cmd)
            self.assertTrue(r.stderr.strip(), cmd)
        # Archive coupée en deux
        self.reglages(home)
        self.assertEqual(self.lancer(env).returncode, 0)
        archive = next(home.glob("nc-sauvegarde-*.tar.gz"))
        data = archive.read_bytes()
        coupee = home / "coupee.tar.gz"
        coupee.write_bytes(data[:len(data) // 2])
        for cmd in ("voir", "restaurer"):
            r = self.lancer(env, cmd, str(coupee))
            self.assertNotIn("Traceback", r.stderr, cmd)

    def test_nc_reglages_absent_restauration_faite(self):
        home, env = self.maison("o")
        self.reglages(home)
        self.assertEqual(self.lancer(env).returncode, 0)
        archive = next(home.glob("nc-sauvegarde-*.tar.gz"))
        (home / ".config/nc/reglages.conf").write_text("LANGUE=en\n")
        (home / ".local/bin/nc-reglages").unlink()
        r = self.lancer(env, "restaurer", str(archive))
        # La restauration est faite : code 0, mais on dit que rien n'a été appliqué
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertNotIn("Traceback", r.stderr)
        self.assertIn("nc-reglages", r.stderr)
        self.assertEqual((home / ".config/nc/reglages.conf").read_text(), "LANGUE=fr\n")


class CodeEtLimites(Base):
    """Restauration d'une archive reçue d'un autre : pas de code, pas d'écriture hors liste, limites de taille."""

    def test_fonds_dossier_dangereux_jamais_utilise(self):
        # A1/A2 : « ~ », « ~/ », ~/bin (dans le PATH), /proc/self/cwd/…, dossier caché : le dossier par défaut est pris
        for i, reglage in enumerate(["~", "~/", "~/bin", "/proc/self/cwd/.local/bin", "~/.local/bin", "/usr/bin"]):
            home, env = self.maison(f"d{i}")
            (home / "bin").mkdir()
            env["PATH"] = f"{home}/bin:" + env["PATH"]
            self.reglages(home, FONDS_DOSSIER=reglage)
            archive = self.piegee([
                (".nc-fonds-externes/.local/bin/nc-reglages", tarfile.REGTYPE, b"#!/bin/sh\ntouch pwned\n", 0o755),
                (".nc-fonds-externes/nc-reglages", tarfile.REGTYPE, b"#!/bin/sh\ntouch pwned\n", 0o755),
                (".nc-fonds-externes/mer.PNG", tarfile.REGTYPE, b"\x89PNG", 0o755),
            ])
            r = self.lancer(env, "restaurer", str(archive))
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual((home / ".local/bin/nc-reglages").read_text(), "#!/bin/sh\nexit 0\n", reglage)
            self.assertEqual(os.listdir(home / "bin"), [], reglage)
            self.assertFalse((home / "pwned").exists(), reglage)
            image = home / "Pictures/Wallpapers/mer.PNG"
            self.assertEqual(image.read_bytes(), b"\x89PNG", reglage)
            self.assertEqual(stat.S_IMODE(image.stat().st_mode), 0o644, reglage)
            self.assertEqual(os.listdir(home / "Pictures/Wallpapers"), ["mer.PNG"], reglage)
            self.assertIn("ignoré", r.stdout)

    def test_code_pas_remis_sans_avec_code(self):
        home, env = self.maison("c1")
        (home / ".config/nc").mkdir(parents=True)
        (home / ".config/nc/raccourcis.conf").write_text("ajout\tSUPER+X\tcommande\tgarde-moi\tdeja la\n")
        archive = self.piegee([
            (".config/hypr/perso.lua", tarfile.REGTYPE, b"os.execute('touch pwned')", 0o644),
            (".zshrc.perso", tarfile.REGTYPE, b"touch pwned", 0o644),
            (".config/kitty/perso.conf", tarfile.REGTYPE, b"x", 0o644),
            (".config/nc/animations/a.py", tarfile.REGTYPE, b"x", 0o755),
            (".config/noctalia/zz-dock.toml", tarfile.REGTYPE, b"x", 0o644),
            (".local/state/noctalia/settings.toml", tarfile.REGTYPE, b"x", 0o644),
            (".config/noctalia/palettes/p.json", tarfile.REGTYPE, b"{}", 0o644),
            (".config/nc/raccourcis.conf", tarfile.REGTYPE,
             b"# c\nchange\t64:code:70\t0:code:36\tnom\naucun\t65:code:9\n"
             b"ajout\tSUPER+X\tcommande\tgarde-moi\tdeja la\n"
             b"ajout\tSUPER + code:28\tcommande\ttouch pwned\tmal\najout\tSUPER + code:29\tappli\tfirefox\tbien\n"
             b"ajout\tSUPER_L\tappli\tsuper-seul\tmal\najout\tCTRL + SUPERSCRIPT\tappli\tsuperscript\tmal\n"
             b"ajout\t0:code:36\tappli\tsans-super\tmal\ninconnu\ta\tb\n", 0o644),
        ])
        r = self.lancer(env, "voir", str(archive))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("contient du code", r.stdout)
        r = self.lancer(env, "restaurer", str(archive))
        self.assertEqual(r.returncode, 0, r.stderr)
        for n in (".config/hypr/perso.lua", ".zshrc.perso", ".config/kitty/perso.conf", ".config/nc/animations",
                  ".config/noctalia/zz-dock.toml", ".local/state/noctalia/settings.toml"):
            self.assertFalse((home / n).exists(), n)
            self.assertIn(n, r.stdout)
        self.assertIn("si c'est ta propre sauvegarde : nc-sauvegarde restaurer --avec-code", r.stdout.lower())
        self.assertIn("--avec-code", r.stdout)
        self.assertTrue((home / ".config/noctalia/palettes/p.json").exists())
        conf = (home / ".config/nc/raccourcis.conf").read_text()
        self.assertIn("garde-moi", conf)          # déjà là à l'identique
        self.assertNotIn("touch pwned", conf)
        self.assertNotIn("inconnu", conf)
        self.assertIn("firefox", conf)
        self.assertNotIn("change", conf)
        self.assertNotIn("aucun", conf)
        self.assertNotIn("sans-super", conf)
        self.assertNotIn("super-seul", conf)               # SUPER_L : pas le modificateur SUPER
        self.assertNotIn("superscript", conf)
        self.assertIn("7 ligne(s) de raccourcis non remise(s)", r.stdout)
        self.assertEqual(list(home.glob(".config/*/.nc-restauration-*")), [])
        # Avec --avec-code : tout est remis, tel quel
        r = self.lancer(env, "restaurer", str(archive), "--avec-code")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual((home / ".config/hypr/perso.lua").read_text(), "os.execute('touch pwned')")
        self.assertTrue((home / ".config/nc/animations/a.py").exists())
        self.assertIn("touch pwned", (home / ".config/nc/raccourcis.conf").read_text())
        conf = (home / ".config/nc/raccourcis.conf").read_text()
        self.assertIn("change\t64:code:70", conf)             # ta sauvegarde : tout revient, change et aucun compris
        self.assertIn("aucun\t65:code:9", conf)

    def test_enfants_d_un_fichier_refuses(self):
        home, env = self.maison("c2")
        archive = self.piegee([
            (".config/hypr/perso.lua/y", tarfile.REGTYPE, b"x", 0o644),
            (".face/z", tarfile.REGTYPE, b"x", 0o644),
            (".config/nc/reglages.conf/z", tarfile.REGTYPE, b"x", 0o644),
        ])
        r = self.lancer(env, "restaurer", str(archive), "--avec-code")
        self.assertEqual(r.returncode, 0, r.stderr)
        for n in (".config/hypr", ".face", ".config/nc"):
            self.assertFalse((home / n).exists(), n)

    def test_noms_affiches_sans_caracteres_de_controle(self):
        home, env = self.maison("c3")
        archive = self.piegee([("\x1b]52;c;ZXZpbA==\x07\x1b[2Kmal", tarfile.REGTYPE, b"x", 0o644)])
        for cmd in ("voir", "restaurer"):
            r = self.lancer(env, cmd, str(archive))
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertNotIn("\x1b", r.stdout + r.stderr)
            self.assertNotIn("\x07", r.stdout + r.stderr)
            self.assertIn("\\x1b]52", r.stdout)

    def test_trop_gros_ou_trop_de_membres(self):
        home, env = self.maison("c4")
        # Un membre qui annonce 3 Gio (un « creux » de quelques octets peut le faire) : refusé avant toute écriture.
        # Appel direct de la fonction : fabriquer une vraie archive de 3 Gio serait long.
        mod = self.module()
        gros = tarfile.TarInfo(".face")
        gros.size = 3 * 2 ** 30
        with self.assertRaises(SystemExit) as e:
            mod.verifier_taille([(gros, ".face")], None)
        self.assertRegex(str(e.exception), "rien n.est écrit|nothing is written")
        # Trop de membres
        with tarfile.open(self.r / "beaucoup.tar.gz", "w:gz") as t:
            for i in range(20001):
                t.addfile(tarfile.TarInfo(f".config/noctalia/palettes/{i}.json"))
        r = self.lancer(env, "restaurer", str(self.r / "beaucoup.tar.gz"))
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("trop d'éléments", r.stderr)
        self.assertNotIn("Traceback", r.stderr)
        self.assertFalse((home / ".config/noctalia").exists())

    def test_original_garde_une_fois_et_dossier_avant_unique(self):
        home, env = self.maison("c5")
        (home / ".face").write_text("original\n")
        archive = self.piegee([(".face", tarfile.REGTYPE, b"v1\n", 0o644), (".face", tarfile.REGTYPE, b"v2\n", 0o644)])
        r = self.lancer(env, "restaurer", str(archive))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual((home / ".face").read_text(), "v2\n")
        copies = list((home / ".cache/nc/avant-restauration").glob("*/.face"))
        self.assertEqual([c.read_text() for c in copies], ["original\n"])
        # Une 2e restauration dans la même seconde ne réutilise pas le même dossier
        self.assertEqual(self.lancer(env, "restaurer", str(archive)).returncode, 0)
        self.assertEqual(len(list((home / ".cache/nc/avant-restauration").iterdir())), 2)

    def test_membre_en_erreur_ignore_sans_arreter(self):
        home, env = self.maison("c6")
        (home / ".config/noctalia/palettes").mkdir(parents=True)
        (home / ".config/noctalia/palettes/x").write_text("un fichier\n")
        archive = self.piegee([
            (".config/noctalia/palettes/x/y.json", tarfile.REGTYPE, b"1", 0o644),   # x est un fichier : ENOTDIR
            (".config/noctalia/palettes/" + "a" * 300 + ".json", tarfile.REGTYPE, b"1", 0o644),   # nom trop long
            (".config/noctalia/palettes/bon.json", tarfile.REGTYPE, b"{}", 0o644),
        ])
        r = self.lancer(env, "restaurer", str(archive))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertNotIn("Traceback", r.stderr)
        self.assertEqual((home / ".config/noctalia/palettes/bon.json").read_text(), "{}")
        self.assertEqual((home / ".config/noctalia/palettes/x").read_text(), "un fichier\n")
        self.assertIn("2 élément(s)", r.stdout)

    def test_aucun_dossier_des_fonds_sur(self):
        home, env = self.maison("s1")
        (home / "Pictures/Wallpapers").mkdir(parents=True)
        env["PATH"] = f"{home}/Pictures/Wallpapers:" + env["PATH"]       # le dossier par défaut devient interdit
        self.reglages(home, FONDS_DOSSIER="~")
        archive = self.piegee([(".nc-fonds-externes/mer.png", tarfile.REGTYPE, b"\x89PNG", 0o644),
                               (".face", tarfile.REGTYPE, b"x", 0o644)])
        r = self.lancer(env, "restaurer", str(archive))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertNotIn("Traceback", r.stderr)
        self.assertIn("aucun dossier sûr", r.stdout)
        self.assertEqual(os.listdir(home / "Pictures/Wallpapers"), [])
        self.assertTrue((home / ".face").exists())

    def test_fichiers_trop_gros_refuses(self):
        home, env = self.maison("s2")
        archive = self.piegee([
            (".config/nc/raccourcis.conf", tarfile.REGTYPE, b"\n" * (1024 ** 2 + 1), 0o644),
            (".config/nc/style.conf", tarfile.REGTYPE, b"A=1\n", 0o644),
            (".face", tarfile.REGTYPE, b"x" * (5 * 1024 ** 2), 0o644),
        ])
        r = self.lancer(env, "restaurer", str(archive))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertFalse((home / ".config/nc/raccourcis.conf").exists())
        self.assertTrue((home / ".config/nc/style.conf").exists())
        self.assertEqual((home / ".face").stat().st_size, 5 * 1024 ** 2)
        archive = self.piegee([(".face", tarfile.REGTYPE, b"x" * (10 * 1024 ** 2 + 1), 0o644)])
        (home / ".face").unlink()
        self.lancer(env, "restaurer", str(archive))
        self.assertFalse((home / ".face").exists())

    def test_lecture_arretee_au_plafond(self):
        mod = self.module()
        lus = []

        def membres():
            for i in range(10 * mod.MAX_MEMBRES):
                lus.append(i)
                yield tarfile.TarInfo(f"d{i}")
        with self.assertRaises(SystemExit):
            mod.lire_membres(membres(), None, False)
        self.assertEqual(len(lus), mod.MAX_MEMBRES + 1)

    def test_reglages_de_securite_gardes_en_local(self):
        home, env = self.maison("s3")
        (home / ".config/nc").mkdir(parents=True)
        (home / ".config/nc/reglages.conf").write_text("IA_MODE = non\nVEILLE_VERROU=5\nLANGUE=en\nFONDS_DOSSIER=/x\nMAJ_VERIFIER=oui\n")
        archive = self.piegee([(".config/nc/reglages.conf", tarfile.REGTYPE,
            b"# commentaire\nIA_MODE=oui\nVEILLE_VERROU=0\nLANGUE=fr\nNOEUD_JARVIS=oui\nAPPLI_TERMINAL=sh -c evil\nMAJ_VERIFIER=non\n"
            b"mauvaise ligne; touch pwned\nminuscule=1\nSTYLE=apple\n", 0o644)])
        r = self.lancer(env, "restaurer", str(archive))
        self.assertEqual(r.returncode, 0, r.stderr)
        lignes = (home / ".config/nc/reglages.conf").read_text().splitlines()
        self.assertEqual(sorted(lignes), sorted(["IA_MODE=non", "VEILLE_VERROU=5", "LANGUE=fr", "FONDS_DOSSIER=/x", "MAJ_VERIFIER=oui", "STYLE=apple"]))
        # « IA_MODE = non » (avec espaces, comme le lisent nc-ia et nc-reglages) : la valeur locale reste, réécrite CLE=valeur
        for cle in ("IA_MODE", "VEILLE_VERROU", "NOEUD_JARVIS", "APPLI_TERMINAL"):
            self.assertIn(cle, r.stdout)
        # Avec --avec-code : tel quel
        r = self.lancer(env, "restaurer", str(archive), "--avec-code")
        self.assertIn("IA_MODE=oui", (home / ".config/nc/reglages.conf").read_text())

    def test_image_deguisee_ignoree(self):
        home, env = self.maison("s4")
        (home / "Pictures/Wallpapers").mkdir(parents=True)
        archive = self.piegee([
            (".nc-fonds-externes/faux.png", tarfile.REGTYPE, b"<svg onload=alert(1)>", 0o644),
            (".nc-fonds-externes/vrai.jpg", tarfile.REGTYPE, b"\xff\xd8\xff\xe0JFIF", 0o644),
            (".nc-fonds-externes/vrai.webp", tarfile.REGTYPE, b"RIFF\0\0\0\0WEBPVP8 ", 0o644),
            (".nc-fonds-externes/vrai.avif", tarfile.REGTYPE, b"\0\0\0\x1cftypavif", 0o644),
        ])
        r = self.lancer(env, "restaurer", str(archive))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(sorted(os.listdir(home / "Pictures/Wallpapers")), ["vrai.avif", "vrai.jpg", "vrai.webp"])
        self.assertIn("faux.png", r.stdout)
        self.assertEqual(list((home / "Pictures/Wallpapers").glob(".nc-restauration-*")), [])



class PourLeCloud(Base):
    """I3 : la version qui part sur le Cloud JARVIS. Aucun secret (clé de JARVIS, jeton, export de shell ou de Lua, clé
    ajoutée à la main, commande avec Authorization) dans l'archive envoyée, ni dans son contenu décompressé."""
    SECRETS = ("CLE-JARVIS-7f3a9", "JETON-TROUSSEAU-51bc", "X_TOKEN_VALEUR-zz81", "LUA_TOKEN-qq42", "MA_CLE_API_VAL-ww07",
               "Bearer-AUTH-hh63", "COMMENTAIRE-SECRET-kk11", "VILLE-PRIVEE-Tarascon")

    def preparer_home(self):
        home, env = self.maison("cloud")
        (home / ".config/nc").mkdir(parents=True, exist_ok=True)
        (home / ".config/nc/assistant.conf").write_text("SECRET_KEY=CLE-JARVIS-7f3a9\n")
        (home / ".local/share/keyrings").mkdir(parents=True)
        (home / ".local/share/keyrings/login.keyring").write_text("JETON-TROUSSEAU-51bc")
        (home / ".zshrc.perso").write_text("export X_TOKEN=X_TOKEN_VALEUR-zz81\n")
        (home / ".config/hypr").mkdir(parents=True)
        (home / ".config/hypr/perso.lua").write_text('hl.env("LUA", "LUA_TOKEN-qq42")\n')
        (home / ".config/nc/reglages.conf").write_text(
            "LANGUE=fr\nTHEME=sombre\nMA_CLE_API=MA_CLE_API_VAL-ww07\nmon_password=x\nLONG=" + "a" * 600 + "\n"
            "# COMMENTAIRE-SECRET-kk11\nMETEO_VILLE=VILLE-PRIVEE-Tarascon\nIA_MODE=non\n DOCK = oui\nGARMIN_JARVIS=oui\n"
            "VPN_KILLSWITCH=non\nDOCK_TAILLE=99999\n")
        (home / ".config/nc/raccourcis.conf").write_text(
            "ajout\tSUPER + B\tappli\tfirefox\tNavigateur\n"
            "ajout\tSUPER + K\tcommande\tcurl -H 'Authorization: Bearer-AUTH-hh63' x\tAppel\n# COMMENTAIRE-SECRET-kk11\n")
        (home / ".config/nc/style.conf").write_text("STYLE=verre\n")
        (home / ".config/noctalia/palettes").mkdir(parents=True)
        (home / ".config/noctalia/palettes/a.json").write_text("{}")
        (home / ".config/noctalia/palettes/lien.json").symlink_to(home / ".zshrc.perso")
        os.link(home / ".zshrc.perso", home / ".config/noctalia/palettes/dur.json")     # lien dur : son contenu est un autre
        (home / ".config/noctalia/palettes/.cachee.json").write_text("{}")
        (home / ".config/noctalia/palettes/sous").mkdir()
        (home / ".config/noctalia/palettes/sous/x.json").write_text("{}")
        (home / ".face").write_bytes(b"\x89PNG\r\n\x1a\nimage")
        return home, env

    def test_aucun_secret_contenu_exact_entetes_anonymes(self):
        home, env = self.preparer_home()
        sortie = self.r / "envoi.tar.gz"
        r = self.lancer(env, "creer", "--pour-le-cloud", "--sortie", str(sortie))
        self.assertEqual(r.returncode, 0, r.stderr)
        brut = sortie.read_bytes()
        decompresse = gzip.decompress(brut)
        for x in self.SECRETS:
            self.assertNotIn(x.encode(), brut, x)
            self.assertNotIn(x.encode(), decompresse, x)
        with tarfile.open(sortie) as t:
            noms = sorted(m.name for m in t)
            self.assertEqual(noms, [".config/nc/raccourcis.conf", ".config/nc/reglages.conf", ".config/noctalia/palettes/a.json", ".face"])
            for m in t.getmembers():
                self.assertEqual((m.uid, m.gid, m.uname, m.gname, m.type), (0, 0, "", "", tarfile.REGTYPE), m.name)
                self.assertEqual(m.mode, 0o600 if m.name.startswith(".config/nc/") else 0o644, m.name)
            regl = t.extractfile(".config/nc/reglages.conf").read().decode()
            racc = t.extractfile(".config/nc/raccourcis.conf").read().decode()
        self.assertEqual(regl, "LANGUE=fr\nDOCK=oui\n")             # la liste blanche de nc-reglages, valeurs valides
        self.assertEqual(racc, "ajout\tSUPER + B\tappli\tfirefox\tNavigateur\n")
        self.assertIn("10 ligne(s) de réglages écartée(s)", r.stdout)    # 12 lignes, 2 parties
        self.assertIn("4 palette(s) écartée(s)", r.stdout)               # lien, lien dur, cachée, dossier
        self.assertIn("2 ligne(s) de raccourcis écartée(s)", r.stdout)
        self.assertEqual(oct(sortie.stat().st_mode & 0o777), oct(0o600))      # umask de l'appelant ; ici mkstemp
        # La reprise de cette archive : rien de nouveau ne vient du code, et voir la lit
        r = self.lancer(env, "voir", "--pour-le-cloud", str(sortie))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("~/.config/nc/reglages.conf", r.stdout)
        self.assertIn("2 réglage(s)", r.stdout)
        self.assertIn("LANGUE, DOCK", r.stdout)
        # Une photo qui n'est pas une image ne part pas
        (home / ".face").write_bytes(b"#!/bin/sh\necho x\n" * 4)
        self.assertEqual(self.lancer(env, "creer", "--pour-le-cloud", "--sortie", str(sortie)).returncode, 0)
        with tarfile.open(sortie) as t:
            self.assertNotIn(".face", t.getnames())

    def archive_cloud(self, membres, nom="cloud.tar.gz"):
        """Une archive au format de celles du cloud : [(nom, contenu, mode)], fichiers ordinaires."""
        f = self.r / nom
        with tarfile.open(f, "w:gz") as t:
            for n, contenu, mode in membres:
                ti = tarfile.TarInfo(n)
                ti.size, ti.mode = len(contenu), mode
                t.addfile(ti, io.BytesIO(contenu))
        return f

    PNG = b"\x89PNG\r\n\x1a\n" + b"x" * 20

    def test_reprise_hostile_fusion_et_reglages_sensibles_gardes(self):
        home, env = self.maison("hostile")
        (home / ".config/nc").mkdir(parents=True, exist_ok=True)
        pc = "LANGUE=fr\nPERSO_A_MOI=1\nGARMIN_JARVIS=non\nVPN_KILLSWITCH=oui\nIA_MODE=non\n DOCK = oui\n# mon commentaire\n"
        (home / ".config/nc/reglages.conf").write_text(pc)
        sensibles = {"GARMIN_JARVIS": "oui", "DICTEE_SECOURS": "oui", "NOTIFS_IA": "oui", "TELEGRAM_AGENTS": "oui",
                     "VPN_KILLSWITCH": "non", "VPN_IP_PUBLIQUE": "oui", "VPN_IP_SERVICE": "https://espion.example/ip",
                     "CLOUD_JARVIS": "oui", "VEILLE_VERROU": "0", "IA_MODE": "cloud", "GOOGLE_INTEGRATION": "oui",
                     "MAJ_SYSTEME": "auto", "NOEUD_JARVIS": "oui", "SESSIONS_CAPTURE": "oui", "GPU_JAMAIS_RTX": "x",
                     "PANNES_IGNORER": "tout", "FONDS_DOSSIER": "/tmp", "X": "$(touch PWN)"}
        regl = "LANGUE=en\nDOCK=non\n" + "".join(f"{k}={v}\n" for k, v in sensibles.items())
        f = self.archive_cloud([(".config/nc/reglages.conf", regl.encode(), 0o644), (".face", self.PNG, 0o4755)])
        r = self.lancer(env, "restaurer", "--pour-le-cloud", str(f))
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        apres = (home / ".config/nc/reglages.conf").read_text()
        self.assertEqual(apres, "LANGUE=en\nPERSO_A_MOI=1\nGARMIN_JARVIS=non\nVPN_KILLSWITCH=oui\nIA_MODE=non\nDOCK=non\n# mon commentaire\n")
        for k in sensibles:
            self.assertNotIn(k + "=" + sensibles[k], apres, k)
        self.assertEqual(stat.S_IMODE((home / ".face").stat().st_mode), 0o644)
        self.assertIn("non repris", r.stdout)
        self.assertNotIn("--avec-code", r.stdout + r.stderr)

    def test_reprise_refuse_tout_element_hors_liste(self):
        home, env = self.maison("hors-liste")
        self.reglages(home, LANGUE="fr")
        avant = (home / ".config/nc/reglages.conf").read_text()
        bon = (".config/nc/reglages.conf", b"LANGUE=en\n", 0o600)
        for intrus in ((".nc-fonds-externes/a.png", self.PNG, 0o644), ("Pictures/Wallpapers/a.png", self.PNG, 0o644),
                       (".config/nc/style.conf", b"STYLE=x\n", 0o644), (".config/nc/style-avant", b"--x\n", 0o644),
                       (".config/noctalia/palettes/.cache.json", b"{}", 0o644), (".config/noctalia/palettes/sous/x.json", b"{}", 0o644),
                       (".config/noctalia/palettes/\x1b[31m.json", b"{}", 0o644), (".zshrc.perso", b"touch PWN", 0o644),
                       (".config/hypr/perso.lua", b"x", 0o644)):
            with self.subTest(intrus=intrus[0]):
                f = self.archive_cloud([bon, intrus])
                for cmd in ("voir", "restaurer"):
                    r = self.lancer(env, cmd, "--pour-le-cloud", str(f))
                    self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
                    self.assertIn("rien à faire dans une sauvegarde du cloud", r.stderr)
                self.assertEqual((home / ".config/nc/reglages.conf").read_text(), avant)
        # Une photo de profil qui n'est pas une image : pas remise (le reste l'est)
        r = self.lancer(env, "restaurer", "--pour-le-cloud", str(self.archive_cloud([bon, (".face", b"#!/bin/sh\n" * 4, 0o755)])))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertFalse((home / ".face").exists())
        self.assertIn("LANGUE=en", (home / ".config/nc/reglages.conf").read_text())

    def test_vraies_bombes_refusees_avant_lecture(self):
        home, env = self.maison("bombes")
        def tar_brut(*blocs):
            return b"".join(blocs) + bytes(1024)
        def entete(nom, type_, taille):
            ti = tarfile.TarInfo(nom)
            ti.size = taille if type_ == tarfile.REGTYPE else 0
            b = bytearray(ti.tobuf(tarfile.USTAR_FORMAT))
            b[156:157] = type_
            b[124:136] = b"%011o\0" % taille
            b[148:156] = b"        "
            b[148:156] = b"%06o\0 " % sum(b)
            return bytes(b)
        bombes = {}
        z = io.BytesIO()                                         # bombe gzip : 100 Mio de zéros (moins de 200 Kio compressés)
        with tarfile.open(fileobj=z, mode="w:gz") as t:
            ti = tarfile.TarInfo(".face")
            ti.size = 100 * 1024 ** 2
            t.addfile(ti, io.BytesIO(bytes(ti.size)))
        bombes["gzip"] = (z.getvalue(), "décompressée")
        x = io.BytesIO()                                         # en-tête PAX de 1 Mio
        with tarfile.open(fileobj=x, mode="w:gz", format=tarfile.PAX_FORMAT) as t:
            ti = tarfile.TarInfo(".face")
            ti.pax_headers = {"comment": "x" * 1024 ** 2}
            ti.size = len(self.PNG)
            t.addfile(ti, io.BytesIO(self.PNG))
        bombes["pax"] = (x.getvalue(), "type refusé")
        g = io.BytesIO()                                         # nom long GNU (« L »)
        with tarfile.open(fileobj=g, mode="w:gz", format=tarfile.GNU_FORMAT) as t:
            ti = tarfile.TarInfo(".config/noctalia/palettes/" + "p" * 200 + ".json")
            t.addfile(ti, io.BytesIO(b""))
        bombes["gnu"] = (g.getvalue(), "type refusé")
        bombes["inconnu"] = (gzip.compress(tar_brut(entete(".face", b"Z", 1024 ** 3))), "type refusé")
        bombes["taille-fausse"] = (gzip.compress(tar_brut(entete(".face", tarfile.REGTYPE, 1024 ** 2))[:-1024] + b"x" * 10), "coupée")
        un = gzip.compress(tar_brut(entete(".face", tarfile.REGTYPE, 0)))
        bombes["concatenee"] = (un + un, "après la fin")
        bombes["tronquee"] = (un[:len(un) // 2], "coupée")
        bombes["fin-gzip-absente"] = (un[:-8], "coupée")       # le tar est entier, le flux gzip non
        for nom, (octets, raison) in bombes.items():
            with self.subTest(nom):
                f = self.r / (nom + ".tar.gz")
                f.write_bytes(octets)
                for cmd in ("voir", "restaurer"):
                    r = self.lancer(env, cmd, "--pour-le-cloud", str(f))
                    self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
                    self.assertIn(raison, r.stderr)
                    self.assertNotIn("Traceback", r.stderr)
                self.assertFalse((home / ".face").exists())

    def rien_d_ecrit(self, home, avant):
        self.assertEqual((home / ".config/nc/reglages.conf").read_text(), avant)
        self.assertFalse((home / ".face").exists())
        self.assertFalse((home / ".config/noctalia/palettes").exists())
        self.assertFalse((home / ".config/nc/raccourcis.conf").exists())

    def test_nom_en_double_refuse_toute_l_archive(self):
        """voir ne montrerait que le premier reglages.conf, la reprise les prendrait tous : refusée en entier."""
        home, env = self.maison("doubles")
        self.reglages(home, LANGUE="fr")
        avant = (home / ".config/nc/reglages.conf").read_text()
        r1, r2 = (".config/nc/reglages.conf", b"DOCK_TAILLE=40\n", 0o600), (".config/nc/reglages.conf", b"LANGUE=en\n", 0o600)
        f1, p1 = (".face", self.PNG, 0o644), (".config/noctalia/palettes/a.json", b"{}", 0o644)
        for nom, membres in (("reglages", [r1, r2]), ("face", [r1, f1, f1]), ("palette", [r1, p1, p1])):
            with self.subTest(nom):
                f = self.archive_cloud(membres, nom=nom + ".tar.gz")
                for cmd in ("voir", "restaurer"):
                    r = self.lancer(env, cmd, "--pour-le-cloud", str(f))
                    self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
                    self.assertIn("deux fois dans l'archive", r.stderr)
                self.rien_d_ecrit(home, avant)
        # Le contrôle : chaque membre une fois, la reprise passe
        r = self.lancer(env, "restaurer", "--pour-le-cloud", str(self.archive_cloud([r1, f1, p1])))
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_entetes_lus_pareil_par_la_boucle_et_tarfile(self):
        home, env = self.maison("desaccord")
        self.reglages(home, LANGUE="fr")
        avant = (home / ".config/nc/reglages.conf").read_text()

        def entete(nom, type_=b"0", size=0, champ=None, prefix=b"", magie=None, somme=True):
            t = tarfile.TarInfo(nom)
            t.size = size
            b = bytearray(t.tobuf(tarfile.USTAR_FORMAT))
            b[156:157] = type_
            b[345:345 + len(prefix)] = prefix
            if champ is not None:
                b[124:136] = champ
            if magie is not None:
                b[257:265] = magie
            b[148:156] = b"        "
            b[148:156] = b"%06o\0 " % (sum(b) + (0 if somme else 1))
            return bytes(b)

        def bloc(d):
            return d + bytes((-len(d)) % 512)

        def pax(type_, enregs):
            txt = b""
            for k, v in enregs:
                rec = f" {k}={v}\n".encode()
                n = len(rec) + 1
                while len(str(n)) + len(rec) != n:
                    n += 1
                txt += str(n).encode() + rec
            return entete("././@PaxHeader", type_, len(txt)) + bloc(txt)
        fin = bytes(1024)
        regl = entete(".config/nc/reglages.conf", size=15) + bloc(b"DOCK_TAILLE=33\n")
        cas = {
            "taille qui commence par NUL": (entete(".config/noctalia/palettes/a.json", champ=b"\0" + b"0000001000" + b"\0")
                                            + regl + fin, "en-tête abîmé"),
            "PAX size=0": (pax(b"x", [("size", "0")]) + entete(".config/noctalia/palettes/b.json", size=512) + bytes(512) + fin,
                           "type refusé"),
            "PAX path": (pax(b"x", [("path", ".config/nc/reglages.conf")]) + entete(".config/noctalia/palettes/c.json", size=15)
                         + bloc(b"DOCK_TAILLE=33\n") + fin, "type refusé"),
            "deux PAX de suite": (pax(b"x", [("comment", "a")]) * 2 + regl + fin, "type refusé"),
            "999 PAX": (pax(b"x", [("comment", "x")]) * 999 + regl + fin, "type refusé"),
            "PAX global": (pax(b"g", [("comment", "x")]) + regl + fin, "type refusé"),
            "prefix": (entete("reglages.conf", size=15, prefix=b".config/nc") + bloc(b"DOCK_TAILLE=33\n") + fin, "pas USTAR simple"),
            "sans magie": (entete(".config/nc/reglages.conf", size=15, magie=bytes(8)) + bloc(b"DOCK_TAILLE=33\n") + fin,
                           "pas USTAR simple"),
            # tarfile s'arrête sur un en-tête à la somme fausse, la boucle non : lus de deux façons
            "somme fausse": (entete(".config/noctalia/palettes/d.json", size=2) + bloc(b"{}")
                             + entete(".config/nc/reglages.conf", size=15, somme=False) + bloc(b"DOCK_TAILLE=33\n") + fin,
                             "lus de deux façons"),
        }
        for nom, (brut, raison) in cas.items():
            with self.subTest(nom):
                f = self.r / "desaccord.tar.gz"
                f.write_bytes(gzip.compress(brut))
                for cmd in ("voir", "restaurer"):
                    r = self.lancer(env, cmd, "--pour-le-cloud", str(f))
                    self.assertEqual(r.returncode, 1, nom + " " + cmd + " : " + r.stdout + r.stderr)
                    self.assertIn(raison, r.stderr)
                    self.assertNotIn("Traceback", r.stderr)
                self.rien_d_ecrit(home, avant)
        # Le contrôle : le même reglages.conf seul, en USTAR simple, passe
        f.write_bytes(gzip.compress(regl + fin))
        self.assertEqual(self.lancer(env, "restaurer", "--pour-le-cloud", str(f)).returncode, 0)
        self.assertIn("DOCK_TAILLE=33", (home / ".config/nc/reglages.conf").read_text())

    def test_toute_erreur_de_tarfile_est_un_refus_propre(self):
        import contextlib
        mod = self.module()
        mod.POUR_LE_CLOUD = True
        f = self.archive_cloud([(".config/nc/reglages.conf", b"LANGUE=en\n", 0o600)])

        def plante(*a, **k):
            raise RecursionError("maximum recursion depth exceeded")
        for ou in ("ouvrir", "lire"):
            with self.subTest(ou):
                err = io.StringIO()
                vrai_open, vrai_lire = mod.tarfile.open, mod.lire_membres_de
                if ou == "ouvrir":
                    mod.tarfile.open = plante
                else:
                    mod.lire_membres_de = plante
                try:
                    with contextlib.redirect_stderr(err), self.assertRaises(SystemExit) as fin:
                        with mod.ouvrir(str(f)) as t:
                            mod.lire_membres(t, None, False)
                finally:
                    mod.tarfile.open, mod.lire_membres_de = vrai_open, vrai_lire
                self.assertNotEqual(fin.exception.code, 0)
                self.assertIn("RecursionError", str(fin.exception.code) + err.getvalue())

    def test_palette_accentuee_aller_retour_sans_pax(self):
        home, env = self.maison("accent")
        self.reglages(home, LANGUE="fr")
        (home / ".config/noctalia/palettes").mkdir(parents=True)
        (home / ".config/noctalia/palettes/Été.json").write_text('{"a": 1}')
        (home / ".config/noctalia/palettes" / ("p" * 80 + ".json")).write_text("{}")      # plus de 100 octets en tout : écartée
        sortie = self.r / "accent.tar.gz"
        r = self.lancer(env, "creer", "--pour-le-cloud", "--sortie", str(sortie))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("1 palette(s) écartée(s)", r.stdout)
        with tarfile.open(sortie) as t:
            self.assertEqual(t.getnames(), [".config/nc/reglages.conf", ".config/noctalia/palettes/Été.json"])
            self.assertFalse(any(m.pax_headers for m in t.getmembers()))
        self.assertNotIn(b"PaxHeader", gzip.decompress(sortie.read_bytes()))
        autre, env2 = self.maison("accent-2")
        r = self.lancer(env2, "restaurer", "--pour-le-cloud", str(sortie))
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual((autre / ".config/noctalia/palettes/Été.json").read_text(), '{"a": 1}')

    def test_tri_des_reglages_avant_toute_ecriture(self):
        """nc-reglages manque ou plante : rien n'est écrit (ni photo, ni palette, ni raccourcis)."""
        home, env = self.maison("tri")
        self.reglages(home, LANGUE="fr")
        avant = (home / ".config/nc/reglages.conf").read_text()
        f = self.archive_cloud([(".face", self.PNG, 0o644), (".config/noctalia/palettes/a.json", b"{}", 0o644),
                                (".config/nc/raccourcis.conf", b"ajout\tSUPER + B\tappli\tfirefox\tNavigateur\n", 0o600),
                                (".config/nc/reglages.conf", b"LANGUE=en\n", 0o600)])
        bin_ = self.r / "bin-plante"
        bin_.mkdir()
        (bin_ / "nc-sauvegarde").write_bytes(NC_SAUVEGARDE.read_bytes())
        (bin_ / "nc-sauvegarde").chmod(0o755)
        for corps in (None, "#!/bin/sh\nexit 1\n"):
            with self.subTest(nc_reglages="absent" if corps is None else "plante"):
                if corps:
                    (bin_ / "nc-reglages").write_text(corps)
                    (bin_ / "nc-reglages").chmod(0o755)
                r = subprocess.run([str(bin_ / "nc-sauvegarde"), "restaurer", "--pour-le-cloud", str(f)], env=env, cwd=env["HOME"],
                                   capture_output=True, text=True, timeout=60)
                self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
                self.assertIn("rien n'est envoyé ni remis", r.stderr)
                self.rien_d_ecrit(home, avant)

    def test_fusion_ne_coupe_jamais_un_reglages_local_trop_gros(self):
        """Le fichier grossit entre le contrôle d'avant et l'écriture : la fusion refuse, elle ne coupe pas."""
        home, env = self.maison("course")
        (home / ".config/nc").mkdir(parents=True, exist_ok=True)
        (home / ".config/nc/reglages.conf").write_text("# " + "x" * (1024 ** 2) + "\n")
        mod = self.module()
        mod.HOME = str(home)
        with self.assertRaises(mod.Refus):
            mod.fusion_cloud(b"LANGUE=en\n")

    def test_reglages_local_trop_gros_jamais_coupe(self):
        home, env = self.maison("gros")
        (home / ".config/nc").mkdir(parents=True, exist_ok=True)
        gros = "LANGUE=fr\n" + "# " + "x" * (1024 ** 2) + "\n"
        (home / ".config/nc/reglages.conf").write_text(gros)
        f = self.archive_cloud([(".config/nc/reglages.conf", b"LANGUE=en\n", 0o600), (".face", self.PNG, 0o644)])
        r = self.lancer(env, "restaurer", "--pour-le-cloud", str(f))
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("jamais coupé", r.stderr)
        self.rien_d_ecrit(home, gros)

    def test_usage_strict(self):
        home, env = self.preparer_home()
        for args in (("creer", "--pour-le-cloud"), ("creer", "--pour-le-cloud", "--sortie", "x", "--avec-code"),
                     ("creer", "--pour-le-cloud", "--sortie", "x", "--fonds"), ("restaurer", "--pour-le-cloud", "--avec-code", "x")):
            with self.subTest(args=args):
                r = self.lancer(env, *args)
                self.assertNotEqual(r.returncode, 0)
                self.assertFalse((home / "x").exists())

    def test_bornes_d_une_archive_venue_du_cloud(self):
        home, env = self.maison("borne")
        # Trop de membres pour le cloud (mais pas pour une sauvegarde ordinaire)
        with tarfile.open(self.r / "membres.tar.gz", "w:gz") as t:
            for i in range(501):
                t.addfile(tarfile.TarInfo(f".config/noctalia/palettes/{i}.json"))
        for cmd in ("voir", "restaurer"):
            r = self.lancer(env, cmd, "--pour-le-cloud", str(self.r / "membres.tar.gz"))
            self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
            self.assertIn("trop d'éléments", r.stderr)
        self.assertEqual(self.lancer(env, "voir", str(self.r / "membres.tar.gz")).returncode, 0)
        # Tailles annoncées cumulées au-delà de 64 Mio : arrêt AVANT de lire leurs données
        mod = self.module()
        mod.POUR_LE_CLOUD = True
        gros = [tarfile.TarInfo(".face") for _ in range(2)]
        for g in gros:
            g.size = 40 * 1024 ** 2
        with self.assertRaises(SystemExit) as e:
            mod.lire_membres(iter(gros), None, False)
        self.assertRegex(str(e.exception), "annonce plus de|announces over")
        # Fichier de plus de 32 Mio : refusé sans être lu
        f = self.r / "gros.tar.gz"
        with open(f, "wb") as o:
            o.truncate(33 * 1024 ** 2)
        r = self.lancer(env, "voir", "--pour-le-cloud", str(f))
        self.assertEqual(r.returncode, 1)
        self.assertIn("refusée sans être lue", r.stderr)
        self.assertNotIn("Traceback", r.stderr)


if __name__ == "__main__":
    unittest.main()
