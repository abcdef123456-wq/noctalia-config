"""Cadence de la musique du verrou (nc/verrou musique.luau) et de la pilule (nc/ile pilule.luau) :
  - écran éteint ($XDG_RUNTIME_DIR/nc-ecran-eteint, posé par nc-ecran) : plus aucun lancement de processus ;
  - rallumage : une relecture tout de suite ;
  - rien ne joue : une relecture toutes les 5 s au lieu de 1 s (verrou) ou 2 s (pilule).
Pas d'interpréteur Luau ici : le bloc entre « DEBUT cadence » et « FIN cadence » de chaque fichier est écrit dans le
sous-ensemble commun à Lua et Luau, et exécuté avec lua (sauté s'il est absent) avec une horloge simulée qui remplace les
appels de processus par un compteur. L'existence du fichier se teste avec noctalia.fileExists (un stat), jamais avec
un « test -e » lancé. Vie privée (VERROU_MUSIQUE) et réglage : vérifiés sur le texte."""
from pathlib import Path
import os
import re
import shutil
import subprocess
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[1]
MUSIQUE = REPO / "home/.local/share/noctalia/plugins/nc-verrou/musique.luau"
PILULE = REPO / "home/.local/share/noctalia/plugins/nc-ile/pilule.luau"
REGLAGES = REPO / "home/.local/bin/nc-reglages"
LUA = shutil.which("lua") or shutil.which("lua5.4") or shutil.which("lua5.3")

# Décor commun : horloge simulée, fichier nc-ecran-eteint simulé, compteurs de lancements
DECOR = r'''
local horloge, eteint, joue = 0, false, false
local lancements, rendus = 0, 0
ETEINT = "nc-ecran-eteint"
noctalia = { fileExists = function(p) assert(p == ETEINT, "fichier testé : " .. tostring(p)); return eteint end,
  setUpdateInterval = function() end }
function maintenant() return horloge end
ecranEteint, media, derniereLecture, dernierMedia, derniereSeconde = false, nil, 0, 0, 0
function rendre() rendus = rendus + 1 end
function surveiller() end
local function lecture()
  lancements = lancements + 1
  media = joue and { etat = "Playing" } or nil
end
'''

# Scénarios : 60 tours d'une seconde ; chaque cas rend « lancements » sur la minute
SCENARIOS = r'''
local function minute(etat_a, etat_b, bascule)
  -- etat_*: { eteint, joue } ; bascule : seconde du changement (nil : aucun)
  horloge, lancements, rendus = 1000000, 0, 0
  ecranEteint, media, derniereLecture, dernierMedia = false, nil, horloge - 100000, horloge - 100000
  eteint, joue = etat_a[1], etat_a[2]
  media = joue and { etat = "Playing" } or nil
  local au_rallumage = nil
  for s = 0, 59 do
    if bascule and s == bascule then eteint, joue = etat_b[1], etat_b[2] end
    local avant = lancements
    update()
    if bascule and s == bascule and not eteint then au_rallumage = lancements - avant end
    horloge = horloge + 1000
  end
  return lancements, au_rallumage, rendus
end
local function egal(a, b, m) if a ~= b then error(m .. " : " .. tostring(a) .. " ~= " .. tostring(b)) end end
local j, r, e = minute({ false, true }), minute({ false, false }), minute({ true, true })
print("joue", j); print("rien", r); print("eteint", e)
local _, rall = minute({ true, true }, { false, true }, 30)
local tot = minute({ true, true }, { false, true }, 30)
print("rallumage", tot, "au tour du rallumage", rall)
egal(e, 0, "écran éteint : aucun lancement")
egal(rall, 1, "rallumage : une relecture tout de suite")
print("OK")
'''


def lancer(bloc, extra):
    with tempfile.TemporaryDirectory(prefix="nc-cadence-") as d:
        f = Path(d) / "cadence.lua"
        f.write_text(DECOR + extra + bloc + SCENARIOS)
        env = {"HOME": d, "TMPDIR": d, "XDG_RUNTIME_DIR": d, "PATH": os.environ.get("PATH", "")}
        return subprocess.run([LUA, str(f)], capture_output=True, text=True, timeout=20, env=env, cwd=d)


def bloc(chemin):
    m = re.search(r"-- DEBUT cadence[^\n]*\n(.*?)-- FIN cadence", chemin.read_text(), re.S)
    assert m, "marqueurs DEBUT/FIN cadence"
    return m.group(1)


def chiffres(sortie):
    return {l.split()[0]: int(l.split()[1]) for l in sortie.splitlines() if l.split() and l.split()[0] in ("joue", "rien", "eteint", "rallumage")}


class CadenceVerrou(unittest.TestCase):
    @unittest.skipUnless(LUA, "lua absent")
    def test_musique_du_verrou(self):
        r = lancer(bloc(MUSIQUE), "lire = function() derniereLecture = maintenant(); lecture() end\n")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        c = chiffres(r.stdout)
        self.assertEqual(c["joue"], 60)       # 1 s tant que ça joue
        self.assertEqual(c["rien"], 12)       # 5 s quand rien ne joue
        self.assertEqual(c["eteint"], 0)
        self.assertEqual(c["rallumage"], 30)     # 30 s éteint (rien), puis 1 s tant que ça joue

    @unittest.skipUnless(LUA, "lua absent")
    def test_pilule(self):
        r = lancer(bloc(PILULE), "lireMedia = function() dernierMedia = maintenant(); lecture() end\n")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        c = chiffres(r.stdout)
        self.assertEqual(c["joue"], 30)       # 2 s tant que ça joue
        self.assertEqual(c["rien"], 12)
        self.assertEqual(c["eteint"], 0)
        self.assertEqual(c["rallumage"], 15)

    def test_fichier_teste_sans_processus(self):
        for f in (MUSIQUE, PILULE):
            b = bloc(f)
            self.assertIn("noctalia.fileExists(ETEINT)", b)
            self.assertNotRegex(b, r"runAsync|os\.execute|io\.popen|test -e")
            self.assertRegex(f.read_text(), r'nc-ecran-eteint"')

    def test_heure_et_batterie_rien_ecran_eteint(self):
        # l'heure et la batterie du verrou ne relisent ni ne redessinent rien écran éteint (test d'un fichier, sans processus)
        for nom in ("heure.luau", "batterie.luau"):
            src = (MUSIQUE.parent / nom).read_text()
            self.assertRegex(src, r'local ETEINT = \(noctalia\.getenv\("XDG_RUNTIME_DIR"\) or "/tmp"\) \.\. "/nc-ecran-eteint"', nom)
            corps = re.search(r"\nfunction update\(\)\n(.*?)\nend\n", src, re.S)
            self.assertTrue(corps, nom)
            garde, rendu = corps.group(1).find("if noctalia.fileExists(ETEINT) then return end"), corps.group(1).find("rendre()")
            self.assertTrue(0 <= garde < rendu, nom)        # la garde passe avant tout rendu
            self.assertNotRegex(src, r"runAsync|os\.execute|io\.popen", nom)

    def test_musique_vie_privee(self):
        s = MUSIQUE.read_text()
        self.assertIn("VERROU_MUSIQUE", s)
        self.assertRegex(s, r'local mode = "sans-navigateur"')
        self.assertRegex(s, r'if k == "VERROU_MUSIQUE"')
        self.assertIn('"Lecture en cours"', s)
        # navigateur reconnu par le nom du lecteur MPRIS
        for n in ("firefox", "chrom", "brave", "vivaldi", "opera", "edge", "zen", "librewolf", "epiphany"):
            self.assertIn('"%s"' % n, s)
        self.assertIn("navigateur(media.joueur)", s)
        # les boutons ne sont cliquables qu'avec « tout »
        self.assertRegex(s, r'if mode == "tout" then\s+commandes = ui\.row')
        self.assertEqual(s.count('commander("'), 3)
        self.assertIn("-- Précédent / lecture / suivant : cliquables seulement avec VERROU_MUSIQUE=tout", s)

    def test_reglage(self):
        s = REGLAGES.read_text()
        self.assertRegex(s, r'R\("VERROU_MUSIQUE", "Apparence", L\("Musique sur le verrouillage", "Music on the lock screen"\), "choix", "sans-navigateur"')
        self.assertIn('"VERROU_MUSIQUE": "verrou"', s)          # caché sans le verrou nc
        self.assertIn('"verrou": os.path.isfile(', s)
        for v in ('("tout"', '("sans-navigateur"', '("icone"'):
            self.assertIn(v, s)


if __name__ == "__main__":
    unittest.main()
