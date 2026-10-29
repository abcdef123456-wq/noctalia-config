"""nc-vpn : Proton par sa CLI officielle `protonvpn` (paquet proton-vpn-cli 1.0.5). Un faux `protonvpn` note ses arguments et rend des
sorties conformes aux sources (commands/account.py, server.py, location_discovery.py, __init__.py), avec un faux e-mail, un faux nom
de compte, un faux jeton et une fausse IP qui ne doivent ressortir NULLE PART. Trois états ; pays seulement à « pret », traduits
depuis le code ISO et triés ; connect en argv exact ; code pays refusé sans appel ; verrou ; kill switch ; appli graphique ouverte
(la CLI refuse de tourner avec elle) ; login par l'appli ou par kitty `protonvpn signin` ; repli sur l'état « pilote_appli ».
PATH = faux-bin seul : jamais le vrai protonvpn, ni protonvpn-app, ni kitty."""
import fcntl
import json
import os
import subprocess
import sys
import time
import unittest
from unittest import mock

from tests._vpn_faux import BaseVpn, BIN, connexions
from tests.test_nc_vpn_securite_v6 import FAUX_SUDO, charger

EMAIL = "alice.faux@example.invalid"
COMPTE = "alice-faux-test"
JETON = "pvpn_FAUXJETON0123456789abcdefghij"
IP = "192.0.2.77"
SECRETS = (EMAIL, COMPTE, JETON, IP, "alice")

INFO_OK = f"Account: '{COMPTE}'\nEmail: {EMAIL}\nToken: {JETON}\n"
INFO_SANS = "Account: 'None'\n"
PAYS = ("Server list is outdated, updating... This may take a moment.\n"
        "Country        Code\n"
        "-------------  ------\n"
        "Sweden         SE\n"
        "France         FR\n"
        "Germany        DE\n"
        "Atlantis       ZZ\n")
AUTORISEES = {"info", "countries", "connect", "disconnect", "signin"}     # jamais « status » : il réapplique le kill switch de Proton
APPLI = ("Error: Proton VPN desktop app is currently running\n"
         "The CLI and GUI cannot run simultaneously. Please close the GUI application and try again.\n")
CONNECTE_OK = f"Connected to FR#7 in Paris, France. \nYour new IP address is {IP}.\n"
UP = "55555555-5555-4555-8555-555555555555"


def lire(r):
    return r.stdout + r.stderr


class ProtonCli(BaseVpn):
    def cli(self, info=INFO_OK, pays=PAYS, **autres):
        conf = {"info": {"out": info}, "countries": {"out": pays}, "status": {"out": "Status: Disconnected\n", "err": "BOOM-status", "code": 99},
                "connect": {"out": CONNECTE_OK}, "disconnect": {"out": "Disconnected.\n"}}
        conf.update(autres)
        self.poser("protonvpn", conf)
        self.addCleanup(self.aucune_commande_interdite)

    def aucune_commande_interdite(self):
        """Quoi qu'ait fait le test, aucune sous-commande en dehors de la liste (surtout pas `status`) n'a été lancée."""
        vus = {a[0] for a in self.appels_de("protonvpn") if a}
        self.assertLessEqual(vus, AUTORISEES)

    def fiche(self, verifier=True, **env):
        r = self.seul(*(("fournisseurs-json", "--verifier-proton") if verifier else ("fournisseurs-json",)), **env)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.vu = lire(r)
        for s in SECRETS:
            self.assertNotIn(s, self.vu, s)
        return next(f for f in json.loads(r.stdout)["fournisseurs"] if f["id"] == "proton")

    def pas_de_secret(self, r):
        for s in SECRETS:
            self.assertNotIn(s, lire(r), s)

    def killswitch_actif(self):
        f = self.r / "faux-bin" / "sudo"
        f.write_text(FAUX_SUDO)
        f.chmod(0o755)
        h = self.r / "nc-vpn-root"
        h.write_text("#!/bin/sh\n")
        (self.r / "ks-etat").write_text("actif")
        return str(h)

    # ── états ──
    def test_absent_sans_cli_ni_appli(self):
        f = self.fiche()
        self.assertEqual(f["etat"], "absent")
        self.assertNotIn("pays", f)

    def test_sans_compte(self):
        self.cli(info=INFO_SANS)
        f = self.fiche()
        self.assertEqual((f["etat"], f["peut_login"], f["connecte"], f["pilotage"]), ("sans_compte", True, False, "direct"))
        self.assertNotIn("pays", f)
        self.assertEqual(self.appels_de("protonvpn"), [["info"]])              # ni la liste des pays sans compte

    def test_pret_pays_seulement_a_pret_traduits_et_tries(self):
        self.cli()
        f = self.fiche(NC_LANGUE="fr")
        self.assertEqual((f["etat"], f["connecte"], f["pays_actif"], f["pilotage"]), ("pret", False, "", "direct"))
        self.assertEqual(f["pays"], [{"code": "DE", "nom": "Allemagne"}, {"code": "FR", "nom": "France"}, {"code": "SE", "nom": "Suède"}])
        self.assertEqual(self.appels_de("protonvpn"), [["info"], ["countries", "list"]])
        en = self.fiche(verifier=False, NC_LANGUE="en")                         # lecture automatique : le dernier relevé, aucun appel de plus
        self.assertEqual([p["nom"] for p in en["pays"]], ["France", "Germany", "Sweden"])
        self.assertEqual(self.appels_de("protonvpn"), [["info"], ["countries", "list"]])

    def test_tunnel_actif_et_pays_lus_dans_networkmanager(self):
        self.cli()
        for nom, cc in (("ProtonVPN SE#12", "SE"), ("ProtonVPN CH-US#1", "US"), ("ProtonVPN US-CA#12", "US"), ("ProtonVPN UK#3", "GB")):
            (self.r / "etat.json").write_text(json.dumps(connexions() + [dict(uuid=UP, type="wireguard", active=True, dev="proton0", nom=nom)]))
            f = self.fiche()
            self.assertEqual((f["etat"], f["connecte"], f["pays_actif"]), ("pret", True, cc), nom)
            actives = json.loads(self.seul("etat-json").stdout)["actives"]
            self.assertEqual([c["pays"] for c in actives if "Proton" in c["nom"]], [cc], nom)        # même règle pour la carte principale
            self.assertEqual(charger().pays_proton_nom(nom), cc, nom)

    def test_pays_du_serveur_secure_core_et_gratuit(self):
        mod = charger()
        for nom, cc in (("IT#23", "IT"), ("CH-IT#1", "IT"), ("US-FREE#5", "US"), ("XX#1", ""), ("", ""), ("US-CA#12", "US"),
                        ("CH-US#1", "US"), ("IS-FR#2", "FR"), ("SE-DE#3", "DE"), ("UK#3", "GB"), ("CH#1", "CH"), ("SE-FREE#1", "SE")):
            self.assertEqual(mod.proton_pays_serveur(nom), cc, nom)

    def test_lectures_automatiques_ne_lancent_jamais_protonvpn(self):
        """Événement NetworkManager simulé, relire(), indicateur, fournisseurs-json sans l'action explicite : aucun appel."""
        self.cli()
        (self.r / "etat.json").write_text(json.dumps(connexions() + [dict(uuid=UP, type="wireguard", active=True, dev="proton0", nom="ProtonVPN FR#12")]))
        for args in (("fournisseurs-json",), ("indicateur", "--json"), ("etat-json",), ("fournisseurs-json",)):
            r = self.seul(*args)
            self.assertEqual(r.returncode, 0, args)
        self.assertEqual(self.appels_de("protonvpn"), [])
        f = self.fiche(verifier=False)                                           # pas encore vérifié : dit d'ouvrir l'onglet, sans appel
        self.assertEqual((f["etat"], f["probleme"], f["connecte"]), ("sans_compte", "non_verifie", False))
        self.assertEqual(self.appels_de("protonvpn"), [])

    def test_verification_explicite_ecrit_un_cache_sans_identifiant(self):
        self.cli()
        self.fiche()
        cache = (self.r / "run" / "nc-vpn-proton.json").read_text()
        for s in SECRETS:
            self.assertNotIn(s, cache)
        self.assertEqual(json.loads(cache)["pays"], ["SE", "FR", "DE"])
        self.assertEqual(oct((self.r / "run" / "nc-vpn-proton.json").stat().st_mode & 0o777), "0o600")
        f = self.fiche(verifier=False, NC_LANGUE="fr")
        self.assertEqual(f["etat"], "pret")

    def test_verification_refusee_si_le_verrou_est_tenu(self):
        self.cli()
        verrou = os.open(str(self.r / "run" / "nc-vpn.lock"), os.O_RDWR | os.O_CREAT, 0o600)
        self.addCleanup(os.close, verrou)
        fcntl.flock(verrou, fcntl.LOCK_EX | fcntl.LOCK_NB)
        f = self.fiche()
        self.assertEqual(f["probleme"], "non_verifie")
        self.assertEqual(self.appels_de("protonvpn"), [])
        fcntl.flock(verrou, fcntl.LOCK_UN)
        self.assertEqual(self.fiche()["etat"], "pret")
        self.assertEqual(self.appels_de("protonvpn"), [["info"], ["countries", "list"]])
        fcntl.flock(verrou, fcntl.LOCK_EX | fcntl.LOCK_NB)
        self.fiche()                                                             # verrou tenu : le relevé précédent sert, rien de plus
        self.assertEqual(len(self.appels_de("protonvpn")), 2)

    def test_delai_de_la_liste_des_pays_compte_valide_et_reessayer(self):
        self.cli(countries={"dormir": 4, "out": PAYS})
        f = self.fiche(NC_VPN_PROTON_DELAI_PAYS="1")
        self.assertEqual((f["etat"], f["pays"], f["pays_probleme"], f["probleme"]), ("pret", [], "delai", ""))   # le compte reste valide
        self.assertEqual(self.appels_de("protonvpn"), [["info"], ["countries", "list"]])
        auto = self.fiche(verifier=False)                                        # lecture automatique : même constat, aucun appel de plus
        self.assertEqual((auto["etat"], auto["pays_probleme"]), ("pret", "delai"))
        self.assertEqual(len(self.appels_de("protonvpn")), 2)
        self.cli()                                                               # « Réessayer » : la vérification explicite, la liste revient
        f = self.fiche()
        self.assertEqual((f["pays_probleme"], [p["code"] for p in f["pays"]]), ("", ["DE", "FR", "SE"]))
        self.assertEqual(self.fiche(verifier=False)["pays_probleme"], "")

    def test_menage_des_dossiers_abandonnes_ne_touche_jamais_au_cache_proton(self):
        """nettoyer_abandonnes ne vise que des DOSSIERS nc-vpn-* : le cache Proton (un fichier) et le verrou restent, même très vieux."""
        self.cli()
        self.fiche()
        run = self.r / "run"
        cache, verrou = run / "nc-vpn-proton.json", run / "nc-vpn.lock"
        vieux = run / "nc-vpn-abandonne"
        vieux.mkdir(mode=0o700)
        verrou.touch()
        avant = cache.read_text()
        for chemin in (cache, verrou, vieux):
            os.utime(chemin, (time.time() - 7200, time.time() - 7200))
        with mock.patch.dict(os.environ, {"XDG_RUNTIME_DIR": str(run)}):
            charger().nettoyer_abandonnes(600)
        self.assertTrue(cache.is_file())
        self.assertEqual(cache.read_text(), avant)
        self.assertTrue(verrou.exists())
        self.assertFalse(vieux.exists(), "le ménage reste actif pour les vrais dossiers abandonnés")

    def test_verification_refusee_pendant_la_montee_du_tunnel(self):
        self.cli()
        (self.r / "etat.json").write_text(json.dumps(connexions() + [dict(uuid=UP, type="wireguard", active=True, dev="proton0",
                                                                           nom="ProtonVPN FR#12", etat="activating")]))
        f = self.fiche()
        self.assertEqual(f["probleme"], "non_verifie")
        self.assertEqual(self.appels_de("protonvpn"), [])

    def test_tunnel_nm_proton_compte_aussi_sans_doublon_dans_la_fiche(self):
        self.cli()
        (self.r / "etat.json").write_text(json.dumps(connexions() + [dict(uuid=UP, type="wireguard", active=True, dev="proton0", nom="ProtonVPN FR#12")]))
        f = self.fiche()
        self.assertEqual((f["etat"], f["connecte"], f["pays_actif"]), ("pret", True, "FR"))
        self.assertEqual(len([1 for c in json.loads(self.seul("etat-json").stdout)["actives"] if "Proton" in c["nom"]]), 1)

    def test_session_expiree_est_sans_compte(self):
        self.poser("protonvpn", {"info": {"out": INFO_OK}, "countries": {"err": "Error: Authentication required to view complete country list.\n", "code": 2}})
        f = self.fiche()
        self.assertEqual((f["etat"], f["peut_login"]), ("sans_compte", True))
        self.assertNotIn("pays", f)

    def test_info_illisible_ou_en_echec(self):
        self.cli(info="quelque chose d'inattendu\n")
        f = self.fiche()
        self.assertEqual((f["etat"], f["probleme"], f["peut_login"]), ("sans_compte", "illisible", False))
        self.regler("protonvpn", {"info": {"out": INFO_OK, "code": 1}})
        self.assertEqual(self.fiche()["probleme"], "illisible")

    def test_appli_graphique_ouverte_la_cli_refuse(self):
        self.cli(info=APPLI)
        f = self.fiche()
        self.assertEqual((f["etat"], f["probleme"], f["pilotage"], f["peut_login"]), ("pilote_appli", "appli_ouverte", "appli", True))
        self.assertIn("Ferme l'application Proton VPN pour piloter depuis l'île", f["message"])
        self.assertNotIn("pays", f)
        self.assertEqual(self.appels_de("protonvpn"), [["info"]])

    def test_repli_pilote_appli_sans_cli(self):
        self.poser("protonvpn-app", {})
        f = self.fiche()
        self.assertEqual((f["etat"], f["pilotage"]), ("pilote_appli", "appli"))
        self.assertEqual(f["probleme"], "")

    def test_cli_prime_sur_l_appli(self):
        self.poser("protonvpn-app", {})
        self.cli(info=INFO_SANS)
        self.assertEqual(self.fiche()["etat"], "sans_compte")

    def test_identifiants_jamais_ressortis_nulle_part(self):
        for kw in ({}, {"info": INFO_SANS}, {"info": APPLI}):
            self.cli(**kw)
            self.fiche()
        self.cli(connect={"out": "Error: " + EMAIL + " " + COMPTE + " " + JETON + " " + IP + "\n", "code": 1})
        for args in (("fournisseur", "proton", "connecter", "FR"), ("fournisseur", "proton", "deconnecter")):
            self.pas_de_secret(self.seul(*args))
        r = self.seul("fournisseur", "proton", "connecter", "FR")
        self.assertEqual(r.returncode, 1)
        self.assertIn("refusé", r.stderr)

    # ── actions ──
    def test_connecter_argv_exact(self):
        self.cli()
        r = self.seul("fournisseur", "proton", "connecter", "FR")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.appels_de("protonvpn"), [["connect", "--country", "FR"]])
        self.assertIn("(FR)", r.stdout)
        self.pas_de_secret(r)

    def test_code_invalide_refuse_sans_appel(self):
        self.cli()
        self.poser("protonvpn-app", {})
        for cc in ("fr", "FRA", "F", "", "ZZ", "F1", "--random", "FR;ls"):
            r = self.seul("fournisseur", "proton", "connecter", cc)
            self.assertEqual(r.returncode, 1, cc)
        time.sleep(0.3)
        self.assertEqual(self.appels_de("protonvpn"), [])
        self.assertEqual(self.appels_de("protonvpn-app"), [])

    def test_deconnecter_argv_exact(self):
        self.cli()
        r = self.seul("fournisseur", "proton", "deconnecter")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.appels_de("protonvpn"), [["disconnect"]])

    def test_deconnexion_code_non_nul_confirmee_par_networkmanager(self):
        """« Disconnected. » avec un code non nul : succès seulement si NetworkManager confirme qu'aucun tunnel Proton n'est actif."""
        proton = dict(uuid=UP, type="wireguard", active=True, dev="proton0", nom="ProtonVPN FR#12")
        self.cli(disconnect={"out": "Disconnected.\n", "code": 3})
        # 1. NetworkManager confirme : aucun tunnel Proton actif (les autres tunnels ne comptent pas) -> succès
        r = self.seul("fournisseur", "proton", "deconnecter")
        self.assertEqual(r.returncode, 0, r.stderr)
        # 2. un tunnel Proton est encore actif -> échec
        (self.r / "etat.json").write_text(json.dumps(connexions() + [proton]))
        r = self.seul("fournisseur", "proton", "deconnecter")
        self.assertEqual(r.returncode, 1)
        self.assertIn("refusé", r.stderr)
        # 2 bis. un tunnel Proton en montée -> échec aussi
        (self.r / "etat.json").write_text(json.dumps(connexions() + [dict(proton, etat="activating")]))
        self.assertEqual(self.seul("fournisseur", "proton", "deconnecter").returncode, 1)
        # 3. NetworkManager muet ou en erreur -> échec, jamais un succès
        (self.r / "etat.json").write_text(json.dumps(connexions()))
        r = self.seul("fournisseur", "proton", "deconnecter", NM_ARRETE="1")
        self.assertEqual(r.returncode, 1)
        # 3 bis. nmcli absent du PATH -> échec
        sans_nmcli = self.r / "bin-sans-nmcli"
        sans_nmcli.mkdir()
        (sans_nmcli / "protonvpn").symlink_to(self.r / "faux-bin" / "protonvpn")
        (sans_nmcli / "python3").symlink_to(sys.executable)
        self.assertEqual(self.vpn("fournisseur", "proton", "deconnecter", PATH=str(sans_nmcli)).returncode, 1)
        # 4. code 0 : succès comme avant, sans dépendre de NetworkManager
        self.cli()
        self.assertEqual(self.seul("fournisseur", "proton", "deconnecter", NM_ARRETE="1").returncode, 0)
        # code non nul SANS le message de succès : jamais un succès, même si NetworkManager ne voit plus de tunnel
        self.cli(disconnect={"out": "Error: boom\n", "code": 3})
        self.assertEqual(self.seul("fournisseur", "proton", "deconnecter").returncode, 1)

    def test_deconnexion_second_appel_nmcli_en_erreur_ou_en_montee_seule_est_un_echec(self):
        self.cli(disconnect={"out": "Disconnected.\n", "code": 3})
        # 1er appel : aucun Proton actif ; 2e appel (STATE,NAME) en erreur -> pas confirmé -> échec
        r = self.seul("fournisseur", "proton", "deconnecter", NM_ECHEC_STATE="1")
        self.assertEqual(r.returncode, 1)
        self.assertIn("refusé", r.stderr)
        # seule la branche « en montée » : rien d'actif au 1er appel, mais le 2e appel voit une connexion Proton en montée -> échec
        r = self.seul("fournisseur", "proton", "deconnecter", NM_ETAT_EXTRA="activating:ProtonVPN FR#12")
        self.assertEqual(r.returncode, 1)
        # contrôle : sans ces anomalies, le même cas réussit
        self.assertEqual(self.seul("fournisseur", "proton", "deconnecter").returncode, 0)

    def test_verrou_un_changement_a_la_fois(self):
        self.cli(connect={"dormir": 3, "out": CONNECTE_OK})
        env = self.env(PATH=str(self.r / "faux-bin"))
        p1 = subprocess.Popen([sys.executable, str(BIN), "fournisseur", "proton", "connecter", "FR"], env=env, stdin=subprocess.DEVNULL,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            for _ in range(100):
                if any(a[:1] == ["connect"] for a in self.appels_de("protonvpn")):
                    break
                time.sleep(0.1)
            for args in (("fournisseur", "proton", "connecter", "DE"), ("fournisseur", "proton", "deconnecter")):
                r = self.seul(*args)
                self.assertEqual(r.returncode, 1, args)
                self.assertIn("autre changement", r.stderr)
            self.assertNotIn(["disconnect"], self.appels_de("protonvpn"))
        finally:
            p1.wait(timeout=20)
            p1.stdout.close()
            p1.stderr.close()
        self.assertEqual(p1.returncode, 0)

    def test_killswitch_actif_refuse_la_connexion(self):
        self.cli()
        h = self.killswitch_actif()
        r = self.seul("fournisseur", "proton", "connecter", "FR", NC_VPN_ROOT=h)
        self.assertEqual(r.returncode, 1)
        self.assertIn("kill switch", r.stderr)
        self.assertEqual(self.appels_de("protonvpn"), [])
        j = self.seul("fournisseur", "proton", "deconnecter", NC_VPN_ROOT=h)          # couper reste permis
        self.assertEqual(j.returncode, 0, j.stderr)
        (self.r / "ks-etat").write_text("inactif")
        self.assertEqual(self.seul("fournisseur", "proton", "connecter", "FR", NC_VPN_ROOT=h).returncode, 0)

    def test_appli_ouverte_message_clair_aucune_fermeture(self):
        self.cli(connect={"out": APPLI}, disconnect={"out": APPLI})
        for args, mot in ((("connecter", "FR"), "connect"), (("deconnecter",), "disconnect")):
            r = self.seul("fournisseur", "proton", *args)
            self.assertEqual(r.returncode, 1, args)
            self.assertIn("Ferme l'application Proton VPN pour piloter depuis l'île", r.stderr)
            self.assertNotIn("Error: Proton VPN desktop", r.stderr)               # message à nous, pas la sortie brute
        self.assertEqual([a[0] for a in self.appels_de("protonvpn")], ["connect", "disconnect"])
        self.assertEqual(self.appels(), [])                                      # pas de nmcli : rien n'est coupé de force

    def test_refus_de_la_cli_messages_prevus(self):
        cas = (("Error: Location selection is not available on the free plan. Please use 'protonvpn connect'", "payant"),
               ("Error: Authentication required.Please sign in with 'protonvpn signin' before connecting.", "Aucun compte"),
               ("Error: Invalid country code 'FR'. Please use a valid country code.", "ne propose pas"),
               ("Error: No servers found matching criteria.", "ne propose pas"),
               ("Error: Connection failed. Try connecting to a different server.", "refusé"),
               ("", "refusé"))                                                   # code 0 sans « Connected to » (palier supérieur) : refus
        for brut, attendu in cas:
            self.cli(connect={"err": brut + "\n", "code": 0 if brut == "" else 2})
            r = self.seul("fournisseur", "proton", "connecter", "FR")
            self.assertEqual(r.returncode, 1, brut)
            self.assertIn(attendu, r.stderr, brut)
            self.assertNotIn("protonvpn connect", r.stderr)

    # ── login ──
    def attendre(self, nom):
        for _ in range(50):
            if self.appels_de(nom):
                break
            time.sleep(0.1)
        return self.appels_de(nom)

    def test_login_ouvre_l_appli_si_elle_est_installee(self):
        self.cli(info=INFO_SANS)
        self.poser("protonvpn-app", {})
        self.poser("kitty", {})
        r = self.seul("fournisseur", "proton", "login")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.attendre("protonvpn-app"), [[]])
        self.assertEqual(self.appels_de("kitty"), [])
        self.assertEqual(self.appels_de("protonvpn"), [])

    def test_login_sans_appli_ouvre_kitty_avec_protonvpn_signin(self):
        self.cli(info=INFO_SANS)
        self.poser("kitty", {})
        r = self.seul("fournisseur", "proton", "login", NC_LANGUE="fr")
        self.assertEqual(r.returncode, 0, r.stderr)
        (appel,) = self.appels_de("kitty")
        i = appel.index("sh")
        self.assertEqual(appel[:1], ["--hold"])
        self.assertEqual(appel[i:i + 2], ["sh", "-c"])
        script, invite, exe = appel[i + 2], appel[i + 4], appel[i + 5]
        self.assertEqual(appel[i + 3], "sh")
        self.assertTrue(exe.endswith("/protonvpn"))
        self.assertIn('"$2" signin -- "$u"', script)
        self.assertEqual(len(appel), i + 6)
        self.assertNotIn("Proton", script)                                        # script fixe : le texte arrive en argument
        self.assertIn("Nom de compte", invite)
        self.assertEqual(self.appels_de("protonvpn"), [])                         # nous ne lançons pas signin nous-mêmes
        self.pas_de_secret(r)

    def test_login_signin_obligatoire_nom_demande_dans_le_terminal(self):
        """Source : `signin USERNAME` (argument obligatoire) : le script lit le nom dans le terminal puis le passe à signin."""
        self.cli(info=INFO_SANS)
        faux = self.r / "faux-bin" / "kitty"
        faux.write_text("#!/bin/sh\n"
                        'while [ "$1" != "-c" ]; do shift; done\n'
                        'shift; script=$1; shift; shift\n'                        # script ; puis « sh » (nom du script) retiré
                        'exec /bin/sh -c "$script" sh "$@" < "$FAUX_DIR/saisie"\n')
        faux.chmod(0o755)
        (self.r / "saisie").write_text(COMPTE + "\n")                           # ce que l'utilisateur tape dans le terminal
        r = self.seul("fournisseur", "proton", "login")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.appels_de("protonvpn"), [["signin", "--", COMPTE]])

    def test_login_sans_kitty_ni_appli(self):
        self.cli(info=INFO_SANS)
        r = self.seul("fournisseur", "proton", "login")
        self.assertEqual(r.returncode, 1)
        self.assertIn("protonvpn signin", r.stderr)
        self.assertEqual(self.appels_de("protonvpn"), [])

    def test_login_ni_cli_ni_appli(self):
        r = self.seul("fournisseur", "proton", "login")
        self.assertEqual(r.returncode, 1)
        self.assertIn("pas installé", r.stderr)

    def test_aucun_programme_ferme_ni_tue(self):
        bloc = BIN.read_text(encoding="utf-8").split("def proton_lire_cli")[1].split('API_FOURNISSEURS["proton"]')[0]
        for nom in ("pkill", "killall", "killpg", "os.kill", "taskkill"):
            self.assertNotIn(nom, bloc)


if __name__ == "__main__":
    unittest.main()
