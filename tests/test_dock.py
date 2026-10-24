"""Applis épinglées au dock sans éditer de fichier (issue #16) : nc-dock (liste, epingler, retirer, monter, descendre),
joué dans un faux HOME avec un faux noctalia qui note ses appels (jamais le vrai HOME ni la vraie session). Vérifie que
seule la clé [dock] pinned change, écrite dans settings.toml (réglages de l'interface de Noctalia, qui priment, là où
écrit le menu « Épingler » de son dock) ou, sans lui, dans zz-dock.toml ; que config.toml (remplacé par les mises à
jour) n'est jamais touché, et que deux nc-dock lancés ensemble n'effacent rien.
Le config.toml du faux HOME vient du dépôt, seul @BROWSER@ rempli : nc-dock le lit sans jamais l'écrire.
Puis le Spotlight de l'île (clic droit et Alt + P sur une appli) et nc-reglages → Barre et dock."""
import importlib.machinery
import importlib.util
import json
import os
import re
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest import mock
import warnings

REPO = Path(__file__).resolve().parents[1]
NC_DOCK = REPO / "home/.local/bin/nc-dock"
QML = REPO / "home/.config/quickshell/nc-ile"
CONFIG = REPO / "home/.config/noctalia/config.toml"

DESKTOP = "[Desktop Entry]\nType=Application\nName={nom}\n{autre}Exec={exe}\n"


class Banc:
    """HOME temporaire : config.toml du dépôt (marqueurs remplis), quelques applis, un faux noctalia."""

    def __init__(self):
        self._tmp = tempfile.TemporaryDirectory(prefix="nc-dock-")
        r = self.r = Path(self._tmp.name)
        self.config = r / ".config/noctalia"
        self.config.mkdir(parents=True)
        self.etat = r / ".local/state/noctalia/settings.toml"
        self.etat.parent.mkdir(parents=True)
        texte = CONFIG.read_text(encoding="utf-8").replace("@BROWSER@", "firefox")
        (self.config / "config.toml").write_text(texte, encoding="utf-8")
        self.origine = texte
        apps = r / ".local/share/applications"
        (apps / "kde").mkdir(parents=True)
        for ident, nom, autre in (("kitty", "Kitty", ""), ("firefox", "Firefox", ""), ("gimp", "GIMP", ""),
                                  ("org.gnome.Nautilus", "Files", "Name[fr]=Fichiers\n")):
            (apps / f"{ident}.desktop").write_text(DESKTOP.format(nom=nom, autre=autre, exe=ident))
        (apps / "kde/kate.desktop").write_text(DESKTOP.format(nom="Kate", autre="", exe="kate"))   # identifiant kde-kate
        self.bin = r / "faux"
        self.bin.mkdir()
        (self.bin / "noctalia").write_text(f'#!/bin/sh\necho "noctalia $*" >> "{r}/appels"\n')
        (self.bin / "noctalia").chmod(0o755)
        (r / "run").mkdir(mode=0o700)
        self.env = {k: v for k, v in os.environ.items() if not k.startswith("NOCTALIA_")}
        # Les dossiers de Noctalia (NOCTALIA_*_HOME, puis XDG_*_HOME) : ceux du faux HOME, jamais ceux du garde-fou
        self.env.update(HOME=str(r), XDG_CONFIG_HOME=str(r / ".config"), XDG_STATE_HOME=str(r / ".local/state"),
                        XDG_DATA_HOME=str(r / ".local/share"), XDG_DATA_DIRS=str(r / "rien"),
                        XDG_RUNTIME_DIR=str(r / "run"), XDG_CACHE_HOME=str(r / "cache"), NC_LANGUE="fr", PATH=str(self.bin) + os.pathsep + os.environ["PATH"])

    def dock(self, *args):
        return subprocess.run([str(NC_DOCK), *args], env=self.env, capture_output=True, text=True, timeout=20)

    def liste(self):
        r = self.dock("liste", "--json")
        assert r.returncode == 0, r.stderr
        return [x["id"] for x in json.loads(r.stdout)]

    def appels(self):
        p = self.r / "appels"
        return p.read_text().splitlines() if p.exists() else []

    def fermer(self):
        self._tmp.cleanup()


class NcDock(unittest.TestCase):
    def setUp(self):
        self.b = Banc()

    def tearDown(self):
        self.b.fermer()

    def test_format_de_pinned_dans_la_config(self):
        # Identifiants de fichiers .desktop sans l'extension, dans la table [dock] (et un autre pinned, celui du lanceur)
        m = re.search(r"^\[dock\]$(.*?)^\[", CONFIG.read_text(encoding="utf-8"), re.M | re.S)
        self.assertIn('pinned = ["@BROWSER@", "kitty", "org.gnome.Nautilus"]', m[1])
        self.assertEqual(self.b.liste(), ["firefox", "kitty", "org.gnome.Nautilus"])

    def test_epingler_retirer(self):
        b = self.b
        r = b.dock("epingler", "gimp.desktop")              # avec ou sans .desktop
        self.assertEqual((r.returncode, r.stdout.strip()), (0, "« GIMP » épinglé au dock."), r.stderr)
        self.assertEqual(b.liste(), ["firefox", "kitty", "org.gnome.Nautilus", "gimp"])
        self.assertEqual(b.appels(), ["noctalia msg config-reload"])
        # config.toml jamais touché (nc-maj le remplace) : la liste est dans zz-dock.toml, lu après lui
        self.assertEqual((b.config / "config.toml").read_text(encoding="utf-8"), b.origine)
        zz = (b.config / "zz-dock.toml").read_text(encoding="utf-8")
        self.assertTrue(zz.startswith("# Écrit par nc-dock"))
        self.assertIn('\n[dock]\npinned = ["firefox", "kitty", "org.gnome.Nautilus", "gimp"]\n', zz)
        # Déjà là : rien d'écrit, rien rechargé
        r = b.dock("epingler", "gimp")
        self.assertEqual((r.returncode, r.stdout.strip()), (0, "« GIMP » est déjà dans le dock."))
        self.assertEqual(len(b.appels()), 1)
        r = b.dock("retirer", "kitty")
        self.assertEqual((r.returncode, r.stdout.strip()), (0, "« Kitty » retiré du dock."))
        self.assertEqual(b.liste(), ["firefox", "org.gnome.Nautilus", "gimp"])
        r = b.dock("retirer", "kitty")
        self.assertEqual((r.returncode, r.stdout.strip()), (0, "« kitty » n'est pas dans le dock."))
        # Sous-dossier d'applications : identifiant XDG (kde/kate.desktop → kde-kate)
        self.assertEqual(b.dock("epingler", "kde-kate").returncode, 0)
        self.assertEqual(b.liste()[-1], "kde-kate")
        # Rien d'autre dans le dossier de Noctalia (aucun fichier temporaire laissé)
        self.assertEqual(sorted(p.name for p in b.config.iterdir()), ["config.toml", "zz-dock.toml"])

    def test_refus(self):
        b = self.b
        r = b.dock("epingler", "inconnue")
        self.assertEqual(r.returncode, 2)
        self.assertIn("Appli inconnue : inconnue", r.stderr)
        self.assertFalse((b.config / "zz-dock.toml").exists())
        for args in ([], ["epingler"], ["liste", "--x"], ["nimporte", "kitty"]):
            self.assertEqual(b.dock(*args).returncode, 1, args)
        self.assertEqual(b.dock("epingler", "../kitty").returncode, 1)
        self.assertEqual(b.appels(), [])

    def test_liste_texte_et_sans_config(self):
        b = self.b
        (b.config / "config.toml").unlink()
        self.assertEqual(b.liste(), [])
        self.assertEqual(b.dock("liste").stdout.strip(), "Aucune appli épinglée au dock.")
        self.assertEqual(b.dock("epingler", "kitty").returncode, 0)
        out = b.dock("liste").stdout.strip()
        self.assertEqual(out, "kitty  (Kitty)")
        r = json.loads(b.dock("liste", "--json").stdout)
        self.assertEqual(r, [{"id": "kitty", "nom": "Kitty"}])

    def test_settings_toml_prime_et_suit(self):
        # La liste changée dans les réglages de Noctalia (settings.toml, son format : tables indentées, espaces dans
        # les crochets) : c'est elle que voit le dock ; nc-dock change cette seule valeur, tout le reste à l'octet près
        b = self.b
        etat = ('config_version = 15\n\n[dock]\nenabled = true\npinned = [ "kitty",\n  "firefox" # commentaire\n]\n'
                'radius = 26\n\n    [dock.x]\n    pinned = [ "ailleurs" ]\n\n[shell.launcher]\npinned = [ "kitty" ]\n')
        b.etat.write_text(etat, encoding="utf-8")
        self.assertEqual(b.liste(), ["kitty", "firefox"])
        self.assertEqual(b.dock("epingler", "org.gnome.Nautilus").returncode, 0)
        self.assertEqual(b.etat.read_text(encoding="utf-8"),
                         etat.replace('[ "kitty",\n  "firefox" # commentaire\n]', '["kitty", "firefox", "org.gnome.Nautilus"]'))
        self.assertEqual(b.liste(), ["kitty", "firefox", "org.gnome.Nautilus"])
        self.assertEqual((b.config / "config.toml").read_text(encoding="utf-8"), b.origine)
        self.assertFalse((b.config / "zz-dock.toml").exists())
        # L'ancien fichier, copié avant l'écriture
        self.assertEqual((b.r / "cache/nc/dock/settings.toml.avant").read_text(encoding="utf-8"), etat)

    def test_dossiers_de_noctalia_xdg(self):
        # C-2 : Noctalia lit NOCTALIA_CONFIG_HOME, puis XDG_CONFIG_HOME, puis ~/.config (et pareil pour l'état :
        # NOCTALIA_STATE_HOME, XDG_STATE_HOME, ~/.local/state) ; nc-dock écrivait un fichier que Noctalia ne lisait pas
        b = self.b
        etat = 'config_version = 15\n\n[dock]\npinned = ["kitty"]\n'
        for nom in ("xdg-etat", "noctalia-etat"):
            (b.r / nom / "noctalia").mkdir(parents=True)
            (b.r / nom / "noctalia/settings.toml").write_text(etat, encoding="utf-8")
        b.env.pop("XDG_CONFIG_HOME")
        b.env["XDG_STATE_HOME"] = str(b.r / "xdg-etat")
        self.assertEqual(b.liste(), ["kitty"])
        self.assertEqual(b.dock("epingler", "gimp").returncode, 0)
        self.assertEqual((b.r / "xdg-etat/noctalia/settings.toml").read_text(encoding="utf-8"),
                         'config_version = 15\n\n[dock]\npinned = ["kitty", "gimp"]\n')
        self.assertFalse(b.etat.exists(), "rien dans ~/.local/state quand XDG_STATE_HOME est ailleurs")
        # NOCTALIA_STATE_HOME passe avant XDG_STATE_HOME
        b.env["NOCTALIA_STATE_HOME"] = str(b.r / "noctalia-etat")
        self.assertEqual(b.dock("retirer", "kitty").returncode, 0)
        self.assertEqual((b.r / "noctalia-etat/noctalia/settings.toml").read_text(encoding="utf-8"),
                         'config_version = 15\n\n[dock]\npinned = []\n')
        self.assertIn("gimp", (b.r / "xdg-etat/noctalia/settings.toml").read_text(encoding="utf-8"))
        # Sans settings.toml : zz-dock.toml dans XDG_CONFIG_HOME/noctalia (config.toml relu au même endroit)
        b.env.pop("NOCTALIA_STATE_HOME"); b.env["XDG_STATE_HOME"] = str(b.r / "vide")
        b.env["XDG_CONFIG_HOME"] = str(b.r / "xdg-config")
        (b.r / "xdg-config/noctalia").mkdir(parents=True)
        shutil.copy2(b.config / "config.toml", b.r / "xdg-config/noctalia/config.toml")
        self.assertEqual(b.liste(), ["firefox", "kitty", "org.gnome.Nautilus"])
        self.assertEqual(b.dock("retirer", "kitty").returncode, 0)
        self.assertTrue((b.r / "xdg-config/noctalia/zz-dock.toml").exists())
        self.assertFalse((b.config / "zz-dock.toml").exists())

    def test_settings_toml_sans_liste(self):
        # settings.toml de Noctalia (config_version) sans pinned : la liste y est ajoutée, comme le fait le menu
        # « Épingler » du dock (setOverride) ; dans [dock] s'il existe, sinon une table [dock] à la fin
        b = self.b
        etat = 'config_version = 15\n\n[lockscreen_widgets]\nenabled = true\n\n    [lockscreen_widgets.grid]\n    cell_size = 16\n'
        b.etat.write_text(etat, encoding="utf-8")
        self.assertEqual(b.dock("epingler", "gimp").returncode, 0)
        self.assertEqual(b.etat.read_text(encoding="utf-8"),
                         etat + '\n[dock]\npinned = ["firefox", "kitty", "org.gnome.Nautilus", "gimp"]\n')
        etat = 'config_version = 15\n\n[dock]\nauto_hide = false\n\n[theme]\nmode = "dark"\n'
        b.etat.write_text(etat, encoding="utf-8")
        self.assertEqual(b.dock("retirer", "kitty").returncode, 0)
        self.assertEqual(b.etat.read_text(encoding="utf-8"),
                         etat.replace("[dock]\n", '[dock]\npinned = ["firefox", "org.gnome.Nautilus"]\n'))
        self.assertEqual(b.liste(), ["firefox", "org.gnome.Nautilus"])
        self.assertFalse((b.config / "zz-dock.toml").exists())
        # Une valeur que nc-dock ne sait pas relire : rien d'écrit
        etat = 'config_version = 15\n[dock]\npinned = "kitty"\n'
        b.etat.write_text(etat, encoding="utf-8")
        r = b.dock("epingler", "gimp")
        self.assertEqual(r.returncode, 3)
        self.assertEqual(b.etat.read_text(encoding="utf-8"), etat)

    def test_dock_ecrit_dans_une_chaine_multiligne(self):
        # Une ligne « [dock] » dans le texte multiligne d'un autre réglage n'est pas la table [dock] : nc-dock lit et
        # change le vrai dock, et ce texte reste tel quel (contre-relecture de Codex, DOCK-R1)
        b = self.b
        for guillemets in ('"""', "'''"):
            with self.subTest(guillemets=guillemets):
                etat = (f'config_version = 15\n\n[autre]\ntexte = {guillemets}\n[dock]\npinned = ["leurre"]\n{guillemets}\n\n'
                        '[dock]\npinned = ["firefox"]\n')
                b.etat.write_text(etat, encoding="utf-8")
                self.assertEqual(b.liste(), ["firefox"])
                self.assertEqual(b.dock("epingler", "gimp").returncode, 0)
                self.assertEqual(b.etat.read_text(encoding="utf-8"),
                                 etat.replace('pinned = ["firefox"]', 'pinned = ["firefox", "gimp"]'))

    def test_format_mal_compris_jamais_ecrit(self):
        # pinned donné en clé pointée (dock.pinned = …) : nc-dock ne le voit pas ; ajouter une table [dock] ferait un
        # fichier que Noctalia refuserait. Vérifié par tomllib (Python 3.11 et plus) : rien n'est écrit
        try:
            import tomllib  # noqa: F401
        except ImportError:
            self.skipTest("tomllib (Python 3.11 et plus)")
        b = self.b
        etat = 'config_version = 15\ndock.pinned = ["kitty"]\n'
        b.etat.write_text(etat, encoding="utf-8")
        r = b.dock("epingler", "gimp")
        self.assertEqual(r.returncode, 3, r.stdout)
        self.assertEqual(b.etat.read_text(encoding="utf-8"), etat)

    def test_sans_verrou_rien_n_est_ecrit(self):
        # Verrou impossible à prendre : deux nc-dock pourraient s'effacer l'un l'autre, donc rien n'est écrit (DOCK-R2)
        b = self.b
        bloque = b.r / "pas-un-dossier"
        bloque.write_text("")
        b.env["XDG_RUNTIME_DIR"] = str(bloque)
        r = b.dock("epingler", "gimp")
        self.assertEqual(r.returncode, 3)
        self.assertIn("verrou", r.stderr)
        self.assertFalse((b.config / "zz-dock.toml").exists())
        self.assertEqual(b.appels(), [])

    def test_monter_descendre(self):
        b = self.b
        r = b.dock("descendre", "firefox")
        self.assertEqual((r.returncode, r.stdout.strip()), (0, "« Firefox » déplacé (2ᵉ place sur 3)."))
        self.assertEqual(b.liste(), ["kitty", "firefox", "org.gnome.Nautilus"])
        self.assertEqual(b.dock("monter", "org.gnome.Nautilus").returncode, 0)
        self.assertEqual(b.liste(), ["kitty", "org.gnome.Nautilus", "firefox"])
        r = b.dock("up", "kitty")
        self.assertEqual((r.returncode, r.stdout.strip()), (0, "« Kitty » est déjà en tête de dock."))
        self.assertEqual(b.dock("descendre", "firefox").stdout.strip(), "« Firefox » est déjà en bout de dock.")
        self.assertEqual(b.dock("monter", "gimp").stdout.strip(), "« gimp » n'est pas dans le dock.")

    def test_appli_cachee(self):
        # NoDisplay : le dock de Noctalia ne la montrerait pas (resolveEntries) ; refusée
        b = self.b
        (b.r / ".local/share/applications/outil.desktop").write_text(DESKTOP.format(nom="Outil", autre="NoDisplay=true\n", exe="outil"))
        r = b.dock("epingler", "outil")
        self.assertEqual(r.returncode, 2)
        self.assertIn("Appli cachée", r.stderr)

    def test_ecritures_simultanees(self):
        # Clics rapides : chaque nc-dock attend le précédent (verrou), aucune épingle perdue
        b = self.b
        ps = [subprocess.Popen([str(NC_DOCK), "epingler", x], env=b.env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
              for x in ("gimp", "kde-kate")]
        self.assertEqual([p.wait(timeout=20) for p in ps], [0, 0])
        self.assertEqual(sorted(b.liste()[3:]), ["gimp", "kde-kate"])

    def test_en_anglais(self):
        b = self.b
        b.env["NC_LANGUE"] = "en"
        r = b.dock("pin", "org.gnome.Nautilus")
        self.assertEqual((r.returncode, r.stdout.strip()), (0, "“Files” is already in the dock."))


class Reglages(unittest.TestCase):
    """nc-reglages → Barre et dock, avec le vrai nc-dock dans un faux HOME (chargé après HOME changé : BIN en dépend)."""

    def setUp(self):
        self.b = Banc()
        self.addCleanup(self.b.fermer)
        bin_ = self.b.r / ".local/bin"
        bin_.mkdir(parents=True)
        shutil.copy2(NC_DOCK, bin_ / "nc-dock")
        apps = [{"id": "kitty", "name": "Kitty"}, {"id": "gimp", "name": "GIMP"}, {"id": "org.gnome.Nautilus", "name": "Fichiers"}]
        (bin_ / "nc-apps").write_text("#!/bin/sh\necho '" + json.dumps(apps) + "'\n")
        (bin_ / "nc-apps").chmod(0o755)
        env = mock.patch.dict(os.environ, self.b.env)
        env.start()
        self.addCleanup(env.stop)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", ResourceWarning)              # lecture de /sys par materiel()
            l = importlib.machinery.SourceFileLoader("ncreglages_dock", str(REPO / "home/.local/bin/nc-reglages"))
            self.m = importlib.util.module_from_spec(importlib.util.spec_from_loader("ncreglages_dock", l))
            l.exec_module(self.m)
        self.m.catalogue_raccourcis = lambda: []
        self.m.lignes_sessions = lambda: []

    def dock_du_catalogue(self):
        return [x for x in self.m.catalogue({}) if x["section"] == "Barre et dock"]

    def test_catalogue(self):
        # Une ligne par appli épinglée (« Retirer », sans confirmation : ça se remet d'un geste), puis l'ajout (une info :
        # le choix parmi toutes les applis se fait dans le Spotlight ou le terminal)
        cat = self.dock_du_catalogue()
        self.assertEqual([x["cle"] for x in cat][-4:], ["dock:firefox", "dock:kitty", "dock:org.gnome.Nautilus", "dock:ajouter"])
        kitty = cat[-3]
        self.assertEqual((kitty["nom"], kitty["genre"], kitty["commande"], kitty.get("confirmer"), kitty["relire"], kitty["affiche"]),
                         ("Kitty", "action", ["nc-dock", "retirer", "kitty"], None, True, "Retirer"))
        self.assertEqual((cat[-1]["genre"], cat[-1]["nom"]), ("info", "Ajouter une appli…"))
        self.assertIn("clic droit", cat[-1]["aide"])
        self.assertEqual(cat[0]["cle"], "BARRE_OPACITE")              # les réglages d'avant restent en tête
        # La commande de la fenêtre graphique, telle quelle : la liste relue n'a plus kitty
        r = subprocess.run([str(self.b.r / ".local/bin" / kitty["commande"][0]), *kitty["commande"][1:]],
                           capture_output=True, text=True, timeout=20)
        self.assertEqual(r.stdout.strip(), "« Kitty » retiré du dock.")
        self.assertNotIn("dock:kitty", [x["cle"] for x in self.dock_du_catalogue()])
        for x in ("firefox", "org.gnome.Nautilus"):
            self.b.dock("retirer", x)
        self.assertEqual([x["cle"] for x in self.dock_du_catalogue()][-2:], ["info:dock-vide", "dock:ajouter"])

    def test_choix_des_applis_a_ajouter(self):
        applis = [{"id": "kitty", "name": "Kitty"}, {"id": "org.kde.kate", "name": "Kate"}, {"id": "gimp", "name": "GIMP"},
                  {"id": "katarakt", "name": "Katarakt"}, {"id": "akatsuki", "name": "Akatsuki"}, {"id": "e", "name": "Éditeur"}]
        self.assertEqual([a["id"] for a in self.m.applis_a_epingler(applis, "kat", ["katarakt"])], ["org.kde.kate", "akatsuki"])
        self.assertEqual([a["id"] for a in self.m.applis_a_epingler(applis, "GIMP", [])], ["gimp"])
        self.assertEqual([a["id"] for a in self.m.applis_a_epingler(applis, "edit", [])], ["e"])
        self.assertEqual(self.m.applis_a_epingler(applis, " ", []), [])

    def ecran(self, saisies, reponses):
        """L'écran du terminal sans curses ; saisir et choisir répondent dans l'ordre."""
        m = self.m
        e = m.Ecran.__new__(m.Ecran)
        e.messages, e.questions, e.pos, e.vals = [], [], {}, {}
        e.sec = m.SECTIONS.index("Barre et dock")
        e.statut = lambda texte, erreur=False: e.messages.append((texte, erreur))
        e.dessiner = lambda: None
        e.saisir = lambda titre, initial="", aide="": saisies.pop(0)
        e.choisir = lambda titre, options, aide="", texte="": e.questions.append(options) or reponses.pop(0)
        return e

    def test_terminal(self):
        e = self.ecran(["zzz", "i", "i", None], [None, 0, 0, 2, 1])
        lignes = e.items()
        i = lignes.index({"genre": "titre", "nom": "Applis épinglées au dock"})
        self.assertEqual([x.get("cle") for x in lignes[i + 1:]],
                         ["dock:firefox", "dock:kitty", "dock:org.gnome.Nautilus", "dock:ajouter"])
        ajouter = lignes[-1]
        # Rien ne correspond ; puis Échap dans le choix ; puis GIMP (kitty et Fichiers, déjà là, ne sont pas proposés)
        e.assistant(ajouter)
        self.assertEqual(e.messages[-1], ("Aucune appli installée ne correspond à « zzz »", True))
        e.assistant(ajouter)
        self.assertEqual(e.questions[-1], ["GIMP"])
        self.assertEqual(e.messages[-1], ("Rien n'a changé", False))
        e.assistant(ajouter)
        self.assertEqual(e.messages[-1], ("« GIMP » épinglé au dock.", False))
        self.assertEqual(e.items()[-2]["cle"], "dock:gimp")
        e.assistant(ajouter)                             # Échap dans la saisie : rien
        self.assertEqual(len(e.messages), 3)
        # Entrée sur une appli : monter (pas pour la première), descendre (pas pour la dernière), retirer
        e.pos[e.sec] = len(e.items()) - 3
        e.assistant(e.items()[-3])                       # Fichiers (3ᵉ sur 4) : Monter
        self.assertEqual(e.questions[-1], ["Monter (vers le début du dock)", "Descendre (vers la fin du dock)", "Retirer du dock", "Annuler"])
        self.assertEqual(e.messages[-1], ("« Fichiers » déplacé (2ᵉ place sur 4).", False))
        self.assertEqual(self.b.liste(), ["firefox", "org.gnome.Nautilus", "kitty", "gimp"])
        self.assertEqual(e.pos[e.sec], len(e.items()) - 4, "le curseur suit l'appli")
        lignes = e.items()
        e.assistant(next(x for x in lignes if isinstance(x, dict) and x.get("cle") == "dock:firefox"))  # la première, pas de « Monter » : Annuler
        self.assertEqual(e.questions[-1], ["Descendre (vers la fin du dock)", "Retirer du dock", "Annuler"])
        self.assertEqual(e.messages[-1], ("Rien n'a changé", False))
        e.assistant(next(x for x in lignes if isinstance(x, dict) and x.get("cle") == "dock:gimp"))     # la dernière : Retirer
        self.assertEqual(e.questions[-1], ["Monter (vers le début du dock)", "Retirer du dock", "Annuler"])
        self.assertEqual(e.messages[-1], ("« GIMP » retiré du dock.", False))
        self.assertEqual(self.b.liste(), ["firefox", "org.gnome.Nautilus", "kitty"])
        self.assertEqual((self.b.config / "config.toml").read_text(encoding="utf-8"), self.b.origine)


@unittest.skipUnless(shutil.which("qs"), "quickshell absent")
class Spotlight(unittest.TestCase):
    def test_clic_droit_et_alt_p(self):
        with tempfile.TemporaryDirectory(prefix="nc-spotlight-dock-") as d:
            root = Path(d); shutil.copytree(QML, root / "qml"); (root / "runtime").mkdir(mode=0o700)
            q = root / "qml"
            (q / "Reglages.qml").write_text('pragma Singleton\nimport QtQuick\nQtObject {readonly property bool iaCoupee: false; readonly property bool sobre: true; function t(fr,en){return fr} function val(k,d){return d} function pageActive(n){return true}}')
            (q / "Etat.qml").write_text('pragma Singleton\nimport QtQuick\nimport Quickshell\nQtObject {property string saisie: ""; property string texteIA: ""; property bool recherche: true\n'
                                        ' readonly property string bin: Quickshell.env("HOME") + "/.local/bin/"; property int fermetures: 0; signal validerRecherche()\n'
                                        ' function faire(c) {} function fermer() { fermetures++ } function aller(p) {}}')
            (q / "AssistantEtat.qml").write_text('pragma Singleton\nimport QtQuick\nQtObject {function formater(t){return t}}')
            (q / "Etincelle.qml").write_text('import QtQuick\nItem {property real taille: 10; property bool tourne: false; property string agent: ""}')
            noms = ["Reglages", "Etat", "AssistantEtat", "Couleurs", "Connexion", "Recherche", "Etincelle", "Texte", "Ico"]
            (q / "qmldir").write_text("\n".join(("singleton " if n in ("Reglages", "Etat", "AssistantEtat", "Couleurs", "Connexion") else "") + n + " 1.0 " + n + ".qml" for n in noms))
            b = root / ".local/bin"; b.mkdir(parents=True)
            # Faux nc-dock : la liste dans un fichier de son propre HOME temporaire ; journalise ses appels
            faux_dock = '''#!/bin/sh
L="$HOME/epingles"; [ -e "$L" ] || echo kitty > "$L"
echo "nc-dock $*" >> "$HOME/appels"
case "$1" in
  liste) printf '['; s=""; while read -r x; do printf '%s{"id": "%s", "nom": ""}' "$s" "$x"; s=", "; done < "$L"; echo ']' ;;
  epingler) echo "$2" >> "$L"; echo "« $2 » épinglé au dock." ;;
  retirer) grep -vx "$2" "$L" > "$L.n"; mv "$L.n" "$L"; echo "« $2 » retiré du dock." ;;
esac
'''
            apps = '[{"id": "kitty", "name": "Kitty", "generic": "Terminal", "keywords": "", "exe": "kitty", "icon": "", "wmclass": ""}, ' \
                   '{"id": "gimp", "name": "GIMP", "generic": "Images", "keywords": "", "exe": "gimp", "icon": "", "wmclass": ""}]'
            scripts = {"nc-apps": "#!/bin/sh\necho '" + apps + "'\n", "hyprctl": "#!/bin/sh\necho '[]'\n", "nc-aide-config": "#!/bin/sh\nexit 0\n",
                       "nc-demander": '#!/bin/sh\necho \'{"nom": "", "agent": "", "coupee": false}\'\n', "nc-dock": faux_dock,
                       "nc-session": "#!/bin/sh\necho '[]'\n"}
            for nom, code in scripts.items():
                (b / nom).write_text(code); (b / nom).chmod(0o755)
            (q / "shell.qml").write_text('''import QtQuick
import Quickshell
ShellRoot {
 property int etape: 0
 function trouver(item,nom){if(item.objectName===nom)return item;for(var i=0;i<item.children.length;i++){var r=trouver(item.children[i],nom);if(r)return r}return null}
 function verifier(ok,message){if(!ok){console.error(message);Qt.exit(2);throw new Error(message)}}
 function titres(){ return spot.resultats.map(x => x.titre) }
 FloatingWindow { visible: true; implicitWidth: 700; implicitHeight: 500
  Recherche { id: spot; width: 700; actif: true } }
 Timer { interval: 100; running: true; repeat: true; onTriggered: {
  var champ = trouver(spot, "nc-spotlight-champ")
  if (etape === 0) { if (!spot.applis.length || !spot.dockLu) return; champ.text = "gimp"; etape++; return }
  if (etape === 1) { verifier(titres()[0] === "GIMP", JSON.stringify(titres()))
   verifier(spot.resultats[0].dock === "gimp" && !spot.resultats[0].epingle, "GIMP pas encore épinglé")
   verifier(spot.resultats[0].aide.indexOf("Alt P épingler au dock") >= 0, "aide : " + spot.resultats[0].aide)
   // Clic droit sur la ligne : épingler ; le Spotlight reste ouvert
   spot.actionDock(0)
   verifier(Etat.fermetures === 0, "le Spotlight reste ouvert")
   etape++; return }
  if (etape === 2) { if (!spot.retourDock || spot.retourDock.ok === undefined || spot.dockOccupe) return
   verifier(titres()[0] === "« gimp » épinglé au dock." && spot.resultats[0].glyphe === "push_pin", "retour : " + JSON.stringify(spot.resultats[0]))
   verifier(spot.resultats[1].titre === "GIMP" && spot.resultats[1].epingle, "GIMP épinglé : " + JSON.stringify(spot.resultats[1]))
   // Une ligne qui n'est pas une appli : Alt + P ne fait rien (la touche revient à la saisie)
   verifier(spot.actionDock(0) === false, "retour : pas une appli")
   champ.text = "kitty"
   verifier(spot.retourDock === null, "une nouvelle saisie efface le retour")
   verifier(spot.resultats[0].epingle && spot.resultats[0].aide.indexOf("Alt P retirer du dock") >= 0, "kitty épinglé : " + spot.resultats[0].aide)
   // Alt + P au clavier : retirer
   champ.forceActiveFocus()
   etape++; return }
  if (etape === 3) { if (!champ.activeFocus) return
   var ev = { key: Qt.Key_P, modifiers: Qt.AltModifier, accepted: false }
   spot.toucheDock(ev)
   verifier(ev.accepted, "Alt + P accepté")
   etape++; return }
  if (etape === 4) { if (!spot.retourDock || spot.retourDock.ok === undefined || spot.dockOccupe) return
   verifier(titres()[0] === "« kitty » retiré du dock." && !spot.resultats[1].epingle, "retiré : " + JSON.stringify(titres()))
   Qt.quit() }
 } }
 Timer { interval: 12000; running: true; onTriggered: Qt.exit(9) }
}''')
            env = dict(os.environ, HOME=d, QT_QPA_PLATFORM="offscreen", QT_QUICK_BACKEND="software", XDG_RUNTIME_DIR=str(root / "runtime"),
                       XDG_CACHE_HOME=str(root / "cache"), PATH=str(b) + os.pathsep + os.environ["PATH"])
            env.pop("WAYLAND_DISPLAY", None)
            r = subprocess.run(["qs", "--no-color", "-p", str(q / "shell.qml")], env=env, text=True, capture_output=True, timeout=25)
            sortie = r.stdout + r.stderr
            self.assertEqual(r.returncode, 0, sortie)
            for erreur in ("ReferenceError", "TypeError", "is not a type"):
                self.assertNotIn(erreur, sortie)
            appels = (root / "appels").read_text().splitlines()
            self.assertIn("nc-dock epingler gimp", appels)
            self.assertIn("nc-dock retirer kitty", appels)
            self.assertEqual(appels[0], "nc-dock liste --json")


if __name__ == "__main__":
    unittest.main()
