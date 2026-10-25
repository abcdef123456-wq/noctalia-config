"""nc-apps : exec_argv retire les codes de champ du Desktop Entry, seuls ou dans un argument (« --url=%u », « sh -c "… %U" »).
Un code seul est retiré, dans un argument il est remplacé par rien, %% devient %, %i devient --icon NOM, %c le nom."""
from importlib.machinery import SourceFileLoader
from importlib.util import module_from_spec, spec_from_loader
from pathlib import Path
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "home/.local/bin/nc-apps"


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


if __name__ == "__main__":
    unittest.main()
