"""Île-12 : petits correctifs vérifiés sur le texte des fichiers (le comportement des pages est testé dans
test_presse.py et test_island_pages.py)."""
from pathlib import Path
import re
import unittest

REPO = Path(__file__).resolve().parents[1]
QML = REPO / "home/.config/quickshell/nc-ile"


def lire(nom):
    return (QML / nom).read_text(encoding="utf-8")


class LotIle12(unittest.TestCase):
    def test_texte_jamais_lu_comme_du_html(self):
        self.assertRegex(lire("Texte.qml"), r"textFormat:\s*Text\.PlainText")

    def test_aucun_texte_n_attend_du_html(self):
        # Texte est en texte brut : aucun Texte { } ne doit compter sur une balise ou une entité HTML
        for f in QML.glob("*.qml"):
            if f.name.startswith(("Assistant", "DemandeClaude", "ClesIA")):
                continue
            for m in re.finditer(r"\bTexte\s*\{[^\n]*\btext:\s*[^;\n]*(<\w+>|&(?:amp|nbsp|lt|gt|quot);)", f.read_text(encoding="utf-8")):
                self.fail(f.name + " : " + m.group(0)[:120])

    def test_fond_et_jeu_ne_tournent_pas_ecran_eteint(self):
        self.assertRegex(lire("Fond.qml"), r"anime:\s*Etat\.ecranVu\s*&&")
        self.assertRegex(lire("Jeu.qml"), r"running:\s*j\.visible\s*&&\s*Etat\.ecranVu")

    def test_filet_du_partage_24_h(self):
        self.assertRegex(lire("Partage.qml"), r"delaiFilet:\s*86400000\b")

    def test_son_du_minuteur_avec_repli(self):
        etat = lire("Etat.qml")
        self.assertIn("function jouerSon(", etat)
        self.assertIn("pw-play", etat)
        self.assertIn("/usr/share/sounds/freedesktop/stereo/", etat)
        self.assertRegex(etat, r"command -v pw-play[^\n]*\[ -r")
        self.assertIn('jouerSon("complete")', etat)
        self.assertIn('jouerSon("alarm-clock-elapsed")', etat)
        self.assertNotIn("canberra-gtk-play -i complete || true", etat)

    def test_install_ajoute_le_theme_sonore(self):
        install = (REPO / "install.sh").read_text(encoding="utf-8")
        self.assertRegex(install, r"GENERIC=\([^)]*\bsound-theme-freedesktop\b")

    def test_micro_pas_encore_lie_est_neutre(self):
        son = lire("Son.qml")
        self.assertIn("readonly property bool lie:", son)
        self.assertRegex(son, r'mic\.lie && mic\.coupe \? Couleurs\.rouge')
        self.assertRegex(son, r'!mic\.lie \? "…"')

    def test_veilleur_presse_papiers_relance_et_sans_stderr(self):
        pp = lire("PressePapiers.qml")
        self.assertRegex(pp, r"onExited:")
        self.assertNotIn("stderr: StdioCollector", pp)
        self.assertRegex(pp, r"essais < 5")

    def test_reglage_presse_duree_declare(self):
        reglages = (REPO / "home/.local/bin/nc-reglages").read_text(encoding="utf-8")
        self.assertRegex(reglages, r'R\("PRESSE_DUREE",[^\n]*"choix", "7"')
        self.assertIn("jamais", reglages)
        self.assertIn("PRESSE_DUREE", (REPO / "README.md").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
