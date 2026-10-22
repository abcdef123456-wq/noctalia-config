"""Une seule porte vers les réglages : la fenêtre graphique (nc-reglages fenetre, dans l'île). Aucune touche, aucun
menu, aucun bouton ne lance plus l'écran du terminal (nc-reglages seul, ses raccourcis, ses nouveautés, nc-raccourci)
dans kitty, foot, alacritty… : c'est nc-reglages fenetre qui l'ouvre de lui-même, en repli, quand l'île est absente
(openSUSE, sans Quickshell) ou ne répond pas. Lecture des fichiers de home/ seulement : rien n'est lancé."""
from pathlib import Path
import re
import unittest

REPO = Path(__file__).resolve().parents[1]
HOME = REPO / "home"

TERMINAUX = re.compile(r"\b(kitty|foot|footclient|alacritty|wezterm|ghostty|konsole|gnome-terminal|ptyxis|xterm|"
                       r"xdg-terminal-exec|x-terminal-emulator|uwsm-terminal)\b")
OUTIL = re.compile(r"(?<![\w-])nc-(reglages|settings|raccourci|shortcut)(?![\w.-])")
# Sous-commandes qui ouvrent l'écran du terminal (remplacé par la fenêtre) ; les autres (mode-graphique, assistant…)
# sont des questions ponctuelles, permises
ECRANS = {"", "raccourcis", "shortcuts", "nouveautes", "nouveautés", "news"}
# Le repli lui-même (nc-reglages fenetre, sans île) ; nc-raccourci renvoie vers l'écran de nc-reglages déjà ouvert
PERMIS = {"home/.local/bin/nc-reglages", "home/.local/bin/nc-raccourci"}
# Repli assumé hors d'un bureau graphique : Neovim par SSH ou en console (sans WAYLAND_DISPLAY)
PERMIS_LIGNES = {("home/.config/nvim/lua/plugins/bureau.lua", 'terminal({ maison .. "/.local/bin/nc-reglages" })()')}


def fichiers():
    for f in sorted(HOME.rglob("*")):
        if not f.is_file() or f.is_symlink():
            continue
        try:
            b = f.read_bytes()
        except OSError:
            continue
        if b"\0" in b[:8192]:
            continue
        yield f, b.decode("utf-8", "replace")


def portes_terminal(ligne):
    """Les lancements de l'écran du terminal sur cette ligne : [(outil, sous-commande)]."""
    t = TERMINAUX.search(ligne)
    if not t:
        return []
    res = []
    for m in OUTIL.finditer(ligne, t.end()):
        avant = re.sub(r"[\s\"',\[]+$", "", ligne[:m.start()])
        if re.search(r"(--class|--app-id|--name|class=|app_id=|-T|--title)[= ]*$", avant):
            continue                                                  # le nom de la fenêtre, pas la commande
        # Lancé par le terminal : après -e (ou --, -x, start), ou juste après son nom (« kitty ~/…/nc-reglages ») ;
        # une simple liste de noms (« jamais="kitty foot … nc-reglages" ») n'en est pas un
        entre = ligne[t.end():m.start()]
        if not (re.search(r"(^|[\s\"',])(-e|-x|--|start|--command)([\s\"',=]|$)", entre)
                or re.fullmatch(r"[\s\"',]*[~$\w/.{}+\" ]*?/", entre)):
            continue
        # La sous-commande : après une espace, ou l'élément suivant d'un tableau (« "nc-reglages", "raccourcis" ») ;
        # rien si la chaîne se ferme (« nc-reglages") »)
        suite = re.match(r"(?:\s+|[\"']\s*,\s*[\"']|[\"']\s+)?([\w-]*)", ligne[m.end():]).group(1)
        if suite.lower() in ECRANS:
            res.append((m.group(0), suite))
    return res


def portes_desktop(texte):
    """Une entrée de menu (.desktop) qui lance l'écran du terminal : Exec sans sous-commande, ou avec Terminal=true."""
    res = []
    terminal = re.search(r"^Terminal\s*=\s*true", texte, re.M | re.I)
    for l in re.findall(r"^Exec\s*=(.*)$", texte, re.M):
        for m in OUTIL.finditer(l):
            suite = re.match(r"[\s\"']*([\w-]*)", l[m.end():]).group(1)
            if suite.lower() in ECRANS or terminal:
                res.append(l.strip())
    return res


class Portes(unittest.TestCase):
    def test_la_regle_reconnait_les_anciennes_portes(self):
        # Les formes d'avant (touche Outils, bouton de la fenêtre, fiche de Noctalia, « Tout voir » de nc-maj)
        anciennes = [
            'touche("XF86Tools", cmd("kitty --class nc-reglages -e ~/.local/bin/nc-reglages"), portable)',
            'onClic: Quickshell.execDetached(["kitty", "--class", "nc-reglages", "-e", fen.bin + "nc-reglages", "raccourcis"]) }',
            'noctalia.runAsync({ "sh", "-c", "kitty --class nc-reglages -e ~/.local/bin/nc-raccourci || x" })',
            'exec kitty --class nc-maj -e sh -c "$HOME/.local/bin/nc-reglages nouveautes | less -R"',
            'foot -e nc-settings',
        ]
        for l in anciennes:
            self.assertTrue(portes_terminal(l), l)
        permises = [
            'cmd("~/.local/bin/nc-reglages fenetre")',
            'kitty --class nc-reglages -e ~/.local/bin/nc-reglages mode-graphique',
            'hl.window_rule({ name = "nc-reglages-fenetre", match = { class = "kitty" } })',
            'kitty --class nc-reglages -e nvim',
        ]
        for l in permises:
            self.assertFalse(portes_terminal(l), l)
        self.assertTrue(portes_desktop("[Desktop Entry]\nExec=/x/nc-reglages\n"))
        self.assertTrue(portes_desktop("[Desktop Entry]\nTerminal=true\nExec=/x/nc-reglages fenetre\n"))
        self.assertFalse(portes_desktop('[Desktop Entry]\nExec="@HOME@/.local/bin/nc-reglages" fenetre\n'))

    def test_aucune_porte_vers_l_ecran_du_terminal(self):
        trouvees = []
        for f, texte in fichiers():
            rel = f.relative_to(REPO).as_posix()
            if rel in PERMIS:
                continue
            if f.suffix == ".desktop":
                trouvees += [f"{rel} : {l}" for l in portes_desktop(texte)]
            for n, ligne in enumerate(texte.splitlines(), 1):
                if (rel, ligne.strip()) in PERMIS_LIGNES:
                    continue
                if portes_terminal(ligne):
                    trouvees.append(f"{rel}:{n} : {ligne.strip()}")
        self.assertEqual(trouvees, [], "Lance plutôt « nc-reglages fenetre [SECTION] » (repli sur le terminal sans l'île) :\n"
                         + "\n".join(trouvees))

    def test_le_repli_existe_toujours(self):
        # L'écran du terminal reste : seul réglage sur openSUSE et sans île, ouvert par nc-reglages fenetre
        src = (HOME / ".local/bin/nc-reglages").read_text(encoding="utf-8")
        self.assertIn("def tui(", src)
        corps = src.split("def fenetre_graphique(", 1)[1].split("\ndef ", 1)[0]
        self.assertIn('"--class", "nc-reglages", "-e"', corps)

    def test_portes_connues_passent_par_la_fenetre(self):
        lire = lambda p: (HOME / p).read_text(encoding="utf-8")
        self.assertIn('touche("XF86Tools",             cmd("~/.local/bin/nc-reglages fenetre")', lire(".config/hypr/nc/raccourcis.lua"))
        self.assertIn("nc-reglages fenetre Raccourcis", lire(".local/share/noctalia/plugins/nc-keys/panel.luau"))
        self.assertIn('"$HOME/.local/bin/nc-reglages" fenetre Nouveautés', lire(".local/bin/nc-maj"))
        self.assertIn('"/.local/bin/nc-reglages", "fenetre"', lire(".config/nvim/lua/plugins/bureau.lua"))
        self.assertIn('Exec="@HOME@/.local/bin/nc-reglages" fenetre', lire(".local/share/applications/nc-reglages.desktop"))
        self.assertIn("function reglagesSection(nom: string)", lire(".config/quickshell/nc-ile/shell.qml"))
        self.assertIn("function allerSection(s)", lire(".config/quickshell/nc-ile/Parametres.qml"))


if __name__ == "__main__":
    unittest.main()
