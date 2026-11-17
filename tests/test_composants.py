"""Section « Composants » de nc-reglages : état de chaque composant optionnel, boutons à argv fixe, plugins nc-* manquants.
Tout est isolé (faux HOME, faux outils, faux noctalia) ; rien ne touche au vrai ~ ni à la vraie config."""
import os
import re
import runpy
import subprocess
import tempfile
import unittest
import warnings
from pathlib import Path
from unittest.mock import patch

REPO = Path(__file__).resolve().parents[1]
NC_REGLAGES = REPO / "home/.local/bin/nc-reglages"
PLUG = ".local/share/noctalia/plugins"


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        h = self.home = Path(self.tmp.name)
        (h / ".config/noctalia").mkdir(parents=True)
        (h / "tmp").mkdir()
        (h / "bin").mkdir()
        self.env = dict(HOME=str(h), XDG_CONFIG_HOME=str(h / ".config"), XDG_DATA_HOME=str(h / ".local/share"),
                        XDG_STATE_HOME=str(h / ".local/state"), XDG_CACHE_HOME=str(h / ".cache"), TMPDIR=str(h / "tmp"),
                        NC_LANGUE="fr", PATH=str(h / "bin"))
        with patch.dict(os.environ, self.env), warnings.catch_warnings():
            warnings.simplefilter("ignore", ResourceWarning)
            self.nc = runpy.run_path(str(NC_REGLAGES))
        faux = type("S", (), {k: getattr(subprocess, k) for k in dir(subprocess) if not k.startswith("__")})
        faux.run = staticmethod(lambda *a, **k: subprocess.CompletedProcess(a, 0, "", ""))
        self.nc["appliquer_noctalia"].__globals__["subprocess"] = faux
        # un faux dépôt avec trois plugins
        self.depot = h / "depot"
        for n in ("nc-aaa", "nc-bbb", "nc-garmin"):
            (self.depot / "home" / PLUG / n).mkdir(parents=True)
            (self.depot / "home" / PLUG / n / "plugin.toml").write_text('id = "x"\n')
        (h / ".config/nc").mkdir(parents=True)
        (h / ".config/nc/depot").write_text(str(self.depot) + "\n")

    def appel(self, nom, *a):
        with patch.dict(os.environ, self.env):
            return self.nc[nom](*a)

    def outil(self, nom):
        f = self.home / "bin" / nom
        f.write_text("#!/bin/sh\n")
        f.chmod(0o755)

    def conf(self, enabled):
        (self.home / ".config/noctalia/config.toml").write_text(
            "[plugins]\nenabled = [%s]\n" % ", ".join('"%s"' % e for e in enabled))


class Detection(Base):
    def manquants(self, depot, installes, actifs):
        return self.nc["plugins_manquants"](depot, installes, actifs)

    def test_present_et_active(self):
        self.assertEqual(self.manquants(["nc-aaa"], {"nc-aaa"}, ["nc/aaa"]), [])

    def test_present_pas_active(self):
        self.assertEqual(self.manquants(["nc-aaa"], {"nc-aaa"}, []), ["nc-aaa"])

    def test_dossier_absent(self):
        self.assertEqual(self.manquants(["nc-aaa"], set(), ["nc/aaa"]), ["nc-aaa"])

    def test_optionnels_ignores(self):
        self.assertEqual(self.manquants(["nc-garmin", "nc-ile"], set(), []), [])

    def test_noms_hostiles_dans_la_config(self):
        for h in ("../x", "nc-a/b", "", "nc/../x"):
            self.assertEqual(self.manquants(["nc-aaa"], {"nc-aaa"}, [h, "nc/aaa"]), [], h)

    def test_depot_ignore_les_noms_hostiles(self):
        (self.depot / "home" / PLUG / "nc-A b").mkdir()
        (self.depot / "home" / PLUG / "autre").mkdir()
        self.assertEqual(sorted(self.appel("plugins_depot")), ["nc-aaa", "nc-bbb", "nc-garmin"])


class Etats(Base):
    def etats(self, vals=None):
        return {c[0]: c for c in self.appel("composants", vals or {})}

    def test_garmin(self):
        self.assertEqual(self.etats()["garmin"][3], "absent")
        py = self.home / ".local/share/nc/garmin-venv/bin/python"
        py.parent.mkdir(parents=True)
        py.write_text("")
        py.chmod(0o755)
        e = self.etats()["garmin"]
        self.assertEqual((e[3], e[5]), ("desactive", ["nc-reglages", "set", "GARMIN_ACTIF", "oui"]))
        self.assertEqual(self.etats({"GARMIN_ACTIF": "oui"})["garmin"][3], "installe")

    def test_garmin_installer_est_laction_existante(self):
        e = self.etats()["garmin"]
        self.assertEqual(e[5], self.appel("garmin_installer_argv"))
        self.assertIn("nc-garmin installer --texte", " ".join(e[5]))

    def test_vpn_et_outils(self):
        self.assertEqual(self.etats()["vpn-nord"][5], ["nc-vpn", "installer-client", "nord"])
        self.outil("mullvad")
        e = self.etats()
        self.assertEqual((e["vpn-mullvad"][3], e["vpn-mullvad"][5]), ("installe", None))
        self.assertEqual(e["vpn-proton"][5], ["nc-vpn", "installer-client", "proton"])

    def test_claude_firefox_jarvis(self):
        e = self.etats()
        self.assertEqual(e["claude"][5], ["nc-claude", "installer"])
        self.assertEqual(e["firefox"][5], ["nc-firefox", "installer"])
        self.assertEqual(e["jarvis"][5], ["nc-reglages", "set", "NOEUD_JARVIS", "oui"])
        e = self.etats({"FIREFOX_STYLE": "oui", "NOEUD_JARVIS": "oui"})
        self.assertEqual((e["firefox"][3], e["jarvis"][3]), ("installe", "installe"))

    def test_assistant(self):
        self.assertEqual(self.etats()["assistant"][3], "absent")
        (self.home / ".config/nc/assistant.conf").write_text("x\n")
        self.assertEqual(self.etats()["assistant"][3], "installe")

    def test_chaque_argv_est_fixe_et_sans_texte_libre(self):
        for c in self.appel("composants", {}):
            if c[5]:
                self.assertTrue(all(isinstance(x, str) for x in c[5]))
                self.assertNotIn("shell", " ".join(c[5]))


class Plugins(Base):
    def lignes(self):
        self.conf(["nc/aaa"])
        (self.home / PLUG / "nc-aaa").mkdir(parents=True)
        return {x["cle"]: x for x in self.appel("catalogue_composants", {})}

    def test_bouton_plugin_argv_fixe(self):
        l = self.lignes()
        self.assertNotIn("plugin:nc-aaa", l)
        self.assertEqual(l["plugin:nc-bbb"]["commande"], ["nc-reglages", "activer-plugin", "nc-bbb"])
        self.assertNotIn("plugin:nc-garmin", l)

    def test_nom_inconnu_refuse(self):
        for h in ("nc-zzz", "nc-aa", "nc-aaa/../x", "../nc-aaa", "nc-aaa ", ""):
            with self.assertRaises(ValueError, msg=h):
                self.appel("activer_plugin", {}, h)
        self.assertFalse((self.home / PLUG).exists())

    def test_activation_copie_et_ecrit_sans_perdre_les_autres_lignes(self):
        self.conf(["nc/aaa", "nc/launcher"])
        self.appel("activer_plugin", {}, "nc-bbb")
        self.assertTrue((self.home / PLUG / "nc-bbb/plugin.toml").is_file())
        vals = self.appel("lire")
        self.assertEqual(vals.get("PLUGINS_NC"), "nc-bbb")
        self.appel("appliquer_noctalia", vals)
        t = (self.home / ".config/noctalia/zy-reglages.toml").read_text()
        m = re.search(r"enabled = \[(.*?)\]", t, re.S)
        self.assertIsNotNone(m)
        for n in ("nc/aaa", "nc/launcher", "nc/bbb"):
            self.assertIn(n, m.group(1))

    def test_catalogue_complet_a_la_section(self):
        self.conf([])
        cat = self.appel("catalogue", {})
        self.assertTrue(any(x["section"] == "Composants" for x in cat))
        self.assertFalse(any(x["cle"] == "PLUGINS_NC" for x in cat))


if __name__ == "__main__":
    unittest.main()
