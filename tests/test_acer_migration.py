"""Lot A5 : migrer_anciens_assistants (install.sh) retire les anciens assistants root de l'Acer.
Racine d'essai, faux sudo et faux visudo seulement : rien de réel n'est touché."""
import os
import re
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
INSTALL = (REPO / "install.sh").read_text()
ANCIENS = ["nc-cpu-limite", "nc-ventilateurs", "nc-puissance", "nc-gpu-limite"]
PROPRE = "".join(f"alice ALL=(root) NOPASSWD: /usr/local/bin/{n} *\n" for n in ANCIENS)


def fonction(nom):
    m = re.search(r"(?ms)^%s\(\) \{.*?^\}\n" % nom, INSTALL)
    assert m, nom
    return m.group(0)


class Migration(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.d = Path(self._tmp.name)
        self.r = self.d / "racine"
        (self.r / "usr/local/bin").mkdir(parents=True)
        (self.r / "etc/sudoers.d").mkdir(parents=True)
        self.bk = self.d / "bk"
        self.bk.mkdir()
        self.faux = self.d / "faux"
        self.faux.mkdir()
        sudo = self.faux / "sudo"
        self.journal = self.d / "journal"
        sudo.write_text(f'#!/bin/bash\necho "$*" >> {self.journal}\nexec "$@"\n')
        sudo.chmod(0o755)
        self.path = f"{self.faux}:/usr/bin:/bin"

    def visudo(self, code):
        v = self.faux / "visudo"
        v.write_text(f"#!/bin/bash\nexit {code}\n")
        v.chmod(0o755)

    def prog(self, nom):
        p = self.r / "usr/local/bin" / nom
        p.write_text("#!/bin/sh\n")
        p.chmod(0o755)
        return p

    def sudoers(self, nom, texte):
        p = self.r / "etc/sudoers.d" / nom
        p.write_text(texte)
        p.chmod(0o440)
        return p

    def lance(self, uid_root=None):
        uid = os.getuid() if uid_root is None else uid_root
        script = ("set -u\nt(){ printf '%s' \"$1\"; }\ninfo(){ echo \"INFO: $*\"; }\nwarn(){ echo \"WARN: $*\"; }\n"
                  f"BK={self.bk}\n" + fonction("migrer_anciens_assistants") + "migrer_anciens_assistants\n")
        env = {"PATH": self.path, "NC_LANGUE": "fr", "NC_RACINE_MIGRATION": str(self.r),
               "NC_SUDO": str(self.faux / "sudo"), "NC_MIGRATION_UID_ROOT": str(uid)}
        return subprocess.run(["bash", "-c", script], env=env, capture_output=True, text=True, timeout=30,
                              stdin=subprocess.DEVNULL)

    def present(self, rel):
        return (self.r / rel).exists() or (self.r / rel).is_symlink()

    def test_retire_et_sauvegarde(self):
        for n in ANCIENS:
            self.prog(n)
        self.sudoers("nc-limites", PROPRE)
        self.visudo(0)
        p = self.lance()
        for n in ANCIENS:
            self.assertFalse(self.present(f"usr/local/bin/{n}"), p.stdout)
            self.assertTrue((self.bk / "system/usr/local/bin" / n).is_file())
        self.assertFalse(self.present("etc/sudoers.d/nc-limites"))
        self.assertEqual((self.bk / "system/etc/sudoers.d/nc-limites").read_text(), PROPRE)
        self.assertEqual(p.stdout.count("INFO: Anciens assistants root"), 1, p.stdout)
        self.assertIn("nc-puissance", p.stdout)
        self.assertIn(str(self.bk / "system"), p.stdout)

    def test_pas_a_root(self):
        for n in ANCIENS:
            self.prog(n)
        self.sudoers("nc-limites", PROPRE)
        p = self.lance(uid_root=os.getuid() + 1)
        for n in ANCIENS:
            self.assertTrue(self.present(f"usr/local/bin/{n}"), p.stdout)
        self.assertTrue(self.present("etc/sudoers.d/nc-limites"))
        self.assertNotIn("retirés", p.stdout)
        self.assertFalse((self.bk / "system").exists())

    def test_liens_et_noms_proches(self):
        (self.d / "cible").write_text("x")
        (self.r / "usr/local/bin/nc-cpu-limite").symlink_to(self.d / "cible")
        for n in ("nc-cpu-limite2", "nc-puissance.bak", "nc-energie-root"):
            self.prog(n)
        p = self.lance()
        for rel in ("nc-cpu-limite", "nc-cpu-limite2", "nc-puissance.bak", "nc-energie-root"):
            self.assertTrue(self.present(f"usr/local/bin/{rel}"), p.stdout)
        self.assertEqual(p.stdout, "")

    def test_sudoers_melange_ou_all(self):
        self.prog("nc-puissance")
        cas = {
            "mixte1": PROPRE + "alice ALL=(ALL) ALL\n",
            "mixte2": "alice ALL=(root) NOPASSWD: /usr/local/bin/nc-puissance *, /usr/bin/id\n",
            "tout": "alice ALL=(root) NOPASSWD: ALL\n",
            "tout2": "alice ALL=(root) NOPASSWD: /usr/local/bin/nc-puissance *, ALL\n",
            "autre": "alice ALL=(root) NOPASSWD: /usr/local/bin/nc-puissance2 *\n",
            "proche": "alice ALL=(root) NOPASSWD: /opt/nc-puissance *\n",
        }
        for nom, texte in cas.items():
            self.sudoers(nom, texte)
        p = self.lance()
        for nom in cas:
            self.assertTrue(self.present(f"etc/sudoers.d/{nom}"), (nom, p.stdout))
        self.assertIn("mixte1", p.stdout)
        self.assertFalse(self.present("usr/local/bin/nc-puissance"), "le programme à root part quand même")

    def test_nos_fichiers_intacts(self):
        for nom in ("nc-energie", "nc-vpn", "nc-limite-charge"):
            self.sudoers(nom, PROPRE)
        p = self.lance()
        for nom in ("nc-energie", "nc-vpn", "nc-limite-charge"):
            self.assertTrue(self.present(f"etc/sudoers.d/{nom}"), p.stdout)
        self.assertEqual(p.stdout, "")

    def test_sauvegarde_impossible(self):
        for n in ANCIENS:
            self.prog(n)
        self.sudoers("nc-limites", PROPRE)
        self.bk.chmod(0o555)
        self.addCleanup(self.bk.chmod, 0o755)
        if os.access(self.bk, os.W_OK):
            self.skipTest("dossier inscriptible malgré 0555 (root)")
        p = self.lance()
        for n in ANCIENS:
            self.assertTrue(self.present(f"usr/local/bin/{n}"), p.stdout)
        self.assertTrue(self.present("etc/sudoers.d/nc-limites"))
        self.assertIn("WARN", p.stdout)

    def test_visudo_refuse_remet_le_fichier(self):
        self.prog("nc-puissance")
        self.sudoers("nc-limites", PROPRE)
        self.visudo(1)
        p = self.lance()
        self.assertEqual((self.r / "etc/sudoers.d/nc-limites").read_text(), PROPRE, p.stdout)
        self.assertIn("WARN", p.stdout)
        self.assertIn("remises", p.stdout)

    def test_liste_et_visudo_par_sudo(self):
        """/etc/sudoers.d (0750) et /etc/sudoers ne se lisent qu'en root : find et visudo passent par sudo."""
        self.prog("nc-puissance")
        self.sudoers("nc-limites", PROPRE)
        self.visudo(0)
        self.lance()
        appels = self.journal.read_text().split()
        self.assertIn("find", appels)
        self.assertIn("visudo", appels)
        self.assertFalse(self.present("etc/sudoers.d/nc-limites"))

    def test_include_n_est_pas_un_commentaire(self):
        self.sudoers("nc-limites", PROPRE + "#includedir /etc/autre\n")
        self.visudo(0)
        p = self.lance()
        self.assertTrue(self.present("etc/sudoers.d/nc-limites"), p.stdout)

    def test_regles_piegees_gardees(self):
        """Relecture : chaque piège garde le fichier (et donc sudo pour l'utilisateur)."""
        pieges = {
            "deux-points": "alice ALL=(root) NOPASSWD: /usr/local/bin/nc-puissance * : ALL=(ALL) ALL\n",
            "suite-de-ligne": "alice ALL=(root) NOPASSWD: /usr/local/bin/nc-puissance \\\n    , ALL\n",
            "uid": PROPRE + "#1000 ALL=(ALL) NOPASSWD: ALL\n",
            "negation": "alice ALL=(root) NOPASSWD: /usr/local/bin/nc-puissance !*\n",
            "egal": "alice ALL=(root) NOPASSWD: /usr/local/bin/nc-puissance x=y\n",
        }
        self.prog("nc-puissance")
        self.visudo(0)
        for nom, texte in pieges.items():
            self.sudoers(nom, texte)
        p = self.lance()
        for nom, texte in pieges.items():
            with self.subTest(nom=nom):
                self.assertTrue(self.present(f"etc/sudoers.d/{nom}"), p.stdout)
                self.assertEqual((self.r / "etc/sudoers.d" / nom).read_text(), texte)

    def test_regle_gardee_si_son_programme_reste(self):
        p = self.prog("nc-puissance")
        os.symlink(p, self.r / "usr/local/bin/nc-gpu-limite")   # lien : pas retiré, donc sa règle reste
        self.sudoers("nc-gpu", "alice ALL=(root) NOPASSWD: /usr/local/bin/nc-gpu-limite *\n")
        self.visudo(0)
        self.lance()
        self.assertTrue(self.present("etc/sudoers.d/nc-gpu"))

    def test_visudo_refuse_mv_en_retour_sans_lire_bk(self):
        self.prog("nc-puissance")
        self.sudoers("nc-limites", PROPRE)
        self.visudo(1)
        p = self.lance()
        self.assertEqual((self.r / "etc/sudoers.d/nc-limites").read_text(), PROPRE, p.stdout)
        self.assertFalse(self.present("etc/sudoers.d/nc-limites.nc-retrait"))
        self.assertTrue(self.present("usr/local/bin/nc-puissance"))   # aucun programme retiré non plus
        appels = self.journal.read_text().splitlines()
        self.assertIn(f"mv -f {self.r}/etc/sudoers.d/nc-limites.nc-retrait {self.r}/etc/sudoers.d/nc-limites", appels)
        self.assertEqual([a for a in appels if str(self.bk) in a], [], "root ne lit ni n'écrit rien dans $BK")

    def test_lien_dans_bk_jamais_suivi_par_root(self):
        piege = self.d / "piege"
        piege.mkdir()
        (self.bk / "system").mkdir()
        os.symlink(piege, self.bk / "system/etc")
        self.prog("nc-puissance")
        self.sudoers("nc-limites", PROPRE)
        self.visudo(0)
        p = self.lance()
        self.assertEqual([a for a in self.journal.read_text().splitlines() if str(self.bk) in a], [], p.stdout)

    def test_autre_pc_aucun_message(self):
        p = self.lance()
        self.assertEqual((p.returncode, p.stdout, p.stderr), (0, "", ""))

    def test_appel_apres_etape_energie_root(self):
        corps = fonction("etape_energie_root")
        self.assertEqual(corps.count("migrer_anciens_assistants"), 2)
        i_ok = corps.index('installé." "Advanced power profiles helper installed.")"')
        i_deja = corps.index("déjà en place.")
        # une fois après « déjà en place », une fois après « installé », jamais dans la branche d'échec
        appels = [m.start() for m in re.finditer(r"^\s*migrer_anciens_assistants$", corps, re.M)]
        self.assertEqual(len(appels), 2)
        self.assertTrue(i_deja < appels[0] < corps.index("else\n"))
        self.assertTrue(i_ok < appels[1] < corps.index("        sudo rm -f"))
        self.assertLess(INSTALL.index("migrer_anciens_assistants() {"), INSTALL.index("etape_energie_root() {"))


if __name__ == "__main__":
    unittest.main()
