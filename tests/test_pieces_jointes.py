"""Pièces jointes de l'assistant (issue #31) : validation des fichiers, refus des secrets, sélecteur, envoi à JARVIS."""
import base64
import json
import os
from pathlib import Path
import shutil
import types
import unittest
from unittest import mock

from tests import test_assistant as base  # les modules seulement : leurs classes de tests ne sont pas rejouées ici
from tests import test_assistant_page as page

BIN = base.BIN


class PiecesJointes(unittest.TestCase):
    # Même décor que les tests de l'assistant (faux serveur, HOME temporaire), sans rejouer leurs tests
    setUp = base.Assistant.setUp
    arreter = base.Assistant.arreter
    cli = base.Assistant.cli
    settings = base.Assistant.settings

    def preparer(self):
        shutil.copy2(BIN / "nc-bac", self.bin / "nc-bac")
        self.dossier = self.root / "docs"
        self.dossier.mkdir()

    def fichier(self, nom, contenu=b"bonjour", dossier=None):
        p = (dossier or self.dossier) / nom
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(contenu)
        return str(p)

    def refus(self, chemin, *mots):
        with self.assertRaises(self.m.Erreur) as e:
            self.m.preparer_fichiers([chemin])
        for mot in mots:
            self.assertIn(mot, str(e.exception))

    def test_fichier_ordinaire_encode_en_base64(self):
        self.preparer()
        p = self.fichier("note.txt", "café".encode())
        r = self.m.preparer_fichiers([p, p, "file://" + p, "file://localhost" + p])
        self.assertEqual(r, [dict(filename="note.txt", content_base64=base64.b64encode("café".encode()).decode())])

    def test_url_file_decodee_et_hote_refuse(self):
        self.preparer()
        p = self.fichier("mon fichier é.txt")
        url = "file://" + p.replace(" ", "%20").replace("é", "%C3%A9")
        self.assertEqual(self.m.preparer_fichiers([url])[0]["filename"], "mon fichier é.txt")
        self.refus("file://serveur.exemple" + p, "this computer")
        self.refus("fichier-relatif.txt", "absolute")
        self.refus("/tmp/a\0b", "Invalid")

    def test_endroits_et_noms_proteges_refuses_en_nommant_le_fichier(self):
        self.preparer()
        home = self.root
        for rel in (".ssh/config", ".gnupg/x", ".password-store/a.gpg", ".local/share/keyrings/k", ".mozilla/p/logins.json",
                    ".config/nc/ia.conf", ".claude/.credentials.json", ".codex/auth.json", ".netrc", ".git-credentials",
                    ".config/gh/hosts.yml", ".aws/credentials", ".kube/config", ".docker/config.json"):
            with self.subTest(rel=rel):
                self.refus(self.fichier(rel, dossier=home), Path(rel).name, "protected")
        for nom in (".env", ".env.local", "cle.pem", "a.key", "b.p12", "c.pfx", "id_rsa", "id_rsa.pub", "id_ed25519", "id_ecdsa"):
            with self.subTest(nom=nom):
                self.refus(self.fichier(nom), nom, "secrets")
        for chemin in ("/proc/self/environ", "/dev/null", "/sys/kernel/version", "/etc/shadow"):
            with self.subTest(chemin=chemin):
                self.refus(chemin, "protected")

    def test_lien_symbolique_vers_un_secret_refuse_apres_resolution(self):
        self.preparer()
        secret = self.fichier(".ssh/id", dossier=self.root)
        lien = self.dossier / "innocent.txt"
        lien.symlink_to(secret)
        self.refus(str(lien), "innocent.txt", "symbolic link")

    def test_contenu_secret_refuse(self):
        self.preparer()
        self.refus(self.fichier("a.txt", b"-----BEGIN OPENSSH PRIVATE KEY-----\nabc"), "a.txt", "key")
        self.refus(self.fichier("b.md", b"jeton = sk-" + b"a" * 30), "b.md", "key")
        self.refus(self.fichier("c.md", b"ghp_" + b"A" * 25), "c.md")
        self.refus(self.fichier("d.bin", b"\0\1\2 PRIVATE KEY-----"), "d.bin")
        # un binaire qui contient par hasard « sk-… » passe (seul le texte est cherché pour les clés d'API)
        self.assertEqual(len(self.m.preparer_fichiers([self.fichier("e.bin", b"\0sk-" + b"a" * 30)])), 1)

    def test_pas_de_piege_fifo_dossier_peripherique(self):
        self.preparer()
        fifo = self.dossier / "tube"
        os.mkfifo(fifo)
        self.refus(str(fifo), "tube", "regular")                  # ne bloque pas
        self.refus(str(self.dossier), "docs", "regular")
        self.refus(str(self.dossier / "absent"), "absent")

    def test_limites_nombre_taille_total(self):
        self.preparer()
        six = [self.fichier(f"f{i}.txt") for i in range(6)]
        with self.assertRaises(self.m.Erreur):
            self.m.preparer_fichiers(six)
        self.assertEqual(len(self.m.preparer_fichiers(six[:5])), 5)
        gros = self.dossier / "gros.bin"
        with open(gros, "wb") as f:
            f.truncate(20 * 1024 * 1024 + 1)
        self.refus(str(gros), "gros.bin", "20")
        # la taille est vue avant la lecture : aucune lecture d'un fichier trop gros
        with open(self.dossier / "g1.bin", "wb") as f:
            f.truncate(20 * 1024 * 1024)
        with open(self.dossier / "g2.bin", "wb") as f:
            f.truncate(20 * 1024 * 1024)
        un = self.fichier("un.txt", b"x")
        self.assertEqual(len(self.m.preparer_fichiers([str(self.dossier / "g1.bin"), str(self.dossier / "g2.bin")])), 2)
        with self.assertRaises(self.m.Erreur) as e:
            self.m.preparer_fichiers([str(self.dossier / "g1.bin"), str(self.dossier / "g2.bin"), un])
        self.assertIn("40", str(e.exception))

    def test_ia_coupee_aucun_fichier_lu(self):
        self.preparer()
        p = self.fichier("a.txt")
        self.settings("IA_MODE=non\n")
        with unittest.mock.patch.object(self.m.os, "open", side_effect=AssertionError("lu")):
            with self.assertRaises(self.m.Erreur):
                self.m.preparer_fichiers([p])
        r = self.cli("selectionner-fichiers")
        self.assertFalse(json.loads(r.stdout)["ok"])
        r = self.cli("demander", "-f", p, "salut")
        self.assertEqual(r.returncode, 1)
        self.assertFalse(self.server.recus)

    def test_requete_ile_envoie_les_fichiers_sans_chemin_dans_les_sorties(self):
        self.preparer()
        shutil.copy2(BIN / "nc-ia", self.bin / "nc-ia")
        p = self.fichier("rapport.txt", b"contenu")
        r = self.cli("requete-ile", input=json.dumps(dict(session_id="a" * 32, question="lis", fichiers=["file://" + p])) + "\n")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        corps = self.server.recus[-1][3]
        self.assertEqual(corps["files"], [dict(filename="rapport.txt", content_base64=base64.b64encode(b"contenu").decode())])
        self.assertNotIn(p, r.stdout + r.stderr)
        # un fichier refusé : erreur lisible qui nomme le fichier, rien n'est envoyé
        n = len(self.server.recus)
        r = self.cli("requete-ile", input=json.dumps(dict(session_id="a" * 32, question="lis", fichiers=[self.fichier(".env")])))
        sortie = json.loads(r.stdout)
        self.assertFalse(sortie["ok"])
        self.assertIn(".env", sortie["error"])
        self.assertEqual(len(self.server.recus), n)

    def test_fichiers_jamais_vers_l_ia_du_bureau(self):
        self.preparer()
        shutil.copy2(BIN / "nc-ia", self.bin / "nc-ia")
        p = self.fichier("a.txt")
        r = self.cli("requete-ile", input=json.dumps(dict(session_id="a" * 32, question="lis", fichiers=[p], ia_du_bureau=True)))
        self.assertFalse(json.loads(r.stdout)["ok"])
        self.assertFalse(self.server.recus)
        # JARVIS en panne : pas de repli vers une autre IA avec les fichiers
        self.server.reponse = (500, b"x")
        r = self.cli("requete-ile", input=json.dumps(dict(session_id="a" * 32, question="lis", fichiers=[p])))
        self.assertFalse(json.loads(r.stdout)["ok"])
        self.assertNotIn("relais", r.stdout)

    def test_demander_option_fichier(self):
        self.preparer()
        p = self.fichier("a.txt", b"zz")
        r = self.cli("demander", "-f", p, "--fichier", p)
        self.assertEqual(r.returncode, 0, r.stderr)
        corps = self.server.recus[-1][3]
        self.assertEqual(corps["prompt"], "Analyze these files")
        self.assertEqual(len(corps["files"]), 1)
        r = self.cli("demander", "-f", self.fichier(".env"), "salut")
        self.assertEqual(r.returncode, 1)
        self.assertIn(".env", r.stderr)

    def test_variable_hors_de_home_aucune_piece_jointe(self):
        # Point 1 : si les protections déplacées ne se calculent pas, rien ne part (et pas « aucune protection »)
        self.preparer()
        p = self.fichier("ok.txt")
        self.assertEqual(len(self.m.preparer_fichiers([p])), 1)
        for env in (dict(XDG_CONFIG_HOME="/x/cfg", CODEX_HOME="relatif"), dict(CODEX_HOME="relatif"),
                    dict(XDG_CONFIG_HOME="/mnt/ailleurs/cfg")):
            with self.subTest(env=env), mock.patch.dict(os.environ, env):
                self.refus(p, "cannot be computed")

    def test_course_dossier_remplace_par_un_lien_apres_realpath(self):
        # Point 2 : le fichier ouvert doit être celui qui a été vérifié
        self.preparer()
        d = self.dossier / "lien"
        d.mkdir()
        (d / "logins.json").write_bytes(b"innocent")
        secret = self.root / ".mozilla/p"
        secret.mkdir(parents=True)
        (secret / "logins.json").write_bytes(b"SECRET")
        cible, vrai, fait = str(d / "logins.json"), os.path.realpath, []

        def faux(p, *a, **k):
            r = vrai(p, *a, **k)
            if str(p) == cible and not fait:
                fait.append(1)
                shutil.rmtree(d)
                d.symlink_to(secret)
            return r
        with mock.patch.object(self.m.os.path, "realpath", faux):
            self.refus(cible, "changed during the check")
        self.assertTrue(fait)

    def test_limite_totale_sur_les_octets_lus(self):
        # Point 4 : st_size peut mentir ; la limite se vérifie sur ce qui est lu
        self.preparer()
        fichiers = []
        for nom, taille in (("g1.bin", 20 * 1024 * 1024), ("g2.bin", 20 * 1024 * 1024), ("un.txt", 1)):
            with open(self.dossier / nom, "wb") as f:
                f.truncate(taille)
            fichiers.append(str(self.dossier / nom))
        vrai = os.fstat

        def ment(fd):
            r = vrai(fd)
            return types.SimpleNamespace(st_mode=r.st_mode, st_dev=r.st_dev, st_ino=r.st_ino, st_nlink=r.st_nlink, st_size=0)
        with mock.patch.object(self.m.os, "fstat", ment):
            with self.assertRaises(self.m.Erreur) as e:
                self.m.preparer_fichiers(fichiers)
        self.assertIn("40", str(e.exception))

    def test_telegram_jeton_refuse(self):
        self.preparer()
        self.refus(self.fichier("t.txt", b"bot 123456789:AA" + b"x" * 33), "t.txt")

    def test_chemin_relatif_seulement_en_ligne_de_commande(self):
        self.preparer()
        self.fichier("rel.txt")
        ancien = os.getcwd()
        os.chdir(self.dossier)
        self.addCleanup(os.chdir, ancien)
        self.assertEqual(self.m.preparer_fichiers(["rel.txt"], relatif_ok=True)[0]["filename"], "rel.txt")
        self.refus("rel.txt", "absolute")

    def test_transport_http_clair_sur_internet_refuse(self):
        for url, attendu in (("https://exemple.test", True), ("http://127.0.0.1:8000", True), ("http://[::1]:8000", True),
                             ("http://10.0.0.5", True), ("http://172.16.4.1", True), ("http://192.168.1.2:8000", True),
                             ("http://100.101.102.103", True), ("http://pc.tail1234.ts.net", True), ("http://mon-pi.local", True),
                             ("http://203.0.113.5", False), ("http://exemple.test", False), ("http://172.32.0.1", False),
                             ("http://100.128.0.1", False)):
            with self.subTest(url=url):
                self.assertEqual(self.m.transport_sur(url), attendu)
        self.preparer()
        p = self.fichier("a.txt")
        fichiers = self.m.preparer_fichiers([p])
        with self.assertRaises(self.m.Erreur) as e:
            self.m.demander(dict(self.c, URL="http://203.0.113.5:8000", TIMEOUT=2.0), "a" * 32, "q", suivi=False, fichiers=fichiers)
        self.assertIn("plain HTTP", str(e.exception))
        self.assertFalse(self.server.recus)

    def test_proxy_ignore_avec_des_fichiers(self):
        self.preparer()
        fichiers = self.m.preparer_fichiers([self.fichier("a.txt")])
        with mock.patch.dict(os.environ, {"http_proxy": "http://127.0.0.1:9", "HTTP_PROXY": "http://127.0.0.1:9"}):
            self.m.demander(dict(self.c, TIMEOUT=2.0), "a" * 32, "q", suivi=False, fichiers=fichiers)
        self.assertEqual(len(self.server.recus), 1)

    def faux(self, nom, script):
        f = self.bin / nom
        f.write_text("#!/bin/sh\n" + script)
        f.chmod(0o755)

    def test_selecteur_zenity_argv_et_separateur_sur(self):
        self.preparer()
        self.faux("zenity", 'printf "%s\\n" "$@" > "$0.args"\nprintf "a\\nb\\037/c d\\n"\n')
        r = self.cli("selectionner-fichiers")
        self.assertEqual(json.loads(r.stdout), dict(ok=True, files=["a\nb", "/c d"]))
        args = (self.bin / "zenity.args").read_text().split("\n")
        self.assertIn("--file-selection", args)
        self.assertIn("--multiple", args)

    def test_selecteur_annule_kdialog_et_absent(self):
        self.preparer()
        self.faux("zenity", "exit 1\n")
        self.assertEqual(json.loads(self.cli("selectionner-fichiers").stdout), dict(ok=True, files=[]))
        (self.bin / "zenity").unlink()
        a, b = self.fichier("a.txt"), self.fichier("b.txt")
        self.faux("kdialog", f'printf "%s\\n" "{a}" "{b}" /etc/hostname /inexistant\n')
        self.env["PATH"] = str(self.bin)
        # kdialog : seuls les fichiers existants du dossier du premier morceau restent
        self.assertEqual(json.loads(self.cli("selectionner-fichiers").stdout), dict(ok=True, files=[a, b]))
        (self.bin / "kdialog").unlink()
        r = self.cli("selectionner-fichiers")
        sortie = json.loads(r.stdout)
        self.assertFalse(sortie["ok"])
        self.assertIn("zenity", sortie["error"])


@unittest.skipUnless(shutil.which("qs"), "Quickshell requis")
class PiecesJointesIle(unittest.TestCase):
    """L'état et la page de l'île, avec le vrai QML (faux nc-assistant qui note ce qu'il reçoit sur son entrée)."""
    executer = page.PageAssistant.executer

    def test_chemins_urls_et_limites(self):
        self.executer('''
if(etape===0){
 var E=AssistantEtat
 verifier(E.cheminLocal("file:///tmp/a%20b")==="/tmp/a b","url décodée")
 verifier(E.cheminLocal("file://localhost/x")==="/x","localhost")
 verifier(E.cheminLocal("file://serveur/x")==="","hôte distant accepté")
 verifier(E.cheminLocal("http://exemple.test/x")==="","http accepté")
 verifier(E.cheminLocal("relatif.txt")==="","relatif accepté")
 verifier(E.ajouterFichiers(["/tmp/a","/tmp/a","file:///tmp/b","/tmp/c","/tmp/d","/tmp/e"])===5,"cinq attendus")
 verifier(E.fichiersEnAttente.length===5,"doublon gardé")
 verifier(E.ajouterFichiers(["/tmp/f"])===0&&E.erreur!=="","sixième accepté")
 E.retirerFichier(0);verifier(E.fichiersEnAttente.length===4&&E.fichiersEnAttente[0].nom==="b","retrait")
 Qt.quit()
}
''')

    def test_envoi_de_fichiers_seuls_badge_et_restauration(self):
        recus = self.executer('''
if(etape===0){creer();AssistantEtat.ajouterFichiers(["/tmp/doc.txt"]);verifier(page.historiqueOuvert,"historique fermé")
 verifier(trouver(page,"nc-jarvis-attachments-preview").visible,"pastilles absentes")
 verifier(trouver(page,"nc-jarvis-send").enabled,"envoi inactif avec des fichiers seuls")
 AssistantEtat.envoyer();verifier(AssistantEtat.enCours,"pas parti");verifier(AssistantEtat.fichiersEnAttente.length===0,"attente non vidée");etape++}
else if(etape===1&&!AssistantEtat.enCours){verifier(AssistantEtat.erreur==="",AssistantEtat.erreur)
 verifier(AssistantEtat.messages[0].fichiers.join()==="doc.txt","badge absent")
 verifier(trouver(page,"nc-jarvis-message-files")!==null,"badge non affiché")
 AssistantEtat.ajouterFichiers(["/tmp/autre.txt"]);AssistantEtat.brouillon="erreur";AssistantEtat.envoyer();etape++}
else if(etape===2&&!AssistantEtat.enCours){
 verifier(AssistantEtat.fichiersEnAttente.length===1&&AssistantEtat.fichiersEnAttente[0].nom==="autre.txt","fichiers non restaurés")
 verifier(AssistantEtat.brouillon==="erreur","question perdue");Qt.quit()}
''')
        self.assertEqual(recus[0]["payload"]["fichiers"], ["/tmp/doc.txt"])
        self.assertEqual(recus[0]["payload"]["question"], "Analyze these files")
        self.assertEqual(recus[0]["argv"], ["requete-ile"])
        self.assertEqual(recus[1]["payload"]["fichiers"], ["/tmp/autre.txt"])


if __name__ == "__main__":
    unittest.main()


class MotifsPartages(unittest.TestCase):
    """Relecture de la refonte : nc-assistant (pièces jointes) et nc-ia commit doivent voir les mêmes sortes de clés.
    Chaque exemple est vu par les deux listes (lues dans les scripts, sans les charger)."""
    EXEMPLES = ("sk-proj-AbCdEf0123456789AbCdEf0123", "ghp_" + "a1B2" * 9, "github_pat_" + "a1B2_" * 6,
                "AKIAABCDEFGHIJKLMNOP", "xoxb-0123456789-abcdefghij", "AIzaSyA" + "b1C2d3E4f5" * 3 + "xyz",
                "gsk_" + "Ab12" * 8, "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dBjftJeZ4CVPmB92K27uhbUJU1p1r_wW1gFWFOEjXk")

    def test_chaque_cle_vue_des_deux_cotes(self):
        import re
        a = (BIN / "nc-assistant").read_text()
        i = a.index("CLE_API = re.compile(")
        cle_api = eval(a[i + len("CLE_API = "):a.index(")\n", i) + 1], {"re": re})
        n = (BIN / "nc-ia").read_text()
        j = n.index("COMMIT_MOTIFS_SECRETS = (")
        motifs = eval(n[j + len("COMMIT_MOTIFS_SECRETS = "):n.index("\n)\n", j) + 2], {"re": re})
        for e in self.EXEMPLES:
            with self.subTest(e=e[:12]):
                self.assertTrue(cle_api.search(e.encode()), "nc-assistant ne voit pas cette clé")
                self.assertTrue(any(m.search(e) for _, m in motifs), "nc-ia commit ne voit pas cette clé")
