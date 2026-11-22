"""Défauts des thèmes v3 vus sur le vrai écran : (1) l'île sur les fenêtres quand la barre n'est pas en haut (bande
ILE_BANDE), (2) barre verticale non adaptée, (3) dock visible par-dessus les fenêtres (reserve_space), (4) île plus
haute que la barre en haut (gruvbox, apple), (5) texte de la pilule rogné pendant que l'île grandit (nord).
Faux HOME, faux noctalia ; les rendus hors écran se font dans une copie de l'île (outils/rendu-ile.py), jamais à l'écran."""
from tests import _isolation  # noqa: F401  (HOME, XDG_*, langue : avant tout le reste)
import importlib.machinery
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
ILE_Y, ILE_FERMEE = 9, 30            # Ile.qml : y de l'île sur la barre de base, hauteur de la pilule fermée


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


def y_ile(d):
    """y de l'île fermée (Ile.qml) : 6 dans la bande de 42 px, sinon centrée dans la barre du haut (ILE_Y de nc-reglages),
    9 sans barre en haut."""
    b = barre(d)
    if d.get("reglages", {}).get("ILE_BANDE") == "oui":
        return 6
    return b["margin_edge"] + (b["thickness"] - ILE_FERMEE) // 2 if b["position"] == "top" else ILE_Y


def hauteur_ile(d, y=None):
    """Bas de l'île fermée : y + hauteur, plus le contour quand il entoure aussi la pilule fermée (Couleurs.qml)."""
    reglages = d.get("reglages", {})
    e = int(reglages.get("ILE_CONTOUR_EPAISSEUR", "2"))
    contour = reglages.get("ILE_CONTOUR_FERMEE") == "oui" and reglages.get("ILE_CONTOUR", "degrade") != "aucun"
    return (y_ile(d) if y is None else y) + ILE_FERMEE + (e if contour else 0)


def regle_hauteur(d, y=None):
    """Vrai si l'île fermée tient dans la barre du haut, ou si la bande lui garde sa place (y : celui de l'île, par
    défaut centré comme Ile.qml le fait aujourd'hui)."""
    b = barre(d)
    return d["reglages"].get("ILE_BANDE") == "oui" or b["thickness"] + b["margin_edge"] >= hauteur_ile(d, y)


def lire_toml(texte):
    """Le zy-reglages.toml écrit par nc-reglages, à plat par nom de table ([bar.default] → "bar.default"). Avec tomllib
    (tables en ligne des groupes de pastilles comprises) ; sans, repli ligne à ligne (JSON pour les textes et listes)."""
    try:
        import tomllib
    except ImportError:
        tomllib = None
    if tomllib:
        tables = {}
        for l in texte.splitlines():
            m = re.fullmatch(r"\[(.+)\]", l)
            if m:
                tables.setdefault(m.group(1), {})
        d = tomllib.loads(texte)
        for nom in tables:
            v = d
            for partie in re.findall(r'"[^"]*"|[^.]+', nom):
                v = v[partie.strip('"')]
            tables[nom] = v
        return tables
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
                        nom, barre(d)["thickness"], barre(d)["margin_edge"], hauteur_ile(d)))

    def test_apple_et_gruvbox_explicites(self):
        """Vus à l'écran : l'île pendait sous la barre. Contrôle du contrôle : leurs barres de 7378cd3, avec l'île à y fixe
        (9, comme à l'époque), échouent."""
        t = themes()
        for nom, ancienne in (("apple", 30), ("gruvbox", 34)):
            with self.subTest(theme=nom):
                self.assertTrue(regle_hauteur(t[nom]))
                d = json.loads(json.dumps(t[nom]))
                d["noctalia"]["bar.default"]["thickness"] = ancienne
                if nom == "gruvbox":
                    d["reglages"]["ILE_CONTOUR_FERMEE"] = "oui"
                self.assertFalse(regle_hauteur(d, ILE_Y))

    def test_base_tient_deja(self):
        self.assertTrue(regle_hauteur(themes()["noctalia"]))


# --- L'île centrée en hauteur dans la barre du haut de chaque thème (vu sur pluie-verte : 4 px trop bas)
class Centrage(unittest.TestCase):
    def test_ile_centree_dans_la_barre_du_haut(self):
        spec = importlib.util.spec_from_loader("nc_reglages_y", importlib.machinery.SourceFileLoader(
            "nc_reglages_y", str(DEPOT / "home/.local/bin/nc-reglages")))
        nc = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(nc)
        for nom, d in themes().items():
            b = barre(d)
            with self.subTest(theme=nom):
                self.assertEqual(nc.ile_y(d) if d["reglages"].get("ILE_BANDE") != "oui" else 6, y_ile(d))
                if b["position"] == "top" and d["reglages"].get("ILE_BANDE") != "oui":
                    haut = y_ile(d) - b["margin_edge"]
                    bas = b["margin_edge"] + b["thickness"] - y_ile(d) - ILE_FERMEE
                    self.assertLessEqual(abs(haut - bas), 1, f"{haut} px au-dessus, {bas} px dessous")
        # contrôle : l'ancien y fixe (9) dans le bandeau de pluie-verte (collé, 40 px) n'est pas centré
        b = barre(themes()["pluie-verte"])
        self.assertGreater(abs((ILE_Y - b["margin_edge"]) - (b["margin_edge"] + b["thickness"] - ILE_Y - ILE_FERMEE)), 1)


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
        # l'encoche est collée au bord ; sinon centrée (ILE_Y) ou dans la bande
        self.assertIn('y: Couleurs.forme === "encoche" ? 0 : (Reglages.val("ILE_BANDE", "non") === "oui" ? 6 : '
                      '(parseInt(Reglages.val("ILE_Y", "%d")) || %d))' % (ILE_Y, ILE_Y), ile)
        self.assertGreaterEqual(zone, 6 + ILE_FERMEE + 6)                  # dans la bande : 6 au-dessus, 6 dessous
        self.assertRegex(ile, r"fen\.hauteurBanniere : (?:\(pointFerme \? 10 : )?%d\)" % ILE_FERMEE)   # forme « point » : 10


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
        # Plus aucun thème n'a de barre de côté ; le filtre vertical reste prouvé sur un thème factice (l'ancienne barre de nord)
        d = json.loads((THEMES / "nord.json").read_text(encoding="utf-8"))
        d["nom"] = "essai-cote"
        d["noctalia"] = {"bar.default": {"position": "left", "margin_edge": 0, "thickness": 52, "background_opacity": 0.9,
                                         "capsule_fill": "surface_variant", "start": ["logo", "workspaces"], "center": [],
                                         "end": ["tray", "group:status", "t-heure"]},
                         "widget.workspaces": {"style": "regular", "show_labels": False},
                         "widget.t-heure": {"type": "clock", "format": "{:%H:%M}"}}
        (self.themes / "essai-cote.json").write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
        for style in ("essai-cote",):
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
        t = self.appliquer("catppuccin")                  # dock à gauche toujours visible ; à 7378cd3, rien
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


NODE = shutil.which("node")


@unittest.skipUnless(NODE, "node absent")
class EchellePilule(unittest.TestCase):
    """L'échelle de la pilule fermée (Ile.qml) : jamais NaN, jamais 0 au repos ; contenu de 32 px ou moins = 1."""
    def test_valeurs_limites(self):
        import subprocess
        src = (Path(__file__).resolve().parents[1] / "home/.config/quickshell/nc-ile/Ile.qml").read_text(encoding="utf-8")
        expr = re.search(r"^\s*scale: (!\(compact\.largeur > 32\).*)$", src, re.M).group(1)
        cas = [(0, 0), (0, 31), (31, 31), (32, 32), (33, 33), (40, 200), (200, 200), (10, None), (10, 200), (300, 200)]
        js = ("const r = [];\n" + "".join(
            f"{{ const ile = {{ width: {w} }}, compact = {{ largeur: {'undefined' if l is None else l} }}; r.push({expr}); }}\n"
            for w, l in cas) + "console.log(JSON.stringify(r));")
        sortie = subprocess.run([NODE, "-e", js], capture_output=True, text=True, timeout=30)
        self.assertEqual(sortie.returncode, 0, sortie.stderr)
        r = json.loads(sortie.stdout)          # NaN et Infinity deviennent null en JSON : refusés par l'égalité
        self.assertEqual(r[:5], [1, 1, 1, 1, 1], "0, 31, 32 et 33 au repos (et largeur 0) : échelle 1")
        self.assertAlmostEqual(r[5], 8 / 168)  # en pleine croissance : réduit, jamais négatif
        self.assertEqual(r[6:8], [1, 1], "au repos et largeur pas encore connue : 1")
        self.assertEqual(r[8:], [0, 1], "bornée : jamais négative (île plus étroite que 32), jamais au-dessus de 1")
