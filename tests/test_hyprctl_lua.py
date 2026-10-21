"""Hyprland 0.56 (config Lua) : « hyprctl dispatch » évalue du Lua (hl.dispatch(...)) et « hyprctl keyword » n'existe plus.
L'ancienne syntaxe (sendshortcut CTRL,V, ; closewindow address:…) échoue en silence : tout appel du dépôt doit passer
une expression hl.… (ou une variable qui en contient une, comme eval_lua "$1" de nc-fenetre)."""
from pathlib import Path
import re
import unittest

REPO = Path(__file__).resolve().parents[1]
DOSSIERS = [REPO / "home/.local/bin", REPO / "home/.config", REPO / "home/.local/share"]
EXTENSIONS = {".qml", ".lua", ".sh", ".py", ".luau", ""}
DISPATCH = re.compile(r"hyprctl\s+dispatch\s+(?P<reste>.*)")
KEYWORD = re.compile(r"hyprctl\s+(keyword|--batch\s+\"keyword)")


def fichiers():
    for racine in DOSSIERS + [REPO]:
        for f in racine.rglob("*") if racine != REPO else racine.glob("*.sh"):
            if f.is_file() and f.suffix in EXTENSIONS and ".git" not in f.parts and "nvim" not in f.parts:
                try:
                    f.read_text(encoding="utf-8")
                except (UnicodeDecodeError, OSError):
                    continue
                yield f


class HyprctlLua(unittest.TestCase):
    def test_dispatch_en_lua(self):
        fautes = []
        for f in fichiers():
            for n, ligne in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
                for m in DISPATCH.finditer(ligne):
                    reste = m.group("reste")
                    if "hl." not in reste and "$" not in reste and "{" not in reste:
                        fautes.append(f"{f.relative_to(REPO)}:{n}: {ligne.strip()[:120]}")
        self.assertEqual(fautes, [], "ancienne syntaxe de hyprctl dispatch (il faut hl.dsp…) :\n" + "\n".join(fautes))

    def test_pas_de_keyword(self):
        fautes = [f"{f.relative_to(REPO)}:{n}: {l.strip()[:120]}" for f in fichiers()
                  for n, l in enumerate(f.read_text(encoding="utf-8").splitlines(), 1) if KEYWORD.search(l)]
        self.assertEqual(fautes, [], "hyprctl keyword ne marche pas avec la config Lua (hyprctl eval) :\n" + "\n".join(fautes))

    def test_le_test_voit_le_depot(self):
        vus = list(fichiers())
        self.assertTrue(any(f.name == "nc-fenetre" for f in vus), "nc-fenetre non parcouru")
        self.assertTrue(any(f.name == "PressePapiers.qml" for f in vus), "les .qml ne sont pas parcourus")


if __name__ == "__main__":
    unittest.main()
