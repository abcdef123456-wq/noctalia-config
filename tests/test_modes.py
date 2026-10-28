"""Modes Concentration : la commande nc-modes, nc-fond-jour-nuit imposer, le réglage ILE_CONCENTRATION.

- Aucun mode par défaut : rien ne change, rien n'est écrit.
- Activer applique (arguments exacts des faux outils) ; désactiver remet l'état d'avant.
- Un réglage changé à la main pendant le mode n'est pas écrasé à la sortie (Ne pas déranger, profil d'énergie, fond, IA).
- Le mode actif est dans un fichier d'état (survit au redémarrage de l'île) ; relire l'état ne réapplique rien.
- IA_MODE=non : l'IA des notifications n'est jamais touchée. Fichier abîmé, trop gros ou aux valeurs hors liste : ignoré.
- Écriture atomique, noms en texte brut, jamais de shell, aucune commande root ni sudo.
Tout se passe dans un dossier temporaire court (HOME, XDG_*, TMPDIR) avec de faux outils qui notent leurs arguments."""
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[1]
BIN = REPO / "home/.local/bin"
NC_MODES = BIN / "nc-modes"

FAUX_ENERGIE = """#!/usr/bin/env python3
import json, os, sys
d = os.environ["FAUX_ETAT"]
open(d + "/journal", "a").write("nc-energie " + " ".join(sys.argv[1:]) + "\\n")
def lire(n):
    try: return open(d + "/" + n).read().strip()
    except OSError: return ""
a = sys.argv[1:]
if a[0] == "liste":
    print(json.dumps({"ia": False, "disponible": True, "assistant_root": False, "actif": lire("actif") or None,
                      "profils": [{"id": "calme", "nom": "Calme", "valide": True}, {"id": "vite", "nom": "Vite", "valide": True}]}))
elif a[0] == "apercu":
    print(json.dumps({"changements": [] if lire("reglage") == a[1] else [{"cle": "x"}]}))
elif a[0] == "appliquer":
    if lire("reglage") == a[1]:
        print(json.dumps({"ok": True, "applique": False})); sys.exit(0)
    open(d + "/actif", "w").write(a[1]); open(d + "/reglage", "w").write(a[1])
    print(json.dumps({"ok": True, "applique": True}))
elif a[0] == "revenir":
    for n in ("actif", "reglage"):
        try: os.unlink(d + "/" + n)
        except OSError: pass
    print(json.dumps({"ok": True, "revenu": True}))
"""
FAUX_FOND = """#!/usr/bin/env python3
import os, sys
d = os.environ["FAUX_ETAT"]
open(d + "/journal", "a").write("nc-fond-jour-nuit " + " ".join(sys.argv[1:]) + "\\n")
f = os.environ["XDG_STATE_HOME"] + "/nc/fond-impose"
if sys.argv[1] == "imposer":
    if sys.argv[2] == "aucun":
        try: os.unlink(f)
        except OSError: pass
    else:
        os.makedirs(os.path.dirname(f), exist_ok=True); open(f, "w").write(sys.argv[2] + "\\n")
"""
FAUX_REGLAGES = """#!/usr/bin/env python3
import os, re, sys
d = os.environ["FAUX_ETAT"]
open(d + "/journal", "a").write("nc-reglages " + " ".join(sys.argv[1:]) + "\\n")
f = os.environ["XDG_CONFIG_HOME"] + "/nc/reglages.conf"
try: l = [x for x in open(f).read().splitlines() if not x.startswith(sys.argv[2] + "=")]
except OSError: l = []
if sys.argv[1] == "set": l.append(sys.argv[2] + "=" + sys.argv[3])
os.makedirs(os.path.dirname(f), exist_ok=True); open(f, "w").write("\\n".join(l) + "\\n")
"""


class Base(unittest.TestCase):
    def setUp(self):
        os.makedirs("/tmp/claude-1000", exist_ok=True)
        self.tmp = tempfile.TemporaryDirectory(prefix="nm-", dir="/tmp/claude-1000")
        self.addCleanup(self.tmp.cleanup)
        r = Path(self.tmp.name)
        self.r = r
        for s in ("home", "config", "state", "data", "cache", "run", "tmp", "outils", "faux"):
            (r / s).mkdir()
        for nom, texte in (("nc-energie", FAUX_ENERGIE), ("nc-fond-jour-nuit", FAUX_FOND), ("nc-reglages", FAUX_REGLAGES)):
            f = r / "outils" / nom
            f.write_text(texte)
            f.chmod(0o755)
        self.env = dict(os.environ, HOME=str(r / "home"), XDG_CONFIG_HOME=str(r / "config"), XDG_STATE_HOME=str(r / "state"),
                        XDG_DATA_HOME=str(r / "data"), XDG_CACHE_HOME=str(r / "cache"), XDG_RUNTIME_DIR=str(r / "run"),
                        TMPDIR=str(r / "tmp"), NC_MODES_OUTILS=str(r / "outils"), FAUX_ETAT=str(r / "faux"), NC_LANGUE="fr")
        self.conf = r / "config/nc/reglages.conf"
        self.modes = r / "config/nc/modes.json"
        self.etat = r / "state/nc/modes-etat.json"

    def reglages(self, **v):
        self.conf.parent.mkdir(parents=True, exist_ok=True)
        self.conf.write_text("".join("%s=%s\n" % kv for kv in v.items()))

    def nc(self, *args):
        p = subprocess.run([sys.executable, str(NC_MODES), *args], env=self.env, capture_output=True, text=True, timeout=60,
                           stdin=subprocess.DEVNULL)
        try:
            return json.loads(p.stdout), p.returncode
        except ValueError:
            self.fail("sortie illisible : %r %r" % (p.stdout, p.stderr))

    def journal(self):
        j = self.r / "faux/journal"
        return j.read_text().splitlines() if j.exists() else []

    def creer(self, nom="Travail", **champs):
        r, _ = self.nc("creer", nom)
        for cle, val in champs.items():
            self.assertTrue(self.nc("regler", r["id"], cle, val)[0]["ok"])
        return r["id"]

    def faux_etat(self, nom):
        f = self.r / "faux" / nom
        return f.read_text().strip() if f.exists() else ""

    def impose(self):
        f = self.r / "state/nc/fond-impose"
        return f.read_text().strip() if f.exists() else ""


class Defauts(Base):
    def test_aucun_mode_rien_ne_change(self):
        r, code = self.nc("liste")
        self.assertEqual((code, r["ok"], r["modes"], r["actif"]), (0, True, [], None))
        self.assertEqual(self.nc("etat")[0]["actif"], None)
        r, _ = self.nc("sortir", "--dnd", "oui")
        self.assertEqual((r["ok"], r["dnd"]), (True, None))
        self.assertFalse(self.modes.exists() or self.etat.exists())      # même pas un fichier créé par la lecture
        self.assertEqual(self.journal(), [])
        self.assertEqual(self.nc("activer", "travail", "--dnd", "non")[1], 1)       # mode inconnu : refusé, rien appliqué
        self.assertEqual(self.journal(), [])

    def test_exemples_a_creer_d_un_clic(self):
        for nom, ex in (("Travail", "travail"), ("Nuit", "nuit"), ("Jeu", "jeu")):
            self.assertTrue(self.nc("creer", nom, "--exemple", ex)[0]["ok"])
        modes = {m["id"]: m for m in self.nc("liste")[0]["modes"]}
        self.assertEqual(modes["nuit"]["fond"], "nuit")
        self.assertEqual(modes["jeu"]["notifs_ia"], "non")
        self.assertEqual({m["dnd"] for m in modes.values()}, {"oui"})
        self.assertEqual(self.journal(), [])                              # créer n'applique rien

    def test_creer_renommer_regler_supprimer(self):
        i = self.creer("Mon mode")
        self.assertEqual(i, "mon-mode")
        self.assertEqual(self.creer("Mon mode"), "mon-mode-2")
        self.assertTrue(self.nc("renommer", i, "Lecture")[0]["ok"])
        self.assertEqual(self.nc("regler", i, "fond", "midi")[1], 1)       # hors liste
        self.assertEqual(self.nc("regler", i, "energie", "a b; rm")[1], 1)
        self.assertEqual(self.nc("regler", i, "icone", "inconnue")[1], 1)
        self.assertEqual(self.nc("renommer", i, "x" * 25)[1], 1)
        self.assertEqual(self.nc("renommer", i, "a\x1bb")[1], 1)
        self.assertEqual(self.nc("creer", "  ")[1], 1)
        self.assertTrue(self.nc("supprimer", i)[0]["ok"])
        self.assertEqual([m["id"] for m in self.nc("liste")[0]["modes"]], ["mon-mode-2"])
        for n in range(20):
            self.nc("creer", "M%d" % n)
        self.assertEqual(len(self.nc("liste")[0]["modes"]), 12)           # bornés

    def test_ecriture_atomique(self):
        self.creer("A")
        self.assertEqual(sorted(p.name for p in self.modes.parent.iterdir()), ["modes.json"])     # pas de .tmp qui traîne
        src = NC_MODES.read_text()
        self.assertIn("tempfile.mkstemp", src)
        self.assertIn("dir=dossier", src)                # fichier temporaire dans le MÊME dossier
        self.assertIn("os.replace(tmp, chemin)", src)
        self.assertIn("os.fsync", src)
        self.assertEqual(oct(self.modes.stat().st_mode & 0o777), "0o600")


class Validation(Base):
    def test_fichier_abime_trop_gros_ou_hors_liste(self):
        self.modes.parent.mkdir(parents=True)
        self.modes.write_text("{pas du json")
        self.assertEqual(self.nc("liste")[0]["modes"], [])
        self.modes.write_text(json.dumps({"modes": [{"id": "x", "nom": "x", "pad": "y" * 70000}]}))
        self.assertEqual(self.nc("liste")[0]["modes"], [])
        self.modes.write_text("[1, 2]")
        self.assertEqual(self.nc("liste")[0]["modes"], [])
        bon = {"id": "bon", "nom": "Bon", "champ_inconnu": 1}
        self.modes.write_text(json.dumps({"version": 9, "extra": 1, "modes": [
            bon, {"id": "A B", "nom": "id"}, {"id": "dnd", "nom": "d", "dnd": "peut-etre"}, {"id": "fond", "nom": "f", "fond": "soir"},
            {"id": "ia", "nom": "i", "notifs_ia": 1}, {"id": "en", "nom": "e", "energie": "x;y"}, {"id": "ic", "nom": "i", "icone": "../x"},
            {"id": "long", "nom": "n" * 25}, {"id": "bon", "nom": "doublon"}, "texte", None, {"id": "ctl", "nom": "a\x07b"}]}))
        modes = self.nc("liste")[0]["modes"]
        self.assertEqual([m["id"] for m in modes], ["bon"])
        self.assertNotIn("champ_inconnu", modes[0])
        self.assertEqual((modes[0]["dnd"], modes[0]["energie"], modes[0]["fond"], modes[0]["notifs_ia"]), ("garder", "", "garder", "garder"))

    def test_etat_abime_ignore(self):
        self.etat.parent.mkdir(parents=True)
        for texte in ("{nope", "[]", json.dumps({"actif": "../x", "nom": "x"}), json.dumps({"actif": "a", "nom": "\x00"}),
                      json.dumps({"actif": "a", "nom": "ok", "pad": "x" * 70000})):
            self.etat.write_text(texte)
            self.assertEqual(self.nc("etat")[0]["actif"], None, texte[:30])
        self.etat.write_text(json.dumps({"actif": "a", "nom": "ok", "dnd": {"avant": "oui", "pose": True}, "energie": {"pose": "a b"},
                                         "fond": {"avant": "lune", "pose": "nuit"}, "notifs_ia": {"avant": 3, "pose": "oui"}}))
        e = self.nc("etat")[0]
        self.assertEqual((e["actif"], e["dnd_pose"]), ("a", None))        # chaque morceau invalide est ignoré, le reste tient

    def test_noms_en_texte_brut_dans_le_fichier(self):
        i = self.creer("<b>x</b> 'q' $(id)")
        m = self.nc("liste")[0]["modes"][0]
        self.assertEqual(m["nom"], "<b>x</b> 'q' $(id)")
        self.assertEqual(i, "b-x-b-q-id")
        self.assertRegex(i, r"^[a-z0-9-]{1,24}$")


class Appliquer(Base):
    def test_activer_applique_avec_les_arguments_exacts(self):
        self.reglages(FONDS_JOUR_NUIT="oui", NOTIFS_IA="non")
        i = self.creer("Travail", dnd="oui", energie="calme", fond="nuit", notifs_ia="oui")
        r, code = self.nc("activer", i, "--dnd", "non")
        self.assertEqual((code, r["ok"], r["actif"], r["dnd"]), (0, True, i, "oui"))
        self.assertEqual(self.journal(), ["nc-energie liste --json", "nc-energie appliquer calme --oui --json",
                                          "nc-fond-jour-nuit imposer nuit", "nc-reglages set NOTIFS_IA oui"])
        self.assertEqual(self.impose(), "nuit")
        e = json.loads(self.etat.read_text())
        self.assertEqual((e["actif"], e["nom"], e["dnd"], e["energie"], e["fond"], e["notifs_ia"]),
                         (i, "Travail", {"avant": False, "pose": True}, {"pose": "calme", "avant_actif": None},
                          {"avant": "", "pose": "nuit"}, {"avant": "non", "pose": "oui"}))
        self.assertEqual(self.nc("etat")[0]["actif"], i)

    def test_desactiver_remet_exactement_l_avant(self):
        self.reglages(FONDS_JOUR_NUIT="oui", NOTIFS_IA="non")
        (self.r / "faux/actif").write_text("vite")                        # un profil était déjà actif
        (self.r / "faux/reglage").write_text("vite")
        i = self.creer("Travail", dnd="oui", energie="calme", fond="nuit", notifs_ia="oui")
        self.nc("activer", i, "--dnd", "non")
        self.assertEqual(self.faux_etat("actif"), "calme")
        (self.r / "faux/journal").unlink()
        r, _ = self.nc("sortir", "--dnd", "oui")
        self.assertEqual((r["ok"], r["actif"], r["dnd"]), (True, None, "non"))
        j = self.journal()
        self.assertEqual(j[:4], ["nc-energie liste --json", "nc-energie apercu calme --json", "nc-energie revenir --json",
                                 "nc-energie appliquer vite --oui --json"])
        self.assertIn("nc-fond-jour-nuit imposer aucun", j)
        self.assertEqual(j[-1], "nc-reglages set NOTIFS_IA non")
        self.assertEqual(self.faux_etat("actif"), "vite")
        self.assertEqual(self.impose(), "")
        self.assertFalse(self.etat.exists())

    def test_ia_absente_du_fichier_est_remise_absente(self):
        self.reglages(FONDS_JOUR_NUIT="oui")
        i = self.creer("Jeu", notifs_ia="oui")
        self.nc("activer", i, "--dnd", "non")
        self.assertEqual(self.journal(), ["nc-reglages set NOTIFS_IA oui"])
        self.nc("sortir", "--dnd", "non")
        self.assertEqual(self.journal()[-1], "nc-reglages reset NOTIFS_IA")

    def test_ne_pose_rien_quand_c_est_deja_comme_voulu(self):
        self.reglages(NOTIFS_IA="oui")
        i = self.creer("Jeu", dnd="oui", notifs_ia="oui")
        r, _ = self.nc("activer", i, "--dnd", "oui")
        self.assertIsNone(r["dnd"])
        self.assertEqual(self.journal(), [])
        e = json.loads(self.etat.read_text())
        self.assertEqual((e["dnd"], e["notifs_ia"]), (None, None))
        r, _ = self.nc("sortir", "--dnd", "oui")
        self.assertIsNone(r["dnd"])                                       # il n'avait rien changé : rien à remettre

    def test_ia_mode_non_notifications_ia_jamais_touchees(self):
        self.reglages(IA_MODE="non", NOTIFS_IA="oui")
        i = self.creer("Jeu", dnd="oui", notifs_ia="non")
        r, _ = self.nc("activer", i, "--dnd", "non")
        self.assertEqual(r["dnd"], "oui")                                 # le reste s'applique
        self.assertEqual([l for l in self.journal() if "nc-reglages" in l], [])
        self.nc("sortir", "--dnd", "oui")
        self.assertEqual([l for l in self.journal() if "nc-reglages" in l], [])
        self.assertIn("NOTIFS_IA=oui", self.conf.read_text())

    def test_fond_sans_effet_si_reglage_coupe(self):
        self.reglages(FONDS_JOUR_NUIT="non")
        i = self.creer("Nuit", fond="nuit")
        self.nc("activer", i, "--dnd", "non")
        self.assertEqual(self.journal(), [])
        self.assertEqual(json.loads(self.etat.read_text())["fond"], None)

    def test_un_seul_mode_a_la_fois(self):
        self.reglages(NOTIFS_IA="non")
        a = self.creer("A", dnd="oui", notifs_ia="oui")
        b = self.creer("B", dnd="non")
        self.nc("activer", a, "--dnd", "non")
        r, _ = self.nc("activer", b, "--dnd", "oui")
        self.assertEqual(self.nc("etat")[0]["actif"], b)
        self.assertIn("NOTIFS_IA=non", self.conf.read_text())             # A a été remis avant B
        self.assertEqual(r["dnd"], "non")                                 # A remet « non » (avant), B voulait « non »
        self.assertEqual(self.nc("supprimer", b)[1], 1)                   # actif : refusé

    def test_jamais_de_shell_ni_de_root(self):
        src = NC_MODES.read_text()
        code = re.sub(r"#.*", "", src)
        self.assertNotRegex(code, r"shell\s*=\s*True|os\.system|\bsudo\b|pkexec|doas|os\.popen|/usr/local/bin|nc-energie-root|nc-limite-charge")
        self.assertIn("subprocess.run([outil(nom), *args]", src)
        self.assertNotRegex(src.split('"""')[1] if '"""' in src else "", r"\bpkexec\b")

    def test_texte_venu_du_fichier_n_atteint_pas_un_programme(self):
        # Un identifiant d'énergie piégé dans le fichier est refusé à la lecture : jamais passé à nc-energie
        self.modes.parent.mkdir(parents=True)
        self.modes.write_text(json.dumps({"modes": [{"id": "m", "nom": "M", "energie": "--oui; touch pwn"}]}))
        self.assertEqual(self.nc("liste")[0]["modes"], [])
        self.assertEqual(self.nc("activer", "m", "--dnd", "non")[1], 1)
        self.assertEqual(self.journal(), [])


class MainsLibres(Base):
    """Cas 1 : ce que l'utilisateur change à la main pendant le mode n'est pas écrasé à la sortie."""

    def activer_tout(self):
        self.reglages(FONDS_JOUR_NUIT="oui", NOTIFS_IA="non")
        i = self.creer("Travail", dnd="oui", energie="calme", fond="nuit", notifs_ia="oui")
        self.nc("activer", i, "--dnd", "non")
        (self.r / "faux/journal").unlink()
        return i

    def test_dnd_avant_oui_puis_main(self):
        i = self.creer("Calme", dnd="non")
        self.nc("activer", i, "--dnd", "oui")                              # avant : oui, posé : non
        r, _ = self.nc("sortir", "--dnd", "oui")                           # l'utilisateur a remis « oui » à la main
        self.assertIsNone(r["dnd"])                                       # c'est son choix : rien par-dessus
        self.assertTrue(any("Ne pas déranger" in m for m in r["messages"]))
        self.nc("activer", i, "--dnd", "oui")
        r, _ = self.nc("sortir", "--dnd", "non")                           # resté tel que posé
        self.assertEqual(r["dnd"], "oui")

    def test_profil_energie_change_a_la_main(self):
        i = self.activer_tout()
        (self.r / "faux/actif").write_text("vite")                        # l'utilisateur applique un autre profil
        r, _ = self.nc("sortir", "--dnd", "oui")
        self.assertNotIn("nc-energie revenir --json", self.journal())
        self.assertEqual(self.faux_etat("actif"), "vite")
        self.assertTrue(any("énergie" in m for m in r["messages"]))

    def test_reglage_d_energie_touche_a_la_main(self):
        self.activer_tout()
        (self.r / "faux/reglage").write_text("autre")                     # le profil est actif mais un réglage a bougé
        self.nc("sortir", "--dnd", "oui")
        self.assertNotIn("nc-energie revenir --json", self.journal())

    def test_profil_energie_retire_a_la_main(self):
        self.activer_tout()
        (self.r / "faux/actif").unlink()                                  # l'utilisateur a fait « revenir » lui-même
        self.nc("sortir", "--dnd", "oui")
        self.assertNotIn("nc-energie revenir --json", self.journal())

    def test_fond_et_ia_changes_a_la_main(self):
        self.activer_tout()
        (self.r / "state/nc/fond-impose").unlink()
        self.reglages(FONDS_JOUR_NUIT="oui", NOTIFS_IA="non")             # l'utilisateur a recoupé l'IA
        self.nc("sortir", "--dnd", "oui")
        self.assertEqual([l for l in self.journal() if "nc-fond-jour-nuit" in l or "nc-reglages" in l], [])
        self.assertIn("NOTIFS_IA=non", self.conf.read_text())

    def test_tout_intact_tout_remis(self):
        self.activer_tout()
        r, _ = self.nc("sortir", "--dnd", "oui")
        self.assertEqual(r["dnd"], "non")
        self.assertIn("nc-energie revenir --json", self.journal())
        self.assertIn("nc-fond-jour-nuit imposer aucun", self.journal())
        self.assertIn("nc-reglages set NOTIFS_IA non", self.journal())


class Survie(Base):
    """Cas 2 : le mode actif survit au redémarrage de l'île ; relire ne réapplique rien."""

    def test_etat_sur_disque_relu_sans_rien_reappliquer(self):
        self.reglages(FONDS_JOUR_NUIT="oui", NOTIFS_IA="non")
        i = self.creer("Travail", dnd="oui", energie="calme", fond="nuit", notifs_ia="oui")
        self.nc("activer", i, "--dnd", "non")
        avant = self.journal()
        self.assertTrue(self.etat.is_file())
        # « Redémarrage » : un nouveau processus lit l'état (liste et état à plusieurs reprises)
        for _ in range(3):
            e = self.nc("etat")[0]
            self.assertEqual((e["actif"], e["nom"], e["dnd_pose"]), (i, "Travail", True))
            self.assertEqual(self.nc("liste")[0]["actif"], i)
        self.assertEqual(self.journal(), avant)                           # rien de relancé
        self.assertEqual(json.loads(self.etat.read_text())["dnd"], {"avant": False, "pose": True})
        # Et la sortie après redémarrage remet bien tout
        r, _ = self.nc("sortir", "--dnd", "oui")
        self.assertEqual(r["dnd"], "non")
        self.assertIn("nc-energie revenir --json", self.journal())

    def test_pas_de_dossier_prive_dans_le_depot(self):
        for f in (BIN / "nc-modes", REPO / "home/.config/quickshell/nc-ile/Modes.qml"):
            self.assertNotRegex(f.read_text(), r"/home/[a-z]|@gmail|\.com\b")


class FondImpose(unittest.TestCase):
    """nc-fond-jour-nuit imposer : le vrai script, écran « éteint » pour qu'aucun fond ni minuteur ne soit touché."""

    def setUp(self):
        os.makedirs("/tmp/claude-1000", exist_ok=True)
        self.tmp = tempfile.TemporaryDirectory(prefix="nf-", dir="/tmp/claude-1000")
        self.addCleanup(self.tmp.cleanup)
        r = Path(self.tmp.name)
        for s in ("home", "config/nc", "state", "run", "tmp"):
            (r / s).mkdir(parents=True)
        (r / "run/nc-ecran-eteint").write_text("")
        self.r = r
        self.env = dict(os.environ, HOME=str(r / "home"), XDG_CONFIG_HOME=str(r / "config"), XDG_STATE_HOME=str(r / "state"),
                        XDG_RUNTIME_DIR=str(r / "run"), TMPDIR=str(r / "tmp"), PATH="/usr/bin:/bin")

    def lancer(self, *a):
        return subprocess.run([sys.executable, str(BIN / "nc-fond-jour-nuit"), *a], env=self.env, capture_output=True, text=True,
                              timeout=30, stdin=subprocess.DEVNULL).returncode

    def test_imposer(self):
        f = self.r / "state/nc/fond-impose"
        self.assertEqual(self.lancer("imposer", "nuit"), 1)               # réglage coupé : refusé
        self.assertFalse(f.exists())
        (self.r / "config/nc/reglages.conf").write_text("FONDS_JOUR_NUIT=oui\n")
        self.assertEqual(self.lancer("imposer", "nuit"), 0)
        self.assertEqual(f.read_text(), "nuit\n")
        self.assertEqual(self.lancer("imposer", "jour"), 0)
        self.assertEqual(f.read_text(), "jour\n")
        self.assertEqual(self.lancer("imposer", "midi"), 2)
        self.assertEqual(self.lancer("imposer"), 2)
        self.assertEqual(f.read_text(), "jour\n")
        self.assertEqual(self.lancer("imposer", "aucun"), 0)
        self.assertFalse(f.exists())
        self.assertEqual([p.name for p in f.parent.iterdir()], [])
        (self.r / "config/nc/reglages.conf").write_text("FONDS_JOUR_NUIT=non\n")
        self.assertEqual(self.lancer("imposer", "aucun"), 0)              # « aucun » marche toujours (rendre la main)


class Reglage(unittest.TestCase):
    def test_reglage_et_garde_ile(self):
        import importlib.machinery
        import importlib.util
        c = importlib.machinery.SourceFileLoader("nc_reglages_modes", str(BIN / "nc-reglages"))
        m = importlib.util.module_from_spec(importlib.util.spec_from_loader(c.name, c))
        c.exec_module(m)
        r = m.PAR_CLE["ILE_CONCENTRATION"]
        self.assertEqual((r.defaut, r.section, r.genre), ("oui", "Île", "ouinon"))
        self.assertEqual(m.MATERIEL["ILE_CONCENTRATION"], "ile")
        self.assertIn("`ILE_CONCENTRATION`", (REPO / "README.md").read_text())
        self.assertIn(".local/bin/nc-modes", (REPO / "export.sh").read_text())

    def test_qml_branchement(self):
        qml = REPO / "home/.config/quickshell/nc-ile"
        sans = lambda n: re.sub(r"//.*", "", (qml / n).read_text())
        self.assertIn('Modes.pagePossible ? ["concentration"] : []', sans("Etat.qml"))
        self.assertIn("concentration: pConcentration", sans("Ile.qml"))
        self.assertIn("Component { id: pConcentration; PageConcentration {} }", sans("Ile.qml"))
        self.assertIn("Modes.ouvrirPage()", sans("Centre.qml"))
        self.assertIn("visible: Modes.pastille", sans("Compact.qml"))
        self.assertIn("Modes.nomVisible", sans("Compact.qml"))
        self.assertIn("Partage.silence ? \"\" : actifNom", sans("Modes.qml"))
        # Aucun minuteur ni sondage ; programme lancé en argv ; pas de shell
        code = sans("Modes.qml") + sans("PageConcentration.qml") + sans("EditeurMode.qml") + sans("ChoixMode.qml")
        self.assertNotRegex(code, r"Timer|repeat:\s*true|running:\s*true|\bsh -c|bash -c|sudo|pkexec")
        # Textes venus du fichier : texte brut (Texte.qml), jamais Text ni RichText
        self.assertNotRegex(code, r"(?m)^\s*Text \{|RichText|StyledText|AutoText")
        self.assertIn("maximumLength: 24", sans("PageConcentration.qml"))
        # Pas de nouveau component inline dans un fichier existant
        for n in ("Etat.qml", "Ile.qml", "Centre.qml", "Compact.qml"):
            neuf = subprocess.run(["git", "diff", "-U0", "HEAD", "--", str(qml / n)], cwd=REPO, capture_output=True, text=True).stdout
            self.assertNotRegex("\n".join(l for l in neuf.splitlines() if l.startswith("+")), r"\bcomponent\s+\w+\s*:")


if __name__ == "__main__":
    unittest.main()
