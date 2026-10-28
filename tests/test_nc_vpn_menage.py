"""nc-vpn : arrêt propre (SIGTERM pendant un nmcli lent : le dossier du mot de passe disparaît) et ménage des dossiers
« nc-vpn-* » abandonnés dans XDG_RUNTIME_DIR (connecter et importer). Faux nmcli, faux secret-tool : rien de réel."""
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import time
import unittest

from tests._vpn_faux import BaseVpn, BIN, U1

LENT = '''#!/bin/sh
case "$*" in
  *"connection up"*) : > "$FAUX_DIR/up-commence"; sleep 60 ;;
  *) exec "$FAUX_DIR/faux-bin/nmcli-orig" "$@" ;;
esac
'''


class Menage(BaseVpn):
    def setUp(self):
        super().setUp()
        (self.r / "vpn_data.json").write_text(json.dumps({U1: "password-flags = 1, username = moi"}))
        (self.r / "secret-valeur").write_bytes(b"MOTDEPASSEDETEST")
        self.run_dir = self.r / "run"

    def vieux(self, chemin, age=3600):
        t = time.time() - age
        os.utime(chemin, (t, t), follow_symlinks=False)

    def dossiers(self):
        return sorted(p.name for p in self.run_dir.iterdir())

    # ── arrêt propre ──
    def test_sigterm_pendant_nmcli_efface_le_dossier_du_mot_de_passe(self):
        nmcli = self.r / "faux-bin" / "nmcli"
        nmcli.rename(self.r / "faux-bin" / "nmcli-orig")
        nmcli.write_text(LENT)
        nmcli.chmod(0o755)
        for sig in (signal.SIGTERM, signal.SIGHUP, signal.SIGINT):
            marque = self.r / "up-commence"
            marque.unlink(missing_ok=True)
            p = subprocess.Popen([sys.executable, str(BIN), "connecter", U1], env=self.env(), stdin=subprocess.DEVNULL,
                                 stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            self.addCleanup(lambda p=p: p.poll() is None and p.kill())
            for _ in range(200):
                if marque.exists():
                    break
                time.sleep(0.05)
            self.assertTrue(marque.exists(), "nmcli up a commencé")
            (d,) = [x for x in self.run_dir.iterdir() if x.name.startswith("nc-vpn-")]
            self.assertTrue((d / "mdp").exists(), "le mot de passe est dans le dossier pendant nmcli up")
            p.send_signal(sig)
            p.communicate(timeout=20)
            self.assertNotEqual(p.returncode, 0)
            self.assertEqual([x.name for x in self.run_dir.iterdir() if x.name.startswith("nc-vpn-")], [], sig)

    # ── ménage ──
    def test_menage_vieux_efface_recent_garde(self):
        vieux = self.run_dir / "nc-vpn-vieux"
        vieux.mkdir(mode=0o700)
        (vieux / "mdp").write_text("x")
        self.vieux(vieux)
        recent = self.run_dir / "nc-vpn-recent"
        recent.mkdir(mode=0o700)
        r = self.vpn("connecter", U1)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertNotIn("nc-vpn-vieux", self.dossiers())
        self.assertIn("nc-vpn-recent", self.dossiers())

    def test_menage_ne_touche_ni_lien_ni_autre_prefixe_ni_fichier(self):
        cible = self.r / "cible"
        cible.mkdir()
        (cible / "precieux").write_text("garder")
        lien = self.run_dir / "nc-vpn-lien"
        lien.symlink_to(cible)
        self.vieux(lien)
        self.vieux(cible)
        autre = self.run_dir / "autre-vieux"
        autre.mkdir()
        self.vieux(autre)
        fichier = self.run_dir / "nc-vpn-fichier"
        fichier.write_text("x")
        self.vieux(fichier)
        r = self.vpn("connecter", U1)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue(lien.is_symlink(), "un lien n'est jamais effacé")
        self.assertTrue((cible / "precieux").exists(), "un lien n'est jamais suivi")
        self.assertTrue(autre.exists())
        self.assertTrue(fichier.exists(), "un fichier ordinaire du même nom reste")

    def test_menage_seulement_les_dossiers_directs(self):
        a = self.run_dir / "sous"
        (a / "nc-vpn-profond").mkdir(parents=True)
        self.vieux(a / "nc-vpn-profond")
        self.vpn("connecter", U1)
        self.assertTrue((a / "nc-vpn-profond").exists())

    def test_menage_aussi_a_l_import(self):
        vieux = self.run_dir / "nc-vpn-vieux"
        vieux.mkdir(mode=0o700)
        self.vieux(vieux)
        conf = self.r / "labo.conf"
        conf.write_text("[Interface]\nPrivateKey = AAAA\nAddress = 192.0.2.2/32\n[Peer]\nPublicKey = BBBB\nEndpoint = 192.0.2.1:51820\nAllowedIPs = 0.0.0.0/0\n")
        self.vpn("importer", str(conf))                 # réussi ou refusé : le ménage passe avant tout
        self.assertFalse(vieux.exists())

    def test_pas_de_menage_sans_xdg_runtime_dir_a_nous(self):
        # sans XDG_RUNTIME_DIR utilisable, rien n'est balayé (et rien ne casse)
        vieux = self.run_dir / "nc-vpn-vieux"
        vieux.mkdir(mode=0o700)
        self.vieux(vieux)
        env = self.env()
        env["XDG_RUNTIME_DIR"] = str(self.r / "absent")
        r = subprocess.run([sys.executable, str(BIN), "connecter", U1], env=env, capture_output=True, text=True, timeout=30, stdin=subprocess.DEVNULL)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue(vieux.exists())

    # ── seuil ──
    def test_seuil_au_dessus_des_delais_de_connecter(self):
        src = BIN.read_text()
        seuil = int(re.search(r"^SEUIL_DOSSIER_ABANDONNE = (\d+)", src, re.M).group(1))
        def corps(nom):
            m = re.search(r"^def %s\(.*?(?=^def |^# ──)" % nom, src, re.M | re.S)
            return m.group(0)
        total = 15 * 2          # nmcli par défaut : connue() puis la lecture des attributs
        for nom in ("connecter", "lire_secret", "mot_de_passe_agent_owned"):
            total += sum(int(x) for x in re.findall(r"(?:delai|timeout)=(\d+)", corps(nom)))
        self.assertGreaterEqual(total, 150, "la somme lue dans le code est plausible")
        self.assertGreaterEqual(seuil, 2 * total, "monter le seuil si les délais de connecter augmentent")


if __name__ == "__main__":
    unittest.main()
