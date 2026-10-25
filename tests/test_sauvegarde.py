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


if __name__ == "__main__":
    unittest.main()
