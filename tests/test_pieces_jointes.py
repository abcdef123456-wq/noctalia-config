"""Pièces jointes de l'assistant (issue #31) : validation des fichiers, refus des secrets, sélecteur, envoi à JARVIS."""
import base64
import json
import os
from pathlib import Path
import shutil
import unittest

from tests import test_assistant as base
from tests import test_assistant_page as page
from tests import test_assistant as base  # le module seulement : sa classe de tests ne doit pas être rejouée ici

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
        self.refus(str(lien), "id", "protected")

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
        self.faux("kdialog", 'printf "/x\\n/y\\n"\n')
        self.env["PATH"] = str(self.bin)
        self.assertEqual(json.loads(self.cli("selectionner-fichiers").stdout), dict(ok=True, files=["/x", "/y"]))
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
