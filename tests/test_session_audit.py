"""nc-session, correctifs de l'audit : « Fermer les autres ? » figée (et annulée si une autre session s'ouvre), secrets
des lignes de commande, aucune capture ni titre quand un gestionnaire de mots de passe ou une navigation privée est
visible, dossier de travail gardé et rouvert, commande relative, noms de bureau avec ], zone à NaN, XDG_RUNTIME_DIR absent,
wezterm. Même cadre que test_sessions_v2 : faux HOME, faux hyprctl, faux outils."""
import importlib.machinery
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_sessions_v2 import Base, ECRANS, FAUX_HYPRCTL, JOURNAL_SH, SCRIPT, client  # noqa: E402

# Le module est chargé avec un faux HOME : il lit Path.home() dès l'import
_RACINE = tempfile.TemporaryDirectory(prefix="nc-session-audit-")
_ENV = {k: os.environ.get(k) for k in ("HOME", "XDG_RUNTIME_DIR", "XDG_STATE_HOME", "XDG_CONFIG_HOME", "XDG_DATA_HOME", "XDG_CACHE_HOME")}


def charger():
    r = Path(_RACINE.name)
    (r / "run").mkdir(mode=0o700, exist_ok=True)
    os.environ.update(HOME=str(r), XDG_RUNTIME_DIR=str(r / "run"), XDG_STATE_HOME=str(r / "state"),
                      XDG_CONFIG_HOME=str(r / "config"), XDG_DATA_HOME=str(r / "data"), XDG_CACHE_HOME=str(r / "cache"))
    try:
        loader = importlib.machinery.SourceFileLoader("nc_session_audit", str(SCRIPT))
        spec = importlib.util.spec_from_loader("nc_session_audit", loader)
        m = importlib.util.module_from_spec(spec)
        loader.exec_module(m)
        return m
    finally:
        for k, v in _ENV.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


def tearDownModule():
    _RACINE.cleanup()


class Unites(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.m = charger()

    def test_secrets_de_la_ligne_de_commande(self):
        m = self.m
        for cmd in (["app", "-p", "hunter2"], ["app", "--password=hunter2"], ["app", "--pass", "x"], ["app", "-p=x"],
                    ["curl", "--header", "Authorization: Bearer abc"], ["curl", "-H", "authorization: x"],
                    ["app", "--apikey", "abc"] if False else ["app", "--api-key=abc"], ["app", "apikey=abc"],
                    ["app", "--key=abc"], ["app", "key=abc"], ["app", "--secret", "x"], ["app", "--cookie", "a=b"],
                    ["app", "https://u:pw@exemple.org/x"], ["app", "https://exemple.org/?token=abc"],
                    ["app", "https://exemple.org/?a=1&access_token=abc"], ["app", "https://exemple.org/?a=1&key=abc"]):
            self.assertTrue(m.secret_dans(cmd), cmd)
        for cmd in (["app", "auth.lua"], ["app", "https://exemple.org/page?a=1"], ["app", "monkey=1"], ["app", "a@b.fr"],
                    ["app", "--profile", "travail"]):
            self.assertFalse(m.secret_dans(cmd), cmd)
        self.assertFalse(m.secret_dans(["nvim", "-p", "a.txt", "b.txt"], avec_p=False), "nvim -p ouvre des onglets")

    def test_commande_sure_garde_les_chemins_existants(self):
        m = self.m
        d = Path(_RACINE.name)
        (d / "notes.txt").write_text("x")
        self.assertEqual(m.commande_sure(["app", "--profile", "travail"], str(d)), ["app", "--profile", "travail"])
        self.assertEqual(m.commande_sure(["app", "-p", "hunter2", "notes.txt", "absent.txt", "-x", str(d)], str(d)),
                         ["app", "notes.txt", str(d)])
        self.assertEqual(m.commande_sure(["app", "--header", "Authorization: Bearer abc"], str(d)), ["app"])

    def test_texte_lua_a_crochets_longs(self):
        m = self.m
        for texte, attendu in (("Code", "[[Code]]"), ("Dev]", "[=[Dev]]=]"), ("a]]b", "[=[a]]b]=]"),
                               ("a]]=]b", "[==[a]]=]b]==]"), ("]", "[=[]]=]")):
            self.assertEqual(m.lua_texte(texte), attendu)

    def test_zone_a_nan_ignoree(self):
        m = self.m
        self.assertIsNone(m.boite({"position": [float("nan"), 0], "taille": [10, 10]}))
        self.assertIsNone(m.boite({"position": [0, 0], "taille": [float("inf"), 10]}))
        s = {"ecrans": {"A": {"x": 0, "y": 0, "largeur": float("nan"), "hauteur": 100}},
             "fenetres": [{"classe": "x", "ecran": "A", "bureau": 1, "position": [10, 10], "taille": [50, 50]},
                          {"classe": "y", "ecran": "A", "bureau": 1, "position": [float("nan"), 0], "taille": [5, 5]}]}
        rects = m.schema(s)[0]["rects"]
        self.assertEqual([r["classe"] for r in rects], ["x"])


def hyprctl_avec_erreur_de_nom():
    return FAUX_HYPRCTL.replace("    # Une fenêtre fermée disparaît",
                                '    if "workspace.rename" in a[1] and (H / "erreur").exists(): print("error: <name> expected")\n'
                                "    # Une fenêtre fermée disparaît")


class Audit(Base):
    def env(self, **plus):
        e = dict(HOME=str(self.home), PATH=self.path, NC_LANGUE="fr", NC_SESSION_DELAI="1", NC_SESSION_CALME="0.5",
                 XDG_RUNTIME_DIR=str(self.home))
        e.update(plus)
        return e

    def ecrire(self, fenetres, **plus):
        d = {"version": 2, "nom": "Dev", "date": 1, "fenetres": fenetres}
        d.update(plus)
        (self.sessions / "Dev.json").write_text(json.dumps(d))

    # 1. Fermer les autres
    def preparer_demande(self):
        self.ecrire([{"classe": "firefox", "bureau": 1, "appli": "firefox"}], fermer_autres="demander")
        self.clients(client("0xf", "firefox", 1), client("0x9a", "gimp", 2))
        # Pendant que la notification attend, une autre session s'ouvre : B apporte 0xb1 (et un clic « fermer »)
        (self.bin / "notify-send").write_text(
            JOURNAL_SH + 'python3 - "$H" <<\'PY\'\nimport json, sys\nfrom pathlib import Path\nH = Path(sys.argv[1])\n'
            'c = json.loads((H / "clients.json").read_text())\n'
            'c.append({"address": "0xb1", "class": "mpv", "title": "B", "mapped": True, "workspace": {"id": 2}, "pid": 999999})\n'
            'for x in c:\n    if x["address"] == "0xf": x["class"] = "autre"\n'
            '(H / "clients.json").write_text(json.dumps(c))\nPY\n'
            'if [ -e "$H/autre-session" ]; then echo autre > "$H/nc-session-derniere"; fi\necho fermer\n')

    def fermer_autres(self):
        r = subprocess.run([str(SCRIPT), "fermer-autres", "Dev"], env=self.env(NC_SESSION_JETON="A"), capture_output=True,
                           text=True, timeout=30)
        self.assertEqual(r.returncode, 0, r.stderr)
        return sorted(l.split("address:")[1].split("'")[0] for l in self.appels().splitlines() if "window.close" in l)

    def test_fermer_autres_liste_figee(self):
        self.preparer_demande()
        (self.home / "nc-session-derniere").write_text("A")
        # B s'est ouverte (0xb1) et 0xf a changé de classe : seule 0x9a, qui existe encore avec sa classe, est fermée
        self.assertEqual(self.fermer_autres(), ["0x9a"])

    def test_fermer_autres_annulee_si_une_autre_session_s_ouvre(self):
        self.preparer_demande()
        (self.home / "nc-session-derniere").write_text("A")
        (self.home / "autre-session").touch()
        self.assertEqual(self.fermer_autres(), [])
        self.assertEqual((self.home / "nc-session-derniere").read_text().strip(), "autre")

    def test_ouvrir_note_sa_marque(self):
        self.ecrire([{"classe": "firefox", "bureau": 1, "appli": "firefox"}])
        self.clients(client("0xf", "firefox", 1))
        self.assertEqual(self.lancer("ouvrir", "Dev").returncode, 0)
        self.assertRegex((self.home / "nc-session-derniere").read_text(), r"^\d+-\d+$")

    # 2 et 4. Secrets et dossier de travail à l'enregistrement
    def test_enregistrer_secrets_et_cwd(self):
        projet = self.home / "projet"
        projet.mkdir()
        (projet / "notes.txt").write_text("x")
        p = subprocess.Popen(["sh", "-c", "sleep 30; :", "_", "-p", "hunter2", "--header", "Authorization: Bearer abc",
                              "notes.txt"], cwd=projet)
        self.addCleanup(p.wait)
        self.addCleanup(p.kill)
        time.sleep(0.3)
        self.clients(client("0xa", "inconnue", 1, pid=p.pid))
        r = self.lancer("enregistrer", "Dev")
        self.assertEqual(r.returncode, 0, r.stderr)
        brut = (self.sessions / "Dev.json").read_text()
        for secret in ("hunter2", "Bearer", "Authorization"):
            self.assertNotIn(secret, brut)
        e = json.loads(brut)["fenetres"][0]
        self.assertEqual(e["commande"], ["sh", "notes.txt"])
        self.assertEqual(e["cwd"], str(projet.resolve()))

    # 3. Aperçu : rien de sensible dans la capture
    def test_pas_de_capture_avec_un_gestionnaire_de_mots_de_passe_ou_une_navigation_privee(self):
        ecrans = [dict(ECRANS[1], activeWorkspace={"id": 1})]
        self.ecrans(ecrans)
        for sensible in (client("0xk", "org.keepassxc.KeePassXC", 1, at=(1700, 10), ecran=1),
                         client("0xp", "firefox", 1, at=(1700, 10), ecran=1, title="Site - Navigation privée"),
                         client("0xi", "chromium", 1, at=(1700, 10), ecran=1, title="Nouvel onglet - Incognito")):
            self.clients(client("0xa", "gimp", 1, at=(1700, 500), ecran=1), sensible)
            self.oublier()
            r = self.lancer("enregistrer", "Dev")
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertNotIn("grim", self.appels(), sensible["class"])
            self.assertFalse((self.apercus / "Dev.png").exists())
            self.assertIn("schéma seulement", r.stdout)
            titres = [e["titre"] for e in json.loads((self.sessions / "Dev.json").read_text())["fenetres"]]
            self.assertNotIn(sensible["title"], titres)
        # Le même gestionnaire, mais sur un autre bureau (non affiché) : capture normale
        self.clients(client("0xa", "gimp", 1, at=(1700, 500), ecran=1), client("0xk", "keepassxc", 2, at=(1700, 10), ecran=1))
        self.oublier()
        self.assertEqual(self.lancer("enregistrer", "Dev").returncode, 0)
        self.assertIn("grim", self.appels())

    # 4. Réouverture : dossier de travail, commande relative
    def test_reouverture_dossier_et_commande_relative(self):
        dossier = self.home / "travail"
        dossier.mkdir()
        note = self.home / "note"
        for chemin in (self.bin / "monappli", dossier / "x"):
            chemin.write_text(f'#!/bin/sh\necho "${{0##*/}} $PWD" >> "{note}"\n')
            chemin.chmod(0o755)
        self.ecrire([
            {"classe": "a", "bureau": 1, "commande": [str(self.bin / "monappli")], "cwd": str(dossier)},
            {"classe": "b", "bureau": 1, "commande": ["monappli"], "cwd": str(self.home / "disparu")},
            {"classe": "c", "bureau": 1, "commande": ["./x"], "cwd": str(dossier)},
            {"classe": "d", "bureau": 1, "commande": ["./absent"], "cwd": str(dossier)},
            {"classe": "e", "bureau": 1, "commande": ["inexistante-ici"], "cwd": str(dossier)}])
        r = self.lancer("ouvrir", "Dev")
        self.assertEqual(r.returncode, 0, r.stderr)
        lignes = sorted(note.read_text().splitlines())
        self.assertEqual(lignes, sorted([f"monappli {dossier.resolve()}", f"monappli {self.home.resolve()}", f"x {dossier.resolve()}"]))
        self.assertIn("d non rouverte : commande relative", r.stderr)
        self.assertIn("e non rouverte : inexistante-ici introuvable", r.stderr)
        self.assertNotIn("a non rouverte", r.stderr)

    # 6. Noms de bureau
    def test_nom_de_bureau_avec_crochet(self):
        self.ecrire([{"classe": "firefox", "bureau": 1, "appli": "firefox"}],
                    bureaux_noms={"1": "Dev]", "2": "a]]=]b", "3": "Code"})
        self.clients(client("0xf", "firefox", 1))
        r = self.lancer("ouvrir", "Dev")
        self.assertEqual(r.returncode, 0, r.stderr)
        a = self.appels()
        self.assertIn("name = [=[Dev]]=] }", a)
        self.assertIn("name = [==[a]]=]b]==] }", a)
        self.assertIn("name = [[Code]] }", a)

    def test_erreur_d_hyprctl_signalee(self):
        (self.bin / "hyprctl").write_text(hyprctl_avec_erreur_de_nom())
        (self.home / "erreur").touch()
        self.ecrire([{"classe": "firefox", "bureau": 1, "appli": "firefox"}], bureaux_noms={"1": "Dev"})
        self.clients(client("0xf", "firefox", 1))
        r = self.lancer("ouvrir", "Dev")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("Bureau 1 : Hyprland a refusé son nom.", r.stderr)

    # 7. Zone à NaN
    def test_session_a_zone_nan(self):
        self.ecrire([{"classe": "a", "bureau": 1, "ecran": 0, "position": [float("nan"), 0], "taille": [10, 10]},
                     {"classe": "b", "bureau": 1, "ecran": 0, "position": [10, 10], "taille": [50, 50]}])
        s = self.session()
        self.assertEqual([r["classe"] for r in s["schema"][0]["rects"]], ["b"])

    # 8. Pas de XDG_RUNTIME_DIR
    def test_sans_xdg_runtime_dir(self):
        self.ecrire([{"classe": "firefox", "bureau": 1, "appli": "firefox"}])
        self.clients(client("0xf", "firefox", 1))
        e = self.env()
        del e["XDG_RUNTIME_DIR"]
        r = subprocess.run([str(SCRIPT), "ouvrir", "Dev"], env=e, capture_output=True, text=True, timeout=30)
        self.assertEqual(r.returncode, 1)
        self.assertIn("XDG_RUNTIME_DIR absent", r.stderr)
        self.assertNotIn("hyprctl", self.appels())

    # 9. wezterm : « wezterm start -- … »
    def test_wezterm_start(self):
        (self.bin / "wezterm").write_text(JOURNAL_SH)
        (self.bin / "wezterm").chmod(0o755)
        self.ecrire([{"classe": "org.wezfurlong.wezterm", "bureau": 1,
                      "terminal": {"programme": "wezterm", "dossier": str(self.home), "commande": ["nvim", "a.md"]}}])
        r = self.lancer("ouvrir", "Dev")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertRegex(self.appels(), r"wezterm start -- sh -c cd \S+; nvim a\.md; exec")
        self.assertNotIn("wezterm -e", self.appels())


if __name__ == "__main__":
    unittest.main()
