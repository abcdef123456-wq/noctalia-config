"""Lot « Install-Réglages » (install.sh et nc-reglages) : Noctalia relancée quoi qu'il arrive, réglages de l'île gardés,
questions à réponse « non » ou « sensible » par défaut, résumé des modifications silencieuses, variables perso de uwsm,
écritures atomiques, sed sûr, repli sans tomllib. Les morceaux d'install.sh sont extraits et lancés avec de faux outils ;
aucun vrai HOME, aucun vrai systemctl ni sudo (tout est dans un dossier temporaire)."""
import importlib.machinery
import importlib.util
import os
from pathlib import Path
import re
import stat
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import warnings

REPO = Path(__file__).resolve().parents[1]
SOURCE = (REPO / "install.sh").read_text()
NC_REGLAGES = REPO / "home/.local/bin/nc-reglages"
PREAMBULE = r'''
set -euo pipefail
OUI="${OUI:-0}"; NC_LANGUE=fr
t() { printf '%s' "$1"; }
info() { printf '   %s\n' "$*"; }
warn() { printf '   ! %s\n' "$*"; }
ok() { printf '   ok %s\n' "$*"; }
'''


def entre(debut, fin):
    return SOURCE[SOURCE.index(debut):SOURCE.index(fin)]


def faux_outil(dossier, nom, corps):
    p = Path(dossier) / nom
    p.write_text("#!/usr/bin/env bash\n" + corps + "\n")
    p.chmod(p.stat().st_mode | stat.S_IEXEC)


class Isole(unittest.TestCase):
    """Un faux HOME et des faux outils en tête du PATH qui notent leurs arguments dans journal.txt."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(prefix="nc-lot-reglages-")
        self.addCleanup(self._tmp.cleanup)
        self.r = Path(self._tmp.name)
        self.home = self.r / "home/user"
        self.home.mkdir(parents=True)
        self.bin = self.r / "bin"
        self.bin.mkdir()
        self.journal = self.r / "journal.txt"
        for nom in ("systemctl", "sudo", "pacman", "gsettings"):
            faux_outil(self.bin, nom, f'echo "{nom} $*" >> "{self.journal}"')
        self.env = {
            "HOME": str(self.home), "XDG_CONFIG_HOME": str(self.home / ".config"), "XDG_DATA_HOME": str(self.home / ".local/share"),
            "XDG_STATE_HOME": str(self.home / ".local/state"), "XDG_CACHE_HOME": str(self.home / ".cache"),
            "XDG_RUNTIME_DIR": str(self.r / "run"), "TMPDIR": str(self.r), "PATH": f"{self.bin}:/usr/bin:/bin", "NC_LANGUE": "fr",
        }
        (self.r / "run").mkdir()

    def bash(self, script, **extra):
        return subprocess.run(["bash", "-c", script], capture_output=True, text=True, stdin=subprocess.DEVNULL,
                              start_new_session=True, env=dict(self.env, **extra), timeout=30)

    def log(self):
        return self.journal.read_text() if self.journal.exists() else ""


class NoctaliaRelancee(Isole):
    BLOC = entre("NOCT_ARRETEE=0\n", "# ── 1. Paquets")
    BLOC = BLOC[:BLOC.index("trap sortie_install EXIT\n") + len("trap sortie_install EXIT\n")]

    def lance(self, fin):
        return self.bash(PREAMBULE + 'BK="$HOME/bk"; mkdir -p "$BK"; tmp="$(mktemp)"\n' + self.BLOC + fin)

    def test_relancee_apres_une_erreur(self):
        r = self.lance("NOCT_ARRETEE=1\nfalse\necho jamais")
        self.assertEqual(r.returncode, 1)
        self.assertNotIn("jamais", r.stdout)
        self.assertIn("systemctl --user start noctalia.service", self.log())

    def test_relancee_apres_sigterm(self):
        r = self.lance("NOCT_ARRETEE=1\nkill -TERM $$\nsleep 5")
        self.assertEqual(r.returncode, 143)
        self.assertIn("systemctl --user start noctalia.service", self.log())

    def test_relancee_apres_ctrl_c(self):
        r = self.lance("NOCT_ARRETEE=1\nkill -INT $$\nsleep 5")
        self.assertEqual(r.returncode, 130)
        self.assertIn("systemctl --user start noctalia.service", self.log())

    def test_pas_relancee_si_elle_na_pas_ete_arretee(self):
        r = self.lance("exit 0")
        self.assertEqual(r.returncode, 0)
        self.assertNotIn("noctalia", self.log())

    def test_relancee_une_seule_fois(self):
        self.lance("NOCT_ARRETEE=1\nrelancer_noctalia\nrelancer_noctalia\nexit 0")
        self.assertEqual(self.log().count("start noctalia.service"), 1)

    def test_arretee_seulement_autour_de_la_copie(self):
        arret = SOURCE.index("systemctl --user stop noctalia.service   # Noctalia réécrit")
        relance = SOURCE.index("relancer_noctalia   # la copie est finie")
        copie = SOURCE.index("done < <(find \"$root\" -type f -print0)")
        fin_install = SOURCE.index("noter_version\nsay")
        self.assertLess(arret, copie)
        self.assertLess(copie, relance)
        self.assertLess(relance, fin_install - 5000)       # bien avant la fin du script, pas pendant tout l'install


class Questions(Isole):
    DEBUT = entre("sans_tty() {", "choisir() {")

    def ask(self, appel, oui="0"):
        return self.bash(PREAMBULE + self.DEBUT + appel, OUI=oui)

    def reponse_par_defaut(self, question):
        m = re.search(r'ask "\$\(t "' + re.escape(question) + r'.*?"\)" ([on])( sensible)?', SOURCE)
        self.assertTrue(m, question)
        return m.group(1), m.group(2) or ""

    def test_ecrasement_de_fichiers_perso_non_par_defaut(self):
        for q in ("Remplacer ton ~/$f", "Remplacer ta config ~/.config/nvim"):
            self.assertEqual(self.reponse_par_defaut(q), ("n", ""), q)
        self.assertEqual(self.ask('ask "Q ?" n').returncode, 1)

    def test_ce_qui_touche_etc_sensible(self):
        for q in ("Activer cette limite de charge", "Installer ces profils énergétiques", "Installer les profils énergétiques",
                  "Bouton d'arrêt", "Régler le pays du Wi-Fi", "Mettre à jour le thème GRUB"):
            self.assertEqual(self.reponse_par_defaut(q)[1], " sensible", q)
        # sans terminal, une étape sensible est refusée sauf avec --oui
        self.assertEqual(self.ask('ask "Q ?" o sensible').returncode, 1)
        self.assertEqual(self.ask('ask "Q ?" o sensible', oui="1").returncode, 0)


class ArchFacultatifs(unittest.TestCase):
    def test_facultatifs_proposes_et_un_refus_ne_casse_rien(self):
        i = SOURCE.index("FACULTATIFS=(")
        bloc = SOURCE[i:SOURCE.index("case \" ${manual[*]} \" in")]
        self.assertIn("missing_opt+=", bloc)
        # une question, et le refus ne fait que le dire (pas de die)
        m = re.search(r'ask "\$\(t "Les installer \?".*?\n(.*?)\n\s*fi\n\s*fi', bloc, re.S)
        self.assertTrue(m)
        self.assertIn("ignorés", bloc)
        self.assertNotIn("die", bloc[bloc.index("Paquets facultatifs ("):])
        # les paquets indispensables restent imposés
        for g in ("uwsm", "hypridle", "kitty", "nautilus", "python", "jq"):
            self.assertNotIn(g, SOURCE[i:i + 400].split("FACULTATIFS=(")[1].split(")")[0].split())


class Silencieux(Isole):
    def test_resume_des_modifications_silencieuses(self):
        bloc = entre("SILENCIEUX=()\n", "# ── 1. Paquets")
        bloc = bloc[:bloc.index("# ── ")] if "# ── " in bloc else bloc
        fin = entre("# Ce qui a été changé sans question", "info \"$(t \"Ferme puis rouvre")
        r = self.bash(PREAMBULE + 'BK="$HOME/bk"; mkdir -p "$BK"\nSILENCIEUX=()\n'
                      + SOURCE[SOURCE.index("noter_silencieux() {"):SOURCE.index("# ── 1. Paquets")].split("\n# Fedora")[0]
                      + 'noter_silencieux "gsettings" "valeurs d\'avant : x"\nnoter_silencieux ".bashrc" "ancienne version : y"\n' + fin)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("Modifications faites sans te demander", r.stdout)
        self.assertIn("gsettings", r.stdout)
        self.assertIn("valeurs d'avant : x", r.stdout)
        resume = (self.home / "bk/silencieux/resume.txt").read_text()
        self.assertIn(".bashrc", resume)
        self.assertIn("ancienne version : y", resume)

    def test_chaque_modification_silencieuse_est_notee_avec_sa_sauvegarde(self):
        for motif in ("gsettings-avant.sh", "backup .config/user-dirs.dirs", "backup .config/gtk-3.0/bookmarks",
                      'noter_silencieux "~/.bashrc', 'mask', "nc-maj-verif.timer", "nc-wifi-sans-veille.conf"):
            self.assertIn(motif, SOURCE, motif)
        for unite in ("$b.service masqué", "$d.service masqué"):
            self.assertIn(unite, SOURCE)
        self.assertIn("noter_silencieux \"services et minuteries systemd", SOURCE)
        self.assertIn("noter_silencieux \"NetworkManager", SOURCE)

    def test_restore_ne_recopie_pas_le_resume(self):
        self.assertIn("-path ./silencieux -prune", SOURCE)


class Utilitaires(Isole):
    HELPERS = SOURCE[SOURCE.index("ecrire_atomique() {"):SOURCE.index("# Modifications faites sans question")]

    def test_ecriture_atomique_suit_un_lien_et_garde_le_mode(self):
        reel = self.home / "depot/bashrc"
        reel.parent.mkdir()
        reel.write_text("ancien\n")
        reel.chmod(0o640)
        (self.home / ".bashrc").symlink_to(reel)
        r = self.bash(self.HELPERS + f'printf "nouveau\\n" | ecrire_atomique "{self.home}/.bashrc"')
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue((self.home / ".bashrc").is_symlink())
        self.assertEqual(reel.read_text(), "nouveau\n")
        self.assertEqual(stat.S_IMODE(reel.stat().st_mode), 0o640)
        self.assertEqual([f.name for f in reel.parent.iterdir()], ["bashrc"])      # aucun temporaire oublié

    def test_ecriture_atomique_ne_touche_pas_au_fichier_si_la_source_echoue(self):
        f = self.home / "f"
        f.write_text("garde\n")
        r = self.bash(self.HELPERS + f'set -o pipefail; {{ echo debut; exit 3; }} | ecrire_atomique "{f}" || true')
        self.assertEqual(f.read_text() in ("garde\n", "debut\n"), True)
        self.assertEqual([x.name for x in self.home.iterdir() if ".nc-" in x.name], [])

    def test_esc_sed(self):
        valeur = r"/home/user/a|b&c\d"
        r = self.bash(self.HELPERS + f'printf "@X@\\n" | sed -e "s|@X@|$(esc_sed \'{valeur}\')|g"')
        self.assertEqual(r.stdout.strip(), valeur)

    def test_sed_des_modeles_utilise_esc_sed(self):
        self.assertIn('sed "${SED_ARGS[@]}" "$src" > "$tmp"', SOURCE)
        self.assertNotIn('sed -e "s|@HOME@|$HOME|g"', SOURCE)

    def test_dpkg_query_et_apt_update_une_fois(self):
        self.assertNotIn("dpkg -l", SOURCE)
        self.assertIn("dpkg-query -W", SOURCE)
        self.assertEqual(len(re.findall(r"sudo apt-get \$APT_OPT update", SOURCE)), 1)      # dans apt_maj seulement
        bloc = entre("APT_A_JOUR=0\napt_maj()", "bpo_on() {")
        faux_outil(self.bin, "apt-get", f'echo "apt-get $*" >> "{self.journal}"')
        r = self.bash(PREAMBULE + 'APT_OPT=""\n' + bloc + "apt_maj; apt_maj; apt_maj\nAPT_A_JOUR=0; apt_maj")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.log().count("apt-get update"), 2)      # 1 + après un ajout de source


class UwsmPerso(Isole):
    def test_variables_perso_reprises_et_jamais_ecrasees(self):
        bloc = entre('# Variables d\'environnement perso de uwsm', "# Ancien cockpit QML orphelin")
        depot = self.r / "depot"
        (depot / "home/.config/uwsm").mkdir(parents=True)
        (depot / "home/.config/uwsm/env").write_text("export QT_QPA_PLATFORMTHEME=qt6ct\n")
        uw = self.home / ".config/uwsm"
        uw.mkdir(parents=True)
        (uw / "env").write_text("export QT_QPA_PLATFORMTHEME=qt6ct\nexport MA_VARIABLE=1\nexport PATH=/x:$PATH\n# commentaire\n")
        script = (PREAMBULE + self.helpers() + f'REPO="{depot}"; MODE=full; BK="$HOME/bk"; mkdir -p "$BK"; SILENCIEUX=()\n' + bloc
                  + 'printf "%s\\n" "${SILENCIEUX[@]}"')
        r = self.bash(script)
        self.assertEqual(r.returncode, 0, r.stderr)
        perso = (uw / "env.d/perso").read_text()
        self.assertIn("export MA_VARIABLE=1", perso)
        self.assertNotIn("PATH", perso)
        self.assertNotIn("QT_QPA", perso)
        self.assertEqual(stat.S_IMODE((uw / "env.d/perso").stat().st_mode), 0o600)
        self.assertIn("env.d/perso", r.stdout)
        # deuxième passage : le fichier perso n'est plus touché
        (uw / "env.d/perso").write_text("export A_MOI=2\n")
        self.bash(script)
        self.assertEqual((uw / "env.d/perso").read_text(), "export A_MOI=2\n")

    def helpers(self):
        return SOURCE[SOURCE.index("ecrire_atomique() {"):SOURCE.index("# Modifications faites sans question")] + \
            SOURCE[SOURCE.index("SILENCIEUX=()\n"):SOURCE.index("# ── 1. Paquets")].split("\n# Fedora")[0]

    def test_uwsm_env_du_depot_lit_le_fichier_perso(self):
        env = (REPO / "home/.config/uwsm/env").read_text()
        self.assertIn('. "$HOME/.config/uwsm/env.d/perso"', env)
        # lu par uwsm (sh POSIX) : il doit rester valide même sans le fichier perso
        r = subprocess.run(["sh", "-c", f'HOME="{self.home}"; . "{REPO}/home/.config/uwsm/env"; echo fin'], capture_output=True,
                           text=True, env=self.env, timeout=10)
        self.assertEqual(r.stdout.strip(), "fin")


def charger_reglages(home, **extra):
    env = dict(HOME=str(home), NC_LANGUE="fr", XDG_CONFIG_HOME=str(home / ".config"), XDG_DATA_HOME=str(home / ".local/share"),
               XDG_STATE_HOME=str(home / ".local/state"), XDG_CACHE_HOME=str(home / ".cache"), **extra)
    with patch.dict(os.environ, env), warnings.catch_warnings():
        warnings.simplefilter("ignore", ResourceWarning)
        chargeur = importlib.machinery.SourceFileLoader("nc_reglages_lot", str(NC_REGLAGES))
        mod = importlib.util.module_from_spec(importlib.util.spec_from_loader(chargeur.name, chargeur))
        chargeur.exec_module(mod)
    return mod


class GardesReglages(unittest.TestCase):
    ILE = ("SPOTLIGHT_ENTREE", "SPOTLIGHT_FICHIERS", "SPOTLIGHT_PAQUETS", "SPOTLIGHT_RESULTATS", "SPOTLIGHT_AIDE", "SPOTLIGHT_EMOJI", "SPOTLIGHT_MOTEUR",
           "SPOTLIGHT_CALCULS", "SPOTLIGHT_FENETRES", "VUE_BUREAUX", "VUE_RECUL", "VUE_VOISINS", "VUE_DUREE", "GOOGLE_INTEGRATION",
           "GOOGLE_CALENDRIER", "NPD_NUIT", "NPD_DEBUT", "NPD_FIN", "POMODORO_CONCENTRATION", "METEO_VILLE", "ECO_IMAGES")

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(prefix="nc-gardes-")
        self.addCleanup(self._tmp.cleanup)
        self.home = Path(self._tmp.name) / "home/user"
        self.home.mkdir(parents=True)

    def test_cles_de_l_ile_gardees(self):
        nc = charger_reglages(self.home)
        for cle in self.ILE:
            self.assertEqual(nc.MATERIEL.get(cle), "ile", cle)
        # sans l'île Quickshell elles sont cachées de la liste
        visibles = {r.cle for r in nc.VISIBLES}
        if not nc._DISPO["ile"]:
            self.assertFalse(visibles & set(self.ILE))

    def test_toute_cle_lue_seulement_par_l_ile_est_gardee(self):
        """Une clé proposée par nc-reglages et lue par les QML de l'île, mais par rien d'autre dans home/, doit être gardée."""
        nc = charger_reglages(self.home)
        qml = set()
        for f in (REPO / "home/.config/quickshell/nc-ile").rglob("*.qml"):
            qml |= set(re.findall(r'"([A-Z][A-Z0-9_]{3,})"', f.read_text()))
        ailleurs = ""
        for f in (REPO / "home").rglob("*"):
            if f.is_file() and "nc-ile" not in f.parts and f.name != "nc-reglages" and f.stat().st_size < 3_000_000:
                try:
                    ailleurs += f.read_text(errors="ignore")
                except OSError:
                    pass
        manquantes = [c for c in sorted(qml & {r.cle for r in nc.REGLAGES})
                      if c not in nc.MATERIEL and not re.search(r"\b" + c + r"\b", ailleurs)]
        self.assertEqual(manquantes, [])

    def test_gardes_firefox_terminal_nvim(self):
        nc = charger_reglages(self.home)
        for r in nc.REGLAGES:
            for pref, garde in (("FIREFOX_", "firefox"), ("TERMINAL_", "kitty"), ("NVIM_", "nvim")):
                if r.cle.startswith(pref):
                    self.assertEqual(nc.MATERIEL.get(r.cle), garde, r.cle)

    def test_sans_firefox_ni_kitty_ni_nvim_ils_sont_caches(self):
        vide = self.home.parent / "pathvide"
        vide.mkdir()
        nc = charger_reglages(self.home, PATH=str(vide))
        for garde in ("firefox", "kitty", "nvim"):
            self.assertFalse(nc._DISPO[garde], garde)
        cles = {r.cle for r in nc.VISIBLES}
        self.assertFalse([c for c in cles if c.startswith(("FIREFOX_", "TERMINAL_", "NVIM_"))])

    def test_avec_les_logiciels_les_reglages_apparaissent(self):
        faux = self.home.parent / "pathplein"
        faux.mkdir()
        for nom in ("firefox", "kitty", "nvim"):
            faux_outil(faux, nom, "exit 0")
        nc = charger_reglages(self.home, PATH=str(faux))
        cles = {r.cle for r in nc.VISIBLES}
        for c in ("FIREFOX_STYLE", "TERMINAL_OPACITE", "NVIM_THEME"):
            self.assertIn(c, cles)


class EcrituresEtToml(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(prefix="nc-atomique-")
        self.addCleanup(self._tmp.cleanup)
        self.home = Path(self._tmp.name) / "home/user"
        self.home.mkdir(parents=True)
        self.nc = charger_reglages(self.home)

    def test_ouvrir_atomique_remplace_d_un_coup(self):
        f = self.home / "a.conf"
        f.write_text("ancien\n")
        f.chmod(0o640)
        with self.nc.ouvrir_atomique(str(f)) as o:
            o.write("nouveau\n")
            self.assertEqual(f.read_text(), "ancien\n")          # pas encore remplacé
        self.assertEqual(f.read_text(), "nouveau\n")
        self.assertEqual(stat.S_IMODE(f.stat().st_mode), 0o640)
        self.assertEqual(sorted(x.name for x in self.home.iterdir()), ["a.conf"])

    def test_ouvrir_atomique_garde_l_ancien_sur_erreur(self):
        f = self.home / "b.conf"
        f.write_text("ancien\n")
        with self.assertRaises(RuntimeError):
            with self.nc.ouvrir_atomique(str(f)) as o:
                o.write("moitié")
                raise RuntimeError("boum")
        self.assertEqual(f.read_text(), "ancien\n")
        self.assertEqual(sorted(x.name for x in self.home.iterdir()), ["b.conf"])

    def test_plus_aucune_ecriture_directe_des_fichiers_generes(self):
        src = NC_REGLAGES.read_text()
        for nom in ("VEILLE_OUT", "VEILLE_UNITE", "KITTY_OUT", "NOCTALIA_OUT", "STYLE_FICHIER", "STYLE_AVANT"):
            self.assertNotIn(f'open({nom}, "w"', src, nom)

    def test_fin_barre_sans_tomllib(self):
        conf = self.home / "config.toml"
        conf.write_text('[bar.default]\nstart = ["a", "b"]\nend = [\n  "tray",  # une note\n  "group:sys",\n  "clock",\n]\n'
                        '[autre]\nend = ["x"]\n')
        self.assertEqual(self.nc.fin_barre(str(conf)), ["tray", "group:sys", "clock"] if self.nc.tomllib is None
                         else self.nc.fin_barre(str(conf)))
        with patch.object(self.nc, "tomllib", None):
            self.assertEqual(self.nc.fin_barre(str(conf)), ["tray", "group:sys", "clock"])
            conf.write_text("[autre]\nend = []\n")
            with self.assertRaises(KeyError):
                self.nc.fin_barre(str(conf))

    def test_repli_tomli_dans_le_source(self):
        src = NC_REGLAGES.read_text()
        self.assertIn("import tomli as tomllib", src)


if __name__ == "__main__":
    unittest.main()
