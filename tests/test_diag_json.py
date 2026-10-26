"""Lot D (A) : « nc-diag --json [--rapide] » et « nc-diag reparer ID [--json] ».

Rien ne touche à la vraie session : HOME, XDG_RUNTIME_DIR et PATH temporaires, faux systemctl, systemd-run, hyprctl,
noctalia, qs et notify-send (chacun note ses appels dans un journal). L'état des unités vient de fichiers d'un dossier
temporaire ($FAKE/etat/<unité>).
"""
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import unittest

REPO = Path(__file__).resolve().parents[1]
DIAG = REPO / "home/.local/bin/nc-diag"

SYSTEMCTL = r"""#!/bin/sh
echo "systemctl $*" >> "$FAKE/appels"
u=""; for a; do u=$a; done
etat() { cat "$FAKE/etat/$1" 2>/dev/null || echo active; }
case "$*" in
  *" is-active "*) etat "$u"; [ "$(etat "$u")" = active ]; exit $? ;;
  *"show -p LoadState"*) [ -e "$FAKE/absente/$u" ] && echo not-found || echo loaded ;;
  *" is-enabled "*) exit 0 ;;
  "--version") cat "$FAKE/systemd-version" 2>/dev/null || echo "systemd 262 (262.1)" ;;
  *" restart "*|*" start "*) sleep "$(cat "$FAKE/lenteur" 2>/dev/null || echo 0)"; mkdir -p "$FAKE/etat"; echo active > "$FAKE/etat/$u" ;;
esac
exit 0
"""
# systemd-run : note ses arguments, puis fait ce que fait le script (redémarrer nc-ile) sans lancer le vrai
SYSTEMD_RUN = r"""#!/bin/sh
echo "systemd-run $*" >> "$FAKE/appels"
[ -e "$FAKE/systemd-run-deja" ] && { echo "Unit nc-diag-reparer-ile.service already exists" >&2; exit 1; }
mkdir -p "$FAKE/etat"; echo active > "$FAKE/etat/nc-ile.service"
exit 0
"""
SIMPLE = '#!/bin/sh\necho "{nom} $*" >> "$FAKE/appels"\n{corps}\n'


class Base(unittest.TestCase):
    def setUp(self):
        d = tempfile.TemporaryDirectory(prefix="nc-diag-json-")
        self.addCleanup(d.cleanup)
        self.racine = Path(d.name)
        self.home = self.racine / "home"
        (self.home / ".local/bin").mkdir(parents=True)
        (self.home / ".config/nc").mkdir(parents=True)
        self.fake = self.racine / "fake"
        (self.fake / "etat").mkdir(parents=True)
        self.bin = self.racine / "bin"
        self.bin.mkdir()
        self.run_dir = self.racine / "run"
        self.run_dir.mkdir(mode=0o700)
        self.proc = self.racine / "proc"             # faux /proc : la vraie île de la machine ne compte pas
        self.proc.mkdir()
        self.appels = self.fake / "appels"
        self.appels.touch()
        faux = {"systemctl": SYSTEMCTL, "systemd-run": SYSTEMD_RUN}
        for nom, corps in (("hyprctl", "[ \"$1\" = version ] && echo '{\"tag\":\"v0.56.0\"}' || true"),
                           ("noctalia", "[ \"$1\" = --version ] && echo 'noctalia 4.0' || true"),
                           ("qs", "[ \"$1\" = --version ] && echo 'quickshell 0.3.0' || true"),
                           ("notify-send", "")):
            faux[nom] = SIMPLE.format(nom=nom, corps=corps)
        for nom, corps in faux.items():
            f = self.bin / nom
            f.write_text(corps)
            f.chmod(0o755)

    def env(self, **plus):
        env = dict(os.environ, HOME=str(self.home), FAKE=str(self.fake), NC_LANGUE="fr", XDG_RUNTIME_DIR=str(self.run_dir),
                   PATH=f"{self.bin}:{os.environ['PATH']}", HYPRLAND_INSTANCE_SIGNATURE="test",
                   NC_DIAG_PROC=str(self.proc))
        for k in ("XDG_CONFIG_HOME", "XDG_STATE_HOME", "IA_MODE", "IA_ACTIONS"):
            env.pop(k, None)
        env.update(plus)
        return env

    def diag(self, *args, **plus):
        return subprocess.run([sys.executable, str(DIAG), *args], env=self.env(**plus), capture_output=True, text=True,
                              timeout=60)

    def etat(self, unite, valeur):
        (self.fake / "etat" / unite).write_text(valeur)

    def journal(self):
        return self.appels.read_text().splitlines()

    def json(self, *args, **plus):
        r = self.diag("--json", *args, **plus)
        self.assertEqual(r.returncode, 0, r.stderr)
        return json.loads(r.stdout)


class Bilan(Base):
    def test_schema(self):
        self.etat("nc-pouls.service", "inactive")
        self.etat("hypridle.service", "failed")
        d = self.json("--rapide")
        self.assertEqual(r_cles(d), ["attention", "constats", "duree_ms", "ko", "langue", "ok", "reparations", "resume", "version"])
        self.assertEqual(d["version"], 1)
        self.assertEqual(d["langue"], "fr")
        self.assertIsInstance(d["duree_ms"], int)
        self.assertIsInstance(d["resume"], str)
        self.assertEqual(d["ko"], sum(c["niveau"] == "faux" for c in d["constats"]))
        self.assertEqual(d["attention"], sum(c["niveau"] == "avert" for c in d["constats"]))
        self.assertGreater(d["ok"], 0)
        for c in d["constats"]:
            self.assertEqual(sorted(c), ["cle", "niveau", "quoi", "reparations", "section", "texte", "texte_ia"])
            self.assertIn(c["niveau"], ("avert", "faux"))      # jamais les ✓
            self.assertTrue(c["cle"])
            for i in c["reparations"]:
                self.assertIn(i, d["reparations"])
        for i, r in d["reparations"].items():
            self.assertRegex(i, r"^(redemarrer|demarrer):[a-z0-9-]+\.(service|path)$|^ia_conf_prive$")
            self.assertEqual(sorted(r), ["danger", "detail", "ferme_ile", "libelle"])
            self.assertIsInstance(r["danger"], bool)
            self.assertIsInstance(r["ferme_ile"], bool)

    def test_cle_et_reparations_des_services(self):
        self.etat("hypridle.service", "failed")
        self.etat("nc-ecran-externe.service", "inactive")
        self.etat("nc-pouls.service", "inactive")             # coupé exprès : pas une panne, pas de « démarrer »
        d = self.json("--rapide")
        par_cle = {c["cle"]: c for c in d["constats"]}
        self.assertEqual(par_cle["service:hypridle.service"]["niveau"], "faux")
        self.assertEqual(par_cle["service:hypridle.service"]["reparations"], ["redemarrer:hypridle.service"])
        self.assertEqual(par_cle["service:nc-ecran-externe.service"]["niveau"], "avert")
        self.assertEqual(par_cle["service:nc-ecran-externe.service"]["reparations"], ["demarrer:nc-ecran-externe.service"])
        self.assertEqual(par_cle["service:nc-pouls.service"]["reparations"], [])
        self.assertNotIn("demarrer:nc-pouls.service", d["reparations"])
        self.assertIn("pour cette session", d["reparations"]["demarrer:nc-ecran-externe.service"]["libelle"])
        self.assertIn("peut-être coupé exprès", d["reparations"]["demarrer:nc-ecran-externe.service"]["detail"])

    def test_session_de_confiance_et_systemd_trop_ancien(self):
        # nc-bac demande PrivatePIDs (systemd 257) : avant, pas de session de confiance ; dit seulement si JARVIS est activé
        (self.home / ".config/nc/reglages.conf").write_text("NOEUD_JARVIS=oui\n")
        (self.fake / "systemd-version").write_text("systemd 254 (254.27)\n")
        cles = {c["cle"]: c for c in self.json("--rapide")["constats"]}
        self.assertIn("noeud_systemd", cles)
        self.assertIn("systemd 257", cles["noeud_systemd"]["texte"])
        (self.fake / "systemd-version").write_text("systemd 257 (257.9)\n")
        self.assertNotIn("noeud_systemd", {c["cle"] for c in self.json("--rapide")["constats"]})
        (self.fake / "systemd-version").write_text("systemd 254 (254.27)\n")
        (self.home / ".config/nc/reglages.conf").write_text("NOEUD_JARVIS=non\n")
        self.assertNotIn("noeud_systemd", {c["cle"] for c in self.json("--rapide")["constats"]})

    def faux_bin(self, nom, corps):
        f = self.bin / nom
        f.write_text("#!/bin/sh\n" + corps + "\n")
        f.chmod(0o755)

    def test_texte_ia_sans_la_ligne_du_journal(self):
        # La dernière ligne du journal (ici un nom de réseau Wi-Fi fictif) reste à l'écran, jamais dans texte_ia
        self.faux_bin("journalctl", 'echo "début"; echo "connecté au réseau Wifi-Fictif-42 (titre : Chanson Secrète)"')
        self.etat("hypridle.service", "failed")
        d = self.json("--rapide")
        c = {c["cle"]: c for c in d["constats"]}["service:hypridle.service"]
        self.assertIn("Wifi-Fictif-42", c["texte"])
        self.assertNotIn("Wifi-Fictif-42", c["texte_ia"])
        self.assertNotIn("Chanson", c["texte_ia"])
        self.assertIn("hypridle.service", c["texte_ia"])
        self.assertIn("2 ligne(s)", c["texte_ia"])
        # le texte affiché de nc-diag garde la ligne
        self.assertIn("Wifi-Fictif-42", self.diag().stdout)

    def test_texte_ia_pareil_sans_journal_et_validate(self):
        self.etat("nc-pouls.service", "inactive")
        c = {c["cle"]: c for c in self.json("--rapide")["constats"]}["service:nc-pouls.service"]
        self.assertEqual(c["texte_ia"], c["texte"])
        self.faux_bin("noctalia", '[ "$1" = --version ] && { echo "noctalia 4.0"; exit 0; }\n'
                      '[ "$2" = validate ] && { echo "ERROR fond d\'écran Photo-Perso.png introuvable"; exit 1; }\nexit 0')
        c = {c["cle"]: c for c in self.json("--rapide")["constats"]}["noctalia_config"]
        self.assertIn("Photo-Perso", c["texte"])
        self.assertNotIn("Photo-Perso", c["texte_ia"])

    def faux_proc(self, pid, *argv):
        d = self.proc / str(pid)
        d.mkdir(parents=True, exist_ok=True)
        (d / "cmdline").write_bytes(b"\0".join(a.encode() for a in argv) + b"\0")

    def lancer_ile_a_la_main(self):
        # des clients et une autre config ne comptent pas
        self.faux_proc(4240, "qs", "-c", "nc-ile", "ipc", "call", "x", "y")
        self.faux_proc(4241, "/usr/bin/qs", "-c", "autre")
        self.faux_proc(4242, "/usr/bin/qs", "-c", "nc-ile")

    def test_ile_a_la_main_pas_de_seconde_ile(self):
        self.etat("nc-ile.service", "inactive")
        c = {c["cle"]: c for c in self.json("--rapide")["constats"]}
        self.assertEqual(c["ile_arretee"]["reparations"], ["demarrer:nc-ile.service"])      # témoin : rien ne tourne
        self.lancer_ile_a_la_main()
        c = {c["cle"]: c for c in self.json("--rapide")["constats"]}
        self.assertEqual(c["ile_arretee"]["reparations"], [])
        r = self.diag("reparer", "demarrer:nc-ile.service", "--json")
        self.assertEqual(json.loads(r.stdout)["resultat"], "deja")
        self.assertFalse([x for x in self.journal() if x.startswith("systemd-run")])

    def test_unite_absente_pas_de_demarrage(self):
        (self.fake / "absente").mkdir()
        (self.fake / "absente/hypridle.service").touch()
        self.etat("hypridle.service", "inactive")
        c = {c["cle"]: c for c in self.json("--rapide")["constats"]}
        self.assertEqual(c["service:hypridle.service"]["reparations"], [])

    def test_ile_arretee_ferme_l_ile_et_passe_en_dernier(self):
        self.etat("nc-ile.service", "failed")
        self.etat("hypridle.service", "failed")
        d = self.json("--rapide")
        self.assertEqual(list(d["reparations"])[-1], "redemarrer:nc-ile.service")
        r = d["reparations"]["redemarrer:nc-ile.service"]
        self.assertTrue(r["danger"] and r["ferme_ile"])
        self.assertFalse(d["reparations"]["redemarrer:hypridle.service"]["ferme_ile"])

    def test_ia_conf_lisible_propose_chmod(self):
        conf = self.home / ".config/nc/ia.conf"
        conf.write_text("X=1\n")
        conf.chmod(0o644)
        # nc-ia factice : la section IA du bilan en a besoin pour arriver jusqu'au constat
        self.faux_nc_ia()
        c = {c["cle"]: c for c in self.json("--rapide")["constats"]}
        self.assertEqual(c["ia_conf_lisible"]["reparations"], ["ia_conf_prive"])

    def faux_nc_ia(self, ias='[{"nom":"x","disponible":true}]'):
        f = self.home / ".local/bin/nc-ia"
        f.write_text('#!/bin/sh\necho "nc-ia $*" >> "$FAKE/appels"\n'
                     'echo \'{"mode":"auto","coupee":false,"ias":' + ias + ','
                     '"usages":{"question":{"nom":"x"},"image":{"nom":"x"}}}\'\n')
        f.chmod(0o755)

    def test_jeton_a_renouveler_dit_quoi_faire(self):
        self.faux_nc_ia('[{"nom":"x","disponible":true},{"id":"claude","nom":"Claude Code","cli":"claude",'
                        '"disponible":true,"jeton_a_renouveler":true},{"id":"codex","nom":"Codex","cli":"codex",'
                        '"disponible":true,"jeton_a_renouveler":false}]')
        c = {c["cle"]: c for c in self.json("--rapide", NC_LANGUE="fr")["constats"]}
        self.assertIn("ia_jeton_claude", c)
        self.assertNotIn("ia_jeton_codex", c)
        self.assertIn("Claude Code doit renouveler sa connexion", c["ia_jeton_claude"]["texte"])
        self.assertIn("ouvre-le une fois dans un terminal (claude)", c["ia_jeton_claude"]["quoi"])

    def test_resume_fr_en_ordre_et_limite(self):
        for u in ("hypridle.service", "nc-ecran-externe.service", "nc-profile-sync.service", "nc-theme-sync.path"):
            self.etat(u, "failed")
        d = self.json("--rapide")
        self.assertRegex(d["resume"], rf"^{d['ko']} problème\(s\) : ")
        self.assertEqual(d["resume"].count(" ; ") + 1 - (1 if d["ko"] > 3 else 0), min(d["ko"], 3))
        self.assertIn(f"et {d['ko'] - 3} autre(s)", d["resume"])
        self.assertIn(f"{d['attention']} point(s) à améliorer", d["resume"])
        en = self.json("--rapide", NC_LANGUE="en")
        self.assertEqual(en["langue"], "en")
        self.assertRegex(en["resume"], rf"^{en['ko']} problem\(s\): ")
        self.assertIn("thing(s) to improve", en["resume"])
        self.assertIn(f"and {en['ko'] - 3} more", en["resume"])

    def test_resume_en_ordre(self):
        # Rien à signaler : on retire tout ce qui peut se plaindre, via un module chargé avec un faux bilan
        import importlib.machinery
        import importlib.util
        ch = importlib.machinery.SourceFileLoader("nc_diag_json", str(DIAG))
        m = importlib.util.module_from_spec(importlib.util.spec_from_loader("nc_diag_json", ch))
        os.environ["NC_LANGUE"] = "fr"
        self.addCleanup(os.environ.pop, "NC_LANGUE", None)
        ch.exec_module(m)
        b = m.Bilan(couleurs=False)
        b.ok("x")
        self.assertEqual(m.resume(b), "Tout est en ordre.")
        m.EN = True
        self.assertEqual(m.resume(b), "Everything is in order.")

    def test_texte_normal_inchange(self):
        self.etat("hypridle.service", "failed")
        r = self.diag()
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue(r.stdout.startswith("Bilan de noctalia-config (nc-diag)\n"))
        self.assertIn("✗ ", r.stdout)
        self.assertIn("hypridle.service", r.stdout)
        self.assertRegex(r.stdout, r"\n\d+ problème\(s\) à corriger\.")
        self.assertNotIn('"constats"', r.stdout)
        # Le mode court et l'aide n'ont pas bougé non plus
        self.assertTrue(self.diag("court").stdout.startswith("Vérification (nc-diag) :"))
        self.assertIn("nc-diag --json", self.diag("aide").stdout)

    def test_rapide_sans_qs_p_et_vite(self):
        (self.home / ".local/bin/nc-qs-capture").write_text("#!/bin/sh\necho capture >> \"$FAKE/appels\"\nexit 0\n")
        debut = time.monotonic()
        d = self.json("--rapide")
        self.assertLess(time.monotonic() - debut, 5)
        self.assertLess(d["duree_ms"], 5000)
        j = "\n".join(self.journal())
        self.assertNotRegex(j, r"qs .*(-p|--path)")
        self.assertNotIn("capture", j)

    def test_chemins_complets_comme_nc_ia(self):
        # L'île a le PATH du système : ~/.local/bin est ajouté, les outils de l'utilisateur sont retrouvés
        f = self.home / ".local/bin/hyprctl"
        f.write_text('#!/bin/sh\necho "hyprctl-utilisateur $*" >> "$FAKE/appels"\n[ "$1" = version ] && echo \'{"tag":"v9.9.9"}\'\n')
        f.chmod(0o755)
        self.json("--rapide")
        self.assertTrue(any(x.startswith("hyprctl-utilisateur") for x in self.journal()))


def r_cles(d):
    return sorted(d)


class Reparer(Base):
    def reparer(self, ident, *plus, **env):
        return self.diag("reparer", ident, *plus, **env)

    def test_ids_refuses_sans_aucun_appel(self):
        for ident in ("redemarrer:sshd.service", "../x", ";rm", "foo", "redemarrer:hypridle.service;id", "", "demarrer:nc-pouls.service",
                      "redemarrer:HYPRIDLE.service", "redemarrer:hypridle.service\n", "ia_conf_prive ", "-h"):
            with self.subTest(ident=ident):
                r = self.reparer(ident)
                self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
                self.assertEqual(self.journal(), [])
                rj = self.reparer(ident, "--json")
                self.assertEqual(rj.returncode, 2)
                self.assertEqual(json.loads(rj.stdout)["resultat"], "refuse")
                self.assertEqual(self.journal(), [])
        r = self.diag("reparer")
        self.assertEqual(r.returncode, 2)
        self.assertEqual(self.journal(), [])

    def test_deja_rien_a_faire(self):
        self.etat("hypridle.service", "active")
        r = self.reparer("redemarrer:hypridle.service", "--json")
        self.assertEqual(r.returncode, 0, r.stderr)
        d = json.loads(r.stdout)
        self.assertEqual((d["id"], d["resultat"]), ("redemarrer:hypridle.service", "deja"))
        self.assertEqual(sorted(d), ["ferme_ile", "id", "libelle", "resultat", "texte"])
        self.assertFalse([x for x in self.journal() if re.search(r" (restart|start|reset-failed) ", x)])
        # Un service seulement arrêté ne se « redémarre » pas
        self.etat("hypridle.service", "inactive")
        self.assertEqual(json.loads(self.reparer("redemarrer:hypridle.service", "--json").stdout)["resultat"], "deja")
        self.assertFalse([x for x in self.journal() if re.search(r" (restart|start) ", x)])

    def test_reset_failed_puis_restart(self):
        self.etat("hypridle.service", "failed")
        r = self.reparer("redemarrer:hypridle.service", "--json")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        d = json.loads(r.stdout)
        self.assertEqual(d["resultat"], "fait")
        self.assertFalse(d["ferme_ile"])
        cmds = [x for x in self.journal() if "hypridle" in x and re.search(r" (restart|start|reset-failed) ", x)]
        self.assertEqual(cmds, ["systemctl --user reset-failed hypridle.service", "systemctl --user restart hypridle.service"])

    def test_demarrer_une_unite_arretee_sans_enable(self):
        self.etat("nc-ecran-externe.service", "inactive")
        r = self.reparer("demarrer:nc-ecran-externe.service")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("✓", r.stdout)
        j = "\n".join(self.journal())
        self.assertIn("systemctl --user start nc-ecran-externe.service", j)
        self.assertNotIn("enable", j)

    def test_echec_code_1(self):
        self.etat("hypridle.service", "failed")
        (self.bin / "systemctl").write_text(SYSTEMCTL.replace('echo active > "$FAKE/etat/$u"', 'echo failed > "$FAKE/etat/$u"'))
        r = self.reparer("redemarrer:hypridle.service", "--json")
        self.assertEqual(r.returncode, 1)
        self.assertEqual(json.loads(r.stdout)["resultat"], "echec")

    def test_chmod_600(self):
        conf = self.home / ".config/nc/ia.conf"
        conf.write_text("CLE=abc\n")
        conf.chmod(0o644)
        r = self.reparer("ia_conf_prive", "--json")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(json.loads(r.stdout)["resultat"], "fait")
        self.assertEqual(conf.stat().st_mode & 0o777, 0o600)
        self.assertEqual(conf.read_text(), "CLE=abc\n")
        self.assertEqual(json.loads(self.reparer("ia_conf_prive", "--json").stdout)["resultat"], "deja")
        self.assertEqual(self.journal(), [])               # aucune commande : un simple chmod

    def test_nc_ile_par_systemd_run(self):
        self.etat("nc-ile.service", "failed")
        r = self.reparer("redemarrer:nc-ile.service", "--json")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        d = json.loads(r.stdout)
        self.assertEqual(d["resultat"], "fait")
        self.assertTrue(d["ferme_ile"])
        lancements = [x for x in self.journal() if x.startswith("systemd-run")]
        self.assertEqual(len(lancements), 1)
        self.assertIn("--user", lancements[0])
        self.assertIn("--collect", lancements[0])
        # Jamais « systemctl restart nc-ile.service » direct : il tuerait le Spotlight qui l'a lancé
        self.assertFalse([x for x in self.journal() if re.match(r"systemctl .* (restart|start) nc-ile", x)])

    def test_nc_ile_deja_en_cours(self):
        self.etat("nc-ile.service", "failed")
        (self.fake / "systemd-run-deja").touch()
        d = json.loads(self.reparer("redemarrer:nc-ile.service", "--json").stdout)
        self.assertEqual(d["resultat"], "deja")

    def test_deux_lancements_un_seul_restart(self):
        self.etat("hypridle.service", "failed")
        (self.fake / "lenteur").write_text("1")            # le restart dure 1 s : le second attend le verrou, puis voit « actif »
        sorties = []

        def lancer():
            sorties.append(json.loads(self.reparer("redemarrer:hypridle.service", "--json").stdout)["resultat"])
        fils = [threading.Thread(target=lancer) for _ in range(2)]
        for f in fils:
            f.start()
            time.sleep(0.3)
        for f in fils:
            f.join(60)
        self.assertEqual(sorted(sorties), ["deja", "fait"])
        self.assertEqual(len([x for x in self.journal() if " restart hypridle" in x]), 1)
        self.assertTrue((self.run_dir / "nc-diag-reparer.lock").exists())

    def test_ia_mode_non_marche_sans_nc_ia(self):
        piege = self.home / ".local/bin/nc-ia"
        piege.write_text('#!/bin/sh\necho "nc-ia $*" >> "$FAKE/appels"\nexit 3\n')
        piege.chmod(0o755)
        self.etat("hypridle.service", "failed")
        r = self.reparer("redemarrer:hypridle.service", "--json", IA_MODE="non", IA_ACTIONS="non")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(json.loads(r.stdout)["resultat"], "fait")
        self.assertFalse([x for x in self.journal() if x.startswith("nc-ia")])

    def test_hors_session_rien_n_est_fait(self):
        (self.bin / "systemctl").write_text('#!/bin/sh\necho "systemctl $*" >> "$FAKE/appels"\necho "Failed to connect to bus" >&2\nexit 1\n')
        r = self.reparer("redemarrer:hypridle.service", "--json")
        self.assertEqual(r.returncode, 1)
        self.assertEqual(json.loads(r.stdout)["resultat"], "echec")
        self.assertFalse([x for x in self.journal() if re.search(r" (restart|start|reset-failed) ", x)])


if __name__ == "__main__":
    unittest.main()
