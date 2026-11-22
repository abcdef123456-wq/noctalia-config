"""Défauts des thèmes v3 vus sur le vrai écran : (1) l'île sur les fenêtres quand la barre n'est pas en haut (bande
ILE_BANDE), (2) barre verticale non adaptée, (3) dock visible par-dessus les fenêtres (reserve_space), (4) île plus
haute que la barre en haut (gruvbox, apple), (5) texte de la pilule rogné pendant que l'île grandit (nord).
Faux HOME, faux noctalia ; les rendus hors écran se font dans une copie de l'île (outils/rendu-ile.py), jamais à l'écran."""
from tests import _isolation  # noqa: F401  (HOME, XDG_*, langue : avant tout le reste)
import importlib.util
import json
from pathlib import Path
import re
import shutil
import tempfile
import unittest

from tests import test_themes as tt

DEPOT = Path(__file__).resolve().parents[1]
THEMES = DEPOT / "home/.local/share/nc/themes"
QML = DEPOT / "home/.config/quickshell/nc-ile"
CONFIG = DEPOT / "home/.config/noctalia/config.toml"
TITRES = ("nc/fenetres:titre", "active_window")
ILE_Y, ILE_FERMEE = 9, 30            # Ile.qml : y de l'île, hauteur de la pilule fermée


def themes():
    return {p.stem: json.loads(p.read_text(encoding="utf-8")) for p in sorted(THEMES.glob("*.json"))}


def barre_de_base():
    t = CONFIG.read_text(encoding="utf-8")
    sec = re.search(r"^\[bar\.default\]\n(.*?)(?=^\[)", t, re.M | re.S).group(1)
    val = {k: int(re.search(r"^%s = (\d+)" % k, sec, re.M).group(1)) for k in ("thickness", "margin_edge")}
    return dict(val, position=re.search(r'^position = "(\w+)"', sec, re.M).group(1))


def liste_de_base(cote):
    """La liste start, center ou end de [bar.default] dans config.toml (celle que Noctalia garde si rien ne la change)."""
    m = re.search(r"^%s = \[(.*?)\]" % cote, CONFIG.read_text(encoding="utf-8"), re.M)
    return re.findall(r'"([^"]*)"', m.group(1))


def barre(d):
    return dict(barre_de_base(), **d.get("noctalia", {}).get("bar.default", {}))


def hauteur_ile(reglages):
    """Bas de l'île fermée : y + hauteur, plus le contour quand il entoure aussi la pilule fermée (Couleurs.qml)."""
    e = int(reglages.get("ILE_CONTOUR_EPAISSEUR", "2"))
    contour = reglages.get("ILE_CONTOUR_FERMEE") == "oui" and reglages.get("ILE_CONTOUR", "degrade") != "aucun"
    return ILE_Y + ILE_FERMEE + (e if contour else 0)


def regle_hauteur(d):
    """Vrai si l'île fermée tient dans la barre du haut, ou si la bande lui garde sa place."""
    b = barre(d)
    return d["reglages"].get("ILE_BANDE") == "oui" or b["thickness"] + b["margin_edge"] >= hauteur_ile(d["reglages"])


def lire_toml(texte):
    """Le zy-reglages.toml écrit par nc-reglages (toml_val : JSON pour les textes et listes, true/false, nombres)."""
    tables, t = {}, None
    for l in texte.splitlines():
        m = re.fullmatch(r"\[(.+)\]", l)
        if m:
            t = tables.setdefault(m.group(1), {})
        elif " = " in l and t is not None:
            k, v = l.split(" = ", 1)
            t[k] = json.loads(v)
    return tables


# --- (1) et (4) : règles sur les fichiers des thèmes
class ReglesDesThemes(unittest.TestCase):
    def test_barre_pas_en_haut_pose_la_bande(self):
        for nom, d in themes().items():
            with self.subTest(theme=nom):
                if barre(d)["position"] != "top":
                    self.assertEqual(d["reglages"].get("ILE_BANDE"), "oui")

    def test_ile_tient_sous_une_barre_en_haut(self):
        for nom, d in themes().items():
            with self.subTest(theme=nom):
                if barre(d)["position"] == "top":
                    self.assertTrue(regle_hauteur(d), "%s : barre %s + %s, île %s" % (
                        nom, barre(d)["thickness"], barre(d)["margin_edge"], hauteur_ile(d["reglages"])))

    def test_apple_et_gruvbox_explicites(self):
        """Vus à l'écran : l'île pendait sous la barre. Contrôle du contrôle : leurs barres de 7378cd3 échouent."""
        t = themes()
        for nom, ancienne in (("apple", 30), ("gruvbox", 34)):
            with self.subTest(theme=nom):
                self.assertTrue(regle_hauteur(t[nom]))
                d = json.loads(json.dumps(t[nom]))
                d["noctalia"]["bar.default"]["thickness"] = ancienne
                if nom == "gruvbox":
                    d["reglages"]["ILE_CONTOUR_FERMEE"] = "oui"
                self.assertFalse(regle_hauteur(d))

    def test_base_tient_deja(self):
        self.assertTrue(regle_hauteur(themes()["noctalia"]))


# --- (1) : la bande, dans la source de l'île
class BandeSource(unittest.TestCase):
    def test_creee_seulement_a_oui(self):
        shell = (QML / "shell.qml").read_text(encoding="utf-8")
        m = re.search(r"LazyLoader \{\s*id: chargeurBande\s*active: Reglages\.val\(\"ILE_BANDE\", \"non\"\) === \"oui\"\s*"
                      r"Variants \{\s*model: Quickshell\.screens\s*ReserveIle \{\}", shell)
        self.assertIsNotNone(m)
        for f in QML.glob("*.qml"):        # nulle part ailleurs
            with self.subTest(fichier=f.name):
                self.assertEqual(len(re.findall(r"\bReserveIle \{", f.read_text(encoding="utf-8"))),
                                 1 if f.name == "shell.qml" else 0)

    def test_bande_vide_sans_clic(self):
        t = (QML / "ReserveIle.qml").read_text(encoding="utf-8")
        self.assertIn("exclusiveZone: 42", t)
        self.assertIn("mask: Region {}", t)
        self.assertIn('color: "transparent"', t)
        self.assertNotRegex(t, r"\b(Text|Rectangle|Image|MouseArea|Timer)\b")

    def test_zone_couvre_la_pilule_et_vaut_la_barre_de_base(self):
        zone = int(re.search(r"exclusiveZone: (\d+)", (QML / "ReserveIle.qml").read_text(encoding="utf-8")).group(1))
        b = barre_de_base()
        self.assertEqual(zone, b["thickness"] + b["margin_edge"])        # une bannière ne déborde pas plus qu'avant
        self.assertGreaterEqual(zone, ILE_Y + ILE_FERMEE + 3)
        ile = (QML / "Ile.qml").read_text(encoding="utf-8")
        self.assertRegex(ile, r"\by: %d\s" % ILE_Y)
        self.assertRegex(ile, r"fen\.hauteurBanniere : %d\)" % ILE_FERMEE)


def charger_rendu():
    spec = importlib.util.spec_from_file_location("rendu_ile_fe", DEPOT / "outils/rendu-ile.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


@unittest.skipUnless(shutil.which("qs"), "Quickshell (qs) absent")
class HorsEcran(unittest.TestCase):
    def setUp(self):
        self.t = Path(tempfile.mkdtemp(prefix="nct-fe-"))
        self.addCleanup(shutil.rmtree, str(self.t), True)

    def rendre(self, m, reglages, etat="fermee"):
        conf = self.t / "reglages.conf"
        conf.write_text(reglages)
        png, journal = m.rendre(etat, str(self.t), str(conf), None)
        self.assertIsNotNone(png, journal[-1500:])
        return journal

    def test_bande_comptee_hors_ecran(self):
        """La bande devient une fenêtre ordinaire dans la copie, exclusiveZone gardée comme simple propriété."""
        m = charger_rendu()
        prep = m.preparer

        def preparer(root, etat, reglages, palette):
            ile = prep(root, etat, reglages, palette)
            t = (QML / "ReserveIle.qml").read_text(encoding="utf-8").replace("PanelWindow {", "FloatingWindow {")
            t = re.sub(r"^\s*(anchors\.\w+|mask|WlrLayershell\.\w+|screen):.*\n", "", t, flags=re.M)
            (ile / "ReserveIle.qml").write_text(t.replace("exclusiveZone:", "property int exclusiveZone:"))
            return ile
        m.preparer = preparer
        m.ACTIONS["fermee"] = ('console.log("BANDE " + JSON.stringify(chargeurBande.item ? chargeurBande.item.instances.map('
                               'b => b.exclusiveZone) : []))')
        for reglages, attendu in (("", []), ("ILE_BANDE=non\n", []), ("ILE_BANDE=oui\n", [42])):
            with self.subTest(reglages=reglages):
                j = self.rendre(m, reglages)
                self.assertEqual(json.loads(re.search(r"BANDE (\[.*?\])", j).group(1)), attendu, j[-800:])

    def test_texte_de_nord_pas_rogne_pendant_que_l_ile_grandit(self):
        """Étape courte puis longue ; 400 ms après, l'île de nord (ILE_ANIM=doux) grandit encore : le contenu doit tenir
        dedans, 8 px de chaque côté au moins (à 7378cd3 : « 7:01 », 270 px dans 246)."""
        m = charger_rendu()
        long_ = m.ACTIONS["agent"]
        court = long_.replace("Lance : Vérifier fiche + aperçu du rendu", "Lit")
        self.assertNotEqual(court, long_)
        m.ACTIONS["agent"] = (court + "; Qt.createQmlObject('import QtQuick; Timer { interval: 2000; running: true }', racine)"
                              ".triggered.connect(function() { " + long_ + " })")
        m.ATTENTE = 2400
        m.PILOTE = m.PILOTE.replace('console.log("CADRE "', 'var k = i.children, c = null\n'
                                    '            for (var n = 0; n < k.length; n++) if (k[n].largeur !== undefined && k[n].actif !== undefined) c = k[n]\n'
                                    '            console.log("PILULE " + JSON.stringify([c.actif.width * c.scale, i.width]))\n'
                                    '            console.log("CADRE "', 1)
        nord = themes()["nord"]["reglages"]
        j = self.rendre(m, "".join("%s=%s\n" % kv for kv in nord.items()), "agent")
        texte, ile = json.loads(re.search(r"PILULE (\[.*?\])", j).group(1))
        self.assertGreater(texte, 100)
        self.assertLessEqual(texte, ile - 16, "texte %.1f px dans une île de %.1f px" % (texte, ile))


# --- (2) et (3) : ce que nc-reglages écrit pour Noctalia
class EcritPourNoctalia(tt.Base):
    def setUp(self):
        super().setUp()
        d = self.home / ".config/noctalia"
        d.mkdir(parents=True, exist_ok=True)
        # config.toml rempli comme par install.sh : marqueurs en fin de liste retirés, marqueurs nus (polkit_agent, cx…) à 0
        t = re.sub(r'(?<=[\["])@[A-Z0-9_]+@(?=\])', "", CONFIG.read_text(encoding="utf-8"))
        t = re.sub(r"= @[A-Z0-9_]+@", "= 0", t)
        (d / "config.toml").write_text(re.sub(r"@[A-Z0-9_]+@", "x", t), encoding="utf-8")
        self.toml = d / "zy-reglages.toml"

    def appliquer(self, style, **reglages):
        for k, v in reglages.items():
            r = self.nc("set", k, v)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        r = self.nc("set", "STYLE", style)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        return lire_toml(self.toml.read_text(encoding="utf-8")) if self.toml.exists() else {}

    def test_barre_verticale_adaptee(self):
        for style in ("nord", "kanagawa"):
            with self.subTest(theme=style):
                b = self.appliquer(style, BARRE_SYSTEME="oui", VPN_PILULE_BARRE="oui")["bar.default"]
                self.assertIn(b["position"], ("left", "right"))
                for cote in ("start", "center", "end"):
                    for w in TITRES + ("group:sys",):
                        self.assertNotIn(w, b.get(cote, liste_de_base(cote)))
                self.assertIn("workspaces", b["start"])
                for w in ("group:status", "tray", "nc/vpn:vpn"):
                    self.assertIn(w, b["end"])
                self.assertGreaterEqual(b["thickness"], 52)

    def test_barre_en_haut_inchangee(self):
        """Barre en haut : la liste de la personne reste telle quelle (pas de « start » écrit, group:sys gardé)."""
        b = self.appliquer("noctalia", BARRE_SYSTEME="oui", VPN_PILULE_BARRE="oui")["bar.default"]
        self.assertNotIn("start", b)
        self.assertNotIn("thickness", b)
        self.assertIn("group:sys", b["end"])

    def test_dock_visible_reserve_sa_place(self):
        t = self.appliquer("tokyo")                       # contrôle du contrôle : à 7378cd3, rien
        self.assertIs(t["dock"]["auto_hide"], False)
        self.assertIs(t["dock"].get("reserve_space"), True)
        self.assertIs(self.appliquer("apple")["dock"].get("reserve_space"), True)

    def test_dock_cache_ne_change_rien(self):
        self.assertNotIn("reserve_space", self.appliquer("kanagawa").get("dock", {}))       # DOCK_AUTO=oui
        self.assertNotIn("reserve_space", self.appliquer("noctalia").get("dock", {}))
        self.assertNotIn("reserve_space", self.appliquer("dracula").get("dock", {}))        # DOCK=non

    def test_dock_de_la_personne(self):
        self.assertIs(self.appliquer("noctalia", DOCK_AUTO="non")["dock"].get("reserve_space"), True)


if __name__ == "__main__":
    unittest.main()
