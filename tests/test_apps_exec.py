"""nc-apps : exec_argv retire les codes de champ du Desktop Entry, seuls ou dans un argument (« --url=%u », « sh -c "… %U" »).
Un code seul est retiré, dans un argument il est remplacé par rien, %% devient %, %i devient --icon NOM, %c le nom."""
from importlib.machinery import SourceFileLoader
from importlib.util import module_from_spec, spec_from_loader
from pathlib import Path
import contextlib
import io
import json
import os
import re
import tempfile
import unittest
from unittest import mock

SCRIPT = Path(__file__).resolve().parents[1] / "home/.local/bin/nc-apps"
PLUGINS = Path(__file__).resolve().parents[1] / "home/.local/share/noctalia/plugins"


def charger():
    chargeur = SourceFileLoader("nc_apps", str(SCRIPT))
    m = module_from_spec(spec_from_loader("nc_apps", chargeur))
    chargeur.exec_module(m)
    return m


class ExecArgv(unittest.TestCase):
    def argv(self, exec_, **champs):
        return charger().exec_argv({"Exec": exec_, "Name": "Exemple", **champs})

    def test_code_seul_retire(self):
        self.assertEqual(self.argv("prog %U"), ["prog"])
        self.assertEqual(self.argv("prog --x %f %F %u %k"), ["prog", "--x"])

    def test_code_dans_un_argument(self):
        self.assertEqual(self.argv("prog --url=%u"), ["prog", "--url="])
        self.assertEqual(self.argv('sh -c "prog %U; echo fin"'), ["sh", "-c", "prog ; echo fin"])
        self.assertEqual(self.argv("prog --f=%F --g=%d"), ["prog", "--f=", "--g="])

    def test_pourcent_double(self):
        self.assertEqual(self.argv("prog 100%%"), ["prog", "100%"])
        self.assertEqual(self.argv("prog %%"), ["prog", "%"])
        self.assertEqual(self.argv("prog %%U"), ["prog", "%U"])     # un « %U » écrit en clair, pas un code
        self.assertEqual(self.argv("prog %%%U"), ["prog", "%"])

    def test_icone_et_nom(self):
        self.assertEqual(self.argv("prog %i", Icon="ico"), ["prog", "--icon", "ico"])
        self.assertEqual(self.argv("prog %i"), ["prog"])
        self.assertEqual(self.argv("prog %c"), ["prog", "Exemple"])
        self.assertEqual(self.argv("prog --nom=%c"), ["prog", "--nom=Exemple"])
        self.assertEqual(self.argv("prog --i=%i"), ["prog", "--i="])

    def test_argument_vide_garde_inconnu_garde(self):
        self.assertEqual(self.argv("prog '' %z"), ["prog", "", "%z"])      # vide d'origine : gardé ; code inconnu : laissé


class RechercheFichiers(unittest.TestCase):
    """nc-apps files : arrêt à MAX_TROUVES, dossiers lourds exclus, jamais plus de 4 résultats, option « -- »."""

    def chercher(self, home, texte, **reglages):
        m = charger()
        for k, v in reglages.items():
            setattr(m, k, v)
        sortie = io.StringIO()
        with mock.patch.dict(os.environ, {"HOME": str(home)}), contextlib.redirect_stdout(sortie):
            m.cmd_files(texte)
        return json.loads(sortie.getvalue())

    def fichiers(self, base, noms):
        for n in noms:
            f = Path(base) / n
            f.parent.mkdir(parents=True, exist_ok=True)
            f.touch()

    def test_dossiers_lourds_et_caches_exclus(self):
        with tempfile.TemporaryDirectory() as t:
            self.fichiers(t, ["node_modules/a/rapport.js", "Games/rapport.txt", ".cache/rapport.txt", ".steam/rapport",
                              "venv/rapport", ".venv/rapport", "target/rapport", "Steam/rapport", "Documents/rapport.odt"])
            chemins = [r["path"] for r in self.chercher(t, "rapport")]
            self.assertEqual(chemins, [str(Path(t) / "Documents/rapport.odt")])

    def test_un_dossier_exclu_reste_trouvable_par_son_nom(self):
        with tempfile.TemporaryDirectory() as t:
            self.fichiers(t, ["Games/x.txt"])
            self.assertEqual([r["name"] for r in self.chercher(t, "games")], ["Games"])

    def test_arret_au_nombre_maximum(self):
        with tempfile.TemporaryDirectory() as t:
            self.fichiers(t, [f"d{i}/cible_{j}.txt" for i in range(10) for j in range(10)])
            m = charger()
            m.MAX_TROUVES = 5
            sortie = io.StringIO()
            with mock.patch.dict(os.environ, {"HOME": t}), contextlib.redirect_stdout(sortie):
                m.cmd_files("cible")
            self.assertLessEqual(len(json.loads(sortie.getvalue())), 4)
            # Le parcours s'arrête dès 5 trouvés : on compte ce que le parcours a vu
            compteur = []
            vrai_scandir = os.scandir
            with mock.patch.dict(os.environ, {"HOME": t}), contextlib.redirect_stdout(io.StringIO()), \
                    mock.patch("os.scandir", side_effect=lambda p: (compteur.append(p), vrai_scandir(p))[1]):
                m.cmd_files("cible")
            self.assertLess(len(compteur), 11)      # le dossier personnel puis quelques dossiers seulement, pas les 10

    def test_arret_apres_le_delai(self):
        with tempfile.TemporaryDirectory() as t:
            self.fichiers(t, ["a/b/cible.txt"])
            self.assertEqual(self.chercher(t, "cible", DELAI_RECHERCHE=-1), [])    # délai déjà passé : rien parcouru
            self.assertEqual(len(self.chercher(t, "cible")), 1)

    def test_quatre_resultats_au_plus_et_ordre(self):
        with tempfile.TemporaryDirectory() as t:
            self.fichiers(t, [f"cible{i}.txt" for i in range(8)] + ["a/b/c/d/e/cible_profond.txt", "a/b/c/d/e/f/g/cible_trop.txt"])
            noms = [r["name"] for r in self.chercher(t, "cible")]
            self.assertEqual(len(noms), 4)
            self.assertTrue(all(re.fullmatch(r"cible\d\.txt", n) for n in noms))
            self.assertEqual(self.chercher(t, "trop"), [])          # au-delà de 5 niveaux

    def test_texte_court_et_option(self):
        with tempfile.TemporaryDirectory() as t:
            self.fichiers(t, ["-x-fichier.txt"])
            self.assertEqual(self.chercher(t, "ab"), [])
            self.assertEqual(len(self.chercher(t, "-x-")), 1)


class TerminalDetecte(unittest.TestCase):
    """commande_terminal : xdg-terminal-exec, $TERMINAL, puis kitty, foot, alacritty, gnome-terminal, konsole (faux PATH)."""

    def commande(self, installes, terminal=None):
        with tempfile.TemporaryDirectory() as t:
            for n in installes:
                f = Path(t) / n
                f.write_text("#!/bin/sh\n")
                f.chmod(0o755)
            env = {"PATH": t, "TERMINAL": terminal or ""}
            with mock.patch.dict(os.environ, env):
                return charger().commande_terminal(["htop", "-d", "5"])

    def test_ordre_et_options(self):
        self.assertEqual(self.commande(["kitty", "foot"]), ["kitty", "-e", "htop", "-d", "5"])
        self.assertEqual(self.commande(["foot", "konsole"]), ["foot", "-e", "htop", "-d", "5"])
        self.assertEqual(self.commande(["alacritty"]), ["alacritty", "-e", "htop", "-d", "5"])
        self.assertEqual(self.commande(["gnome-terminal"]), ["gnome-terminal", "--", "htop", "-d", "5"])
        self.assertEqual(self.commande(["konsole"]), ["konsole", "-e", "htop", "-d", "5"])

    def test_xdg_terminal_exec_d_abord_puis_terminal(self):
        self.assertEqual(self.commande(["kitty", "xdg-terminal-exec"]), ["xdg-terminal-exec", "htop", "-d", "5"])
        self.assertEqual(self.commande(["kitty", "monterm"], terminal="monterm"), ["monterm", "-e", "htop", "-d", "5"])
        self.assertEqual(self.commande(["kitty"], terminal="absent"), ["kitty", "-e", "htop", "-d", "5"])

    def test_aucun_terminal(self):
        self.assertEqual(self.commande([]), [])


class LuauStatique(unittest.TestCase):
    """Garde-fous lus dans le texte des .luau (pas d'interpréteur Luau ici)."""

    def lire(self, rel):
        return (PLUGINS / rel).read_text(encoding="utf-8")

    def test_lanceur_sans_chaine_shell_ni_option_possible(self):
        s = self.lire("nc-launcher/panel.luau")
        self.assertNotIn('APPS_CMD[1] .. " list"', s)
        self.assertIn('{ APPS_CMD[1], "list" }', s)
        self.assertIn('"terminal", "--", question', s)
        self.assertIn('"files", "--", q', s)
        self.assertIn('"(" .. expr .. ")"', s)

    def test_lanceur_anti_rebond_et_numero_de_requete(self):
        s = self.lire("nc-launcher/panel.luau")
        self.assertRegex(s, r"DEBOUNCE_MS = 200")
        self.assertIn("noctalia.nowMs() + DEBOUNCE_MS", s)
        self.assertIn("mien ~= numRequete", s)
        # la recherche de fichiers ne part plus directement de search()
        self.assertEqual(s.count('"files"'), 1)
        self.assertIn("chercherFichiers()", s)

    def test_titre_chemin_protege(self):
        s = self.lire("nc-fenetres/titre.luau")
        self.assertNotIn("\"while :; do '\" .. c.NC", s)
        self.assertIn("cheminSur", s)

    def test_wifi_nom_avec_tiret_refuse_et_mot_de_passe_commente(self):
        s = self.lire("nc-ile/centre.luau")
        self.assertIn('string.sub(nom, 1, 1) == "-"', s)
        i = s.index('string.sub(nom, 1, 1) == "-"')
        self.assertLess(i, s.index('"dev", "wifi", "connect", nom }'))        # avant tout lancement de nmcli
        self.assertIn("Le mot de passe passe en argument de nmcli", s)


if __name__ == "__main__":
    unittest.main()
