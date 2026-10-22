"""nc-session, version 2 (carrousel des sessions) : lecture d'une version 1 telle quelle, réécrite en version 2 à la
première modification ; nc-session json (format figé) ; modifier (chaque clé, valide et refusée) ; renommer et
dupliquer (aperçu compris) ; aperçu (grim sous la barre, à la taille exacte de la carte du carrousel, réglage
SESSIONS_CAPTURE, sans grim : le schéma seul ; plus de tranches inclinées ni d'ImageMagick) ; ouvrir et ses
étapes (fond, profil, Ne pas déranger, noms des bureaux, zones, fermer les autres), chacune sautée sans son outil.
Tout se passe dans un faux HOME ; chaque faux outil prend ce dossier à partir de son propre chemin et note ses appels."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest

REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "home/.local/bin/nc-session"

# Faux outils : <home>/.local/bin/<outil> ; <home> pris de leur propre chemin, jamais de HOME
JOURNAL_SH = '''#!/bin/sh
d=${0%/*}; H="$d/../.."
echo "${0##*/} $*" >> "$H/appels"
'''
FAUX_HYPRCTL = r'''#!/usr/bin/env python3
import json, sys
from pathlib import Path
H = Path(__file__).resolve().parents[2]
a = sys.argv[1:]
if a[:2] == ["clients", "-j"]:
    print((H / "clients.json").read_text())
elif a[:2] == ["monitors", "-j"]:
    f = H / "monitors.json"
    print(f.read_text() if f.exists() else "[]")
elif a and a[0] in ("dispatch", "eval"):
    with (H / "appels").open("a") as f: f.write("hyprctl " + a[0] + " " + a[1] + "\n")
    if a[0] == "eval" and "zones_dispo" in a[1] and not (H / "zones_dispo").exists():
        sys.exit(1)
    # Une fenêtre fermée disparaît
    if "window.close" in a[1]:
        adr = a[1].split("address:")[1].split("'")[0]
        c = [x for x in json.loads((H / "clients.json").read_text()) if x["address"] != adr]
        (H / "clients.json").write_text(json.dumps(c))
'''
FAUX_APPS = r'''#!/usr/bin/env python3
import json, sys
from pathlib import Path
H = Path(__file__).resolve().parents[2]
if sys.argv[1] == "list":
    print(json.dumps([{"id": "firefox", "wmclass": "firefox"}, {"id": "discord", "wmclass": "discord"}, {"id": "gimp", "wmclass": "gimp"}]))
else:
    with (H / "appels").open("a") as f: f.write("nc-apps " + " ".join(sys.argv[1:]) + "\n")
'''
FAUX_GRIM = r'''#!/usr/bin/env python3
import sys
from pathlib import Path
H = Path(__file__).resolve().parents[2]
with (H / "appels").open("a") as f: f.write("grim " + " ".join(sys.argv[1:]) + "\n")
Path(sys.argv[-1]).write_bytes(b"\x89PNG\r\n\x1a\n faux")
'''
# Faux nc-reglages : « set SESSION_DEMARRAGE X » l'écrit dans reglages.conf (comme le vrai)
FAUX_REGLAGES = JOURNAL_SH + '''[ "$1" = set ] && [ "$2" = SESSION_DEMARRAGE ] && printf 'SESSION_DEMARRAGE=%s\\n' "$3" > "$H/.config/nc/reglages.conf"
exit 0
'''
# Faux nc-raccourci : Super+Alt+9 est déjà pris
FAUX_RACCOURCI = JOURNAL_SH + '''[ "$1" = ajoute ] && [ "$2" = Super+Alt+9 ] && { echo "nc-raccourci : Super+Alt+9 est déjà pris" >&2; exit 1; }
exit 0
'''
# Faux qs : l'île ne tourne que si <home>/ile existe
FAUX_QS = JOURNAL_SH + '[ -e "$H/ile" ]\n'
# Faux notify-send : le bouton choisi est dans <home>/bouton
FAUX_NOTIFY = JOURNAL_SH + '[ -e "$H/bouton" ] && { read -r l < "$H/bouton"; echo "$l"; }\nexit 0\n'


def client(adresse, classe, bureau, at=(0, 0), taille=(800, 600), pid=999999, ecran=0, **autres):
    return dict({"address": adresse, "class": classe, "title": classe, "mapped": True, "workspace": {"id": bureau},
                 "monitor": ecran, "floating": False, "at": list(at), "size": list(taille), "fullscreen": 0, "pid": pid}, **autres)


ECRANS = [{"id": 0, "name": "eDP-1", "x": 0, "y": 0, "width": 2560, "height": 1600, "scale": 1.6, "transform": 0, "focused": False},
          {"id": 1, "name": "DP-1", "x": 1600, "y": 0, "width": 1920, "height": 1080, "scale": 1.0, "transform": 0, "focused": True}]

CLES_SESSION = ["nom", "date", "nb_fenetres", "applis", "icone", "couleur", "fond", "profil", "npd", "demarrage",
                "fermer_autres", "raccourci", "bureaux_noms", "apercu", "tranche", "tranche_etroite", "schema", "fenetres"]
CLES_FENETRE = ["classe", "titre", "bureau", "ecran", "flottant", "plein_ecran", "inclure", "terminal"]


class Base(unittest.TestCase):
    def setUp(self):
        d = tempfile.TemporaryDirectory(prefix="nc-session-v2-")
        self.addCleanup(d.cleanup)
        self.home = Path(d.name)
        self.bin = self.home / ".local/bin"
        self.bin.mkdir(parents=True)
        # Seuls les faux outils sont trouvés : un vrai grim, gdbus ou powerprofilesctl ne sera jamais lancé
        base = self.home / "base"
        base.mkdir()
        (base / "python3").symlink_to(sys.executable)
        (base / "sh").symlink_to("/bin/sh")
        self.path = f"{self.bin}:{base}"
        outils = {"hyprctl": FAUX_HYPRCTL, "nc-apps": FAUX_APPS, "grim": FAUX_GRIM, "nc-reglages": FAUX_REGLAGES,
                  "nc-raccourci": FAUX_RACCOURCI, "qs": FAUX_QS, "notify-send": FAUX_NOTIFY}
        for nom in ("noctalia", "powerprofilesctl", "gdbus", "kitty"):
            outils[nom] = JOURNAL_SH
        for nom, code in outils.items():
            (self.bin / nom).write_text(code)
            (self.bin / nom).chmod(0o755)
        self.sessions = self.home / ".config/nc/sessions"
        self.sessions.mkdir(parents=True)
        self.apercus = self.home / ".local/state/noctalia-config/sessions"
        self.clients()

    def retirer(self, *outils):
        for o in outils:
            (self.bin / o).unlink()

    def clients(self, *c):
        (self.home / "clients.json").write_text(json.dumps(list(c)))

    def ecrans(self, l=ECRANS):
        (self.home / "monitors.json").write_text(json.dumps(l))

    def lancer(self, *a, timeout=30):
        env = dict(HOME=str(self.home), PATH=self.path, NC_LANGUE="fr", NC_SESSION_DELAI="2", NC_SESSION_CALME="0.5",
                   XDG_RUNTIME_DIR=str(self.home))
        return subprocess.run([str(SCRIPT), *a], env=env, capture_output=True, text=True, timeout=timeout)

    def appels(self):
        f = self.home / "appels"
        return f.read_text() if f.exists() else ""

    def oublier(self):
        (self.home / "appels").unlink(missing_ok=True)

    def json(self):
        r = self.lancer("json")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(len(r.stdout.strip().splitlines()), 1, "une seule ligne")
        return json.loads(r.stdout)

    def session(self, nom="Dev"):
        return next(s for s in self.json()["sessions"] if s["nom"] == nom)

    def v1(self, nom="Dev"):
        """Une session écrite par l'ancienne version (1)."""
        dossier = self.home / "projet"
        dossier.mkdir(exist_ok=True)
        d = {"version": 1, "nom": nom, "date": 1761153605, "fenetres": [
            {"classe": "kitty", "titre": "nvim", "bureau": 1, "ecran": 0, "flottant": False, "position": [0, 0],
             "taille": [800, 1000], "plein_ecran": 0,
             "terminal": {"programme": "kitty", "dossier": str(dossier), "commande": ["nvim", "notes du jour.md"]}},
            {"classe": "firefox", "titre": "Firefox", "bureau": 1, "ecran": 0, "flottant": False, "position": [800, 0],
             "taille": [800, 1000], "plein_ecran": 0, "appli": "firefox"},
            {"classe": "discord", "titre": "Discord", "bureau": 3, "ecran": 0, "flottant": True, "position": [100, 100],
             "taille": [400, 300], "plein_ecran": 2, "appli": "discord"}]}
        f = self.sessions / f"{nom}.json"
        f.write_text(json.dumps(d))
        return f


class Format(Base):
    def test_v1_lue_telle_quelle_puis_reecrite_en_v2_a_la_premiere_modification(self):
        f = self.v1()
        avant = f.read_bytes()
        d = self.json()
        self.assertEqual(d["version"], 2)
        s = d["sessions"][0]
        self.assertEqual(list(s), CLES_SESSION, "format figé : ces clés, dans cet ordre")
        self.assertEqual(s["nom"], "Dev")
        self.assertRegex(s["date"], r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d$")
        self.assertEqual((s["nb_fenetres"], s["applis"]), (3, ["kitty", "firefox", "discord"]))
        self.assertEqual({k: s[k] for k in CLES_SESSION[4:14]},
                         dict(icone=None, couleur=None, fond=None, profil="garder", npd=False, demarrage=False,
                              fermer_autres="non", raccourci=None, bureaux_noms={}, apercu=None))
        self.assertEqual((s["tranche"], s["tranche_etroite"]), (None, None))
        for e in s["fenetres"]:
            self.assertEqual(list(e), CLES_FENETRE)
        k, ff, dc = s["fenetres"]
        self.assertEqual(k["terminal"], {"programme": "kitty", "dossier": str(self.home / "projet"), "commande": "nvim 'notes du jour.md'"})
        self.assertIsNone(ff["terminal"])
        self.assertEqual((dc["plein_ecran"], dc["flottant"], dc["inclure"], dc["ecran"]), (True, True, True, "0"))
        self.assertEqual(f.read_bytes(), avant, "lue, pas réécrite")
        # Liste --json : inchangée (Spotlight, nc-reglages)
        l = json.loads(self.lancer("liste", "--json").stdout)
        self.assertEqual(l, [{"nom": "Dev", "fenetres": 3, "date": 1761153605, "applis": ["discord", "firefox", "kitty"]}])
        # La première modification la réécrit en version 2, privée, sans rien perdre
        r = self.lancer("modifier", "Dev", "couleur", "primary")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(len(r.stdout.strip().splitlines()), 1)
        v2 = json.loads(f.read_text())
        self.assertEqual(v2["version"], 2)
        self.assertEqual(v2["couleur"], "primary")
        self.assertTrue(all(e["inclure"] for e in v2["fenetres"]))
        self.assertEqual(v2["fenetres"][0]["terminal"]["commande"], ["nvim", "notes du jour.md"])
        self.assertIn("schema", v2, "le schéma est gardé dans le fichier")
        self.assertEqual(f.stat().st_mode & 0o777, 0o600)
        self.assertEqual(self.session()["couleur"], "primary")

    def test_sans_session(self):
        self.assertEqual(self.json(), {"version": 2, "sessions": []})

    def test_schema_normalise_deux_ecrans_deux_bureaux(self):
        self.ecrans()
        self.clients(client("0xa", "kitty", 1, at=(0, 0), taille=(800, 1000), ecran=0),
                     client("0xb", "firefox", 1, at=(800, 0), taille=(800, 500), ecran=0),
                     client("0xc", "gimp", 2, at=(10, 10), taille=(100, 100), ecran=0, fullscreen=2),
                     client("0xd", "discord", 3, at=(2080, 270), taille=(960, 540), ecran=1))
        r = self.lancer("enregistrer", "Dev")
        self.assertEqual(r.returncode, 0, r.stderr)
        s = self.session()
        self.assertEqual([(g["ecran"], g["bureau"], g["largeur"], g["hauteur"]) for g in s["schema"]],
                         [("eDP-1", 1, 1600, 1000), ("eDP-1", 2, 1600, 1000), ("DP-1", 3, 1920, 1080)],
                         "taille logique : 2560 × 1600 à l'échelle 1,6")
        rects = [[(x["x"], x["y"], x["w"], x["h"], x["classe"]) for x in g["rects"]] for g in s["schema"]]
        self.assertEqual(rects, [[(0, 0, 0.5, 1, "kitty"), (0.5, 0, 0.5, 0.5, "firefox")],
                                 [(0, 0, 1, 1, "gimp")],
                                 [(0.25, 0.25, 0.5, 0.5, "discord")]])
        self.assertEqual([e["ecran"] for e in s["fenetres"]], ["eDP-1", "eDP-1", "eDP-1", "DP-1"])
        f = json.loads((self.sessions / "Dev.json").read_text())
        self.assertEqual(f["schema"], s["schema"])
        # Une fenêtre exclue sort du schéma, des applis et du compte
        self.assertEqual(self.lancer("modifier", "Dev", "fenetre.1.inclure", "non").returncode, 0)
        s = self.session()
        self.assertEqual([x["classe"] for x in s["schema"][0]["rects"]], ["kitty"])
        self.assertEqual((s["nb_fenetres"], s["applis"]), (3, ["kitty", "gimp", "discord"]))
        self.assertFalse(s["fenetres"][1]["inclure"])


class Modifier(Base):
    def setUp(self):
        super().setUp()
        self.f = self.v1()

    def ok(self, cle, valeur, champ=None, attendu=None):
        r = self.lancer("modifier", "Dev", cle, valeur)
        self.assertEqual(r.returncode, 0, f"{cle}={valeur!r} : {r.stderr}")
        if champ:
            self.assertEqual(self.session()[champ], attendu, f"{cle}={valeur!r}")

    def refus(self, cle, valeur, nom="Dev"):
        avant = self.f.read_bytes()
        r = self.lancer("modifier", nom, cle, valeur)
        self.assertEqual(r.returncode, 1, f"{cle}={valeur!r} aurait dû être refusé")
        self.assertTrue(r.stderr.strip(), f"{cle}={valeur!r} : message sur stderr")
        self.assertEqual(r.stdout, "")
        self.assertEqual(self.f.read_bytes(), avant, f"{cle}={valeur!r} : rien d'écrit")
        self.assertNotIn("notify-send", self.appels(), "pas de notification pour le carrousel")

    def test_chaque_cle_valide(self):
        fond = self.home / "fond.jpg"
        fond.write_bytes(b"jpg")
        self.ok("icone", "code", "icone", "code")
        self.ok("couleur", "#A1B2C3", "couleur", "#a1b2c3")
        self.ok("couleur", "tertiary", "couleur", "tertiary")
        self.ok("fond", str(fond), "fond", str(fond))
        self.ok("profil", "power-saver", "profil", "power-saver")
        self.ok("npd", "oui", "npd", True)
        self.ok("fermer_autres", "demander", "fermer_autres", "demander")
        self.ok("bureau.1.nom", "Code", "bureaux_noms", {"1": "Code"})
        self.ok("bureau.2.nom", "Web", "bureaux_noms", {"1": "Code", "2": "Web"})
        self.ok("bureau.1.nom", "", "bureaux_noms", {"2": "Web"})
        self.ok("fenetre.2.inclure", "non", "nb_fenetres", 2)
        dossier = self.home / "autre"
        dossier.mkdir()
        self.ok("fenetre.0.dossier", str(dossier))
        self.ok("fenetre.0.commande", "htop -d 5")
        t = self.session()["fenetres"][0]["terminal"]
        self.assertEqual((t["dossier"], t["commande"]), (str(dossier), "htop -d 5"))
        self.ok("fenetre.0.commande", "")
        self.assertIsNone(self.session()["fenetres"][0]["terminal"]["commande"])
        self.ok("zones.1", json.dumps({"sens": "v", "r": 0.6, "a": {"f": 0}, "b": {"f": 1}}))
        self.assertEqual(json.loads(self.f.read_text())["zones"], {"1": {"sens": "v", "r": 0.6, "a": {"f": 0}, "b": {"f": 1}}})
        # Démarrage : le réglage SESSION_DEMARRAGE, que nc-session demarrage suit
        self.ok("demarrage", "oui", "demarrage", True)
        self.assertIn("nc-reglages set SESSION_DEMARRAGE Dev", self.appels())
        self.ok("demarrage", "non", "demarrage", False)
        self.assertIn("nc-reglages set SESSION_DEMARRAGE aucune", self.appels())
        # Raccourci : la forme de nc-raccourci, ajouté parmi tes raccourcis
        self.ok("raccourci", "super + alt + 1", "raccourci", "Super+Alt+1")
        self.assertIn("nc-raccourci ajoute Super+Alt+1 nc-session ouvrir Dev Session « Dev »", self.appels())
        self.ok("raccourci", "Ctrl+Maj+F5", "raccourci", "Ctrl+Maj+F5")
        a = self.appels()
        self.assertLess(a.index("nc-raccourci retire Super+Alt+1"), a.index("nc-raccourci ajoute Ctrl+Maj+F5"))
        # Vide : remise à défaut
        for cle, champ, defaut in (("icone", "icone", None), ("couleur", "couleur", None), ("fond", "fond", None),
                                   ("profil", "profil", "garder"), ("npd", "npd", False), ("fermer_autres", "fermer_autres", "non"),
                                   ("raccourci", "raccourci", None), ("fenetre.2.inclure", "nb_fenetres", 3)):
            self.ok(cle, "", champ, defaut)
        self.assertIn("nc-raccourci retire Ctrl+Maj+F5", self.appels())
        # VALEUR omise : comme vide
        self.assertEqual(self.lancer("modifier", "Dev", "icone").returncode, 0)

    def test_chaque_cle_refusee(self):
        texte = self.home / "notes.txt"
        texte.write_text("x")
        for cle, valeur in (("icone", "Code!"), ("icone", "a b"), ("couleur", "rouge"), ("couleur", "#12345"),
                            ("couleur", "#1234567"), ("fond", "/nexiste/pas.jpg"), ("fond", str(texte)),
                            ("fond", "fond.jpg"), ("profil", "turbo"), ("npd", "peut-être"), ("demarrage", "2"),
                            ("fermer_autres", "toujours"), ("raccourci", "Hyper+1"), ("raccourci", "Super+Ω"),
                            ("raccourci", "A"), ("raccourci", "Super+Alt+9"), ("bureau.0.nom", "X"),
                            ("bureau.1.nom", "a]]b"), ("bureau.1.nom", "x" * 33), ("bureau.x.nom", "X"),
                            ("fenetre.3.inclure", "non"), ("fenetre.-1.inclure", "non"), ("fenetre.0.inclure", "bof"),
                            ("fenetre.1.dossier", "/tmp"), ("fenetre.1.commande", "firefox"),
                            ("fenetre.0.dossier", "/nexiste/pas"), ("fenetre.0.dossier", "relatif"),
                            ("fenetre.0.commande", "nvim 'a"), ("zones.1", '{"f": 7}'), ("zones.1", "pas du json"),
                            ("zones.1", '{"sens": "x", "a": {"f": 0}, "b": {"f": 1}}'),
                            ("zones.1", '{"sens": "v", "r": 0.6, "a": {"f": 0}, "b": {"f": 0}}'),
                            ("inconnue", "1")):
            self.refus(cle, valeur)
        self.assertIn("déjà pris", self.lancer("modifier", "Dev", "raccourci", "Super+Alt+9").stderr)
        r = self.lancer("modifier", "Rien", "icone", "code")
        self.assertEqual(r.returncode, 1)
        self.assertIn("Session inconnue", r.stderr)
        self.assertFalse((self.sessions / "Rien.json").exists())


class RenommerDupliquer(Base):
    def test_renommer_et_dupliquer_avec_l_apercu(self):
        self.v1()
        self.apercus.mkdir(parents=True)
        png = self.apercus / "Dev.png"
        png.write_bytes(b"png")
        png.chmod(0o600)
        self.assertEqual(self.lancer("modifier", "Dev", "raccourci", "Super+Alt+1").returncode, 0)
        self.assertEqual(self.lancer("modifier", "Dev", "demarrage", "oui").returncode, 0)
        self.oublier()
        r = self.lancer("renommer", "Dev", "Projet")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout.strip(), "Session « Dev » renommée « Projet ».")
        self.assertFalse((self.sessions / "Dev.json").exists())
        self.assertFalse(png.exists())
        self.assertEqual((self.apercus / "Projet.png").read_bytes(), b"png")
        s = self.session("Projet")
        self.assertEqual((s["apercu"], s["raccourci"], s["demarrage"]), (str(self.apercus / "Projet.png"), "Super+Alt+1", True))
        self.assertEqual(json.loads((self.sessions / "Projet.json").read_text())["nom"], "Projet")
        a = self.appels()
        self.assertIn("nc-raccourci ajoute Super+Alt+1 nc-session ouvrir Projet", a, "le raccourci ouvre le nouveau nom")
        self.assertIn("nc-reglages set SESSION_DEMARRAGE Projet", a)
        # Dupliquer : tout copié, aperçu compris (privé), sauf le raccourci
        r = self.lancer("dupliquer", "Projet", "Copie")
        self.assertEqual(r.returncode, 0, r.stderr)
        c, p = self.session("Copie"), self.session("Projet")
        self.assertEqual((c["raccourci"], c["demarrage"], c["apercu"]), (None, False, str(self.apercus / "Copie.png")))
        self.assertEqual(c["fenetres"], p["fenetres"])
        self.assertEqual((self.apercus / "Copie.png").stat().st_mode & 0o777, 0o600)
        self.assertTrue((self.apercus / "Projet.png").exists())
        # Refus : nom pris, session absente, nom invalide, même nom
        for a in (("renommer", "Projet", "Copie"), ("dupliquer", "Projet", "Copie"), ("renommer", "Rien", "X"),
                  ("dupliquer", "Rien", "X"), ("renommer", "Projet", "../x"), ("renommer", "Projet", "Projet")):
            r = self.lancer(*a)
            self.assertEqual(r.returncode, 1, a)
            self.assertTrue(r.stderr.strip(), a)
        self.assertEqual(sorted(f.name for f in self.sessions.iterdir()), ["Copie.json", "Projet.json"])

    def test_supprimer_efface_l_apercu_et_le_raccourci(self):
        self.v1()
        self.apercus.mkdir(parents=True)
        (self.apercus / "Dev.png").write_bytes(b"png")
        self.lancer("modifier", "Dev", "raccourci", "Super+Alt+1")
        r = self.lancer("supprimer", "Dev")
        self.assertEqual((r.returncode, r.stdout.strip()), (0, "Session « Dev » supprimée."))
        self.assertFalse((self.apercus / "Dev.png").exists())
        self.assertIn("nc-raccourci retire Super+Alt+1", self.appels())


    def test_anciennes_tranches_effacees(self):
        # Tranches inclinées d'une version précédente : plus jamais produites ni montrées, effacées dès que la session
        # est renommée, dupliquée, réenregistrée ou supprimée ; « tranche » et « tranche_etroite » restent null
        self.v1()
        self.apercus.mkdir(parents=True)
        for suffixe in (".png", ".tranche.png", ".tranche-etroite.png"):
            (self.apercus / ("Dev" + suffixe)).write_bytes(suffixe.encode())
            (self.apercus / ("Dev" + suffixe)).chmod(0o600)
        self.assertEqual((self.session()["tranche"], self.session()["tranche_etroite"]), (None, None))
        self.assertEqual(self.lancer("renommer", "Dev", "Projet").returncode, 0)
        self.assertEqual(sorted(f.name for f in self.apercus.iterdir()), ["Projet.png"])
        self.assertEqual((self.apercus / "Projet.png").read_bytes(), b".png")
        (self.apercus / "Projet.tranche.png").write_bytes(b"x")
        self.assertEqual(self.lancer("dupliquer", "Projet", "Copie").returncode, 0)
        self.assertEqual(sorted(f.name for f in self.apercus.iterdir()), ["Copie.png", "Projet.png"])
        s = self.session("Copie")
        self.assertEqual((s["apercu"], s["tranche"], s["tranche_etroite"]), (str(self.apercus / "Copie.png"), None, None))
        (self.apercus / "Copie.tranche-etroite.png").write_bytes(b"x")
        self.assertEqual(self.lancer("supprimer", "Copie").returncode, 0)
        self.assertEqual(sorted(f.name for f in self.apercus.iterdir()), ["Projet.png"])


class Apercu(Base):
    def setUp(self):
        super().setUp()
        self.ecrans()
        self.clients(client("0xa", "firefox", 1, ecran=0))

    def test_grim_sur_l_ecran_actif(self):
        r = self.lancer("enregistrer", "Dev")
        self.assertEqual(r.returncode, 0, r.stderr)
        # DP-1 (1920 x 1080, échelle 1, sans zone réservée) : l'écran entier, réduit à la carte de 883 points
        self.assertRegex(self.appels(), r"grim -g 1600,0 1920x1080 -s 0\.459896 -t png \S+\n")
        png = self.apercus / "Dev.png"
        self.assertEqual(png.read_bytes()[:4], b"\x89PNG")
        self.assertEqual(png.stat().st_mode & 0o777, 0o600)
        self.assertEqual(self.apercus.stat().st_mode & 0o777, 0o700)
        self.assertEqual(self.session()["apercu"], str(png))
        self.assertEqual(list(self.apercus.iterdir()), [png], "pas de fichier temporaire laissé")
        # apercu NOM : refait
        self.oublier()
        r = self.lancer("apercu", "Dev")
        self.assertEqual((r.returncode, r.stdout.strip()), (0, "Aperçu de « Dev » refait."))
        self.assertIn("grim -g 1600,0 1920x1080", self.appels())
        self.assertEqual(self.lancer("apercu", "Rien").returncode, 1)

    def test_sans_grim_le_schema_seul(self):
        self.retirer("grim")
        r = self.lancer("enregistrer", "Dev")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("(schéma seulement)", r.stdout)
        s = self.session()
        self.assertIsNone(s["apercu"])
        self.assertEqual(s["schema"][0]["rects"][0]["classe"], "firefox")
        r = self.lancer("apercu", "Dev")
        self.assertEqual(r.returncode, 0)
        self.assertIn("schéma seulement", r.stdout)

    def test_capture_desactivee(self):
        self.lancer("enregistrer", "Dev")
        self.assertTrue((self.apercus / "Dev.png").exists())
        (self.home / ".config/nc/reglages.conf").write_text("SESSIONS_CAPTURE=non\n")
        self.oublier()
        self.assertEqual(self.lancer("enregistrer", "Dev").returncode, 0)
        self.assertEqual(self.lancer("apercu", "Dev").returncode, 0)
        self.assertNotIn("grim", self.appels(), "pas de capture")
        self.assertFalse((self.apercus / "Dev.png").exists(), "l'ancienne capture effacée")
        self.assertIsNone(self.session()["apercu"])

    def test_sous_la_barre_a_la_taille_de_la_carte(self):
        # 1600 x 1000 points (2560 x 1600 à l'échelle 1,6), barre de 42 en haut : la zone utile recadrée au ratio de
        # l'écran (1533 x 958 à partir de 33,42), réduite par grim à 1178 pixels de large (la carte de 736 points)
        self.ecrans([{"id": 0, "name": "eDP-1", "x": 0, "y": 0, "width": 2560, "height": 1600, "scale": 1.6, "transform": 0,
                      "reserved": [0, 42, 0, 0], "focused": True}])
        r = self.lancer("enregistrer", "Dev")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertRegex(self.appels(), r"(?m)^grim -g 33,42 1533x958 -s 0\.768428 -t png \S+$")
        self.assertNotIn("-o ", self.appels())

    def test_grim_avant_la_notification(self):
        # La bannière de l'île ne doit pas être dans l'aperçu : la notification « enregistrée » vient après grim
        r = self.lancer("enregistrer", "Dev")
        self.assertEqual(r.returncode, 0, r.stderr)
        for _ in range(50):
            if "notify-send" in self.appels():
                break
            time.sleep(0.05)
        a = self.appels()
        self.assertIn("notify-send", a)
        self.assertLess(a.index("grim "), a.index("notify-send"), a)

    def test_aucun_appel_a_nc_carousel_thumbs(self):
        # Plus de tranches : nc-carousel-thumbs n'est jamais lancé pour une session, avec ou sans capture
        (self.bin / "nc-carousel-thumbs").write_text(JOURNAL_SH)
        (self.bin / "nc-carousel-thumbs").chmod(0o755)
        for capture in ("oui", "non"):
            (self.home / ".config/nc/reglages.conf").write_text(f"SESSIONS_CAPTURE={capture}\n")
            self.assertEqual(self.lancer("enregistrer", "Dev").returncode, 0)
            self.assertEqual(self.lancer("modifier", "Dev", "couleur", "#ff0000").returncode, 0)
            self.assertEqual(self.lancer("modifier", "Dev", "fenetre.0.inclure", "non").returncode, 0)
            self.assertEqual(self.lancer("apercu", "Dev").returncode, 0)
            s = self.session()
            self.assertEqual((s["tranche"], s["tranche_etroite"]), (None, None))
        self.assertNotIn("nc-carousel-thumbs", self.appels())
        self.assertFalse([f for f in self.apercus.iterdir() if "tranche" in f.name] if self.apercus.exists() else [])

    def test_reenregistrer_garde_la_personnalisation(self):
        self.lancer("enregistrer", "Dev")
        self.lancer("modifier", "Dev", "icone", "code")
        self.lancer("modifier", "Dev", "zones.1", '{"f": 0}')
        self.clients(client("0xa", "firefox", 1), client("0xb", "gimp", 2))
        self.assertEqual(self.lancer("enregistrer", "Dev").returncode, 0)
        d = json.loads((self.sessions / "Dev.json").read_text())
        self.assertEqual((d["icone"], d["zones"], len(d["fenetres"])), ("code", {}, 2))


class Ouvrir(Base):
    def setUp(self):
        super().setUp()
        self.fond = self.home / "fond.png"
        self.fond.write_bytes(b"png")
        self.projet = self.home / "projet"
        self.projet.mkdir()
        d = {"version": 2, "nom": "Dev", "date": 1, "fond": str(self.fond), "profil": "performance", "npd": True,
             "fermer_autres": "oui", "bureaux_noms": {"1": "Code", "2": "Web"},
             "zones": {"1": {"sens": "v", "r": 0.6, "a": {"f": 0}, "b": {"f": 1}}, "4": {"f": 2}},
             "fenetres": [
                 {"classe": "kitty", "bureau": 1, "terminal": {"programme": "kitty", "dossier": str(self.projet), "commande": None}},
                 {"classe": "firefox", "bureau": 1, "appli": "firefox"},
                 {"classe": "discord", "bureau": 4, "appli": "discord", "inclure": False}]}
        (self.sessions / "Dev.json").write_text(json.dumps(d))
        (self.home / "zones_dispo").touch()
        # Un terminal occupé (un programme tourne dans son shell) et un terminal au repos
        occupe = subprocess.Popen(["sh", "-c", "sh -c 'sleep 30; :'; :"])
        repos = subprocess.Popen(["sleep", "30"])
        for p in (occupe, repos):
            self.addCleanup(p.wait)
            self.addCleanup(p.kill)
        time.sleep(0.3)
        self.autres = [client("0x9a", "gimp", 2), client("0x0c", "foot", 3, pid=occupe.pid),
                       client("0x2e", "alacritty", 3, pid=repos.pid), client("0xd", "dropterm", -98),
                       client("0x9b", "mpv", 2, pinned=True), client("0x5c", "org.quickshell", 1)]
        self.clients(client("0x1c", "kitty", 1), client("0xf", "firefox", 5), *self.autres)

    def ouvrir(self):
        r = self.lancer("ouvrir", "Dev")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(len(r.stdout.strip().splitlines()), 1)
        return self.appels()

    def test_toutes_les_etapes_dans_l_ordre(self):
        a = self.ouvrir()
        etapes = [f"noctalia msg wallpaper-set {self.fond}", "powerprofilesctl set performance",
                  "qs -c nc-ile ipc call ile concentrationRegler true", "noctalia msg notification-dnd-set on",
                  "hyprctl dispatch hl.dsp.window.close({ window = 'address:0x9a' })",
                  "hyprctl dispatch hl.dsp.window.move({ workspace = 1, follow = false, window = 'address:0xf' })",
                  "hyprctl dispatch hl.dsp.workspace.rename({ workspace = 1, name = [[Code]] })",
                  "hyprctl dispatch hl.dsp.workspace.rename({ workspace = 2, name = [[Web]] })",
                  "hyprctl eval if not (nc and nc.zones_dispo) then error('absent') end",
                  'hyprctl eval nc.zones_poser(1, { sens = "v", r = 0.6, a = { f = "0x1c" }, b = { f = "0xf" } })']
        pos = [a.find(e) for e in etapes]
        self.assertNotIn(-1, pos, "\n".join(e for e, p in zip(etapes, pos) if p < 0) + "\n---\n" + a)
        self.assertEqual(pos, sorted(pos), "dans l'ordre :\n" + a)
        # Fermées : gimp, et le terminal au repos ; gardées : le terminal occupé, le terminal déroulant, l'épinglée,
        # le bureau lui-même, et les fenêtres reprises par la session
        fermees = sorted(l.split("address:")[1].split("'")[0] for l in a.splitlines() if "window.close" in l)
        self.assertEqual(fermees, ["0x2e", "0x9a"])
        # L'exclue n'est ni lancée ni dans les zones (la zone du bureau 4 n'a plus de fenêtre : pas posée)
        self.assertNotIn("discord", a)
        self.assertNotIn("zones_poser(4", a)
        self.assertNotIn("gdbus", a, "powerprofilesctl a suffi")
        self.assertNotIn("kitty --directory", a, "le terminal du bureau 1 est repris")

    def test_variantes_des_outils(self):
        # L'île tourne : sa concentration, pas celle de Noctalia ; sans powerprofilesctl : le service par gdbus ;
        # zones non chargées dans Hyprland : pas posées
        (self.home / "ile").touch()
        (self.home / "zones_dispo").unlink()
        self.retirer("powerprofilesctl")
        a = self.ouvrir()
        self.assertIn("qs -c nc-ile ipc call ile concentrationRegler true", a)
        self.assertNotIn("notification-dnd-set", a)
        self.assertIn("gdbus call --system --dest net.hadess.PowerProfiles --object-path /net/hadess/PowerProfiles "
                      "--method org.freedesktop.DBus.Properties.Set net.hadess.PowerProfiles ActiveProfile <'performance'>", a)
        self.assertNotIn("zones_poser", a)

    def test_sans_aucun_outil_les_etapes_sont_sautees(self):
        self.retirer("noctalia", "powerprofilesctl", "gdbus", "qs", "notify-send")
        a = self.ouvrir()
        for outil in ("noctalia", "powerprofilesctl", "gdbus", "qs "):
            self.assertNotIn(outil, a)
        self.assertIn("workspace.rename", a)

    def test_rien_quand_rien_n_est_demande(self):
        d = json.loads((self.sessions / "Dev.json").read_text())
        for k in ("fond", "profil", "npd", "fermer_autres", "bureaux_noms", "zones"):
            d.pop(k)
        (self.sessions / "Dev.json").write_text(json.dumps(d))
        a = self.ouvrir()
        for mot in ("noctalia", "powerprofilesctl", "gdbus", "qs ", "window.close", "rename", "zones", "notify-send"):
            self.assertNotIn(mot, a)

    def test_fermer_les_autres_en_demandant(self):
        d = json.loads((self.sessions / "Dev.json").read_text())
        d["fermer_autres"] = "demander"
        (self.sessions / "Dev.json").write_text(json.dumps(d))
        # Sans le bouton : rien de fermé
        a = self.ouvrir()
        for _ in range(50):
            if "notify-send" in self.appels():
                break
            time.sleep(0.1)
        time.sleep(0.3)
        a = self.appels()
        self.assertIn("notify-send -a Sessions -i view-grid -A fermer=Fermer les autres -- Session « Dev »", a)
        self.assertNotIn("window.close", a)
        # Avec le bouton : les mêmes que « oui »
        self.oublier()
        (self.home / "bouton").write_text("fermer\n")
        self.clients(client("0x1c", "kitty", 1), client("0xf", "firefox", 5), *self.autres)
        self.ouvrir()
        for _ in range(50):
            if "window.close" in self.appels():
                break
            time.sleep(0.1)
        time.sleep(0.3)
        fermees = sorted(l.split("address:")[1].split("'")[0] for l in self.appels().splitlines() if "window.close" in l)
        self.assertEqual(fermees, ["0x2e", "0x9a"])


if __name__ == "__main__":
    unittest.main()
