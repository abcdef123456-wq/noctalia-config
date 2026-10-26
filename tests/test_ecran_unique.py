"""Écran allumé ou éteint par un seul chemin (nc-ecran) : au retour d'inactivité, hypridle lance tous ses on-resume dans
la même milliseconde ; deux allumages DPMS simultanés ont planté un PC (amdgpu). Vérifie le hypridle.conf du dépôt et
celui généré par nc-reglages (toutes les variantes) : plus aucun dpms direct, un seul allumage par reprise, joué pour de
vrai avec un faux hyprctl. Puis nc-ecran seul : verrou, rien de refait, rien hors Hyprland. Le faux hyprctl note ses
appels dans son propre dossier temporaire, jamais dans le vrai HOME."""
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest

from tests.test_veille_batterie import SRC, charger, listeners

REPO = Path(__file__).resolve().parents[1]
NC_ECRAN = REPO / "home/.local/bin/nc-ecran"

# Variantes de la config de hypridle : celle du dépôt telle quelle, puis celles de nc-reglages
VARIANTES = [
    None,
    {"VEILLE_VERROU": 5},                                          # défaut
    {"VEILLE_ECRAN_BATTERIE": 20, "VEILLE_BAISSE_BATTERIE": 90},   # batterie, délais choisis
    {"VEILLE_ECRAN_BATTERIE": 0, "VEILLE_BAISSE_BATTERIE": 0},     # batterie comme sur secteur
    {"VEILLE_VERROU": 0},                                          # jamais de verrouillage
    {"VEILLE_VERROU": 0, "VEILLE_ECRAN": 0, "VEILLE_SUSPENSION": 0},  # veille coupée
    {"VEILLE_ECRAN": 1},                                           # écran éteint après 1 min
    {"VEILLE_SECTEUR": 30},                                        # veille sur secteur
    {"VEILLE_VERROU": 2, "VEILLE_ECRAN": 3, "VEILLE_ECRAN_BATTERIE": 120},
]

FAUX_HYPRCTL = """#!/bin/sh
D='{d}'
case "$1" in
  monitors) [ -f "$D/reel" ] && [ -f "$D/dpms" ] && printf '[{{"name": "eDP-1", "dpmsStatus": %s}}]\\n' "$(cat "$D/dpms")"
            exit 0 ;;
  eval) printf '%s\\n' "$2" >> "$D/journal_eval" ;;
  dispatch) printf '%s\\n' "$2" >> "$D/journal"
            sleep 0.3      # un allumage prend du temps : les appels simultanés se chevaucheraient
            case "$2" in *'"on"'*) echo true > "$D/dpms" ;; *'"off"'*) echo false > "$D/dpms" ;; esac ;;
esac
exit 0
"""


class Banc:
    """HOME, XDG_RUNTIME_DIR et faux hyprctl temporaires ; le vrai nc-ecran dans ~/.local/bin."""

    def __init__(self, reel=False):
        self._tmp = tempfile.TemporaryDirectory(prefix="nc-ecran-")
        r = Path(self._tmp.name)
        self.r, self.faux, self.run = r, r / "faux", r / "run"
        self.run.mkdir(mode=0o700)
        self.faux.mkdir()
        bin_ = r / "home/.local/bin"
        bin_.mkdir(parents=True)
        shutil.copy2(NC_ECRAN, bin_ / "nc-ecran")
        shutil.copy2(NC_ECRAN.with_name("nc-gpu-regle"), bin_ / "nc-gpu-regle")   # nc_sur_batterie, sourcée par hypridle
        for nom in ("nc-brightness",):
            (bin_ / nom).write_text("#!/bin/sh\nexit 0\n")
            (bin_ / nom).chmod(0o755)
        (self.faux / "hyprctl").write_text(FAUX_HYPRCTL.format(d=self.faux))
        (self.faux / "hyprctl").chmod(0o755)
        if reel:
            (self.faux / "reel").write_text("")      # le faux hyprctl répond l'état DPMS
            (self.faux / "dpms").write_text("true\n")
        self.env = dict(os.environ, HOME=str(r / "home"), XDG_RUNTIME_DIR=str(self.run),
                        PATH=f"{self.faux}:/usr/bin:/bin", HYPRLAND_INSTANCE_SIGNATURE="test",
                        NC_POWER_SUPPLY=str(r / "power_supply"))
        self.ps = r / "power_supply"

    def fermer(self):
        self._tmp.cleanup()

    def journal(self, vider=True):
        f = self.faux / "journal"
        a = f.read_text().splitlines() if f.exists() else []
        if vider:
            f.unlink(missing_ok=True)
        return a

    def evals(self):
        f = self.faux / "journal_eval"
        a = f.read_text().splitlines() if f.exists() else []
        f.unlink(missing_ok=True)
        return a

    def batterie(self):
        self.ps.mkdir(exist_ok=True)
        for nom, typ, val in (("BAT0", "Battery", "1"), ("AC", "Mains", "0")):
            (self.ps / nom).mkdir(exist_ok=True)
            (self.ps / nom / "type").write_text(typ + "\n")
            (self.ps / nom / "online").write_text(val + "\n")

    def lancer(self, cmd):
        cmd = cmd.replace("/sys/class/power_supply", str(self.ps))
        return subprocess.Popen(["sh", "-c", cmd], env=self.env)

    def jouer(self, *cmds):
        """Lance les commandes en même temps (comme hypridle) et attend leur fin."""
        ps = [self.lancer(c) for c in cmds]
        for p in ps:
            self.assertzero(p.wait(timeout=30))

    @staticmethod
    def assertzero(code):
        assert code == 0, code


def allumages(journal):
    return [l for l in journal if "dpms" in l and '"on"' in l]


class ConfigHypridle(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix="nc-ecran-reglages-")
        cls.nc = charger(Path(cls.tmp.name))

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def textes(self):
        for v in VARIANTES:
            yield v, SRC if v is None else self.nc.texte_veille({k: str(x) for k, x in v.items()}, SRC)

    @staticmethod
    def commandes(texte):
        """Lignes actives (sans commentaires) de la config."""
        return [l for l in texte.splitlines() if l.strip() and not l.strip().startswith("#")]

    def test_aucun_dpms_direct(self):
        for v, t in self.textes():
            with self.subTest(v=v):
                self.assertEqual([l for l in self.commandes(t) if "dpms" in l], [])
                self.assertIn("after_sleep_cmd = ~/.local/bin/nc-ecran on reveil", t)
                for x in listeners(t):
                    if "nc-ecran" in x.get("on-resume", ""):
                        self.assertIn("nc-ecran on", x["on-resume"])
                        self.assertIn("nc-ecran off", x["on-timeout"])

    def test_ecran_eteint_garde_ses_delais(self):
        # Le générateur reconnaît toujours les deux listeners « écran éteint »
        l = listeners(self.nc.texte_veille({"VEILLE_VERROU": "5", "VEILLE_ECRAN_BATTERIE": "20"}, SRC))
        eteint = [x["timeout"] for x in l if "nc-ecran off" in x["on-timeout"]]
        self.assertEqual(eteint, [330, 20])
        # Un ancien hypridle.conf (dpms direct) reste reconnu
        ancien = SRC.replace("~/.local/bin/nc-ecran off", "hyprctl dispatch 'hl.dsp.dpms({ action = \"off\" })'")
        l = listeners(self.nc.texte_veille({"VEILLE_ECRAN": "7"}, ancien))
        self.assertIn(420, [x["timeout"] for x in l if "dpms" in x["on-timeout"]])

    def test_un_seul_allumage_par_reprise(self):
        # Portable sur batterie, écran verrouillé : tous les listeners qui éteignent l'écran se déclenchent, puis la
        # reprise lance tous les on-resume (et le réveil) en même temps
        for reel in (False, True):
            for v, t in self.textes():
                l = listeners(t)
                ecran = [x for x in l if "nc-ecran" in x["on-timeout"]]
                if not ecran:
                    continue
                with self.subTest(v=v, reel=reel):
                    b = Banc(reel=reel)
                    try:
                        b.batterie()
                        (b.run / "nc-verrouille").write_text("")
                        for x in ecran:
                            b.jouer(x["on-timeout"])
                        self.assertTrue(b.journal(), "l'écran ne s'est pas éteint")
                        reprises = [x["on-resume"] for x in l if "on-resume" in x]
                        b.jouer(*reprises, "~/.local/bin/nc-ecran on")
                        self.assertEqual(len(allumages(b.journal())), 1)
                    finally:
                        b.fermer()


@unittest.skipUnless(shutil.which("flock"), "flock requis (util-linux)")
class NcEcran(unittest.TestCase):
    def setUp(self):
        self.b = Banc()

    def tearDown(self):
        self.b.fermer()

    def ecran(self, *actions):
        self.b.jouer(*(f"~/.local/bin/nc-ecran {a}" for a in actions))

    def test_deux_on_simultanes_un_seul_appel(self):
        self.ecran("on", "on")
        self.assertEqual(self.b.journal(), ['hl.dsp.dpms({ action = "on" })'])
        # Et beaucoup à la fois
        self.ecran("off")
        self.b.journal()
        self.ecran(*["on"] * 6)
        self.assertEqual(len(allumages(self.b.journal())), 1)

    def test_on_apres_on_ne_fait_rien(self):
        self.ecran("on")
        self.assertEqual(len(self.b.journal()), 1)
        self.ecran("on")
        self.assertEqual(self.b.journal(), [])

    def test_off_puis_on_refait_l_appel(self):
        self.ecran("off")
        self.ecran("off")
        self.ecran("on")
        self.assertEqual(self.b.journal(), ['hl.dsp.dpms({ action = "off" })', 'hl.dsp.dpms({ action = "on" })'])

    def test_bordure_suit_l_ecran(self):
        # Extinction : nc.bordure(true) et marque ; rallumage : nc.bordure(false) et marque retirée
        self.ecran("off")
        self.assertEqual(self.b.evals(), ["nc.bordure(true)"])
        self.assertTrue((self.b.run / "nc-ecran-eteint").exists())
        self.ecran("on")
        self.assertEqual(self.b.evals(), ["nc.bordure(false)"])
        self.assertFalse((self.b.run / "nc-ecran-eteint").exists())
        # Appels simultanés : un seul eval
        self.ecran("off", "off", "off")
        self.assertEqual(self.b.evals(), ["nc.bordure(true)"])

    def test_bordure_rendue_meme_si_ecran_deja_rallume(self):
        # Une touche a rallumé l'écran avant le on-resume : pas de dpms, mais la bordure doit repartir
        b = Banc(reel=True)
        try:
            (b.run / "nc-ecran-eteint").write_text("")
            b.jouer("~/.local/bin/nc-ecran on")
            self.assertEqual(b.journal(), [])
            self.assertEqual(b.evals(), ["nc.bordure(false)"])
            self.assertFalse((b.run / "nc-ecran-eteint").exists())
        finally:
            b.fermer()

    def test_etat_reel_de_hyprland(self):
        b = Banc(reel=True)
        try:
            # Écran déjà allumé d'après Hyprland (une touche l'a rallumé) : rien, même sans état noté
            b.jouer("~/.local/bin/nc-ecran on")
            self.assertEqual(b.journal(), [])
            # Plus de 5 s après : l'état réel décide encore
            (b.run / "nc-ecran.etat").write_text("on 1\n")
            b.jouer("~/.local/bin/nc-ecran on")
            self.assertEqual(b.journal(), [])
            # Éteint d'après Hyprland alors que l'état noté dit « on » (vieux) : rallumé
            (b.faux / "dpms").write_text("false\n")
            b.jouer("~/.local/bin/nc-ecran on")
            self.assertEqual(len(allumages(b.journal())), 1)
        finally:
            b.fermer()

    def test_reveil_rallume_une_seule_fois(self):
        # Au réveil, Hyprland peut croire l'écran allumé alors qu'il reste noir : « reveil » rallume quand même, mais
        # derrière le verrou et la garde, donc un seul appel avec les on-resume lancés en même temps
        b = Banc(reel=True)
        try:
            b.jouer("~/.local/bin/nc-ecran on reveil", "~/.local/bin/nc-ecran on", "~/.local/bin/nc-ecran on")
            self.assertEqual(len(allumages(b.journal())), 1)
            b.jouer("~/.local/bin/nc-ecran on reveil")
            self.assertEqual(b.journal(), [])
            # « reveil » ne force qu'un allumage : écran déjà éteint d'après Hyprland, « off reveil » ne fait rien
            (b.run / "nc-ecran.etat").write_text("on 1\n")
            (b.faux / "dpms").write_text("false\n")
            b.jouer("~/.local/bin/nc-ecran off reveil")
            self.assertEqual(b.journal(), [])
        finally:
            b.fermer()

    def test_hors_hyprland_rien_sans_erreur(self):
        env = {k: v for k, v in self.b.env.items() if k != "HYPRLAND_INSTANCE_SIGNATURE"}
        for e in (env, dict(self.b.env, PATH="/nulle-part")):
            p = subprocess.run([str(NC_ECRAN), "on"], env=e, capture_output=True, text=True, timeout=10)
            self.assertEqual((p.returncode, p.stdout, p.stderr), (0, "", ""))
        self.assertEqual(self.b.journal(), [])

    def test_usage(self):
        p = subprocess.run(["sh", str(NC_ECRAN)], env=self.b.env, capture_output=True, text=True, timeout=10)
        self.assertEqual(p.returncode, 1)
        self.assertIn("nc-ecran on", p.stdout)

    def test_sh_simple(self):
        self.assertEqual(NC_ECRAN.read_text().splitlines()[0], "#!/bin/sh")
        self.assertTrue(os.access(NC_ECRAN, os.X_OK))
        for sh in ("sh", "dash", "bash"):
            if shutil.which(sh):
                self.assertEqual(subprocess.run([sh, "-n", str(NC_ECRAN)]).returncode, 0, sh)


class AppelantsPassentParNcEcran(unittest.TestCase):
    def test_aucun_dpms_direct_dans_le_depot(self):
        fautes = []
        for f in list((REPO / "home").rglob("*")) + [REPO / "install.sh"]:
            if not f.is_file() or f == NC_ECRAN:
                continue
            try:
                t = f.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue
            for n, l in enumerate(t.splitlines(), 1):
                if re.search(r"hl\.dsp\.dpms|dispatch\s+['\"]?dpms", l):
                    fautes.append(f"{f.relative_to(REPO)}:{n}")
        self.assertEqual(fautes, [], "allumer ou éteindre l'écran : passer par nc-ecran")


if __name__ == "__main__":
    unittest.main()
