"""nc-vpn : Proton installé en Flatpak (com.protonvpn.www). Un FAUX flatpak (jamais le vrai) note ses arguments (appels-flatpak.jsonl)
et, pour `run --command=protonvpn`, rejoue les réponses de protonvpn.json comme le faux protonvpn des autres tests. Ordre : CLI native
d'abord ; toutes les gardes restent (aucune lecture automatique, jamais `status`) ; l'appli Flatpak ouverte se voit par `flatpak ps`.
PATH = faux-bin seul : jamais le vrai flatpak, ni protonvpn, ni kitty."""
import json
import os
import stat
import subprocess
import sys
import time
import unittest
from unittest import mock

from tests._vpn_faux import BaseVpn, BIN
from tests.test_nc_vpn_indicateur import charger
from tests.test_nc_vpn_proton_cli import APPLI, COMPTE, CONNECTE_OK, EMAIL, INFO_OK, INFO_SANS, IP, JETON, PAYS, SECRETS, lire

APP = "com.protonvpn.www"

# Réponses de flatpak.json : {"installe": ["--user", "--system"], "ps": "texte", "ps_code": 0}. `run … APP ARGS` : les ARGS vont dans
# appels-protonvpn.jsonl et la réponse vient de protonvpn.json (voir FAUX_CLIENT).
FAUX_FLATPAK = r'''#!@PYTHON@
import json, os, sys, time
from pathlib import Path
R = Path(os.environ["FAUX_DIR"])
a = sys.argv[1:]
with (R / "appels-flatpak.jsonl").open("a") as f: f.write(json.dumps(a) + "\n")
conf = json.loads((R / "flatpak.json").read_text()) if (R / "flatpak.json").exists() else {}
if a[:1] == ["info"]:
    sys.stdout.write("ID: com.protonvpn.www\nSecret: Hors-sujet-faux\n")
    sys.exit(0 if (a[1] in conf.get("installe", []) and a[-1] == "com.protonvpn.www") else 1)
if a[:1] == ["ps"]:
    sys.stdout.write(conf.get("ps", "Application\n")); sys.exit(conf.get("ps_code", 0))
if a[:1] == ["run"]:
    i = a.index("com.protonvpn.www")
    cmd = [x for x in a[1:i] if x.startswith("--command=")]
    args = a[i + 1:]
    nom = cmd[0].split("=", 1)[1] if cmd else "protonvpn-app"
    with (R / ("appels-" + nom + ".jsonl")).open("a") as f: f.write(json.dumps(args) + "\n")
    c = json.loads((R / (nom + ".json")).read_text()) if (R / (nom + ".json")).exists() else {}
    c = c.get(args[0] if args else "", c.get("*", {}))
    if c.get("dormir"): time.sleep(c["dormir"])
    sys.stdout.write(c.get("out", "")); sys.stderr.write(c.get("err", ""))
    sys.exit(c.get("code", 0))
sys.exit(1)
'''


class ProtonFlatpak(BaseVpn):
    def flatpak(self, installe=("--user",), ps="Application\n", cli=None, **conf):
        f = self.r / "faux-bin" / "flatpak"
        f.write_text(FAUX_FLATPAK.replace("@PYTHON@", sys.executable))
        f.chmod(0o755)
        (self.r / "flatpak.json").write_text(json.dumps(dict(installe=list(installe), ps=ps, **conf)))
        c = {"info": {"out": INFO_OK}, "countries": {"out": PAYS}, "status": {"out": "x", "err": "BOOM-status", "code": 99},
             "connect": {"out": CONNECTE_OK}, "disconnect": {"out": "Disconnected.\n"}}
        c.update(cli or {})
        self.regler("protonvpn", c)

    def appels_flatpak(self):
        return self.appels_de("flatpak")

    def runs(self):
        return [a for a in self.appels_flatpak() if a[0] == "run"]

    def fiche(self, verifier=True, **env):
        r = self.seul(*(("fournisseurs-json", "--verifier-proton") if verifier else ("fournisseurs-json",)), **env)
        self.assertEqual(r.returncode, 0, r.stderr)
        for s in SECRETS + ("Hors-sujet-faux",):
            self.assertNotIn(s, lire(r), s)
        return next(f for f in json.loads(r.stdout)["fournisseurs"] if f["id"] == "proton")

    def test_ordre_user_puis_system_et_argv_exacts(self):
        self.flatpak(installe=("--system",))
        f = self.fiche()
        self.assertEqual((f["etat"], f["pilotage"]), ("pret", "direct"))
        self.assertEqual(self.appels_flatpak()[:2], [["info", "--user", APP], ["info", "--system", APP]])
        self.assertEqual(self.runs(), [["run", "--system", "--command=protonvpn", APP, "info"],
                                       ["run", "--system", "--command=protonvpn", APP, "countries", "list"]])
        self.assertEqual(self.appels_de("protonvpn"), [["info"], ["countries", "list"]])
        self.assertEqual([p["code"] for p in f["pays"]], ["DE", "FR", "SE"])

    def test_installation_utilisateur(self):
        self.flatpak(installe=("--user",))
        self.assertEqual(self.fiche()["etat"], "pret")
        self.assertEqual(self.appels_flatpak()[0], ["info", "--user", APP])
        self.assertNotIn(["info", "--system", APP], self.appels_flatpak())          # trouvé au premier essai
        self.assertTrue(all(a[1] == "--user" for a in self.runs()))

    def test_sans_compte_dans_le_flatpak(self):
        self.flatpak(cli={"info": {"out": INFO_SANS}})
        f = self.fiche()
        self.assertEqual((f["etat"], f["peut_login"]), ("sans_compte", True))
        self.assertEqual(self.appels_de("protonvpn"), [["info"]])

    def test_flatpak_absent_ou_appli_non_installee_reste_absent_et_silencieux(self):
        self.assertEqual(self.fiche()["etat"], "absent")                             # aucun flatpak dans PATH
        self.flatpak(installe=())
        f = self.fiche()
        self.assertEqual(f["etat"], "absent")
        self.assertEqual(self.runs(), [])

    def test_cli_native_prime_sur_le_flatpak(self):
        self.flatpak()
        self.poser("protonvpn", {"info": {"out": INFO_SANS}})
        self.assertEqual(self.fiche()["etat"], "sans_compte")
        self.assertEqual(self.appels_flatpak(), [])                                  # le Flatpak n'est même pas interrogé
        self.assertEqual(self.appels_de("protonvpn"), [["info"]])

    def test_lectures_automatiques_ne_lancent_ni_info_ni_countries(self):
        self.flatpak()
        for args in (("fournisseurs-json",), ("indicateur", "--json"), ("etat-json",)):
            self.assertEqual(self.seul(*args).returncode, 0, args)
        self.assertEqual(self.runs(), [])
        self.assertEqual(self.appels_de("protonvpn"), [])
        f = self.fiche(verifier=False)
        self.assertEqual((f["etat"], f["probleme"]), ("sans_compte", "non_verifie"))
        self.assertEqual(self.runs(), [])

    def test_jamais_status_et_aucun_identifiant_ressorti(self):
        self.flatpak(cli={"connect": {"out": "Error: " + EMAIL + " " + COMPTE + " " + JETON + " " + IP + "\n", "code": 1}})
        self.fiche()
        for args in (("fournisseur", "proton", "connecter", "FR"), ("fournisseur", "proton", "deconnecter")):
            r = self.seul(*args)
            for s in SECRETS + ("Hors-sujet-faux",):
                self.assertNotIn(s, lire(r), s)
        vus = {a[0] for a in self.appels_de("protonvpn") if a}
        self.assertLessEqual(vus, {"info", "countries", "connect", "disconnect"})

    def test_appli_flatpak_ouverte_vue_par_flatpak_ps(self):
        self.flatpak(ps="Application\n%s\n" % APP)
        f = self.fiche()
        self.assertEqual((f["etat"], f["probleme"], f["pilotage"]), ("pilote_appli", "appli_ouverte", "appli"))
        self.assertIn("Ferme l'application Proton VPN pour piloter depuis l'île", f["message"])
        self.assertIn(["ps", "--columns=application"], self.appels_flatpak())
        self.assertEqual(self.appels_de("protonvpn"), [])                            # la CLI n'est même pas lancée
        for args in (("connecter", "FR"), ("deconnecter",)):
            r = self.seul("fournisseur", "proton", *args)
            self.assertEqual(r.returncode, 1, args)
            self.assertIn("Ferme l'application Proton VPN", r.stderr)
        self.assertEqual(self.appels_de("protonvpn"), [])
        self.assertFalse([a for a in self.appels() if a[:1] == ["connection"] and "show" not in a])      # aucune coupure forcée (lectures seules)

    def test_autres_applis_flatpak_ouvertes_ne_comptent_pas(self):
        self.flatpak(ps="Application\norg.example.Autre\ncom.protonvpn.www.Extra\n")
        self.assertEqual(self.fiche()["etat"], "pret")

    def test_ps_en_echec_la_cli_decide(self):
        self.flatpak(ps="", ps_code=1, cli={"info": {"out": APPLI}})
        f = self.fiche()
        self.assertEqual((f["etat"], f["probleme"]), ("pilote_appli", "appli_ouverte"))        # message de la CLI du Flatpak lui-même

    def test_connecter_et_deconnecter_dans_le_flatpak(self):
        self.flatpak()
        r = self.seul("fournisseur", "proton", "connecter", "FR")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.runs(), [["run", "--user", "--command=protonvpn", APP, "connect", "--country", "FR"]])
        r = self.seul("fournisseur", "proton", "deconnecter")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.appels_de("protonvpn")[-1], ["disconnect"])
        for s in SECRETS:
            self.assertNotIn(s, lire(r))

    def test_commande_absente_du_flatpak_est_illisible(self):
        self.flatpak(cli={"info": {"err": "error: Failed to execute command protonvpn\n", "code": 1}})
        f = self.fiche()
        self.assertEqual((f["etat"], f["probleme"]), ("sans_compte", "illisible"))

    def test_login_ouvre_l_appli_flatpak_detachee(self):
        self.flatpak(cli={"info": {"out": INFO_SANS}})
        self.poser("kitty", {})
        r = self.seul("fournisseur", "proton", "login")
        self.assertEqual(r.returncode, 0, r.stderr)
        for _ in range(50):
            if ["run", "--user", APP] in self.runs():
                break
            time.sleep(0.1)
        self.assertIn(["run", "--user", APP], self.runs())
        self.assertEqual(self.appels_de("kitty"), [])

    def test_verrou_et_montee_gardes_comme_pour_la_cli_native(self):
        self.flatpak()
        from tests._vpn_faux import connexions
        (self.r / "etat.json").write_text(json.dumps(connexions() + [dict(uuid="55555555-5555-4555-8555-555555555555", type="wireguard",
                                                                           active=True, dev="proton0", nom="ProtonVPN FR#12", etat="activating")]))
        f = self.fiche()
        self.assertEqual(f["probleme"], "non_verifie")
        self.assertEqual(self.runs(), [])

    def test_delais_plus_longs_et_bornes_pour_le_flatpak(self):
        mod = charger()
        vus = []

        def faux(argv, delai, borne=64 * 1024):
            vus.append((argv, delai))
            return 0, b"", b""
        with mock.patch.object(mod, "lancer_borne", faux), mock.patch.object(mod, "proton_cli_argv", lambda: ["/x/flatpak", "run", "--user", "--command=protonvpn", APP]), \
                mock.patch.object(mod, "proton_flatpak_ouvert", lambda: False):
            mod.proton_cli(["info"], 10)
        self.assertEqual(vus[0][1], 10 + mod.DELAI_FLATPAK)
        vus.clear()
        with mock.patch.object(mod, "lancer_borne", faux), mock.patch.object(mod, "proton_cli_argv", lambda: ["/x/protonvpn"]):
            mod.proton_cli(["info"], 10)
        self.assertEqual(vus[0][1], 10)
        self.assertLessEqual(mod.DELAI_FLATPAK, 30)
        self.assertLessEqual(mod.DELAI_FLATPAK_LECTURE, 10)


if __name__ == "__main__":
    unittest.main()
