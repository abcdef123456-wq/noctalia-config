"""Interrupteurs réactifs du centre de contrôle Noctalia (centre.luau) : même règle que Voulu.qml (état voulu local, 3 s).
Il n'y a pas d'interpréteur Luau ici : le bloc entre « DEBUT voulu » et « FIN voulu » est écrit dans le sous-ensemble
commun à Lua 5.x et exécuté avec lua (sauté s'il est absent) avec une fausse horloge ; le reste est vérifié sur le texte."""
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[1]
LUAU = REPO / "home/.local/share/noctalia/plugins/nc-ile/centre.luau"

LUA = shutil.which("lua") or shutil.which("lua5.4") or shutil.which("lua5.3")

TESTS = r'''
local maintenant = 100
os.clock = function() return maintenant end
local function egal(a, b, m) if a ~= b then error(m .. " : " .. tostring(a) .. " ~= " .. tostring(b)) end end

-- bascule immédiate
e = { wifi = "on" }
voulu("wifi", "off")
egal(valeur("wifi", e.wifi), "off", "voulu pris tout de suite")
egal(valeur("halo", "0"), "0", "une autre clé garde sa mesure")

-- mesure contraire pendant la grâce : ignorée, le bouton ne bascule pas
maintenant = 101
e = { wifi = "on" }; confirmer()
egal(valeur("wifi", e.wifi), "off", "mesure contraire ignorée")
maintenant = 102.9; expirer()
egal(valeur("wifi", e.wifi), "off", "toujours voulu à 2,9 s")

-- fin de grâce : retour à la mesure
maintenant = 103.1; expirer()
egal(valeur("wifi", e.wifi), "on", "après 3 s : retour à la mesure")

-- confirmation par la mesure : le voulu s'efface bien avant 3 s
voulu("wifi", "off")
maintenant = 103.5
e = { wifi = "off" }; confirmer()
egal(voulus.wifi, nil, "voulu effacé par la confirmation")
e = { wifi = "on" }
egal(valeur("wifi", e.wifi), "on", "puis la mesure reprend la main (pas de voulu fantôme)")

-- échec de la commande : retour tout de suite
voulu("bluetooth", "off")
annuler("bluetooth")
egal(valeur("bluetooth", "on"), "on", "échec : retour immédiat")

-- inversion on/off et 1/0
egal(CONTRAIRE["on"], "off", "on -> off"); egal(CONTRAIRE["0"], "1", "0 -> 1")
print("OK")
'''


class Reactivite(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = LUAU.read_text()

    def bloc(self):
        m = re.search(r"-- DEBUT voulu\n(.*?)-- FIN voulu", self.source, re.S)
        self.assertIsNotNone(m, "marqueurs DEBUT/FIN voulu")
        return m.group(1)

    @unittest.skipUnless(LUA, "lua absent")
    def test_logique_du_voulu(self):
        with tempfile.TemporaryDirectory(prefix="nc-luau-") as d:
            f = Path(d) / "voulu.lua"
            f.write_text("local e = {}\n" + self.bloc() + TESTS)
            r = subprocess.run([LUA, str(f)], capture_output=True, text=True, timeout=20)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertIn("OK", r.stdout)

    def test_grace_de_3_s_et_pas_de_tick_inutile(self):
        self.assertRegex(self.bloc(), r"local GRACE = 3\b")

    def test_commande_en_echec_revient_a_l_etat_reel(self):
        self.assertRegex(self.source, r"if cle and r\.exitCode and r\.exitCode ~= 0 then[^\n]*\n\s+annuler\(cle\)")

    def test_relecture_a_la_fin_puis_a_1_5_s(self):
        self.assertRegex(self.source, r"lire\(\); lirePage\(\)\s+relire = horloge\(\) \+ 1\.5")
        self.assertRegex(self.source, r"expirer\(\)\s+if relire and horloge\(\) >= relire then relire = nil; lire\(\) end")
        self.assertRegex(self.source, r"e = analyser\(r\.stdout\)\s+confirmer\(\)")

    def test_tous_les_interrupteurs_passent_par_le_voulu(self):
        s = self.source
        for cle in ("wifi", "bluetooth", "dnd", "jeu", "halo", "profil", "muet", "micro_muet"):
            self.assertRegex(s, r'valeur\("%s", e\.%s\)' % (cle, cle), cle)
        # aucune lecture directe de la mesure pour afficher un interrupteur
        for cle in ("wifi", "bluetooth", "dnd", "jeu", "halo", "muet", "micro_muet"):
            self.assertNotRegex(s, r'[^(", ]\s*e\.%s\s*==' % cle, cle)
        self.assertNotIn('msg("wifi-toggle")', s)
        self.assertNotIn('msg("bluetooth-toggle")', s)
        self.assertNotIn('msg("notification-dnd-toggle")', s)
