"""Réglages du PC depuis Telegram (/nc, nc_noctalia) : liste blanche, mode local seulement, table fixe de commandes,
confirmation des actions sensibles, jamais de shell. Les commandes de l'hôte sont remplacées par un enregistreur."""
import asyncio
import os
from pathlib import Path
import types
import unittest
from unittest import mock

REPO = Path(__file__).resolve().parents[1]
SOURCE = REPO / "home/.local/share/nc-jarvis/server/nc_noctalia.py"


def module():
    m = types.ModuleType("nc_noctalia_test")
    m.__file__ = str(SOURCE)
    exec(compile(SOURCE.read_text(), str(SOURCE), "exec"), m.__dict__)
    return m


class Noctalia(unittest.TestCase):
    def setUp(self):
        self.m = module()
        self.m._en_attente.clear()
        self.appels = []
        self.reponses = {}
        async def executer(argv, delai=20):
            self.appels.append(list(argv))
            return self.reponses.get(argv[0], (0, "ok " + " ".join(argv)))
        self.m.executer = executer
        self.env = mock.patch.dict(os.environ, DEPLOY_MODE="local")
        self.env.start()
        self.addCleanup(self.env.stop)

    def nc(self, texte, chat=1, maintenant=1000.0):
        return asyncio.run(self.m.commande(texte, chat, maintenant))

    def test_etat_et_aide(self):
        r = self.nc("")
        self.assertTrue(r.startswith("✅"), r)
        self.assertEqual([a[0] for a in self.appels], ["nc-sysinfo", "nc-sysinfo", "powerprofilesctl", "nc-reglages", "nc-paquets"])
        self.assertIn("/nc energie", self.nc("aide"))
        self.assertIn("Commande inconnue", self.nc("danser"))
        self.assertIn("Action inconnue", asyncio.run(self.m.agir("rm", []))["output"])

    def test_energie_theme_fond_reglage(self):
        self.assertTrue(self.nc("energie").startswith("✅"))
        self.assertEqual(self.appels[-1], ["powerprofilesctl", "get"])
        self.nc("energie eco")
        self.assertEqual(self.appels[-1], ["powerprofilesctl", "set", "power-saver"])
        self.nc("energie Performance")
        self.assertEqual(self.appels[-1], ["powerprofilesctl", "set", "performance"])
        self.assertIn("Profil", self.nc("energie turbo"))
        self.nc("theme clair")
        self.assertEqual(self.appels[-1], ["nc-reglages", "set", "--distant", "THEME_MODE", "light"])
        self.nc("fond")
        self.assertEqual(self.appels[-1], ["noctalia", "msg", "wallpaper", "random"])
        self.nc("reglage ILE_STYLE")
        self.assertEqual(self.appels[-1], ["nc-reglages", "get", "ILE_STYLE"])
        self.nc("reglage ILE_STYLE noir")
        self.assertEqual(self.appels[-1], ["nc-reglages", "set", "--distant", "ILE_STYLE", "noir"])
        n = len(self.appels)
        self.assertIn("ne se change pas à distance", self.nc("reglage FONDS_DOSSIER ~/Images/Fonds d'écran"))
        self.assertEqual(len(self.appels), n, "hors liste blanche : rien n'est lancé")
        n = len(self.appels)
        self.assertIn("Réglage", self.nc("reglage ile_style noir"))
        self.assertIn("Réglage", self.nc("reglage $(rm) x"))
        self.assertEqual(len(self.appels), n, "clé invalide : rien n'est lancé")
        self.nc("reglage THEME_MODE $(touch x); rm -rf /")
        self.assertEqual(self.appels[-1], ["nc-reglages", "set", "--distant", "THEME_MODE", "$(touch x); rm -rf /"], "la valeur est un argument, jamais un shell : nc-reglages la refuse")
        self.nc("maj")
        self.assertEqual(self.appels[-1], ["nc-paquets"])
        self.reponses["nc-reglages"] = (1, "nc-settings: value rejected")
        self.assertTrue(self.nc("theme sombre").startswith("❌"))

    def test_ecran_sensible_avec_confirmation(self):
        self.nc("ecran")
        self.assertEqual(self.appels[-1], ["nc-ecrans", "etat"])
        self.nc("ecran miroir")
        self.assertEqual(self.appels[-1], ["nc-ecrans", "miroir"])
        n = len(self.appels)
        r = self.nc("ecran pc", chat=7, maintenant=1000)
        self.assertTrue(r.startswith("⚠️"), r)
        self.assertEqual(len(self.appels), n, "action sensible : rien avant la confirmation")
        self.assertIn("Rien à confirmer", self.nc("oui", chat=8, maintenant=1001), "un autre chat ne confirme pas")
        self.assertIn("Rien à confirmer", self.nc("oui", chat=7, maintenant=1000 + 121), "confirmation expirée")
        self.nc("ecran externe", chat=7, maintenant=2000)
        r = self.nc("oui", chat=7, maintenant=2060)
        self.assertTrue(r.startswith("✅"), r)
        self.assertEqual(self.appels[-1], ["nc-ecrans", "externe"])
        self.assertIn("Rien à confirmer", self.nc("oui", chat=7, maintenant=2061), "une confirmation ne sert qu'une fois")
        self.assertIn("Mode", self.nc("ecran off"))

    def test_mode_serveur_et_liste_blanche(self):
        with mock.patch.dict(os.environ, DEPLOY_MODE="server"):
            r = self.nc("energie eco")
        self.assertIn("mode serveur", r)
        self.assertEqual(self.appels, [])
        reponses = []
        class Message:
            async def reply_text(self, texte):
                reponses.append(texte)
        update = types.SimpleNamespace(effective_user=types.SimpleNamespace(id=42), effective_chat=types.SimpleNamespace(id=42), message=Message())
        tb = types.SimpleNamespace(_is_allowed=lambda uid: uid == 42)
        handler = self.m.handler(tb)
        asyncio.run(handler(update, types.SimpleNamespace(args=["energie", "eco"])))
        self.assertEqual(self.appels[-1], ["powerprofilesctl", "set", "power-saver"])
        self.assertTrue(reponses[-1].startswith("✅"))
        update.effective_user.id = 43
        asyncio.run(handler(update, types.SimpleNamespace(args=["energie", "performance"])))
        self.assertEqual(reponses[-1], "⛔ Accès non autorisé.")
        self.assertEqual(self.appels[-1], ["powerprofilesctl", "set", "power-saver"], "utilisateur refusé : rien lancé")
        # Revue SRV-03 : la confirmation se mesure à l'heure des messages, pas à celle du traitement
        import datetime
        update.effective_user.id = 42
        date = lambda t: datetime.datetime.fromtimestamp(t, datetime.timezone.utc)
        update.message.date = date(5000)
        asyncio.run(handler(update, types.SimpleNamespace(args=["ecran", "externe"])))
        update.message.date = date(5000 + 3600)                 # « oui » envoyé une heure plus tard
        asyncio.run(handler(update, types.SimpleNamespace(args=["oui"])))
        self.assertIn("Rien à confirmer", reponses[-1])
        self.assertNotEqual(self.appels[-1], ["nc-ecrans", "externe"])

    def test_execution_reelle_sans_shell(self):
        m = module()      # executer réel, avec un faux programme dans BIN
        with mock.patch.object(m, "BIN", Path(mock.mock_open.__module__ and "/nonexistent")):
            code, sortie = asyncio.run(m.executer(["/bin/echo", "a b", "$(echo c)"]))
        self.assertEqual((code, sortie), (0, "a b $(echo c)"))
        code, sortie = asyncio.run(m.executer(["/nonexistent/prog"]))
        self.assertEqual(code, 127)
        code, sortie = asyncio.run(m.executer(["/bin/sleep", "5"], delai=0.2))
        self.assertEqual((code, sortie), (124, "Délai dépassé"))


if __name__ == "__main__":
    unittest.main()
