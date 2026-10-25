"""npm installé avec sudo dans le préfixe du système (/usr, /usr/local) : Codex, Gemini CLI, Claude Code ou OpenCode ne
peuvent plus se mettre à jour seuls (EACCES). install.sh propose prefix=~/.local et la réinstallation, sans jamais
lancer sudo ni rien faire sans « oui » ; nc-diag signale npm 12 sur un Node trop ancien et une CLI d'IA bloquée ;
nc-ia trouve les CLI de ~/.local/bin et de ~/.npm-global/bin.

Jamais le vrai npm, node ou sudo : faux programmes dans un faux PATH (sans /usr/bin), faux HOME.
"""
import importlib.machinery
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

REPO = Path(__file__).resolve().parents[1]
SOURCE = (REPO / "install.sh").read_text()
ASK = SOURCE[SOURCE.index("sans_tty() {"):SOURCE.index("have() {")]
SONDE = SOURCE[SOURCE.index("sonder() {"):SOURCE.index("choisir() {")]
NPM = SOURCE[SOURCE.index("# ── 3d. npm"):SOURCE.index("# ── 4. Services de la session")]
DIAG = REPO / "home/.local/bin/nc-diag"
NCIA = REPO / "home/.local/bin/nc-ia"
ENGINES = "^22.22.2 || ^24.15.0 || >=26.0.0"   # npm 12.2.1

# Faux npm : garde chaque appel ; « config set prefix » est retenu dans le faux HOME, « install » crée le paquet
FAUX = r'''#!/usr/bin/env python3
import json,os,sys
from pathlib import Path
nom=Path(sys.argv[0]).name; args=sys.argv[1:]
with open(os.environ['NC_TEST_CALLS'],'a') as f:f.write(json.dumps([nom,*args])+'\n')
rc=Path(os.environ['HOME'])/'.npmrc-faux'
if nom=='npm':
 if args==['config','get','prefix']:print(rc.read_text() if rc.exists() else os.environ['NC_TEST_PREFIXE'])
 elif args[:3]==['config','set','prefix']:rc.write_text(args[3])
 elif args[:1]==['install']:
  p=Path(args[args.index('--prefix')+1])/'lib/node_modules'/args[-1];p.mkdir(parents=True);(p/'package.json').write_text('{}')
 elif args==['--version']:print(os.environ.get('NC_TEST_NPMV','12.2.1'))
elif nom=='node':print(os.environ.get('NC_TEST_NODEV','v20.20.2'))
elif nom=='pacman' and os.environ.get('NC_TEST_PROPRIO'):print(os.environ['NC_TEST_PROPRIO'])
else:sys.exit(1 if nom!='sudo' else 99)
'''
OUTILS = ("timeout", "tail", "head", "cut", "dirname", "python3", "env", "mkdir")


class Base(unittest.TestCase):
    def setUp(self):
        if os.geteuid() == 0:
            self.skipTest("en root, tout dossier est inscriptible")
        d = tempfile.TemporaryDirectory(prefix="nc-npm-")
        self.addCleanup(d.cleanup)
        self.racine = Path(d.name)
        self.home = self.racine / "home"
        self.home.mkdir()
        self.faux = self.racine / "faux"          # faux npm, node, sudo, pacman, rpm, dpkg-query
        self.faux.mkdir()
        self.outils = self.racine / "outils"      # seulement les outils de base : ni le vrai npm, ni le vrai sudo
        self.outils.mkdir()
        for o in OUTILS:
            if shutil.which(o):
                os.symlink(shutil.which(o), self.outils / o)
        self.calls = self.racine / "calls"
        self.calls.touch()
        # Préfixe du « système » : codex installé là par sudo npm, illisible en écriture
        self.systeme = self.racine / "usr"
        self.codex = self.systeme / "lib/node_modules/@openai/codex"
        (self.codex / "bin").mkdir(parents=True)
        (self.codex / "package.json").write_text("{}")
        (self.codex / "bin/codex.js").write_text("#!/bin/sh\n")
        (self.codex / "bin/codex.js").chmod(0o755)
        (self.systeme / "bin").mkdir()
        os.symlink(self.codex / "bin/codex.js", self.systeme / "bin/codex")
        self.addCleanup(self.verrouiller, False)

    def verrouiller(self, oui=True):
        for p in (self.systeme / "lib/node_modules", self.systeme / "bin", self.systeme / "lib/node_modules/@openai"):
            p.chmod(0o555 if oui else 0o755)

    def programme(self, nom, corps=FAUX):
        f = self.faux / nom
        f.write_text(corps)
        f.chmod(0o755)

    def appels(self):
        return [json.loads(l) for l in self.calls.read_text().splitlines() if l.strip()]


class InstallNpm(Base):
    def setUp(self):
        super().setUp()
        for nom in ("npm", "node", "sudo", "pacman", "rpm", "dpkg-query"):
            self.programme(nom)

    def lancer(self, reponse=None, prefixe=None, vrai_ask=False, proprio=""):
        prelude = r'''
set -euo pipefail
say(){ printf '%s\n' "$*"; }
info(){ printf '%s\n' "$*"; }
ok(){ printf '%s\n' "$*"; }
warn(){ printf '%s\n' "$*"; }
t(){ printf '%s' "$1"; }
have(){ command -v "$1" >/dev/null 2>&1; }
'''
        if vrai_ask:
            prelude += ASK
        else:   # comme le vrai : vide -> défaut ; vrai seulement pour o/oui/y/yes
            prelude += r'''ask(){ printf 'QUESTION %s\n' "$1"; local r="${NC_TEST_REPONSE:-}"; r="${r:-${2:-n}}"; [[ "$r" =~ ^[oOyY] ]]; }
'''
        script = self.racine / "test.sh"
        script.write_text(prelude + SONDE + NPM + "\necho FINI\n")
        env = {"HOME": str(self.home), "PATH": f"{self.faux}:{self.outils}", "NC_TEST_CALLS": str(self.calls),
               "NC_TEST_PREFIXE": str(prefixe or self.systeme), "NC_TEST_REPONSE": reponse or "", "NC_TEST_PROPRIO": proprio}
        self.verrouiller()
        r = subprocess.run([shutil.which("bash") or "/bin/bash", str(script)], env=env, capture_output=True, text=True,
                           timeout=30, start_new_session=True)   # sans terminal de contrôle : /dev/tty illisible
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("FINI", r.stdout)
        return r.stdout

    def actions(self):
        """Appels qui changent quelque chose : config set, install, uninstall, et tout appel à sudo."""
        return [c for c in self.appels() if c[0] == "sudo" or (c[0] == "npm" and c[1:2] != ["config"] and c[1:2] != ["--version"])
                or c[:3] == ["npm", "config", "set"]]

    def test_question_posee_sans_reponse_ou_non_rien_n_est_fait(self):
        for reponse in ("", "non", "n"):
            with self.subTest(reponse=reponse):
                self.calls.write_text("")
                out = self.lancer(reponse)
                self.assertIn("QUESTION Installer désormais les paquets globaux de npm dans ~/.local "
                              "(npm config set prefix ~/.local, sans sudo) ?", out)
                self.assertIn(f"npm installe ses paquets globaux dans {self.systeme}, où tu ne peux pas écrire", out)
                self.assertIn("Rien n'est changé. Pour le faire plus tard : npm config set prefix ~/.local ; "
                              "npm install -g @openai/codex", out)
                self.assertEqual(self.actions(), [])
                self.assertFalse((self.home / ".npmrc-faux").exists())

    def test_sans_terminal_seulement_un_message(self):
        out = self.lancer(vrai_ask=True)
        self.assertIn("(npm config set prefix ~/.local, sans sudo) ? -> réponse par défaut (n)", out)
        self.assertIn("Rien n'est changé.", out)
        self.assertEqual(self.actions(), [])

    def test_oui_change_le_prefixe_et_reinstalle_sans_sudo(self):
        out = self.lancer("oui")
        local = str(self.home / ".local")
        self.assertEqual(self.actions(), [["npm", "config", "set", "prefix", local],
                                          ["npm", "install", "-g", "--prefix", local, "@openai/codex"]])
        self.assertNotIn("sudo", [c[0] for c in self.appels()])
        self.assertIn(f"QUESTION @openai/codex est dans {self.systeme} : le réinstaller dans ~/.local, sans sudo "
                      "(npm install -g @openai/codex) ?", out)
        self.assertIn("@openai/codex installé dans ~/.local : il pourra se mettre à jour seul.", out)
        self.assertIn(f"Ancienne copie du système, à retirer toi-même : sudo npm uninstall -g --prefix {self.systeme} "
                      "@openai/codex", out)
        self.assertTrue((self.home / ".local/lib/node_modules/@openai/codex/package.json").exists())
        self.assertTrue((self.codex / "package.json").exists())    # la copie du système n'est jamais retirée

    def test_paquet_de_la_distribution_pas_reinstalle(self):
        out = self.lancer("oui", proprio="codex-distrib")
        self.assertIn("@openai/codex : paquet codex-distrib de ta distribution, mis à jour avec le système.", out)
        self.assertEqual(self.actions(), [["npm", "config", "set", "prefix", str(self.home / ".local")]])
        self.assertNotIn("réinstaller", out)

    def test_prefixe_deja_inscriptible_aucune_question(self):
        for prefixe in (self.home / ".local", self.home / ".npm-global"):
            with self.subTest(prefixe=prefixe):
                self.calls.write_text("")
                out = self.lancer("oui", prefixe=prefixe)
                self.assertNotIn("QUESTION", out)
                self.assertEqual(out.strip(), "FINI")
                self.assertEqual(self.appels(), [["npm", "config", "get", "prefix"]])

    def test_npm_absent_rien(self):
        (self.faux / "npm").unlink()
        out = self.lancer("oui")
        self.assertEqual(out.strip(), "FINI")
        self.assertEqual(self.appels(), [])


def charger_diag():
    with mock.patch.dict(os.environ, NC_LANGUE="fr"):
        chargeur = importlib.machinery.SourceFileLoader("nc_diag_npm", str(DIAG))
        spec = importlib.util.spec_from_loader("nc_diag_npm", chargeur)
        m = importlib.util.module_from_spec(spec)
        chargeur.exec_module(m)
    return m


class DiagNpm(Base):
    def setUp(self):
        super().setUp()
        self.m = charger_diag()

    def npm(self, version="12.2.1", engines=ENGINES, paquet=True):
        """Faux npm installé comme le vrai (PRÉFIXE/lib/node_modules/npm, lien dans faux/), ou un simple script."""
        if not paquet:
            self.programme("npm")
            return
        n = self.racine / "npmpkg/lib/node_modules/npm"
        (n / "bin").mkdir(parents=True)
        (n / "package.json").write_text(json.dumps({"name": "npm", "version": version, "engines": {"node": engines}}))
        (n / "bin/npm-cli.js").write_text(FAUX)
        (n / "bin/npm-cli.js").chmod(0o755)
        os.symlink(n / "bin/npm-cli.js", self.faux / "npm")

    def bilan(self, node="v20.20.2", codex=False, npmv="12.2.1", verrou=True):
        self.programme("node")
        if codex:
            os.symlink(self.systeme / "bin/codex", self.faux / "codex")
        b = self.m.Bilan(couleurs=False)
        if verrou:
            self.verrouiller()
        env = {"PATH": f"{self.faux}:{self.outils}", "NC_TEST_CALLS": str(self.calls), "NC_TEST_NODEV": node,
               "NC_TEST_NPMV": npmv, "HOME": str(self.home)}
        with mock.patch.dict(os.environ, env):
            self.m.npm_node(b)
        return b

    def test_npm_12_et_node_trop_ancien(self):
        self.npm()
        for node in ("v20.20.2", "v22.10.0", "v23.3.0", "v24.1.0"):
            with self.subTest(node=node):
                b = self.bilan(node)
                self.assertEqual(b.attention, 1)
                self.assertIn("npm récent, mais Node trop ancien : mets Node à jour (npm 12.2.1 demande Node "
                              f"{ENGINES}, Node {node[1:]} installé)", b.texte())
        self.assertFalse([c for c in self.appels() if c[0] == "npm"])   # version lue dans package.json, sans lancer npm

    def test_node_assez_recent_ou_npm_plus_ancien_silence(self):
        self.npm()
        for node in ("v22.22.2", "v24.15.0", "v26.0.0"):
            self.assertEqual(self.bilan(node).lignes, [], node)

    def test_npm_11_sur_node_20_silence(self):
        self.npm("11.6.0", "^20.17.0 || >=22.9.0")
        self.assertEqual(self.bilan("v20.20.2").lignes, [])

    def test_npm_sans_package_json_seuils_de_npm_12(self):
        self.npm(paquet=False)
        b = self.bilan("v20.1.0", npmv="12.0.1")
        self.assertIn("npm récent, mais Node trop ancien", b.texte())
        self.assertIn(f"npm 12.0.1 demande Node {ENGINES}", b.texte())
        self.assertEqual(self.bilan("v24.15.0", npmv="12.0.1").lignes, [])

    def test_cli_d_ia_dans_un_prefixe_non_inscriptible(self):
        self.npm()
        b = self.bilan("v24.15.0", codex=True)
        self.assertEqual(b.attention, 1)
        texte = b.texte()
        self.assertIn(f"la CLI codex (@openai/codex) est dans {self.systeme}, où tu ne peux pas écrire : "
                      "elle ne pourra pas se mettre à jour seule", texte)
        self.assertIn(f"npm config set prefix ~/.local ; npm install -g @openai/codex ; puis, quand tu veux : "
                      f"sudo npm uninstall -g --prefix {self.systeme} @openai/codex (install.sh le propose)", texte)

    def test_les_deux_alertes(self):
        self.npm()
        self.assertEqual(self.bilan("v20.20.2", codex=True).attention, 2)

    def test_cli_inscriptible_ou_paquet_de_la_distribution_silence(self):
        self.npm()
        self.assertEqual(self.bilan("v24.15.0", codex=True, verrou=False).lignes, [])
        with mock.patch.object(self.m, "_paquet_proprio", return_value="codex-distrib"):
            self.assertEqual(self.bilan("v24.15.0", verrou=True).lignes, [])

    def test_sans_npm_silence(self):
        b = self.bilan("v20.20.2", codex=True)
        self.assertEqual(b.lignes, [])


class IaTrouveLesCli(unittest.TestCase):
    """prefix=~/.local met les commandes dans ~/.local/bin ; l'ancien conseil (~/.npm-global) reste trouvé."""

    def test_local_bin_et_npm_global(self):
        with tempfile.TemporaryDirectory(prefix="nc-npm-ia-") as d:
            home = Path(d)
            for dossier, prog in ((".local/bin", "codex"), (".npm-global/bin", "gemini")):
                (home / dossier).mkdir(parents=True)
                (home / dossier / prog).write_text("#!/bin/sh\nexit 0\n")
                (home / dossier / prog).chmod(0o755)
            (home / ".config/nc").mkdir(parents=True)
            (home / ".config/nc/reglages.conf").write_text("LANGUE=fr\n")
            (home / "run").mkdir(mode=0o700)
            env = {"HOME": str(home), "PATH": str(home / "rien"), "NC_LANGUE": "fr", "NC_IA_EN_LIGNE": "1",
                   "XDG_RUNTIME_DIR": str(home / "run"), "XDG_CACHE_HOME": str(home / "cache"),
                   "NC_POWER_SUPPLY": "secteur", "NC_PROFIL": "balanced"}
            r = subprocess.run([sys.executable, str(NCIA), "etat", "--json"], env=env, capture_output=True, text=True,
                               timeout=30)
            self.assertEqual(r.returncode, 0, r.stderr)
            dispo = {i["nom"] for i in json.loads(r.stdout)["ias"] if i["disponible"]}
            self.assertIn("Codex", dispo)
            self.assertIn("Gemini CLI", dispo)
            self.assertNotIn("node_modules", NCIA.read_text().split("os.environ[\"PATH\"]", 1)[1].split("\n\n", 1)[0])


if __name__ == "__main__":
    unittest.main()
