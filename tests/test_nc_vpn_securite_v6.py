"""nc-vpn, relecture de sécurité V6 : un seul changement à la fois pour les commandes fournisseur et mullvad, lecture réellement
bornée (le processus est arrêté), message d'erreur Mullvad filtré (ANSI, contrôles, secrets), Nord refusé quand le kill switch de
NetworkManager est actif. Faux clients seulement (PATH = faux-bin seul), jamais les vrais."""
import importlib.machinery
import importlib.util
import json
import subprocess
import sys
import time
import unittest

from tests._vpn_faux import BaseVpn, BIN

FAUX_SUDO = r'''#!/usr/bin/env python3
import json, os, sys
from pathlib import Path
R = Path(os.environ["FAUX_DIR"])
a = sys.argv[1:]
with (R / "appels-sudo.jsonl").open("a") as f: f.write(json.dumps(a) + "\n")
if a[2:3] == ["etat"]:
    print((R / "ks-etat").read_text().strip() if (R / "ks-etat").exists() else "inactif")
'''
COMPTE = "Account information\nVPN Service: Active until Jan 1, 2099\n"
PAYS = "France\nGermany\n"


def charger():
    chargeur = importlib.machinery.SourceFileLoader("nc_vpn_mod_securite", str(BIN))
    spec = importlib.util.spec_from_loader("nc_vpn_mod_securite", chargeur)
    m = importlib.util.module_from_spec(spec)
    chargeur.exec_module(m)
    return m


class SecuriteV6(BaseVpn):
    def attendre_appel(self, nom, motif):
        for _ in range(100):
            if any(a[:1] == [motif] for a in self.appels_de(nom)):
                return True
            time.sleep(0.1)
        return False

    def test_verrou_deux_connexions_en_meme_temps(self):
        self.poser("nordvpn", {"account": {"out": COMPTE}, "countries": {"out": PAYS}, "connect": {"dormir": 3, "out": "Connected\n"},
                               "disconnect": {"out": "ok\n"}})
        env = self.env(PATH=str(self.r / "faux-bin"))
        p1 = subprocess.Popen([sys.executable, str(BIN), "fournisseur", "nord", "connecter", "FR"], env=env, stdin=subprocess.DEVNULL,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            self.assertTrue(self.attendre_appel("nordvpn", "connect"))
            for args in (("fournisseur", "nord", "connecter", "DE"), ("fournisseur", "nord", "deconnecter"),
                         ("fournisseur", "mullvad", "deconnecter"), ("mullvad", "connecter")):
                r = self.seul(*args)
                self.assertEqual(r.returncode, 1, args)
                self.assertIn("autre changement", r.stderr, args)
            self.assertNotIn(["disconnect"], self.appels_de("nordvpn"))
            self.assertEqual(self.appels_mullvad(), [])
        finally:
            p1.wait(timeout=20)
            p1.stdout.close()
            p1.stderr.close()
        self.assertEqual(p1.returncode, 0)
        self.assertEqual(self.seul("fournisseur", "nord", "deconnecter").returncode, 0)      # verrou relâché à la fin

    def test_mullvad_connecter_ne_se_bloque_pas_lui_meme(self):
        r = self.seul("fournisseur", "mullvad", "connecter", "FR")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.appels_mullvad(), [["relay", "set", "location", "fr"], ["connect"]])

    def test_message_mullvad_nettoye(self):
        self.r.joinpath("mullvad.json").write_text(json.dumps(
            {"echec": "\x1b[31mError\x1b[0m: \x07refused https://exemple.invalid/x?token=1 ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 moi@exemple.invalid"}))
        r = self.seul("mullvad", "connecter")
        self.assertEqual(r.returncode, 1)
        for interdit in ("\x1b", "\x07", "https://", "exemple.invalid", "ABCDEFGHIJKLMNOP"):
            self.assertNotIn(interdit, r.stderr)
        self.assertIn("Error", r.stderr)

    def test_nord_refuse_si_killswitch_actif(self):
        self.poser("nordvpn", {"account": {"out": COMPTE}, "countries": {"out": PAYS}})
        f = self.r / "faux-bin" / "sudo"
        f.write_text(FAUX_SUDO)
        f.chmod(0o755)
        helper = self.r / "nc-vpn-root"
        helper.write_text("#!/bin/sh\n")
        (self.r / "ks-etat").write_text("actif")
        r = self.seul("fournisseur", "nord", "connecter", "FR", NC_VPN_ROOT=str(helper))
        self.assertEqual(r.returncode, 1)
        self.assertIn("kill switch", r.stderr)
        self.assertEqual([a for a in self.appels_de("nordvpn") if a[:1] == ["connect"]], [])
        m = charger()
        self.assertEqual(m.Echec("x", "killswitch_actif").code, "killswitch_actif")
        (self.r / "ks-etat").write_text("inactif")
        r = self.seul("fournisseur", "nord", "connecter", "FR", NC_VPN_ROOT=str(helper))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual([a for a in self.appels_de("nordvpn") if a[:1] == ["connect"]], [["connect", "France"]])

    def test_nord_sans_assistant_killswitch_n_empeche_pas(self):
        self.poser("nordvpn", {"account": {"out": COMPTE}, "countries": {"out": PAYS}})
        r = self.seul("fournisseur", "nord", "connecter", "FR", NC_VPN_ROOT=str(self.r / "absent"))
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_lecture_bornee_arrete_le_processus(self):
        m = charger()
        pid = self.r / "pid"
        prog = ("import os,sys,time\nopen(%r,'w').write(str(os.getpid()))\n"
                "while True:\n    sys.stdout.buffer.write(b'x'*65536); sys.stdout.flush(); time.sleep(0.01)\n") % str(pid)
        t0 = time.time()
        code, out, err = m.lancer_borne([sys.executable, "-c", prog], 20, 4096)
        self.assertEqual(code, 125)
        self.assertLessEqual(len(out), 4096)
        self.assertLess(time.time() - t0, 10)
        time.sleep(0.3)
        vivant = True
        try:
            import os
            os.kill(int(pid.read_text()), 0)
        except OSError:
            vivant = False
        self.assertFalse(vivant, "le processus doit être arrêté")

    def test_delai_arrete_le_groupe(self):
        m = charger()
        code, out, err = m.lancer_borne([sys.executable, "-c", "import time; time.sleep(60)"], 1, 4096)
        self.assertEqual(code, 124)

    def test_commande_absente_ou_normale(self):
        m = charger()
        self.assertEqual(m.lancer_borne(["/nonexistent/xyz"], 2)[0], 126)
        code, out, err = m.lancer_borne([sys.executable, "-c", "import sys; print('a'); print('b', file=sys.stderr); sys.exit(3)"], 5)
        self.assertEqual((code, out, err), (3, b"a\n", b"b\n"))


if __name__ == "__main__":
    unittest.main()
