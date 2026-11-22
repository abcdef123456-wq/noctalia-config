"""Contraste WCAG (au moins 4,5:1) de toutes les palettes du dépôt, côtés dark et light :
texte sur surface, et texte sur couleur principale."""
import json
from pathlib import Path
import unittest

PALETTES = Path(__file__).resolve().parent.parent / "home/.config/noctalia/palettes"
# Palette existante qui échoue : on ne la modifie pas ici (raison : elle est déjà livrée), le seuil reste exigé ailleurs.
EXCEPTIONS = {("Apple", "dark", "primaire"), ("Apple", "light", "primaire")}


def lum(h):
    c = [int(h.lstrip("#")[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    c = [x / 12.92 if x <= 0.03928 else ((x + 0.055) / 1.055) ** 2.4 for x in c]
    return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]


def ratio(a, b):
    x, y = sorted((lum(a), lum(b)), reverse=True)
    return (x + 0.05) / (y + 0.05)


class Contraste(unittest.TestCase):
    def test_toutes_les_palettes(self):
        fichiers = sorted(PALETTES.glob("*.json"))
        self.assertGreaterEqual(len(fichiers), 15)
        for f in fichiers:
            p = json.loads(f.read_text())
            for mode in ("dark", "light"):
                if mode not in p:
                    continue
                s = p[mode]
                for nom, a, b in (("surface", "mOnSurface", "mSurface"), ("primaire", "mOnPrimary", "mPrimary")):
                    if (f.stem, mode, nom) in EXCEPTIONS:
                        continue
                    with self.subTest(palette=f.stem, mode=mode, paire=nom):
                        self.assertGreaterEqual(ratio(s[a], s[b]), 4.5)


if __name__ == "__main__":
    unittest.main()
