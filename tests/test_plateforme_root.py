"""Où sont les assistants root (NX2-a) : nc-plateforme-root (sh), nc-energie et nc-vpn (Python) suivent la même règle.

Le dossier vient de NC_ROOT_BIN dans ~/.config/nc/plateforme.conf (écrit par l'adaptateur NixOS), sinon /usr/local/bin.
« Root » est simulé par NC_PLATEFORME_UID_ROOT (l'uid courant) : aucun vrai fichier de root n'est touché.
HOME et les dossiers d'essai sont temporaires ; rien ne change os.environ au niveau du module.
"""
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest
from unittest import mock

REPO = Path(__file__).resolve().parents[1]
BIN = REPO / "home/.local/bin"
SH = BIN / "nc-plateforme-root"
NOM = "nc-limite-charge"


def fonction_python(script):
    """Le texte de assistant_root() tel qu'il est dans le script, exécuté seul (os et re suffisent)."""
    src = script.read_text(encoding="utf-8")
    m = re.search(r"^def assistant_root\(nom\):\n(?:(?:    .*)?\n)+", src, re.M)
    assert m, script
    g = {"os": os, "re": re}
    exec(m.group(0), g)
    return g["assistant_root"]


class PlateformeRoot(unittest.TestCase):
    def setUp(self):
        d = tempfile.TemporaryDirectory(prefix="nc-plateforme-")
        self.addCleanup(d.cleanup)
        self.tmp = Path(d.name)
        self.home = self.tmp / "home"
        (self.home / ".config/nc").mkdir(parents=True)
        self.uid = str(os.getuid())
        self.dossier = self.tmp / "nix-bin"
        self.dossier.mkdir(mode=0o755)
        self.fn = {"nc-energie": fonction_python(BIN / "nc-energie"), "nc-vpn": fonction_python(BIN / "nc-vpn"),
                   "nc-diag": fonction_python(BIN / "nc-diag")}

    def assistant(self, nom=NOM, mode=0o755, dossier=None):
        f = (dossier or self.dossier) / nom
        f.write_text("#!/bin/sh\nexit 0\n")
        f.chmod(mode)
        return f

    def conf(self, *lignes):
        (self.home / ".config/nc/plateforme.conf").write_text("\n".join(lignes) + "\n")

    def env(self, uid_root=None):
        return {"HOME": str(self.home), "NC_PLATEFORME_UID_ROOT": uid_root or self.uid}

    def reponses(self, nom=NOM, uid_root=None):
        """La réponse des trois implémentations (qui doivent être identiques) ; "" = refusé."""
        env = self.env(uid_root)
        r = subprocess.run(["sh", "-c", f'. "{SH}"; nc_root_bin {nom}'], env=dict(os.environ, **env),
                           capture_output=True, text=True, timeout=30)
        rep = {"sh": r.stdout.strip()}
        with mock.patch.dict(os.environ, env):
            for k, f in self.fn.items():
                rep[k] = f(nom)
        self.assertEqual(len(set(rep.values())), 1, rep)
        return rep["sh"]

    # ── Acceptés ──
    def test_defaut_sans_fichier_c_est_usr_local_bin(self):
        # sans plateforme.conf : le dossier par défaut ; l'assistant d'essai n'y est pas, donc « absent » (pas de repli ailleurs)
        self.assertEqual(self.reponses("nc-inexistant-xyz"), "")
        # et le chemin choisi est bien /usr/local/bin/<nom> (même argv qu'avant) quand l'assistant existe et est à root
        for nom in ("nc-limite-charge", "nc-vpn-root", "nc-energie-root"):
            f = Path("/usr/local/bin") / nom
            sur = f.is_file() and not f.is_symlink() and all(
                s.st_uid == 0 and not s.st_mode & 0o022 for s in (f.stat(), f.parent.stat()))
            if sur:   # installé par install.sh (root:root 0755) : exactement l'ancien chemin
                self.assertEqual(self.reponses(nom, uid_root="0"), f"/usr/local/bin/{nom}")
        # la valeur par défaut est la même dans les trois implémentations
        self.assertIn("_ncp_dir=/usr/local/bin\n", SH.read_text())
        for s in ("nc-energie", "nc-vpn"):
            self.assertIn('dossier = "/usr/local/bin"', (BIN / s).read_text())

    def test_chemin_de_type_nixos(self):
        self.assistant()
        self.conf(f"NC_ROOT_BIN={self.dossier}")
        self.assertEqual(self.reponses(), f"{self.dossier}/{NOM}")

    def test_lien_vers_un_magasin_sur_est_accepte(self):
        # NixOS : le fichier du dossier est un lien vers le magasin ; le chemin rendu reste celui de la règle sudo
        magasin = self.tmp / "store"
        magasin.mkdir(mode=0o755)
        cible = self.assistant(dossier=magasin)
        (self.dossier / NOM).symlink_to(cible)
        self.conf(f"NC_ROOT_BIN={self.dossier}")
        self.assertEqual(self.reponses(), f"{self.dossier}/{NOM}")

    def test_espaces_et_retour_chariot_sont_retires(self):
        self.assistant()
        self.conf(f"NC_ROOT_BIN=  {self.dossier} \r")
        self.assertEqual(self.reponses(), f"{self.dossier}/{NOM}")

    def test_cle_inconnue_ignoree(self):
        self.assistant()
        self.conf("AUTRE=/tmp/x", f"NC_ROOT_BIN={self.dossier}", "NC_ROOT_BIN_BIS=/tmp/y", "# NC_ROOT_BIN=/tmp/z")
        self.assertEqual(self.reponses(), f"{self.dossier}/{NOM}")

    # ── Refusés (retour au défaut, donc ici « absent ») ──
    def refuse(self, valeur):
        self.assistant()
        self.conf(f"NC_ROOT_BIN={valeur}")
        self.assertEqual(self.reponses(), "", valeur)

    def ecrire_conf(self, octets):
        self.assistant()
        (self.home / ".config/nc/plateforme.conf").write_bytes(octets)

    def test_relecture_memes_reponses(self):
        # Écarts trouvés à la relecture : les trois implémentations doivent répondre pareil
        d = str(self.dossier).encode()
        for nom, octets, attendu in (
                ("retour chariot au milieu", b"NC_ROOT_BIN=" + d[:5] + b"\r" + d[5:] + b"\n", ""),
                ("slash final", b"NC_ROOT_BIN=" + d + b"/\n", ""),
                ("espace insécable", b"NC_ROOT_BIN=" + d + "\u00a0".encode() + b"\n", ""),
                ("octet latin-1 sur une autre ligne", b"# caf\xe9\nNC_ROOT_BIN=" + d + b"\n", f"{self.dossier}/{NOM}"),
                ("tabulations", b"NC_ROOT_BIN=\t" + d + b"\t\r\n", f"{self.dossier}/{NOM}")):
            with self.subTest(nom):
                self.ecrire_conf(octets)
                self.assertEqual(self.reponses(), attendu)

    @unittest.skipUnless(subprocess.run(["locale", "-a"], capture_output=True, text=True).stdout.lower().count("fr_fr.utf"),
                         "pas de locale française")
    def test_lettre_accentuee_refusee_meme_en_francais(self):
        dossier = self.tmp / "bé"
        dossier.mkdir(mode=0o755)
        self.assistant(dossier=dossier)
        self.conf(f"NC_ROOT_BIN={dossier}")
        r = subprocess.run(["sh", "-c", f'. "{SH}"; nc_root_bin {NOM}'], capture_output=True, text=True, timeout=30,
                           env=dict(os.environ, **self.env(), LC_ALL="fr_FR.UTF-8"))
        self.assertEqual(r.stdout.strip(), "")
        self.assertEqual(self.reponses(), "")

    def test_uid_d_essai_ignore_en_root(self):
        # En root, NC_PLATEFORME_UID_ROOT ne compte plus : un fichier qui n'est pas à root est refusé
        self.assistant()
        self.conf(f"NC_ROOT_BIN={self.dossier}")
        faux = self.tmp / "faux"
        faux.mkdir()
        (faux / "id").write_text("#!/bin/sh\necho 0\n")
        (faux / "id").chmod(0o755)
        r = subprocess.run(["sh", "-c", f'. "{SH}"; nc_root_bin {NOM}'], capture_output=True, text=True, timeout=30,
                           env=dict(os.environ, **self.env(), PATH=f"{faux}:{os.environ.get('PATH', '/usr/bin:/bin')}"))
        self.assertEqual(r.stdout.strip(), "")
        with mock.patch.dict(os.environ, self.env()), mock.patch("os.getuid", return_value=0):
            for k, f in self.fn.items():
                self.assertEqual(f(NOM), "", k)

    def test_uid_d_essai_non_numerique(self):
        self.assistant()
        self.conf(f"NC_ROOT_BIN={self.dossier}")
        self.assertEqual(self.reponses(uid_root="abc"), "")

    def test_chemin_relatif(self):
        os.makedirs(self.dossier, exist_ok=True)
        self.refuse("nix-bin")

    def test_segment_point_point(self):
        self.refuse(f"{self.dossier}/../nix-bin")

    def test_segment_point(self):
        self.refuse(f"{self.dossier}/./")

    def test_point_virgule(self):
        self.refuse(f"{self.dossier};id")

    def test_substitution_de_commande(self):
        self.refuse(f"{self.dossier}/$(id)")

    def test_espace_dans_le_chemin(self):
        self.refuse(f"{self.dossier} /x")

    def test_fichier_modifiable_par_le_groupe(self):
        self.assistant(mode=0o775)
        self.conf(f"NC_ROOT_BIN={self.dossier}")
        self.assertEqual(self.reponses(), "")

    def test_fichier_modifiable_par_les_autres(self):
        self.assistant(mode=0o757)
        self.conf(f"NC_ROOT_BIN={self.dossier}")
        self.assertEqual(self.reponses(), "")

    def test_dossier_modifiable_par_le_groupe(self):
        self.assistant()
        self.dossier.chmod(0o775)
        self.conf(f"NC_ROOT_BIN={self.dossier}")
        self.assertEqual(self.reponses(), "")

    def test_fichier_non_exploitable(self):
        self.assistant(mode=0o644)
        self.conf(f"NC_ROOT_BIN={self.dossier}")
        self.assertEqual(self.reponses(), "")

    def test_fichier_pas_a_root(self):
        self.assistant()
        self.conf(f"NC_ROOT_BIN={self.dossier}")
        if os.getuid() == 0:
            self.skipTest("root : le fichier créé est à root")
        self.assertEqual(self.reponses(uid_root=str(os.getuid() + 1)), "")

    def test_lien_vers_un_fichier_de_l_utilisateur(self):
        # le lien est dans un dossier sûr, mais sa cible est dans un dossier que d'autres peuvent modifier
        perso = self.tmp / "perso"
        perso.mkdir(mode=0o777)
        perso.chmod(0o777)
        cible = self.assistant(dossier=perso)
        (self.dossier / NOM).symlink_to(cible)
        self.conf(f"NC_ROOT_BIN={self.dossier}")
        self.assertEqual(self.reponses(), "")

    def test_lien_vers_un_fichier_modifiable(self):
        magasin = self.tmp / "store"
        magasin.mkdir(mode=0o755)
        cible = self.assistant(dossier=magasin, mode=0o777)
        (self.dossier / NOM).symlink_to(cible)
        self.conf(f"NC_ROOT_BIN={self.dossier}")
        self.assertEqual(self.reponses(), "")

    def test_valeur_invalide_puis_valide_garde_la_valide(self):
        # une ligne refusée n'efface pas une ligne bonne ; la dernière bonne gagne
        self.assistant()
        self.conf(f"NC_ROOT_BIN={self.dossier}", "NC_ROOT_BIN=../x;id")
        self.assertEqual(self.reponses(), f"{self.dossier}/{NOM}")

    # ── nc-ile-etat : chemin cherché une fois (limite-bin), puis passé à chaque relecture de la page Système ──
    def ile_etat(self, *args):
        faux = self.tmp / "faux"
        faux.mkdir(exist_ok=True)
        self.journal = self.tmp / "journal"
        for outil in ("stat", "realpath"):   # notent leurs appels, puis font le vrai travail
            vrai = shutil.which(outil)
            (faux / outil).write_text(f'#!/bin/sh\necho {outil} >> "{self.journal}"\nexec {vrai} "$@"\n')
            (faux / outil).chmod(0o755)
        env = dict(os.environ, **self.env(), PATH=f"{faux}:{os.environ['PATH']}")
        return subprocess.run(["bash", str(BIN / "nc-ile-etat"), *args], env=env, capture_output=True, text=True, timeout=60).stdout

    def mesures(self, sortie):
        return dict(l.split("=", 1) for l in sortie.splitlines() if "=" in l)

    def test_ile_etat_chemin_valide(self):
        (self.dossier / NOM).write_text('#!/bin/sh\n[ "$1" = etat ] && echo 1\n')
        (self.dossier / NOM).chmod(0o755)
        self.conf(f"NC_ROOT_BIN={self.dossier}")
        chemin = self.ile_etat("limite-bin").strip()
        self.assertEqual(chemin, f"{self.dossier}/{NOM}")
        self.assertEqual(self.mesures(self.ile_etat("systeme", chemin)).get("protection"), "1")

    def test_ile_etat_chemin_refuse(self):
        (self.dossier / NOM).write_text("#!/bin/sh\necho 1\n")
        (self.dossier / NOM).chmod(0o777)
        self.conf(f"NC_ROOT_BIN={self.dossier}")
        self.assertEqual(self.ile_etat("limite-bin").strip(), "")
        self.assertNotIn("protection", self.mesures(self.ile_etat("systeme", "")))

    def test_deux_relectures_ne_recalculent_pas_le_chemin(self):
        # Énergie invisible : la page Système relit toutes les 2 s ; le chemin, lui, ne se recalcule pas
        (self.dossier / NOM).write_text('#!/bin/sh\n[ "$1" = etat ] && echo 0\n')
        (self.dossier / NOM).chmod(0o755)
        self.conf(f"NC_ROOT_BIN={self.dossier}")
        chemin = self.ile_etat("limite-bin").strip()
        self.assertIn("stat", self.journal.read_text())   # le calcul, une fois
        self.journal.write_text("")
        for _ in range(2):
            self.assertEqual(self.mesures(self.ile_etat("systeme", chemin)).get("protection"), "0")
        self.assertEqual(self.journal.read_text(), "", "aucun stat ni realpath pendant les relectures")
        # côté île : un seul Process « limite-bin » au démarrage, et la relecture passe la valeur gardée
        qml = (REPO / "home/.config/quickshell/nc-ile/Etat.qml").read_text(encoding="utf-8")
        self.assertEqual(qml.count('"nc-ile-etat", "limite-bin"'), 1)
        self.assertRegex(qml, r'Process \{\n\s*running: true\n\s*command: \[etat\.bin \+ "nc-ile-etat", "limite-bin"\]')
        self.assertIn('[bin + "nc-ile-etat", quoi, limiteBin]', qml)

    def test_ile_etat_systeme_refuse_un_chemin_etrange(self):
        piege = self.tmp / "piege"
        piege.write_text(f'#!/bin/sh\ntouch "{self.tmp}/lance"\n')
        piege.chmod(0o755)
        for v in (str(piege), f"{self.dossier}/x;id/nc-limite-charge", "nc-limite-charge", f"{self.dossier}/bé/nc-limite-charge"):
            self.assertNotIn("protection", self.mesures(self.ile_etat("systeme", v)), v)
        self.assertFalse((self.tmp / "lance").exists())

    # ── Les sources ──
    def test_systeme_qml_sans_chemin_en_dur(self):
        qml = (REPO / "home/.config/quickshell/nc-ile/Systeme.qml").read_text(encoding="utf-8")
        self.assertNotIn("/usr/local/bin", qml)
        # le chemin reçu est revérifié avant le lancement : vide ou étrange, rien n'est lancé
        self.assertRegex(qml, r'onClicked: if \(/\^.*nc-limite-charge\$/\.test\(Etat\.limiteBin\)\)\n\s*Etat\.inverser')

    def test_plus_d_appel_en_dur(self):
        # nc-energie, nc-vpn, nc-ile-etat, nc-profile-sync : aucun /usr/local/bin/nc-…-root dans le code exécuté
        for nom in ("nc-energie", "nc-vpn", "nc-ile-etat", "nc-profile-sync"):
            for n, l in enumerate((BIN / nom).read_text(encoding="utf-8").splitlines(), 1):
                if re.search(r"/usr/local/bin/nc-(energie-root|limite-charge|vpn-root)", l):
                    self.assertTrue(l.lstrip().startswith("#") or "installé" in l or "sudoers" in l, f"{nom}:{n}: {l}")

    def test_aucun_os_environ_au_niveau_du_module(self):
        for ligne in Path(__file__).read_text(encoding="utf-8").splitlines():
            if re.match(r"os\.environ(\[|\.(update|setdefault|pop))", ligne):
                self.fail(ligne)


if __name__ == "__main__":
    unittest.main()
