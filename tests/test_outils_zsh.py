"""Outils modernes du terminal (home/.config/nc/outils.zsh) : zsh -i dans un faux HOME, avec de faux outils.
Chaque bloc n'existe que si l'outil est là ; rien sur stderr sans aucun outil ; TERMINAL_OUTILS=non coupe tout ;
les alias, le pager git et les GIT_CONFIG_* de l'utilisateur sont respectés. Plus les noms de paquets d'install.sh."""
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest

RACINE = Path(__file__).resolve().parents[1]
OUTILS = RACINE / "home/.config/nc/outils.zsh"
LAZYGIT_YML = RACINE / "home/.config/nc/lazygit.yml"
INSTALL = (RACINE / "install.sh").read_text(encoding="utf-8")

FAUX = {
    "fzf": 'if [ "$1" = --zsh ]; then echo "FZF_CHARGE=1"; fi',
    "zoxide": 'if [ "$1" = init ]; then echo "ZOXIDE_CHARGE=1"; fi',
    "eza": "true", "bat": "true", "batcat": "true", "delta": "true", "yazi": "true",
    "fd": "true", "fdfind": "true",
    "lazygit": 'echo "LG=$LG_CONFIG_FILE"',
}


@unittest.skipUnless(shutil.which("zsh") and shutil.which("git"), "zsh et git requis")
class OutilsZsh(unittest.TestCase):
    def setUp(self):
        self.t = tempfile.TemporaryDirectory()
        self.addCleanup(self.t.cleanup)
        self.home = Path(self.t.name) / "home/user"
        (self.home / ".config/nc").mkdir(parents=True)
        shutil.copy(LAZYGIT_YML, self.home / ".config/nc/lazygit.yml")
        self.bin = Path(self.t.name) / "bin"
        self.bin.mkdir()
        # PATH minimal : ni les vrais outils de la machine, ni /usr/local ; git et sed viennent de /usr/bin
        self.dirs_sys = self.sys_dirs()

    def sys_dirs(self):
        d = Path(self.t.name) / "sys"
        d.mkdir()
        for nom in ("git", "sed", "sh", "mktemp", "rm", "cat", "env", "dirname", "head", "ls"):
            p = shutil.which(nom)
            if p:
                (d / nom).symlink_to(p)
        return d

    def outils(self, *noms):
        for n in noms:
            f = self.bin / n
            f.write_text("#!/bin/sh\n" + FAUX[n] + "\n")
            f.chmod(0o755)

    def lancer(self, script, avant="", env=None):
        """Source outils.zsh dans un zsh interactif (après `avant`), puis exécute `script`."""
        (self.home / ".zshrc").write_text(f"{avant}\nsource {OUTILS}\n")
        e = {"HOME": str(self.home), "ZDOTDIR": str(self.home), "PATH": f"{self.bin}:{self.dirs_sys}",
             "LANG": "fr_FR.UTF-8", "TERM": "xterm", "XDG_CONFIG_HOME": str(self.home / ".config"),
             "XDG_CACHE_HOME": str(self.home / ".cache"), "XDG_DATA_HOME": str(self.home / ".local/share"),
             "XDG_STATE_HOME": str(self.home / ".local/state"), "TMPDIR": self.t.name}
        e.update(env or {})
        return subprocess.run([shutil.which("zsh"), "-i", "-c", script], env=e, capture_output=True, text=True, timeout=60)

    def reglage(self, ligne):
        (self.home / ".config/nc/reglages.conf").write_text(ligne + "\n")

    def test_syntaxe(self):
        r = subprocess.run(["zsh", "-n", str(OUTILS)], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_aucun_outil_rien_sur_stderr(self):
        r = self.lancer("alias; print GIT=$GIT_CONFIG_COUNT; print FZF=$FZF_DEFAULT_OPTS")
        self.assertEqual(r.stderr, "")
        self.assertNotIn("eza", r.stdout)
        self.assertIn("GIT=\n", r.stdout)
        self.assertIn("FZF=\n", r.stdout)
        self.assertNotIn("FZF_CHARGE", r.stdout)
        # nc-outils existe quand même et dit ce qui manque
        r = self.lancer("nc-outils")
        self.assertIn("· fzf", r.stdout)
        self.assertEqual(r.stderr, "")

    def test_chaque_bloc_seulement_si_l_outil_est_la(self):
        self.outils("fzf", "zoxide")
        r = self.lancer("alias; print GIT=$GIT_CONFIG_COUNT; print BAT=$BAT_THEME; whence -w lg y; "
                        "print OPTS=$FZF_DEFAULT_OPTS; nc-outils")
        self.assertEqual(r.stderr, "")
        self.assertIn("--color=", r.stdout)           # couleurs ANSI de fzf posées
        self.assertNotIn("alias ls=", r.stdout)       # eza absent : pas d'alias
        self.assertIn("GIT=\n", r.stdout)             # delta absent : pas de GIT_CONFIG
        self.assertIn("BAT=\n", r.stdout)
        self.assertIn("lg: none", r.stdout)
        self.assertIn("✓ fzf", r.stdout)
        self.assertIn("· lazygit", r.stdout)

    def test_fzf_et_zoxide_charges(self):
        self.outils("fzf", "zoxide")
        r = self.lancer("print FZF=${FZF_CHARGE:-non} ZO=${ZOXIDE_CHARGE:-non}")
        self.assertIn("FZF=1 ZO=1", r.stdout)

    def test_tous_les_outils(self):
        self.outils("fzf", "zoxide", "eza", "bat", "delta", "lazygit", "yazi", "fd")
        r = self.lancer("print ls=$aliases[ls]; print ll=$aliases[ll]; print lt=$aliases[lt]; print BAT=$BAT_THEME; "
                        "print N=$GIT_CONFIG_COUNT K0=$GIT_CONFIG_KEY_0 V0=$GIT_CONFIG_VALUE_0; print DC=$FZF_DEFAULT_COMMAND; "
                        "whence -w lg y")
        self.assertEqual(r.stderr, "")
        self.assertRegex(r.stdout, r"ls=eza --group-directories-first --icons=auto")
        self.assertIn("ll=eza", r.stdout)
        self.assertIn("lt=eza", r.stdout)
        self.assertIn("BAT=ansi", r.stdout)
        self.assertIn("N=5 K0=core.pager V0=delta", r.stdout)
        self.assertIn("DC=fd --hidden", r.stdout)
        self.assertIn("lg: function", r.stdout)
        self.assertIn("y: function", r.stdout)

    def test_debian_batcat_et_fdfind(self):
        self.outils("batcat", "fdfind", "fzf")
        r = self.lancer("print bat=$aliases[bat] fd=$aliases[fd] BAT=$BAT_THEME DC=$FZF_DEFAULT_COMMAND MP=$MANPAGER")
        self.assertEqual(r.stderr, "")
        self.assertIn("bat=batcat fd=fdfind BAT=ansi DC=fdfind --hidden", r.stdout)
        self.assertIn("batcat -p -lman", r.stdout)

    def test_manpager_de_l_utilisateur_garde(self):
        self.outils("bat")
        r = self.lancer("print MP=$MANPAGER", env={"MANPAGER": "less"})
        self.assertIn("MP=less", r.stdout)

    def test_terminal_outils_non_coupe_tout(self):
        self.outils("fzf", "zoxide", "eza", "bat", "delta", "lazygit", "yazi", "fd")
        self.reglage('TERMINAL_OUTILS="non"')
        r = self.lancer("alias; print N=$GIT_CONFIG_COUNT BAT=$BAT_THEME FZF=${FZF_CHARGE:-non}; whence -w lg y nc-outils")
        self.assertEqual(r.stderr, "")
        self.assertNotIn("eza", r.stdout)
        self.assertIn("N= BAT= FZF=non", r.stdout)
        self.assertIn("lg: none", r.stdout)
        self.assertIn("nc-outils: none", r.stdout)

    def test_icones_coupees(self):
        self.outils("eza")
        self.reglage("TERMINAL_LS_ICONES=non")
        r = self.lancer("print ls=$aliases[ls]")
        self.assertIn("--icons=never", r.stdout)

    def test_alias_ls_de_l_utilisateur_respecte(self):
        self.outils("eza")
        r = self.lancer("print ls=$aliases[ls] ll=$aliases[ll]", avant="alias ls='ls -1 --color=never'\nalias ll='ls -l'")
        self.assertIn("ls=ls -1 --color=never ll=ls -l", r.stdout)

    def test_alias_par_defaut_d_oh_my_zsh_remplace(self):
        self.outils("eza")
        r = self.lancer("print ls=$aliases[ls]", avant="alias ls='ls --color=tty'\nalias ll='ls -lh'")
        self.assertIn("ls=eza", r.stdout)

    def test_fonction_ls_de_l_utilisateur_respectee(self):
        self.outils("eza")
        r = self.lancer("print ls=${aliases[ls]:-aucun}", avant="ls() { command ls -1 \"$@\" }")
        self.assertIn("ls=aucun", r.stdout)

    def test_pager_git_de_l_utilisateur_respecte(self):
        self.outils("delta")
        (self.home / ".gitconfig").write_text("[core]\n\tpager = less -R\n")
        r = self.lancer("print N=$GIT_CONFIG_COUNT")
        self.assertEqual(r.stderr, "")
        self.assertIn("N=\n", r.stdout)

    def test_git_config_existants_gardes(self):
        self.outils("delta")
        r = self.lancer("print N=$GIT_CONFIG_COUNT K0=$GIT_CONFIG_KEY_0 V0=$GIT_CONFIG_VALUE_0 K1=$GIT_CONFIG_KEY_1",
                        env={"GIT_CONFIG_COUNT": "1", "GIT_CONFIG_KEY_0": "user.name", "GIT_CONFIG_VALUE_0": "Zoe"})
        self.assertIn("N=6 K0=user.name V0=Zoe K1=core.pager", r.stdout)

    def test_git_config_core_pager_deja_pose_non_reecrit(self):
        self.outils("delta")
        r = self.lancer("print N=$GIT_CONFIG_COUNT",
                        env={"GIT_CONFIG_COUNT": "1", "GIT_CONFIG_KEY_0": "core.pager", "GIT_CONFIG_VALUE_0": "less"})
        self.assertIn("N=1", r.stdout)

    def test_delta_effectif_dans_git(self):
        self.outils("delta")
        r = self.lancer("git config --get core.pager; git config --get delta.syntax-theme")
        self.assertEqual(r.stdout.split(), ["delta", "ansi"])

    def test_lg_notre_config_puis_celle_de_l_utilisateur(self):
        self.outils("lazygit")
        r = self.lancer("lg")
        self.assertEqual(r.stdout.strip(), f"LG={self.home}/.config/nc/lazygit.yml")
        perso = self.home / ".config/lazygit/config.yml"
        perso.parent.mkdir(parents=True)
        perso.write_text("gui:\n  border: single\n")
        r = self.lancer("lg")
        # lazygit lit dans l'ordre et la dernière gagne : celle de l'utilisateur doit être la dernière
        self.assertEqual(r.stdout.strip(), f"LG={self.home}/.config/nc/lazygit.yml,{perso}")

    def test_lg_config_de_l_utilisateur_par_variable_gardee(self):
        self.outils("lazygit")
        r = self.lancer("lg", env={"LG_CONFIG_FILE": "/home/user/a.yml"})
        self.assertEqual(r.stdout.strip(), "LG=/home/user/a.yml")

    def test_lazygit_yml(self):
        t = LAZYGIT_YML.read_text(encoding="utf-8")
        self.assertIn('nerdFontsVersion: "3"', t)
        self.assertIn("nc-ia commit", t)
        self.assertIn("key: 'A'", t)
        self.assertIn("output: terminal", t)
        self.assertIn("git commit --edit --file", t)
        try:
            import yaml
        except ImportError:
            return
        d = yaml.safe_load(t)
        self.assertEqual(d["customCommands"][0]["context"], "files")
        # le script de la commande est du sh valide
        r = subprocess.run(["sh", "-n"], input=d["customCommands"][0]["command"], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_zshrc_modele(self):
        z = (RACINE / "home/.zshrc").read_text(encoding="utf-8")
        self.assertIn("outils.zsh", z)
        self.assertLess(z.index("ia.zsh"), z.index("outils.zsh"))
        self.assertLess(z.index("fzf-tab"), z.index("zsh-autosuggestions"))
        self.assertIn("-d ${ZSH_CUSTOM:-$ZSH/custom}/plugins/fzf-tab", z, "fzf-tab seulement si son dossier existe")

    def test_ligne_ajoutee_par_install_sh(self):
        # même commande sed que la migration d'install.sh : une seule ligne, juste après celle d'ia.zsh
        self.assertIn("outils.zsh", INSTALL)
        z = self.home / "zshrc"
        z.write_text("a\n[[ -r ~/.config/nc/ia.zsh ]] && source ~/.config/nc/ia.zsh\nz\n")
        script = ("/source.*\\.config\\/nc\\/ia\\.zsh/{a\\\n"
                  "[[ -r ~/.config/nc/outils.zsh ]] \\&\\& source ~/.config/nc/outils.zsh\n:b;n;bb}")
        subprocess.run(["sed", "-i", script, str(z)], check=True)
        self.assertEqual(z.read_text().splitlines()[2], "[[ -r ~/.config/nc/outils.zsh ]] && source ~/.config/nc/outils.zsh")
        self.assertEqual(len(z.read_text().splitlines()), 4)


class PaquetsInstall(unittest.TestCase):
    def ligne(self, famille):
        m = [l for l in INSTALL.splitlines() if re.match(rf"\s*{famille}\)\s+pkg_try\b.*\bfzf\b", l)]
        self.assertEqual(len(m), 1, f"une ligne pkg_try fzf pour {famille}")
        return m[0].split()

    def test_noms_par_distribution(self):
        comuns = {"fzf", "zoxide", "eza", "bat", "git-delta"}
        for fam in ("arch", "debian", "fedora", "suse"):
            self.assertTrue(comuns <= set(self.ligne(fam)), fam)
        self.assertIn("yazi", self.ligne("arch"))
        self.assertIn("yazi", self.ligne("suse"))
        self.assertNotIn("yazi", self.ligne("debian"), "pas de yazi dans Debian 13")
        self.assertNotIn("yazi", self.ligne("fedora"))
        self.assertNotIn("lazygit", self.ligne("fedora"), "pas de lazygit dans Fedora")
        for fam in ("arch", "debian", "suse"):
            self.assertIn("lazygit", self.ligne(fam))
        # fd : fd-find sur Debian et Fedora, fd ailleurs
        self.assertIn("fd-find", self.ligne("debian"))
        self.assertIn("fd-find", self.ligne("fedora"))
        self.assertIn("fd", self.ligne("arch"))
        self.assertIn("fd", self.ligne("suse"))

    def test_fzf_tab_clone_comme_les_autres_plugins(self):
        self.assertIn('["$ZC/plugins/fzf-tab"]=https://github.com/Aloxaf/fzf-tab.git', INSTALL)
        self.assertIn('"$ZC/plugins/fzf-tab"; do', INSTALL)


if __name__ == "__main__":
    unittest.main()
